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

### Phase 0e — Write-Guard Wording Fix ✓ (2026-04-09) — [plan](../plan/feature-phase0e-eval-fix-and-model-selection-1.md)

- [x] Reword write-guard: permission-then-restriction form (SYSTEM_PROMPT lines 44–47).
- [x] Targeted check: gpt-5.4-nano B1 PASSED C1/C2/C3; C1/C3 still pass C4. Fix confirmed.
- [x] Full run: no model passed (closest: gpt-4.1-mini at 79%). See `docs/DECISIONS.md`.
- [x] Root cause of remaining gaps: classification_level rule not encoded (D-category);
  model nondeterminism in gpt-5.4-nano (A4, D5); residual write-guard non-compliance (C1).

### Phase 0f — Access-Classification Rule & Final Model Selection ✓ (2026-04-10) — [plan](../plan/feature-phase0f-eval-fix-and-model-selection-1.md)

- [x] Add access-classification rule to SYSTEM_PROMPT (member→Restricted,
  partner without FA→General, partner with FA→Restricted). D1/D3/D5 now pass C2.
- [x] Fix D4 and D5: missing `get_delegation_info` synthetic data added;
  model was stalling without a tool result to proceed on.
- [x] Verify unit tests (40/40 pass), B1 write-guard unaffected, C1/C3 guard intact.
- [x] Full run (2026-04-10): gpt-5.4-nano and grok-3-mini had network timeouts;
  both re-run individually. gpt-5.4-nano qualifies at 86%; grok-3-mini fails at 69%.
- [x] **Selected model: `gpt-4.1-mini`** — 100% aggregate, all criteria 100%.
  `gpt-5.4-nano` (86%, all criteria pass) noted as a validated cost-saving alternative.
  See `docs/DECISIONS.md` for full rationale.
- [x] Phase 1 can begin with `gpt-4.1-mini`.

## Phase 1 — Shared Data Layer + Classical App (Read Flows) ✓ (2026-04-12) — [PRD](prd-phase1-shared-layer-and-classical-read.md)
> Foundation: database, business rules, seed data, classical app read screens

### Phase 1A — Shared Data Layer ✓ (2026-04-12)
- [x] Implement `shared/database.py` — SQLAlchemy models (Delegation, Delegate, Committee, Document, DAR, Meeting, FrameworkAgreement, MeetingAgendaItem)
- [x] Implement `shared/business_rules.py` — `compute_default_access_level`, `determine_approval_route`, `is_document_visible`, `get_visible_agenda_documents`, `get_new_documents_since`
- [x] Implement `shared/seed_data.py` — populate seed data for UC1 read-flow scenarios (idempotent, incremental — Phase 2+ extends without rebuilding)
- [x] Initialize `one_agent.db` with seed data
- [x] 80 tests passing

### Phase 1B — Classical App (Read Flows) ✓ (2026-04-12)
- [x] Classical app: Delegate picker / impersonation (navbar dropdown + session)
- [x] Classical app: Dashboard (Screen 1)
- [x] Classical app: My Committees list (Screen 2)
- [x] Classical app: Committee detail (Screen 3)
- [x] Classical app: Upcoming Meetings list (Screen 4)
- [x] Classical app: Meeting detail + agenda documents (Screen 5) — document visibility enforced
- [x] Classical app: Document detail (Screen 6) — 403 if DAR insufficient
- [x] 102 tests passing

## Phase 2 — Classical App (Write Flows) — [PRD](prd-phase2-classical-write-flows.md)
> Delegate creation wizard — the 8-screen contrast tool

### Phase 2A — Schema and Seed Data Extensions ✓ (2026-04-15)
- [x] Add `DelegateRole` enum (DELEGATE, DELEGATION_EDITOR) and `role` column to Delegate model
- [x] Extend seed data: mark 3 delegation editors (DEL-2026-0001, DEL-2026-0005, DEL-2026-0007)
- [x] Add 3 target delegations (TGT-ALPHA, TGT-BETA, TGT-GAMMA) for demo wizard writes
- [x] Write 8 tests covering role seeding, target delegations, migration idempotency (110 tests total)
- [x] **TASK-026**: Fresh DB init — 7 delegations (4 original + 3 targets), 3 delegation editors
- [x] **TASK-027**: Migration idempotency — role column added, verified on repeat run
- [x] **TASK-028**: Full test suite — 110 tests pass (102 Phase 1 + 8 new Phase 2A)
- [x] **TASK-029**: Manual UI check (SKIPPED — requires Flask dev server + browser)
- [x] **TASK-030**: Update BACKLOG.md and DESIGN.md with Phase 2A completion

### Phase 2B–2D — Write Flows (upcoming)
- [ ] Extend `shared/seed_data.py` — add write-flow demo scenarios (incremental, does not rebuild Phase 1 data)
- [ ] Classical app: Delegation list (Screen 2)
- [ ] Classical app: Delegation detail with delegate list (Screen 3)
- [ ] Classical app: Add Delegate Step 1 — Personal info (Screen 4)
- [ ] Classical app: Add Delegate Step 2 — Committee selection (Screen 5)
- [ ] Classical app: Add Delegate Step 3 — Document Access Rights (Screen 6)
- [ ] Classical app: Add Delegate Step 4 — Review & Submit (Screen 7)
- [ ] Classical app: Confirmation (Screen 8)
- [ ] Wire up actual delegate + DAR creation using shared business rules

## Phase 3 — Agent App (Read Agent — UC1) ✓ (2026-04-22)
> "The Proactive Read Agent" — meeting brief on session start

### Phase 3A — Tools and Agent Setup ✓ (2026-04-20)
- [x] Implement agent tools: `get_delegation_info`, `lookup_delegate`, `get_upcoming_meetings`, `get_agenda_documents` (thin wrappers over shared layer using `@tool` + `FunctionInvocationContext` for identity threading)
- [x] Write system prompt encoding domain model, access-classification rule, proactive brief sequence, write-guard, grounding rule
- [x] Set up `Agent` with `FoundryChatClient` + read tools + `AuditMiddleware`
- [x] 15 new tests in `tests/agent_app/test_tools.py` (202 tests total)

### Phase 3B — FastAPI AG-UI Server ✓ (2026-04-20)
- [x] FastAPI AG-UI endpoint (`agent_app/server.py`) with `_BoundAgent` identity threading pattern
- [x] Custom AG-UI POST endpoint bypassing `HttpAgent` threadId reset limitation
- [x] Lazy agent singleton + `get_engine` DB initialization
- [x] `/api/delegates` endpoint for persona switcher (JOINed load)

### Phase 3C — CopilotKit Frontend ✓ (2026-04-20)
- [x] Next.js + CopilotKit frontend (`agent_app/frontend/`)
- [x] Streaming brief visually confirmed end-to-end
- [x] Document visibility rules function correctly via `get_agenda_documents` + DAR enforcement

### Phase 3D — Integration Tests and Doc Closure ✓ (2026-04-22)
- [x] `tests/agent_app/test_brief_logic.py` — brief trigger (new docs within lookback), suppress (stale docs, no meetings), grounding (tool-returned titles only), DAR visibility enforcement, multiple meetings, delegate-not-found edge case
- [x] ≥ 20 new tests across Phase 3 (15 Phase 3A + 16 Phase 3D = 31 new tests)
- [x] Full suite green: **203 tests passing**
- [x] Documentation closure: BACKLOG, DESIGN, DECISIONS updated

### Phase 3E — CopilotKit E2E Playwright Tests ✓ (2026-04-20)
- [x] 4 Playwright e2e tests in `tests/e2e_agent/` covering brief trigger, suppress, persona switch, tool call blocks
- [x] Tests require live Azure AI Foundry (excluded from unit test suite)

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
