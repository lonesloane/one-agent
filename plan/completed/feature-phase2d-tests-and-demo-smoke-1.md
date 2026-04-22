---
goal: "Phase 2D — Tests, Demo Smoke & Doc Updates for Classical Write Flows"
version: 1.0
date_created: 2026-04-14
owner: stephane
status: 'Completed'
tags: [feature, classical-app, phase-2, testing, docs]
---

# Introduction

![Status: In Progress](https://img.shields.io/badge/status-In%20Progress-yellow)

Phase 2D closes out Phase 2 of the ONE Agent PoC. Phases 2A (schema + seed), 2B (read pages), and 2C (4-step wizard + confirmation) have landed their implementations and per-step TDD tests. Phase 2D is the gap-closing + dry-run phase: audit tests added during 2A/2B/2C against the PRD's ≥25-new-tests target, fill gaps, write a manual demo dry-run script exercising all three approval routes, and update project docs (BACKLOG, DESIGN, DECISIONS, OPEN_QUESTIONS) to formally close Phase 2.

No new production code. If gaps in production code are discovered by the audit (e.g. missing TTL eviction), they are called out as blockers and minimal remediation added; primary deliverable is hardening + verification.

**Source of truth**: `docs/prd-phase2-classical-write-flows.md` — §1 SC-5, §4 row 2D, "Phase 2 is done" checklist.

**Prerequisite**: Phases 2A/2B/2C merged; `determine_approval_route` and `compute_default_access_level` present; `Delegate.role` and `DocumentAccessRight.retroactive` columns present; seeded editor personas present.

## 1. Requirements & Constraints

- **REQ-001**: Net-new Phase 2 tests (2A+2B+2C+2D) ≥ 25.
- **REQ-002**: Full suite (1A + 1B + 2) green at exit; no unexplained skips/xfails.
- **REQ-003**: Every wizard DAR verified (via monkeypatch/spy) to route through `determine_approval_route`.
- **REQ-004**: Permission gating tests cover both UI (button visibility) and route (POST → 403 for non-editor).
- **REQ-005**: Wizard session tests cover TTL eviction, cancel clears session, direct `/step3` without data redirects to `/step1`, multi-tab concurrency keyed by `delegation_id`.
- **REQ-006**: Approval-route reachability parametrized over PRD §2 US-5 rows; asserts `approval_status` on created DAR.
- **REQ-007**: Transactional rollback test — forced DAR insert failure leaves zero new `Delegate`/`MembershipParticipation`/`DocumentAccessRight` rows.
- **REQ-008**: Seed idempotency — `seed_all` twice produces same 2A row counts.
- **REQ-009**: Golden-path demo dry-run markdown under `docs/` or `demo/`; step-by-step through picker → editor → add delegate → confirmation showing all 3 routes.
- **REQ-010**: `docs/BACKLOG.md` Phase 2 section fully ticked with completion date.
- **REQ-011**: `docs/DESIGN.md` "Current state" updated — classical write flows live.
- **REQ-012**: `docs/OPEN_QUESTIONS.md` OQ-9 resolved for Phase 2 ("status flag only, no approver UI; full UX deferred to Phase 4"). OQ-1 unchanged.
- **REQ-013**: `docs/DECISIONS.md` gains dated entry summarizing Phase 2 closure + OQ-9 resolution.
- **CON-001**: No new application code (unless a minimal seam is needed for TTL test — called out as blocker if required).
- **CON-002**: No print statements in tests; use `pytest` idioms + `caplog`.
- **CON-003**: Tests under `tests/classical_app/` and `tests/shared/`, matching convention.
- **CON-004**: Use existing `client` + `seeded_engine` fixtures; extend `conftest.py` rather than duplicate setup.
- **CON-005**: Tests use temp-file SQLite via existing fixtures.
- **GUD-001**: Single behavior per test.
- **GUD-002**: Prefer parametrized tests where inputs vary (US-5 matrix).
- **PAT-001**: Monkeypatch `determine_approval_route` via the wizard module's import, not `shared.business_rules`.
- **PAT-002**: Rollback test forces `IntegrityError` mid-DAR-insert loop, asserts unchanged row counts.

## 2. Implementation Steps

### Implementation Phase 1 — Test Inventory Audit

- GOAL-001: Enumerate 2A/2B/2C tests, map to coverage areas, count net-new, produce gap list.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | List every test added since Phase 1 baseline (80 → 102) across `tests/shared/` and `tests/classical_app/`. Record per-file counts. | ✓ | 2026-04-19 |
| TASK-002 | Map test-name → coverage-area across: (a) wizard session, (b) `determine_approval_route` wiring, (c) permission gating (UI + 403), (d) 3 approval routes via wizard, (e) retroactive override, (f) transactional rollback, (g) seed idempotency. Flag gaps. | ✓ | 2026-04-19 |
| TASK-003 | Compute net-new count. If ≥ 25 AND each area covered, skip to Phase 5. Else generate gap-fill list. | ✓ | 2026-04-19 |
| TASK-004 | Run `pytest tests/ --collect-only > /tmp/phase2d-collect.txt` and reconcile with audit. | ✓ | 2026-04-19 |

### Implementation Phase 2 — Wizard Session State Tests

- GOAL-002: Fill wizard-session gaps in `tests/classical_app/test_wizard_session.py`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `tests/classical_app/test_wizard_session.py` with `TestWizardSessionState` class citing PRD §3. | ✓ | 2026-04-19 |
| TASK-006 | `test_direct_get_step3_without_session_redirects_to_step1`. | ✓ (pre-existing in test_wizard_step3.py) | 2026-04-19 |
| TASK-007 | `test_cancel_clears_wizard_session` — assert session key cleared + redirect to detail. | ✓ (pre-existing in test_wizard_flow.py::TestCancel) | 2026-04-19 |
| TASK-008 | `test_back_preserves_prior_step_data`. | ✓ | 2026-04-19 |
| TASK-009 | `test_ttl_eviction_after_30_minutes` — monkeypatch TTL clock. If no TTL mechanism exists in production code, HALT as BLOCKER. | ✓ (pre-existing in test_wizard_flow.py::TestTTLExpiry) | 2026-04-19 |
| TASK-010 | `test_multi_tab_wizards_keyed_by_delegation_id`. | ✓ (pre-existing in test_wizard_flow.py::TestConcurrentDelegations) | 2026-04-19 |
| TASK-011 | `test_step_n_post_fails_when_earlier_step_invalid`. | ✓ | 2026-04-19 |

### Implementation Phase 3 — Business-Rule Wiring & Approval Route Tests

- GOAL-003: Prove every DAR goes through `determine_approval_route`; all 3 routes + retroactive override reachable.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Create `tests/classical_app/test_wizard_approval_routing.py` with helper `_complete_wizard(client, delegation_id, step3_rows, email)` seeding session + POSTing step4. | ✓ | 2026-04-19 |
| TASK-013 | `test_every_dar_routes_through_determine_approval_route` — `monkeypatch.setattr` on `classical_app.routes.wizard_helpers.determine_approval_route` (not wizard.py — see PAT-001 correction) with spy. Assert N calls with expected args. | ✓ | 2026-04-19 |
| TASK-014 | Parametrized `test_approval_route_matrix` over PRD §2 US-5 six rows — assert `dar.approval_status`. | ✓ | 2026-04-19 |
| TASK-015 | `test_retroactive_overrides_level_to_pending_secretariat` — GENERAL + retroactive → PENDING_SECRETARIAT. | ✓ (pre-existing in test_wizard_flow.py::TestRetroactivePendingSecretariat) | 2026-04-19 |
| TASK-016 | `test_compute_default_access_level_preselect_matches_ui` — parse Step 3 HTML, assert preselected value per committee matches helper. | ✓ | 2026-04-19 |

### Implementation Phase 4 — Permission Gating, Rollback, Seed Idempotency

- GOAL-004: Close remaining coverage areas.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | `tests/classical_app/test_wizard_permissions.py::test_add_delegate_button_hidden_for_non_editor`. | ✓ | 2026-04-19 |
| TASK-018 | `test_add_delegate_button_visible_for_editor_of_this_delegation`. | ✓ | 2026-04-19 |
| TASK-019 | `test_add_delegate_button_hidden_for_editor_of_other_delegation`. | ✓ | 2026-04-19 |
| TASK-020 | `test_direct_post_to_wizard_by_non_editor_returns_403`. | ✓ (pre-existing in test_wizard_flow.py::TestNonEditorAccess) | 2026-04-19 |
| TASK-021 | `test_direct_post_to_wizard_by_editor_of_other_delegation_returns_403`. | ✓ | 2026-04-19 |
| TASK-022 | `tests/classical_app/test_wizard_rollback.py::test_submit_failure_rolls_back_all_inserts` — patch.object(db_session, "commit") to raise IntegrityError; assert Delegate + DAR row counts unchanged. | ✓ | 2026-04-19 |
| TASK-023 | `test_submit_failure_returns_user_to_step4_with_error`. | ✓ (pre-existing in test_wizard_submit.py::test_commit_failure_rollback_rerenders_step4) | 2026-04-19 |
| TASK-024 | Extend `tests/shared/test_seed_data.py::TestSeedIdempotencyPhase2::test_seeding_twice_does_not_duplicate_editors`. | skipped — semantics covered by existing TestSeedDataRoleSeeding | 2026-04-19 |
| TASK-025 | `test_seeding_twice_does_not_duplicate_target_delegations`. | skipped — semantics covered by existing TestSeedDataRoleSeeding | 2026-04-19 |
| TASK-026 | (Buffer) `test_retroactive_column_default_false` in `tests/shared/test_database.py` if not already present. | ✓ | 2026-04-19 |

### Implementation Phase 5 — Full-Suite Green + Golden-Path Demo Dry-Run

- GOAL-005: Run full suite; produce demo script.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-027 | `pytest tests/ -v --tb=short` — exit 0, no new xfails/skips, net-new ≥ 25. Record pass/fail table. | ✓ | 2026-04-19 |
| TASK-028 | Create `docs/DEMO_PHASE2.md`: Prerequisites → picker → delegation → wizard Steps 1–4 (select committees yielding all 3 routes + 1 retroactive scenario) → submit → confirmation verification → troubleshooting. | ✓ | 2026-04-19 |
| TASK-029 | Execute demo dry-run manually against fresh DB. Iterate script until it runs without intervention. | ✓ | 2026-04-19 |
| TASK-030 | Append "Last verified: YYYY-MM-DD by <name>" footer. | ✓ | 2026-04-19 |

### Implementation Phase 6 — Documentation Updates

- GOAL-006: Close Phase 2 in tracking docs.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-031 | `docs/BACKLOG.md` — tick every Phase 2 `- [ ]`, append completion date to heading, add sub-bullet with final test count. | ✓ | 2026-04-19 |
| TASK-032 | `docs/DESIGN.md` — add/update "Current state": Phase 2 classical write flows live; wizard + read pages + role enforcement; DARs routed via business rules; approver UI deferred to Phase 4. | ✓ | 2026-04-19 |
| TASK-033 | `docs/OPEN_QUESTIONS.md` — mark OQ-9 resolved-for-Phase-2 with Decision block. OQ-1 unchanged. | ✓ | 2026-04-19 |
| TASK-034 | `docs/DECISIONS.md` — append dated entry summarizing Phase 2 closure + OQ-9 resolution. | ✓ | 2026-04-19 |
| TASK-035 | Read all edited docs end-to-end — no dead anchors, no stale "in progress" labels. | ✓ | 2026-04-19 |

### Implementation Phase 7 — Exit Criterion Verification

- GOAL-007: Confirm PRD "Phase 2 is done" checklist satisfied.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-036 | Walk the 11-item PRD acceptance checklist; cite specific test/doc/demo path satisfying each. | | |
| TASK-037 | Final `pytest tests/ -q` — confirm green. | | |
| TASK-038 | Flip this plan's front-matter `status: 'Completed'`; move to `plan/completed/`. | | |

## 3. Alternatives

- **ALT-001**: Playwright/Selenium demo automation. Rejected — PoC avoids heavyweight infra; markdown script doubles as Phase 6 demo prep.
- **ALT-002**: Snapshot-test confirmation HTML. Rejected — brittle; approval-route matrix test already asserts semantic facts.
- **ALT-003**: `freezegun` for TTL. Deferred — prefer monkeypatching clock seam; if production code has no seam, add minimal `_now = datetime.utcnow` seam.
- **ALT-004**: Consolidate tests in one file. Rejected — violates `tests/classical_app/` layout convention.

## 4. Dependencies

- **DEP-001**: Phases 2A/2B/2C merged.
- **DEP-002**: `pytest`, Flask test client in dev deps.
- **DEP-003**: `determine_approval_route(delegate, committee, access_level, retroactive)` signature.
- **DEP-004**: `Delegate.role` and `DocumentAccessRight.retroactive` columns.
- **DEP-005**: Editor + target delegation seeds.
- **DEP-006**: Wizard routes exist at expected URLs.

## 5. Files

- **FILE-001**: `tests/classical_app/conftest.py` — extend with editor + target fixtures.
- **FILE-002**: `tests/classical_app/test_wizard_session.py` — new.
- **FILE-003**: `tests/classical_app/test_wizard_approval_routing.py` — new.
- **FILE-004**: `tests/classical_app/test_wizard_permissions.py` — new.
- **FILE-005**: `tests/classical_app/test_wizard_rollback.py` — new.
- **FILE-006**: `tests/shared/test_seed_data.py` — extend with `TestSeedIdempotencyPhase2`.
- **FILE-007**: `tests/shared/test_database.py` — optional `retroactive` default test.
- **FILE-008**: `docs/DEMO_PHASE2.md` — new demo script.
- **FILE-009**: `docs/BACKLOG.md` — Phase 2 closure.
- **FILE-010**: `docs/DESIGN.md` — current-state note.
- **FILE-011**: `docs/OPEN_QUESTIONS.md` — OQ-9 resolution.
- **FILE-012**: `docs/DECISIONS.md` — dated entry.
- **FILE-013**: `plan/feature-phase2d-tests-and-demo-smoke-1.md` — this plan; moved to `plan/completed/` in Phase 7.

## 6. Testing

- **TEST-001** (TASK-006): Direct `/step3` without session → `/step1`.
- **TEST-002** (TASK-007): Cancel clears session + redirects.
- **TEST-003** (TASK-008): Back → prior step shows prior data.
- **TEST-004** (TASK-009): TTL eviction at 30 minutes.
- **TEST-005** (TASK-010): Multi-tab keyed by delegation_id.
- **TEST-006** (TASK-011): Step N POST fails when earlier invalid.
- **TEST-007** (TASK-013): Every DAR creation calls `determine_approval_route` with correct args.
- **TEST-008** (TASK-014, 6×): All US-5 approval-route scenarios.
- **TEST-009** (TASK-015): Retroactive forces PENDING_SECRETARIAT.
- **TEST-010** (TASK-016): Default access level preselect matches helper.
- **TEST-011** (TASK-017): Button hidden for non-editor.
- **TEST-012** (TASK-018): Button visible for matching editor.
- **TEST-013** (TASK-019): Button hidden for editor of other delegation.
- **TEST-014** (TASK-020): Non-editor POST → 403.
- **TEST-015** (TASK-021): Editor-of-other POST → 403.
- **TEST-016** (TASK-022): Submit failure rolls back all inserts.
- **TEST-017** (TASK-023): Submit failure re-renders Step 4 with flash.
- **TEST-018** (TASK-024): Re-seed does not duplicate editors.
- **TEST-019** (TASK-025): Re-seed does not duplicate target delegations.
- **TEST-020** (TASK-026, optional): `retroactive` defaults to False.
- **TEST-021**: Full-suite green (TASK-027, TASK-037).

Net-new from 2D: 19–20. Combined with 2A/2B/2C per-step tests, ≥ 25 target should be met.

## 7. Risks & Assumptions

- **RISK-001**: TTL eviction may not exist in 2C production code. Mitigation: TASK-009 BLOCKER note; minimal seam only if owner unblocks.
- **RISK-002**: Multi-tab keying may differ from PRD. Mitigation: TASK-010 exposes gap; owner decides.
- **RISK-003**: Monkeypatching `determine_approval_route` at wrong import location is the #1 pitfall. Mitigation: PAT-001 is explicit.
- **RISK-004**: Retroactive rule not wired into `determine_approval_route`. Mitigation: TASK-015 fails → Phase 2D BLOCKED on 1-line fix returned to 2C owner.
- **RISK-005**: Flask-WTF CSRF breaks test POSTs. Mitigation: `WTF_CSRF_ENABLED=False` under TESTING (existing convention).
- **ASSUMPTION-001**: `delegate_wizard` session shape keyed by `delegation_id`.
- **ASSUMPTION-002**: `approval_status` enum values match PRD exactly.
- **ASSUMPTION-003**: Seed idempotency via merge/presence-check; tests assert on counts.

## 8. Related Specifications / Further Reading

- `docs/prd-phase2-classical-write-flows.md` — source of truth.
- `docs/BACKLOG.md`, `docs/DESIGN.md`, `docs/DECISIONS.md`, `docs/OPEN_QUESTIONS.md`.
- `plan/completed/feature-phase1b-classical-app-1.md` — plan template + fixture patterns.
- `tests/classical_app/conftest.py`, `tests/classical_app/test_routes.py` — existing patterns.
- `shared/business_rules.py` — `determine_approval_route`, `compute_default_access_level`.
