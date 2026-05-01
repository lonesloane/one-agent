# ONE Agent PoC — Architecture Overview

> Replacing the ONE MP form-based web application with a conversational agent that compresses multi-step workflows and adds proactive intelligence.

## System Overview

The PoC ships two applications sharing the same database, business rules, and test data:

- **Classical app** (Flask + forms): demonstrates the click-heavy status quo (contrast tool)
- **Agent app** (Chainlit + Microsoft Agent Framework Python): demonstrates conversational, proactive alternative

Side-by-side, they make the case without a slide deck.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Consumers                             │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ Classical App │  │ Agent Tools  │  │ MCP KB Server │ │
│  │ Flask routes  │  │ @tool funcs  │  │ mcp SDK tools │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘ │
│         │                 │                  │          │
│         ▼                 ▼                  ▼          │
│  ┌─────────────────────────────────────────────────┐    │
│  │            Shared Data & Logic Layer             │    │
│  │  SQLAlchemy models    Business rule functions    │    │
│  │  (database.py)        (business_rules.py)       │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         ▼                               │
│                  ┌──────────────┐                        │
│                  │  SQLite DB   │                        │
│                  │ one_agent.db │                        │
│                  └──────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

## Stack

| Layer | Technology |
|---|---|
| Agent runtime | Python 3.11 + Microsoft Agent Framework (`agent-framework`) |
| Model (PoC) | `gpt-4.1-mini` via `FoundryChatClient` (Azure AI Foundry) |
| Model (fallback) | `gpt-5.4-nano` (validated alternative, 86% on eval suite) |
| Classical frontend | Flask + Jinja2 + Bootstrap 5 (Python) |
| Agent frontend | Chainlit (Python) — chat UI, streaming, native HITL prompt action |
| Agent transport | Chainlit's WebSocket — no AG-UI |
| Database | SQLite (single-language now; agent + classical both Python) |
| Shared business rules | `shared/business_rules.py` — single source of truth, called directly by both apps |
| Business KB | MCP server (mcp SDK) + ChromaDB + git-backed markdown (Phase 5) |
| Session/audit | `AgentThread` (Python) — workflow-scoped per use case |
| Tools | `@tool`-decorated functions + `@tool(approval_mode="always_require")` for HITL writes |
| Cross-cutting | Agent Framework middleware (audit, identity, HITL via approval mode) |

## Use Cases (PoC Scope)

**UC1 — Proactive Meeting Brief** (read-only): Agent greets delegate with upcoming meeting info, highlights new/modified agenda documents since last visit. Structurally impossible in the form app.

**UC2 — Delegate Creation with Document Access Rights** (write, complex reasoning): Agent guides delegation editor through creating a delegate, reasons through DAR business rules (membership type, committees, Framework Agreements, approval routing). Compresses 8 screens into ~3 conversational turns.

## Core Domain Entities

- **Delegation**: member country or partner organization (has membership type)
- **Delegate**: individual belonging to one delegation, participates in committees
- **Committee**: OECD body (Education Policy, Trade, etc.)
- **Document**: classified document (Public/General/Restricted/Confidential)
- **Document Access Rights (DAR)**: what a delegate can see, per committee + classification level
- **Framework Agreement**: grants partner delegates elevated access on specific committees
- **Meeting**: committee meeting with linked agenda documents

## Key Architectural Patterns

- **Human-in-the-loop**: `@tool(approval_mode="always_require")` decorates write tools; reads run unwrapped. Approval prompt rendered by Chainlit's native HITL action UI (no custom wire-protocol glue). Validated by spike `spikes/c4_chainlit/` (passed 2026-04-29).
- **Audit trail**: function-invocation middleware intercepts every tool call (who, what, when, result).
- **Identity threading**: delegate identity propagated through Chainlit's per-session `cl.user_session` and injected into tool-function parameters; invisible to the model.
- **MCP KB**: business rules queryable at runtime via MCP protocol (semantic search + structured lookups). Phase 5 — single-language Python.
- **Streaming**: Chainlit's WebSocket streams partial messages and tool-call traces directly into the chat UI.
- **Workflow-scoped sessions**: each use case (UC1 brief, UC2 wizard, UC3 approver) opens a fresh `AgentThread`; identity persists via Chainlit auth, not session history.

## Project Structure

```
one-agent-poc/                 # Project root
├── eval/                      # Phase 0 evaluation harness (Python)
│   ├── __init__.py
│   ├── tools.py               # 6 stub tools with @tool decorator
│   ├── middleware.py          # RecorderMiddleware — captures tool traces
│   ├── evaluators.py          # ScenarioScore, C1–C4 evaluators
│   ├── harness.py             # evaluate_scenario, run_all, __main__
│   ├── scenarios/
│   │   └── scenarios.json     # 15 scenarios across A/B/C/D categories
│   └── results/               # Gitignored output directory
├── shared/                    # Shared data layer (Phase 1)
│   ├── database.py            # SQLAlchemy models (schema owner)
│   ├── business_rules.py      # DAR computation, approval routing — single source of truth
│   └── seed_data.py           # Test data population
├── classical_app/             # Flask form-based app (Phase 1–2)
│   ├── app.py                 # Routes
│   ├── forms.py               # WTForms
│   └── templates/             # Jinja2 templates (14 screens)
├── agent_app/                 # Chainlit + Microsoft Agent Framework Python (Phase 3+)
│   ├── app.py                 # Chainlit entrypoint + agent construction
│   ├── tools/                 # @tool functions; @tool(approval_mode="always_require") for writes
│   └── middleware/            # Audit, identity threading
├── kb_server/                 # MCP Knowledge Base (Phase 5)
│   ├── server.py              # MCP server
│   ├── rules/                 # Business rule markdown entries
│   └── vector_store/          # ChromaDB embeddings
├── tests/                     # pytest suite (shared/, classical_app/, agent_app/)
├── pyproject.toml             # Python metadata + deps
├── .env.example               # FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL
└── one_agent.db               # SQLite (shared by classical_app + agent_app)
```

> **Current state (2026-05-01)**: Phase 0 (model selection — `gpt-4.1-mini`),
> Phase 1 (shared data layer), and Phase 2 (classical app, read + write
> flows including the 8-screen add-delegate wizard) shipped to `main`.
> **Agent stack: C4 (Chainlit + `agent-framework` Python).** The
> 2026-04-29 pivot to C# / .NET was reversed on 2026-05-01 after Step B
> empirically falsified the documented .NET AG-UI HITL contract (see
> `docs/agent-stack-decision-2026-04-29.md` §9). C# spike code retained
> on branch `spike/csharp-b` for re-evaluation when the
> `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` preview ships an
> approval-translation middleware. Phase 3+ implementation proceeds
> against the C4 stack — a `agent-framework` Python agent fronted by
> Chainlit, calling `shared/business_rules.py` directly. 188 tests
> passing (`tests/shared` + `tests/classical_app`).
