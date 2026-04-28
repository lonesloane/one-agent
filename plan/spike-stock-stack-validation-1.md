---
goal: Validate the stock `microsoft/agent-framework` + `agent_framework_ag_ui` + CopilotKit V2 stack via a sequence of isolated spike projects, so that ONE-MP can be rebuilt on a foundation we actually understand instead of one we are forcing to behave.
version: 1.0
date_created: 2026-04-28
owner: Stephane
status: 'Planned'
tags: [spike, architecture, agent_framework, copilotkit, hitl, ag_ui]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

After several days of debugging FINDING-4C-007 (HITL approval-replay leak)
and Phase 4 shim-removal regressions, the conclusion is that ONE-MP's
agent layer was built by guessing the intended use of
`agent_framework_ag_ui` + CopilotKit and patching every disagreement
with a custom shim. The stack is not broken; our integration is.

This plan defines a sequence of small, throwaway spike projects that
each validate one assumption about the stock stack. Each spike is a
fresh repo under `/home/stephane/Playground/GenAI/spikes/`,
self-contained, with one tool/feature/scenario, no shared code with
ONE-MP. Spikes run in order; later spikes depend on lessons from
earlier ones. If a spike fails, we file an upstream issue with a 30-line
repro before any workaround — different muscle than "patch around it".

When all spikes pass clean, ONE-MP rebuilds on the validated wiring.
Each shim currently in `agent_app/server.py` maps to a spike that
proves its replacement.

---

## Context for the next session (read this first if you forget)

If you (the assistant) are picking this up cold, here is everything you
need to make sense of it without re-deriving:

### What ships in ONE-MP today (branch `main`)

- Phases 1A/1B/2A-D/3A-E shipped (data layer, classical Flask app,
  delegation editor, wizard, e2e suite, AG-UI server, CopilotKit V2
  frontend, brief logic). All unit + e2e tests green on `main`.
- Phase 4A (write tools), 4B (server prompt), 4C (frontend HITL
  partial) merged. Phase 4 UI polish (OECD theme) merged.
- Memories index: `~/.claude/projects/-home-stephane-Playground-GenAI-copilot/memory/MEMORY.md`.
  Key entries to rehydrate context: `project_phase3_status`,
  `project_phase4a_status`, `project_phase4b_status`,
  `project_phase4c_status`, `reference_ag_ui_integration`,
  `reference_copilotkit_v2_migration`, `reference_function_invocation_context`.

### What failed and why we are spiking

- Branch `fix/phase4c-hitl-orphan-tool-result` (worktree
  `.worktrees/bug-phase4c-orphan/`) tried to fix the post-approval
  follow-up turn 400 ("No tool output found for function call call_…")
  via 7 server-side shims plus a custom Next.js middleware. Phase 2 of
  the previous plan (fix in middleware, not server) reduced the
  symptom but Phase 4 (delete shims) regressed every time.
- Diagnosis lives in `plan/finding-4c-007-hitl-approval-replay.md`
  (this same folder). Read it for the captured payload.
- Closing plan: `plan/bug-phase4c-hitl-replay-fix-and-shim-reduction-1.md`
  (this same folder, status Completed but with paused tasks). Read its
  TASK-017/018/023 outcomes — they document which shim probes regressed
  and how.

### Current pinned versions (as of 2026-04-28, branch `fix/phase4c-hitl-orphan-tool-result`)

- Python:
  - `agent-framework==1.2.0`
  - `agent-framework-core==1.2.0`
  - `agent-framework-ag-ui==1.0.0b260424` (pinned in `pyproject.toml`)
  - `ag-ui-protocol==0.1.18`
  - `agent-framework-foundry>=1.0.0`
  - `fastapi>=0.110`, `uvicorn>=0.29`, `loguru`, `sqlalchemy>=2.0`
- Frontend (`agent_app/frontend/package.json`):
  - `@ag-ui/client ^0.0.52`
  - `@copilotkit/react-core ^1.56.2`
  - `@copilotkit/react-ui ^1.56.2`
  - `@copilotkit/runtime ^1.56.2`
  - `next 16.2.4`, `react 19.2.4`
- Foundry: `FOUNDRY_MODEL=gpt-4.1-mini` (must be in spike `.env`,
  per memory `reference_foundry_model_config`)

### Current 7 shims in `agent_app/server.py` (each → a spike)

| Shim | LOC ref | BUG-4C-NNN | Spike that validates removal |
|---|---|---|---|
| `_ApprovalRegistry` (`:` strip subclass) | server.py:25-56 | 003 | spike-04 |
| `_install_approval_delegate_id_injector()` (monkey-patches `agent_framework._tools._auto_invoke_function`) | server.py:71-104 | 004 | spike-03 |
| `_BoundAgent` (wraps Agent for `delegate_id` injection) | server.py:132-170 | 004 | spike-02 |
| `_fix_tool_call_ordering` (reorder tool/assistant) | server.py:173-217 | 001 | spike-05 |
| `_synthesize_orphan_tool_results` (fill `{}` stubs) | server.py:220-279 | 005 | spike-03 |
| `_thread_delegate_map` (HITL continuation identity fallback) | server.py:68 + reads | 002/004 | spike-02 |
| Custom `agent_endpoint` POST handler | server.py:349-427 | Phase 3B baseline | spike-01 |

### Library source for reference

- `_message_adapters.py`: `.venv/lib/python3.12/site-packages/agent_framework_ag_ui/_message_adapters.py`
  (lines 522, 547, 626-755 are the approval-detection / `confirm_changes`
  conversion path)
- `_agent_run.py`: same dir, function `run_agent_stream` (line 695),
  `_resolve_approval_responses` (line 407),
  `_clean_resolved_approvals_from_snapshot` (line 591), call site (line 820)

### Key behaviour that surprised us last time (do not re-derive)

- CopilotKit emits a `confirm_changes` toolCall *alongside* the
  underlying write tool's toolCall. Both ride in the same assistant
  message. The approval payload tool message is keyed by the
  `confirm_changes` call_id, not the wrapped function's call_id.
- `_clean_resolved_approvals_from_snapshot` (lib) only matches when the
  snapshot tool message's `tool_call_id` equals the resolved function's
  `call_id`. With the CopilotKit shape, those two ids never match → the
  cleaner is a no-op → snapshot stays dirty → next-turn replay fires.
- The bug we observed (`No tool output found for function call call_…`)
  looked like ordering but was caused by the M12 wipe at
  `_message_adapters.py:645` triggering on a stale approval, then the
  approval failing registry validation, then the wrapped function's
  tool result being absent → orphan toolCall → Foundry 400.
- `_thread_delegate_map` is still load-bearing: empirical evidence
  showed that on uvicorn restart (which wipes the in-memory map), HITL
  continuation POSTs surface "AG-UI request missing delegate_id in
  state" — CopilotKit really does drop `state` from continuation
  POSTs.

---

## 1. Requirements & Constraints

- **REQ-001**: Each spike MUST live under
  `/home/stephane/Playground/GenAI/spikes/spike-NN-<slug>/`. Independent
  Python venv (`uv venv` or `python -m venv`), independent
  `node_modules`, independent SQLite DB if needed. Zero imports from
  ONE-MP source.
- **REQ-002**: Each spike MUST have a `README.md` at its root with: the
  question being asked, the expected pass criterion, the actual
  outcome (filled in after the run), and any upstream issue number
  filed if it failed.
- **REQ-003**: Pin to the same versions as ONE-MP (see "Current pinned
  versions" above). When a spike succeeds and proves a behaviour, that
  pin is what ONE-MP migrates to.
- **REQ-004**: NO custom server-side shims for ordering, identity
  threading, approval registry, or message normalisation. The whole
  point is to use the stock wiring. If something does not work,
  document it; do NOT patch around.
- **CON-001**: Time-boxed exploration. Each spike has a one-line "give
  up after" criterion. We are buying knowledge, not building product.
  If a spike takes longer than its budget, file an upstream issue and
  move on.
- **CON-002**: Spikes are throwaway. No tests, no CI, no plan files of
  their own. Just `README.md` + the minimum code to answer the
  question.
- **CON-003**: Foundry credentials reused from ONE-MP. Symlink or copy
  `agent_app/.env` (`FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`) into
  each spike — do NOT commit.
- **GUD-001**: Before writing any spike code, query Context7
  (`/copilotkit/copilotkit` and
  `/websites/learn_microsoft_en-us_agent-framework`) for the canonical
  pattern that spike is testing. Per memory
  `feedback_context7_for_preview_libs`.
- **GUD-002**: When a spike succeeds, capture the working snippet
  verbatim in its README. That snippet is the contract ONE-MP must
  match when it migrates.
- **PAT-001**: One spike per question. Resist combining. Two questions
  = two spikes, even if they look related.

## 2. Implementation Steps

### Implementation Phase 0 — Workspace setup

- GOAL-000: A clean home for spikes that does not pollute ONE-MP.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-000 | `mkdir -p /home/stephane/Playground/GenAI/spikes`. Add `README.md` at the root listing what spikes exist, when started, current status (Open/Pass/Fail/Filed), and a one-line summary of what each proved or disproved. Update after every spike. |  |  |

### Implementation Phase 1 — Spike 01: stock endpoint

- GOAL-001: Prove that
  `add_agent_framework_fastapi_endpoint(app, agent=…, path="/")` plus a
  minimal CopilotKit V2 frontend can stream a single `whoami` tool to
  the chat UI without any custom Python or TypeScript shim. This is
  the baseline. If it does not work, nothing else matters.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-101 | Create `spikes/spike-01-stock-endpoint/`. Subfolders: `backend/` (FastAPI + agent), `frontend/` (Next 16 + CopilotKit V2). |  |  |
| TASK-102 | Backend: one Python file (`server.py`). Defines a `whoami` tool that returns `{"caller": "anonymous"}` (no identity threading yet). Constructs the agent. Wires `add_agent_framework_fastapi_endpoint` exactly as documented. NO custom POST handler. NO BoundAgent wrapper. NO middleware patches. |  |  |
| TASK-103 | Frontend: one page (`app/page.tsx`) that mounts `CopilotKitProvider` (V2) pointing at the backend. One `[[...path]]/route.ts` that wires a stock `HttpAgent` to `CopilotRuntime` — NO `agent.use(...)` middleware. Use `<CopilotChat />` from `@copilotkit/react-ui`. |  |  |
| TASK-104 | Run scenario: open chat, type "what is my identity?". Acceptance: agent invokes `whoami`, streams the result, chat shows the assistant text. No backend warnings or errors. Capture the working `route.ts` + `server.py` verbatim in `README.md`. |  |  |
| TASK-105 | If TASK-104 passes → Phase 2. If it fails → file upstream issue with 30-line repro and STOP this plan. |  |  |

### Implementation Phase 2 — Spike 02: identity via forwardedProps

- GOAL-002: Prove that per-request identity (e.g. `delegate_id`) can be
  threaded from frontend to a tool via `RunAgentInput.forwardedProps`
  (PR #5264, merged Apr 21 in `260424`) and read inside the tool
  through `session.metadata["forwarded_props"]`. If this works, ONE-MP
  retires `_BoundAgent` and `_thread_delegate_map`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-201 | Copy spike-01 → `spike-02-identity-forwarded-props/`. |  |  |
| TASK-202 | Frontend: in `route.ts` or wherever the agent input is built, set `forwardedProps: { delegate_id: "DEL-2026-0001" }` on every request. Use the v0.0.52 `@ag-ui/client` API (consult node_modules `index.d.ts` for the exact field — Context7 first). |  |  |
| TASK-203 | Backend: rewrite `whoami` to read `delegate_id` from `session.metadata.get("forwarded_props", {}).get("delegate_id", "")` via `FunctionInvocationContext` (per memory `reference_function_invocation_context`). Return `{"caller": delegate_id}`. NO server-side identity-injection middleware. |  |  |
| TASK-204 | Run: type "what is my identity?" Acceptance: response contains `DEL-2026-0001`. Test with two different delegate_ids in two browser tabs simultaneously to verify per-request isolation (the `_BoundAgent` was added because we thought identity needed to be bound to the agent instance — prove or disprove that). |  |  |
| TASK-205 | Edge: send a follow-up turn ("again?") and confirm `delegate_id` still threads through. CopilotKit may not re-send `forwardedProps` on continuation POSTs — verify this assumption empirically and document. |  |  |

### Implementation Phase 3 — Spike 03: HITL approval, stock pattern

- GOAL-003: Prove the framework's *intended* HITL pattern works
  end-to-end without `_install_approval_delegate_id_injector`,
  `_ApprovalRegistry`, `_synthesize_orphan_tool_results`, or our
  custom `confirm_changes` wrapper. Use whatever
  `requires_approval=True` (or equivalent) ships natively, and
  whatever CopilotKit `useCopilotAction` /
  `renderAndWaitForResponse` (or stock approval UI) ships natively.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-301 | Context7 query (mandatory before code): "agent_framework requires_approval", "Microsoft Agent Framework HITL approval pattern", "approval_request emit", "function_approval_request event". Capture the canonical Python pattern in spike's README. |  |  |
| TASK-302 | Context7 query: CopilotKit V2 stock UI for approval — likely `useCopilotAction({ available: 'remote', renderAndWaitForResponse: … })` or a built-in approval renderer. Avoid `useFrontendTool` if not on V2. |  |  |
| TASK-303 | Copy spike-02 → `spike-03-hitl-approval/`. Add a write tool `create_widget(name)` that just appends to an in-memory list. Mark it as requiring approval per the canonical pattern. |  |  |
| TASK-304 | Frontend: implement the canonical approve/deny UI per Context7 findings. NO custom `confirm_changes` wrapper. NO middleware to strip stale anything. |  |  |
| TASK-305 | Run scenario: "create widget Foo" → click Approve → verify tool fires with `name="Foo"` → assistant confirms. THEN send follow-up: "create widget Bar". Acceptance: second turn works, no Foundry 400, no replay warnings. This is the exact failure scenario from FINDING-4C-007; if stock pattern handles it, our `confirm_changes` wrapper was the cause. |  |  |
| TASK-306 | Run rejection scenario: "create widget Baz" → click Deny → assistant acknowledges. Send "create widget Qux" → must work. |  |  |
| TASK-307 | If approval execution path needs `delegate_id` (combining spike-02 lessons): verify `forwarded_props` still reaches the approved tool's `FunctionInvocationContext`. If not, this is the gap that needed `_install_approval_delegate_id_injector` — document precisely what differs. |  |  |

### Implementation Phase 4 — Spike 04: thread continuity & approval registry

- GOAL-004: Prove that `AgentSession(session_id=thread_id)` (PR #5384,
  merged Apr 22 in `260424`) keeps `_pending_approvals` keys consistent
  between registration and validation, retiring our `_ApprovalRegistry`
  `:`-strip subclass.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-401 | Copy spike-03 → `spike-04-thread-continuity/`. |  |  |
| TASK-402 | Add a `loguru` line in the framework path that logs every `_pending_approvals[key] = …` write and every `key in _pending_approvals` read (monkey-patch only for observability — remove before declaring success). Goal: see what `key` shape registers vs. validates. |  |  |
| TASK-403 | Run create + approve. Confirm both keys are `f"{thread_id}:{call_id}"` with the same `thread_id`. If they match without the `:`-strip, BUG-4C-003 is fixed upstream and `_ApprovalRegistry` retires. |  |  |
| TASK-404 | Multi-turn HITL: create A → approve → create B → approve → create C → approve. Acceptance: all three succeed; no "no matching pending approval request" warning; no Foundry 400. |  |  |
| TASK-405 | Restart backend mid-conversation (kill uvicorn, restart). Send a follow-up. Acceptance: either continuation works (registry persisted somewhere) OR documented failure → upstream issue → ONE-MP needs a session-store. |  |  |

### Implementation Phase 5 — Spike 05: multi-tool brief ordering

- GOAL-005: Prove that emitting 5+ tool calls in one assistant turn
  (`whoami` + 4× `get_agenda_documents` style) produces a message
  history the next turn can replay without `_fix_tool_call_ordering`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-501 | Copy spike-02 → `spike-05-multi-tool-brief/` (no HITL needed for this one). |  |  |
| TASK-502 | Add 4 read tools that return distinct stub data (`get_a`, `get_b`, `get_c`, `get_d`). System prompt: "On 'start', call all 4 in parallel + whoami, then summarise." |  |  |
| TASK-503 | Run with chrome-devtools MCP open (or playwright-cli network capture). Capture the AG-UI POST body of the FOLLOW-UP turn (e.g. user types "again"). Acceptance: tool messages immediately follow the assistant message that requested them in the replayed history; no out-of-order pairs; no `_fix_tool_call_ordering` needed. |  |  |
| TASK-504 | Edge: add a `time.sleep(0.5)` to one of the 4 tools so they finish out of order. Verify message order in the snapshot still aligns. |  |  |

### Implementation Phase 6 — Migration plan

- GOAL-006: Translate spike findings into a concrete migration plan
  for ONE-MP. Out of scope: actual migration. In scope: produce the
  plan document.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-601 | Author `plan/migration-onemp-to-stock-stack-1.md`. For each shim in the table above, cite the spike that proved its replacement and the verbatim canonical snippet. List shims that can NOT be retired (with the upstream issue number that explains why). |  |  |
| TASK-602 | Decide branch strategy: hard reset `agent_app/` to a stock skeleton (per spikes) and re-implement Phase 4 write tools on top, OR incremental shim-by-shim retirement. Likely the former, given how interleaved the shims are. |  |  |

## 3. Alternatives

- **ALT-001** (rejected): Drop the stack entirely (CopilotKit + AG-UI)
  and build custom SSE bridge. Fully discussed; user decided to give
  the stock stack one more go because they suspect we never used it
  correctly, not that it is broken. Keep this in pocket if spikes 1-3
  fail outright.
- **ALT-002** (rejected for now): Stay on the current branch and
  continue debugging FINDING-4C-007 with more shims. Two days of
  attempts shows diminishing returns; reset is cheaper than another
  shim.
- **ALT-003** (rejected): Write spikes inside `copilot/` repo. Would
  pollute git history and tempt copy-paste from ONE-MP. Spikes live
  under `Playground/GenAI/spikes/` instead.

## 4. Dependencies

- **DEP-001**: Foundry deployment with `FOUNDRY_MODEL=gpt-4.1-mini`
  reachable from the dev machine.
- **DEP-002**: Pinned versions listed under "Current pinned versions"
  above.
- **DEP-003**: Context7 access (`/copilotkit/copilotkit`,
  `/websites/learn_microsoft_en-us_agent-framework`) for canonical-
  pattern lookups.
- **DEP-004**: `playwright-cli` (already installed globally) for
  browser-driven verification, per memory `reference_playwright_cli`.

## 5. Files

- **FILE-001**: `/home/stephane/Playground/GenAI/spikes/` — root for
  all spike projects (does not exist yet).
- **FILE-002**:
  `/home/stephane/Playground/GenAI/spikes/README.md` — index of
  spikes with status, written first.
- **FILE-003**: Each `spike-NN-<slug>/README.md` — question, pass
  criterion, outcome.
- **FILE-004**: `plan/finding-4c-007-hitl-approval-replay.md`
  (this folder) — diagnosis, captured payload. Re-read before spike-03.
- **FILE-005**: `plan/bug-phase4c-hitl-replay-fix-and-shim-reduction-1.md`
  (this folder) — last attempt. Read TASK-017/018 outcomes.

## 6. Testing

Spikes are throwaway; they have no automated tests. The pass criterion
for each spike is the dry-run repro recipe in its TASK-NNN row, run
manually, with the working snippet captured in the spike's README. The
"test" is "did the canonical pattern work end-to-end without us
intervening".

ONE-MP's existing test suite (`pytest --ignore=tests/e2e
--ignore=tests/e2e_agent -q`, currently 258 passing) is unaffected
during spike work.

## 7. Risks & Assumptions

- **RISK-001**: Stock pattern for HITL might be the same
  `confirm_changes` wrapper we already use, just configured
  differently. If true, spike-03 has to find the right knob, not a
  different mechanism. Budget: 4h.
- **RISK-002**: `forwardedProps` may not survive CopilotKit's
  continuation POSTs (same root cause that makes us need
  `_thread_delegate_map`). Spike-02 TASK-205 must verify; if it does
  not survive, identity threading remains a problem and we may need a
  session store regardless.
- **RISK-003**: Multiple spikes may individually pass but interact
  badly when combined (e.g. forwardedProps + HITL). Spike-04 covers
  the combination; if it fails we know the combination is the gap.
- **RISK-004**: We waste time perfecting spikes instead of returning
  to ONE-MP. Mitigation: CON-001 time-box per spike, CON-002 throwaway
  ethic. If a spike has been "almost there" for two days, escalate.
- **ASSUMPTION-001**: `agent_framework_ag_ui` 1.0.0b260424 is the
  current best pin; Phase 1 of the previous plan validated this.
- **ASSUMPTION-002**: CopilotKit V2 (`@copilotkit/runtime/v2`) is the
  version we should use for new work; ONE-MP is already on V2 per
  memory `reference_copilotkit_v2_migration`.
- **ASSUMPTION-003**: Stock framework HITL pattern exists and is
  documented somewhere in the Microsoft Agent Framework docs. If
  Context7 can't find it, fall back to reading
  `agent-framework-core` source.

## 8. Related Specifications / Further Reading

- `plan/finding-4c-007-hitl-approval-replay.md` — root-cause diagnosis
  and captured payload. Read before spike-03.
- `plan/bug-phase4c-hitl-replay-fix-and-shim-reduction-1.md` — closing
  plan for the failed Phase 4 attempt. Outcomes of TASK-017/018/023
  document what we learned the hard way.
- `plan/feature-phase3b-ag-ui-server-1.md` (in `plan/completed/`) —
  the original wiring decisions for the AG-UI server. Reread to spot
  what we deviated from.
- Microsoft Agent Framework Python docs — Context7 ID
  `/websites/learn_microsoft_en-us_agent-framework`.
- CopilotKit docs — Context7 ID `/copilotkit/copilotkit`.
- AG-UI protocol spec — https://docs.ag-ui.com/.
- Upstream repo — https://github.com/microsoft/agent-framework. PRs
  referenced in this plan: #4232, #4548, #4550, #5201, #5264, #5384,
  #4717, #4758.
- Memories index — `~/.claude/projects/-home-stephane-Playground-GenAI-copilot/memory/MEMORY.md`.
- Library source: `.venv/lib/python3.12/site-packages/agent_framework_ag_ui/`.
