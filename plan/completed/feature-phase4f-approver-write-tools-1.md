---
goal: Phase 4F — approve_dar + reject_dar HITL write tools with scope enforcement
version: 1.0
date_created: 2026-04-24
owner: Stephane
status: 'Deprecated'
tags: [feature, phase4, agent, write-tools, approver, hitl]
---

# Introduction

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red) — superseded by plan/spike-stock-stack-validation-1.md (2026-04-28)

Phase 4F adds the two approver-side HITL write tools. Each enforces scope
in the tool layer (never in the prompt) and raises
`PermissionError("out_of_scope")` for cross-scope attempts. Exit criterion:
status transitions correct; out-of-scope raises; HITL decorator verified.

Spec: `docs/prd-phase4-write-agent.md` §3 Tool Requirements, §4 Sub-phase
4F, §5 RISK "scope-enforcement bug".

## 1. Requirements & Constraints

- **REQ-001**: `agent_app/tools.py` must expose
  `approve_dar(dar_id, reason, ctx)` and
  `reject_dar(dar_id, reason, ctx)` decorated with
  `@tool(approval_mode="always_require")`. `reason` is optional for
  approve, required for reject.
- **REQ-002**: Both tools load the caller via `ctx.kwargs["delegate_id"]`.
  Scope check:
  - `DELEGATION_HEAD`: DAR's `approval_status` must equal
    `PENDING_DELEGATION_HEAD` AND the DAR's delegate must share the
    caller's `delegation_id`.
  - `SECRETARIAT`: DAR's `approval_status` must equal
    `PENDING_SECRETARIAT`.
  - Any other role, or scope mismatch → raise
    `PermissionError("out_of_scope")`.
- **REQ-003**: `approve_dar` flips `approval_status` →
  `APPROVED`; commits; returns JSON with `id`, `approval_status`,
  `approved_by`, `approved_at`, `reason`.
- **REQ-004**: `reject_dar` flips `approval_status` → `REJECTED`; stores
  `reason`; commits; returns JSON with `id`, `approval_status`,
  `rejected_by`, `rejected_at`, `reason`.
- **REQ-005**: If the `DocumentAccessRight` model does not already have
  `approved_by`, `approved_at`, `rejected_by`, `rejected_at`, `reason`
  columns, add them in `shared/database.py`; else reuse. TASK-001 must
  introspect first.
- **REQ-006**: Both tools must be appended to `ALL_TOOLS`.
- **CON-001**: On any exception mid-transaction rollback and re-raise
  (mirror 4A REQ-005).
- **PAT-001**: Reuse the scope-filter predicate from 4E to compute whether
  a DAR is in scope; do not duplicate logic. Extract to a
  `_assert_dar_in_scope(dar, approver)` helper in `agent_app/tools.py`.

## 2. Implementation Steps

### Implementation Phase 1 — Model columns (if needed)

- GOAL-001: DAR table has audit columns needed by approve/reject.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Introspect `DocumentAccessRight` (`shared/database.py` line ~334). If any of `approved_by`, `approved_at`, `rejected_by`, `rejected_at`, `reason` is missing, add as nullable columns. Update the Phase 4E seed if needed to leave the columns null. | | |
| TASK-002 | Update `tests/shared/test_database.py` to cover the new columns' nullability + roundtrip. | | |

### Implementation Phase 2 — approve_dar / reject_dar

- GOAL-002: Both tools implemented with shared scope helper.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | In `agent_app/tools.py` add `_assert_dar_in_scope(dar, approver) -> None` helper raising `PermissionError("out_of_scope")`. Reuse scope predicate semantics from 4E. | | |
| TASK-004 | Implement `approve_dar(dar_id, reason, ctx)`. Load approver + DAR; call `_assert_dar_in_scope`; flip status; stamp `approved_by` + `approved_at = datetime.now(timezone.utc)` + `reason`; commit; return JSON. Rollback on exception. | | |
| TASK-005 | Implement `reject_dar(dar_id, reason, ctx)`. Same pattern but flip to `REJECTED` and require non-empty reason (raise `ValueError` if empty). | | |
| TASK-006 | Append both to `ALL_TOOLS`. | | |

### Implementation Phase 3 — Unit tests

- GOAL-003: Status transitions + HITL + scope + rollback + visibility
  consequence covered.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Extend `tests/agent_app/test_approver_tools.py` with `TestApproveDar`: head approves own-delegation DAR → status `APPROVED` + audit fields set; head approves foreign-delegation DAR → raises `PermissionError`; secretariat approves secretariat-scope DAR; non-approver raises. | | |
| TASK-008 | Add `TestRejectDar`: happy paths; empty reason raises `ValueError`; out-of-scope raises. | | |
| TASK-009 | Add `TestHITLEnforcementApprover`: introspect `approve_dar.approval_mode == "always_require"` + `reject_dar.approval_mode == "always_require"`. | | |
| TASK-010 | Add `TestVisibilityPropagation`: approve a DAR for a Restricted document and assert `is_document_visible(delegate_id, doc, session) == True`; reject and assert `False`. Visibility via `shared/business_rules.is_document_visible`. | | |
| TASK-011 | Add `TestRollbackOnApproverError`: monkeypatch `session.commit` to raise; assert status stays `PENDING_*`. | | |
| TASK-012 | Run full suite: `pytest`. | | |

## 3. Alternatives

- **ALT-001**: Single `decide_dar(dar_id, decision, reason, ctx)` tool.
  Rejected — PRD calls for two distinct tools; easier for model to drive
  and matches HITL dialog clarity.

## 4. Dependencies

- **DEP-001**: Phase 4E merged (list_pending_dars + scope helper
  precedent).
- **DEP-002**: `shared/business_rules.is_document_visible` — present
  (Phase 2A).

## 5. Files

- **FILE-001**: `shared/database.py` — optional DAR audit columns
- **FILE-002**: `agent_app/tools.py` — 2 tools + 1 helper (~120 lines)
- **FILE-003**: `tests/shared/test_database.py` — new column tests (if
  added)
- **FILE-004**: `tests/agent_app/test_approver_tools.py` — extensions
  (~250 added lines)

## 6. Testing

- **TEST-001**: `TestApproveDar` — scope + status + audit
- **TEST-002**: `TestRejectDar` — scope + reason validation
- **TEST-003**: `TestHITLEnforcementApprover` — decorator arg
- **TEST-004**: `TestVisibilityPropagation` — approve → visible; reject →
  invisible
- **TEST-005**: `TestRollbackOnApproverError` — transaction integrity

## 7. Risks & Assumptions

- **RISK-001**: DAR audit columns may require schema migration in prod
  paths. Mitigation: SQLite dev rebuild only; document as future
  Alembic work if prod ever ships.
- **ASSUMPTION-001**: `approval_status=APPROVED` is the universal
  "visible" gate in `is_document_visible`. Verify in TASK-010.

## 8. Related Specifications / Further Reading

- `docs/prd-phase4-write-agent.md` §3 Tool Requirements + Scope Enforcement
- Phase 4E plan: `plan/feature-phase4e-approver-seed-list-tool-1.md`
- Phase 4G plan: `plan/feature-phase4g-approver-prompt-brief-badge-1.md`
