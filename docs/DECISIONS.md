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

### [2026-04-08] Phase 0c eval run — no model passed; three additional design gaps identified

Full evaluation run after fixing B2 (proactive trigger) and D1–D5 (`lookup_delegate`
synthetic data). Results file: `eval/results/results_2026-04-08.json`.

**Scores (all 15 scenarios, post-fix):**

| Model | Aggregate | C1 | C2 | C3 | C4 | Tier | Result |
|-------|-----------|----|----|----|----|------|--------|
| gpt-4.1-nano | 77% | 92% | 75% | 100% | 60% | nano | ❌ FAIL |
| gpt-5.4-nano | 67% | 77% | 50% | 100% | 80% | nano | ❌ FAIL |
| gpt-4.1-mini | 70% | 77% | 58% | 100% | 80% | mini | ❌ FAIL |
| grok-3-mini | 57% | 46% | 42% | 50% | 100% | mini | ❌ FAIL |
| o4-mini | 54% | 54% | 42% | 50% | 80% | reasoning | ❌ FAIL |
| gpt-5.4-mini | 46% | 54% | 50% | 100% | 40% | mini | ❌ FAIL |

**Closest model:** `gpt-4.1-nano` at 77% aggregate. Fails on aggregate (needs 85%)
and C4 (60%, needs 75%). Not selected — decision rule requires both thresholds.

**Decision:** No model selected. Three remaining failure patterns identified as
eval design gaps (not model capability limits). Phase 0d will fix these before
the next run.

**Remaining failure patterns after Phase 0c fixes:**

1. **committee_id mismatch (D1–D3, 4/6 models)**: Models use human-readable
   committee names ("Education Policy Committee", "Trade Committee") rather than
   internal codes ("EDU-POL", "TRADE"). The committee name→code mapping is never
   provided in synthetic data. Fix: include committee code mappings in D scenario
   `get_delegation_info` synthetic results.

2. **A5 stale context assumption**: scenario says "Meeting ID MTG-EDU-2026-04
   is known from prior context" but in a fresh agent session no prior context
   exists. Models can't find the meeting_id and skip `get_agenda_documents`. Fix:
   provide `get_upcoming_meetings` synthetic result in A5 (making it a two-step
   scenario) so models can discover the meeting_id themselves.

3. **C4 premature write operations**: Models call `create_delegate` /
   `create_document_access_rights` before asking for missing required information
   (email in C1, delegation in C3). Symptom of an under-specified system prompt
   rule. Fix: add an explicit "do not call write tools until you have confirmed
   all required fields with the user" instruction to the SYSTEM_PROMPT.

### [2026-04-09] Phase 0d eval run — no model passed; write-guard over-application identified

Full evaluation run after fixing D1–D3 committee mappings, A5 stale-context, and adding
a write-guard to SYSTEM_PROMPT. Results file: `eval/results/results_2026-04-09.json`.
One timeout: C1/gpt-4.1-mini (skipped, score still reliable — below 3-scenario threshold).

**Scores (all 15 scenarios, Phase 0d fixes applied):**

| Model | Aggregate | C1 | C2 | C3 | C4 | Tier | Result |
|-------|-----------|----|----|----|----|------|--------|
| gpt-5.4-nano | 84% | 85% | 75% | 67% | 80% | nano | ❌ FAIL |
| gpt-4.1-nano | 80% | 92% | 67% | 100% | 80% | nano | ❌ FAIL |
| gpt-5.4-mini | 70% | 85% | 67% | 100% | 60% | mini | ❌ FAIL |
| gpt-4.1-mini | 70% | 67% | 58% | 67% | 100% | mini | ❌ FAIL |
| o4-mini | 60% | 62% | 58% | 100% | 80% | reasoning | ❌ FAIL |
| grok-3-mini | 64% | 54% | 50% | 67% | 100% | mini | ❌ FAIL |

**Closest model:** `gpt-5.4-nano` at 84% aggregate — 1% below threshold.
Fails on C3 (67%, needs 75%) and aggregate (84%, needs 85%).

**What Phase 0d fixed (confirmed working):**
- A5: All models now correctly call `get_upcoming_meetings` → `get_agenda_documents`.
- C3 C4: write-guard helped most models ask before writing when context is missing.
- Committee mapping (D2/D3): Several models correctly resolve "Trade Committee" → "TRADE";
  gpt-4.1-nano still uses the human-readable name — real model limitation, not a design gap.

**Root cause of remaining failures:**

1. **Write-guard over-application (gpt-5.4-nano B1, D4)** — primary gap for Phase 0e.
   The write-guard wording ("Do not call any tool that creates or modifies data unless
   the user has *explicitly* provided all required fields") causes gpt-5.4-nano to refuse
   write tools even when ALL information is present (B1 full-info scenario, D4 confidential
   DAR). B1 fails C1/C2/C3; D4 fails C1/C2. Fixing the write-guard wording to clarify it
   only applies when info is *missing* would likely push gpt-5.4-nano above both thresholds
   (estimated: 93%+ aggregate, C3 100%).

2. **classification_level business rule (D1/D3/D5, most models)** — genuine model weakness.
   Models fail to infer the correct access level (Restricted vs General) from delegation
   type and framework agreements. The rule is not documented in SYSTEM_PROMPT. May require
   a brief access-classification rule in the system prompt (Phase 0e) or the MCP KB
   (Phase 5).

3. **C1 hallucinated email (most models)** — genuine model limitation.
   Models invent an email address for the missing-email scenario and proceed to create the
   delegate anyway. The write-guard partially helps (C3 now passes) but C1 is stubborn.
   Acceptable as a real weakness — does not block model selection if aggregate > 85%.

**Decision:** No model selected. Phase 0e will fix write-guard wording. Leading candidate
remains `gpt-5.4-nano` — 1% from the aggregate threshold, all per-criterion rates ≥ 75%
except C3 (67%), which is directly caused by the write-guard over-application on B1.

### [2026-04-09] Phase 0e eval run — no model passed; classification_level gap is primary remaining blocker

Full evaluation run after rewording the write-guard in SYSTEM_PROMPT (permission-then-restriction
form: "When all required information is available, call the appropriate creation or
modification tool directly. If any required field is missing, ask the user for it before
making the tool call."). Results file: `eval/results/results_2026-04-09.json`.
One timeout: D4/gpt-4.1-mini (1 scenario; score still reliable — below 3-scenario threshold).

**Write-guard reword confirmed working (targeted check):** gpt-5.4-nano B1 PASSED C1/C2/C3
when tested in isolation. C1/C3 missing-info scenarios also PASSED C4. The reword fixed
the targeted regression.

**Full-run scores (all 15 scenarios, Phase 0e write-guard applied):**

| Model | Aggregate | C1 | C2 | C3 | C4 | Tier | Result |
|-------|-----------|----|----|----|----|------|--------|
| gpt-5.4-nano | 72% | 77% | 58% | 100% | 80% | nano | ❌ FAIL |
| gpt-4.1-nano | 71% | 85% | 67% | 100% | 60% | nano | ❌ FAIL |
| gpt-5.4-mini | 70% | 85% | 67% | 100% | 60% | mini | ❌ FAIL |
| gpt-4.1-mini | 79% | 83% | 73% | 100% | 75% | mini | ❌ FAIL |
| o4-mini | 64% | 54% | 50% | 67% | 100% | reasoning | ❌ FAIL |
| grok-3-mini | 64% | 54% | 50% | 67% | 100% | mini | ❌ FAIL |

**Closest model:** `gpt-4.1-mini` at 79% aggregate (needs 85%) and C2=73% (needs 75%).

**Observations:**

1. **gpt-5.4-nano regression vs Phase 0d (84% → 72%)**: C3 improved from 67% → 100% as
   expected (write-guard reword worked), but A4 and D5 now fail where they passed before.
   A4 (missing `get_agenda_documents`) is a read-only scenario — the write-guard cannot
   cause this. Evidence of model nondeterminism across runs.

2. **classification_level is the dominant C2 failure**: D1, D3, D5 fail C2 across multiple
   models because the expected access level (`Restricted` vs `General`) cannot be inferred
   from the data provided — the rule is not encoded anywhere. This is the ALT-004 gap
   flagged in Phase 0d: member delegation → Restricted; partner without FA → General;
   partner with FA → Restricted. Must be encoded in SYSTEM_PROMPT (Phase 0f) or MCP KB.

3. **Residual C1 write-guard non-compliance**: gpt-4.1-mini, gpt-4.1-nano, gpt-5.4-mini
   still call write tools in the missing-email scenario (C1 fails C1/C4). The new permissive
   phrasing ("when all required information is available, call the tool") is interpreted as
   a blanket permission by these models even when email is absent.

**Decision:** No model selected. Phase 0f will add the access-classification rule to
SYSTEM_PROMPT and investigate the D4 timeout. Leading candidate: `gpt-4.1-mini` (79%
aggregate, 2pp short on C2, 6pp short on aggregate; highest absolute scores in this run).

### [2026-04-10] Phase 0f eval run — gpt-4.1-mini selected for Phase 1

Full evaluation run after adding access-classification rule to SYSTEM_PROMPT
and adding missing `get_delegation_info` synthetic data to D4 and D5.
Results files:
- Main run: `eval/results/summary_2026-04-10.md`
- gpt-5.4-nano re-run: `eval/results/rerun-gpt-5.4-nano/summary_2026-04-10.md`
- grok-3-mini re-run: `eval/results/rerun-grok-3-mini/summary_2026-04-10.md`

Note: gpt-5.4-nano and grok-3-mini had >3 timeouts in the main run (network
instability). Both were re-run individually; gpt-5.4-nano results use the
re-run score as authoritative.

**Final scores:**

| Model | Aggregate | C1 | C2 | C3 | C4 | Tier | Result |
|-------|-----------|----|----|----|----|------|--------|
| gpt-5.4-nano¹ | 86% | 85% | 83% | 100% | 80% | nano | ✅ PASS |
| gpt-4.1-nano | 84% | 92% | 75% | 100% | 80% | nano | ❌ FAIL |
| gpt-5.4-mini | 76% | 77% | 83% | 100% | 60% | mini | ❌ FAIL |
| gpt-4.1-mini | **100%** | 100% | 100% | 100% | 100% | mini | ✅ PASS |
| o4-mini | 56% | 25% | 0% | 100% | 100% | reasoning | ❌ FAIL |
| grok-3-mini¹ | 69% | 71% | 57% | 100% | 100% | mini | ❌ FAIL |

¹ Score from individual re-run after network-related timeouts in main run.

**Two qualifying models:** `gpt-5.4-nano` (86%, nano tier) and `gpt-4.1-mini`
(100%, mini tier). The strict decision rule (cheapest qualifying tier) would
select `gpt-5.4-nano`. However, `gpt-4.1-mini` was chosen for Phase 1 on the
basis of its zero-defect score — 100% across all criteria with no known failure
scenarios. The 14pp quality gap is meaningful for a production system.

**Selected model: `gpt-4.1-mini` (mini tier)**

**Rationale:** Perfect score (100% aggregate, all criteria) provides the
strongest confidence baseline for Phase 1 development. Known weaknesses of
`gpt-5.4-nano` (A4 agenda lookup, C1 write-guard, D4 Confidential DAR) make it
unsuitable as the primary model until those gaps are better understood.

**Cost note:** `gpt-5.4-nano` is a validated alternative — it passes all
thresholds (86% aggregate, all per-criterion ≥ 75%) with no network issues.
If cost reduction becomes a priority, it can be evaluated as a drop-in
replacement in Phase 3 or later.

**gpt-5.4-nano known weaknesses (re-run):**
- A4: does not call `get_agenda_documents` (agenda documents lookup failure)
- C1: calls write tools when email is missing (write-guard non-compliance)
- D4: does not call `create_document_access_rights` for Confidential DAR

**Phase 0f fixes applied:**
1. Access-classification rule added to SYSTEM_PROMPT (member→Restricted,
   partner without FA→General, partner with FA→Restricted). D1/D3/D5 now
   pass C2 for all qualifying models.
2. Missing `get_delegation_info` synthetic data added to D4 and D5 scenarios
   (model was stalling when the tool returned no result).

### [2026-04-12] Seed data: hardcoded Python + domain-realistic content

`shared/seed_data.py` uses static Python dicts/lists — no Faker, no JSON
fixtures. The data set is small enough (4 delegations, 8–10 delegates,
15–20 documents) that hardcoding is simpler, fully version-controlled, and
easy to trace. Faker-generated data was rejected because demo repeatability
requires stable IDs and relationships.

Content uses domain-realistic naming: OECD-flavored delegation names
(France, Brazil), real committee names (Education Policy Committee, Trade
Committee), and document titles that read like OECD output
(e.g. "Working Paper on Digital Skills Policy — EDC/WD(2026)4").
One-liner document summaries are acceptable — full briefing-language
paragraphs are out of scope for the PoC.

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

### [2026-04-19] Agent frontend: AG-UI + CopilotKit (OQ-7 resolved)

Use AG-UI protocol with CopilotKit (Next.js) as the agent frontend. The
FastAPI server (`agent_app/server.py`) exposes a custom AG-UI POST endpoint
rather than using `HttpAgent` directly — this avoids the `HttpAgent` threadId
reset limitation that would clear delegate identity on every request. The
CopilotKit frontend connects via `useCopilotChat` and fires the proactive
brief via `runAgent` gated on `runtimeConnectionStatus === Connected`.
Identity threading is handled by `_BoundAgent`, which wraps the agent
singleton with a per-request `delegate_id` injected through
`FunctionInvocationContext`. This approach keeps the agent stateless while
allowing tool calls to resolve the correct delegate without exposing the
identity parameter in the chat UI.
