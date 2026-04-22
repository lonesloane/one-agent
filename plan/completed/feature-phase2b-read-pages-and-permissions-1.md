---
goal: Phase 2B — Delegation read pages + editor permissions gating
version: 1.0
date_created: 2026-04-14
last_updated: 2026-04-14
owner: Stephane
status: 'Planned'
tags: [feature, phase2, classical-app, permissions]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 2B delivers the two delegation read pages (`/delegations`, `/delegations/<id>`) and the `@editor_of_delegation_required` permission decorator that the Phase 2C wizard will reuse. Phase 2A is assumed complete: `Delegate.role`, `DocumentAccessRight.retroactive` columns and editor seed data exist. Current `classical_app/` is a single-file Flask app (`app.py`); this phase also introduces the `routes/` package as the first structural step toward the wizard.

## 1. Requirements & Constraints

- **REQ-001**: `GET /delegations` — table: Name, Type, Delegate count, Framework Agreement count. Accessible to every authenticated persona.
- **REQ-002**: `GET /delegations/<id>` — delegation metadata (name, type, FA list) and delegate roster table (name, email, function, committee count).
- **REQ-003**: "Add New Delegate" button rendered only when `session.delegate_id` has `role == 'delegation_editor'` AND `delegation_id == <id>`.
- **REQ-004**: `classical_app/permissions.py` exports `@editor_of_delegation_required(delegation_id)` decorator; direct POST to wizard URL from non-editor returns HTTP 403.
- **REQ-005**: 403 response template visually matches existing Phase 1 `templates/403.html`.
- **REQ-006**: Delegate picker (`templates/switch_delegate.html`) visually distinguishes `delegation_editor` rows via badge/icon.
- **REQ-007**: New test file `tests/classical_app/test_delegations.py` covering: list renders, detail renders, button visibility per persona (editor-of/editor-of-other/non-editor), direct POST to wizard from non-editor → 403.
- **REQ-008**: Full suite (Phase 1A + 1B + 2A) stays green.
- **SEC-001**: 403 enforced server-side via decorator; client-side hiding is cosmetic only.
- **CON-001**: Phase 2A DB columns + seed editors assumed present; no schema or seed changes.
- **CON-002**: No wizard body implementation — only a placeholder POST endpoint for the 403 test.
- **CON-003**: Introduce `routes/` blueprint pattern without regressing existing `app.py` routes.
- **GUD-001**: Follow Phase 1B style: `loguru.logger`, `sqlalchemy.select`, `render_template`, module docstrings, type hints.
- **GUD-002**: Bootstrap 5 classes per `base.html`.
- **PAT-001**: Flask Blueprint `delegations_bp` registered in `create_app`; reuse existing `scoped_session` via `current_app.extensions`.
- **PAT-002**: Decorator is source-of-truth for editor check; templates call a shared helper — no re-derivation in Jinja.

## 2. Implementation Steps

### Implementation Phase 1 — Package scaffolding + permission helper

- GOAL-001: Introduce `routes/` package and `permissions.py` without changing existing behaviour.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `classical_app/routes/__init__.py` (empty module docstring). | | |
| TASK-002 | Create `classical_app/permissions.py` exporting `is_editor_of(db_session, delegate_id, delegation_id) -> bool` and `editor_of_delegation_required(delegation_id_arg='delegation_id')` decorator factory. Decorator reads `session['delegate_id']`, loads the Delegate, `flask.abort(403)` if check fails. | | |
| TASK-003 | In `classical_app/app.py`, import+register `delegations_bp`; expose `db_session` via `flask_app.extensions['db_session']`. | | |
| TASK-004 | Register Jinja global `is_editor_of_delegation(delegation_id)` wrapping `permissions.is_editor_of`. | | |

### Implementation Phase 2 — Delegations list + detail routes

- GOAL-002: Implement `GET /delegations` and `GET /delegations/<id>` plus templates.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `classical_app/routes/delegations.py` with `delegations_bp = Blueprint('delegations', __name__)`. Add `GET /delegations` selecting all Delegation rows, computing `len(d.delegates)` and `len(d.framework_agreements)` per row. | | |
| TASK-006 | Add `GET /delegations/<delegation_id>`: load Delegation (404 if missing), compute committee-count per delegate, pass to template. | | |
| TASK-007 | Create `templates/delegation_list.html` (extends `base.html`): Bootstrap table Name / Type badge / Delegate count / FA count; rows link to detail. | | |
| TASK-008 | Create `templates/delegation_detail.html`: header (name + type badge + FA list); delegate roster table; "Add New Delegate" button inside `{% if is_editor_of_delegation(delegation.id) %}`. | | |
| TASK-009 | Add "Delegations" nav link to `templates/base.html`. | | |

### Implementation Phase 3 — 403 enforcement + wizard stub endpoint

- GOAL-003: Protected POST endpoint sufficient to prove decorator 403 behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Add placeholder `POST /delegations/<delegation_id>/delegates/new/step1` decorated with `@editor_of_delegation_required()`; body returns 501 placeholder. Decorator must hit before body — proves the 403. | | |
| TASK-011 | Update `templates/403.html` to be generic enough for "insufficient DAR" and "not a delegation editor"; optional `reason` variable with neutral default. Retain "Back to Dashboard" button. | | |
| TASK-012 | Ensure global `errorhandler(403)` renders updated template and passes `reason=None` by default. | | |

### Implementation Phase 4 — Editor badge in delegate picker

- GOAL-004: Visually distinguish editor rows.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Edit `templates/switch_delegate.html`: add `<span class="badge bg-warning text-dark">Editor</span>` when `delegate.role == 'delegation_editor'`. | | |
| TASK-014 | Verify existing picker test still passes; add assertion that Editor badge appears for at least one seeded editor. | | |

### Implementation Phase 5 — Tests

- GOAL-005: New test module covering render, visibility gating, 403 enforcement.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Create `tests/classical_app/test_delegations.py`. Reuse existing fixtures. Add fixtures `editor_member_id`, `editor_partner_id`, `editor_other_delegation_id` resolving seeded editors via `Delegate.role` query. | | |
| TASK-016 | `test_list_renders_for_any_persona` — regular delegate GET `/delegations` → 200, all delegation names present. | | |
| TASK-017 | `test_counts_match_seed_data` — delegate/FA counts in response match DB aggregates. | | |
| TASK-018 | `test_detail_renders_for_any_persona` — regular delegate GET `/delegations/<id>` → 200, delegate roster rendered. | | |
| TASK-019 | `test_add_delegate_button_visible_for_editor_of_this_delegation` — editor of X GETs X → substring `Add New Delegate` present. | | |
| TASK-020 | `test_add_delegate_button_hidden_for_non_editor` — regular delegate GETs detail → substring absent. | | |
| TASK-021 | `test_add_delegate_button_hidden_for_editor_of_other_delegation` — editor of Y GETs X → substring absent. | | |
| TASK-022 | `test_direct_post_from_non_editor_returns_403` — regular delegate POSTs wizard URL → 403 and 403 template rendered. | | |
| TASK-023 | `test_direct_post_from_editor_of_other_delegation_returns_403` — editor of Y POSTs X's URL → 403. | | |
| TASK-024 | `test_direct_post_from_correct_editor_does_not_403` — editor of X POSTs X's URL → status != 403 (501 placeholder OK). | | |
| TASK-025 | Run `pytest tests/` — confirm all prior + new tests pass. | | |

## 3. Alternatives

- **ALT-001**: Keep routes in `app.py`. Rejected — Phase 2C adds 5+ wizard endpoints; split now to avoid refactor.
- **ALT-002**: Enforce editor check inside route body. Rejected — decorator guarantees ordering and keeps wizard gate DRY.
- **ALT-003**: Separate `403_permission.html` template. Rejected per PRD §3 "reuse Phase 1 403 style".
- **ALT-004**: Client-only hiding of button. Rejected — SEC-001 mandates server-side 403.

## 4. Dependencies

- **DEP-001**: Phase 2A complete (`Delegate.role`, `DocumentAccessRight.retroactive`, seed editors).
- **DEP-002**: Phase 1B classical app functional (`create_app`, `base.html`, `switch_delegate.html`, `403.html`, delegate-session helper).
- **DEP-003**: `Delegation.delegates` and `Delegation.framework_agreements` relationships usable as defined.
- **DEP-004**: Flask Blueprints, Jinja2 (already in deps).

## 5. Files

- **FILE-001**: `classical_app/routes/__init__.py` — new package marker.
- **FILE-002**: `classical_app/routes/delegations.py` — new blueprint with list, detail, stub POST.
- **FILE-003**: `classical_app/permissions.py` — new helper + decorator.
- **FILE-004**: `classical_app/app.py` — register blueprint, Jinja global, 403 handler.
- **FILE-005**: `classical_app/templates/delegation_list.html` — new.
- **FILE-006**: `classical_app/templates/delegation_detail.html` — new.
- **FILE-007**: `classical_app/templates/403.html` — accept optional `reason`.
- **FILE-008**: `classical_app/templates/switch_delegate.html` — add Editor badge.
- **FILE-009**: `classical_app/templates/base.html` — add Delegations nav link.
- **FILE-010**: `tests/classical_app/test_delegations.py` — new.
- **FILE-011**: `tests/classical_app/conftest.py` — add editor fixtures.

## 6. Testing

- **TEST-001**: `/delegations` renders 200 for every persona.
- **TEST-002**: `/delegations` counts equal DB aggregates.
- **TEST-003**: `/delegations/<id>` renders 200 with delegate roster.
- **TEST-004**: "Add New Delegate" visible only for editor-of-this-delegation.
- **TEST-005**: Direct POST → 403 for non-editor and editor-of-other; not 403 for editor-of-this.
- **TEST-006**: 403 response renders updated template.
- **TEST-007**: Delegate picker shows Editor badge.
- **TEST-008**: Full suite (1A + 1B + 2A) remains green.

## 7. Risks & Assumptions

- **RISK-001**: `Delegation.framework_agreements` relationship name may differ. Mitigation: verify before TASK-005.
- **RISK-002**: Blueprint + `current_app.extensions` may race with existing `scoped_session`/`teardown_appcontext`. Mitigation: reuse same `db_session`; no new session in blueprint.
- **RISK-003**: Editor seed ids not hard-coded. Mitigation: resolve dynamically via `select(Delegate).where(Delegate.role == 'delegation_editor')`.
- **RISK-004**: Editor badge clashes visually. Mitigation: `bg-warning text-dark` or icon.
- **ASSUMPTION-001**: Phase 2A migrated DB; tests use fresh `temp_db`.
- **ASSUMPTION-002**: `session['delegate_id']` always set by `before_request` for non-picker routes.
- **ASSUMPTION-003**: `WTF_CSRF_ENABLED = False` in tests (existing `create_app` convention).

## 8. Related Specifications / Further Reading

- `docs/prd-phase2-classical-write-flows.md` — §2 US-1/US-2, §3 Architecture/Permissions, §4 row 2B.
- `plan/completed/feature-phase1b-classical-app-1.md` — Phase 1B conventions.
- `shared/database.py` — `Delegation`, `Delegate`, `FrameworkAgreement` models.
- `classical_app/app.py` — current route structure.
