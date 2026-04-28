---
goal: Phase 3B — FastAPI AG-UI server with SSE endpoint, CORS, and /api/delegates helper route
version: 1.0
date_created: 2026-04-20
owner: Stephane
status: 'In Progress'
tags: [feature, phase3, fastapi, ag-ui, server]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 3B delivers `agent_app/server.py`: a FastAPI application that
registers the `ONEMPReadAgent` (from Phase 3A) on the AG-UI SSE endpoint
and exposes a `/api/delegates` helper used by the CopilotKit frontend.
CORS is scoped to `localhost:3000`. Exit criterion: a `curl` POST to the
AG-UI endpoint returns a valid SSE stream with at least one agent event;
`GET /api/delegates` returns the seeded delegate list as JSON.

Spec: `docs/prd-phase3-read-agent.md` §4 (Architecture Overview) and §5
(3B exit criterion).

## 1. Requirements & Constraints

- **REQ-001**: `agent_app/server.py` must create a `FastAPI` app and call
  `add_agent_framework_fastapi_endpoint(app, agent)` to register the
  AG-UI endpoint (imported from `agent_framework_ag_ui` or
  `agent_framework.ag_ui` — resolve exact import after 3A installs the
  package).
- **REQ-002**: `GET /api/delegates` must return a JSON array of
  `{id, full_name, delegation_name, role}` for every `Delegate` in the
  seeded DB, sorted alphabetically by `full_name`. Query uses
  `shared.database.get_engine` + `sessionmaker` (same pattern as tools).
- **REQ-003**: CORS middleware must allow `http://localhost:3000`; allow
  methods `["*"]`; allow headers `["*"]`.
- **REQ-004**: `uvicorn` start command documented in this plan (not
  automated): `uvicorn agent_app.server:app --port 8000 --reload`.
- **REQ-005**: AG-UI endpoint must accept the `delegate_id` session
  parameter (per identity-threading pattern confirmed in Phase 3A
  TASK-004) and forward it to tools via `function_invocation_kwargs`.
- **CON-001**: No auth on Phase 3 endpoints (PoC; noted as post-PoC
  concern in PRD §4).
- **CON-002**: Additive only — no modifications to Phase 3A files except
  `agent_app/agent.py` if the Agent constructor requires a server-level
  kwarg binding.
- **CON-003**: Server reads from the same `one_agent.db` as the classical
  app; no new DB file.
- **GUD-001**: Follow CLAUDE.md: loguru, PEP 8, 79-char lines, type hints,
  Google docstrings. Functions < 50 lines. File < 500 lines.
- **GUD-002**: FastAPI route handlers use `async def`; DB sessions created
  per-request with `sessionmaker` (not a global session).

## 2. Implementation Steps

### Implementation Phase 1 — FastAPI App Skeleton

- GOAL-001: Minimal FastAPI app with CORS and `/api/delegates` route.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `agent_app/server.py`. Add module docstring. Import `FastAPI`, `CORSMiddleware` from `fastapi` and `fastapi.middleware.cors`. Create `app = FastAPI(title="ONE-MP Read Agent Server")`. Add `CORSMiddleware` with `allow_origins=["http://localhost:3000"]`, `allow_methods=["*"]`, `allow_headers=["*"]`. | ✅ | 2026-04-20 |
| TASK-002 | In `agent_app/server.py`, implement `GET /api/delegates`. Query all `Delegate` rows joined with `Delegation` (for `delegation_name`). Return list of `DelegateOut` Pydantic model `{id: str, full_name: str, delegation_name: str, role: str}`. Sort by `full_name`. Use per-request `sessionmaker` session. | ✅ | 2026-04-20 |
| TASK-003 | Manually verify `GET /api/delegates` with `uvicorn agent_app.server:app --port 8000 --reload` + `curl http://localhost:8000/api/delegates`. Confirm JSON array with seeded delegates. | ✅ | 2026-04-20 |

### Implementation Phase 2 — AG-UI Endpoint Registration

- GOAL-002: AG-UI SSE endpoint live; agent reachable end-to-end via HTTP.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Resolve exact import path for `add_agent_framework_fastapi_endpoint` by inspecting `agent_framework_ag_ui` package after install (`python -c "import agent_framework_ag_ui; print(dir(agent_framework_ag_ui))"`). Document the correct import in this plan's notes. **DONE 2026-04-20**: `from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint` works, but this helper is NOT used — see TASK-005 note. | ✅ | 2026-04-20 |
| TASK-005 | In `agent_app/server.py`, import `agent` from `agent_app.agent`. Call `add_agent_framework_fastapi_endpoint(app, agent)` (exact signature confirmed in TASK-004). Restart uvicorn. **DEVIATION (2026-04-20)**: `add_agent_framework_fastapi_endpoint` does not support injecting `function_invocation_kwargs` from the HTTP request body into tool calls — verified from package source. A custom `POST /` handler is used instead, which instantiates `AgentFrameworkAgent(agent=_BoundAgent(...))` per request. `_BoundAgent` is a thin `SupportsAgentRun` wrapper that intercepts `agent.run()` and merges `{"delegate_id": delegate_id}` into `function_invocation_kwargs`. This satisfies REQ-001's intent without re-implementing SSE transport. | ✅ | 2026-04-20 |
| TASK-006 | Smoke-test the AG-UI endpoint: send a minimal POST (per AG-UI spec) with `Content-Type: application/json` and `delegate_id` in the session context. Confirm SSE stream response. Record the working curl command in `docs/DEMO_PHASE2.md` or a scratch note for Phase 3D docs. | | |

### Implementation Phase 3 — Identity Threading Wiring

- GOAL-003: `delegate_id` flows from the HTTP request body into tool
  `function_invocation_kwargs` so tools receive it without model exposure.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Using the AG-UI session context mechanism (pattern confirmed in Phase 3A TASK-004): wire `delegate_id` from the incoming AG-UI request body into `function_invocation_kwargs` for the agent session. If the framework provides a session-context dict, set `{"delegate_id": request_body.delegate_id}`. If not supported, promote `delegate_id` to a system-message injection (fallback documented in Phase 3A RISK-001). **DONE 2026-04-20**: implemented via `_BoundAgent` wrapper (see TASK-005 deviation). Client sends `state: {"delegate_id": "DEL-001"}`; server extracts it and merges into `function_invocation_kwargs` before every `agent.run()` call. | ✅ | 2026-04-20 |
| TASK-008 | Test identity threading end-to-end: send a POST with `delegate_id = "DEL-001"` (or actual seed ID); confirm `get_upcoming_meetings` tool is called with the correct `delegate_id` via `AuditMiddleware` log output. | | |

## 3. Alternatives

- **ALT-001**: Use Flask with SSE instead of FastAPI. Rejected — PRD
  explicitly selects FastAPI + AG-UI; Flask is the classical app's stack
  and should not be mixed.
- **ALT-002**: Hand-roll the SSE endpoint without `agent-framework-ag-ui`.
  Noted as fallback in PRD §5 risk register; avoid unless the package
  fails to install.

## 4. Dependencies

- **DEP-001**: Phase 3A complete — `agent_app.agent.agent` importable,
  four tools functional, `pyproject.toml` deps updated.
- **DEP-002**: `fastapi>=0.110` — installed via Phase 3A TASK-001.
- **DEP-003**: `uvicorn>=0.29` — installed via Phase 3A TASK-001.
- **DEP-004**: `agent-framework-ag-ui>=0.1.0` — installed via Phase 3A
  TASK-001.

## 5. Files

- **FILE-001**: `agent_app/server.py` — new, FastAPI app + CORS +
  AG-UI endpoint + `/api/delegates` (~100 lines)

## 6. Testing

- **TEST-001**: Manual `curl GET /api/delegates` — confirms seeded list
  returned as JSON (no automated pytest for Phase 3B; integration tested
  end-to-end in Phase 3D).
- **TEST-002**: Manual `curl POST <ag-ui-endpoint>` — confirms SSE stream
  returned.
- **TEST-003**: Manual identity threading check via AuditMiddleware log
  output confirms `delegate_id` reaches tools.

## 7. Risks & Assumptions

- **RISK-001**: Exact import path for `add_agent_framework_fastapi_endpoint`
  unknown until package installed. Mitigation: TASK-004 resolves before
  writing TASK-005.
- **RISK-002**: AG-UI endpoint path conflicts with FastAPI auto-routes.
  Mitigation: check for path collisions at startup; adjust prefix if needed.
- **ASSUMPTION-001**: `agent_framework_ag_ui` provides a single function
  call to register the FastAPI endpoint (per PRD architecture diagram).
- **ASSUMPTION-002**: Identity threading via `function_invocation_kwargs`
  confirmed working in Phase 3A TASK-004 before this phase starts.

## 8. Related Specifications / Further Reading

- `docs/prd-phase3-read-agent.md` — §4 Architecture Overview
- Phase 3A plan: `plan/feature-phase3a-tools-agent-1.md`
- Phase 3C plan: `plan/feature-phase3c-copilotkit-frontend-1.md`
