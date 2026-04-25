---
goal: Fix delegate identity leak — agent greets wrong delegate by name
version: 1.0
date_created: 2026-04-25
last_updated: 2026-04-25
owner: stephane
status: 'Planned'
tags: [bug, agent, tools, identity]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

ONE-MP Read Agent greets the user with the wrong delegate name regardless of
the dropdown selection. Symptom: dropdown selects "Alice Leblanc" but the
session brief says "Good day, Marie Dupont." Meeting list and document
visibility are correct.

**Root cause** — `agent_app/tools.py::lookup_delegate(delegate_id: str)`
takes `delegate_id` as a model-supplied parameter. The current delegate_id
is intentionally invisible to the model (injected via
`FunctionInvocationContext.kwargs`). The system prompt (step 1 of the
proactive brief) instructs the model to call
`lookup_delegate(current_delegate_id)`, but the model has no access to
that value, so it hallucinates — consistently picking `DEL-2026-0001`
(Marie Dupont, the first seed delegate, used as the example ID in the
tool's `Field(description=...)` on `tools.py:83`).

Other ctx-injected tools (`get_upcoming_meetings`,
`get_agenda_documents`) work correctly — that's why the meeting/document
content matches Alice while the greeting does not.

**Fix strategy (Option B from triage)** — split tool surface:

- Add a new `whoami(ctx)` tool that returns the current delegate profile
  via `FunctionInvocationContext` (mirrors the `get_upcoming_meetings`
  pattern).
- Keep `lookup_delegate(delegate_id)` for explicit lookups of *other*
  delegates (still useful, e.g. "who is DEL-2026-0007?").
- Update `SYSTEM_PROMPT` step 1 to call `whoami()`.

## 1. Requirements & Constraints

- **REQ-001**: Greeting must cite the delegate selected in the dropdown.
- **REQ-002**: `delegate_id` must remain invisible to the model
  (no exposure via tool schema or prompt).
- **REQ-003**: `lookup_delegate` must remain available for explicit
  by-id lookups of arbitrary delegates.
- **SEC-001**: No tool may return profile data for a delegate other than
  the one bound by `_BoundAgent` when ctx-injected.
- **CON-001**: No frontend, AG-UI protocol, or DB schema changes.
- **CON-002**: No new dependencies.
- **GUD-001**: Follow existing ctx-injection pattern from
  `get_upcoming_meetings` (`agent_app/tools.py:130-171`).
- **PAT-001**: Tool tests patch `agent_app.tools._engine` and call tools
  directly (see `tests/agent_app/test_tools.py:157`).
- **PAT-002**: ctx-injected tool tests construct a
  `FunctionInvocationContext` shim with `kwargs={"delegate_id": ...}`
  (see existing `TestGetUpcomingMeetings` class).

## 2. Implementation Steps

### Implementation Phase 1 — tool surface change

- GOAL-001: Add `whoami` ctx-injected tool, keep `lookup_delegate` as
  explicit-id lookup, register `whoami` in `ALL_TOOLS`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `agent_app/tools.py`, add `whoami(ctx: FunctionInvocationContext) -> str` decorated with `@tool(approval_mode="never_require")`. Body: read `delegate_id = ctx.kwargs.get("delegate_id", "")`; if empty return `json.dumps({"id": None, "full_name": None, "delegation_id": None, "committees": [], "access_rights": []})`; otherwise execute the same SQL/serialisation block currently in `lookup_delegate` (lines 95-124) but using the ctx delegate_id. Docstring: state that delegate identity is injected via `FunctionInvocationContext`, mirroring `get_upcoming_meetings`. | ✅ | 2026-04-25 |
| TASK-002 | In `agent_app/tools.py`, factor the shared serialisation block (lines 95-124) into a private helper `_serialize_delegate_profile(session, delegate_id) -> str` to avoid duplication between `whoami` and `lookup_delegate`. Both tools call this helper. Helper returns the same JSON shape; null-filled when not found. | ✅ | 2026-04-25 |
| TASK-003 | In `agent_app/tools.py::ALL_TOOLS` (line 214), add `whoami` to the list. Keep `lookup_delegate` in the list. Order: `get_delegation_info, lookup_delegate, whoami, get_upcoming_meetings, get_agenda_documents`. | ✅ | 2026-04-25 |

### Implementation Phase 2 — prompt update

- GOAL-002: Update `SYSTEM_PROMPT` to call `whoami()` instead of
  `lookup_delegate(current_delegate_id)`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | In `agent_app/agent.py::SYSTEM_PROMPT`, replace step 1 of "Proactive Session Brief" (lines 56-58). New text: `"1. Call whoami() to confirm the current delegate's identity and full name. The delegate identity is injected automatically into the session context."` Remove the now-stale phrase about `current_delegate_id`. | | |
| TASK-005 | In `agent_app/agent.py::SYSTEM_PROMPT`, add a one-line note after the access-classification rule clarifying `lookup_delegate(delegate_id)` is for *other* delegates, not the current one. Suggested wording: `"Use lookup_delegate(delegate_id) only when the user asks about a different delegate by ID; never use it to look up the current delegate (use whoami() for that)."` | | |

### Implementation Phase 3 — tests

- GOAL-003: Add unit tests for `whoami`; verify `lookup_delegate`
  unchanged; update brief-logic test if it asserts step-1 tool name.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | In `tests/agent_app/test_tools.py`, add class `TestWhoami` with two tests: (a) `test_returns_current_delegate_profile_via_ctx` — seed `DEL-T1` (Alice Test), build a `FunctionInvocationContext` shim with `kwargs={"delegate_id": "DEL-T1"}`, call `whoami(ctx)`, assert `full_name == "Alice Test"`, committees and DARs match seed; (b) `test_missing_delegate_id_in_ctx_returns_null_filled` — ctx with empty kwargs, assert null-filled structure. Mirror the FunctionInvocationContext shim used in `TestGetUpcomingMeetings`. | | |
| TASK-007 | In `tests/agent_app/test_tools.py::TestLookupDelegate`, add `test_does_not_consult_ctx` — call `lookup_delegate("DEL-T1")` with a ctx shim that has `kwargs={"delegate_id": "DEL-OTHER"}` (or simply no ctx kwarg, since `lookup_delegate` does not accept ctx); assert returned `id == "DEL-T1"`. Confirms that `lookup_delegate` is unaffected by ctx state. | | |
| TASK-008 | In `tests/agent_app/test_brief_logic.py`, search for any assertion that the agent's first tool call is `lookup_delegate`. If present, update to `whoami`. If the test only asserts behaviour (not tool name), no change needed. Run: `grep -n "lookup_delegate" tests/agent_app/test_brief_logic.py` to enumerate. | | |
| TASK-009 | Run full test suite: `pytest tests/agent_app/ -x`. Expected: all existing tests pass; new `TestWhoami` tests pass. Then `pytest tests/ -x` for regression. Then `ruff format . && ruff check --fix .`. | | |

### Implementation Phase 4 — manual verification

- GOAL-004: Confirm fix end-to-end against running stack.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Start backend: `uvicorn agent_app.server:app --port 8001`. Start frontend: `cd agent_app/frontend && npm run dev`. Open `http://localhost:3000`, select Alice Leblanc, observe brief. Expected: greeting cites "Alice Leblanc" (or her exact seed `full_name`). Switch dropdown to a different delegate; observe new thread; greeting reflects new selection. | | |
| TASK-011 | Optionally re-run e2e_agent suite if Foundry creds present: `pytest tests/e2e_agent/ -x`. | | |

## 3. Alternatives

- **ALT-001**: Add ctx fallback to existing `lookup_delegate` (signature
  `lookup_delegate(ctx, delegate_id: str = "")`). Rejected — overloads
  one tool with two responsibilities and risks the model ignoring the
  default and still hallucinating an ID. Single-purpose tools are
  clearer to the LLM and to readers.
- **ALT-002**: Inject `current_delegate_id` directly into the system
  prompt at request time (server-side string interpolation). Rejected —
  violates REQ-002 (delegate_id stays invisible to the model) and
  couples the prompt to per-request state, complicating caching.
- **ALT-003**: Have `_BoundAgent.run` rewrite `lookup_delegate` calls
  server-side to substitute the bound delegate_id. Rejected — opaque
  magic, hard to audit, masks the design intent of ctx injection.

## 4. Dependencies

- **DEP-001**: No new dependencies. Uses existing
  `agent_framework.FunctionInvocationContext` (already imported in
  `agent_app/tools.py:8`).

## 5. Files

- **FILE-001**: `agent_app/tools.py` — add `whoami` tool, factor
  `_serialize_delegate_profile` helper, register in `ALL_TOOLS`.
- **FILE-002**: `agent_app/agent.py` — update `SYSTEM_PROMPT` step 1
  and add disambiguation note.
- **FILE-003**: `tests/agent_app/test_tools.py` — new `TestWhoami`
  class, additional `TestLookupDelegate` test.
- **FILE-004**: `tests/agent_app/test_brief_logic.py` — possible
  tool-name update (verify first).

## 6. Testing

- **TEST-001**: `TestWhoami::test_returns_current_delegate_profile_via_ctx`
  — ctx-injected delegate_id returns matching profile.
- **TEST-002**: `TestWhoami::test_missing_delegate_id_in_ctx_returns_null_filled`
  — empty ctx returns null-filled structure.
- **TEST-003**: `TestLookupDelegate::test_does_not_consult_ctx` — explicit
  delegate_id arg overrides any ctx state.
- **TEST-004**: Manual e2e — dropdown selection drives greeting.

## 7. Risks & Assumptions

- **RISK-001**: Model may still call `lookup_delegate` with a hallucinated
  ID despite the prompt update. Mitigation: TASK-005 disambiguation
  sentence; if observed in manual test, tighten prompt further.
- **RISK-002**: Prompt-cache invalidation — `SYSTEM_PROMPT` change
  invalidates the Foundry prompt cache once. Acceptable, one-time cost.
- **ASSUMPTION-001**: Model honours updated step-1 instruction and emits
  `whoami` instead of `lookup_delegate`. Verified by TASK-010.
- **ASSUMPTION-002**: Existing `_BoundAgent.run` correctly threads
  `delegate_id` into `function_invocation_kwargs` for `whoami`
  identically to `get_upcoming_meetings`. Confirmed by reading
  `agent_app/server.py:64-80`.

## 8. Related Specifications / Further Reading

- `agent_app/tools.py:130-171` — reference ctx-injection pattern.
- `agent_app/server.py:50-80` — `_BoundAgent` ctx threading.
- Memory: `reference_function_invocation_context.md` — FunctionInvocationContext
  pattern used in this codebase.
- Memory: `reference_phase3b_server_pattern.md` — `_BoundAgent` identity
  threading rationale.
