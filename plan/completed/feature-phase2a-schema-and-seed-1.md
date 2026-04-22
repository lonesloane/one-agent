---
goal: Phase 2A — Schema and Seed Foundations for Classical Write Flows
version: 1.0
date_created: 2026-04-14
last_updated: 2026-04-14
owner: Stephane
status: 'Planned'
tags: [feature, phase-2, schema, seed, migration]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 2A is the schema-and-seed foundation for the Phase 2 classical write flows (delegate-creation wizard). It prepares the data layer so that later sub-phases (2B read pages, 2C wizard, 2D tests+smoke) can be built without touching the ORM or seed again. Scope is strictly additive on the Phase 1 shared data layer: one new column on `Delegate` (`role`), seed-data extensions (delegation editors + empty target delegations), verification of the already-present `DocumentAccessRight.retroactive` column, and verification that `determine_approval_route` already implements the `retroactive=True → pending_secretariat` rule. Exit is reached when migrations apply on both a fresh DB and an existing Phase 1 DB, at least three `delegation_editor` personas are visible, and the full Phase 1 test suite (102 tests) stays green alongside the new Phase 2A tests.

## 1. Requirements & Constraints

- **REQ-001**: Add a nullable=False `role` column to `Delegate` with SQL enum values `{delegate, delegation_editor}` and a server default of `'delegate'` so existing Phase 1 rows migrate cleanly.
- **REQ-002**: Confirm `DocumentAccessRight.retroactive` (Boolean, default False, nullable=False) is present in `shared/database.py`. Verification only — column already exists per Phase 1 schema; no change required.
- **REQ-003**: Confirm `ApprovalStatus` enum contains the three values required by the PRD routing table: the auto-approved route, the delegation-head route, and the secretariat route.
- **REQ-004**: Confirm `shared.business_rules.determine_approval_route` already routes `retroactive=True` to the secretariat status regardless of classification level, with tests proving it for GENERAL and RESTRICTED.
- **REQ-005**: Extend `shared/seed_data.py` idempotently to mark one delegate per seeded delegation (FRA/member, BRA/partner-with-FA, IND/partner-no-FA) as `delegation_editor`.
- **REQ-006**: Add 2–3 empty "target" delegations to `shared/seed_data.py` that the editor can write into during a live demo without mutating Phase 1 read fixtures.
- **REQ-007**: Provide a migration path for an existing Phase 1 SQLite DB (`one_agent.db`) so the new `role` column is added without dropping data.
- **REQ-008**: Exit criterion — `scripts/init_db.py` succeeds on a fresh DB; the migration helper succeeds on an existing Phase 1 DB; the delegate picker used by the classical app lists at least 3 `delegation_editor` personas.
- **SEC-001**: No new PII categories; role is metadata only.
- **CON-001**: Phase 1 (102 tests) must stay green after the schema change — verified by running the full suite before and after.
- **CON-002**: Read-only vs. write distinction is still enforced downstream — Phase 2A introduces no new Flask routes, templates, or forms.
- **CON-003**: No Alembic is used in this project; migrations are expressed either as `Base.metadata.create_all` (fresh DBs) or as a minimal one-shot Python script using raw `ALTER TABLE` (existing DBs).
- **CON-004**: The `Delegate.role` enum must round-trip through SQLAlchemy's `Enum(native_enum=False)` to match the project pattern used for `MembershipType`, `ClassificationLevel`, and `ApprovalStatus`.
- **CON-005**: Seed extensions must be idempotent via `session.merge()` on string PKs; rerunning `seed_all` must not duplicate rows.
- **GUD-001**: Follow `CLAUDE.md` conventions: PEP 8, type hints, `loguru` for logs, `pytest` for tests.
- **GUD-002**: Keep the PRD naming (`pending_delegation_head`, `pending_secretariat`, and the auto-approved route) as the semantic contract. Existing Phase 1 enum uses `AUTO_APPROVED`; do **not** rename — document the mapping in an ADR note within `shared/database.py` docstring.
- **PAT-001**: Use `SQLEnum(..., native_enum=False)` as all other enums do, with `server_default=...` to make Phase 1 row migration safe.
- **PAT-002**: Keep all business rules in `shared/business_rules.py`; never embed approval routing in seed or forms.

## 2. Implementation Steps

### Implementation Phase 1 — Verify Existing Phase 1 Surface (read-only audit)

- GOAL-001: Confirm that `DocumentAccessRight.retroactive`, the `ApprovalStatus` enum, and `determine_approval_route`'s retroactive rule already satisfy the PRD §3 contract before adding anything new, so that later steps do not fork semantics.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Run the full Phase 1 test suite (`uv run pytest`) and record the baseline pass count (expected: 102). Abort Phase 2A if baseline is not green. | | |
| TASK-002 | Read `shared/database.py` and confirm `ApprovalStatus` contains `AUTO_APPROVED`, `PENDING_DELEGATION_HEAD`, `PENDING_SECRETARIAT`. Document the PRD-string → enum-name mapping in the `ApprovalStatus` class docstring. | | |
| TASK-003 | Read `shared/database.py` and confirm `DocumentAccessRight.retroactive = Column(Boolean, nullable=False, default=False)` already exists. No change required; record confirmation. | | |
| TASK-004 | Read `shared/business_rules.py` and confirm `determine_approval_route` returns `PENDING_SECRETARIAT` when `retroactive=True` regardless of level. Confirm unit tests cover retroactive GENERAL and retroactive RESTRICTED. | | |
| TASK-005 | Confirm there is no `Delegate.role` column today by reading `shared/database.py`. | | |

### Implementation Phase 2 — Schema: Add `Delegate.role`

- GOAL-002: Add the `role` enum column to `Delegate` additively, safe for both fresh and existing databases, without breaking any Phase 1 test.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | In `shared/database.py`, add a module-level `class DelegateRole(Enum)` with `DELEGATE = "DELEGATE"` and `DELEGATION_EDITOR = "DELEGATION_EDITOR"`. Place it after `ApprovalStatus`. Add docstring. | | |
| TASK-007 | In `class Delegate`, add `role = Column(SQLEnum(DelegateRole, native_enum=False), nullable=False, server_default=DelegateRole.DELEGATE.value, default=DelegateRole.DELEGATE)`. Update class docstring `Attributes:` block. | | |
| TASK-008 | Export `DelegateRole` and import it in `shared/seed_data.py`. | | |
| TASK-009 | Create `scripts/migrate_phase2a.py`: one-shot migration using raw SQL (`ALTER TABLE delegates ADD COLUMN role VARCHAR NOT NULL DEFAULT 'DELEGATE'`). Detect existing column via `PRAGMA table_info(delegates)` and skip if present. Log each step via `loguru`. Safe to re-run. | | |
| TASK-010 | Update `scripts/init_db.py` docstring to mention the new `role` column. | | |

### Implementation Phase 3 — Seed Data Extensions (idempotent)

- GOAL-003: Make at least 3 `delegation_editor` personas visible (one per delegation type) and add 2–3 empty target delegations for demo writes.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | In `shared/seed_data.py`, import `DelegateRole`. | | |
| TASK-012 | Extend `delegates_data`: add `role` key defaulting to `DelegateRole.DELEGATE`. Override to `DelegateRole.DELEGATION_EDITOR` for exactly these IDs: `DEL-2026-0001` (FRA/member head), `DEL-2026-0005` (BRA/partner-with-FA), `DEL-2026-0007` (IND/partner-no-FA). | | |
| TASK-013 | Pass `role` into the `Delegate(**delegate_data)` constructor. `session.merge()` keeps this idempotent. | | |
| TASK-014 | Add `seed_target_delegations(session)` merging 3 empty targets: `TGT-ALPHA` (MEMBER), `TGT-BETA` (PARTNER), `TGT-GAMMA` (PARTNER). No delegates/DARs/FAs. | | |
| TASK-015 | Call `seed_target_delegations(session)` from `seed_all` after `seed_delegations`. | | |
| TASK-016 | Update `seed_data.py` module docstring: bump delegation count, mention role field and editor IDs. | | |
| TASK-017 | Update `__main__` print block to print count of delegation editors. | | |

### Implementation Phase 4 — Tests

- GOAL-004: Cover the new schema surface and re-prove the retroactive rule.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | `test_delegate_role_default` — persist `Delegate` without setting `role`, assert `role == DelegateRole.DELEGATE`. | | |
| TASK-019 | `test_delegate_role_editor_roundtrip` — persist with `DELEGATION_EDITOR`, reload, assert round-trip. | | |
| TASK-020 | `test_approval_status_contains_required_values` — assert the 3 required values are subset of `ApprovalStatus`. | | |
| TASK-021 | `test_three_delegation_editors_seeded` — run `seed_all`, assert count == 3 and IDs match. | | |
| TASK-022 | `test_target_delegations_present` — assert `TGT-ALPHA/BETA/GAMMA` exist with zero delegates. | | |
| TASK-023 | `test_seed_all_idempotent_with_role` — run `seed_all` twice, assert counts unchanged and editors remain editors. | | |
| TASK-024 | `test_retroactive_confidential_pending_secretariat` — asserts `determine_approval_route(CONFIDENTIAL, True) == PENDING_SECRETARIAT`. Closes retroactive coverage matrix. | | |
| TASK-025 | `tests/shared/test_migrate_phase2a.py` — run migration script on a fresh DB, assert idempotency (second run no-op). | | |

### Implementation Phase 5 — Exit Verification

- GOAL-005: Prove the PRD §4 "2A" exit criteria.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-026 | Delete `one_agent.db`, run `python scripts/init_db.py`, confirm exit 0. | | |
| TASK-027 | On a simulated Phase 1 DB (with `role` column dropped), run `python scripts/migrate_phase2a.py one_agent.db`, confirm `role` column present with default `DELEGATE`. | | |
| TASK-028 | Run `uv run pytest` — expect ≥ 102 prior + 8 new tests green. | | |
| TASK-029 | Open delegate picker, confirm at least 3 `delegation_editor` personas visible. | | |
| TASK-030 | Append completion line to `docs/BACKLOG.md`; update `docs/DESIGN.md` "Current state". | | |

## 3. Alternatives

- **ALT-001**: Introduce Alembic now. Rejected — project uses `create_all`; larger refactor belongs elsewhere.
- **ALT-002**: Rename `ApprovalStatus.AUTO_APPROVED`. Rejected — semantic mapping is 1:1; rename ripples through 102 tests.
- **ALT-003**: Free-text `role` column. Rejected — inconsistent with other enums.
- **ALT-004**: Many-to-many `delegate_roles` table. Rejected — PRD accepts single-enum-now with later M2M widening.
- **ALT-005**: Add new editor delegates vs. mutate existing. Chosen: mutate in place per PRD "1 delegate per delegation".

## 4. Dependencies

- **DEP-001**: Phase 1A shared data layer — merged 2026-04-12.
- **DEP-002**: Phase 1B classical Flask app — used for manual verification.
- **DEP-003**: `sqlalchemy`, `loguru`, `pytest`, `uv` — already in `pyproject.toml`.
- **DEP-004**: No new third-party libraries.

## 5. Files

- **FILE-001**: `shared/database.py` — `DelegateRole` enum + `Delegate.role` column; `ApprovalStatus` docstring mapping.
- **FILE-002**: `shared/seed_data.py` — set `role` on delegates, add `seed_target_delegations`, wire into `seed_all`.
- **FILE-003**: `scripts/migrate_phase2a.py` — new one-shot migration helper.
- **FILE-004**: `scripts/init_db.py` — docstring refresh.
- **FILE-005**: `tests/shared/test_database.py` — role + approval status tests.
- **FILE-006**: `tests/shared/test_seed_data.py` — editor count, targets, idempotency.
- **FILE-007**: `tests/shared/test_business_rules.py` — retroactive CONFIDENTIAL coverage.
- **FILE-008**: `tests/shared/test_migrate_phase2a.py` — new migration helper test.
- **FILE-009**: `docs/BACKLOG.md` — tick Phase 2A row.
- **FILE-010**: `docs/DESIGN.md` — "Current state" update.

## 6. Testing

- **TEST-001**: `test_delegate_role_default`
- **TEST-002**: `test_delegate_role_editor_roundtrip`
- **TEST-003**: `test_approval_status_contains_required_values`
- **TEST-004**: `test_three_delegation_editors_seeded`
- **TEST-005**: `test_target_delegations_present`
- **TEST-006**: `test_seed_all_idempotent_with_role`
- **TEST-007**: `test_retroactive_confidential_pending_secretariat`
- **TEST-008**: `test_migrate_phase2a_idempotent`
- **TEST-009** (meta): full `uv run pytest` green (≥ 102 prior + 8 new).

## 7. Risks & Assumptions

- **RISK-001**: `ALTER TABLE ADD COLUMN NOT NULL DEFAULT` fails on ancient SQLite. Mitigation: log `PRAGMA compile_options` on failure; fallback drop-and-reseed is acceptable for PoC.
- **RISK-002**: Mutating `DEL-2026-0001`'s role could surprise Phase 1 tests. Mitigation: TASK-001 baseline + TASK-028 re-run.
- **RISK-003**: 3 chosen editors are all heads. Mitigation: acceptable for PoC; add non-head editor if future UX requires.
- **RISK-004**: `native_enum=False` stores strings; `ALTER TABLE` uses VARCHAR — compatible.
- **ASSUMPTION-001**: No Alembic required.
- **ASSUMPTION-002**: Phase 1B picker displays all delegates across delegations.
- **ASSUMPTION-003**: PRD lowercase strings are UI display values, not enum names.

## 8. Related Specifications / Further Reading

- `docs/prd-phase2-classical-write-flows.md` — §3 Data-model changes, §3 Seed data, §4 row 2A.
- `plan/completed/feature-phase1a-shared-data-layer-1.md` — Phase 1A baseline.
- `plan/completed/feature-phase1b-classical-app-1.md` — Phase 1B consumer of picker.
- `CLAUDE.md` — project conventions.
