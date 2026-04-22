---
goal: pytest-playwright E2E test suite automating the Phase 2 demo dry-run (Scenarios A–F)
version: 1.0
date_created: 2026-04-19
last_updated: 2026-04-19
owner: Stephane
status: 'Done'
tags: [feature, testing, e2e, playwright]
---

# Introduction

![Status: Done](https://img.shields.io/badge/status-Done-brightgreen)

Automate the manual walkthrough described in `docs/DEMO_PHASE2.md` using
`pytest-playwright` (Python). The suite covers all six scenarios: three
approval routes (A–C), retroactive override (D), permission gates (E), and
cancel/session-clear (F). A thread-based Werkzeug live server is used so that
test-side SQLAlchemy queries can inspect the same database as the running app,
enabling the DB-state assertions required by Scenarios A–D.

---

## 1. Requirements & Constraints

- **REQ-001**: All six scenarios from `docs/DEMO_PHASE2.md` must be covered
  (A: AUTO_APPROVED, B: PENDING_SECRETARIAT, C: PENDING_DELEGATION_HEAD,
  D: retroactive override, E: permission gates, F: cancel/session-clear).
- **REQ-002**: DB-state assertions (e.g., 1 new `Delegate` + 2 `DAR` rows with
  expected `approval_status`) must query the database directly, not infer state
  from the UI.
- **REQ-003**: Each test must run against a fresh seeded database to prevent
  row-bleed between scenarios A–D.
- **REQ-004**: "Login" must go through the real `/switch-delegate` POST — no
  cookie forgery (Flask signs sessions with `secret_key`).
- **REQ-005**: 403 checks in Scenario E must use `page.request.post()` to keep
  session cookies consistent with the browser context.
- **CON-001**: `classical_app/app.py` executes `app = create_app()` at module
  level; `ONE_AGENT_DB_PATH` must **not** be the deciding factor — the E2E
  conftest must call `create_app(db_url=...)` directly and never rely on the
  module-level singleton.
- **CON-002**: `WTF_CSRF_ENABLED = False` is already set inside `create_app()`
  — no extra config needed.
- **CON-003**: Wizard blueprint `wizard_bp` is registered in `create_app()` at
  `classical_app/app.py:390–393`. All wizard URLs are rooted under
  `/delegations/<delegation_id>/delegates/new/`.
- **GUD-001**: Follow PEP 8 and existing project conventions (79-char lines,
  Google-style docstrings on public fixtures, `loguru` for any logging).
- **GUD-002**: The "rollback verification" scenario (temporarily breaking
  `session.commit`) is **out of scope** for this E2E suite; it belongs to unit
  tests with mocked commits.

---

## 2. Implementation Steps

### Implementation Phase 1 — Infrastructure

- **GOAL-001**: Install dependencies, create the live-server + DB-reset +
  login fixtures, and verify with a smoke test that the server starts and
  redirects an unauthenticated visitor to `/switch-delegate`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Run `pip install pytest-playwright` and `playwright install chromium` in the active venv. Add `pytest-playwright` to `pyproject.toml` under `[project.optional-dependencies] dev`. | ✓ | 2026-04-19 |
| TASK-002 | Create `tests/e2e/__init__.py` (empty, marks directory as package). | ✓ | 2026-04-19 |
| TASK-003 | Create `tests/e2e/conftest.py`. Implement the following session-scoped fixtures: `e2e_db_path` (tmp_path_factory temp file), `e2e_engine` (calls `get_engine` + `init_db` + `seed_all` on that path), `e2e_app` (calls `create_app(db_url=f"sqlite:///{e2e_db_path}")` with `TESTING=True`), `live_server` (starts Werkzeug `make_server("127.0.0.1", 5001, app)` in a daemon thread; yields the base URL string; calls `server.shutdown()` on teardown). Also implement: `reset_db` (function-scoped `autouse=True`; calls `e2e_app.extensions["db_session"].remove()`, then `Base.metadata.drop_all(e2e_engine)`, then `init_db(e2e_engine)`, then `seed_all` in a new session); `login_as` (function-scoped factory fixture; accepts `delegate_id: str` and a Playwright `page`; navigates to `/switch-delegate`, fills and submits the delegate picker form, then asserts the page URL contains `/`). | ✓ | 2026-04-19 |
| TASK-004 | Create `tests/e2e/test_smoke.py`. One test: assert `page.goto(base_url + "/")` results in the page URL ending with `/switch-delegate` (unauthenticated redirect). Run `pytest tests/e2e/test_smoke.py -v` — must be green before proceeding. | ✓ | 2026-04-19 |

### Implementation Phase 2 — Scenario A (AUTO_APPROVED)

- **GOAL-002**: Prove the full happy-path wizard flow and DB-state assertion
  work end-to-end for the AUTO_APPROVED route.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `tests/e2e/test_scenario_a.py`. Login as `DEL-2026-0001` (Marie Dupont). Navigate to `GET /delegations/FRA/delegates/new/step1`. Fill Step 1: full_name=`Alice Leblanc`, email=`alice.leblanc@example.com`, function=`Policy Analyst`, title=`Ms`. Click Next; assert URL ends with `step2`. | ✓ | 2026-04-19 |
| TASK-006 | Continue Scenario A: Step 2 — select checkboxes for `EDU` and `TRADE`. Click Next; assert URL ends with `step3`. Step 3 — for each committee row, select access level `GENERAL` and leave retroactive unchecked. Click Next; assert URL ends with `step4`. | ✓ | 2026-04-19 |
| TASK-007 | Continue Scenario A: Step 4 — assert review table shows both committees with `GENERAL / non-retroactive`. Click Submit. Assert URL ends with `confirmation`. Assert confirmation page contains "Alice Leblanc". Then query `e2e_engine` directly: assert exactly 1 `Delegate` row where `full_name = "Alice Leblanc"`, and exactly 2 `DocumentAccessRight` rows for that delegate both with `approval_status = AUTO_APPROVED`. Run `pytest tests/e2e/test_scenario_a.py -v` — must be green. | ✓ | 2026-04-19 |

### Implementation Phase 3 — Scenarios B, C, D (parameterized)

- **GOAL-003**: Cover the three remaining approval routes (PENDING_SECRETARIAT,
  PENDING_DELEGATION_HEAD, and retroactive override) by parameterising the
  Scenario A flow.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | Create `tests/e2e/test_scenarios_bcd.py`. Use `@pytest.mark.parametrize` with three parameter sets: (B) name=`Bob Renard`, email=`bob.renard@example.com`, level=`CONFIDENTIAL`, retroactive=`False`, expected_status=`PENDING_SECRETARIAT`; (C) name=`Claire Morel`, email=`claire.morel@example.com`, level=`RESTRICTED`, retroactive=`False`, expected_status=`PENDING_DELEGATION_HEAD`; (D) name=`Denis Fontaine`, email=`denis.fontaine@example.com`, level=`GENERAL` (both committees), retroactive=`True` (both), expected_status=`PENDING_SECRETARIAT`. For each: run the full wizard flow (login, steps 1–4, submit), verify confirmation page, then DB-assert 2 DARs with the expected `approval_status`. | ✓ | 2026-04-19 |

### Implementation Phase 4 — Scenario E (permission gates)

- **GOAL-004**: Verify that the "Add New Delegate" button is hidden for
  non-editors, and that direct POSTs to the wizard return 403 for
  non-editors and editors of other delegations.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create `tests/e2e/test_scenario_e.py`. **E-1**: Login as `DEL-2026-0002` (Jean Martin). Navigate to `/delegations/FRA`. Assert the "Add New Delegate" link is absent (locator count = 0). | ✓ | 2026-04-19 |
| TASK-010 | **E-2**: Still as Jean Martin, use `page.request.post(base_url + "/delegations/FRA/delegates/new/step1", form={"full_name": "X"})`. Assert response status is 403. | ✓ | 2026-04-19 |
| TASK-011 | **E-3**: Login as `DEL-2026-0005` (Carlos Silva, BRA editor). Use `page.request.post(base_url + "/delegations/FRA/delegates/new/step1", form={"full_name": "X"})`. Assert response status is 403. | ✓ | 2026-04-19 |

### Implementation Phase 5 — Scenario F (cancel / session clear)

- **GOAL-005**: Verify that clicking Cancel from Step 3 clears wizard state
  and that navigating directly to Step 3 redirects to Step 1.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Create `tests/e2e/test_scenario_f.py`. Login as `DEL-2026-0001`. Complete Steps 1 and 2 (same data as Scenario A). Assert URL ends with `step3` (GET renders successfully). POST to `/delegations/FRA/delegates/new/cancel` via the Cancel button (or `page.request.post`). Assert redirect lands on `/delegations/FRA`. | ✓ | 2026-04-19 |
| TASK-013 | Continue Scenario F: Navigate directly to `/delegations/FRA/delegates/new/step3`. Assert the final URL ends with `step1` (wizard state was cleared; `require_steps` redirected). | ✓ | 2026-04-19 |

---

## 3. Alternatives

- **ALT-001**: **Subprocess live server** — start Flask as a child process via
  `subprocess.Popen`. Rejected: cannot share the SQLAlchemy engine with the
  test process, making DB-state assertions (Scenarios A–D) impossible without
  an extra IPC layer.
- **ALT-002**: **`pytest-flask` `live_server` fixture** — adds a dependency for
  equivalent functionality. Rejected: the thread-based Werkzeug approach
  achieves the same result with zero extra packages.
- **ALT-003**: **playwright-cli code generator** — records browser interactions
  and emits JavaScript/TypeScript. Rejected: the project is Python-only and
  requires Python-side DB assertions.
- **ALT-004**: **Per-test temp DB + per-test server** — one `create_app()` call
  per test. Rejected: Werkzeug startup time would multiply test suite
  wall-clock time significantly.
- **ALT-005**: **`requests` library for 403 checks** — would require a separate
  session-cookie sync mechanism. Rejected in favour of
  `page.request.post()` which shares the browser context and cookies.

---

## 4. Dependencies

- **DEP-001**: `pytest-playwright` — Python Playwright bindings + pytest plugin.
  Install: `pip install pytest-playwright` + add to `pyproject.toml` dev extras.
- **DEP-002**: `playwright` Chromium browser — `playwright install chromium`.
- **DEP-003**: `Werkzeug` — already installed as a Flask transitive dependency;
  `werkzeug.serving.make_server` is used for the thread-based live server.
- **DEP-004**: `shared.database` — `get_engine`, `init_db`, `Base` — used in
  `reset_db` and DB-assertion helpers.
- **DEP-005**: `shared.seed_data.seed_all` — used in `reset_db` to restore
  clean state before each test.

---

## 5. Files

- **FILE-001**: `tests/e2e/__init__.py` — new empty package marker.
- **FILE-002**: `tests/e2e/conftest.py` — new; session-scoped live server,
  function-scoped DB reset, `login_as` factory, `base_url` fixture.
- **FILE-003**: `tests/e2e/test_smoke.py` — new; Phase 1 checkpoint test.
- **FILE-004**: `tests/e2e/test_scenario_a.py` — new; AUTO_APPROVED full flow.
- **FILE-005**: `tests/e2e/test_scenarios_bcd.py` — new; parameterized
  PENDING_* and retroactive flows.
- **FILE-006**: `tests/e2e/test_scenario_e.py` — new; permission gate checks.
- **FILE-007**: `tests/e2e/test_scenario_f.py` — new; cancel / session-clear.
- **FILE-008**: `pyproject.toml` — modified; add `pytest-playwright` to
  `[project.optional-dependencies] dev`.

---

## 6. Testing

- **TEST-001**: Smoke test (`test_smoke.py`) — unauthenticated GET `/` redirects
  to `/switch-delegate`. Must pass before any other E2E test is written.
- **TEST-002**: Scenario A DB assertion — exactly 1 `Delegate` row with
  `full_name = "Alice Leblanc"` and exactly 2 `DocumentAccessRight` rows with
  `approval_status = ApprovalStatus.AUTO_APPROVED`.
- **TEST-003**: Scenarios B/C/D DB assertions — 2 DARs each with the expected
  `approval_status` value per parametrize case.
- **TEST-004**: Scenario E-1 — Playwright locator for "Add New Delegate" link
  returns count 0 for non-editor.
- **TEST-005**: Scenarios E-2 and E-3 — `page.request.post()` returns HTTP 403.
- **TEST-006**: Scenario F — after Cancel, navigating to `step3` redirects to
  `step1`.
- **TEST-007**: Full suite regression — `pytest tests/e2e/ -v` must be green
  without affecting the existing 188 unit tests in `tests/classical_app/` and
  `tests/shared/`.

---

## 7. Risks & Assumptions

- **RISK-001**: SQLite write-locking between the live-server thread and the
  `reset_db` fixture. Mitigated by calling
  `e2e_app.extensions["db_session"].remove()` before DDL to release any
  thread-local connection held by the scoped session.
- **RISK-002**: `classical_app/app.py` module-level `app = create_app()` (line
  399) fires at import time and may connect to the wrong DB. Mitigated by
  always using `create_app(db_url=...)` directly in `e2e_app` and never
  importing the module-level singleton in test code.
- **RISK-003**: Werkzeug single-threaded dev server may serialize requests in
  unexpected ways for multi-step wizard sessions. Acceptable — each Playwright
  step awaits a network idle before proceeding.
- **ASSUMPTION-001**: Seed delegate IDs are stable: `DEL-2026-0001` = Marie
  Dupont (FRA editor), `DEL-2026-0002` = Jean Martin (FRA delegate),
  `DEL-2026-0005` = Carlos Silva (BRA editor).
- **ASSUMPTION-002**: Step 3 form field names follow the pattern
  `rows-{i}-access_level` and `rows-{i}-retroactive` as implemented in
  `wizard.py::_handle_step3_post`.
- **ASSUMPTION-003**: The `wizard_bp` blueprint is registered in `create_app()`
  at `classical_app/app.py:390–393`. Verified against on-disk file.

---

## 8. Related Specifications / Further Reading

- [`docs/DEMO_PHASE2.md`](../docs/DEMO_PHASE2.md) — manual dry-run this suite automates
- [`classical_app/routes/wizard.py`](../classical_app/routes/wizard.py) — wizard route handlers and URL patterns
- [`classical_app/wizard_state.py`](../classical_app/wizard_state.py) — session state management (TTL, require_steps)
- [`classical_app/app.py`](../classical_app/app.py) — `create_app()`, blueprint registration, `before_request` auth guard
- [`tests/classical_app/conftest.py`](../tests/classical_app/conftest.py) — existing unit-test fixtures (`seeded_engine`, `client`) to mirror pattern
- [pytest-playwright docs](https://playwright.dev/python/docs/pytest)
- [Werkzeug `make_server` API](https://werkzeug.palletsprojects.com/en/latest/serving/)
