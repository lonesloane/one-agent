---
goal: Phase 4E — approver personas seed, DelegateRole enum extension, list_pending_dars read tool
version: 1.0
date_created: 2026-04-24
owner: Stephane
status: 'Deprecated'
tags: [feature, phase4, agent, seed, approver, read-tool]
---

# Introduction

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red) — superseded by plan/spike-stock-stack-validation-1.md (2026-04-28)

Phase 4E extends `DelegateRole` with `DELEGATION_HEAD` + `SECRETARIAT`,
seeds one persona of each, pre-seeds ~3-5 pending DARs spread across
`PENDING_DELEGATION_HEAD` and `PENDING_SECRETARIAT` statuses, and adds the
read-only `list_pending_dars` tool with scope enforcement. Exit criterion:
picker shows both new approver personas; `list_pending_dars` returns only
in-scope DARs; scope test passes.

Spec: `docs/prd-phase4-write-agent.md` §2 (Personas), §3 (Tool Requirements,
Scope Enforcement), §4 (Sub-phase 4E, Integration Points).

## 1. Requirements & Constraints

- **REQ-001**: `shared/database.py::DelegateRole` Enum must gain
  `DELEGATION_HEAD = "DELEGATION_HEAD"` and
  `SECRETARIAT = "SECRETARIAT"`. Existing `DELEGATION_EDITOR` stays as
  default.
- **REQ-002**: `shared/seed_data.py` must seed idempotently one
  `DELEGATION_HEAD` delegate (e.g. "DEL-2026-HEAD-FRA" in the FRA
  delegation) and one `SECRETARIAT` delegate (e.g. "DEL-2026-SEC-001",
  delegation TBD — reuse a sentinel "OECD" delegation if present, else
  document the placement in the task).
- **REQ-003**: `shared/seed_data.py` must seed 3-5 `DocumentAccessRight`
  rows with `approval_status IN (PENDING_DELEGATION_HEAD,
  PENDING_SECRETARIAT)` spread across multiple delegates and committees so
  the approver inbox is non-empty and non-overwhelming.
- **REQ-004**: `shared/business_rules.py` gains a new pure helper
  `count_pending_dars_for_approver(approver: Delegate, session) -> int`
  returning the in-scope pending DAR count for a given approver using the
  scope rule from the PRD (head → same delegation + PENDING_DELEGATION_HEAD;
  secretariat → all PENDING_SECRETARIAT).
- **REQ-005**: `agent_app/tools.py` gains
  `list_pending_dars(ctx)` decorated with
  `@tool(approval_mode="never_require")`. Reads `ctx.kwargs["delegate_id"]`,
  loads the approver, applies the scope rule, returns JSON array of
  `{id, delegate_id, delegate_full_name, committee_id, classification_level,
    approval_status, retroactive, created_at}`.
- **REQ-006**: `list_pending_dars` must return `[]` for any caller whose
  role is not `DELEGATION_HEAD` or `SECRETARIAT`.
- **REQ-007**: Add `list_pending_dars` to `ALL_TOOLS`.
- **CON-001**: Seed extension must be idempotent — running `seed_all()`
  twice leaves the DB unchanged after the first run. Test must cover this.
- **CON-002**: No modifications to the approval-status enum itself; the
  `PENDING_*` values are already present (Phase 2A).
- **GUD-001**: If a sentinel "OECD" or "SECRETARIAT" delegation does not
  already exist, add one in seed with `membership_type=MEMBER` and flag
  the decision in `docs/DECISIONS.md`.
- **PAT-001**: `list_pending_dars` follows the Phase 3A context-injection
  pattern; identity never visible to the model.

## 2. Implementation Steps

### Implementation Phase 1 — Schema + seed extension

- GOAL-001: Enum, personas, pending DARs present; idempotency preserved.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Edit `shared/database.py::DelegateRole` enum: add `DELEGATION_HEAD` and `SECRETARIAT` values. No migration needed (SQLite dev DB recreated from seed). | | |
| TASK-002 | In `shared/seed_data.py` add a `seed_approver_personas(session)` helper that inserts the two new delegates idempotently (check-then-insert). Call it from `seed_all()`. | | |
| TASK-003 | In `shared/seed_data.py` add `seed_pending_dars(session)` that inserts 3-5 `DocumentAccessRight` rows with `approval_status=PENDING_DELEGATION_HEAD` or `PENDING_SECRETARIAT`, spread across delegates + committees. Idempotent. Call from `seed_all()`. | | |
| TASK-004 | In `shared/business_rules.py` add `count_pending_dars_for_approver(approver, session)` with the scope rule. | | |
| TASK-005 | Update `tests/shared/test_seed_data.py` to cover: new roles persist; pending DARs seeded; `seed_all()` twice leaves row counts stable. | | |
| TASK-006 | Add `tests/shared/test_business_rules.py::TestCountPendingDarsForApprover` covering: head scoped to own delegation; secretariat scoped across all; editor returns 0. | | |

### Implementation Phase 2 — list_pending_dars tool

- GOAL-002: Scoped read tool wired into `ALL_TOOLS`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | In `agent_app/tools.py` implement `list_pending_dars(ctx)` per REQ-005 + REQ-006. Load approver via `_Session(_engine)`; branch by `approver.role`; apply scope filter in the SQL query (not post-filtering). | | |
| TASK-008 | Extend `ALL_TOOLS` to include `list_pending_dars`. | | |
| TASK-009 | Add `tests/agent_app/test_approver_tools.py::TestListPendingDars`: head sees only own-delegation pending; secretariat sees only PENDING_SECRETARIAT; editor sees `[]`; unknown delegate returns `[]`. | | |
| TASK-010 | Run full suite: `pytest`. | | |

## 3. Alternatives

- **ALT-001**: Enforce scope in a shared `business_rules.py` function and
  have the tool call it. Chosen — placed count helper in
  `business_rules.py` (REQ-004) but the list variant lives inline in
  `tools.py` because it shapes JSON for the agent. Revisit if a second
  caller emerges.
- **ALT-002**: Add a `role` column index. Rejected — premature; seed-scale
  data.

## 4. Dependencies

- **DEP-001**: Phase 4A–4D merged (create side shipped).
- **DEP-002**: `ApprovalStatus.PENDING_DELEGATION_HEAD` +
  `PENDING_SECRETARIAT` enum values present (Phase 2A).

## 5. Files

- **FILE-001**: `shared/database.py` — enum extension
- **FILE-002**: `shared/seed_data.py` — `seed_approver_personas` +
  `seed_pending_dars` (~80 added lines)
- **FILE-003**: `shared/business_rules.py` —
  `count_pending_dars_for_approver` (~20 lines)
- **FILE-004**: `agent_app/tools.py` — `list_pending_dars` (~50 lines)
- **FILE-005**: `tests/shared/test_seed_data.py` — extensions
- **FILE-006**: `tests/shared/test_business_rules.py` — new test class
- **FILE-007**: `tests/agent_app/test_approver_tools.py` — new file

## 6. Testing

- **TEST-001**: Seed idempotency + new personas present
- **TEST-002**: `TestCountPendingDarsForApprover` — scope arithmetic
- **TEST-003**: `TestListPendingDars` — scope filter + non-approver → `[]`

## 7. Risks & Assumptions

- **RISK-001**: Existing tests assumed `DelegateRole` had a specific shape;
  enum extensions should be additive-safe but run the full suite in
  TASK-010 to catch drift.
- **ASSUMPTION-001**: SQLite dev DB is rebuilt from seed (`one_agent.db`)
  during dev — no Alembic migration needed. Confirmed by
  `reference_db_reset.md` pattern.

## 8. Related Specifications / Further Reading

- `docs/prd-phase4-write-agent.md` §3 Scope Enforcement
- `shared/database.py::DelegateRole` — current enum
- Phase 4F plan: `plan/feature-phase4f-approver-write-tools-1.md`
