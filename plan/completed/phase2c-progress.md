---
goal: Phase 2C execution progress — subagent-driven development session state
version: 2.0
date_created: 2026-04-19
last_updated: 2026-04-19
owner: Stephane
status: In Progress
tags: [phase2c, wizard, progress, session-state]
---

# Phase 2C — Execution Progress

This document captures mid-session state of Phase 2C implementation so a
fresh session can resume without losing context.

## Worktree

- **Path:** `/home/stephane/Playground/GenAI/copilot/.worktrees/phase2c-wizard`
- **Branch:** `feature/phase2c-wizard`
- **Base branch:** `main` (128 tests passing at branch point)
- **Python venv:** `/home/stephane/Playground/GenAI/copilot/.venv`
- **Run tests:** `source /home/stephane/Playground/GenAI/copilot/.venv/bin/activate && pytest tests/ -q --tb=short`

## Git log (as of save point)

```
31049f9 Phase 2C Task 12-13: refactor _handle_step4_post under 50 lines; narrow exception; fix docstring
0094b8b Phase 2C Task 12-13: strengthen test assertions for submit + cancel
f0823e3 Phase 2C Task 12-13: Step 4 POST single-transaction submit + Cancel handler
611a806 Phase 2C Task 11: Step 4 GET handler; split wizard_helpers.py; add auto-approved test
bb02c54 Phase 2C Task 11: Step 4 GET handler with review rows and approval routing
7fcc5bf Phase 2C Task 9-10: fix access_level validation and test name length
26441a1 Phase 2C Task 9-10: expand step3 tests and remove dead import
b7991d0 Phase 2C Task 9-10: Step 3 GET/POST — DAR rows with _allowed_levels helper
e68698b Phase 2C Task 8: Step 2 GET/POST — committee multi-select; fix nested form in all templates
7852c27 Phase 2C Task 7: refactor wizard_step1 to stay under 50-line limit  ← session 1 end
4843875 Phase 2C Task 7: Step 1 GET/POST — personal info with email uniqueness
c1652cd Phase 2C Task 4: fix Jinja2 include syntax in step templates
cebf513 Phase 2C Task 4: wizard HTML templates (step1-4, confirmation, progress partial)
9144fd3 Phase 2C Task 5-6: fix assert in require_steps to safe guard
098f07d Phase 2C Task 5-6: wizard_state.py session helpers with TTL
c6f96f0 Phase 2C Task 2: wizard blueprint stubs for steps 1-4, confirmation, cancel
0f9c625 Phase 2C Task 1: wizard form classes (Step1-4, DARRowForm)
fe1b600 Phase 2B Task 5: fix code quality issues in test_delegations  ← branch base
```

## Test count: 152 passing

---

## Task Status

### ✅ Completed

| Task ID | Plan Ref | Description | Commit(s) |
|---------|----------|-------------|-----------|
| #1 | TASK-001 | Forms package — Step1-4, DARRowForm | 0f9c625 |
| #2 | TASK-002 | Wizard blueprint stubs | c6f96f0 |
| #3 | TASK-003 | Blueprint registered in app.py; CSRF disabled | c6f96f0 |
| #4 | TASK-004 | Wizard HTML templates (6 files) | cebf513, c1652cd |
| #5 | TASK-005/006 | wizard_state.py — load/save/clear/is_stale/require_steps/get+set_created_delegate_id | 098f07d, 9144fd3 |
| #6 | TASK-007 | Step 1 GET/POST — personal info with email uniqueness | 4843875, 7852c27 |
| #7 | TASK-008 | Step 2 GET/POST — committee multi-select; fix nested form in templates | e68698b |
| #8 | TASK-009/010 | Step 3 GET/POST + `_allowed_levels` helper | b7991d0, 26441a1, 7fcc5bf |
| #9 | TASK-011 | Step 4 GET — review rows with approval routing labels | bb02c54, 611a806 |
| #10 | TASK-012/013 | Step 4 POST (single-transaction submit) + Cancel handler | f0823e3, 0094b8b, 31049f9 |

### ⏳ Pending (ordered by execution sequence)

| Task ID | Plan Ref | Description |
|---------|----------|-------------|
| #11 | TASK-014/015 | Confirmation GET handler + APPROVAL_LABELS (already defined in wizard_helpers.py) |
| #12 | TASK-016/017 | Flesh out templates (already done in scaffolding) — verify and polish |
| #13 | TASK-018 | test_wizard_forms.py — form validation unit tests |
| #14 | TASK-019-028 | test_wizard_flow.py — integration and flow tests |
| #15 | TASK-029 | Full pytest suite — confirm 1A/1B/2A/2B/2C all green |

---

## Key Architecture Decisions Made During Implementation

### CSRF
`WTF_CSRF_ENABLED = False` globally in `create_app()`. No test-fixture scoping needed.

### Cancel button — no nested forms
All step templates use `<button formaction="...">` instead of a nested `<form>` for
Cancel. Nested `<form>` elements are invalid HTML5 and were fixed in Task #7.

### wizard.py split into wizard_helpers.py
`wizard.py` grew beyond 500 lines and was refactored:
- `classical_app/routes/wizard.py` — route handlers only (472 lines)
- `classical_app/routes/wizard_helpers.py` — pure helpers + APPROVAL_LABELS (357 lines)

Helpers in `wizard_helpers.py`:
- `APPROVAL_LABELS` — approval status → human-readable label dict
- `_allowed_levels(delegation, committee_id)` — MEMBER/PARTNER access level logic
- `_apply_dar_row_override(row_entry, saved, default_level)`
- `_build_step3_form(delegation, committee_ids, committee_map, state)`
- `_build_review_rows(state, committee_map)`
- `_generate_delegate_id(db_session)`
- `_build_delegate(step1, delegation_id, new_id, now)`
- `_build_dars(delegate_id, step3_rows, now, created_by)`
- `_handle_step4_post(delegation_id, db_session, state)`

### Step 3 POST raw form reading
WTForms `FieldList(FormField(...))` doesn't validate reliably server-side.
Step 3 POST reads raw `request.form` data: `rows-{i}-committee_id`, `rows-{i}-access_level`,
`rows-{i}-retroactive`. Access levels are server-side validated against `ClassificationLevel` enum.

### Delegate ID generation
No dedicated generator function exists. Generated as `DEL-{year}-{seq:04d}` where
`seq = max(existing sequence numbers) + 1`. Lives in `_generate_delegate_id` in wizard_helpers.py.

### Transaction on Step 4 POST
Single `try/except SQLAlchemyError` block: add Delegate + DARs, commit.
On failure: rollback, flash, re-render step4. On success: set_created_delegate_id,
clear wizard state, redirect to confirmation.

### DARRowForm.Meta.csrf = False
Required for FieldList/FormField embedding. Outer Step3DARsForm carries CSRF.

---

## Files Created/Modified in This Branch

### New files
- `classical_app/forms/__init__.py`
- `classical_app/forms/delegate_wizard.py` — Step1-4 forms + DARRowForm
- `classical_app/wizard_state.py` — session helpers
- `classical_app/routes/wizard.py` — wizard blueprint (full implementation)
- `classical_app/routes/wizard_helpers.py` — extracted pure helpers
- `classical_app/templates/wizard/_progress.html`
- `classical_app/templates/wizard/step1.html`
- `classical_app/templates/wizard/step2.html`
- `classical_app/templates/wizard/step3.html`
- `classical_app/templates/wizard/step4.html`
- `classical_app/templates/wizard/confirmation.html`
- `tests/classical_app/test_wizard_step2.py` (8 tests)
- `tests/classical_app/test_wizard_step3.py` (9 tests)
- `tests/classical_app/test_wizard_step4.py` (4 tests)
- `tests/classical_app/test_wizard_submit.py` (3 tests)

### Modified files
- `classical_app/app.py` — registers wizard_bp
- `classical_app/routes/delegations.py` — removed wizard_step1 stub
- `classical_app/templates/delegation_detail.html` — url_for updated to `wizard.wizard_step1`
- `tests/classical_app/test_delegations.py` — updated expectation (501→200) for editor POST

---

## How to Resume in a Fresh Session

1. **Read the full plan:**
   `plan/feature-phase2c-wizard-and-confirmation-1.md`

2. **Invoke `/subagent-driven-development`** — worktree already exists at
   `.worktrees/phase2c-wizard` on branch `feature/phase2c-wizard`. Skip
   `using-git-worktrees`.

3. **Re-create TaskCreate entries** from the Pending table above (tasks #11–#15).

4. **Gather context** before dispatching:
   - `classical_app/routes/wizard.py` — current route handlers
   - `classical_app/routes/wizard_helpers.py` — helper functions
   - `classical_app/wizard_state.py` — session helper signatures
   - `classical_app/forms/delegate_wizard.py` — form classes
   - `shared/database.py` — ORM models
   - `shared/business_rules.py` — business rule functions
   - `classical_app/app.py` — db_session via `current_app.extensions["db_session"]`
   - `tests/classical_app/conftest.py` — fixtures

5. **Seed data facts** for tests:
   - FRA delegation: MEMBER, editor=DEL-2026-0001 (Marie Dupont)
   - DEU delegation: MEMBER, no DELEGATION_EDITOR in seed
   - BRA delegation: PARTNER, editor=DEL-2026-0005 (Carlos Silva), active FA on EDU
   - IND delegation: PARTNER, editor=DEL-2026-0007, expired FA on DAC
   - Committees: EDU, TRADE, DAC, ENV, SKILLS
   - DEL-2026-0002 (Jean Martin) is a non-editor on FRA

6. **Next immediate task** (#11 — TASK-014/015): Confirmation GET handler.

---

## Next Task Spec: Confirmation GET Handler (TASK-014/015)

**File to modify:** `classical_app/routes/wizard.py`

**Replace** the `wizard_confirmation` stub with:

### GET:
1. Read `wizard_state.get_created_delegate_id(delegation_id)` — if absent/None,
   redirect to `delegations.delegation_detail`
2. Load `Delegate` by ID: `select(Delegate).where(Delegate.id == delegate_id)`.
   If None, redirect to delegation detail.
3. Load `DocumentAccessRight` records: `select(DocumentAccessRight).where(DocumentAccessRight.delegate_id == delegate_id)`.
4. Load committee names for those DARs' committee_ids.
5. Build `dar_rows` list: `[{'committee_name': ..., 'level': dar.classification_level.value, 'retroactive': dar.retroactive, 'status_label': APPROVAL_LABELS.get(dar.approval_status.value, dar.approval_status.value)} for dar in dars]`
6. Render `wizard/confirmation.html` with `delegate`, `dar_rows`, `delegation_id`.

**`confirmation.html` already exists** with the correct structure.

**`APPROVAL_LABELS`** is already imported in `wizard.py` from `wizard_helpers.py`.

**Imports needed in wizard.py:**
```python
from shared.database import DocumentAccessRight
```
(Add to existing database import block.)

**Additional imports in wizard_helpers.py already present:**
- `DocumentAccessRight` is imported

**Key note:** `wizard_state.get_created_delegate_id(delegation_id)` reads from
`session['created_delegate_id'][delegation_id]`, which is preserved by `clear()`.

---

## Remaining Test Requirements (TASK-018 to TASK-028)

### test_wizard_forms.py (TASK-018)
Create `tests/classical_app/test_wizard_forms.py`:
- Step1: email format validation fails for non-email
- Step2: zero selection fails (`validate_committee_ids`); ≥1 passes
- Step3/DARRowForm: basic field presence (access_level, retroactive, committee_id)

### test_wizard_flow.py (TASK-019-028)
Create `tests/classical_app/test_wizard_flow.py` with integration tests:
- TASK-019: E2E happy path for MEMBER → all 3 approval routes in one run
- TASK-020: PARTNER-with-FA → RESTRICTED allowed; PARTNER-without-FA → RESTRICTED absent
- TASK-021: retroactive=True → PENDING_SECRETARIAT
- TASK-022: Direct GET /step3 without session → redirect /step1
- TASK-023: Cancel clears session; subsequent /step1 GET shows empty form
- TASK-024: Back from step3→step2 preserves selections
- TASK-025: Submit failure (monkeypatched commit IntegrityError) → rollback, no Delegate, re-render step4
- TASK-026: Non-editor POST /step1 → 403
- TASK-027: TTL expiry — updated_at 31 min in past → /step2 GET redirects /step1
- TASK-028: Concurrent delegations — state for FRA and BRA don't clobber each other

### TASK-029: Full pytest suite
Run `pytest tests/ -q --tb=short` targeting ≥140 tests (152 currently + ≥12 new).

**Note:** Many scenarios from TASK-018/019-028 are already partially covered
by test_wizard_step2.py, test_wizard_step3.py, test_wizard_step4.py,
test_wizard_submit.py. Focus test_wizard_flow.py on the remaining gaps:
E2E flows, TTL expiry, concurrent delegations, and 403 enforcement.
