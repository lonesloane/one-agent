# ONE Agent + Business Knowledge Base via MCP: Deep Architecture Analysis

> How to combine the ONE Agent agentic application with a business knowledge base
> exposed as an MCP server, enabling the agent to reason over user requests with
> high confidence and ask for clarification only when the KB cannot provide a clear answer.
>
> **Agent technology: [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python)** (Python) — with native MCP support via `MCPStdioTool` and `MCPStreamableHTTPTool`.

---

## Meta-Cognitive Framing

The core insight driving this design: the agent's intent ambiguity problem is not a prompt
engineering problem — it's a **knowledge distribution problem**. All the rules, workflows,
and eligibility logic that resolve "add a new partner" into a specific, unambiguous operation
currently live in the heads of power users and scattered documentation. The KB externalizes
that institutional memory into a form the agent can query at runtime.

The secondary insight from the [RAG-MCP paper](https://arxiv.org/html/2505.03275v1): semantic
retrieval of relevant context before tool selection improves accuracy by **3x** (43% vs 13%
baseline) and cuts prompt tokens by 50%. This is not a marginal gain — it's a qualitative
difference.

---

## 1. Architecture of the Business Knowledge Base

### What Lives in the KB

The KB is the institutional memory of ONE MP. It contains everything that currently lives in
the heads of power users or in scattered documentation:

| Category | Examples | Format |
|---|---|---|
| Entity schemas | Partner fields, required vs optional, allowed values | Structured JSON/YAML |
| Workflow definitions | Step-by-step process for create/update/close operations | Structured YAML |
| Business rules | Eligibility criteria, validation rules, conditional logic | Semantic documents |
| Decision trees | "Which workflow applies given these conditions?" | Structured JSON |
| Role-based permissions | Who can do what, approval thresholds | Structured YAML |
| Edge cases & exceptions | "When X and Y are both true, do Z" | Semantic documents with metadata |
| Regulatory constraints | GDPR handling, compliance checkpoints | Semantic documents |
| Glossary | Domain terminology, disambiguation | Key-value store |

### Structure: A Hybrid, Not a Monolith

The KB uses different representations for different content types because different content is
queried differently:

```yaml
# Example KB entry: partner_create_service_001.md
---
rule_id: "partner_create_service_001"
entity_type: "partner"
operation: "create"
partner_type: "service"
certainty_level: "authoritative"     # authoritative | verified | draft | deprecated
source: "ONE MP v3.2 functional spec, §4.2"
last_validated: "2025-11-15"
validated_by: "product-owner@company.com"
scope_conditions: "applies when partner_category = 'SERVICE'"
supersedes: []
tags: ["create", "partner", "service", "eligibility"]
---

A Service Partner is created when an external vendor provides billable services
under contract. Required fields: legal_name, vat_number, contract_type,
primary_contact_name, billing_email.

Manager approval is required if contract_value > 50,000 EUR.
The billing_email must be different from the primary_contact_email.
VAT numbers must be validated against the EU VIES registry before submission.
```

### Granularity Principle

- Too coarse (one big document per workflow) → retrieval picks up irrelevant content
- Too fine (one sentence per document) → retrieval misses connections between related rules
- **Sweet spot**: topic-sized chunks (~200-500 words) with rich, structured front matter metadata

### Authoring and Maintenance

- **Initial population**: power-user interviews + walking through existing app screens + reading source code/form validation logic
- **Ongoing**: business analysts/product owners via a git-backed CMS (markdown files in a repo — human-editable, version-controlled, diffable)
- **Sync discipline**: the KB should drive app behavior, not mirror it retroactively. If the KB says X and the app does Y, that's a bug in one or the other — flag it

---

## 2. MCP as the Exposure Layer

### Why MCP, Specifically?

The key distinction, sourced from [Meibel's RAG vs MCP analysis](https://www.meibel.ai/post/the-right-context-at-the-right-time-designing-with-rag-and-mcp):

> RAG is the *what* (what knowledge gets added). MCP is the *how* (how the agent connects to
> and queries it). RAG excels for stable policy/rule documents. MCP enables agent-driven,
> multi-hop, runtime retrieval.

MCP wins here because:
- The agent decides **at runtime** what to query, based on current conversational context — not pre-loaded into the prompt
- The agent can do **multi-hop**: "I retrieved rule X, which references condition Y, let me look up Y"
- The interface is **standardized** — any MCP-compatible client works without custom integration
- **Resources** expose static entity schemas as always-available context; **Tools** expose dynamic query capabilities

Why not just embed rules in the system prompt?
- Token-limited — a full ONE MP rulebook would exceed what can be attended to effectively
- Static — requires redeployment on every rule change
- No selective retrieval — agent gets everything even when most is irrelevant

Why not RAG-only (without MCP)?
- RAG is pre-agentic: retrieval happens before the agent reasons, not during
- The agent cannot ask follow-up questions about the KB mid-reasoning
- No standardized query interface

**The optimal design: an MCP server that internally uses RAG** for semantic search, but also
exposes structured lookup tools for exact queries.

### Microsoft Agent Framework MCP Integration

The Agent Framework provides **native MCP support** through three connection types, eliminating
the need for custom MCP client code:

| Connection Type | Class | Use Case |
|---|---|---|
| Local process (stdio) | `MCPStdioTool` | KB server running as a local Python process |
| HTTP / SSE | `MCPStreamableHTTPTool` | KB server deployed as an HTTP service |
| WebSocket | `MCPWebsocketTool` | Real-time streaming connections |

For the ONE Agent KB, `MCPStdioTool` is ideal for development (zero infrastructure), with
`MCPStreamableHTTPTool` for production deployment.

```python
from agent_framework import Agent, MCPStdioTool
from agent_framework.anthropic import AnthropicClient

# Connect to the KB MCP server running as a local process
async with (
    MCPStdioTool(
        name="one-mp-knowledge-base",
        command="python",
        args=["-m", "one_agent.kb_server"],
    ) as kb_mcp,
    Agent(
        client=AnthropicClient(model="claude-sonnet-4-6"),
        name="ONEAgent",
        instructions=SYSTEM_PROMPT,
        tools=[kb_mcp, lookup_partner, create_partner, assign_contact],
    ) as agent,
):
    result = await agent.run("Register Acme Corp as a new partner")
```

For production (HTTP-deployed KB server):

```python
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.anthropic import AnthropicClient

async with (
    MCPStreamableHTTPTool(
        name="one-mp-knowledge-base",
        url="https://kb.onemp.internal/mcp",
    ) as kb_mcp,
    Agent(
        client=AnthropicClient(model="claude-sonnet-4-6"),
        name="ONEAgent",
        instructions=SYSTEM_PROMPT,
        tools=[kb_mcp, lookup_partner, create_partner, assign_contact],
    ) as agent,
):
    result = await agent.run("Register Acme Corp as a new partner")
```

### MCP KB Server Tool Interface Design

The KB server is built using the standard MCP Python SDK (`mcp`) and exposes tools that the
Agent Framework automatically discovers and makes available to the agent:

```python
# MCP KB Server — Tool Definitions (runs as a separate process / HTTP service)
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("one-mp-knowledge-base")

@server.tool()
async def search_business_rules(
    query: str,
    entity_type: str | None = None,
    operation: str | None = None,
) -> dict:
    """
    Semantic search over the business rule KB.
    Returns matching rules ranked by relevance, with confidence metadata.
    Use when you need to understand what rules apply to a given situation
    before deciding how to proceed.
    """
    # Internally: embed query, search vector store, return top-k with scores
    return {
        "results": [{"rule_id": "...", "content": "...", "score": 0.94}],
        "confidence": "high",       # high (>0.90) | medium (0.75-0.90) | low (<0.75)
        "coverage": "complete",     # complete | partial | none
        "contradictions": [],       # any conflicting rules found
    }

@server.tool()
async def get_workflow_definition(
    entity_type: str,
    operation: str,
) -> dict:
    """
    Retrieve the exact workflow definition for a given entity type and operation.
    Returns required steps, required/optional fields, and conditional branches.
    Always call this before starting any create/update/delete operation.
    """
    return {
        "workflow_id": "partner_create_service",
        "steps": ["validate_eligibility", "collect_fields", "manager_approval_if_needed", "create"],
        "required_fields": ["legal_name", "vat_number", "contract_type", "primary_contact_name"],
        "optional_fields": ["billing_email", "phone"],
        "conditional_branches": [
            {"condition": "contract_value > 50000", "then": "require_manager_approval"}
        ],
        "confidence": "high",
        "found": True,
    }

@server.tool()
async def check_eligibility(
    entity_type: str,
    operation: str,
    context: dict,
) -> dict:
    """
    Given what we know about the entity/request so far, determine if the
    operation is eligible and what additional information is needed.
    Use after collecting partial context to identify what's still missing.
    """
    return {
        "eligible": "yes | no | unknown",
        "missing_required_fields": ["contract_type"],
        "blocking_conditions": [],
        "confidence": "medium",
        "next_question": "What type of contract will this partner operate under?",
    }

@server.tool()
async def resolve_ambiguity(
    user_request: str,
    candidates: list[str],
) -> dict:
    """
    Given an ambiguous user request and a list of possible interpretations
    identified from the KB, return the most likely match with confidence,
    and a ready-to-use clarification question if confidence is insufficient.
    """
    return {
        "best_match": "create_service_partner",
        "confidence": 0.71,
        "alternatives": ["create_reseller_partner", "create_affiliate_partner"],
        "clarification_needed": True,
        "clarification_question": (
            "Is Acme Corp a Service Partner (provides billable services) "
            "or a Reseller Partner (distributes your products)?"
        ),
    }

# MCP Resources — static, always available as context
@server.resource("kb://schemas/{entity_type}")
async def get_entity_schema(entity_type: str) -> str:
    """Full schema for a given entity type: fields, types, constraints, relationships."""
    # ... return schema as JSON string ...

@server.resource("kb://workflows/index")
async def get_workflow_index() -> str:
    """Index of all available workflows by entity type and operation."""
    # ... return workflow index as JSON string ...


# Run the server
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

### What "Confident" vs "Ambiguous" Looks Like

Every KB tool response carries explicit confidence signals. The agent reads these to decide
what to do next:

| Confidence | Signal | Agent behavior |
|---|---|---|
| `high` (score > 0.90, coverage: complete) | Exact rule found, unambiguous | Act directly, no clarification needed |
| `medium` (0.75-0.90, coverage: partial) | Rules found but conditions don't fully match | Propose action, ask user to confirm |
| `low` (< 0.75, coverage: none) | No applicable rule found, or rules contradict | Ask targeted clarification question |
| `contradictions` present | Two rules conflict | Surface the conflict explicitly, ask user to resolve |

---

## 3. The Agent's Reasoning Loop

### Full Walk-Through

```
User: "Register Acme Corp as a new partner — they're based in Lyon,
       main contact is Claire Dupont"

━━━ STEP 1: Intent Classification ━━━
Agent queries KB (via MCPStdioTool): search_business_rules("register new partner")
→ KB returns: "partner_create workflow family" with confidence: "medium"
  (medium because "partner" is ambiguous — multiple types exist)
→ Agent also calls: resolve_ambiguity("register new partner",
    ["create_service_partner", "create_reseller_partner", "create_affiliate_partner"])
→ KB returns: confidence: 0.68, clarification_needed: true
→ Clarification question generated by KB:
  "Is Acme Corp a Service Partner (provides services) or a Reseller Partner
   (distributes your products)?"

━━━ STEP 2: Single Targeted Clarification ━━━
Agent → User: "Is Acme Corp a Service Partner or a Reseller Partner?"
User → "Service partner"

━━━ STEP 3: Workflow Retrieval ━━━
Agent calls: get_workflow_definition("partner", "create_service")
→ KB returns: required_fields=[legal_name, vat_number, contract_type,
    primary_contact_name, billing_email], confidence: "high"

━━━ STEP 4: Context Matching ━━━
From user's message: legal_name="Acme Corp", city="Lyon", contact="Claire Dupont"
Missing: vat_number, contract_type, billing_email
Agent calls: check_eligibility("partner", "create_service",
    {legal_name: "Acme Corp", contact: "Claire Dupont"})
→ KB returns: missing_required_fields=["vat_number", "contract_type"],
  next_question: "What is Acme Corp's VAT number and what contract type
                  will they operate under? (Standard, Framework, or Project)"

━━━ STEP 5: Batched Clarification ━━━
Agent → User: "To complete Acme Corp's registration I need:
  - Their VAT number
  - Contract type: Standard, Framework, or Project?"
User → "VAT FR12345678, Standard contract"

━━━ STEP 6: Execution with Confirmation ━━━
Agent calls create_partner({...})
→ Tool has approval_mode="always_require"
→ Agent Framework returns user_input_requests to the caller
→ UI shows: "Here's what I'm about to do:
  Create Service Partner: Acme Corp
  - Location: Lyon
  - VAT: FR12345678
  - Contract: Standard
  - Primary contact: Claire Dupont
  Shall I proceed?"
User → approves → create_response(True)
→ Tool executes → success
Agent calls assign_contact → same approval flow → success
Audit middleware logs: user identity, KB rules used, tool calls, user confirmation

━━━ RESULT ━━━
Total clarification questions: 2 (vs ~15 form fields in ONE MP)
Both questions were necessary and could not be inferred from context.
```

### How the Agent Framework Manages This Flow

The key difference from a hand-rolled agentic loop: the Agent Framework's runtime handles the
LLM inference → tool call → result synthesis cycle automatically. The developer defines tools
and middleware; the framework manages the loop:

```python
from agent_framework import Agent, MCPStdioTool, AgentSession, Message
from agent_framework.anthropic import AnthropicClient

async def run_registration_flow(user_message: str, session: AgentSession, user_identity):
    async with (
        MCPStdioTool(
            name="one-mp-knowledge-base",
            command="python",
            args=["-m", "one_agent.kb_server"],
        ) as kb_mcp,
        Agent(
            client=AnthropicClient(model="claude-sonnet-4-6"),
            name="ONEAgent",
            instructions=SYSTEM_PROMPT,
            tools=[kb_mcp, lookup_partner, create_partner, assign_contact],
            middleware=[AuditMiddleware(), SecurityMiddleware()],
        ) as agent,
    ):
        result = await agent.run(
            user_message,
            session=session,
            function_invocation_kwargs={"user_identity": user_identity},
        )

        # Handle approval requests (human-in-the-loop)
        while result.user_input_requests:
            for req in result.user_input_requests:
                # Present to user via UI
                print(f"Approve {req.function_call.name}({req.function_call.arguments})?")

            # Collect user decisions and continue
            approved = await get_user_approval_from_ui(result.user_input_requests)
            messages = build_approval_messages(user_message, result.user_input_requests, approved)
            result = await agent.run(
                messages,
                session=session,
                function_invocation_kwargs={"user_identity": user_identity},
            )

        return result.text
```

### When Does the Agent Query the KB?

- **Proactively on every new intent** — before considering any backend tools, the agent queries the KB (via MCP) to classify the operation and retrieve the applicable workflow. This happens once per new user goal, not per message
- **Multi-hop when confidence is medium** — first query returns medium confidence → agent probes with a more specific query (e.g., narrow by entity type or operation)
- **Never for pure reads** — simple lookups ("find partner Acme Corp") don't need KB consultation; the agent already knows the search tool and its schema
- **On conditional branches** — mid-workflow, when the agent hits a conditional step (e.g., "if contract_value > 50k, require approval"), it re-queries the KB to confirm the condition and retrieve the approval sub-workflow

### Handling Contradictory Rules

The KB response includes a `contradictions` array. When non-empty:
1. Agent does not guess — it surfaces the conflict explicitly: *"I found two applicable rules that conflict: Rule A says [X] (applies when [Y]), Rule B says [Z] (applies when [W]). Which applies here?"*
2. The contradiction is logged as a KB quality flag for human review
3. Long-term: contradictions auto-detected on KB ingestion, preventing them from reaching the agent

---

## 4. The Clarification Strategy

### The Anti-Pattern to Avoid

The "20 questions" failure mode: agent asks field by field, recreating the form experience in
chat. This happens when the agent treats the KB as a field checklist rather than a reasoning
resource.

### The Right Pattern: Targeted, Batched, Contextualized

| Scenario | Wrong | Right |
|---|---|---|
| Missing required field | "What is the VAT number?" | KB generates question with context: "What is Acme Corp's EU VAT number? (format: FR12345678)" |
| Ambiguous operation type | "Which type of partner?" | KB generates multiple-choice with descriptions: "Service Partner (provides services) or Reseller Partner (distributes your products)?" |
| Multiple missing fields | Ask one by one | KB's `check_eligibility` returns `next_question` — the single most blocking missing field. Batch non-blocking ones |
| Low KB coverage | "I don't understand" | "I don't have a specific rule for this scenario. Based on similar cases, I'd proceed with [X]. Does that sound right?" |

### Clarification → KB Learning Loop

User clarifications are high-signal data about KB gaps. The pipeline:

```
User answers clarification question
    ↓
Agent logs: {original_request, KB_confidence, clarification_asked, user_answer}
    (captured by AuditMiddleware via FunctionInvocationContext)
    ↓
Review queue: "3 users were asked the same clarification for 'register partner'"
    ↓
KB maintainer creates new disambiguation rule:
  "When user says 'register partner' without type, ask: Service or Reseller?"
    ↓
KB coverage improves → same question no longer asked next time
```

This is the compounding return of the architecture: **the agent gets smarter over time without
retraining the model**.

### Fallback Chain

```
KB confidence: high        → Agent acts directly
KB confidence: medium      → Agent proposes plan, user confirms
KB confidence: low         → Agent asks one targeted clarification
Clarification + still low  → Agent presents draft action for human review
No resolution possible     → Agent creates escalation ticket, notifies owner
```

---

## 5. KB Quality and Confidence Scoring

### KB Entry Metadata Schema

Every entry carries machine-readable metadata that the MCP server uses to compute confidence
scores:

```yaml
---
rule_id: "partner_create_service_001"
entity_type: "partner"
operation: "create"
partner_type: "service"
certainty_level: "authoritative"   # authoritative | verified | draft | deprecated
source: "ONE MP v3.2 functional spec, §4.2"
last_validated: "2025-11-15"
validated_by: "product-owner@company.com"
scope_conditions: "applies when partner_category = 'SERVICE'"
supersedes: []
superseded_by: null
tags: ["create", "partner", "service", "eligibility"]
---
```

Confidence is computed from multiple signals:

| Signal | Weight |
|---|---|
| Semantic similarity score from vector search | High |
| `certainty_level` of the retrieved entry | High |
| `last_validated` recency | Medium |
| Whether `scope_conditions` match current context | High |
| Absence of contradicting rules | Medium |

### Staleness Detection — Closing the Feedback Loop

The agent can flag KB entries as potentially outdated based on what it observes when calling
backend tools. This is captured by **function middleware** that compares KB expectations with
actual API behavior:

```python
from agent_framework import FunctionMiddleware, FunctionInvocationContext

class KBStalenessDetector(FunctionMiddleware):
    """Detects when KB rules diverge from actual API behavior."""

    async def process(self, context: FunctionInvocationContext, call_next):
        # Record pre-call expectations from KB
        kb_expectations = context.kwargs.get("kb_expectations", {})

        await call_next()

        # Compare expectations with actual results
        if kb_expectations and context.result:
            # e.g., KB said vat_number is required, but API accepted without it
            self._check_field_divergence(kb_expectations, context.result)

    def _check_field_divergence(self, expected, actual):
        # ... log to KB health dashboard for review ...
        pass
```

Example flow:
```
KB says: "vat_number is required for create_service_partner"
Agent calls create_service_partner without vat_number → API accepts it
→ KBStalenessDetector logs: "KB rule partner_create_service_001 may be outdated —
   API accepted call without vat_number field"
→ Flag appears in KB health dashboard for review
```

This is the most powerful quality mechanism: **the production system itself validates the KB**.

### Coverage Testing

Run a batch of representative historical user requests against the KB:

| Metric | Target |
|---|---|
| Requests answered with high confidence | > 80% |
| Requests requiring one clarification question | < 15% |
| Requests requiring human escalation | < 5% |
| Mean KB round-trips per request | < 2 |

---

## 6. Rigorous Comparison: MCP KB vs Alternatives

### Option A — Rules in System Prompt

**Pros:** Zero latency, always available, zero infrastructure
**Cons:** Token-limited; static (requires redeployment on every rule change); no selective
retrieval — agent gets everything even when most is irrelevant; poor maintainability by
non-technical staff

**Verdict:** Use for the 10 most stable, most-used rules. Not for the full KB. These two
approaches are complementary, not competing.

### Option B — Standalone RAG with Vector DB

**Pros:** Semantic retrieval, scalable, updateable without redeployment, well-understood
**Cons:** Retrieval is *pre-agentic* — happens before the agent reasons, not during; agent
cannot do multi-hop KB queries mid-reasoning; confidence scoring is implicit (similarity score
only); no standardized interface

**Verdict:** The right *internal implementation* for the KB's search capability. But MCP
should be the interface layer above it. RAG alone is a retrieval mechanism, not an
agent-accessible service.

### Option C — MCP KB (RAG inside MCP) ✓ Recommended

**Pros:** Agent-driven retrieval at runtime with full conversational context; structured query
interface with explicit confidence signals; multi-hop capable; updateable without redeployment;
standardized protocol; exposes both static resources and dynamic query tools; audit trail of
which rules the agent used; **natively supported by the Microsoft Agent Framework** via
`MCPStdioTool` / `MCPStreamableHTTPTool` — no custom client code needed

**Cons:** Adds latency per request (one KB round-trip — mitigated by caching); more complex
to build than pure RAG; requires MCP server maintenance

**Verdict:** The right architecture for ONE Agent's business rule layer. RAG is the engine
inside; MCP is the interface the agent drives.

### Option D — Fine-Tuned Model

**Pros:** Knowledge baked into weights, no retrieval latency
**Cons:** Business rules change constantly; fine-tuning is expensive; catastrophic forgetting;
you cannot audit which rule the model used; retraining required on every rule change

**Verdict:** Wrong tool entirely. Fine-tuning is for style and format, not for volatile
business knowledge.

### The Optimal Hybrid

```
┌─────────────────────────────────────────────────────┐
│ Agent Instructions (system prompt)                   │
│  - Core behavioral rules (tone, safety, fallback)   │
│  - Top 5-10 most stable, most-used workflows        │
│  - Agent persona and authorization boundaries       │
└─────────────────────────────────────────────────────┘
            ↕ always loaded (via Agent instructions=)
┌─────────────────────────────────────────────────────┐
│ MCP KB Server (via MCPStdioTool / MCPStreamableHTTP)│
│  Resources: entity schemas, workflow index          │
│  Tools: search_rules, get_workflow, check_eligibility│
│  Internal engine: RAG (vector store + embeddings)   │
│  Storage: git-backed markdown + ChromaDB            │
│  Built with: mcp Python SDK                         │
└─────────────────────────────────────────────────────┘
            ↕ queried on demand (MCP protocol)
┌─────────────────────────────────────────────────────┐
│ MCP Backend Tools Server (or direct function tools) │
│  Tools: create_partner, lookup_member, assign_contact│
│  Built with: @tool decorator + FunctionInvocationCtx│
│  Connects to: ONE MP's existing API/database        │
│  Approval: approval_mode per tool                   │
└─────────────────────────────────────────────────────┘
            ↕ managed by Agent Framework runtime
┌─────────────────────────────────────────────────────┐
│ Microsoft Agent Framework                            │
│  Agent: AnthropicClient (Claude) / FoundryChatClient│
│  Session: AgentSession (state, serialization)       │
│  Middleware: AuditMiddleware, SecurityMiddleware,    │
│             KBStalenessDetector                     │
│  Streaming: agent.run(stream=True)                  │
└─────────────────────────────────────────────────────┘
```

---

## 7. PoC Implementation Path

### Minimal MCP KB Server

For the PoC, the KB server covers only the chosen single workflow deeply rather than ALL of
ONE MP shallowly.

**Phase 1 — Static KB (Week 1)**
- 10-15 KB entries covering the PoC workflow
- 3 MCP tools: `search_business_rules`, `get_workflow_definition`, `check_eligibility`
- 1 MCP resource: entity schema for the target entity
- Storage: SQLite + ChromaDB (zero infrastructure, runs in-process)
- MCP server: Python + `mcp` SDK, connected via `MCPStdioTool`
- Agent: `Agent` with `AnthropicClient`, `@tool`-decorated backend functions, `AuditMiddleware`

**Phase 2 — Dynamic KB (Week 3)**
- Add `resolve_ambiguity` tool to MCP server
- Add contradiction detection on ingestion
- Add `KBStalenessDetector` middleware for observing KB/API divergence
- Add clarification logging → review queue (via `AuditMiddleware`)

**Phase 3 — Coverage Measurement (Week 5)**
- Batch test against 50 real historical user requests
- Coverage dashboard: high/medium/low confidence distribution
- Identify top KB gaps → fill them

### Tech Stack

```
KB Storage:       Git-backed markdown files (human-editable, version-controlled)
Vector Store:     ChromaDB (PoC) → Weaviate or Qdrant (production)
Embeddings:       Voyage AI voyage-3-lite (best quality/cost for domain text)
MCP Server:       Python + mcp SDK (standard MCP protocol)
MCP Connection:   MCPStdioTool (dev) / MCPStreamableHTTPTool (production)
Agent Runtime:    Python + Microsoft Agent Framework (pip install agent-framework)
Model (primary):  Claude Sonnet 4.6 via AnthropicClient (most tasks)
Model (complex):  Claude Opus 4.6 via AnthropicClient (complex disambiguation)
Model (alt):      GPT-4.1 via FoundryChatClient (if Azure-hosted preferred)
Tool Layer:       @tool decorator + Pydantic Field schemas + approval_mode
Middleware:       AuditMiddleware, SecurityMiddleware, KBStalenessDetector
Session:          AgentSession (serializable to Redis/SQLite)
Frontend:         Next.js + Vercel AI SDK (streaming tool call display)
```

### Initial KB Population Strategy

1. **Walk the app**: record a power user going through each step of the PoC workflow — every field, every validation error, every branch
2. **Extract rules**: for each screen/field, write a KB entry: what is it, why is it required, what are valid values, what happens if wrong
3. **Interview edge cases**: "tell me about the 3 most confusing situations you've seen with this workflow"
4. **Write disambiguation entries**: for every term with multiple meanings in the domain, write a glossary entry with examples

---

## 8. Adversarial Self-Challenge

### "Is a KB-guided agent actually better than a well-prompted agent with rich tool descriptions?"

For a **small, stable workflow** (5-10 rules, rarely changing): probably not. Rich tool
descriptions via `@tool(description=...)` + a detailed system prompt will get you 80% of the
way there with far less infrastructure. The MCP KB earns its complexity when:
- The rulebook is too large for the system prompt (> ~50 rules)
- Rules change frequently (monthly or more)
- Rules are highly conditional (eligibility depends on 5+ intersecting conditions)
- You need auditability of *which specific rule* the agent used

For a PoC demonstrating one workflow: start with system prompt encoding. Switch to MCP KB
when you hit the limits.

### "KB becomes a latency bottleneck"

Every request adds a KB round-trip. Mitigations:
- **Cache entity schemas and workflow definitions** per session (store in `AgentSession.state`)
- **Pre-warm**: on session start, load the workflow index as an MCP resource (always in context)
- **Async parallel queries**: the Agent Framework's runtime can fire KB query and read tool calls simultaneously
- **Typical latency**: a ChromaDB semantic search over 1,000 entries takes < 50ms — not a concern at PoC scale

### "Agent becomes KB-dependent and fails on gaps"

The most likely real-world failure mode. Mitigations:
- Agent has an explicit fallback: "I don't have a specific rule for this. Based on similar cases I'd proceed with [X] — does that sound right?"
- KB coverage metric tracked and alerted on
- Human escalation path is always the final fallback, never a dead end

### "KB content quality is terrible"

The most likely *silent* failure mode. Poor KB entries produce confident-but-wrong agent
behavior — worse than uncertainty. Mitigations:
- `certainty_level: "draft"` for any entry not yet validated — agent treats draft entries as medium confidence maximum
- Agent outputs which KB rule it used — reviewers can verify and improve (captured by `AuditMiddleware`)
- Contradiction detection on ingestion prevents mutually exclusive rules from reaching the agent
- `KBStalenessDetector` middleware flags KB/API divergence in production

### "This is just RAG with extra steps"

The MCP layer adds genuine value beyond RAG alone:
1. **Agent-driven queries**: the agent decides *what* to retrieve based on current conversational context, not pre-retrieval before reasoning starts
2. **Structured tool interface**: `check_eligibility` and `resolve_ambiguity` are reasoning operations over the KB that return structured, actionable results — not just document retrieval
3. **Protocol standardization**: the KB server works with any MCP client — the Agent Framework's `MCPStdioTool`/`MCPStreamableHTTPTool`, Claude Desktop, VS Code Copilot, and future agents all benefit
4. **Multi-hop**: the agent can chain KB queries mid-reasoning, which pure RAG cannot do

### "Why not use the Anthropic SDK directly to build the agentic loop?"

For a minimal PoC, the raw Anthropic SDK's agentic loop is ~20 lines. But the Agent Framework adds:
1. **Built-in human-in-the-loop** via `approval_mode` — no custom confirmation code needed
2. **Session management** via `AgentSession` — serializable, resumable conversations
3. **Middleware pipeline** — audit trails, security checks, KB staleness detection without modifying core logic
4. **Native MCP support** — `MCPStdioTool`/`MCPStreamableHTTPTool` connect to the KB server with zero custom client code
5. **Model portability** — switch between Claude (AnthropicClient), GPT (FoundryChatClient), or local models (Ollama) without changing agent logic
6. **Agent composition** — `agent.as_tool()` enables hierarchical architectures; `agent.as_mcp_server()` exposes the agent itself as an MCP tool for other systems

The abstraction cost is near-zero (same ~20 lines for basic setup). The enterprise readiness gain is significant.

---

## Architecture Diagram

```
User Intent
    │
    ▼
┌───────────────────────────────────────────────┐
│  Microsoft Agent Framework                     │
│  Agent(client=AnthropicClient, tools=[...])   │
│                                               │
│  1. Receive user message                      │
│  2. Query MCP KB → classify intent            │
│  3. Retrieve workflow definition              │
│  4. Match context → identify gaps             │
│  5. KB confidence HIGH?  → proceed            │
│     KB confidence LOW?   → clarify            │
│  6. Collect missing inputs (minimal)          │
│  7. Propose action → approval_mode gates      │
│  8. user_input_requests → UI confirmation     │
│  9. Call backend tools                        │
│ 10. AuditMiddleware logs every step           │
│ 11. Report outcome via streaming              │
│                                               │
│  Session: AgentSession (serializable)         │
│  Middleware: [Audit, Security, KBStaleness]   │
└───────────────────────────────────────────────┘
       │ MCP (stdio/HTTP)     │ Function tools
       ▼                      ▼
┌──────────────────┐  ┌──────────────────────────┐
│  MCP KB Server   │  │  Backend Function Tools   │
│  (mcp SDK)       │  │  (@tool decorator)        │
│                  │  │                            │
│  Resources:      │  │  create_partner            │
│  - schemas       │  │  lookup_member             │
│  - wf index      │  │  assign_contact            │
│                  │  │  update_status             │
│  Tools:          │  │  ...                       │
│  - search_rules  │  │                            │
│  - get_workflow  │  │  approval_mode per tool    │
│  - check_eligib  │  │  FunctionInvocationContext │
│  - resolve_amb   │  │  for user identity         │
│                  │  │                            │
│  ↕ stores        │  │  ↕ calls                   │
│                  │  │                            │
│  ChromaDB +      │  │  ONE MP API /              │
│  Git markdown    │  │  Database                  │
└──────────────────┘  └──────────────────────────┘
```

---

## Summary: What This Buys You

| Problem | Without KB | With MCP KB + Agent Framework |
|---|---|---|
| "Add a partner" → which workflow? | Agent guesses or asks user | KB classifies with confidence score |
| Missing required fields | Agent asks field-by-field | KB's `check_eligibility` generates one batched question |
| Business rule changes | Requires redeployment | Update a markdown file, re-embed |
| Agent made a wrong call | Hard to diagnose | AuditMiddleware + KB rule ID in logs |
| Write operations need confirmation | Custom confirmation code | `approval_mode="always_require"` built-in |
| New agent/tool needs the rules | Rewrite the integration | Reuse the same MCP server (protocol-standard) |
| Power user knowledge is siloed | Lost when they leave | Externalized in the KB |
| Need to switch models | Rewrite the agentic loop | Change `AnthropicClient` → `FoundryChatClient` |
| KB rules diverge from reality | Silent failures | `KBStalenessDetector` middleware flags divergence |

The MCP KB transforms the agent from a *prompt-engineered approximation* of ONE MP's logic
into a *reasoning system grounded in explicit, auditable, maintainable business knowledge* —
built on a framework that provides enterprise-grade session management, middleware, and
model-agnostic execution out of the box.
