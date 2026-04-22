---
goal: "Phase 1B: Classical Flask App — 6 Read Screens + Delegate Picker"
version: 1.0
date_created: 2026-04-11
owner: stephane
status: 'Complete'
tags: [feature, classical-app, phase-1]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Build the classical Flask web app (`classical_app/`) that demonstrates the
click-heavy status quo for UC1 read flows. This is the **contrast tool** —
6 screens, 5 clicks, zero proactive intelligence. The delegate must
navigate to the information themselves.

This plan depends on Plan A (`feature-phase1a-shared-data-layer`) being
complete. All data access and business logic comes from the `shared/`
package — the Flask app is a thin presentation layer.

**Prerequisite**: `shared/database.py`, `shared/business_rules.py`,
`shared/seed_data.py`, and `one_agent.db` must exist and pass all tests.

## 1. Requirements & Constraints

- **REQ-001**: 6 read-only screens implementing the UC1 flow: Dashboard →
  My Committees → Committee Detail → Upcoming Meetings → Meeting Detail
  + Agenda → Document Detail.
- **REQ-002**: Delegate picker — dropdown or dedicated page to switch
  the impersonated delegate. Selection stored in Flask session. Delegate
  name + delegation shown in navbar.
- **REQ-003**: Document visibility enforced — Meeting Detail screen
  shows only documents the current delegate can see (via
  `get_visible_agenda_documents` from shared layer). Hidden documents
  simply don't appear — no "access denied" rows.
- **REQ-004**: Document Detail screen returns 403 if the current
  delegate's DAR does not permit viewing that document (via
  `is_document_visible` from shared layer).
- **REQ-005**: If no delegate is selected (no `delegate_id` in session),
  redirect to the delegate picker.
- **REQ-006**: All screens render correctly with seed data — no empty
  states, no broken links (SC-1 from PRD).
- **REQ-007**: The dashboard deliberately shows no upcoming-meeting
  summary, no "new since last visit" markers, no highlighted changes.
  This absence is by design — the contrast with the agent app.
- **SEC-001**: No real authentication. The delegate picker is a demo
  convenience, not a security feature.
- **CON-001**: Bootstrap 5 via CDN. No custom CSS. The app should look
  functional, not beautiful.
- **CON-002**: Flask + Jinja2 + Flask-WTF. No additional frontend
  frameworks.
- **CON-003**: All data comes from `one_agent.db` via the shared layer.
  No direct SQL — use SQLAlchemy ORM exclusively.
- **GUD-001**: Follow PEP 8, Google-style docstrings, type hints per
  `CLAUDE.md`.
- **GUD-002**: No file over 500 lines. If `app.py` grows large, split
  routes into a Flask Blueprint.
- **PAT-001**: Use `scoped_session` or a request-scoped session pattern
  to ensure each request gets a clean session.

## 2. Implementation Steps

### Phase 1: Flask App Scaffolding

- GOAL-001: Create the `classical_app` package, add Flask dependencies,
  set up the base application and session management.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `classical_app/__init__.py` (package init) | ✅ | 2026-04-12 |
| TASK-002 | Update `pyproject.toml`: add `flask>=3.0` and `flask-wtf>=1.2` to `dependencies`; add `"classical_app"` to `[tool.setuptools] packages` list | ✅ | 2026-04-12 |
| TASK-003 | Run `pip install -e ".[dev]"` to install new dependencies | ✅ | 2026-04-12 |
| TASK-004 | Create `classical_app/app.py` — Flask app factory or module-level app. Configure: `SECRET_KEY` (hardcoded demo value is fine), SQLAlchemy session setup (bind to `one_agent.db`), `before_request` hook to load current delegate from session and redirect to picker if absent. | ✅ | 2026-04-12 |
| TASK-005 | Create `classical_app/templates/` directory | ✅ | 2026-04-12 |
| TASK-006 | Create `classical_app/templates/base.html` — base Jinja2 template with Bootstrap 5 CDN, navbar showing app name ("ONE MP — Delegation Management Portal"), current delegate name + delegation, "Switch Delegate" link. Use Jinja2 template inheritance (`{% block content %}`). | ✅ | 2026-04-12 |

### Phase 2: Delegate Picker

- GOAL-002: Implement the delegate selection mechanism so all subsequent
  screens have a current delegate context.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Create `GET /switch-delegate` route — query all delegates (grouped by delegation), render a delegate picker page (table or list with delegate name, delegation, function). | ✅ | 2026-04-12 |
| TASK-008 | Create `classical_app/templates/switch_delegate.html` — list all delegates, each as a clickable row or button that POSTs the selected `delegate_id`. | ✅ | 2026-04-12 |
| TASK-009 | Create `POST /switch-delegate` route — receive `delegate_id` from form, store in `session['delegate_id']`, redirect to `/` (dashboard). | ✅ | 2026-04-12 |
| TASK-010 | Verify: when no delegate is in session, any route redirects to `/switch-delegate`. After selecting a delegate, navbar shows their name and delegation. | ✅ | 2026-04-12 |

### Phase 3: Dashboard (Screen 1)

- GOAL-003: Implement the dashboard — welcome message, navigation links,
  deliberately no proactive information.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Create `GET /` route — load current delegate and delegation from DB, render dashboard template. | ✅ | 2026-04-12 |
| TASK-012 | Create `classical_app/templates/dashboard.html` — welcome message with delegate name, delegation name, and navigation cards/links: "My Committees". No upcoming-meeting summary, no notifications (REQ-007). | ✅ | 2026-04-12 |

### Phase 4: My Committees (Screen 2)

- GOAL-004: List the current delegate's committees with next meeting date.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Create `GET /committees` route — query the delegate's committees via the M2M relationship. For each committee, subquery or eager-load the next upcoming meeting date (earliest future `Meeting.date` for that committee). Pass to template. | ✅ | 2026-04-12 |
| TASK-014 | Create `classical_app/templates/committees.html` — table with columns: Committee Name (link to `/committees/<id>`), Next Meeting Date (or "—" if none). | ✅ | 2026-04-12 |

### Phase 5: Committee Detail (Screen 3)

- GOAL-005: Show committee name, description, and navigation links.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Create `GET /committees/<id>` route — load committee by ID. Verify the current delegate participates in this committee (if not, 404 or redirect). Render template. | ✅ | 2026-04-12 |
| TASK-016 | Create `classical_app/templates/committee_detail.html` — committee name, description, navigation links: "Upcoming Meetings" (→ `/committees/<id>/meetings`). | ✅ | 2026-04-12 |

### Phase 6: Upcoming Meetings (Screen 4)

- GOAL-006: List future meetings for a committee, ordered by date.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Create `GET /committees/<id>/meetings` route — query `Meeting` where `committee_id == id` and `date > now()`, ordered by date ascending. For each meeting, compute the visible agenda document count for the current delegate (using `get_visible_agenda_documents` from shared layer). | ✅ | 2026-04-12 |
| TASK-018 | Create `classical_app/templates/upcoming_meetings.html` — table with columns: Date, Title (link to `/meetings/<id>`), Location, Docs (visible count). Show committee name in heading. | ✅ | 2026-04-12 |

### Phase 7: Meeting Detail + Agenda (Screen 5)

- GOAL-007: Show meeting info and the filtered agenda documents. This is
  where document visibility enforcement is most visible.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-019 | Create `GET /meetings/<id>` route — load meeting + committee. Call `get_visible_agenda_documents(delegate_id, meeting_id, session)` from shared layer. Render template with meeting info and filtered document list. | ✅ | 2026-04-12 |
| TASK-020 | Create `classical_app/templates/meeting_detail.html` — meeting title, date, location, committee name. Table of agenda documents with columns: Item # (item_order), Document Title (link to `/documents/<id>`), Classification Level, Last Modified. No "new since last visit" indicators (REQ-007). | ✅ | 2026-04-12 |

### Phase 8: Document Detail (Screen 6)

- GOAL-008: Show document metadata. Return 403 if delegate cannot see it.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | Create `GET /documents/<id>` route — load document by ID. Call `is_document_visible(delegate_id, document, session)` from shared layer. If not visible, `abort(403)`. Otherwise render template. | ✅ | 2026-04-12 |
| TASK-022 | Create `classical_app/templates/document_detail.html` — document title, classification level, committee name, publication date, last modified date, summary text. "[Download PDF]" placeholder link (no actual file). | ✅ | 2026-04-12 |
| TASK-023 | Create `classical_app/templates/403.html` — custom error page for access denied. | ✅ | 2026-04-12 |

### Phase 9: Run Script & Smoke Test

- GOAL-009: Provide a way to run the app and verify all screens work
  end-to-end with seed data.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-024 | Add `if __name__ == "__main__"` block to `classical_app/app.py` (or create `scripts/run_classical.py`) — `app.run(debug=True, port=5000)`. | ✅ | 2026-04-12 |
| TASK-025 | Manual smoke test: walk the full UC1 flow (Dashboard → My Committees → Committee Detail → Upcoming Meetings → Meeting Detail → Document Detail) for at least 2 delegates (1 member, 1 partner). Verify all screens render, visibility filtering works, no broken links. | ⏳ | pending |
| TASK-026 | Switch to a partner delegate — verify fewer committees visible, fewer documents visible on meeting agendas. Verify a Restricted document visible as member is NOT visible as partner (unless FA applies). | ⏳ | pending |

### Phase 10: Tests

- GOAL-010: Test Flask routes using Flask's test client. Verify correct
  rendering, session handling, and visibility enforcement.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-027 | Create `tests/classical_app/__init__.py` and `tests/classical_app/conftest.py` — Flask test client fixture using in-memory SQLite with seed data loaded. | ✅ | 2026-04-12 |
| TASK-028 | `tests/classical_app/test_routes.py` — test delegate picker: GET renders list, POST sets session, redirect works. Test session-less request redirects to picker. | ✅ | 2026-04-12 |
| TASK-029 | `tests/classical_app/test_routes.py` — test dashboard: returns 200, contains delegate name and delegation name. | ✅ | 2026-04-12 |
| TASK-030 | `tests/classical_app/test_routes.py` — test My Committees: returns only the current delegate's committees (not all committees). | ✅ | 2026-04-12 |
| TASK-031 | `tests/classical_app/test_routes.py` — test Committee Detail: returns 200 for a committee the delegate participates in. | ✅ | 2026-04-12 |
| TASK-032 | `tests/classical_app/test_routes.py` — test Upcoming Meetings: returns only future meetings, ordered by date. | ✅ | 2026-04-12 |
| TASK-033 | `tests/classical_app/test_routes.py` — test Meeting Detail: returns visible documents only. Verify a Confidential doc is NOT in the response body for a delegate with Restricted DAR. | ✅ | 2026-04-12 |
| TASK-034 | `tests/classical_app/test_routes.py` — test Document Detail: returns 200 for a visible document. Returns 403 for a document the delegate cannot see. | ✅ | 2026-04-12 |
| TASK-035 | Run full test suite: `pytest` — all tests pass (shared layer + classical app). | ✅ | 2026-04-12 |

## 3. Alternatives

- **ALT-001**: Use Flask Blueprints from the start. Rejected for Phase 1:
  6 routes fit comfortably in a single `app.py`. If Phase 2 write flows
  push the file past 500 lines, refactor to Blueprints then.
- **ALT-002**: Use server-side rendering with HTMX instead of full page
  loads. Rejected: adds unnecessary complexity for a PoC contrast tool.
  Full page loads make the click count more obvious.
- **ALT-003**: Use Django instead of Flask. Rejected: Flask is lighter,
  the team has prior experience, and Django's admin/ORM would compete
  with the shared SQLAlchemy layer.
- **ALT-004**: Build a REST API + SPA frontend. Rejected: the point is
  to show a traditional multi-page, click-heavy app. A SPA would
  undermine the contrast narrative.

## 4. Dependencies

- **DEP-001**: `flask>=3.0` — web framework (new dependency)
- **DEP-002**: `flask-wtf>=1.2` — form handling for delegate picker and
  future write forms (new dependency)
- **DEP-003**: Plan A (`feature-phase1a-shared-data-layer`) must be
  complete — `shared/` package, `one_agent.db` with seed data
- **DEP-004**: Bootstrap 5 via CDN — no install, loaded in base template

## 5. Files

- **FILE-001**: `classical_app/__init__.py` — package init (new)
- **FILE-002**: `classical_app/app.py` — Flask app, routes, session
  management (new, ~200–350 lines)
- **FILE-003**: `classical_app/templates/base.html` — base layout with
  navbar (new)
- **FILE-004**: `classical_app/templates/switch_delegate.html` (new)
- **FILE-005**: `classical_app/templates/dashboard.html` (new)
- **FILE-006**: `classical_app/templates/committees.html` (new)
- **FILE-007**: `classical_app/templates/committee_detail.html` (new)
- **FILE-008**: `classical_app/templates/upcoming_meetings.html` (new)
- **FILE-009**: `classical_app/templates/meeting_detail.html` (new)
- **FILE-010**: `classical_app/templates/document_detail.html` (new)
- **FILE-011**: `classical_app/templates/403.html` — access denied (new)
- **FILE-012**: `tests/classical_app/__init__.py` (new)
- **FILE-013**: `tests/classical_app/conftest.py` — test fixtures (new)
- **FILE-014**: `tests/classical_app/test_routes.py` — route tests (new)
- **FILE-015**: `pyproject.toml` — updated dependencies and packages
  (existing)

## 6. Testing

- **TEST-001**: Delegate picker — GET renders delegate list, POST sets
  session and redirects, session-less request redirects to picker.
- **TEST-002**: Dashboard — returns 200, contains delegate name and
  delegation name in response body.
- **TEST-003**: My Committees — returns only committees the delegate
  participates in (filtered, not all).
- **TEST-004**: Committee Detail — 200 for valid committee participation,
  404 for non-participating committee.
- **TEST-005**: Upcoming Meetings — returns only future meetings, ordered
  by date, with correct visible document counts.
- **TEST-006**: Meeting Detail — returns only visible agenda documents.
  Confidential doc absent for Restricted-level delegate.
- **TEST-007**: Document Detail — 200 for visible document, 403 for
  invisible document.
- **TEST-008**: End-to-end UC1 flow — walk all 6 screens sequentially
  with test client, verify no 500 errors, no broken links.
- **TEST-009**: Delegate switching — switch delegate via POST, verify
  subsequent requests reflect new delegate's data.

## 7. Risks & Assumptions

- **RISK-001**: Agenda document count on Upcoming Meetings screen
  (TASK-017) may be expensive if there are many documents. Mitigation:
  PoC scale is small (~40 agenda items total). If needed, cache counts.
- **RISK-002**: Flask session cookie size limit (~4KB) could be an issue
  if more data is stored later. Mitigation: Phase 1 only stores
  `delegate_id` (a short string). Acceptable.
- **RISK-003**: Template styling may look inconsistent across screens.
  Mitigation: Bootstrap 5 defaults are consistent enough. No custom CSS
  means no CSS bugs.
- **ASSUMPTION-001**: Plan A is complete and `one_agent.db` exists with
  seed data before this plan starts.
- **ASSUMPTION-002**: The app runs single-user (demo operator). No
  concurrent session concerns.
- **ASSUMPTION-003**: "Upcoming meetings" means `Meeting.date > now()`.
  Meetings on today's date are included as upcoming.

## 8. Related Specifications / Further Reading

- [PRD: Phase 1 — Shared Data Layer + Classical App (Read Flows)](../docs/prd-phase1-shared-layer-and-classical-read.md)
- [Plan A: Shared Data Layer](feature-phase1a-shared-data-layer-1.md) — prerequisite plan
- [Brainstorming: Dual-Demo Architecture](../docs/brainstorming/ONE-Agent-PoC-dual-demo.md) — screen flow wireframes (lines 352–438)
- [Backlog](../docs/BACKLOG.md) — Phase 1 items
