# ONE Agent PoC — Architecture Overview

> Replacing the ONE MP form-based web application with a conversational agent that compresses multi-step workflows and adds proactive intelligence.

## System Overview

The PoC ships two applications sharing the same database, business rules, and test data:

- **Classical app** (Flask + forms): demonstrates the click-heavy status quo (contrast tool)
- **Agent app** (Microsoft Agent Framework): demonstrates conversational, proactive alternative

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
| Agent runtime | C# / .NET 8–9 + Microsoft Agent Framework (`Microsoft.Agents.AI`) |
| Model (PoC) | `gpt-4.1-mini` via `FoundryChatClient` (Azure AI Foundry) |
| Model (fallback) | `gpt-5.4-nano` (validated alternative, 86% on eval suite) |
| Classical frontend | Flask + Jinja2 + Bootstrap 5 (Python, unchanged) |
| Agent frontend | CopilotKit React via AG-UI (`HttpAgent` runtime registration) |
| Agent transport | `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` (`MapAGUI`) |
| Database | SQLite (cross-language integration surface) |
| Shared business rules | Python `shared/business_rules.py` ↔ C# `shared/csharp/BusinessRules.cs` (parity-tested) |
| Business KB | MCP server (mcp SDK) + ChromaDB + git-backed markdown (Phase 5) |
| Session/audit | `AgentThread` / `AgentSession` (.NET) — workflow-scoped per use case |
| Tools | `[Description]`-annotated methods + `ApprovalRequiredAIFunction` for HITL writes |
| Cross-cutting | Agent Framework middleware (audit, identity, bidirectional HITL) |

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

- **Human-in-the-loop**: `ApprovalRequiredAIFunction` wraps write tools; reads run unwrapped. Round-trip via the AG-UI `request_approval` synthetic client tool + bidirectional middleware (C# zone of MS Learn HITL doc).
- **Audit trail**: function-invocation middleware intercepts every tool call (who, what, when, result).
- **Identity threading**: user identity propagated through `IServiceProvider`-scoped context (HTTP scope) and injected into tool-method parameters; invisible to the model.
- **MCP KB**: business rules queryable at runtime via MCP protocol (semantic search + structured lookups). Phase 5 — language-agnostic, consumed by the C# agent.
- **Streaming**: AG-UI SSE stream surfaced through CopilotKit React for real-time transparency.
- **Workflow-scoped sessions**: each use case (UC1 brief, UC2 wizard, UC3 approver) opens a fresh `AgentThread`; identity persists via auth, not session history.

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
│   ├── database.py            # SQLAlchemy models (Python — schema owner)
│   ├── business_rules.py      # DAR computation, approval routing (Python)
│   ├── seed_data.py           # Test data population (Python)
│   └── csharp/                # C# port of business rules (Phase 3+)
│       ├── BusinessRules.cs   # Mirrors business_rules.py, parity-tested
│       └── BusinessRules.csproj
├── classical_app/             # Flask form-based app (Phase 1–2, Python)
│   ├── app.py                 # Routes
│   ├── forms.py               # WTForms
│   └── templates/             # Jinja2 templates (14 screens)
├── agent_app/                 # Microsoft Agent Framework app (Phase 3+, C# / .NET)
│   ├── AgentApp.csproj        # ASP.NET Core host
│   ├── Program.cs             # MapAGUI("/", agent) + DI wiring
│   ├── Tools/                 # Agent tools (`ApprovalRequiredAIFunction` writes, plain reads)
│   ├── Middleware/            # Audit, identity threading, bidirectional HITL
│   └── frontend/              # CopilotKit React app (Next.js or Vite)
│       └── (HttpAgent runtime registration → AG-UI server)
├── kb_server/                 # MCP Knowledge Base (Phase 5, language-agnostic over MCP)
│   ├── server.py              # MCP server
│   ├── rules/                 # Business rule markdown entries
│   └── vector_store/          # ChromaDB embeddings
├── tests/                     # pytest suite (Python: shared/, classical_app/)
├── pyproject.toml             # Python metadata + deps
├── global.json                # .NET SDK pin (TBD during scaffold)
├── .editorconfig              # dotnet format + ruff source of truth
├── .env.example               # FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL
└── one_agent.db               # SQLite (cross-language integration surface)
```

> **Current state (2026-04-29)**: Phase 0 (model selection — `gpt-4.1-mini`),
> Phase 1 (shared data layer), and Phase 2 (classical app, read + write
> flows including the 8-screen add-delegate wizard) shipped to `main`.
> **Agent stack pivoted to C# / .NET** — the Python `agent_app/` attempt
> was abandoned 2026-04-28 and quarantined under `docs/_archived/` and
> `plan/_archived/`; the Python AG-UI client surface proved too under-baked
> for HITL round-trip (see `docs/agent-stack-decision-2026-04-29.md`).
> Microsoft Agent Framework retained as agent runtime via the .NET package
> set; CopilotKit React selected as frontend. `agent_app/` C# scaffold +
> spike pending (Step B of the path forward). 188 tests passing
> (`tests/shared` + `tests/classical_app`).
