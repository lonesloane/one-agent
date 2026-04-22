---
goal: Phase 2D execution progress — session state for tests, demo dry-run & doc updates
version: 1.0
date_created: 2026-04-19
last_updated: 2026-04-19
owner: Stephane
status: In Progress
tags: [phase2d, tests, demo, docs, progress, session-state]
---

# Phase 2D — Execution Progress

This document captures mid-session state of Phase 2D so a fresh session
can resume without losing context.

## Branch

Phase 2D works directly on **`main`** — no new production code, tests only.

- **Branch:** `main`
- **Base commit:** `27cb21b` (Phase 2C merge — 172 tests passing)
- **Python venv:** `/home/stephane/Playground/GenAI/copilot/.venv`
- **Run tests:** `source /home/stephane/Playground/GenAI/copilot/.venv/bin/activate && pytest tests/ -q --tb=short`

## Test Count at Phase Start: 172 passing

Net-new since Phase 1B baseline (102): **70 tests** — REQ-001 (≥25) already met.

---

## Phase 1 Audit — Coverage Gap Analysis

Audit completed at phase start (2026-04-19). Results below.

### Test file inventory (Phase 2 net-new)

| File | Tests | Phase |
|------|-------|-------|
| tests/shared/test_migrate_phase2a.py | 1 | 2A |
| tests/shared/test_seed_data.py | 9 | 2A/2B |
| tests/shared/test_database.py | 8 | 1A/2A |
| tests/classical_app/test_routes.py | varies | 1B |
| tests/classical_app/test_delegations.py | varies | 2B |
| tests/classical_app/test_wizard_step2.py | 8 | 2C |
| tests/classical_app/test_wizard_step3.py | 9 | 2C |
| tests/classical_app/test_wizard_step4.py | 4 | 2C |
| tests/classical_app/test_wizard_submit.py | 3 | 2C |
| tests/classical_app/test_wizard_forms.py | 10 | 2C |
| tests/classical_app/test_wizard_flow.py | 11 | 2C |

### Coverage area map

| Area | REQ | Status | Gap detail |
|------|-----|--------|------------|
| (a) Wizard session — TTL eviction | REQ-005 | ✅ Covered | test_wizard_flow.py TestTTLExpiry (2 tests) |
| (a) Wizard session — cancel clears | REQ-005 | ✅ Covered | test_wizard_flow.py TestCancel (2 tests) |
| (a) Wizard session — direct step3 without data | REQ-005 | ✅ Covered | test_wizard_step3.py (1 test) |
| (a) Wizard session — multi-tab keyed by delegation_id | REQ-005 | ✅ Covered | test_wizard_flow.py TestConcurrentDelegations (1 test) |
| (a) Wizard session — back preserves prior data | REQ-005 | ❌ Missing | test_wizard_session.py TASK-008 |
| (a) Wizard session — step N fails without earlier step | REQ-005 | ❌ Missing | test_wizard_session.py TASK-011 |
| (b) determine_approval_route wiring (monkeypatch/spy) | REQ-003 | ❌ Missing | test_wizard_approval_routing.py TASK-013 |
| (c) Permission gating — 403 POST non-editor | REQ-004 | ✅ Covered | test_wizard_flow.py TestNonEditorAccess (2 tests) |
| (c) Permission gating — 403 POST editor-of-other | REQ-004 | ❌ Missing | test_wizard_permissions.py TASK-021 |
| (c) Permission gating — UI button visibility | REQ-004 | ❌ Missing | test_wizard_permissions.py TASK-017/018/019 |
| (d) 3 approval routes via wizard | REQ-006 | ✅ Covered | test_wizard_flow.py TestE2EHappyPath (all 3 statuses) |
| (d) Parametrized approval-route matrix (US-5 rows) | REQ-006 | ❌ Missing | test_wizard_approval_routing.py TASK-014 |
| (e) Retroactive override → PENDING_SECRETARIAT | REQ-006 | ✅ Covered | test_wizard_flow.py TestRetroactivePendingSecretariat |
| (e) Default access level preselect matches helper | REQ-006 | ❌ Missing | test_wizard_approval_routing.py TASK-016 |
| (f) Transactional rollback — re-renders step4 | REQ-007 | ✅ Covered | test_wizard_submit.py (1 test) |
| (f) Transactional rollback — zero new rows | REQ-007 | ❌ Missing | test_wizard_rollback.py TASK-022 |
| (g) Seed idempotency — editors | REQ-008 | ✅ Covered | test_seed_data.py TestSeedDataRoleSeeding |
| (g) Seed idempotency — target delegations | REQ-008 | ✅ Covered | test_seed_data.py TestSeedDataRoleSeeding |
| (g) Seed idempotency Phase 2 explicit class | REQ-008 | ❌ Missing | test_seed_data.py TASK-024/025 (nice-to-have; existing tests cover semantics) |
| (h) retroactive column default=False | n/a | ❌ Missing | test_database.py TASK-026 (optional) |

### Gap fill list (ordered by plan phase)

**Phase 2** — Wizard Session State (test_wizard_session.py):
- TASK-008: `test_back_preserves_prior_step_data`
- TASK-011: `test_step_n_post_fails_when_earlier_step_invalid`

**Phase 3** — Business-Rule Wiring (test_wizard_approval_routing.py):
- TASK-013: `test_every_dar_routes_through_determine_approval_route` (monkeypatch spy)
- TASK-014: `test_approval_route_matrix` parametrized × 6 US-5 rows
- TASK-016: `test_compute_default_access_level_preselect_matches_ui`

**Phase 4** — Permission Gating + Rollback (test_wizard_permissions.py, test_wizard_rollback.py):
- TASK-017: `test_add_delegate_button_hidden_for_non_editor`
- TASK-018: `test_add_delegate_button_visible_for_editor_of_this_delegation`
- TASK-019: `test_add_delegate_button_hidden_for_editor_of_other_delegation`
- TASK-021: `test_direct_post_to_wizard_by_editor_of_other_delegation_returns_403`
- TASK-022: `test_submit_failure_rolls_back_all_inserts` (row count assertions)

---

## Task Status

### ✅ Completed

| Task ID | Plan Ref | Description |
|---------|----------|-------------|
| Audit | TASK-001–004 | Phase 1 audit done; gap list above; net-new=70 ≥ 25 → proceed to fill gaps |
| #1 | TASK-005/008/011 | test_wizard_session.py created — 2 tests passing (back preserves data; step3 POST without step2 redirects) | 2026-04-19 |
| #2–4 | TASK-012/013/014/016 | test_wizard_approval_routing.py created — 8 tests passing (spy, US-5 matrix ×6, preselect) | 2026-04-19 |
| #5–6 | TASK-017/018/019/021 | test_wizard_permissions.py created — 4 tests passing (button visibility ×3, editor-of-other 403) | 2026-04-19 |
| #7 | TASK-022 | test_wizard_rollback.py created — 1 test passing (row count rollback) | 2026-04-19 |
| #8 | TASK-026 | tests/shared/test_database.py extended — retroactive default test added | 2026-04-19 |

**Full suite: 188 passing (was 172 at Phase 2D start — 16 net-new tests this phase).**

### ⏳ Pending (ordered by execution sequence)

| Task ID | Plan Ref | Description | File |
|---------|----------|-------------|------|
| ~~#9~~ | TASK-027 | ~~pytest tests/ -v — confirm green, count ≥ 25 net-new~~ ✓ 188 passing | — |
| ~~#10~~ | TASK-028/029/030 | ~~docs/DEMO_PHASE2.md — golden-path demo dry-run script~~ ✓ Created | NEW |
| ~~#11~~ | TASK-031 | ~~docs/BACKLOG.md~~ ✓ Phase 2D section ticked, 188 tests noted | DONE |
| ~~#12~~ | TASK-032 | ~~docs/DESIGN.md~~ ✓ Current state updated to Phase 2 complete | DONE |
| ~~#13~~ | TASK-033 | ~~docs/OPEN_QUESTIONS.md~~ ✓ OQ-9 resolved with Decision block | DONE |
| ~~#14~~ | TASK-034 | ~~docs/DECISIONS.md~~ ✓ Phase 2 closure entry + OQ-9 resolution appended | DONE |
| ~~#15~~ | TASK-035 | ~~Read all edited docs~~ ✓ No dead anchors or stale labels | DONE |
| ~~#16~~ | TASK-036/037/038 | ~~Exit criterion walk + final pytest + flip plan to Completed~~ ✓ All 11 PRD items satisfied; 188 green; plan moved to `plan/completed/` | DONE |

---

## Key Architecture Context

### Wizard state shape (session)
```python
session["delegate_wizard"] = {
    "<delegation_id>": {
        "step1": {"full_name": ..., "email": ..., "function": ..., "title": ...},
        "step2": {"committee_ids": [...]},
        "step3": {"rows": [{"committee_id": ..., "access_level": ..., "retroactive": bool}]},
        "updated_at": "<ISO-8601 UTC>",   # TTL: stale if > 30 min ago
    }
}
```

### PAT-001 (critical — monkeypatch location)
**CORRECTED 2026-04-19**: `determine_approval_route` is imported and called in
`wizard_helpers.py`, not `wizard.py`. Correct target is:
```python
# CORRECT — patch at the module that calls the function:
monkeypatch.setattr(
    "classical_app.routes.wizard_helpers.determine_approval_route",
    mock_fn
)
# WRONG — patching wizard.py or shared.business_rules won't intercept calls
```

### Seed data facts for tests
- FRA: MEMBER, editor=DEL-2026-0001 (Marie Dupont)
- DEU: MEMBER, no editor in seed
- BRA: PARTNER, editor=DEL-2026-0005 (Carlos Silva), active FA on EDU
- IND: PARTNER, editor=DEL-2026-0007, expired FA on DAC
- TGT-ALPHA/BETA/GAMMA: MEMBER, target delegations for demo writes
- Committees: EDU, TRADE, DAC, ENV, SKILLS
- DEL-2026-0002 (Jean Martin): non-editor on FRA

### Conftest fixtures (tests/classical_app/conftest.py)
- `client` — Flask test client
- `seeded_engine` — in-memory SQLite with full seed
- `editor_member_id` — DEL-2026-0001 (FRA editor)
- `non_editor_member_id` — DEL-2026-0002 (FRA non-editor)

**Note:** No `editor_partner_id` (BRA editor) in conftest yet — TASK-005 may need
a new `editor_bra_id` fixture for permission tests crossing delegations.

### delegation_detail.html — "Add New Delegate" button
The button is guarded by the `is_editor_of_delegation` Jinja global:
```html
{% if is_editor_of_delegation(delegation.id) %}
  <a href="{{ url_for('wizard.wizard_step1', delegation_id=delegation.id) }}">
    Add New Delegate
  </a>
{% endif %}
```
Permission tests (TASK-017/018/019) must GET the delegation detail page and
assert presence/absence of this link.

### Approval route US-5 matrix (PRD §2) — CORRECTED 2026-04-19
| Row | delegation_type | access_level | retroactive | expected_status |
|-----|----------------|--------------|-------------|-----------------|
| 1 | any | GENERAL | False | AUTO_APPROVED |
| 2 | any | CONFIDENTIAL | False | PENDING_SECRETARIAT |
| 3 | any | RESTRICTED | False | PENDING_DELEGATION_HEAD |
| 4 | any | GENERAL | True | PENDING_SECRETARIAT |
| 5 | any | CONFIDENTIAL | True | PENDING_SECRETARIAT |
| 6 | any | RESTRICTED | True | PENDING_SECRETARIAT |

### docs current state
- `docs/BACKLOG.md`: Phase 2D section still shows `- [ ]` items referencing
  Confirmation screen and seed extensions (Phase 2C scope that was merged).
  Needs: tick all Phase 2C/2D items, add completion date, test count.
- `docs/DESIGN.md`: "Current state" block still reads Phase 2A. Needs Phase 2 full update.
- `docs/OPEN_QUESTIONS.md`: OQ-9 open — resolution = "status flag only, no approver UI;
  full UX deferred to Phase 4."
- `docs/DECISIONS.md`: no Phase 2 closure entry yet.

---

## How to Resume in a Fresh Session

1. **Read the full plan:** `plan/feature-phase2d-tests-and-demo-smoke-1.md`

2. **Read this file** (`plan/phase2d-progress.md`) for current task status.

3. **Update task statuses** in this file after each task completes.

4. **Next immediate task (#9 — TASK-027):**
   `pytest tests/ -v --tb=short` — confirm 188 green, ≥ 25 net-new.
   Then proceed to **TASK-028–030**: create `docs/DEMO_PHASE2.md`.

5. **Conftest fixtures confirmed present** — `editor_other_delegation_id`
   already in `tests/classical_app/conftest.py` (delegates to BRA editor).
   No changes needed.
