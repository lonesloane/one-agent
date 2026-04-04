# ONE Agent: Concept Analysis and Architecture

> Replacing the "ONE MP" (ONE for Members and Partners) form-based web application with an agentic application — "ONE Agent".
>
> **Agent technology: [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python)** (Python) — the unified successor to Semantic Kernel and AutoGen.
>
> **PoC Model Constraint**: Development runs on a Visual Studio Enterprise subscription with limited Azure credits. Claude Sonnet and Opus are not viable for the PoC budget. The primary model path is Azure OpenAI via `FoundryChatClient` (gpt-4o-mini / gpt-4.1-mini as starting points), with local Ollama models for zero-cost iteration during development. A short **Model Exploration Phase** (see PoC Strategy below) is needed to validate which model provides the minimum reasoning quality required for reliable tool selection in the ONE MP domain.

---

## The Paradigm Inversion

The shift from form-based to agentic is not just a UI change — it is a fundamental inversion:

| Dimension | Form-Based (ONE MP) | Agentic (ONE Agent) |
|---|---|---|
| Process locus | In the UI/frontend | In the model's reasoning |
| User role | Data-entry operator | Intent declarator |
| User mental model | "I am here, next is X" | "I said what I want, now I watch" |
| Error surface | Per-field validation | Anywhere in an unbounded plan |
| Authorization | "User clicked Submit" = consent | "Agent determined this was needed" = ? |
| Auditability | Form submit = one event | Chain of inferences + tool calls |
| Undo semantics | Back button, clear form | What does "undo" mean for a chain? |
| Determinism | Same input → same screen flow | Same prompt → potentially different path |

---

## The Building Blocks (Sub-Projects)

### 1. Intent Layer (Conversation Interface)
Entry point where users express goals in natural language. Must:
- Parse intent with sufficient precision to route to the right agent/tool
- Handle ambiguity gracefully with minimal clarifying questions
- Maintain conversational context across a session (and across sessions for long-running tasks)
- Stream intermediate results — the user needs to see the agent working, not just get a final answer

The Microsoft Agent Framework provides native streaming via `agent.run(query, stream=True)`, returning an async generator of `AgentResponseUpdate` chunks that can be relayed to the UI in real time.

### 2. Agent Orchestration Layer
The reasoning core. Recommended pattern: **orchestrator-worker** model.

The Agent Framework offers two levels of orchestration:

- **Single agent with tools** — an `Agent` instance with a rich tool set. The agent's built-in runtime loop handles LLM inference → tool calls → result synthesis automatically. Ideal for the PoC.
- **Workflow-based orchestration** — graph-based `Workflow` with typed executors and edges for multi-agent coordination, conditional routing, checkpointing, and human-in-the-loop gates. Use when scaling beyond a single agent.
- **Agent composition** — any agent can be exposed as a tool for another agent via `agent.as_tool()`, enabling hierarchical agent architectures without a separate orchestration framework.

Example agentic loop:
```
User: "Register the new partner Acme Corp, they're based in Lyon, main contact is Claire Dupont"

Agent reasoning:
  1. Look up if Acme Corp already exists → call lookup_partner_by_name
  2. Not found → determine required fields for partner creation
  3. Have: name, city, contact name → missing: partner type, VAT, contract terms
  4. Ask user for missing required fields
  5. Once complete → call create_partner with all fields
  6. Call assign_contact to link Claire Dupont
  7. Confirm completion with summary
```

### 3. Tool / Action Layer
Every form submission becomes a typed function tool with:
- A precise schema for inputs (Pydantic `Field` annotations or explicit JSON schema via `@tool(schema=...)`)
- Execution logic that calls the existing backend/API
- Return values shaped for agent consumption (high-signal, not raw API responses)
- Error semantics that give the agent enough context to recover or escalate

**Tool design principles:**
- Use the `@tool` decorator with `Annotated` type hints and `Field(description=...)` for self-documenting schemas
- Consolidate related operations (one `create_member` with optional params, not multiple variants)
- Return semantic identifiers, not opaque IDs
- Include validation logic in the tool, not the prompt — the tool is the authority
- Tool descriptions act as contracts: if it can't do X, say so explicitly
- Use `approval_mode="always_require"` on write tools for human-in-the-loop confirmation
- Use `FunctionInvocationContext` to inject per-request context (user identity, tenant, permissions) without exposing it to the model

```python
from typing import Annotated
from pydantic import Field
from agent_framework import tool, FunctionInvocationContext

@tool(approval_mode="always_require")
def create_partner(
    legal_name: Annotated[str, Field(description="Legal name of the partner entity")],
    vat_number: Annotated[str, Field(description="EU VAT number, e.g. FR12345678")],
    contract_type: Annotated[str, Field(description="Standard, Framework, or Project")],
    primary_contact_name: Annotated[str, Field(description="Full name of the primary contact")],
    city: Annotated[str, Field(description="City where the partner is based")] = "",
    billing_email: Annotated[str, Field(description="Billing email address")] = "",
    ctx: FunctionInvocationContext = None,
) -> str:
    """Create a new Service Partner in ONE MP. Requires confirmation."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP backend API as the authenticated user ...
    return f"Partner '{legal_name}' created successfully (ID: PART-12345)"
```

### 4. State Management
Three kinds of state:

- **Conversational state**: Managed by `AgentSession` — the Agent Framework's built-in session container. Supports `session_id`, `service_session_id` (for server-managed history), and a mutable `state` dictionary. Sessions are serializable (`to_dict()` / `from_dict()`) for persistence and resumption.
- **Task state**: Where is the agent in a multi-step process? Persist intent + gathered inputs + completed steps in the session's `state` dict so conversations can resume. For complex processes, use Workflow checkpointing.
- **Domain state**: The actual data in ONE MP's backend. Agent must be idempotent-aware: check before creating.

```python
# Session creation and multi-turn conversation
session = agent.create_session()
first = await agent.run("Register Acme Corp as a partner", session=session)
# ... user provides clarification ...
second = await agent.run("Service partner, VAT is FR12345678", session=session)

# Session persistence for resumption
serialized = session.to_dict()   # store in Redis/DB
resumed = AgentSession.from_dict(serialized)
```

### 5. Authorization and Trust Layer
A permission model for agent actions, implemented via the Agent Framework's **tool approval** mechanism:

| Level | Operations | Agent Framework Implementation |
|---|---|---|
| Auto-approve | Reads, lookups, searches | `@tool(approval_mode="never_require")` |
| Confirm before execute | Mutations that can be undone | `@tool(approval_mode="always_require")` — agent returns `user_input_requests` |
| Hard approval gate | Irreversible / high-consequence actions | `@tool(approval_mode="always_require")` + custom middleware validation |
| Prohibited | Defined forbidden actions | Agent middleware that blocks and raises `MiddlewareTermination` |

The human-in-the-loop pattern works as follows:
1. Agent proposes a tool call requiring approval
2. `agent.run()` returns a result with `user_input_requests` instead of a final answer
3. The caller presents the proposed action to the user
4. User approves or rejects → `user_input_needed.create_response(True/False)`
5. The response is passed back via a new `agent.run()` call with the approval message

For a PoC: simple `approval_mode="always_require"` on all write tools is sufficient.

### 6. Audit Trail
Richer than what form-based apps produce. Implemented via **function middleware** that intercepts every tool call:

```python
from agent_framework import FunctionMiddleware, FunctionInvocationContext
import time

class AuditTrailMiddleware(FunctionMiddleware):
    """Logs every tool invocation with full context."""

    async def process(self, context: FunctionInvocationContext, call_next):
        start = time.time()
        user = context.kwargs.get("user_identity", "unknown")
        print(f"[AUDIT] User={user} Tool={context.function.name} Args={context.arguments}")

        await call_next()

        duration = time.time() - start
        print(f"[AUDIT] Tool={context.function.name} Result={context.result} Duration={duration:.3f}s")
        # ... persist to audit log store ...
```

This captures:
- Who initiated the action (user identity from `FunctionInvocationContext.kwargs`)
- What tools were called, in what order, with what arguments
- What the result of each call was
- Timing of each step

The *why* is captured alongside the *what* — a significant improvement over form submission logs.

### 7. Identity and Auth Integration
- User's identity/session token must be threaded through every tool call via `function_invocation_kwargs`
- Tools receive the identity through `FunctionInvocationContext` and enforce the same RBAC/permissions as the existing app
- The agent should NOT have super-user access — it acts as the authenticated user

```python
# Pass user identity at runtime — invisible to the model
result = await agent.run(
    "Register Acme Corp as a partner",
    session=session,
    function_invocation_kwargs={"user_identity": current_user},
)
```

### 8. Interruption and Recovery
- Tool errors return structured messages the agent can reason about and relay
- Users can cancel at any point ("stop", "cancel")
- No irreversible actions without explicit confirmation (enforced by `approval_mode`)
- Partial task state is persisted via `AgentSession` — nothing is silently lost
- Middleware can raise `MiddlewareTermination` to halt execution with a custom response

---

## The Hardest Non-Obvious Problems

### Problem 1: The Confirmation UX Trap
If every write requires confirmation, you risk recreating the click-through tedium of the form app — but worse, because the interaction is unpredictable.

**Solution**: Progressive trust. Use `approval_mode="never_require"` for low-risk operations; `approval_mode="always_require"` only for consequential, irreversible, or high-value mutations. The Agent Framework's per-tool approval granularity makes this straightforward.

### Problem 2: Partial Completion and Data Integrity
A form is a transaction boundary. An agent workflow spanning 5 tool calls is not. If the 4th call fails, what state is the system in?

**Solutions**: Transactional tooling (all-or-nothing), compensating actions (the agent knows how to undo), or explicit partial state with a "resume" capability via `AgentSession` serialization and Workflow checkpointing.

### Problem 3: Intent Ambiguity in High-Stakes Domain
"Add the new partner" might mean 15 different things depending on ONE MP's domain model.

**Solution**: Encode domain specificity in tool names and descriptions — `create_service_partner`, `create_reseller_partner` is clearer than one `create_partner` with a `type` field. The `@tool` decorator's `name` and `description` parameters encode the domain contract explicitly.

### Problem 4: The "What Did the Agent Do?" UX Problem
Users in a form app always know what happened. In an agentic app, the agent might execute 7 tool calls and produce a 3-sentence summary.

**Solution**: A transparency layer — real-time streaming of tool calls as they happen ("Looking up Acme Corp... Not found. Creating new partner record..."). The Agent Framework's streaming mode (`stream=True`) combined with function middleware for tool-call events solves both transparency and the "nothing is happening" UX problem simultaneously.

### Problem 5: Regulatory and Compliance Constraints
"Members and Partners" implies regulated data, fiduciary relationships, and potentially real financial or legal consequences:
- GDPR/data protection obligations
- Contract law implications (agent-initiated actions may constitute legal commitments)
- Financial regulations (if ONE MP handles payments or financial instruments)
- Mandatory audit requirements

The audit trail is not optional in a regulated context — it is a compliance requirement. The Agent Framework's middleware pipeline (function middleware + agent middleware) provides the interception points needed.

### Problem 6: Model Reliability and Hallucination in Tool Calls
The agent will occasionally call a tool with an incorrect argument or misinterpret intent.

**Mitigations**:
- Strict tool schemas via Pydantic `Field` annotations or explicit `schema=` on `@tool`
- Tool call validation via function middleware before any side effects
- Test harness running representative scenarios
- Confirmation before writes via `approval_mode="always_require"` (solves most "wrong action" cases)
- `gpt-4o` or `gpt-4.1` (via `FoundryChatClient`) as fallback if `gpt-4o-mini` / `gpt-4.1-mini` show unreliable tool selection — the Agent Framework is model-agnostic, switching is one line

---

## PoC Strategy: The Minimal Compelling Slice

**Do not replicate all of ONE MP.** Pick ONE workflow that:
- Has 3-7 form screens in the current app (so the compression is visible)
- Has conditional logic (so agent reasoning is genuinely valuable)
- Is frequently performed (so stakeholders recognize the value)
- Is commonly the most *painful* workflow (best candidate for demonstrating improvement)

### Three Phases, Each a Standalone Demo

**Phase 0 — Model Exploration (Week 0, parallel to domain discovery)**

Before committing to a model, run a small benchmark on ONE MP's actual domain vocabulary and tool-selection patterns. This takes 1-2 days and prevents wasted PoC effort on a model that can't reliably pick the right tool.

Candidates to evaluate (all accessible via Azure OpenAI with VS Enterprise credits):

| Model | Client | Cost tier | Known strengths |
|---|---|---|---|
| `gpt-4o-mini` | `FoundryChatClient` | Very cheap | Fast, good instruction following |
| `gpt-4.1-mini` | `FoundryChatClient` | Very cheap | Newer, improved tool use vs 4o-mini |
| `gpt-4.1-nano` | `FoundryChatClient` | Cheapest | Minimal reasoning — probably insufficient |
| `gpt-4o` | `FoundryChatClient` | Medium | Strong tool selection, higher cost |
| `phi-4-mini` (Ollama) | `OllamaChatClient` | Free (local) | Microsoft model, reasonable tool use |
| `mistral-small` (Ollama) | `OllamaChatClient` | Free (local) | Good agentic behavior for size |

**Evaluation criteria** (run 10-15 representative ONE MP intent prompts):
1. Correct tool selected (no hallucinated tool names or parameters)?
2. Structured tool arguments match schema without coercion?
3. Multi-step reasoning: does it call lookup before create?
4. Does it ask for missing required fields rather than inventing them?

**Decision rule**: use the cheapest model that passes criteria 1-4 on ≥ 85% of test prompts. If `gpt-4o-mini` or `gpt-4.1-mini` passes → use it throughout the PoC. If not → step up to `gpt-4o` / `gpt-4.1` and flag the cost implication.

The Agent Framework's model-agnostic design means switching is a one-line change:
```python
# Development iteration (zero cost)
client = OllamaChatClient(model="phi-4-mini")

# PoC target (affordable, Azure credits)
client = FoundryChatClient(model="gpt-4o-mini")    # or gpt-4.1-mini

# Fallback if mini-tier fails (higher cost)
client = FoundryChatClient(model="gpt-4o")         # or gpt-4.1
```

**Phase 1 — "The Read Agent" (Weeks 1-2)**
The agent can look up, search, and summarize information from ONE MP's data. No writes. Proves: conversational interface works, tools integrate with the backend, agent can reason over domain data. Zero risk of data corruption.

**Phase 2 — "The Write Agent with Full Confirmation" (Weeks 3-4)**
Add write tools with `approval_mode="always_require"` on every mutation. Proves: full workflow works end-to-end, confirmation UX is usable, audit trail (via function middleware) is correct.

**Phase 3 — "The Trust-Calibrated Agent" (Weeks 5-6)**
Tune the approval policy: `approval_mode="never_require"` on low-risk operations, `"always_require"` only on high-risk ones. Demonstrates the production-ready UX. This is the stakeholder demo.

Each phase is a shippable, demonstrable artifact. Stakeholders can engage at each phase.

---

## Recommended Architecture

### Stack

| Layer | Technology |
|---|---|
| Agent Runtime | Python + [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python) (`pip install agent-framework`) |
| Model (PoC — affordable) | `gpt-4o-mini` or `gpt-4.1-mini` via `FoundryChatClient` (Azure OpenAI, VS Enterprise credits) — starting point, subject to exploration |
| Model (PoC — fallback) | `gpt-4o` or `gpt-4.1` via `FoundryChatClient` if mini-tier reasoning proves insufficient for tool selection |
| Model (dev / zero-cost) | Local Ollama model (`phi-4-mini`, `mistral-small`) via `OllamaChatClient` for iteration without consuming credits |
| Model (future / if budget allows) | Claude Sonnet 4.6 via `AnthropicClient` or Claude Opus 4.6 for complex disambiguation — deferred post-PoC |
| Frontend | Next.js + Vercel AI SDK (streaming, tool call display, conversation state) |
| Session state / Audit log | Redis or SQLite (via `AgentSession.to_dict()` serialization) |
| Tool execution | Typed Python functions with `@tool` decorator and Pydantic `Field` schemas |
| Cross-cutting concerns | Agent Framework middleware (audit, security, logging) |
| MCP integration | `MCPStdioTool` / `MCPStreamableHTTPTool` (native Agent Framework support) |
| Multi-agent orchestration | Agent Framework Workflows (when needed beyond PoC) |

**Why Microsoft Agent Framework?**

The Agent Framework combines AutoGen's simple agent abstractions with Semantic Kernel's enterprise features — session-based state management, type safety, middleware, telemetry — and adds graph-based workflows for multi-agent orchestration. Key advantages for ONE Agent:

1. **Model-agnostic**: Switch between Claude (via `AnthropicClient`), GPT (via `FoundryChatClient`), or local models (via Ollama) without changing agent logic
2. **Built-in human-in-the-loop**: `approval_mode` on `@tool` + `user_input_requests` pattern — no custom confirmation code needed
3. **Native MCP support**: Both local (`MCPStdioTool`) and hosted (`MCPStreamableHTTPTool`) MCP servers as first-class tools
4. **Enterprise middleware pipeline**: Agent, function, and chat middleware for audit trails, security checks, and telemetry without modifying core logic
5. **Session management**: `AgentSession` with serialization handles conversational state, resumption, and multi-turn flows out of the box
6. **Agent composition**: `agent.as_tool()` and `agent.as_mcp_server()` enable hierarchical and interoperable agent architectures
7. **Workflow engine**: When the PoC succeeds and complexity grows, graph-based workflows with checkpointing and conditional routing are available without a framework migration

**No LangChain / LangGraph / CrewAI.** The Agent Framework provides everything needed at PoC scale and beyond. Its `Agent` + `@tool` + middleware is ~20 lines of code for a basic agent. Workflows add explicit multi-agent orchestration when needed.

### Core Agentic Loop (Sketch)

```python
import asyncio
from typing import Annotated, Any
from pydantic import Field
from agent_framework import Agent, tool, FunctionInvocationContext, AgentSession, Message
from agent_framework.azure import FoundryChatClient  # primary: Azure OpenAI via VS Enterprise

# --- System prompt encodes ONE MP domain, user permissions, behavioral rules ---
SYSTEM_PROMPT = """You are ONE Agent, an assistant for the ONE MP platform.
You help users manage members, partners, contracts, and related operations.
Always confirm write operations before executing them.
When information is missing, ask the user — do not guess."""


# --- Tool definitions ---

@tool(approval_mode="never_require")
def lookup_partner_by_name(
    name: Annotated[str, Field(description="Partner name to search for")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Search for an existing partner by name in ONE MP."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP API as authenticated user ...
    return "No partner found matching 'Acme Corp'"


@tool(approval_mode="always_require")
def create_partner(
    legal_name: Annotated[str, Field(description="Legal name of the partner entity")],
    vat_number: Annotated[str, Field(description="EU VAT number, e.g. FR12345678")],
    contract_type: Annotated[str, Field(description="Standard, Framework, or Project")],
    primary_contact_name: Annotated[str, Field(description="Full name of the primary contact")],
    city: Annotated[str, Field(description="City where the partner is based")] = "",
    ctx: FunctionInvocationContext = None,
) -> str:
    """Create a new Service Partner in ONE MP. Requires user confirmation."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP backend API ...
    return "Partner 'Acme Corp' created (ID: PART-12345)"


@tool(approval_mode="always_require")
def assign_contact(
    partner_id: Annotated[str, Field(description="Partner ID to assign the contact to")],
    contact_name: Annotated[str, Field(description="Full name of the contact")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Assign a primary contact to a partner. Requires user confirmation."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP backend API ...
    return f"Contact '{contact_name}' assigned to partner {partner_id}"


# --- Audit middleware ---

class AuditMiddleware:
    async def process(self, context: FunctionInvocationContext, call_next):
        user = context.kwargs.get("user_identity", "unknown")
        print(f"[AUDIT] user={user} tool={context.function.name} args={context.arguments}")
        await call_next()
        print(f"[AUDIT] tool={context.function.name} result={context.result}")


# --- Agent setup and execution ---

async def run_one_agent(user_message: str, session: AgentSession, user_identity: Any):
    """Run ONE Agent with a user message."""
    client = FoundryChatClient(model="gpt-4o-mini")  # swap for gpt-4.1-mini / gpt-4o as needed

    async with Agent(
        client=client,
        name="ONEAgent",
        instructions=SYSTEM_PROMPT,
        tools=[lookup_partner_by_name, create_partner, assign_contact],
        middleware=[AuditMiddleware()],
    ) as agent:

        result = await agent.run(
            user_message,
            session=session,
            function_invocation_kwargs={"user_identity": user_identity},
        )

        # Handle approval requests (human-in-the-loop)
        while result.user_input_requests:
            for request in result.user_input_requests:
                print(f"Agent proposes: {request.function_call.name}({request.function_call.arguments})")
                # In production: present to user via UI, await their decision
                approved = True  # placeholder — real UI interaction here

            messages = [user_message]
            for request in result.user_input_requests:
                messages.append(Message("assistant", [request]))
                messages.append(Message("user", [request.create_response(approved)]))

            result = await agent.run(messages, session=session,
                                     function_invocation_kwargs={"user_identity": user_identity})

        return result.text


# --- Streaming variant for the frontend ---

async def run_one_agent_streaming(user_message: str, session: AgentSession, user_identity: Any):
    """Run ONE Agent with streaming for real-time UI updates."""
    client = FoundryChatClient(model="gpt-4o-mini")  # swap for gpt-4.1-mini / gpt-4o as needed

    async with Agent(
        client=client,
        name="ONEAgent",
        instructions=SYSTEM_PROMPT,
        tools=[lookup_partner_by_name, create_partner, assign_contact],
        middleware=[AuditMiddleware()],
    ) as agent:
        async for chunk in agent.run(
            user_message,
            session=session,
            stream=True,
            function_invocation_kwargs={"user_identity": user_identity},
        ):
            if chunk.text:
                yield chunk.text  # stream to UI
            if chunk.user_input_requests:
                yield chunk.user_input_requests  # signal UI to show confirmation dialog
```

---

## Key Questions About ONE MP's Domain

Answers to these questions will fundamentally shape every design decision:

### Domain Model
1. What are the core entities? (Members, Partners, Contracts, Plans, Invoices, Events?) What is the full entity graph?
2. What distinguishes a "member" from a "partner"? Are there subtypes of each? What are the key state transitions?
3. What are the most frequently performed workflows? (Rank by volume and strategic importance)
4. What are the most **painful** workflows — the ones users most complain about? (Best PoC candidates)

### Business Rules and Compliance
5. Are there regulatory requirements governing data about members or partners? (GDPR, sector-specific regulations?)
6. Are any workflows legally or contractually consequential?
7. Who has access to do what? What is the permission/role model?
8. What is the consequence of a mistake? How hard is it to correct wrong data?

### Existing Architecture
9. Does ONE MP have a documented API / OpenAPI spec?
10. Is there an existing authentication system? (OAuth, SAML, session tokens?)
11. Is there existing audit logging? Should the agent piggyback on it or create a parallel log?
12. What data volumes are involved?

### PoC Scope and Success
13. Who is the primary user of this PoC — developer, power user, or business stakeholder?
14. What would make this PoC a **success**? What would make it a **failure**?
15. Is there a specific workflow that is notoriously complex or error-prone in the current app?
16. What is the appetite for "the agent gets it slightly wrong sometimes"?

---

## Adversarial Self-Challenge

**"The agent is just a more complex form"**
If every action requires confirmation, you've replaced "fill form, click submit" with "say thing, read plan, click confirm." The win is *compression*: one intent drives 15 steps. This only holds if workflows are genuinely multi-step. Validate this assumption early.

**"LLM reasoning is not reliable enough for consequential operations"**
Legitimate concern. Claude Opus 4.6 is highly reliable but not infallible. The Agent Framework's `approval_mode` gates and function middleware mitigate this. If the domain requires 100% accuracy, the PoC must be honest about error rates and have clear correction workflows.

**"This just moves the complexity into the system prompt"**
True. Business logic that was in the UI now lives in the system prompt and tool descriptions. This is harder to test and maintain than a UI flowchart. Significant testing discipline required. The Agent Framework's middleware provides interception points for testing.

**"Users don't want to talk to an agent, they want to click"**
Some users will prefer the predictability of forms. Agentic is better for high-variability, multi-step, expert-knowledge-requiring tasks — not for simple, repetitive, standardized operations. Hybrid is probably the right long-term answer.

**"Why not use the Anthropic SDK directly?"**
For a minimal PoC, the raw Anthropic SDK is ~20 lines for an agentic loop. But the Agent Framework adds built-in human-in-the-loop approval, session management, middleware for audit/security, native MCP support, agent composition, and a migration path to workflows — all without changing core agent logic. The abstraction cost is near-zero; the enterprise readiness gain is significant.

---

## Bottom Line

The technology exists today to build this convincingly. The hard problems are not the AI — they are the **trust architecture, confirmation UX, audit trail, and domain encoding in the tool layer**.

The Microsoft Agent Framework provides the right level of abstraction: simple enough for a PoC (Agent + @tool + middleware), powerful enough for production (workflows, checkpointing, model-agnostic routing, A2A protocol support).

The most valuable next step is understanding ONE MP's domain model and identifying the single most painful multi-step workflow to use as the PoC target.
