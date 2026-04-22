---
goal: Phase 3E — CopilotKit E2E browser tests with pytest-playwright (brief fire/suppress, tool blocks, persona switch)
version: 1.0
date_created: 2026-04-20
owner: Stephane
status: 'Completed'
tags: [feature, phase3, e2e, playwright, tests, copilotkit]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Phase 3E automates the four browser verification tasks left open from Phase
3C (TASK-009–012) as a repeatable pytest-playwright suite. Tests run against
real Azure AI Foundry (no LLM mocking) and a test-specific SQLite database
that adds a fresh document within the 7-day lookback window. Exit criterion:
all 4 tests green in a single `pytest tests/e2e/copilot/` run.

Spec: `plan/feature-phase3c-copilotkit-frontend-1.md` §6 (TEST-001–004).

> **Note**: Tests require Azure CLI login (`az login`) and
> `FOUNDRY_PROJECT_ENDPOINT` set in the environment. Ports 8000 (FastAPI)
> and 3000 (Next.js) must be free before the run.

## 1. Requirements & Constraints

- **REQ-001**: Four passing browser tests covering: (a) brief fires on
  session open for a delegate with new documents; (b) greeting-only response
  for a delegate with no new documents; (c) persona switch resets thread and
  fires a new brief; (d) tool call collapsible blocks are rendered.
- **REQ-002**: Tests use a session-scoped test SQLite database — standard
  `seed_all()` plus one fresh document (`last_modified = datetime.now(UTC)`)
  linked to `MTG-EDU-2026-05` (Education Committee Spring Meeting, 2026-05-10)
  for delegate DEL-2026-0001 (Marie Dupont, EDU member). All seed documents
  have dates before 2026-04-13 so this addition is required for the brief
  to fire.
- **REQ-003**: The FastAPI server (`agent_app.server:app`) is started as a
  subprocess with `DATABASE_PATH` pointing to the test DB. The Next.js dev
  server (`npm run dev`) is started as a separate subprocess. Both are torn
  down at session end.
- **REQ-004**: Follow `CLAUDE.md` Python conventions (PEP 8, Google
  docstrings, type hints, 79-char lines, loguru not print).
- **CON-001**: LLM responses are non-deterministic. Tests assert document
  title substring presence/absence, not exact text. Timeout: 90 seconds for
  any assistant message to appear.
- **CON-002**: Location `tests/e2e/copilot/` (subdirectory of existing
  `tests/e2e/`). Must include a no-op `reset_db` fixture to shadow the
  Flask-specific autouse fixture in `tests/e2e/conftest.py`.
- **CON-003**: No changes to `shared/seed_data.py`. Fresh document is added
  in the test conftest only.
- **CON-004**: Next.js `app/api/copilotkit/route.ts` hardcodes
  `http://localhost:8000/` — FastAPI test server must run on port 8000.
- **GUD-001**: Delegate picker `<select>` in `DelegatePicker.tsx` is a
  plain HTML `<select>`. Use `page.select_option("select", label=...)` to
  switch delegates.
- **GUD-002**: Tool call blocks are `<details>` elements rendered by
  `ToolCallBlock` in `app/page.tsx`. Assert with
  `page.locator("details").count() > 0`.

## 2. Implementation Steps

### Implementation Phase 1 — Test Infrastructure

- GOAL-001: Session-scoped fixtures that start both servers against a
  test database containing a fresh document.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `tests/e2e_agent/__init__.py` (empty). Create `tests/e2e_agent/conftest.py` with module docstring. | ✅ | 2026-04-20 |
| TASK-002 | In `conftest.py`, add session-scoped `agent_db_path` fixture returning a temp SQLite path. | ✅ | 2026-04-20 |
| TASK-003 | Add session-scoped `agent_engine` fixture: seed_all + fresh `DOC-TEST-001` linked to `MTG-EDU-2026-05`. | ✅ | 2026-04-20 |
| TASK-004 | Add session-scoped `fastapi_server` fixture on a free port (not 8000); polls `/api/delegates`. | ✅ | 2026-04-20 |
| TASK-005 | Add session-scoped `nextjs_server` fixture on a free port (not 3000); process group for clean teardown; Turbopack lock eviction. | ✅ | 2026-04-20 |
| TASK-006 | Autouse no-op `reset_db` dropped — suite moved to `tests/e2e_agent/` (own root), so Flask's `reset_db` no longer shadows. | ✅ | 2026-04-20 |
| TASK-007 | `base_url` fixture returns `http://localhost:{nextjs_port}`. | ✅ | 2026-04-20 |

### Implementation Phase 2 — Browser Tests

- GOAL-002: Four tests covering the Phase 3C exit criteria.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | Create `tests/e2e_agent/test_copilot_brief.py` with module docstring + `_visible_brief_mention` helper (filters out hidden tool-call `<pre>`). | ✅ | 2026-04-20 |
| TASK-009 | `test_brief_fires_on_session_open`: auto-selects first delegate, asserts `E2E Test Policy Draft` visible within 90 s. | ✅ | 2026-04-20 |
| TASK-010 | `test_brief_suppressed_no_new_docs`: switches to DEL-2026-0007 (Priya, IND) via `select_option(value=…)`; asserts fresh doc title absent. Uses `data-testid='copilot-assistant-message'` (CopilotKit v2 uses PascalCase `copilotKitMessage`). | ✅ | 2026-04-20 |
| TASK-011 | `test_persona_switch_resets_thread`: waits for Marie brief, switches to Priya, waits for old brief to hide, then asserts fresh doc title absent from new message. | ✅ | 2026-04-20 |
| TASK-012 | `test_tool_call_blocks_visible`: asserts `page.locator("details").count() >= 1` after brief completes. | ✅ | 2026-04-20 |

### Implementation Phase 3 — Verification

- GOAL-003: Full run confirmation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | `pytest tests/e2e_agent/test_copilot_brief.py -v` → **4 passed in 46.26s** (2 consecutive runs, stable). | ✅ | 2026-04-20 |
| TASK-014 | Existing suite unaffected: 203 unit tests still green. | ✅ | 2026-04-20 |
| TASK-015 | Root-cause fix for render silent-failure: `ChatPane` useEffect in `app/page.tsx` now gates on `copilotkit.runtimeConnectionStatus === Connected` and includes `agent` in deps — otherwise the effect closes over a provisional `ProxiedCopilotRuntimeAgent` while `CopilotChat` later rebinds to the real per-thread clone, and mutations are orphaned. | ✅ | 2026-04-20 |

## 3. Alternatives

- **ALT-001**: Playwright TypeScript (`npx playwright test`) co-located with
  the Next.js app. Rejected — project uses Python throughout; pytest-playwright
  is already installed and the existing e2e suite follows this pattern.
- **ALT-002**: Mock the LLM in browser tests (intercept AG-UI SSE stream).
  Rejected — Phase 3D already covers mocked integration tests; the
  browser suite's value is end-to-end confidence with a real model.
- **ALT-003**: Use the production `one_agent.db` (skip temp DB). Rejected —
  all seed documents are older than 7 days as of 2026-04-20; the brief would
  never fire without a fresh document injected at test time.
- **ALT-004**: Modify `shared/seed_data.py` to add recent documents. Rejected
  — seed dates would go stale again; isolating the fresh document in the test
  conftest keeps the change reversible and date-independent.

## 4. Dependencies

- **DEP-001**: Phase 3C complete and merged — `agent_app/frontend/` present
  on `main`; `npm run dev` starts cleanly.
- **DEP-002**: Phase 3B complete — `agent_app/server.py` accepts
  `DATABASE_PATH` env var (line 23); `/api/delegates` endpoint available.
- **DEP-003**: `pytest-playwright` already in `pyproject.toml` dev extras
  (verified via `tests/e2e/` existing suite).
- **DEP-004**: Azure CLI logged in (`az login`) — `create_agent()` in
  `agent_app/agent.py:96` uses `AzureCliCredential()`.
- **DEP-005**: `FOUNDRY_PROJECT_ENDPOINT` set in environment (required at
  `agent_app/agent.py:98`). Optional: `FOUNDRY_MODEL` (defaults to
  `"gpt-4o"`).
- **DEP-006**: Node.js ≥ 18 and `node_modules/` present in
  `agent_app/frontend/` (installed during Phase 3C).

## 5. Files

- **FILE-001**: `tests/e2e/copilot/__init__.py` — new, empty
- **FILE-002**: `tests/e2e/copilot/conftest.py` — new; session fixtures for
  temp DB, FastAPI subprocess, Next.js subprocess, no-op `reset_db` override
- **FILE-003**: `tests/e2e/copilot/test_copilot_brief.py` — new; 4 browser
  tests

## 6. Testing

- **TEST-001**: `test_brief_fires_on_session_open` — "E2E Test Policy Draft"
  appears in chat within 90 s for DEL-2026-0001
- **TEST-002**: `test_brief_suppressed_no_new_docs` — "E2E Test Policy Draft"
  absent from chat for DEL-2026-0007 (Priya Sharma, IND)
- **TEST-003**: `test_persona_switch_resets_thread` — switching to DEL-2026-0007
  after DEL-2026-0001's brief produces a new message without the fresh doc title
- **TEST-004**: `test_tool_call_blocks_visible` — at least one `<details>`
  element present in the page after DEL-2026-0001's brief completes

## 7. Risks & Assumptions

- **RISK-001**: CopilotKit chat DOM selectors may differ from assumed
  patterns (class names, element hierarchy). Mitigation: run the dev server
  manually first and use `page.pause()` or `playwright codegen` to inspect
  the live DOM before writing assertions; adjust selectors in TASK-009–012.
- **RISK-002**: 90-second timeout may be insufficient for cold-start Foundry
  calls. Mitigation: increase to 120 s if flaky on first run; document the
  chosen timeout in the conftest.
- **RISK-003**: Port 8000 conflict if the dev FastAPI server is still running.
  The `fastapi_server` fixture should check port availability before starting
  and raise a clear `RuntimeError` if occupied.
- **RISK-004**: The `nextjs_server` subprocess captures stdout/stderr in
  a pipe. Next.js writes to stdout when ready; polling HTTP 200 on port 3000
  is more reliable than parsing output.
- **ASSUMPTION-001**: DEL-2026-0007 (Priya Sharma, IND) participates in
  DAC, ENV, TRADE committees only — confirmed from `seed_data.py:215`. She
  has no EDU participation, so the fresh EDU document never appears in her
  brief.
- **ASSUMPTION-002**: `pytest-playwright` installs Chromium browser via
  `playwright install`. If not yet installed, the test run will fail with
  a clear error; fix with `playwright install chromium`.
- **ASSUMPTION-003**: `FOUNDRY_PROJECT_ENDPOINT` and Azure CLI credentials
  are available in the shell that runs `pytest`. Tests will fail at agent
  startup otherwise.

## 8. Related Specifications / Further Reading

- `plan/feature-phase3c-copilotkit-frontend-1.md` — §6 TEST-001–004 (the
  manual tests this plan automates)
- `plan/feature-phase3d-brief-logic-and-tests-1.md` — complementary mocked
  integration tests (no Foundry required)
- `tests/e2e/conftest.py` — existing Flask e2e conftest (autouse `reset_db`
  that must be shadowed)
- `agent_app/agent.py:96–102` — `AzureCliCredential` + `FOUNDRY_PROJECT_ENDPOINT`
- `agent_app/server.py:23` — `DATABASE_PATH` env var consumed at import time
- `agent_app/frontend/app/page.tsx:11–37` — `ToolCallBlock` renders `<details>`
- `agent_app/frontend/app/components/DelegatePicker.tsx:82` — plain `<select>`
