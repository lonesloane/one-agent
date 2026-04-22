# PRD — Phase 3: Agent App (Read Agent — UC1)

**Status**: Draft
**Owner**: Stephane
**Target phase**: Phase 3 (per `docs/BACKLOG.md`)
**Depends on**: Phase 2 (classical write flows, completed 2026-04-19)
**Blocks**: Phase 4 (write agent, UC2); Phase 6 (side-by-side demo)

---

## 1. Executive Summary

### Problem Statement

The classical app (Phase 2) demonstrates the status quo: a delegate navigates
multiple screens to find upcoming meetings and relevant documents. There is no
classical-app equivalent for UC1 — the agent must proactively surface what is
new and relevant the moment a session opens. This capability is structurally
impossible in a form-based UI, which makes it the strongest single differentiator
to showcase.

### Proposed Solution

Build the Read Agent — a conversational AI agent that greets the delegate on
session start, queries upcoming meetings and agenda documents, and highlights
anything new since a configurable lookback window. Delivered via an AG-UI
FastAPI backend and a CopilotKit Next.js frontend, both living in `agent_app/`
inside the monorepo. The agent is read-only (UC2 write tools come in Phase 4).

### Success Criteria

1. Agent streams a proactive meeting brief within **5 seconds** of session start
   when ≥ 1 upcoming meeting with new documents exists for the current delegate.
2. Agent produces **no brief** (greeting only) when no new documents are found
   in the lookback window — no false positive noise.
3. Document visibility rules enforced: a delegate never receives agenda documents
   they lack a `DocumentAccessRight` for, verified by test.
4. Agent answers follow-up questions about meetings and documents using **only
   tool-returned data** — no hallucinated document titles, meeting dates, or
   committee names.
5. **≥ 20 new tests** covering tool wrappers, proactive brief logic, visibility
   enforcement, and agent integration. Full project suite (188 baseline) remains
   green.
6. CopilotKit UI displays streaming text with tool call events visible during
   agent execution.

---

## 2. User Experience & Functionality

### User Personas

| Persona | Role | Phase 3 access |
|---|---|---|
| **Delegate** | Committee participant, consumes meeting documents | Full agent session; sees meetings and documents they have DARs for |
| **Delegation editor** | Also a delegate role; same read access here | Same as delegate for Phase 3; write tools come in Phase 4 |
| **Demo observer** | Stakeholder watching the demo | Sees the streaming brief unfold in the browser — the "wow moment" |

Persona is selected via a **delegate picker** in the CopilotKit frontend — same
concept as the classical app's navbar dropdown. Selection sets the current
delegate identity for the agent session.

### User Stories

**US-1 — Proactive meeting brief on session start**
> As a delegate, when I open the agent, I want it to immediately tell me about
> upcoming meetings and any new documents I should read, so I don't have to
> navigate anywhere.

**AC:**
- On session start (before the user sends any message), the agent automatically
  runs the brief.
- Brief fires only if ≥ 1 upcoming meeting exists **and** ≥ 1 new agenda
  document exists within the lookback window for the current delegate.
- If no new documents exist: agent greets the delegate by name and states there
  is nothing new to report. No tool call output displayed.
- Brief includes: meeting name, committee, date, and a list of new/modified
  documents (title + classification level).
- Response streams in real-time — first tokens visible within 2 seconds.

**US-2 — Ask follow-up questions about meetings**
> As a delegate, after the brief, I want to ask about a specific meeting or
> committee so I can get more detail without navigating screens.

**AC:**
- Agent resolves follow-up questions (e.g. "What documents are on the Education
  Policy agenda?") by calling `get_agenda_documents` and summarising results.
- Agent only returns documents the delegate has a DAR for.
- Agent does not invent documents, dates, or committee names — if the tool
  returns nothing, it says so.

**US-3 — Delegate picker in the frontend**
> As a demo presenter, I want to switch delegate persona in the UI so I can show
> how the brief changes for a GENERAL vs RESTRICTED access delegate.

**AC:**
- Frontend shows a dropdown listing all seed delegates with their delegation
  name and role badge.
- Switching persona resets the agent thread (new session, new brief).
- Picker selection is visible in the UI at all times.

### Non-Goals

- **No write tools.** `create_delegate`, `create_document_access_rights` — Phase 4.
- **No approver UI.** Pending DARs have status flags only.
- **No last-login tracking.** The lookback window is a fixed configurable value
  (default: 7 days), not per-user session history. Accurate "last visit" tracking
  is post-PoC.
- **No side-by-side view.** Classical app and agent app run on separate ports;
  the combined demo script is Phase 6.
- **No MCP KB.** Business rules are in the system prompt for Phase 3; the MCP
  knowledge base is Phase 5.
- **No mobile layout.** Desktop browser only for the PoC.
- **No authentication.** Delegate identity is set via the UI picker; no login
  flow.

---

## 3. AI System Requirements

### Tool Requirements

All four tools are read-only (`approval_mode="never_require"`), thin wrappers
over `shared/`:

| Tool | Inputs | Returns | Shared function |
|---|---|---|---|
| `get_delegation_info` | `delegation_id: str` | Delegation metadata, delegate roster, framework agreements | `shared/database.py` queries |
| `lookup_delegate` | `delegate_id: str` | Delegate profile, committee participations, DARs | `shared/database.py` queries |
| `get_upcoming_meetings` | `delegate_id: str` | Meetings for the delegate's committees, ordered by date | `shared/business_rules.py` (visibility-aware) |
| `get_agenda_documents` | `meeting_id: str`, `delegate_id: str` | Agenda items + visible documents (DAR-filtered) | `shared/business_rules.py::get_visible_agenda_documents` |

Document visibility is enforced inside `get_agenda_documents` via
`is_document_visible` — not in the agent layer.

### Proactive Brief Logic

The agent's system prompt instructs it to run the brief automatically on session
start using this sequence:

```
1. call lookup_delegate(current_delegate_id)       → confirm identity
2. call get_upcoming_meetings(current_delegate_id) → find meetings
3. for each meeting: call get_agenda_documents(meeting_id, current_delegate_id)
4. filter to documents newer than NOW - BRIEF_LOOKBACK_DAYS
5. if any new docs: stream brief
6. if none: stream greeting only
```

`BRIEF_LOOKBACK_DAYS` is a configurable constant (default: 7). The system prompt
carries the current delegate's ID via `function_invocation_kwargs` (identity
threading pattern, already established in the eval harness).

### System Prompt Requirements

The system prompt must encode:

- **Domain model**: Delegation, Delegate, Committee, Document, DAR, Meeting —
  enough for the agent to produce natural-language output from tool results.
- **Access-classification rule** (from Phase 0f): member → Restricted; partner
  without FA → General; partner with FA → Restricted. Required for Phase 4 but
  must be present now.
- **Proactive brief instruction**: explicit trigger on session start, conditional
  on new documents.
- **Write-guard**: "This agent has no write tools. Do not offer to create or
  modify any records."
- **Grounding rule**: "All facts about meetings, documents, and delegates must
  come from tool results. Do not invent or infer data."

### Evaluation Strategy

- **Functional correctness**: unit tests assert each tool returns correct data
  and enforces visibility.
- **Brief trigger**: integration test with mock client verifies brief fires when
  new docs exist, suppressed when none.
- **Grounding**: integration test with mock client asserts agent response cites
  only tool-returned document titles (no hallucination of a title not in the
  mock result).
- **Latency**: manual verification that first streaming token appears within
  2 seconds in the CopilotKit UI (not automated in Phase 3).

---

## 4. Technical Specifications

### Architecture Overview

```
agent_app/frontend/           (CopilotKit Next.js — new)
    package.json
    app/
      page.tsx                — chat UI + delegate picker
      copilotkit-provider.tsx
        │
        │  HTTP POST + SSE (AG-UI protocol)
        ▼
agent_app/server.py           (FastAPI + AG-UI endpoint — new)
    add_agent_framework_fastapi_endpoint(app, agent)
        │
        ▼
agent_app/agent.py            (Agent setup — new)
    Agent(
        client=FoundryChatClient(...),
        name="ONEMPReadAgent",
        instructions=SYSTEM_PROMPT,
        tools=[get_delegation_info, lookup_delegate,
               get_upcoming_meetings, get_agenda_documents],
        middleware=[AuditMiddleware()],
    )
        │
        ▼
agent_app/tools.py            (4 @tool wrappers — new)
        │
        ▼
shared/                       (unchanged — Phase 1/2)
    database.py
    business_rules.py
```

### New Files

| File | Purpose |
|---|---|
| `agent_app/__init__.py` | Package marker |
| `agent_app/agent.py` | Agent creation, `SYSTEM_PROMPT`, `BRIEF_LOOKBACK_DAYS` constant |
| `agent_app/tools.py` | 4 `@tool` functions; `function_invocation_kwargs` carries `delegate_id` |
| `agent_app/middleware.py` | `AuditMiddleware(FunctionMiddleware)` — logs tool name, args, result, timestamp |
| `agent_app/server.py` | FastAPI app; `add_agent_framework_fastapi_endpoint`; CORS for localhost frontend |
| `agent_app/frontend/` | CopilotKit Next.js app (see frontend spec below) |
| `tests/agent_app/test_tools.py` | Unit tests for all 4 tool wrappers |
| `tests/agent_app/test_brief_logic.py` | Integration tests for proactive brief trigger/suppress |

### Frontend Spec (`agent_app/frontend/`)

- **Framework**: Next.js 14+ (App Router)
- **Agent integration**: `@copilotkit/react-core` + `@copilotkit/react-ui`;
  backend registered as `HttpAgent` pointing to the FastAPI AG-UI endpoint
- **Delegate picker**: dropdown in the header; fetches delegate list from a
  `/api/delegates` FastAPI endpoint (thin wrapper over `shared/database.py`);
  on change, resets `threadId`
- **Chat UI**: `<CopilotChat />` component with streaming; tool call events
  displayed as collapsible "thinking" blocks during agent execution
- **Dev server**: `npm run dev` on port 3000; FastAPI on port 8000; CORS allows
  localhost:3000

### Dependency Changes

**Python (`pyproject.toml`)**:
```toml
dependencies = [
    ...
    "agent-framework-ag-ui>=0.1.0",  # --pre; pin to first working version
    "fastapi>=0.110",
    "uvicorn>=0.29",
]
```

Add `"agent_app"` to `[tool.setuptools] packages`.

**Node (`agent_app/frontend/package.json`)**:
```json
{
  "dependencies": {
    "@copilotkit/react-core": "latest",
    "@copilotkit/react-ui": "latest",
    "next": "^14",
    "react": "^18",
    "react-dom": "^18"
  }
}
```

### Integration Points

- **Database**: `shared/database.py` via `get_engine` + `sessionmaker`; same
  `one_agent.db` as classical app (read-only queries)
- **Azure AI Foundry**: `FOUNDRY_PROJECT_ENDPOINT` env var (already in
  `.env.example`); `AzureCliCredential` (already in `pyproject.toml` deps)
- **Identity threading**: `delegate_id` injected via `function_invocation_kwargs`
  in the AG-UI session context; tools receive it as a keyword-only parameter
  invisible to the model

### Security & Privacy

- No new PII categories. Tools return delegate data already in the seeded DB.
- CORS restricted to `localhost:3000` in development; no external exposure.
- AG-UI endpoint has no auth in Phase 3 (PoC only — noted as post-PoC concern).
- No secrets in the frontend; Foundry endpoint is server-side only.

---

## 5. Risks & Roadmap

### Phased Rollout (within Phase 3)

| Sub-phase | Deliverable | Exit criterion |
|---|---|---|
| **3A — tools + agent** | 4 `@tool` wrappers, `AuditMiddleware`, `agent.py`, unit tests | All 4 tools return correct data + enforce visibility; `AuditMiddleware` logs to loguru |
| **3B — AG-UI server** | FastAPI endpoint, `server.py`, CORS, `/api/delegates` route | `curl` to AG-UI endpoint returns SSE stream; agent runs end-to-end via HTTP |
| **3C — CopilotKit frontend** | Next.js app, delegate picker, streaming chat UI | Streaming brief visible in browser; tool call events shown; delegate switch resets thread |
| **3D — brief logic + tests + docs** | Proactive brief trigger/suppress, integration tests, doc closure | Brief fires for new-doc delegates; suppressed for no-new-doc delegates; ≥ 20 new tests; suite green |

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `agent-framework-ag-ui` preview API breaks | Medium | High | Pin to a specific pre-release version; test on install; have fallback plan to hand-roll SSE |
| CopilotKit ↔ Agent Framework integration gaps | Medium | Medium | Test AG-UI endpoint with `curl` before wiring CopilotKit; consult AG-UI Dojo sample app |
| Proactive brief fires on every session (no new docs) | Low | Medium | `BRIEF_LOOKBACK_DAYS` window + explicit suppress path in system prompt; tested |
| Identity threading (`delegate_id` in `function_invocation_kwargs`) not supported by AG-UI wrapper | Low | High | Verify in Phase 3A before building frontend; fallback: pass delegate_id as part of initial system message |
| `get_new_documents_since` lookback produces too many results for a fresh DB | Low | Low | Demo uses a freshly seeded DB; seed document `created_at` timestamps set within the lookback window |

### Open Questions Carried into Phase 3

- **OQ-7** (frontend technology): Resolved — AG-UI + CopilotKit. See `docs/DECISIONS.md`.
- **Post-Phase 3 refinement**: Replace fixed `BRIEF_LOOKBACK_DAYS` with
  per-delegate last-session timestamp once `AgentSession` persistence is wired
  (Phase 4+).

---

## Acceptance — "Phase 3 is done" checklist

- [ ] `agent_app/tools.py` — 4 tools implemented, all with `approval_mode="never_require"`
- [ ] `agent_app/middleware.py` — `AuditMiddleware` logs every tool call via loguru
- [ ] `agent_app/agent.py` — `Agent` created with correct system prompt, tools, middleware
- [ ] `agent_app/server.py` — FastAPI AG-UI endpoint; `/api/delegates` helper route
- [ ] `agent_app/frontend/` — CopilotKit Next.js app with delegate picker + streaming chat
- [ ] Proactive brief fires automatically on session start when new docs exist
- [ ] Proactive brief suppressed (greeting only) when no new docs in lookback window
- [ ] Document visibility enforced: delegate never receives documents without a DAR
- [ ] Agent uses only tool-returned data — no hallucination (verified by integration test)
- [ ] Delegate picker switch resets agent thread (fresh brief for new persona)
- [ ] ≥ 20 new tests; full project suite (188 baseline) green
- [ ] `pyproject.toml` updated with new Python deps; `agent_app` added to packages list
- [ ] `docs/DESIGN.md` "Current state" updated to Phase 3
- [ ] `docs/BACKLOG.md` Phase 3 items checked off with completion date
