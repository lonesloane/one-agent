---
goal: Phase 2C — 4-step delegate-creation wizard with server-side session state, business-rule-driven DAR routing, and confirmation screen
version: 1.0
date_created: 2026-04-14
last_updated: 2026-04-14
owner: Stephane
status: 'Planned'
tags: [feature, phase2, wizard, flask, wtforms]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan delivers Phase 2C of the Classical App write flows: a 4-step delegate-creation wizard (`/delegations/<id>/delegates/new/step{1..4}`) and a confirmation screen, wiring every DAR through `shared.business_rules.determine_approval_route` and `compute_default_access_level`. Phase 2A (schema + seed editors) and Phase 2B (read pages, `@editor_of_delegation_required`) are assumed complete. The wizard uses server-side Flask session state keyed by `delegation_id`, CSRF protection via Flask-WTF defaults, and a single-transaction submit that rolls back on failure. Exit criterion: all three approval routes (`AUTO_APPROVED`, `PENDING_DELEGATION_HEAD`, `PENDING_SECRETARIAT`) reachable end-to-end, and every AC in US-3/US-4/US-5 passes.

## 1. Requirements & Constraints

- **REQ-001**: Four WTForms classes (one per step) in `classical_app/forms/delegate_wizard.py`.
- **REQ-002**: Step 1 validates email format and uniqueness within delegation on submit; fields: `full_name`, `email`, `function`, `title` (optional).
- **REQ-003**: Step 2 multi-select of all committees; ≥1 required.
- **REQ-004**: Step 3: one row per committee from Step 2 with Committee | Access Level | Retroactive. Level dropdown restricted by membership type (member → GENERAL/RESTRICTED/CONFIDENTIAL; partner-no-FA → GENERAL/CONFIDENTIAL; partner-with-active-FA-on-this-committee → GENERAL/RESTRICTED/CONFIDENTIAL). Default preselected via `compute_default_access_level`.
- **REQ-005**: Step 4 read-only review; renders per-DAR routing text from `determine_approval_route` (called in route handler, not Jinja, not reimplemented).
- **REQ-006**: Submit creates `Delegate` + N `delegate_committees` association rows + N `DocumentAccessRight` rows in a single transaction. On exception: `rollback()`, flash error, re-render Step 4.
- **REQ-007**: Session at `flask.session['delegate_wizard'][<delegation_id>] = {'step1': {...}, 'step2': {...}, 'step3': {...}, 'updated_at': <iso>}`. Cleared on cancel/submit; 30-min soft TTL (stale entries purged on access → redirect to Step 1).
- **REQ-008**: Direct GET to `/step2..4` without prior-step data → redirect to `/step1`.
- **REQ-009**: Back preserves data; Cancel clears session and redirects to `/delegations/<id>`.
- **REQ-010**: Confirmation at `/delegations/<id>/delegates/new/confirmation` shows delegate id + name; one bullet per DAR `<committee> — <level> [+ retroactive] (<status>)` with human-readable status. Buttons: "Back to Delegation", "Add Another Delegate".
- **REQ-011**: Created delegate id stashed in session (`created_delegate_id`) so confirmation works after other wizard state clears.
- **SEC-001**: All wizard + confirmation routes decorated with `@editor_of_delegation_required`. CSRF via Flask-WTF defaults on all POSTs (scope disable to test config only).
- **CON-001**: No business logic in wizard — all routing via `determine_approval_route`; all defaults via `compute_default_access_level`.
- **CON-002**: Server-side session only; no client-side state.
- **CON-003**: Additive only — no modifications to `shared/business_rules.py`, `shared/database.py`, or Phase 1B routes.
- **CON-004**: No `MembershipParticipation` table exists; use `delegate_committees` association table for Step 2 persistence.
- **GUD-001**: Follow Phase 1B: `loguru`, `select()`, `scoped_session`, templates extending `base.html`.
- **PAT-001**: Blueprint registration mirrors Phase 2B's `delegations_bp`.
- **PAT-002**: Forms inherit `FlaskForm`. Step 3 uses `FieldList(FormField(DARRowForm))` dynamically sized from Step 2 selection.

## 2. Implementation Steps

### Implementation Phase 1 — Scaffolding & Forms

- GOAL-001: Form layer and route shell with CSRF enabled, no business logic yet.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `classical_app/forms/__init__.py` and `classical_app/forms/delegate_wizard.py` with `Step1PersonalInfoForm`, `Step2CommitteesForm`, `DARRowForm`, `Step3DARsForm`, `Step4ReviewForm`. Email validator on `email`. | | |
| TASK-002 | Create `classical_app/routes/wizard.py` with `Blueprint('wizard', __name__)`. Register `GET/POST` for step1..step4, `GET /confirmation`, `POST /cancel`. Decorate all with `@editor_of_delegation_required`. | | |
| TASK-003 | Register wizard blueprint in `classical_app/app.py`. Enable CSRF (scope `WTF_CSRF_ENABLED=False` to test fixture only). Ensure `secret_key` is set. | | |
| TASK-004 | Create `classical_app/templates/wizard/` with `step1.html`, `step2.html`, `step3.html`, `step4.html`, `confirmation.html`, and `_progress.html` partial. | | |

### Implementation Phase 2 — Session State Helpers

- GOAL-002: Centralize wizard-session read/write/TTL/purge; zero business decisions.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `classical_app/wizard_state.py`: `load`, `save`, `clear`, `is_stale`, `require_steps`. TTL via `updated_at` ISO-8601 UTC vs `datetime.now(timezone.utc)`. | | |
| TASK-006 | Add constants `SESSION_KEY = 'delegate_wizard'`, `TTL_MINUTES = 30`. Add `get_created_delegate_id`/`set_created_delegate_id` for confirmation continuity (REQ-011). | | |

### Implementation Phase 3 — Step Handlers

- GOAL-003: Wire GET/POST for each step using forms + session helpers.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Step 1 GET: pre-fill from session. POST: validate + check email uniqueness within delegation (`SELECT 1 FROM delegates WHERE delegation_id=:id AND lower(email)=lower(:email)`); on pass `save('step1', form.data)` → redirect step2. | | |
| TASK-008 | Step 2 GET: `require_steps(('step1',))`. Build choices from all committees. POST: require ≥1; save; redirect step3. | | |
| TASK-009 | Step 3 GET: `require_steps(('step1','step2'))`. Build `DARRowForm` per committee with filtered `access_level` choices (TASK-010) and default via `compute_default_access_level`. Rehydrate overrides if `step3` in session. POST: save rows; redirect step4. | | |
| TASK-010 | Helper `_allowed_levels(delegation, committee_id) -> list[ClassificationLevel]` in `routes/wizard.py`: MEMBER → all 3; PARTNER → check FA active on `committee_id` → all 3 or [GENERAL, CONFIDENTIAL]. Unit-tested (TEST-004). Mirrors `compute_default_access_level`; does NOT duplicate approval logic. | | |
| TASK-011 | Step 4 GET: `require_steps(('step1','step2','step3'))`. For each row, call `determine_approval_route(classification_level, retroactive)` and build display struct. Render with bare CSRF-only `Step4ReviewForm`. | | |
| TASK-012 | Step 4 POST: single transaction — (a) generate new delegate id; (b) create `Delegate(role='delegate', ...)` from step1; (c) append committees to `delegate.committees`; (d) for each row, compute approval via `determine_approval_route` and create `DocumentAccessRight(delegate_id, committee_id, classification_level, retroactive, approval_status, created_at, created_by)`. Commit. On exception: rollback, flash, log, re-render step4. On success: `set_created_delegate_id`, `clear()` (except `created_delegate_id`), redirect confirmation. | | |
| TASK-013 | Cancel POST `/cancel`: `clear(delegation_id)`; redirect `/delegations/<id>`. | | |

### Implementation Phase 4 — Confirmation & Templates

- GOAL-004: Render all screens; produce all three approval-status labels.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Confirmation GET: read `created_delegate_id`; if absent redirect delegation detail. Load delegate + DARs. Render `confirmation.html`. | | |
| TASK-015 | Module-level `APPROVAL_LABELS = {AUTO_APPROVED: 'auto-approved', PENDING_DELEGATION_HEAD: 'pending delegation head approval', PENDING_SECRETARIAT: 'pending OECD secretariat approval'}`. | | |
| TASK-016 | Flesh out step templates with progress partial, `{{ form.hidden_tag() }}`, Previous/Next/Cancel. Step 3 iterates `form.rows`. Step 4 summary + routing bullets. | | |
| TASK-017 | `confirmation.html`: delegate id+name header, `<ul>` of DARs with `{{ committee }} — {{ level }} {% if retroactive %}+ retroactive{% endif %} ({{ status_label }})`, two buttons. | | |

### Implementation Phase 5 — Tests

- GOAL-005: ≥ 12 new Phase 2C tests (contributing to ≥ 25 target). Full suite green.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | `tests/classical_app/test_wizard_forms.py`: Step 1 email-format fail, email-uniqueness-within-delegation fail + allow across delegations. Step 2 zero fails, ≥1 passes. Step 3 per-row validation. | | |
| TASK-019 | `tests/classical_app/test_wizard_flow.py`: end-to-end happy path for MEMBER producing one DAR of each status. Assert DB rows, associations, statuses, confirmation labels. | | |
| TASK-020 | PARTNER-with-FA on X → Restricted allowed in dropdown; PARTNER-without-FA → Restricted absent. | | |
| TASK-021 | Retroactive=True → PENDING_SECRETARIAT regardless of level. | | |
| TASK-022 | Direct GET `/step3` without session → redirect `/step1`. Direct GET `/step2` with only `step1` renders. | | |
| TASK-023 | Cancel clears session and redirects; subsequent `/step1` GET shows empty form. | | |
| TASK-024 | Back from step3 → step2 preserves selections; Back from step4 → step3 preserves overrides. | | |
| TASK-025 | Submit failure (monkeypatched commit IntegrityError) rolls back — no `Delegate`, no DARs — and re-renders step4 with flash. | | |
| TASK-026 | Non-editor POSTing `/step1` → 403. | | |
| TASK-027 | TTL expiry — `updated_at` 31 min in past → `/step2` GET redirects `/step1` and prior data cleared. | | |
| TASK-028 | Concurrent-delegation isolation — state for A and B in same session; advancing A does not clobber B. | | |
| TASK-029 | Run full `pytest` — confirm 1A/1B/2A/2B/2C green. Fix any CSRF breakage via test fixture `WTF_CSRF_ENABLED=False`. | | |

## 3. Alternatives

- **ALT-001**: Client-side JS wizard with single end POST. Rejected — PRD mandates server-side session; preserves click-heavy contrast.
- **ALT-002**: Single omnibus form. Rejected — PRD mandates 4 discrete URLs for demo visibility.
- **ALT-003**: Persist partial state in `wizard_draft` DB table. Rejected — session sufficient; avoids schema churn.
- **ALT-004**: Allowed-levels helper in `shared/business_rules.py`. Viable but out of scope (CON-003). If Phase 2A added it, reuse instead of `_allowed_levels`.

## 4. Dependencies

- **DEP-001**: Phase 2A complete — `role` column, `retroactive` column, editor seed.
- **DEP-002**: Phase 2B complete — `permissions.py`, `/delegations` + `/delegations/<id>`, "Add New Delegate" button.
- **DEP-003**: `shared/business_rules.py` unchanged — `compute_default_access_level` and `determine_approval_route` signatures verified.
- **DEP-004**: `Flask-WTF` present.
- **DEP-005**: Delegate id generator from Phase 1A.

## 5. Files

- **FILE-001**: `classical_app/forms/__init__.py` — marker.
- **FILE-002**: `classical_app/forms/delegate_wizard.py` — 4 forms + `DARRowForm`.
- **FILE-003**: `classical_app/routes/__init__.py` — marker.
- **FILE-004**: `classical_app/routes/wizard.py` — blueprint + `_allowed_levels` + `APPROVAL_LABELS`.
- **FILE-005**: `classical_app/wizard_state.py` — session helpers.
- **FILE-006**: `classical_app/templates/wizard/*.html` — 5 templates + progress partial.
- **FILE-007**: `classical_app/app.py` — register blueprint; CSRF scoping.
- **FILE-008**: `tests/classical_app/test_wizard_forms.py`, `test_wizard_flow.py` — new.
- **FILE-009**: `tests/classical_app/conftest.py` — extend with test CSRF-disable if needed.

## 6. Testing

- **TEST-001**: Step 1 email format + uniqueness (US-3).
- **TEST-002**: Step 2 ≥1 required (US-3).
- **TEST-003**: Step 3 rows per committee, default preselected (US-3).
- **TEST-004**: `_allowed_levels` matrix (MEMBER/PARTNER-no-FA/PARTNER-with-FA).
- **TEST-005**: Step 4 status labels from `determine_approval_route` (US-3, US-4).
- **TEST-006**: E2E creates all 3 approval routes in one run (US-5).
- **TEST-007**: Retroactive → PENDING_SECRETARIAT (US-5).
- **TEST-008**: Direct-nav without data → step1 (REQ-008).
- **TEST-009**: Cancel clears; Back preserves (US-3).
- **TEST-010**: Submit rollback on failure (US-3).
- **TEST-011**: 403 for non-editor POST (SEC-001).
- **TEST-012**: 30-min TTL eviction (REQ-007).
- **TEST-013**: Concurrent delegations isolated (REQ-007).
- **TEST-014**: Confirmation shows correct status strings + both buttons (US-4).
- **TEST-015**: Full 1A+1B+2 suite green.

## 7. Risks & Assumptions

- **RISK-001**: Phase 2B decorator name/signature may differ. Mitigation: verify before TASK-002.
- **RISK-002**: `MembershipParticipation` not in schema. Mitigation: use `delegate_committees` association.
- **RISK-003**: Enabling CSRF may break `/switch-delegate` POST tests. Mitigation: test-fixture-scoped disable.
- **RISK-004**: Delegate id generator location unknown. Mitigation: locate during TASK-012; else generate `DEL-<year>-<seq>` consistently.
- **RISK-005**: Session cookie size with many committees. Mitigation: store ids + minimal row data; 4KB limit is ample.
- **ASSUMPTION-001**: `ClassificationLevel` contains GENERAL/RESTRICTED/CONFIDENTIAL.
- **ASSUMPTION-002**: `ApprovalStatus.AUTO_APPROVED` is the auto-approved value.
- **ASSUMPTION-003**: `@editor_of_delegation_required` accepts `delegation_id` path param.
- **ASSUMPTION-004**: Flask-WTF already installed.

## 8. Related Specifications / Further Reading

- `docs/prd-phase2-classical-write-flows.md` — §2 US-3/US-4/US-5; §3 Wizard state + Business-rule integration; §4 row 2C.
- `shared/business_rules.py` — single source of truth.
- `shared/database.py` — `ApprovalStatus`, `ClassificationLevel`, `Delegate`, `DocumentAccessRight`, `delegate_committees`.
- `plan/completed/feature-phase1b-classical-app-1.md` — Phase 1B conventions.
- `classical_app/app.py` — Flask factory.
