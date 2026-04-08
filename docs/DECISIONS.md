# Decision Log

Format: `[YYYY-MM-DD] Decision — rationale`

---

### [2025-04] Microsoft Agent Framework over LangChain/CrewAI/raw SDK

Use the Microsoft Agent Framework (Python) as the agent runtime. It provides built-in human-in-the-loop (`approval_mode`), session management (`AgentSession`), middleware pipeline, native MCP support, and model-agnostic execution. Near-zero abstraction cost over a raw SDK loop, with significant enterprise readiness. No LangChain, LangGraph, or CrewAI.

### [2025-04] Dual-demo architecture (classical + agent)

Ship two apps sharing the same SQLite database and business rules. The classical Flask app is a contrast tool — it makes the agent's value self-evident by showing the same tasks completed in both paradigms. Same data, same rules, different experience.

### [2025-04] Azure OpenAI models for PoC via Azure AI Foundry

PoC runs on VS Enterprise subscription credits, accessed exclusively via `FoundryChatClient` (Azure AI Foundry). Phase 0 evaluates six candidates: `gpt-5.4-nano` and `gpt-4.1-nano` (cheapest, baselines), `gpt-5.4-mini` and `gpt-4.1-mini` (low-cost, primary candidates), `o4-mini` (reasoning model), and `grok-3-mini` (alternative). Decision rule: select cheapest model passing ≥ 85% aggregate and ≥ 75% per criterion across the 15-prompt eval suite. Claude deferred post-PoC due to budget. No local Ollama — all evaluation runs through Foundry.

### [2026-04-08] Phase 0b eval run — no model passed; two eval design gaps identified

Full evaluation run across all 6 models × 15 scenarios. Results file:
`eval/results/results_2026-04-08.json`.

**Raw scores (all 15 scenarios):**
| Model | Aggregate | C1 | C2 | C3 | C4 | Result |
|-------|-----------|----|----|----|----|--------|
| gpt-5.4-nano | 59% | 54% | 50% | 50% | 80% | ❌ FAIL |
| gpt-4.1-nano | 60% | 77% | 50% | 50% | 60% | ❌ FAIL |
| gpt-5.4-mini | 42% | 46% | 33% | 50% | 60% | ❌ FAIL |
| gpt-4.1-mini | 56% | 46% | 50% | 50% | 80% | ❌ FAIL |
| o4-mini | 44% | 38% | 33% | 0% | 80% | ❌ FAIL |
| grok-3-mini | 57% | 46% | 42% | 0% | 100% | ❌ FAIL |

**Root cause — two eval design gaps, not model capability:**

1. **B2 (proactive login flow) — fails 6/6 models.** The system prompt
   contains no instruction to proactively call tools when a user logs in.
   Models correctly respond "Hello, how can I help?" Fix: add an explicit
   proactive-brief trigger to the system prompt and/or system_context.

2. **D1–D5 (DAR creation) — fails 5–6/6 models.** The system prompt
   instructs the agent to call `lookup_delegate` first before any write
   operation. D scenarios provide no `lookup_delegate` synthetic result,
   so the model stalls after finding nothing. Fix: add `lookup_delegate`
   synthetic results to D scenarios so the model can verify the delegate
   and proceed to `create_document_access_rights`.

**Scores excluding design-gap scenarios (9 non-gap scenarios):**
| Model | Score | Tier |
|-------|-------|------|
| gpt-5.4-nano | **89%** | nano |
| gpt-4.1-mini | **89%** | mini |
| grok-3-mini | 83% | mini |
| o4-mini | 67% | reasoning |
| gpt-4.1-nano | 72% | nano |
| gpt-5.4-mini | 61% | mini |

**Decision:** No model selected yet. Fix the two eval design gaps, re-run,
and apply the decision rule. Tentative leading candidates: `gpt-5.4-nano`
(cheapest, 89% on valid scenarios) and `gpt-4.1-mini` (89%, more capable
on C1). Genuine model weaknesses noted: C1 failures (models call write
tools when email is missing — 4/6 models), B1 failures on grok-3-mini and
o4-mini (incomplete delegate-creation sequence).

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
