---
goal: Phase 3A — agent_app package scaffolding, 4 DB-backed @tool wrappers, AuditMiddleware, and agent.py with system prompt
version: 1.0
date_created: 2026-04-20
owner: Stephane
status: 'Planned'
tags: [feature, phase3, agent, tools, middleware]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 3A bootstraps the `agent_app` Python package and delivers the four
read-only `@tool` wrappers backed by `shared/database.py` and
`shared/business_rules.py`, an `AuditMiddleware`, and `agent.py` with the
full system prompt and `BRIEF_LOOKBACK_DAYS` constant. This is the
foundation for every subsequent Phase 3 sub-phase. Exit criterion: all
four tools return correct data, enforce DAR visibility, and pass unit tests;
`AuditMiddleware` logs each tool call to loguru; the full project test suite
(188 baseline + new tests) is green.

Spec: `docs/prd-phase3-read-agent.md` §3 (Tool Requirements) and §5
(3A exit criterion).

## 1. Requirements & Constraints

- **REQ-001**: `agent_app/tools.py` must expose four functions decorated
  with `@tool(approval_mode="never_require")`:
  `get_delegation_info(delegation_id)`, `lookup_delegate(delegate_id)`,
  `get_upcoming_meetings(delegate_id)`,
  `get_agenda_documents(meeting_id, delegate_id)`.
- **REQ-002**: `delegate_id` in `get_upcoming_meetings` and
  `get_agenda_documents` must arrive via `function_invocation_kwargs`
  (invisible to the model); tools declare it as a keyword-only parameter
  `delegate_id: str = ""`.
- **REQ-003**: `get_agenda_documents` must call
  `shared.business_rules.get_visible_agenda_documents(delegate_id,
  meeting_id, session)` — visibility enforced in the business layer, not
  in the tool.
- **REQ-004**: `get_upcoming_meetings` must return only meetings for
  committees the delegate participates in, ordered by date ascending.
- **REQ-005**: `agent_app/middleware.py` must define
  `AuditMiddleware(FunctionMiddleware)` that logs tool name, arguments,
  result, and UTC timestamp via loguru at INFO level.
- **REQ-006**: `agent_app/agent.py` must define `BRIEF_LOOKBACK_DAYS = 7`
  and `SYSTEM_PROMPT` (see §3 of PRD for required sections), and create
  an `Agent` instance wiring the four tools and `AuditMiddleware`.
- **REQ-007**: `pyproject.toml` updated: `fastapi>=0.110`,
  `uvicorn>=0.29`, `agent-framework-ag-ui>=0.1.0` added to
  `[project.dependencies]`; `"agent_app"` added to
  `[tool.setuptools] packages`.
- **CON-001**: No modifications to `shared/database.py`,
  `shared/business_rules.py`, or any Phase 1/2 file.
- **CON-002**: `get_new_documents_since` in `shared/business_rules.py`
  accepts a `delegate_last_login: datetime` argument. The brief tool
  computes the cutoff as
  `datetime.now(timezone.utc) - timedelta(days=BRIEF_LOOKBACK_DAYS)`
  and passes it as `delegate_last_login`. No new shared helper required.
- **CON-003**: Tools return JSON strings (serialized with `json.dumps`)
  so the agent framework can consume them as tool results.
- **GUD-001**: Follow CLAUDE.md: loguru, PEP 8, 79-char lines, Google
  docstrings, type hints on all public functions.
- **PAT-001**: Mirror `eval/middleware.py`'s `RecorderMiddleware` pattern
  for `AuditMiddleware` (same `process` / `call_next` signature).
- **PAT-002**: Mirror `eval/tools.py` tool decorator pattern; import
  `agent_framework.tool` and `pydantic.Field`.
- **RISK-001**: `function_invocation_kwargs` support in AG-UI wrapper is
  unverified. TASK-004 (spike) must pass before building full tool
  signatures. Fallback: pass `delegate_id` as a first-class tool
  parameter visible to the model.

## 2. Implementation Steps

### Implementation Phase 1 — Package Bootstrap & Dependency Wiring

- GOAL-001: Get `agent_app` importable, dependencies installable, test
  package discoverable.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Edit `pyproject.toml`: add `"fastapi>=0.110"`, `"uvicorn>=0.29"`, `"agent-framework-ag-ui>=0.1.0"` to `[project.dependencies]`. Add `"agent_app"` to `[tool.setuptools] packages` list. Run `pip install -e ".[dev]"` to verify install. | | |
| TASK-002 | Create `agent_app/__init__.py` — empty file with module docstring `"""ONE-MP Read Agent package."""`. | | |
| TASK-003 | Create `tests/agent_app/__init__.py` — empty file. | | |

### Implementation Phase 2 — Identity Threading Spike

- GOAL-002: Confirm `delegate_id` injected via `function_invocation_kwargs`
  reaches the tool before building all four tools around that pattern.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Write a minimal spike in `tests/agent_app/test_tools.py` (placeholder test class `TestKwargInjection`). Run `get_upcoming_meetings` directly with a known `delegate_id` kwarg. If the AG-UI session context does NOT support `function_invocation_kwargs`, document fallback (promote `delegate_id` to a visible `@tool` param). Update TASK-005 accordingly. | | |

### Implementation Phase 3 — Tool Implementations

- GOAL-003: Four DB-backed tools, all returning JSON strings, visibility
  enforced at the business-rule layer.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `agent_app/tools.py`. Add module docstring. Import `get_engine`, `sessionmaker` from `shared.database`; import `get_visible_agenda_documents` from `shared.business_rules`. Implement `get_delegation_info(delegation_id: str) -> str`: query `Delegation` by `id`, join `FrameworkAgreement`; return JSON with keys `id`, `name`, `membership_type`, `delegates`, `framework_agreements`. | | |
| TASK-006 | In `agent_app/tools.py`, implement `lookup_delegate(delegate_id: str) -> str`: query `Delegate` by `id`; join `delegate_committees` association and `DocumentAccessRight`; return JSON with keys `id`, `full_name`, `delegation_id`, `committees`, `access_rights`. | | |
| TASK-007 | In `agent_app/tools.py`, implement `get_upcoming_meetings(*, delegate_id: str = "") -> str`: query `Meeting` rows for committees where `delegate_id` appears in `delegate_committees`; filter `meeting_date >= datetime.now(timezone.utc)`; order by `meeting_date`; return JSON array of `{id, title, committee_id, meeting_date}`. | | |
| TASK-008 | In `agent_app/tools.py`, implement `get_agenda_documents(meeting_id: str, *, delegate_id: str = "") -> str`: call `get_visible_agenda_documents(delegate_id, meeting_id, session)`; serialize each `Document` to `{id, title, classification, last_modified}`; return JSON array. | | |

### Implementation Phase 4 — Middleware & Agent

- GOAL-004: `AuditMiddleware` and `agent.py` with full system prompt.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create `agent_app/middleware.py`. Define `AuditMiddleware(FunctionMiddleware)` mirroring `eval/middleware.py` structure. `process` logs: `logger.info("tool={name} args={args} result={result} ts={utcnow}")` before returning. Import `loguru.logger`. | | |
| TASK-010 | Create `agent_app/agent.py`. Define `BRIEF_LOOKBACK_DAYS: int = 7`. Define `SYSTEM_PROMPT: str` covering: domain model summary (Delegation/Delegate/Committee/Document/DAR/Meeting), access-classification rule (member→RESTRICTED; partner-no-FA→GENERAL; partner-with-FA→RESTRICTED), proactive brief instruction (fire on session start; conditional on `BRIEF_LOOKBACK_DAYS`), write-guard, grounding rule. Instantiate `Agent` with `name="ONEMPReadAgent"`, `instructions=SYSTEM_PROMPT`, the four tools, and `AuditMiddleware()`. | | |

### Implementation Phase 5 — Unit Tests

- GOAL-005: Tool correctness and visibility enforcement covered by tests.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | In `tests/agent_app/test_tools.py`, add `TestGetDelegationInfo`: one test per happy path (valid `delegation_id`) and one for unknown ID (returns JSON with null/empty). Use the same in-memory SQLite pattern from `tests/shared/conftest.py` (`get_engine("sqlite:///:memory:")`, `init_db`). | | |
| TASK-012 | In `tests/agent_app/test_tools.py`, add `TestLookupDelegate`: test delegate found with committees and DARs; test unknown delegate. | | |
| TASK-013 | In `tests/agent_app/test_tools.py`, add `TestGetUpcomingMeetings`: test delegate with upcoming meetings returns correct sorted list; test delegate with no meetings returns empty array. | | |
| TASK-014 | In `tests/agent_app/test_tools.py`, add `TestGetAgendaDocuments`: test DAR-holding delegate sees correct documents; test delegate lacking DAR sees no documents for that classification; test empty meeting returns empty array. This verifies visibility enforcement end-to-end. | | |
| TASK-015 | In `tests/agent_app/test_tools.py`, add `TestAuditMiddleware`: use `RecorderMiddleware` pattern as model; assert `AuditMiddleware.process` calls `call_next` and logs at INFO (mock loguru or capture loguru output). | | |
| TASK-016 | Run full test suite: `pytest` (all tests must pass, ≥ 10 new tests from this phase). | | |

## 3. Alternatives

- **ALT-001**: Reuse `eval/tools.py` stub tool names and add DB logic there
  instead of creating `agent_app/tools.py`. Rejected — eval stubs are
  scenario-data mocks; mixing live DB queries would break the eval harness.
- **ALT-002**: Add a new `get_new_documents_since_window(meeting_id,
  days, session)` helper to `shared/business_rules.py`. Rejected (CON-001
  additive-only); the cutoff computation is trivial enough to live in
  the tool.

## 4. Dependencies

- **DEP-001**: `agent-framework>=1.0.0` — already in `pyproject.toml`.
- **DEP-002**: `agent-framework-ag-ui>=0.1.0` (pre-release) — added in
  TASK-001.
- **DEP-003**: `fastapi>=0.110` — added in TASK-001 (needed for Phase 3B
  but must be installable by 3A to keep the environment consistent).
- **DEP-004**: `uvicorn>=0.29` — added in TASK-001 (same reason).
- **DEP-005**: `sqlalchemy>=2.0` — already in `pyproject.toml`.
- **DEP-006**: Phase 2 complete (shared data layer + seed data operational).

## 5. Files

- **FILE-001**: `pyproject.toml` — add deps, add `agent_app` to packages
- **FILE-002**: `agent_app/__init__.py` — new, package marker
- **FILE-003**: `agent_app/tools.py` — new, 4 @tool wrappers (~120 lines)
- **FILE-004**: `agent_app/middleware.py` — new, AuditMiddleware (~40 lines)
- **FILE-005**: `agent_app/agent.py` — new, Agent + SYSTEM_PROMPT (~80 lines)
- **FILE-006**: `tests/agent_app/__init__.py` — new, empty
- **FILE-007**: `tests/agent_app/test_tools.py` — new, ≥10 tests (~200 lines)

## 6. Testing

- **TEST-001**: `TestGetDelegationInfo` — happy path + unknown ID
- **TEST-002**: `TestLookupDelegate` — found with committees/DARs; not found
- **TEST-003**: `TestGetUpcomingMeetings` — meetings present sorted; no
  meetings returns empty
- **TEST-004**: `TestGetAgendaDocuments` — DAR grants access; no DAR blocks;
  empty meeting; this is the DAR enforcement test
- **TEST-005**: `TestAuditMiddleware` — middleware logs and calls next

## 7. Risks & Assumptions

- **RISK-001**: `function_invocation_kwargs` injection unverified (see
  TASK-004 spike). Mitigation: fallback to visible tool param documented.
- **RISK-002**: `agent-framework-ag-ui` pre-release may not install cleanly.
  Mitigation: pin to first working version after `pip install --pre`.
- **ASSUMPTION-001**: `shared/database.py` `get_engine` + `sessionmaker`
  pattern from Phase 1 is sufficient; no new DB connection abstraction
  needed.
- **ASSUMPTION-002**: Seed data from Phase 2A (`shared/seed_data.py`) is
  sufficient for tool unit tests; tests use in-memory SQLite + seed.

## 8. Related Specifications / Further Reading

- `docs/prd-phase3-read-agent.md` — full PRD for Phase 3
- `eval/tools.py` — existing stub tool pattern (reference only)
- `eval/middleware.py` — RecorderMiddleware (AuditMiddleware model)
- `shared/business_rules.py` — `get_visible_agenda_documents`,
  `get_new_documents_since`
- Phase 3B plan: `plan/feature-phase3b-ag-ui-server-1.md`
