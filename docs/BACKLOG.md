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

### Phase 2B — Read Pages + Editor Permissions ✓ (2026-04-18)
- [x] Classical app: Delegation list (Screen 2) — accessible to all personas
- [x] Classical app: Delegation detail with delegate roster (Screen 3)
- [x] `@editor_of_delegation_required` decorator — guards all write-wizard entry points
- [x] `is_editor_of_delegation` Jinja global — controls "Add New Delegate" button visibility
- [x] 403 template extended with optional `reason` variable
- [x] Editor badge in delegate picker — visually distinguishes DELEGATION_EDITOR personas
- [x] Routes package scaffold + permissions helper (`classical_app/permissions.py`)
- [x] 128 tests passing (110 Phase 1+2A + 18 new Phase 2B)

### Phase 2C — Add Delegate Wizard ✓ (2026-04-19)
- [x] Classical app: Add Delegate Step 1 — Personal info (Screen 4)
- [x] Classical app: Add Delegate Step 2 — Committee selection (Screen 5)
- [x] Classical app: Add Delegate Step 3 — Document Access Rights (Screen 6)
- [x] Classical app: Add Delegate Step 4 — Review & Submit (Screen 7)
- [x] Wire up delegate + DAR creation through `compute_default_access_level` + `determine_approval_route`
- [x] 172 tests passing (merged to main at 27cb21b)

### Phase 2D — Tests, Demo Dry-Run & Doc Closure ✓ (2026-04-19)
- [x] Test inventory audit (2A/2B/2C net-new: 70 tests; REQ-001 met)
- [x] `tests/classical_app/test_wizard_session.py` — back-preserves-data, step-skip redirect
- [x] `tests/classical_app/test_wizard_approval_routing.py` — monkeypatch spy, US-5 matrix ×6, preselect
- [x] `tests/classical_app/test_wizard_permissions.py` — button visibility ×3, editor-of-other 403
- [x] `tests/classical_app/test_wizard_rollback.py` — transactional rollback row-count assertion
- [x] `tests/shared/test_database.py` extended — `retroactive` column default=False
- [x] Full suite green: **188 tests passing** (102 Phase 1 baseline + 86 net-new Phase 2)
- [x] `docs/DEMO_PHASE2.md` — golden-path demo dry-run script (6 scenarios, all 3 approval routes)
- [x] Documentation closure: BACKLOG, DESIGN, OPEN_QUESTIONS, DECISIONS updated

## Phase 3+ — Agent App (C# / .NET rebuild)
> First attempt (Phase 3 / 3.5 / 4 / spikes) abandoned 2026-04-28; artifacts under `docs/_archived/` and `plan/_archived/`. Stack pivot to C# / .NET decided 2026-04-29 (see `docs/agent-stack-decision-2026-04-29.md`). Microsoft Agent Framework retained as runtime; CopilotKit React via AG-UI on `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` selected as frontend; HITL via `ApprovalRequiredAIFunction` + `request_approval` synthetic client tool + bidirectional middleware.

Research & decision (done):
- [x] Agent stack research — `docs/research-agent-stack.md`, `docs/research-agent-stack-candidates.md`
- [x] HITL approach — folded into stack decision (`docs/agent-stack-decision-2026-04-29.md` §5–6); standalone `research-hitl-approach.md` not needed
- [x] OQ-7 resolved (frontend) — see `docs/OPEN_QUESTIONS.md`
- [x] OQ-9 Phase 4 resolved (approver UX = separate CopilotKit route, UC3) — see `docs/OPEN_QUESTIONS.md`

Pre-implementation prerequisites:
- [ ] `shared/csharp/BusinessRules.cs` port + parity tests against `shared/business_rules.py`
- [ ] `agent_app/` .NET scaffold: `AgentApp.csproj`, `Program.cs` w/ `MapAGUI("/", agent)`, `FoundryChatClient` wiring, `.editorconfig` + `global.json`
- [ ] PRD — read agent (UC1, proactive meeting brief)
- [ ] PRD — write agent (UC2, delegate creation + DAR routing via HITL)
- [ ] PRD — approver UX (UC3, separate CopilotKit route over `DocumentAccessRight.approval_status`)
- [ ] Implementation plans per phase

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
