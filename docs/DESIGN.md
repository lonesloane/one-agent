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
| Agent runtime | Python + Microsoft Agent Framework |
| Model (PoC) | `gpt-4o-mini` or `gpt-4.1-mini` via `FoundryChatClient` (Azure OpenAI) |
| Model (dev) | Local Ollama (`phi-4-mini`, `mistral-small`) via `OllamaChatClient` |
| Model (fallback) | `gpt-4o` or `gpt-4.1` if mini-tier fails tool selection |
| Classical frontend | Flask + Jinja2 + Bootstrap 5 |
| Agent frontend | TBD — research phase pending (re-opened 2026-04-28, see OQ-7) |
| Database | SQLite (shared) |
| Business KB | MCP server (mcp SDK) + ChromaDB + git-backed markdown |
| Session/audit | `AgentSession` serialized to SQLite |
| Tools | `@tool` decorator + Pydantic `Field` schemas |
| Cross-cutting | Agent Framework middleware (audit, security) |

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

- **Human-in-the-loop**: `approval_mode="always_require"` on write tools; `"never_require"` on reads
- **Audit trail**: `FunctionMiddleware` intercepts every tool call (who, what, when, result)
- **Identity threading**: user identity passed via `function_invocation_kwargs`, invisible to model
- **MCP KB**: business rules queryable at runtime via MCP protocol (semantic search + structured lookups)
- **Streaming**: `agent.run(stream=True)` for real-time transparency in the UI

## Project Structure

```
one-agent-poc/                 # Project root
├── eval/                      # Phase 0 evaluation harness ← built in Phase 0a
│   ├── __init__.py
│   ├── tools.py               # 6 stub tools with @tool decorator
│   ├── middleware.py          # RecorderMiddleware — captures tool traces
│   ├── evaluators.py          # ScenarioScore, C1 evaluator, C2-C4 stubs
│   ├── harness.py             # evaluate_scenario, run_all, __main__
│   ├── scenarios/
│   │   └── scenarios.json     # A1, B1, C1 scenarios (Phase 0a); grows in 0b
│   └── results/               # Gitignored output directory
├── shared/                    # Shared data layer (Phase 1)
│   ├── database.py            # SQLAlchemy models
│   ├── business_rules.py      # DAR computation, approval routing
│   └── seed_data.py           # Test data population
├── classical_app/             # Flask form-based app (Phase 1-2)
│   ├── app.py                 # Routes
│   ├── forms.py               # WTForms
│   └── templates/             # Jinja2 templates (14 screens)
├── agent_app/                 # Agent Framework app (Phase 3-4)
│   ├── agent.py               # Agent setup + execution loop
│   ├── tools.py               # @tool wrappers over shared/
│   ├── middleware.py          # Audit, security
│   └── kb_server/             # MCP Knowledge Base (Phase 5)
│       ├── server.py          # MCP server
│       ├── rules/             # Business rule markdown entries
│       └── vector_store/      # ChromaDB embeddings
├── pyproject.toml             # Project metadata + dependencies
├── .env.example               # Template for FOUNDRY_PROJECT_ENDPOINT
└── one_agent.db               # SQLite (shared, Phase 1+)
```

> **Current state (2026-04-28)**: Phase 0 (model selection — `gpt-4.1-mini`),
> Phase 1 (shared data layer), and Phase 2 (classical app, read + write flows)
> shipped. **`agent_app/` rebuild pending fresh research and PRDs** — first
> attempt (Phase 3 / 3.5 / 4 / spikes) abandoned 2026-04-28 and quarantined
> under `docs/_archived/` and `plan/_archived/`. Microsoft Agent Framework
> retained as agent runtime; frontend stack and HITL approach are open
> questions again (OQ-7, OQ-9). 188 tests passing (`tests/shared` +
> `tests/classical_app`).
