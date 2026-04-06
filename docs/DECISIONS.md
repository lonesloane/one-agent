# Decision Log

Format: `[YYYY-MM-DD] Decision — rationale`

---

### [2025-04] Microsoft Agent Framework over LangChain/CrewAI/raw SDK

Use the Microsoft Agent Framework (Python) as the agent runtime. It provides built-in human-in-the-loop (`approval_mode`), session management (`AgentSession`), middleware pipeline, native MCP support, and model-agnostic execution. Near-zero abstraction cost over a raw SDK loop, with significant enterprise readiness. No LangChain, LangGraph, or CrewAI.

### [2025-04] Dual-demo architecture (classical + agent)

Ship two apps sharing the same SQLite database and business rules. The classical Flask app is a contrast tool — it makes the agent's value self-evident by showing the same tasks completed in both paradigms. Same data, same rules, different experience.

### [2025-04] Azure OpenAI models for PoC via Azure AI Foundry

PoC runs on VS Enterprise subscription credits, accessed exclusively via `FoundryChatClient` (Azure AI Foundry). Phase 0 evaluates six candidates: `gpt-5.4-nano` and `gpt-4.1-nano` (cheapest, baselines), `gpt-5.4-mini` and `gpt-4.1-mini` (low-cost, primary candidates), `o4-mini` (reasoning model), and `grok-3-mini` (alternative). Decision rule: select cheapest model passing ≥ 85% aggregate and ≥ 75% per criterion across the 15-prompt eval suite. Claude deferred post-PoC due to budget. No local Ollama — all evaluation runs through Foundry.

### [2025-04] MCP-exposed business knowledge base (not system prompt, not RAG-only)

Business rules live in git-backed markdown files with structured frontmatter, embedded into ChromaDB, and exposed via an MCP server. The agent queries the KB at runtime (agent-driven, multi-hop capable) rather than having rules pre-loaded into the system prompt. RAG is the engine inside; MCP is the interface. Start with system prompt encoding for Phase 1 (read-only), switch to MCP KB for Phase 2 (write agent with DAR reasoning).

### [2025-04] Shared data layer with business rules as Python functions

Business rules (DAR computation, approval routing) are Python functions in `shared/business_rules.py`, not embedded in prompts or templates. All three consumers (classical app, agent tools, MCP server) call the same functions. Single source of truth.

### [2025-04] Two PoC use cases chosen

UC1 (Proactive Meeting Brief): demonstrates what agents can do that forms cannot — proactive intelligence. UC2 (Delegate Creation with DAR): demonstrates multi-step workflow compression and business rule reasoning. Together they cover read-only + write, proactive + reactive.

### [2025-04] SQLite for PoC database

Single-file database, zero infrastructure. Shared between both apps. Sufficient for demo scale (6-8 delegations, 30-50 delegates, 40-60 documents).

### [2025-04] Human-in-the-loop via approval_mode, not custom code

Write tools use `approval_mode="always_require"` — the Agent Framework handles the confirmation flow natively via `user_input_requests`. No custom confirmation UI code needed at the tool layer.
