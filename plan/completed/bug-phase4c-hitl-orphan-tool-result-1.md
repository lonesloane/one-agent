---
goal: Fix BUG-4C-005 — orphan create_delegate / create_document_access_rights tool_call after HITL approval causes Foundry 400 on the next user turn; surface real tool error messages
version: 1.0
date_created: 2026-04-26
owner: Stephane
status: 'Deprecated'
tags: [bug, phase4, agent_app, server, hitl, copilotkit]
---

# Introduction

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red) — superseded by plan/spike-stock-stack-validation-1.md (2026-04-28)

After the BUG-4C-004 synthetic-`confirm_changes` pattern shipped, a HITL-
approved write tool (e.g. `create_delegate`) runs successfully on the server
and emits a `TOOL_CALL_RESULT` event over SSE — but the closing
`MESSAGES_SNAPSHOT` event lists tool messages **only** for the synthetic
`confirm_changes` call (`<uuid>` keyed on the approval request id), not for
the underlying real call (`call_<openai-id>`). CopilotKit persists from
`MESSAGES_SNAPSHOT`, so the next user turn ships a history with:

```
assistant.toolCalls = [call_Wr8por…(create_delegate), 8beb255a…(confirm_changes)]
tool messages       = [..., 8beb255a…]                ← call_Wr8por… dangling
```

Foundry rejects with `400 — No tool output found for function call call_Wr8por…`,
the SSE stream emits `RUN_ERROR{code:"ChatClientException", message:"Internal
streaming error."}`, and the chat surface visibly resets. This is the same
shape as BUG-4C-001 (dangling tool_call_id) but a different cause: not
client-side reordering, but a tool result that never makes it into
CopilotKit's persistent message log.

A second, smaller defect compounds the user pain: when any write tool
raises (e.g. `PermissionError` from `_assert_editor` when a non-editor
attempts a write), `agent_framework._tools._auto_invoke_function` returns
the literal string `"Error: Function failed."` with no detail unless
`include_detailed_errors=True` is set on the agent's
`FunctionInvocationConfiguration`. The model sees a generic failure and
hallucinates "operation failed without specific error message" — making
authorisation failures and validation failures indistinguishable to the
user.

**Fix**: extend `_fix_tool_call_ordering` (in `agent_app/server.py`) to
also synthesize a stub tool message for any assistant tool_call_id that
has no matching tool message — making the request well-formed before it
reaches Foundry. Separately, set `include_detailed_errors=True` on the
agent's `FunctionInvocationConfiguration` so authorisation/validation
errors surface to the model and ultimately the user.

Spec: this plan; live diagnosis 2026-04-26 from chrome-devtools dry-run
captured in run67/run70 SSE traces (Marie Dupont / DELEGATION_EDITOR
session, thread `89cc63e2-a2fd-43fa-b8c0-9d4ade864393`).

## 1. Requirements & Constraints

- **REQ-001**: After a successful HITL-approved write, the next user
  message in the same thread must NOT produce a `RUN_ERROR` /
  `ChatClientException`. The agent must complete its run and stream a
  reply that references the prior write outcome.
- **REQ-002**: When a write tool raises (e.g. `PermissionError`,
  `SQLAlchemyError`), the model must see the exception message verbatim
  in the function-result string, and the agent's text reply must surface
  it to the user (per the `## Failure reporting` system-prompt rule that
  already exists).
- **REQ-003**: The synthesis logic must be idempotent — well-formed
  histories (every assistant tool_call already has a matching tool
  message) pass through unchanged.
- **REQ-004**: Phase 4C "happy path" (single-tool HITL approve →
  follow-up turn) must continue to succeed end-to-end against Foundry.
- **REQ-005**: Full unit suite (currently 243 tests) must remain green
  after the change.
- **CON-001**: Fix lives in `agent_app/server.py` (history pre-process)
  and `agent_app/agent.py` (one config flag). No changes to the
  CopilotKit proxy route, no changes to library code, no patching of
  `agent_framework_ag_ui`.
- **CON-002**: `agent_framework_ag_ui` is a preview package — do not
  pin a new version or patch it; work around the issue in our code.
  Same constraint as BUG-4C-001.
- **GUD-001**: Capture the real misordered/orphaned payload at DEBUG
  level (TASK-001) before coding. The algorithm must match the actual
  request body shape, not memory.
- **PAT-001**: New synthesis branch must be unit-tested with a synthetic
  fixture derived from the logged real payload (same discipline as
  BUG-4C-001 PAT-001).

## 2. Implementation Steps

### Implementation Phase 1 — Reproduce and capture the orphan-tool-call payload

- GOAL-001: Confirm the exact AG-UI message shape that arrives at
  `agent_endpoint` on the user turn that follows a HITL-approved write,
  so the synthesis branch is grounded in the actual payload.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `agent_app/server.py` `agent_endpoint`, add a temporary `logger.debug("AG-UI messages: %s", input_data.get("messages"))` line immediately after `input_data = request_body.model_dump(...)`. Start uvicorn (`uvicorn agent_app.server:app --port 8001 --reload`), pick `Marie Dupont (France — DELEGATION_EDITOR)`, wait for brief, send `Please create a new delegate: full name X, email …, function delegate, delegation FRA, role DELEGATE.`, walk through the HITL dialog, approve. After the approval-execution run completes, send a follow-up message (`Now please assign access rights …`). Capture the logged message list of the follow-up request. Identify each assistant message that contains `tool_calls`/`toolCalls` and verify which `tool_call_id`s have NO matching `role: "tool"` entry. Record the pattern (always exactly one orphan per HITL round? variable count? prefix shape `call_*` vs UUID?) — drives the algorithm in TASK-003. | | |
| TASK-002 | Remove (or downgrade to `logger.trace`) the temporary debug log from TASK-001 once the payload shape is confirmed. Keep a comment referencing BUG-4C-005. | | |

### Implementation Phase 2 — Extend `_fix_tool_call_ordering` to synthesize orphan tool results

- GOAL-002: Make every assistant tool_call_id resolvable to a tool
  message before the request hits the protocol runner.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | In `agent_app/server.py`, extend `_fix_tool_call_ordering` (or split into a new helper `_synthesize_orphan_tool_results` that runs after the existing reorder pass). Algorithm: <br><br>1. Build set of all `tool_call_id` values from `role: "tool"` messages (both `tool_call_id` snake_case and `toolCallId` camelCase). <br>2. For every assistant message with `tool_calls`/`toolCalls`, for each `tc.id` not in that set: append a synthetic tool message after the assistant entry with `{"role": "tool", "tool_call_id": tc.id, "content": "{}"}` (empty-JSON placeholder; the prior assistant text already describes the outcome to the model). <br>3. Preserve insertion order; assistant message remains first as guaranteed by the existing reorder pass. <br><br>Update the docstring to reference both BUG-4C-001 (reorder) and BUG-4C-005 (synthesize). Reason comment must explain WHY the placeholder is empty (the AG-UI MESSAGES_SNAPSHOT drops the real result; the assistant text in the next message preserves user-visible context). | | |
| TASK-004 | Wire the new synthesis call into `agent_endpoint` immediately after the existing reorder call (single helper or two calls — author's choice; document in code if two). Reorder MUST run before synthesis so newly-spliced assistant entries are in the right position before we look for orphans. | | |

### Implementation Phase 3 — Surface tool exceptions

- GOAL-003: Model receives `Exception:` detail for every failed tool
  invocation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | In `agent_app/agent.py` `create_agent`, locate where the agent's `FunctionInvocationConfiguration` (or equivalent kwargs) is constructed and pass `include_detailed_errors=True`. If currently only the default config is used, add an explicit one. Verify against Context7 (`/websites/learn_microsoft_en-us_agent-framework`) that the field name and location have not changed in the current preview release. | | |
| TASK-006 | Add a regression unit test in `tests/agent_app/test_agent.py`: invoke a tool that raises `PermissionError` via the same path the agent would use; assert the returned `Content.from_function_result` payload contains the exception message string. If the path is hard to drive without an LLM, fall back to verifying the `FunctionInvocationConfiguration` carries `include_detailed_errors=True` after `create_agent()`. | | |

### Implementation Phase 4 — Unit tests for the synthesis branch

- GOAL-004: Lock the orphan-tool-result contract with synthetic fixtures
  derived from the real payload captured in TASK-001.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Extend `tests/agent_app/test_server.py`. Add cases (parametrize or separate methods): <br>**Case I** — single orphan: assistant has 2 tool_calls, only one has a matching tool message; synthesis adds the missing one with `content: "{}"` and `tool_call_id` set to the orphan id. <br>**Case J** — no orphans (idempotency): well-formed history passes through unchanged. <br>**Case K** — orphan precedes valid tool message in same assistant block: ordering preserved (reorder pass ran first). <br>**Case L** — multiple orphans across multiple assistant messages: each synthesized once. <br>**Case M** — camelCase `toolCalls` + camelCase `toolCallId` lookups: synthesis still works. <br>**Case N** — empty messages list: returns `[]` (no synthesis). | | |
| TASK-008 | Run `pytest tests/agent_app/test_server.py -v` — all new tests must pass. Then run `pytest --ignore=tests/e2e_agent --ignore=tests/e2e -q` — full suite (≥ 243 tests) must remain green. | | |

### Implementation Phase 5 — Dry-run verification

- GOAL-005: Confirm BUG-4C-005 is resolved end-to-end in the browser.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Start backend: `uvicorn agent_app.server:app --port 8001 --reload`. Start frontend: `cd agent_app/frontend && npm run dev`. Pick `Marie Dupont (France — DELEGATION_EDITOR)`, wait for brief. Send `Please create a new delegate …`, walk through HITL, approve. **Then** send a follow-up message (`Now please assign access rights for <new delegate> to EDU committee at GENERAL level.`). Confirm: no `RUN_ERROR`; agent emits a new `create_document_access_rights` tool_call; HITL dialog renders. | | |
| TASK-010 | Approve the DAR. Confirm DAR is written (`select * from document_access_rights where delegate_id='DEL-2026-NNNN'` returns the new row). Send a third follow-up (`Anything else I should know?`); confirm the run completes with a coherent reply that references the just-created delegate by name. | | |
| TASK-011 | Trigger the error-surfacing path: pick `Alice Leblanc (France — DELEGATE)` (non-editor), ask `Create a delegate named Test Person, email t@x.fr, function delegate, delegation FRA, role DELEGATE.` Walk through HITL, approve. Confirm the agent reply now includes the `PermissionError` message verbatim ("Only delegation editors can create delegates/DARs") rather than the prior generic "operation failed without specific error message". | | |
| TASK-012 | Update `docs/BACKLOG.md` § "Phase 4C dry-run findings": add BUG-4C-005 with fix summary (orphan-tool-result synthesis in `_fix_tool_call_ordering`) and BUG-4C-006 with fix summary (`include_detailed_errors=True`). | | |

## 3. Alternatives

- **ALT-001**: Frontend fix — intercept `TOOL_CALL_RESULT` events in the
  CopilotKit proxy route (`[[...path]]/route.ts`) and inject them into
  the persistent message log. Rejected — requires patching CopilotKit
  runtime internals and would not survive library upgrades.
- **ALT-002**: Drop the orphan tool_call from the assistant message
  instead of synthesizing a tool result. Rejected — loses the model's
  record that the call happened, leading to confused follow-ups
  ("did I create the delegate or not?"). Synthesis is conservative.
- **ALT-003**: Patch `_resolve_approval_call_id` / `_replace_approval_contents_with_results`
  in `agent_framework_ag_ui` to add the executed tool result to the
  outgoing `MESSAGES_SNAPSHOT`. Rejected — overengineered; same
  ALT-003 reasoning as BUG-4C-001 (preview package, drop-in
  maintenance burden).

## 4. Dependencies

- **DEP-001**: Phase 4C HITL frontend merged to main (done — 6e482b9).
- **DEP-002**: `.env` with `FOUNDRY_MODEL=gpt-4.1-mini` and
  `DATABASE_PATH` present for dry-run.
- **DEP-003**: `node_modules` installed in `agent_app/frontend/`.

## 5. Files

- **FILE-001**: `agent_app/server.py` — extend `_fix_tool_call_ordering`
  (or add `_synthesize_orphan_tool_results`); wire into `agent_endpoint`.
- **FILE-002**: `agent_app/agent.py` — set
  `include_detailed_errors=True` in `FunctionInvocationConfiguration`.
- **FILE-003**: `tests/agent_app/test_server.py` — add Cases I–N for the
  synthesis branch.
- **FILE-004**: `tests/agent_app/test_agent.py` — add regression test
  for `include_detailed_errors`.
- **FILE-005**: `docs/BACKLOG.md` — add BUG-4C-005 + BUG-4C-006 entries.

## 6. Testing

- **TEST-001**: `tests/agent_app/test_server.py` — Cases I–N (6 tests)
  for orphan-tool-result synthesis covering single, none, multi, mixed
  case, camelCase fallback, empty.
- **TEST-002**: `tests/agent_app/test_agent.py` — regression test for
  `include_detailed_errors=True`.
- **TEST-003**: Full unit suite — ≥ 243 + 7 new = ≥ 250 tests green.
- **TEST-004**: Manual dry-run (TASK-009..011) — follow-up turn after
  HITL produces no `RUN_ERROR`; DAR is written; PermissionError
  message reaches the user verbatim.

## 7. Risks & Assumptions

- **RISK-001**: A future `agent_framework_ag_ui` release may start
  including the real tool result in `MESSAGES_SNAPSHOT`, in which case
  our synthesis would create a duplicate. Mitigation: synthesis only
  fires when the tool message is missing; idempotency test (Case J)
  catches a regression where it would fire spuriously.
- **RISK-002**: Empty-JSON placeholder (`content: "{}"`) might confuse
  the model into thinking the operation returned nothing. Mitigation:
  TASK-010 verifies the assistant reply still references the created
  delegate by name (drawn from the prior assistant text). If the model
  gets confused, fall back to inserting the structured assistant text
  excerpt as the tool content.
- **RISK-003**: `include_detailed_errors=True` may leak stack-trace-
  flavoured text into user-visible chat. Mitigation: the framework
  already formats the message as `f"{message} Exception: {exc}"`; no
  full traceback. Manual TASK-011 confirms the visible string is just
  the exception message.
- **ASSUMPTION-001**: Every AG-UI HITL approval round produces exactly
  one orphan tool_call (the underlying real tool). Confirmed by
  diagnosis on 2026-04-26. If TASK-001 reveals batched approvals can
  produce multiple orphans in one assistant block, the algorithm
  generalises naturally — Case L covers this.
- **ASSUMPTION-002**: `tool_call_id` (snake_case) is the dominant field
  name; `toolCallId` (camelCase) appears on CopilotKit-emitted tool
  messages. Algorithm checks both, same as BUG-4C-001.

## 8. Related Specifications / Further Reading

- `plan/feature-phase4c-fix-message-ordering-1.md` — BUG-4C-001 (the
  reorder fix this plan extends)
- `docs/BACKLOG.md` § Phase 4C dry-run findings
- `agent_app/server.py` — `_fix_tool_call_ordering` (line 173),
  `agent_endpoint` (line 287)
- `agent_app/agent.py` — `create_agent` (system prompt + agent
  construction)
- `agent_framework._tools._auto_invoke_function` — error-formatting
  path (reads `config.get("include_detailed_errors", False)`)
- Live diagnosis 2026-04-26: chrome-devtools dry-run, thread
  `89cc63e2-a2fd-43fa-b8c0-9d4ade864393`, runs 67 (approval-execution,
  emits orphan) and 70 (follow-up, fails with `ChatClientException`).
