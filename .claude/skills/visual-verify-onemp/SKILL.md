---
name: visual-verify-onemp
description: Browser-driven end-to-end check of the ONE-MP web app via playwright-cli. Use when verifying an agent_app/ change in the running UI — backend tool surface, SYSTEM_PROMPT behavior, brief content, identity threading, or any behavior unit tests can't cover. Triggers on /visual-verify, "verify in browser", "check the brief", "test the agent UI", "run the agent end-to-end", or after merging an agent_app/ fix when you want eyes-on confirmation.
---

# Visual Verify — ONE-MP Web App

Browser-driven sanity check of the running stack. Driver is **playwright-cli**
(global npm `@playwright/cli`). Snapshots land on disk as YAML; grep them
instead of dumping DOM into context. chrome-devtools MCP remains the fallback
for SSE/network deep-dive only.

## When to use

- Code change in `agent_app/` that affects the brief, tool calls, or
  identity threading — unit tests pass but the model behavior is the real
  spec.
- Suspected regression in the streamed brief, dropdown switch, or
  tool-call accordion.
- Manual TASK in a plan file that says "open the browser and confirm X".

## When NOT to use

- Pure DB / shared / classical_app changes — exercise via Flask UI or
  pytest, not the agent stack.
- Frontend-only CSS / typography changes — open the page directly, no
  brief re-run needed.
- No Foundry creds / model env — brief fails with `DeploymentNotFound`.
  Check `agent_app/.env` has `FOUNDRY_MODEL` and `FOUNDRY_PROJECT_ENDPOINT`
  first.

## When to fall back to chrome-devtools MCP

- Need raw network inspection (SSE event shape, AG-UI payloads, request
  headers) — `list_network_requests` / `get_network_request` have no
  playwright-cli equivalent.
- Lighthouse / performance trace.
- Otherwise prefer playwright-cli — token cost lower, snapshot stored on
  disk not piped through context.

## Playbook

### 0. One-time install

```bash
npm install -g @playwright/cli@latest
playwright-cli install --skills    # writes .claude/skills/playwright-cli/SKILL.md
```

### 1. Pre-flight ports

```bash
ss -tlnp 2>/dev/null | grep -E ':(3000|8001) '
```

Pre-existing backend on `:8001` likely runs **main-checkout** code (editable
install registered the main path). When verifying a worktree fix, that
backend will not exercise your change. Kill it; record original command
for later restart.

```bash
pkill -f 'uvicorn agent_app.server'
```

Frontend on `:3000` reusable — pure renderer. Restart only if change
touches `agent_app/frontend/`.

### 2. Launch backend from the right cwd

Venv at project root, editable-installed. **cwd-import precedence** — uvicorn
launched from worktree dir loads worktree `agent_app/` package, no reinstall.

```bash
cd <worktree-or-main-checkout>
source /home/stephane/Playground/GenAI/copilot/.venv/bin/activate
set -a && source agent_app/.env && set +a
nohup uvicorn agent_app.server:app --port 8001 \
  > /tmp/uvicorn-verify.log 2>&1 < /dev/null &
disown
sleep 4
ss -tlnp | grep ':8001 '
tail -8 /tmp/uvicorn-verify.log
```

Verify right code loaded:

```bash
python -c "import agent_app.tools as t; print(t.__file__)"
```

Path must be inside worktree, not main checkout.

### 3. Harvest seed data

```bash
curl -s http://127.0.0.1:8001/api/delegates | python -m json.tool
```

Note exact `id` strings (`DEL-2026-XXXX`) and `full_name`. **`select`
command takes the option `value` (delegate ID), not the label.** `full_name`
still used as snapshot grep anchor.

### 4. Drive the browser (playwright-cli)

```bash
playwright-cli open http://localhost:3000
# Snapshot YAML at .playwright-cli/page-<timestamp>.yml; cmd echoes path.
```

Find the combobox ref (typically `e9` in current layout):

```bash
playwright-cli snapshot 2>&1 | grep -B1 -A3 "Acting as\|combobox"
```

Wait for first brief — non-blocking via `run_in_background`:

```bash
# Bash run_in_background=true:
until playwright-cli snapshot 2>&1 \
  | grep -qE "Good day|Hello |Dear |nothing new|no new"; do
    sleep 3
done && echo "BRIEF_READY"
```

Capture greeting + tool calls:

```bash
playwright-cli snapshot 2>&1 | grep -B1 -A2 "Good day\|Hello\|Dear\|paragraph"
```

Switch delegate (use ID, not label):

```bash
playwright-cli select e9 "DEL-2026-0006"      # Ana Souza
# Re-arm wait loop for the new greeting; greeting wording is non-deterministic.
until playwright-cli snapshot 2>&1 \
  | grep -qE "Good day, Ana|Hello Ana|Dear Ana|Hi Ana"; do
    sleep 3
done
playwright-cli snapshot 2>&1 | grep -B1 -A2 "Ana Souza\|paragraph"
```

### 5. Assertions

From snapshot grep:

- **Positive:** greeting contains selected delegate's `full_name`.
- **Negative:** greeting does NOT contain any other delegate's name.
  Canonical leak symptom: `"Marie Dupont"` showing when Alice selected
  (Marie was first seed delegate + the example ID in `lookup_delegate`'s
  `Field` description, hence the default hallucination).
- **Tool-call accordion:** `button "<tool> COMPLETE"` rows in expected
  order. Canonical brief chain: `whoami → get_upcoming_meetings →
  get_agenda_documents (×N)`.

```bash
playwright-cli snapshot 2>&1 | grep -E "COMPLETE|whoami|get_upcoming|get_agenda"
```

### 6. Console + network artifacts

playwright-cli auto-writes per-call logs:

```bash
ls -lt .playwright-cli/ | head        # console-*.log, page-*.yml, network-*
```

Inspect for runtime errors:

```bash
grep -i "error\|warn" .playwright-cli/console-*.log | tail -20
```

### 7. Cleanup

```bash
playwright-cli close
pkill -f 'uvicorn agent_app.server'
# Restore user's main backend if killed:
cd /home/stephane/Playground/GenAI/copilot
source .venv/bin/activate
set -a && source agent_app/.env && set +a
nohup uvicorn agent_app.server:app --reload --port 8001 \
  > /tmp/uvicorn-main.log 2>&1 < /dev/null &
disown
```

## Gotchas

- **`select` takes option value, not label.** chrome-devtools `fill` took
  the visible label string; playwright-cli `select e9 "<value>"` needs
  the `<option value=...>` attribute — i.e. the delegate `id`
  (`DEL-2026-0006`), not `"Ana Souza (Brazil — DELEGATE)"`.
- **Greeting wording varies.** Real runs produced both `"Good day, Alice
  Leblanc."` and `"Hello Ana Souza,"` for the same prompt template. Wait
  loops must use a wide alternation: `Good day|Hello |Dear |Hi `.
- **Brief takes 30–45 s.** Four+ tool calls plus token streaming. Use
  `run_in_background` Bash with `until` loop, timeout ≥90 s.
- **Don't grep for the bare delegate name as readiness anchor.** It
  matches the dropdown `<option>` element instantly — false positive
  before brief streams. Anchor on greeting prefixes.
- **Snapshot file accumulates.** `.playwright-cli/` not gitignored by
  default — add it to `.gitignore` or `rm -rf .playwright-cli/` after
  cleanup.
- **`pkill` exits 144 in this sandbox** when killing only matching
  process. Treat 144 as success; verify with `ss -tlnp | grep ':8001 '`.

## Quick reference

| Step | Command |
|------|---------|
| Check ports | `ss -tlnp \| grep -E ':(3000\|8001) '` |
| Kill backend | `pkill -f 'uvicorn agent_app.server'` |
| Start backend | `cd <dir> && source .venv && source agent_app/.env && nohup uvicorn ... & disown` |
| Confirm code path | `python -c "import agent_app.tools as t; print(t.__file__)"` |
| Seed data | `curl -s :8001/api/delegates` |
| Open browser | `playwright-cli open http://localhost:3000` |
| Snapshot (grep on disk) | `playwright-cli snapshot 2>&1 \| grep ...` |
| Wait for brief | `until snapshot \| grep -qE 'Good day\|Hello \|Dear '; do sleep 3; done` (bg) |
| Pick delegate | `playwright-cli select e9 "DEL-2026-XXXX"` |
| Close | `playwright-cli close` |

Source playbook (chrome-devtools era): `docs/visual-verify-chrome-devtools-notes.md`.
