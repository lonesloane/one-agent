# Backlog

## Phase 0 — Model Exploration
> Validate which model provides minimum reasoning quality for tool selection

### Phase 0a — Harness Infrastructure ✓ (2026-04-06)
- [x] Set up evaluation harness (tool call recorder, C1 scoring, harness runner)
- [x] Implement 6 stub tools with `@tool` decorator and `SCENARIO_DATA` injection
- [x] Implement `RecorderMiddleware` capturing tool name, args, result
- [x] Define 3 representative scenarios (A1 single-tool, B1 multi-step, C1 missing-info)
- [x] Implement C1 evaluator; C2-C4 stubbed for Phase 0b
- [x] **TASK-026**: run `python -m eval.harness` against live `gpt-4.1-mini` via Azure AI Foundry — completed 2026-04-06. A1 PASS, B1 PASS (after adding delegate-creation sequence rule to system prompt), C1 FAIL (genuine signal: model invoked write tools despite missing email, and hallucinated `Confidential` access level for a member delegate). C1 failure is valid data for C2/C4 evaluators in Phase 0b.

### Phase 0b — Full Evaluation Suite ✓ (2026-04-08)
- [x] Define remaining 12 scenarios (A2-A5, B2, C2-C3, D1-D5) in `eval/scenarios/scenarios.json`
- [x] Implement C2 (schema-valid args), C3 (sequencing), C4 (asks vs invents) evaluators
- [x] Implement score aggregation, CLI (`--all`, `--model`, `--category`, `--output`), JSON + Markdown output
- [x] Run full evaluation: all 6 models × 15 scenarios (2026-04-08)
- [x] **Finding**: No model passed. Two eval design gaps identified (B2 proactive trigger missing; D1-D5 lack `lookup_delegate` synthetic data). Excluding gaps: gpt-5.4-nano and gpt-4.1-mini both score 89%. See `docs/DECISIONS.md`.

### Phase 0c — Eval Design Fix & Final Model Selection ✓ (2026-04-08)
- [x] Fix B2: add proactive login instruction to SYSTEM_PROMPT in `eval/harness.py`
- [x] Fix D1-D5: add `lookup_delegate` synthetic results; discovered secondary gap
  (`get_delegation_info` also missing for D1-D3) and fixed that too
- [x] Re-run `python -m eval.harness --all --output eval/results/`
- [x] Apply decision rule — no model passed (closest: gpt-4.1-nano at 77%)
- [x] Update `docs/DECISIONS.md` — three new design gaps documented (Phase 0d)

### Phase 0d — Remaining Eval Design Gaps ✓ (2026-04-09) — [plan](../plan/feature-phase0d-eval-fix-and-model-selection-1.md)

- [x] Fix committee_id mapping (D1–D3): added `committees` array to
  `get_delegation_info` synthetic results with name→code mappings.
- [x] Fix A5 stale context: replaced stale system_context with
  `get_upcoming_meetings` synthetic result; A5 now a two-step scenario.
- [x] Fix C4 write-before-asking: added write-guard to SYSTEM_PROMPT (two
  iterations). C3 scenario now passes C4 for most models.
- [x] Re-run `python -m eval.harness --all` — no model passed.
  Closest: gpt-5.4-nano at 84% aggregate. See `docs/DECISIONS.md`.

### Phase 0e — Write-Guard Wording Fix & Final Model Selection (planned)
> Single remaining issue: write-guard over-application causes gpt-5.4-nano
> to refuse write tools even when all required info is present (B1, D4 regress).
> Fixing the wording is expected to push gpt-5.4-nano above both thresholds.

**Leading candidate:** `gpt-5.4-nano` — 84% aggregate, C3=67%.
Both failures are write-guard regressions on B1/D4. Estimated post-fix: ~93%.

- [ ] Reword write-guard so it only applies when info is *missing*, not as a
  blanket prohibition. Candidate: "If any required field is missing, ask the
  user before calling a creation or modification tool. When all required
  information is available, proceed without asking."
- [ ] Verify B1 passes (all models call write tools when all info is present).
- [ ] Verify C1/C3 still pass C4 (write-guard still catches missing-info cases).
- [ ] Re-run `python -m eval.harness --all`.
- [ ] Apply decision rule and update `docs/DECISIONS.md`.

## Phase 1 — Shared Data Layer + Classical App (Read Flows)
> Foundation: database, business rules, seed data, classical app read screens

- [ ] Implement `shared/database.py` — SQLAlchemy models (Delegation, Delegate, Committee, Document, DAR, Meeting, FrameworkAgreement, MeetingAgendaItem)
- [ ] Implement `shared/business_rules.py` — `compute_default_access_level`, `determine_approval_route`, `get_new_documents_since`
- [ ] Implement `shared/seed_data.py` — populate test data covering all demo scenarios
- [ ] Initialize `one_agent.db` with seed data
- [ ] Classical app: Dashboard (Screen 1)
- [ ] Classical app: My Committees list (Screen 2)
- [ ] Classical app: Committee detail (Screen 3)
- [ ] Classical app: Upcoming Meetings list (Screen 4)
- [ ] Classical app: Meeting detail + agenda documents (Screen 5)
- [ ] Classical app: Document detail (Screen 6)

## Phase 2 — Classical App (Write Flows)
> Delegate creation wizard — the 8-screen contrast tool

- [ ] Classical app: Delegation list (Screen 2)
- [ ] Classical app: Delegation detail with delegate list (Screen 3)
- [ ] Classical app: Add Delegate Step 1 — Personal info (Screen 4)
- [ ] Classical app: Add Delegate Step 2 — Committee selection (Screen 5)
- [ ] Classical app: Add Delegate Step 3 — Document Access Rights (Screen 6)
- [ ] Classical app: Add Delegate Step 4 — Review & Submit (Screen 7)
- [ ] Classical app: Confirmation (Screen 8)
- [ ] Wire up actual delegate + DAR creation using shared business rules

## Phase 3 — Agent App (Read Agent — UC1)
> "The Proactive Read Agent" — meeting brief on session start

- [ ] Implement agent tools: `get_delegation_info`, `lookup_delegate`, `get_upcoming_meetings`, `get_agenda_documents` (thin wrappers over shared layer)
- [ ] Write system prompt encoding ONE MP domain and behavioral rules
- [ ] Set up `Agent` with `FoundryChatClient` + read tools + `AuditMiddleware`
- [ ] Implement proactive meeting brief: on session start, greet with upcoming meetings + new documents
- [ ] Implement streaming for real-time UI feedback
- [ ] Verify document visibility rules function correctly

## Phase 4 — Agent App (Write Agent — UC2)
> "The Write Agent with Reasoning" — delegate creation with DAR

- [ ] Implement write tools: `create_delegate`, `create_document_access_rights` (with `approval_mode="always_require"`)
- [ ] Agent reasons through DAR business rules (membership type -> access level -> approval routing)
- [ ] Human-in-the-loop confirmation flow via `user_input_requests`
- [ ] Audit trail captures full chain of reasoning and approvals
- [ ] Test: member delegate creation (General + Restricted access)
- [ ] Test: partner delegate creation (General only)
- [ ] Test: partner + Framework Agreement (elevated access)
- [ ] Test: Confidential access request (secretariat approval)
- [ ] Test: retroactive access request (secretariat approval)

## Phase 5 — MCP Knowledge Base
> Business rules as a queryable MCP server

- [ ] Write 10-15 KB entries (markdown with structured frontmatter) covering DAR rules, workflows, edge cases
- [ ] Set up ChromaDB vector store with embeddings
- [ ] Implement MCP server: `search_business_rules`, `get_workflow_definition`, `check_eligibility`
- [ ] Connect to agent via `MCPStdioTool`
- [ ] Add `resolve_ambiguity` tool
- [ ] Add `KBStalenessDetector` middleware
- [ ] Validate agent uses KB for tool selection on UC2

## Phase 6 — Trust Calibration + Demo
> Combine use cases, tune approval policy, prepare stakeholder demo

- [ ] Tune approval policy: auto-approve reads + General DAR for members; confirm Restricted/Confidential
- [ ] Combine UC1 + UC2 in single agent session
- [ ] Write side-by-side demo script
- [ ] Run demo: classical app (6 screens) vs agent (instant brief) for UC1
- [ ] Run demo: classical app (8 screens) vs agent (3 turns) for UC2
- [ ] Document findings and model performance observations
