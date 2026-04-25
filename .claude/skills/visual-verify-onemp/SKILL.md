---
name: visual-verify-onemp
description: Browser-driven end-to-end check of the ONE-MP web app via chrome-devtools MCP. Use when verifying an agent_app/ change in the running UI — backend tool surface, SYSTEM_PROMPT behavior, brief content, identity threading, or any behavior unit tests can't cover. Triggers on /visual-verify, "verify in browser", "check the brief", "test the agent UI", "run the agent end-to-end", or after merging an agent_app/ fix when you want eyes-on confirmation.
---

# Visual Verify — ONE-MP Web App

Browser-driven sanity check of the running stack. Built from the obstacles
captured during the bug-delegate-identity-leak fix
(`docs/visual-verify-chrome-devtools-notes.md`).

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
- Frontend-only CSS / typography changes — open the page directly, you
  do not need the brief to re-run.
- No Foundry creds / model env — the brief will fail with
  `DeploymentNotFound`. Check `agent_app/.env` has `FOUNDRY_MODEL` and
  `FOUNDRY_PROJECT_ENDPOINT` first.

## Playbook

### 1. Pre-flight ports

```bash
ss -tlnp 2>/dev/null | grep -E ':(3000|8001) '
```

Pre-existing backend on `:8001` likely runs **main-checkout** code
(editable install registered the main path). If you are verifying a
worktree fix, that backend will not exercise your change. Kill it,
record the original command for later restart.

```bash
pkill -f 'uvicorn agent_app.server'
```

Frontend on `:3000` can usually be reused — it is a pure renderer. Only
restart frontend if your change touches `agent_app/frontend/`.

### 2. Launch backend from the right cwd

The venv is at project root and editable-installed. **cwd-import
precedence** wins — launching uvicorn from the worktree directory loads
the worktree `agent_app/` package, no reinstall needed.

```bash
cd <worktree-or-main-checkout>
source /home/stephane/Playground/GenAI/copilot/.venv/bin/activate
set -a && source agent_app/.env && set +a
nohup uvicorn agent_app.server:app --port 8001 \
  > /tmp/uvicorn-verify.log 2>&1 < /dev/null &
disown
sleep 4
ss -tlnp | grep ':8001 '          # confirm bound
tail -8 /tmp/uvicorn-verify.log   # confirm startup complete
```

Verify the right code is loaded:

```bash
python -c "import agent_app.tools as t; print(t.__file__)"
```

The path should be inside your worktree, not the main checkout.

### 3. Harvest seed data

```bash
curl -s http://127.0.0.1:8001/api/delegates | python -m json.tool
```

Note the exact `full_name` strings. You will use them as `wait_for`
anchors and as `fill` values for the dropdown.

### 4. Drive the browser (chrome-devtools MCP)

```
mcp__chrome-devtools__navigate_page → http://localhost:3000
mcp__chrome-devtools__take_snapshot      # find the combobox uid
mcp__chrome-devtools__wait_for           # wait for first brief
  text=["nothing new", "no new", "Good day", "Hello ", "Dear "]
  timeout=60000
mcp__chrome-devtools__take_snapshot      # capture greeting + tool-calls
```

⚠ Do NOT use the bare delegate full_name as a wait_for anchor — it
matches the dropdown `<option>` element and fires instantly, before the
brief streams. Anchor on chat-area phrasing (greeting prefixes,
"nothing new" / "no new"). The model wording is non-deterministic so
pass several candidates.

Switch delegate (no click-to-open needed — `fill` triggers React
onChange directly):

```
mcp__chrome-devtools__fill
  uid=<combobox uid>
  value="Marie Dupont (France — DELEGATION_EDITOR)"   # exact option label
mcp__chrome-devtools__wait_for                            \
  text=["Good day, Marie", "Hello Marie", "Dear Marie"]  \
  timeout=60000
mcp__chrome-devtools__take_snapshot
```

### 5. Assertions

From the snapshot, check:

- **Positive:** greeting contains the selected delegate's `full_name`.
- **Negative:** greeting does NOT contain any other delegate's name
  (the canonical leak symptom: `"Marie Dupont"` showing when Alice was
  selected — Marie is the first seed delegate, the example ID in
  `lookup_delegate`'s `Field` description, hence the default
  hallucination).
- **Tool-call accordion:** `DisclosureTriangle "<tool> COMPLETE"` rows
  appear in the expected order. For the brief the canonical chain is
  `whoami → get_upcoming_meetings → get_agenda_documents (×N)`.

### 6. Cleanup

```bash
pkill -f 'uvicorn agent_app.server'
# Restore the user's main backend if you killed it:
cd /home/stephane/Playground/GenAI/copilot
source .venv/bin/activate
set -a && source agent_app/.env && set +a
nohup uvicorn agent_app.server:app --reload --port 8001 \
  > /tmp/uvicorn-main.log 2>&1 < /dev/null &
disown
```

## Gotchas

- **`wait_for` text candidates must NOT collide with the dropdown.** The
  bare delegate name (`"Alice Leblanc"`) appears as a `<option>` element
  in the combobox and matches instantly — false positive, brief not yet
  streamed. Anchor on chat-area phrasing (greeting prefix +
  delegate-name, or `"nothing new"` / `"no new"`). The model picks
  greeting wording (`"Hello"` vs `"Good day"` vs `"Dear"`) freely, so
  pass several candidates.
- **Brief takes 30-45 s.** Four+ tool calls plus token streaming. Use
  `timeout: 45000` or higher on `wait_for`.
- **Bash tool resets cwd between calls.** Always start uvicorn commands
  with an explicit `cd <path>` in the same Bash invocation, or rely on
  the bash-tool default cwd being correct for that call.
- **`pkill` exits 144 in this sandbox** when it kills the only matching
  process. Treat 144 as success and verify with a follow-up
  `ss -tlnp | grep ':8001 '` rather than retrying.
- **Frontend `.env.local` is missing in fresh worktrees.** Don't bother
  recreating it for backend-only fixes — reuse the main-checkout
  frontend on `:3000`.

## Quick reference

| Step | Command / tool |
|------|----------------|
| Check ports | `ss -tlnp \| grep -E ':(3000\|8001) '` |
| Kill backend | `pkill -f 'uvicorn agent_app.server'` |
| Start backend | `cd <dir> && source .venv && source agent_app/.env && nohup uvicorn ... & disown` |
| Confirm code path | `python -c "import agent_app.tools as t; print(t.__file__)"` |
| Seed data | `curl -s :8001/api/delegates` |
| Navigate | `mcp__chrome-devtools__navigate_page` |
| Snapshot | `mcp__chrome-devtools__take_snapshot` |
| Wait for text | `mcp__chrome-devtools__wait_for text=["Good day, <name>","Hello <name>","nothing new"] timeout=60000` |
| Pick delegate | `mcp__chrome-devtools__fill uid=<combobox> value="<exact label>"` |

Full obstacle log: `docs/visual-verify-chrome-devtools-notes.md`.
