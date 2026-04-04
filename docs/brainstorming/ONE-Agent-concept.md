# ONE Agent: Concept Analysis and Architecture

> Replacing the "ONE MP" (ONE for Members and Partners) form-based web application with an agentic application — "ONE Agent".
>
> **ONE MP** is an OECD application used by delegations of member countries and partner organizations. It provides three core services: (1) access to official documents from the OECD document management system, governed by complex visibility rules based on document classification, country membership status, and committee participation; (2) access to events organized by OECD committees, where individual delegates participate based on their professional function; and (3) a register of all delegates, with role-based visibility. The current UI is form-driven and multi-step; the goal is to replace key workflows with a conversational agent that compresses interactions and adds proactive intelligence.
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
User: "I need to add a new delegate to our delegation — Marie Laurent,
       she's an advisor on education policy"

Agent reasoning:
  1. Identify the user's delegation → call get_delegation_info
  2. Look up if Marie Laurent already exists → call lookup_delegate
  3. Not found → determine required fields for delegate creation
  4. Have: name, function (education policy advisor)
  5. Infer relevant committees from function → "Education Policy Committee"
  6. Ask user to confirm committee participations and provide email
  7. Determine delegation's membership type (member vs partner) → drives access levels
  8. Once complete → call create_delegate
  9. Apply business rules → call create_document_access_rights for each committee
     (classification level depends on membership type and any Framework Agreements)
  10. Confirm completion with summary of delegate and access rights created
```

### 3. Tool / Action Layer
Every form submission becomes a typed function tool with:
- A precise schema for inputs (Pydantic `Field` annotations or explicit JSON schema via `@tool(schema=...)`)
- Execution logic that calls the existing backend/API
- Return values shaped for agent consumption (high-signal, not raw API responses)
- Error semantics that give the agent enough context to recover or escalate

**Tool design principles:**
- Use the `@tool` decorator with `Annotated` type hints and `Field(description=...)` for self-documenting schemas
- Consolidate related operations (one `create_delegate` with optional params, not multiple variants)
- Return semantic identifiers, not opaque IDs
- Include validation logic in the tool, not the prompt — the tool is the authority
- Tool descriptions act as contracts: if it can't do X, say so explicitly
- Use `approval_mode="always_require"` on write tools for human-in-the-loop confirmation
- Use `FunctionInvocationContext` to inject per-request context (user identity, tenant, permissions) without exposing it to the model

```python
from typing import Annotated
from pydantic import Field
from agent_framework import tool, FunctionInvocationContext

@tool(approval_mode="never_require")
def get_delegation_info(
    delegation_id: Annotated[str, Field(description="Delegation ID or country/organization name")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Retrieve delegation details: country/organization, membership type (member/partner),
    active delegate count, and any Framework Agreements in effect."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP backend API as the authenticated user ...
    return '{"name": "France", "type": "member", "delegates": 42, "framework_agreements": []}'

@tool(approval_mode="always_require")
def create_delegate(
    full_name: Annotated[str, Field(description="Full name of the delegate")],
    delegation_id: Annotated[str, Field(description="Delegation this delegate belongs to")],
    function: Annotated[str, Field(description="Professional function, e.g. 'Education Policy Advisor'")],
    email: Annotated[str, Field(description="Professional email address")],
    committee_ids: Annotated[list[str], Field(description="Committees the delegate will participate in")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Create a new delegate within a delegation. Requires confirmation."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP backend API as the authenticated user ...
    return "Delegate 'Marie Laurent' created (ID: DEL-2026-0891)"

@tool(approval_mode="always_require")
def create_document_access_rights(
    delegate_id: Annotated[str, Field(description="Delegate to grant access to")],
    committee_id: Annotated[str, Field(description="Committee scoping the document access")],
    classification_level: Annotated[str, Field(description="Max classification: General, Restricted, or Confidential")],
    retroactive: Annotated[bool, Field(description="Include documents published before accreditation date")] = False,
    ctx: FunctionInvocationContext = None,
) -> str:
    """Create Document Access Rights for a delegate, scoped to a committee and classification level.
    Requires confirmation.
    Rules: member delegates get up to 'Restricted'; partner delegates get 'General' only
    (unless a Framework Agreement covers the committee). 'Confidential' and retroactive
    access require OECD secretariat approval."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP backend API as the authenticated user ...
    return f"Document Access Rights created: delegate={delegate_id}, committee={committee_id}, level={classification_level}"
```

### 4. State Management
Three kinds of state:

- **Conversational state**: Managed by `AgentSession` — the Agent Framework's built-in session container. Supports `session_id`, `service_session_id` (for server-managed history), and a mutable `state` dictionary. Sessions are serializable (`to_dict()` / `from_dict()`) for persistence and resumption.
- **Task state**: Where is the agent in a multi-step process? Persist intent + gathered inputs + completed steps in the session's `state` dict so conversations can resume. For complex processes, use Workflow checkpointing.
- **Domain state**: The actual data in ONE MP's backend. Agent must be idempotent-aware: check before creating.

```python
# Session creation and multi-turn conversation
session = agent.create_session()
first = await agent.run("Add Marie Laurent as a delegate, she works on education policy", session=session)
# ... user provides clarification ...
second = await agent.run("Yes, assign her to the Education Policy Committee", session=session)

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
    "Add Marie Laurent as a delegate, she works on education policy",
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
"Add a new delegate" sounds simple but hides significant complexity: which delegation? Which committees? What document access levels? Does a Framework Agreement apply? Should access be retroactive?

**Solution**: Encode domain specificity in tool names and descriptions — `create_delegate` and `create_document_access_rights` are separate tools with distinct schemas rather than one monolithic operation. The `@tool` decorator's `name` and `description` parameters encode the domain contract explicitly. The agent reasons through the steps sequentially, querying delegation info to determine membership type before deciding access levels.

### Problem 4: The "What Did the Agent Do?" UX Problem
Users in a form app always know what happened. In an agentic app, the agent might execute 7 tool calls and produce a 3-sentence summary.

**Solution**: A transparency layer — real-time streaming of tool calls as they happen ("Checking delegation info for France... Looking up Marie Laurent... Not found. Creating delegate record... Setting up Document Access Rights..."). The Agent Framework's streaming mode (`stream=True`) combined with function middleware for tool-call events solves both transparency and the "nothing is happening" UX problem simultaneously.

### Problem 5: Regulatory and Compliance Constraints
ONE MP manages OECD delegation data — regulated institutional data with diplomatic, legal, and data protection implications:
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

**Do not replicate all of ONE MP.** Two specific use cases have been identified as PoC targets, chosen because they demonstrate complementary strengths of the agentic approach:

**Use Case 1 — Proactive Meeting Brief** (read-only, proactive intelligence)
A delegate connects to ONE MP. The agent greets them with information about their next scheduled committee meeting — which committee, when, how many agenda documents. If any documents were added or modified since the delegate's last visit, the agent highlights them and provides direct links. *This use case is structurally impossible in a form-based app — it demonstrates what an agent can do that forms cannot.*

**Use Case 2 — Delegate Creation with Document Access Rights** (write, complex reasoning)
A delegation editor creates a new delegate. Based on the information provided (name, function, committees) and the delegation's membership type, the agent must reason through business rules to determine the correct Document Access Rights — what document classification levels the delegate can see, for which committees, and whether any special conditions apply (Framework Agreements, retroactive access, approval routing). *This use case compresses a multi-screen form workflow into a guided conversation and demonstrates the agent's ability to apply conditional business logic.*

### PoC Business Rules (Illustrative)

For the PoC, the following business rules drive Document Access Rights. These are designed to demonstrate reasoning complexity rather than mirror the production system exactly:

| Rule | Description |
|---|---|
| Classification tiers | Documents are classified as Public, General, Restricted, or Confidential |
| Member access | Delegates from member countries get General + Restricted access for their committees |
| Partner access | Delegates from partner organizations get General access only |
| Framework Agreement | If a partner has a Framework Agreement covering specific committees, their delegates get Restricted access for those committees |
| Confidential access | Requires explicit OECD secretariat approval, regardless of membership type |
| Retroactive access | Access to documents published before the delegate's accreditation date requires secretariat approval |
| Approval routing | General access → auto-approved; Restricted → delegation head; Confidential/retroactive → secretariat |

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

**Phase 1 — "The Proactive Read Agent" (Weeks 1-2)**
Implements Use Case 1. The agent greets delegates with their upcoming meeting brief, highlights new agenda documents, and answers questions about schedules and document content. No writes. Proves: proactive conversational interface works, document visibility rules function correctly, streaming UX gives real-time feedback. Zero risk of data corruption.

**Phase 2 — "The Write Agent with Reasoning" (Weeks 3-4)**
Implements Use Case 2. The agent guides delegation editors through delegate creation, reasons through Document Access Rights business rules, and executes writes with `approval_mode="always_require"` on every mutation. Proves: multi-step reasoning over business rules works end-to-end, confirmation UX is usable, audit trail (via function middleware) captures the full chain of reasoning and approvals.

**Phase 3 — "The Trust-Calibrated Agent" (Weeks 5-6)**
Combines both use cases. Tunes the approval policy: lookups and reads are auto-approved, General-level DAR creation can be auto-approved for member delegates, Restricted/Confidential access always requires confirmation. Demonstrates the production-ready UX. This is the stakeholder demo.

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
SYSTEM_PROMPT = """You are ONE Agent, an assistant for the ONE MP platform at the OECD.
You help delegation editors and delegates manage delegate records, committee participations,
document access rights, and meeting preparation.
Always confirm write operations before executing them.
When information is missing, ask the user — do not guess.
When creating a delegate, always determine the correct Document Access Rights based on
the delegation's membership type (member or partner) and the delegate's committee participations.
Member delegates get General + Restricted access; partner delegates get General only
(unless a Framework Agreement covers the committee). Confidential and retroactive access
require OECD secretariat approval."""


# --- Read tools (auto-approved) ---

@tool(approval_mode="never_require")
def get_delegation_info(
    delegation_id: Annotated[str, Field(description="Delegation ID or country/organization name")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Retrieve delegation details: country/organization, membership type (member/partner),
    active delegate count, and any Framework Agreements in effect."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP API as authenticated user ...
    return '{"name": "France", "type": "member", "delegates": 42, "framework_agreements": []}'


@tool(approval_mode="never_require")
def lookup_delegate(
    name: Annotated[str, Field(description="Delegate name to search for")],
    delegation_id: Annotated[str, Field(description="Delegation to search within")] = "",
    ctx: FunctionInvocationContext = None,
) -> str:
    """Search for an existing delegate by name, optionally within a specific delegation."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP API as authenticated user ...
    return "No delegate found matching 'Marie Laurent'"


@tool(approval_mode="never_require")
def get_upcoming_meetings(
    delegate_id: Annotated[str, Field(description="Delegate ID to look up meetings for")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Retrieve upcoming committee meetings for a delegate based on their
    committee participations. Returns meeting date, committee name, and agenda status."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP API as authenticated user ...
    return '[{"committee": "Education Policy Committee", "date": "2026-04-18", "agenda_docs": 12, "new_since_last_login": 3}]'


@tool(approval_mode="never_require")
def get_agenda_documents(
    meeting_id: Annotated[str, Field(description="Meeting ID to retrieve agenda documents for")],
    since: Annotated[str, Field(description="ISO date — only return docs added/modified after this date")] = "",
    ctx: FunctionInvocationContext = None,
) -> str:
    """Retrieve documents on a committee meeting's agenda, optionally filtered
    to only those added or modified since a given date."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP API as authenticated user ...
    return '[{"title": "Education at a Glance 2026 — Draft", "classification": "Restricted", "modified": "2026-04-02"}]'


# --- Write tools (require confirmation) ---

@tool(approval_mode="always_require")
def create_delegate(
    full_name: Annotated[str, Field(description="Full name of the delegate")],
    delegation_id: Annotated[str, Field(description="Delegation this delegate belongs to")],
    function: Annotated[str, Field(description="Professional function, e.g. 'Education Policy Advisor'")],
    email: Annotated[str, Field(description="Professional email address")],
    committee_ids: Annotated[list[str], Field(description="Committees the delegate will participate in")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Create a new delegate within a delegation. Requires user confirmation."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP backend API ...
    return "Delegate 'Marie Laurent' created (ID: DEL-2026-0891)"


@tool(approval_mode="always_require")
def create_document_access_rights(
    delegate_id: Annotated[str, Field(description="Delegate to grant access to")],
    committee_id: Annotated[str, Field(description="Committee scoping the document access")],
    classification_level: Annotated[str, Field(description="Max classification: General, Restricted, or Confidential")],
    retroactive: Annotated[bool, Field(description="Include documents published before accreditation date")] = False,
    ctx: FunctionInvocationContext = None,
) -> str:
    """Create Document Access Rights for a delegate, scoped to a committee and classification level.
    Requires user confirmation.
    Rules: member delegates get up to 'Restricted'; partner delegates get 'General' only
    (unless a Framework Agreement covers the committee). 'Confidential' and retroactive
    access require OECD secretariat approval."""
    user = ctx.kwargs.get("user_identity")
    # ... call ONE MP backend API ...
    return f"Document Access Rights created: delegate={delegate_id}, committee={committee_id}, level={classification_level}"


# --- Audit middleware ---

class AuditMiddleware:
    async def process(self, context: FunctionInvocationContext, call_next):
        user = context.kwargs.get("user_identity", "unknown")
        print(f"[AUDIT] user={user} tool={context.function.name} args={context.arguments}")
        await call_next()
        print(f"[AUDIT] tool={context.function.name} result={context.result}")


# --- Agent setup and execution ---

ALL_TOOLS = [
    get_delegation_info, lookup_delegate, get_upcoming_meetings,
    get_agenda_documents, create_delegate, create_document_access_rights,
]

async def run_one_agent(user_message: str, session: AgentSession, user_identity: Any):
    """Run ONE Agent with a user message."""
    client = FoundryChatClient(model="gpt-4o-mini")  # swap for gpt-4.1-mini / gpt-4o as needed

    async with Agent(
        client=client,
        name="ONEAgent",
        instructions=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
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
        tools=ALL_TOOLS,
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

## Domain Context (Established)

The following domain understanding shapes all design decisions. For the PoC, business rules are illustrative — designed to demonstrate the agent's reasoning capabilities rather than mirror the production system exactly.

### Core Entities
- **Delegation**: Represents a member country or partner organization at the OECD. One delegation per country/organization. Has a membership type: *member* or *partner*
- **Delegate**: An individual belonging to exactly one delegation. Has a professional function (e.g., "Education Policy Advisor") that determines which OECD committees they participate in
- **Committee**: An OECD body (e.g., Education Policy Committee, Trade Committee, Development Assistance Committee). Individual delegates participate in committees based on their professional function — delegations themselves are not linked to committees
- **Document**: An official document in the OECD document management system. Has a classification level (Public, General, Restricted, Confidential) and belongs to one or more committees
- **Document Access Rights (DAR)**: Drives what documents a delegate can see. Scoped to a specific committee and classification level. Created when a delegate is registered, based on business rules involving the delegation's membership type, the delegate's committee participations, and any Framework Agreements

### Key Actors
- **Delegate**: Uses ONE MP to access documents, view committee meeting schedules, and consult the delegate registry
- **Delegation editor**: Administrative user who manages delegates within their delegation (creates, updates, deactivates). Some delegations require delegation head approval for certain operations; others allow the editor to act autonomously
- **OECD secretariat**: Approves high-sensitivity operations (Confidential access, retroactive access)

### Remaining Open Questions (Post-PoC)
- What is the full permission/role model beyond delegation editor and secretariat?
- What existing APIs, authentication, and audit infrastructure exist? (Deferred — the PoC will use simulated backends)
- What data volumes are involved in production?
- What are the compliance/GDPR requirements for delegate personal data?
- What is the full scope of document visibility rules beyond the three axes used in the PoC (classification, membership type, committee participation)?

---

## Adversarial Self-Challenge

**"The agent is just a more complex form"**
If every action requires confirmation, you've replaced "fill form, click submit" with "say thing, read plan, click confirm." Two counters: (1) Use Case 1 (proactive meeting brief) is structurally impossible in a form — the agent adds a capability that didn't exist, not just a different skin on the same one. (2) Use Case 2 compresses a multi-screen form into a guided conversation where the agent reasons through Document Access Rights rules — the win is *compression* and *intelligence*, not just a different input modality.

**"LLM reasoning is not reliable enough for consequential operations"**
Legitimate concern. Claude Opus 4.6 is highly reliable but not infallible. The Agent Framework's `approval_mode` gates and function middleware mitigate this. If the domain requires 100% accuracy, the PoC must be honest about error rates and have clear correction workflows.

**"This just moves the complexity into the system prompt"**
True. Business logic that was in the UI now lives in the system prompt and tool descriptions. This is harder to test and maintain than a UI flowchart. Significant testing discipline required. The Agent Framework's middleware provides interception points for testing.

**"Users don't want to talk to an agent, they want to click"**
Some delegates will prefer the predictability of forms. Agentic is better for high-variability, multi-step, expert-knowledge-requiring tasks (like navigating Document Access Rights rules) — not for simple, repetitive, standardized operations. The proactive meeting brief (UC1) sidesteps this objection entirely: no one "wants to click" through a form to get a summary of what's new. Hybrid is probably the right long-term answer.

**"Why not use the Anthropic SDK directly?"**
For a minimal PoC, the raw Anthropic SDK is ~20 lines for an agentic loop. But the Agent Framework adds built-in human-in-the-loop approval, session management, middleware for audit/security, native MCP support, agent composition, and a migration path to workflows — all without changing core agent logic. The abstraction cost is near-zero; the enterprise readiness gain is significant.

---

## Bottom Line

The technology exists today to build this convincingly. The hard problems are not the AI — they are the **trust architecture, confirmation UX, audit trail, and domain encoding in the tool layer**.

The Microsoft Agent Framework provides the right level of abstraction: simple enough for a PoC (Agent + @tool + middleware), powerful enough for production (workflows, checkpointing, model-agnostic routing, A2A protocol support).

The most valuable next step is understanding ONE MP's domain model and identifying the single most painful multi-step workflow to use as the PoC target.
