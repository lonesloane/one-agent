---
goal: Fix BUG-4C-001 — tool-result / tool-call message misordering that causes Foundry 400 errors on follow-up turns
version: 1.0
date_created: 2026-04-25
owner: Stephane
status: 'Planned'
tags: [bug, phase4, agent_app, server, copilotkit]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

CopilotKit v2 reconstructs AG-UI conversation history with `tool` (result)
messages appearing **before** the `assistant` message that contains the
matching `tool_calls`. On any follow-up turn after the initial brief, the
message array fed to `AgentFrameworkAgent.run()` has this reversed ordering.
The library's `_sanitize_tool_history` (in `agent_framework_ag_ui`) drops
out-of-order tool results rather than reordering them, leaving dangling
tool-call IDs in the assistant message. Azure AI Foundry rejects with:
`400 — No tool output found for function call <id>`.

**Fix**: reorder `input_data["messages"]` in `agent_endpoint` (server.py)
before passing to `protocol_runner.run()` — a single O(n) pass that
ensures every assistant tool-call message precedes its corresponding
tool-result messages. The library then receives correctly ordered input
and its deduplication / sanitisation logic works as intended.

Spec: `docs/BACKLOG.md` § Phase 4C dry-run findings — BUG-4C-001.

## 1. Requirements & Constraints

- **REQ-001**: After the fix, a follow-up user message sent after the
  initial brief must NOT produce a `400` from Foundry. The agent must
  complete its run and stream a valid reply.
- **REQ-002**: The reordering must be idempotent — correctly ordered
  messages pass through without modification.
- **REQ-003**: The fix must not affect the read-agent brief flow
  (first turn has no tool history to reorder).
- **REQ-004**: Full test suite (currently 243 tests) must remain green
  after the change.
- **CON-001**: Fix lives entirely in `agent_app/server.py`. No changes
  to the CopilotKit proxy route (`[[...path]]/route.ts`), `page.tsx`,
  or any library code.
- **CON-002**: `agent_framework_ag_ui` is a preview package — do not
  pin a new version or patch it; work around the issue in our code.
- **GUD-001**: Log the actual misordered payload at DEBUG level before
  patching (TASK-001) — capture the real shape so the algorithm matches
  reality, not memory.
- **PAT-001**: Helper function must be unit-tested with a synthetic
  fixture derived from the logged real payload (not invented).

## 2. Implementation Steps

### Implementation Phase 1 — Reproduce and capture real misorder shape

- GOAL-001: Confirm the exact AG-UI message shape that arrives at
  `agent_endpoint` on a follow-up turn so the fix algorithm is
  grounded in the actual payload.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `agent_app/server.py` `agent_endpoint`, add a temporary `logger.debug("AG-UI messages: %s", input_data.get("messages"))` line immediately after line 146 (`input_data = request_body.model_dump(...)`). Start uvicorn (`uvicorn agent_app.server:app --port 8001 --reload`), pick a `DELEGATION_EDITOR` persona, wait for brief, then send a follow-up message ("What documents are new?"). Capture the logged message list. Identify the exact index positions where a `role: "tool"` entry precedes the `role: "assistant"` entry whose `tool_calls` contains the matching `id`. Record the pattern (e.g. [tool, assistant] consecutive pair, or [tool, tool, assistant], etc.) — this drives the algorithm in TASK-003. | ✅ | 2026-04-25 |
| TASK-002 | Remove (or downgrade to `logger.trace`) the temporary debug log from TASK-001 once the payload shape is confirmed. Keep a comment referencing BUG-4C-001. | ✅ | 2026-04-25 |

### Implementation Phase 2 — Implement the fix

- GOAL-002: Add `_fix_tool_call_ordering` to `server.py` and wire it
  into `agent_endpoint`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | ✅ | 2026-04-25 | Add the following function to `agent_app/server.py` (before `_get_agent`, after `_BoundAgent`). Adjust the inner algorithm if TASK-001 reveals a more complex misorder shape than the standard pair: <br><br>```python<br>def _fix_tool_call_ordering(<br>    messages: list[dict[str, Any]],<br>) -> list[dict[str, Any]]:<br>    """Reorder messages so every assistant tool-call message<br>    precedes its tool-result messages.<br><br>    CopilotKit v2 may reconstruct conversation history with<br>    tool results before the assistant message that requested<br>    them. AgentFrameworkAgent._sanitize_tool_history drops<br>    out-of-order results rather than fixing the order, leaving<br>    dangling tool_call IDs that Foundry rejects with 400.<br>    """<br>    # Build map: call_id → index of the assistant message owning it<br>    call_to_asst: dict[str, int] = {}<br>    for i, msg in enumerate(messages):<br>        if msg.get("role") == "assistant":<br>            for tc in msg.get("tool_calls") or []:<br>                if isinstance(tc, dict) and tc.get("id"):<br>                    call_to_asst[str(tc["id"])] = i<br><br>    result: list[dict[str, Any]] = []<br>    skip: set[int] = set()<br>    for i, msg in enumerate(messages):<br>        if i in skip:<br>            continue<br>        if msg.get("role") == "tool":<br>            cid = str(msg.get("tool_call_id") or msg.get("toolCallId") or "")<br>            asst_idx = call_to_asst.get(cid, -1)<br>            if asst_idx > i:<br>                # Assistant message comes after its result — splice it in first<br>                result.append(messages[asst_idx])<br>                skip.add(asst_idx)<br>        result.append(msg)<br>    return result<br>``` | | |
| TASK-004 | ✅ | 2026-04-25 | In `agent_endpoint` (`agent_app/server.py` line ~146), apply the fix immediately after building `input_data` and before constructing `_BoundAgent`. Replace: <br><br>```python<br>input_data: dict[str, Any] = request_body.model_dump(exclude_none=True)<br>```<br><br>with:<br><br>```python<br>input_data: dict[str, Any] = request_body.model_dump(exclude_none=True)<br>if "messages" in input_data:<br>    input_data["messages"] = _fix_tool_call_ordering(<br>        input_data["messages"]<br>    )<br>```<br><br>This is the only call site; no other paths reach `protocol_runner.run()`. |

### Implementation Phase 3 — Unit tests

- GOAL-003: Lock the `_fix_tool_call_ordering` contract with a
  synthetic test fixture derived from the real payload shape
  captured in TASK-001.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | ✅ | 2026-04-25 | Create `tests/agent_app/test_server.py`. Import `_fix_tool_call_ordering` from `agent_app.server`. Write the following test cases (parametrize or separate methods — author's choice): <br>**Case A** — correct order unchanged: `[{role:"user"}, {role:"assistant", tool_calls:[{id:"c1", type:"function", function:{...}}]}, {role:"tool", tool_call_id:"c1", content:"..."}]` → output equals input. <br>**Case B** — single misordered pair fixed: `[{role:"user"}, {role:"tool", tool_call_id:"c1", content:"..."}, {role:"assistant", tool_calls:[{id:"c1",...}]}]` → output is `[user, assistant, tool]`. <br>**Case C** — multiple tools per assistant (all after assistant): input already correct, output unchanged. <br>**Case D** — multiple misordered pairs: two separate (tool, assistant) pairs both get fixed. <br>**Case E** — tool message with no matching call_id: message is preserved in place, no crash. <br>**Case F** — empty messages list: returns `[]`. |
| TASK-006 | ✅ | 2026-04-25 | Run `pytest tests/agent_app/test_server.py -v` — all new tests must pass. Then run `pytest --ignore=tests/e2e_agent --ignore=tests/e2e -q` — full suite (≥ 243 tests) must remain green. |

### Implementation Phase 4 — Dry-run verification

- GOAL-004: Confirm BUG-4C-001 is resolved end-to-end in the browser.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Start backend: `uvicorn agent_app.server:app --port 8001 --reload`. Start frontend: `cd agent_app/frontend && npm run dev` (port 3000). Pick a `DELEGATION_EDITOR` persona, wait for the brief to complete. Send a follow-up message ("What documents are new?"). Confirm: no `RUN_ERROR` event in the SSE stream; the chat pane shows an agent reply. | | |
| TASK-008 | Send a delegate-creation request ("Create a new delegate named Test User, email test@example.com, in delegation FRA, role DELEGATE."). Confirm the agent follows up with HITL tool-call step (approval dialog or prompt, depending on CopilotKit v2 rendering). Record whether FINDING-4C-002 (no `useHumanInTheLoop` hook) also needs action or auto-renders. | | |
| TASK-009 | Update `docs/BACKLOG.md` § "Phase 4C dry-run findings": mark BUG-4C-001 resolved with fix summary (`_fix_tool_call_ordering` in `server.py`); update FINDING-4C-002 with verification result from TASK-008. | | |

## 3. Alternatives

- **ALT-001**: Client-side sort in the Next.js proxy route (`[[...path]]/route.ts`). Rejected — TypeScript, framework-shaped file, requires touching CopilotKit runtime internals. Server-side fix owns the same choke point with less coupling.
- **ALT-002**: Pin a newer version of `agent_framework_ag_ui` that may fix the misorder upstream. Rejected — preview package; no known fix version; pinning a pre-release without validation risks new regressions.
- **ALT-003**: Patch `_sanitize_tool_history` behavior by subclassing `AgentFrameworkAgent`. Rejected — overengineered; the library drop-in approach would need to be maintained across version bumps.

## 4. Dependencies

- **DEP-001**: Phase 4A + 4B merged to main (done — 8280471 / 6fb4fed).
- **DEP-002**: `.env` with `FOUNDRY_MODEL=gpt-4.1-mini` and `DATABASE_PATH` present for dry-run.
- **DEP-003**: `node_modules` installed in `agent_app/frontend/` (no shared symlinks — Turbopack worktree bug).

## 5. Files

- **FILE-001**: `agent_app/server.py` — add `_fix_tool_call_ordering` function; call it in `agent_endpoint` after `model_dump`.
- **FILE-002**: `tests/agent_app/test_server.py` — new file; 6 unit-test cases for `_fix_tool_call_ordering`.
- **FILE-003**: `docs/BACKLOG.md` — update BUG-4C-001 status + FINDING-4C-002 verification result.

## 6. Testing

- **TEST-001**: `tests/agent_app/test_server.py` — 6 unit tests (Cases A–F) for `_fix_tool_call_ordering` covering idempotency, single pair fix, multi-tool, multi-pair, unknown call_id, empty input.
- **TEST-002**: Full unit suite (`pytest --ignore=tests/e2e_agent --ignore=tests/e2e -q`) — ≥ 243 tests green.
- **TEST-003**: Manual dry-run (TASK-007 + TASK-008) — follow-up message produces agent reply; HITL flow reachable.

## 7. Risks & Assumptions

- **RISK-001**: CopilotKit v2 may produce more complex misorder patterns (e.g. multiple consecutive (tool, tool, assistant) groups). Mitigation: TASK-001 captures the real shape before coding; algorithm can be extended from the single-pair base if needed.
- **RISK-002**: `_sanitize_tool_history` in the library may interact unexpectedly with a pre-sorted message list (e.g. double-counting). Mitigation: the library expects correctly ordered input; feeding it correct order is the intended usage per its docstring (`pending_tool_call_ids` tracks assistant→tool flow). Idempotency test (Case A) catches any such regression.
- **RISK-003**: FINDING-4C-002 (`useHumanInTheLoop` absence) may still block HITL after BUG-4C-001 is fixed. Mitigation: TASK-008 verifies whether V2Provider auto-renders for `function_approval_request`; if not, a separate plan item is filed before proceeding to Phase 4D.
- **ASSUMPTION-001**: The misorder is a consistent pattern (tool before its owning assistant) on every follow-up turn with tool history, not intermittent. Confirmed by dry-run observation (every follow-up turn fails).
- **ASSUMPTION-002**: `tool_call_id` (snake_case) is the field name in the AG-UI messages dict arriving at `agent_endpoint`. Fallback to `toolCallId` (camelCase) is included in the algorithm for safety.

## 8. Related Specifications / Further Reading

- `docs/BACKLOG.md` § Phase 4C dry-run findings
- `docs/prd-phase4-write-agent.md` § 2 (US-1 HITL AC)
- `agent_app/server.py` — `agent_endpoint` (line 121), `_BoundAgent` (line 50)
- `agent_framework_ag_ui/_message_adapters.py` — `_sanitize_tool_history` (line 29) — library function that drops misordered tool results instead of fixing them
- Phase 4C validation plan: `plan/feature-phase4c-create-frontend-hitl-1.md`
