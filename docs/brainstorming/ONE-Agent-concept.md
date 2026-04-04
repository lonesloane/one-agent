# ONE Agent: Concept Analysis and Architecture

> Replacing the "ONE MP" (ONE for Members and Partners) form-based web application with an agentic application — "ONE Agent".

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

### 2. Agent Orchestration Layer
The reasoning core. Recommended pattern: **orchestrator-worker** model.
- An orchestrator agent receives user intent, decomposes it into sub-tasks, and directs workers
- For a PoC: a single agent with a rich tool set is sufficient — multi-agent adds complexity not justified at this stage

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
Every form submission becomes a typed tool with:
- A precise JSON schema for inputs
- Execution logic that calls the existing backend/API
- Return values shaped for agent consumption (high-signal, not raw API responses)
- Error semantics that give the agent enough context to recover or escalate

**Tool design principles:**
- Consolidate related operations (one `create_member` with optional params, not multiple variants)
- Return semantic identifiers, not opaque IDs
- Include validation logic in the tool, not the prompt — the tool is the authority
- Tool descriptions act as contracts: if it can't do X, say so explicitly

### 4. State Management
Three kinds of state:

- **Conversational state**: The dialogue history (Claude messages array, per session)
- **Task state**: Where is the agent in a multi-step process? Persist intent + gathered inputs + completed steps so conversations can resume
- **Domain state**: The actual data in ONE MP's backend. Agent must be idempotent-aware: check before creating

### 5. Authorization and Trust Layer
A permission model for agent actions:

| Level | Operations | Behavior |
|---|---|---|
| Auto-approve | Reads, lookups, searches | Agent executes without asking |
| Confirm before execute | Mutations that can be undone | Agent proposes, user confirms |
| Hard approval gate | Irreversible / high-consequence actions | Explicit confirmation with visible preview |
| Prohibited | Defined forbidden actions | Agent refuses regardless of instruction |

For a PoC: simple confirm-before-write is sufficient.

### 6. Audit Trail
Richer than what form-based apps produce:
- Who initiated the action (user identity)
- What the agent was asked to do (the original intent)
- What tools were called, in what order, with what arguments
- What the final state change was
- Timestamp of each step

The *why* is captured alongside the *what* — a significant improvement over form submission logs.

### 7. Identity and Auth Integration
- User's identity/session token must be threaded through every tool call
- Tools must enforce the same RBAC/permissions as the existing app
- The agent should NOT have super-user access — it acts as the authenticated user

### 8. Interruption and Recovery
- Tool errors return structured messages the agent can reason about and relay
- Users can cancel at any point ("stop", "cancel")
- No irreversible actions without explicit confirmation
- Partial task state is persisted — nothing is silently lost

---

## The Hardest Non-Obvious Problems

### Problem 1: The Confirmation UX Trap
If every write requires confirmation, you risk recreating the click-through tedium of the form app — but worse, because the interaction is unpredictable.

**Solution**: Progressive trust. Auto-approve low-risk operations; only confirm consequential, irreversible, or high-value mutations.

### Problem 2: Partial Completion and Data Integrity
A form is a transaction boundary. An agent workflow spanning 5 tool calls is not. If the 4th call fails, what state is the system in?

**Solutions**: Transactional tooling (all-or-nothing), compensating actions (the agent knows how to undo), or explicit partial state with a "resume" capability.

### Problem 3: Intent Ambiguity in High-Stakes Domain
"Add the new partner" might mean 15 different things depending on ONE MP's domain model.

**Solution**: Encode domain specificity in tool names and descriptions — `create_service_partner`, `create_reseller_partner` is clearer than one `create_partner` with a `type` field. The tools themselves encode the domain.

### Problem 4: The "What Did the Agent Do?" UX Problem
Users in a form app always know what happened. In an agentic app, the agent might execute 7 tool calls and produce a 3-sentence summary.

**Solution**: A transparency layer — real-time streaming of tool calls as they happen ("Looking up Acme Corp... Not found. Creating new partner record..."). Streaming solves both transparency and the "nothing is happening" UX problem simultaneously.

### Problem 5: Regulatory and Compliance Constraints
"Members and Partners" implies regulated data, fiduciary relationships, and potentially real financial or legal consequences:
- GDPR/data protection obligations
- Contract law implications (agent-initiated actions may constitute legal commitments)
- Financial regulations (if ONE MP handles payments or financial instruments)
- Mandatory audit requirements

The audit trail is not optional in a regulated context — it is a compliance requirement.

### Problem 6: Model Reliability and Hallucination in Tool Calls
The agent will occasionally call a tool with an incorrect argument or misinterpret intent.

**Mitigations**:
- Strict tool schemas (use `strict: true` for schema enforcement)
- Tool call validation at the execution layer before any side effects
- Test harness running representative scenarios
- Confirmation before writes (solves most "wrong action" cases)
- Claude Opus 4.6 for complex tool selection

---

## PoC Strategy: The Minimal Compelling Slice

**Do not replicate all of ONE MP.** Pick ONE workflow that:
- Has 3–7 form screens in the current app (so the compression is visible)
- Has conditional logic (so agent reasoning is genuinely valuable)
- Is frequently performed (so stakeholders recognize the value)
- Is commonly the most *painful* workflow (best candidate for demonstrating improvement)

### Three Phases, Each a Standalone Demo

**Phase 1 — "The Read Agent" (Weeks 1–2)**
The agent can look up, search, and summarize information from ONE MP's data. No writes. Proves: conversational interface works, tools integrate with the backend, agent can reason over domain data. Zero risk of data corruption.

**Phase 2 — "The Write Agent with Full Confirmation" (Weeks 3–4)**
Add write tools with mandatory confirmation before every mutation. Proves: full workflow works end-to-end, confirmation UX is usable, audit trail is correct.

**Phase 3 — "The Trust-Calibrated Agent" (Weeks 5–6)**
Tune the confirmation policy: auto-approve low-risk operations, confirm only high-risk ones. Demonstrates the production-ready UX. This is the stakeholder demo.

Each phase is a shippable, demonstrable artifact. Stakeholders can engage at each phase.

---

## Recommended Architecture

### Stack

| Layer | Technology |
|---|---|
| Backend / Agent Runtime | Python + Anthropic SDK (direct — no framework needed at PoC scale) |
| Model | Claude Sonnet 4.6 (most tasks); Claude Opus 4.6 (complex tool selection) |
| Frontend | Next.js + Vercel AI SDK (streaming, tool call display, conversation state) |
| Session state / Audit log | Redis or SQLite |
| Tool execution | Typed Python functions with Pydantic schemas |

**No LangChain / LangGraph / CrewAI at PoC scale.** The Anthropic SDK's agentic loop is ~20 lines of code. Add a framework only when you have multiple agents with complex state transitions — i.e., after the PoC succeeds.

**MCP (Model Context Protocol)**: Relevant when scaling to many integrations. Hand-crafted tools are simpler for a PoC.

### Core Agentic Loop (Sketch)

```python
async def run_agent(user_message: str, session: Session) -> AsyncGenerator:
    session.messages.append({"role": "user", "content": user_message})

    while True:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            system=SYSTEM_PROMPT,       # encodes ONE MP domain, user permissions, behavioral rules
            messages=session.messages,
            tools=ALL_TOOLS,            # typed tool definitions
            max_tokens=4096,
        )

        session.messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            yield response.content      # final answer
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    yield ToolCallEvent(block.name, block.input)   # stream to UI

                    if is_write_operation(block.name):
                        confirmed = await request_user_confirmation(block)
                        if not confirmed:
                            tool_results.append(tool_result(block.id, "User declined"))
                            continue

                    result = await execute_tool(block.name, block.input, session.user)
                    audit_log.record(session.user, block.name, block.input, result)
                    tool_results.append(tool_result(block.id, result))

            session.messages.append({"role": "user", "content": tool_results})
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
Legitimate concern. Claude Opus 4.6 is highly reliable but not infallible. Confirmation gates and strict schemas mitigate this. If the domain requires 100% accuracy, the PoC must be honest about error rates and have clear correction workflows.

**"This just moves the complexity into the system prompt"**
True. Business logic that was in the UI now lives in the system prompt and tool descriptions. This is harder to test and maintain than a UI flowchart. Significant testing discipline required.

**"Users don't want to talk to an agent, they want to click"**
Some users will prefer the predictability of forms. Agentic is better for high-variability, multi-step, expert-knowledge-requiring tasks — not for simple, repetitive, standardized operations. Hybrid is probably the right long-term answer.

---

## Bottom Line

The technology exists today to build this convincingly. The hard problems are not the AI — they are the **trust architecture, confirmation UX, audit trail, and domain encoding in the tool layer**.

The most valuable next step is understanding ONE MP's domain model and identifying the single most painful multi-step workflow to use as the PoC target.
