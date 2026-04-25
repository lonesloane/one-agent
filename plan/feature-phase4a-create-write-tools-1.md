---
goal: Phase 4A — create-side write tools (create_delegate, create_document_access_rights) + identity threading + unit tests
version: 1.0
date_created: 2026-04-24
owner: Stephane
status: 'Planned'
tags: [feature, phase4, agent, write-tools, hitl]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 4A delivers the two create-side HITL write tools in `agent_app/tools.py`
with `approval_mode="always_require"`, editor identity injected via
`FunctionInvocationContext` (Phase 3A pattern), and unit tests covering DAR
routing across all 5 scenarios plus rollback-on-error. Exit criterion: tools
callable in isolation, HITL decorator arg verified by test, all 5 DAR
scenarios produce correct `classification_level` + `approval_status` via
`compute_default_access_level` + `determine_approval_route`.

Spec: `docs/prd-phase4-write-agent.md` §3 (Tool Requirements) and §4
(Sub-phase 4A exit criterion).

## 1. Requirements & Constraints

- **REQ-001**: `agent_app/tools.py` must expose `create_delegate` decorated
  with `@tool(approval_mode="always_require")`. Inputs: `full_name`, `email`,
  `delegation_id`, `membership_type` (from the delegation), `role`
  (`DelegateRole` value as string, defaults to `DELEGATION_EDITOR`). Returns
  JSON string with `id`, `full_name`, `delegation_id`, `role`.
- **REQ-002**: `agent_app/tools.py` must expose
  `create_document_access_rights` decorated with
  `@tool(approval_mode="always_require")`. Inputs: `delegate_id`,
  `committee_id`, `classification_level` (string enum value), `retroactive`
  (bool). Internally calls `compute_default_access_level` +
  `determine_approval_route` to derive the authoritative `classification_level`
  + `approval_status`. Returns JSON with `id`, `delegate_id`, `committee_id`,
  `classification_level`, `approval_status`, `retroactive`.
- **REQ-003**: Both write tools must consume `editor_id` via
  `FunctionInvocationContext` (`ctx.kwargs["delegate_id"]` — identity key
  unchanged from Phase 3A) and reject calls when the editor's
  `Delegate.role != DelegateRole.DELEGATION_EDITOR`, raising
  `PermissionError("Only delegation editors can create delegates/DARs")`.
- **REQ-004**: ID generation for the new `Delegate` must follow the existing
  `DEL-YYYY-XXXX` pattern (reuse the generator already used by
  `classical_app/routes/wizard_helpers.py` if exposed, else inline the same
  logic). DAR ID follows the existing `DAR-YYYY-XXXX` pattern.
- **REQ-005**: On any SQLAlchemy exception mid-transaction, session must
  rollback and the tool must re-raise. No partial writes.
- **CON-001**: No modifications to `shared/database.py`,
  `shared/business_rules.py`, or `shared/seed_data.py`. 4A is purely additive
  in `agent_app/tools.py`.
- **CON-002**: Existing read tools in `agent_app/tools.py` must remain
  unchanged and their unit tests green.
- **GUD-001**: Mirror Phase 3A tool module conventions: `_engine` module-level,
  `_Session(_engine)` per call, JSON-stringified return.
- **PAT-001**: `FunctionInvocationContext` param pattern from Phase 3A
  `get_upcoming_meetings` (ctx non-keyword param, model-invisible).
- **PAT-002**: DAR-routing encapsulation: always flow through
  `compute_default_access_level` and `determine_approval_route` — never
  hard-code.
- **RISK-001**: `compute_default_access_level` signature takes
  `MembershipType` + `committee_id` + `framework_agreements`; the tool must
  load the delegation + its FAs in the same session.

## 2. Implementation Steps

### Implementation Phase 1 — Helper + create_delegate

- GOAL-001: `create_delegate` implemented, editor-gated, tested.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `agent_app/tools.py` add helper `_assert_editor(ctx, session)` that loads the current delegate by `ctx.kwargs["delegate_id"]`, raises `PermissionError` if `role != DelegateRole.DELEGATION_EDITOR`. | ✅ | 2026-04-25 |
| TASK-002 | Add helper `_next_delegate_id(session)` that mirrors the `DEL-YYYY-XXXX` generator used by the classical wizard. Reuse existing helper if `from classical_app.routes.wizard_helpers import generate_delegate_id` is viable; otherwise inline with unit-test coverage. | ✅ | 2026-04-25 |
| TASK-003 | Implement `create_delegate(full_name, email, delegation_id, role, ctx)` decorated with `@tool(approval_mode="always_require")`. Validates editor via TASK-001, loads target delegation (404-style JSON error if missing), assigns ID via TASK-002, inserts `Delegate` row with given `role`. Commit + return JSON. | ✅ | 2026-04-25 |

### Implementation Phase 2 — create_document_access_rights

- GOAL-002: DAR creation tool with routing + rollback.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add helper `_next_dar_id(session)` mirroring `DAR-YYYY-XXXX` pattern. | | |
| TASK-005 | Implement `create_document_access_rights(delegate_id, committee_id, retroactive, ctx)` decorated with `@tool(approval_mode="always_require")`. Loads target delegate + delegation + framework_agreements; computes `classification_level = compute_default_access_level(...)`; derives `approval_status = determine_approval_route(classification_level, retroactive)`; inserts `DocumentAccessRight` row; commit; return JSON including derived fields. | | |
| TASK-006 | Wrap the DB work in try/except: on any `SQLAlchemyError` call `session.rollback()` and re-raise. | | |
| TASK-007 | Extend `ALL_TOOLS` list at bottom of `agent_app/tools.py` to include `create_delegate` + `create_document_access_rights`. | | |

### Implementation Phase 3 — Unit tests

- GOAL-003: Scenario matrix + HITL decorator arg + rollback covered.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | Create `tests/agent_app/test_write_tools.py`. Use the function-scoped engine fixture pattern from `tests/agent_app/test_tools.py` (`monkeypatch agent_app.tools._engine`). | | |
| TASK-009 | Add `TestCreateDelegate`: happy path (editor creates delegate → row present); non-editor caller (role=DELEGATION_HEAD fixture) raises `PermissionError`; unknown delegation returns structured JSON error. | | |
| TASK-010 | Add `TestCreateDocumentAccessRights` parametrised over the 5 PRD scenarios: (member General), (member Restricted), (partner General no-FA), (partner+FA → Restricted), (Confidential retroactive → PENDING_SECRETARIAT). Assert both `classification_level` and `approval_status` on the returned JSON AND on the persisted row. | | |
| TASK-011 | Add `TestHITLEnforcement`: introspect both tool objects' `approval_mode` attribute; assert it equals `"always_require"`. This guards against accidental regression. | | |
| TASK-012 | Add `TestRollbackOnError`: monkeypatch `session.commit` to raise; assert no `DocumentAccessRight` row persists and the original exception surfaces. | | |
| TASK-013 | Run full suite: `pytest` — all Phase 3 + 4A tests green. | | |

## 3. Alternatives

- **ALT-001**: Inline DAR-routing logic in the tool. Rejected — duplicates
  `shared/business_rules.py` and violates PAT-002.
- **ALT-002**: Pass `editor_id` as a visible tool parameter. Rejected — model
  could forge it; `FunctionInvocationContext` injection is the Phase 3A
  pattern.

## 4. Dependencies

- **DEP-001**: Phase 3 complete (merged 2026-04-22).
- **DEP-002**: `shared/business_rules.py` `compute_default_access_level` +
  `determine_approval_route` — already present (Phase 2A).
- **DEP-003**: Wizard ID-generation helpers — reuse if exposed.

## 5. Files

- **FILE-001**: `agent_app/tools.py` — extend with 2 write tools + 3 helpers
  (~150 added lines)
- **FILE-002**: `tests/agent_app/test_write_tools.py` — new, ~250 lines

## 6. Testing

- **TEST-001**: `TestCreateDelegate` — happy + non-editor reject + unknown
  delegation
- **TEST-002**: `TestCreateDocumentAccessRights` — 5-scenario matrix
- **TEST-003**: `TestHITLEnforcement` — decorator arg introspection
- **TEST-004**: `TestRollbackOnError` — transaction integrity

## 7. Risks & Assumptions

- **RISK-001**: `FunctionInvocationContext` kwarg name `delegate_id` already
  threads the *editor's* ID when the persona is an editor. Assumption
  confirmed via Phase 3B `_BoundAgent.run`.
- **ASSUMPTION-001**: Wizard ID-generator helpers are importable or trivially
  re-implementable; verify in TASK-002.

## 8. Related Specifications / Further Reading

- `docs/prd-phase4-write-agent.md` §3 Tool Requirements
- `agent_app/tools.py` — Phase 3A patterns
- `classical_app/routes/wizard_helpers.py` — ID generators + DAR routing
  reference
- Phase 4B plan: `plan/feature-phase4b-create-server-prompt-1.md`
