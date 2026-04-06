---
goal: "Phase 0b: Complete Evaluation Suite, Scoring & Reporting"
version: 1.0
date_created: 2026-04-06
last_updated: 2026-04-06
owner: Stephane
status: Planned
tags:
  - feature
  - evaluation
  - phase-0
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Complete the Phase 0 evaluation harness with the full 15-scenario test
catalog, all 4 scoring criteria (C1-C4), CLI interface, and reporting.
Run the evaluation across all 6 candidate models and produce the decision
matrix for model selection.

**Prerequisite**: Phase 0a completed — the harness infrastructure is
validated end-to-end with 3 scenarios on 1 model.

**Exit criterion**: `python -m eval.harness --all` runs all 15 scenarios
across 6 models, produces `eval/results/results_YYYY-MM-DD.json` and
`eval/results/summary_YYYY-MM-DD.md` with per-model, per-criterion pass
rates and a final model recommendation.

## 1. Requirements & Constraints

- **REQ-001**: All 15 test prompts from spec S3.3 must be implemented as
  scenarios in `scenarios.json`.
- **REQ-002**: All 4 evaluation criteria (C1: correct tool, C2: schema-valid
  arguments, C3: multi-step sequencing, C4: asks vs invents) must have
  full evaluator implementations.
- **REQ-003**: Per-prompt scoring: `prompt_score = passing_criteria /
  applicable_criteria`.
- **REQ-004**: Per-model scoring: `model_score = sum(prompt_scores) /
  number_of_prompts`. Pass threshold: >= 0.85 (85%).
- **REQ-005**: Per-criterion pass rate: `prompts_passing_criterion /
  prompts_where_criterion_applies`. Each criterion must independently
  pass >= 75%.
- **REQ-006**: 6 models evaluated: `gpt-5.4-nano`, `gpt-4.1-nano`,
  `gpt-5.4-mini`, `gpt-4.1-mini`, `o4-mini`, `grok-3-mini`.
- **REQ-007**: CLI supports `--all`, `--model <name>`,
  `--category <name>`, `--output <path>` flags.
- **REQ-008**: JSON output contains raw traces (tool calls + agent
  response) and scores for every model x scenario combination.
- **REQ-009**: Markdown summary contains decision matrix table with
  per-criterion pass rates, aggregate score, cost tier, and
  pass/fail decision per model.
- **CON-001**: Reuse all Phase 0a infrastructure (tools, middleware,
  harness core loop, evaluator interface) without modification.
- **CON-002**: Scenarios must match spec S3.3 exactly (user messages,
  expected behaviors, applicable criteria per the matrix in S4).
- **GUD-001**: Evaluator functions must return human-readable explanations
  alongside pass/fail, enabling debugging of model failures.

## 2. Implementation Steps

### Phase 1: Remaining 12 Scenarios

- GOAL-001: Complete the test catalog with all scenarios from categories
  A, B, C, D. Each scenario must include user_message,
  system_context (if needed), synthetic_results, and expected behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add scenario A2 (Delegate search): user = "Is there a delegate named Marie Laurent in our delegation?", system_context = "User is from France delegation (FRA), delegate DEL-2026-0042.", expected: `lookup_delegate` with name="Marie Laurent" and delegation_id referencing France. Applicable: C1, C2. | | |
| TASK-002 | Add scenario A3 (Meeting schedule): user = "What meetings do I have coming up?", system_context = "User is delegate DEL-2026-0042.", expected: `get_upcoming_meetings` with delegate_id="DEL-2026-0042". Applicable: C1, C2. | | |
| TASK-003 | Add scenario A4 (Agenda documents): user = "Show me the agenda documents for the next Education Policy Committee meeting", system_context = "Meeting ID MTG-EDU-2026-04 is known from prior context.", expected: `get_agenda_documents` with meeting_id="MTG-EDU-2026-04". Applicable: C1, C2. | | |
| TASK-004 | Add scenario A5 (New documents since last visit): user = "Any new documents since my last login?", system_context = "Meeting ID MTG-EDU-2026-04, last login 2026-03-15.", expected: `get_agenda_documents` with meeting_id and since="2026-03-15". Applicable: C1, C2. | | |
| TASK-005 | Add scenario B2 (Meeting brief - proactive flow): user = "Hi, I just logged in.", system_context = "User is delegate DEL-2026-0042, last login 2026-03-15.", expected sequence: (1) `get_upcoming_meetings(delegate_id="DEL-2026-0042")`, (2) `get_agenda_documents(meeting_id=..., since="2026-03-15")`. Applicable: C1, C2, C3. synthetic_results must include meetings data that triggers the second call. | | |
| TASK-006 | Add scenario C2 (Delegate creation - missing committee): user = "I need to add a new delegate, Sophie Martin, she's an economist.", expected: should_ask_user=true, model should ask for committee and email. Applicable: C4. | | |
| TASK-007 | Add scenario C3 (Ambiguous delegation): user = "Add a delegate to our delegation - Pierre Blanc, he works on development aid.", system_context = "" (no delegation established), expected: should_ask_user=true, model should ask which delegation. Applicable: C4. | | |
| TASK-008 | Add scenario D1 (Member delegate - correct access level): user = "Create DAR for delegate DEL-2026-0891, Education Policy Committee. Our delegation is a member country.", expected: `create_document_access_rights` with classification_level="Restricted". Applicable: C1, C2. | | |
| TASK-009 | Add scenario D2 (Partner delegate - correct access level): user = "Create DAR for delegate DEL-2026-0500, Trade Committee. We're a partner organization, no framework agreement for this committee.", expected: `create_document_access_rights` with classification_level="General". Applicable: C1, C2. | | |
| TASK-010 | Add scenario D3 (Partner with Framework Agreement): user = "Create DAR for delegate DEL-2026-0500, Trade Committee. We're a partner but we have a Framework Agreement covering Trade.", expected: `create_document_access_rights` with classification_level="Restricted". Applicable: C1, C2. | | |
| TASK-011 | Add scenario D4 (Confidential access - flags approval): user = "I need Confidential access for delegate DEL-2026-0891 on the Education Policy Committee.", expected: `create_document_access_rights` with classification_level="Confidential", model should communicate secretariat approval requirement. Applicable: C1, C2, C4. | | |
| TASK-012 | Add scenario D5 (Retroactive access - flags approval): user = "Grant delegate DEL-2026-0891 access to Education Policy Committee documents, including documents from before their accreditation.", expected: `create_document_access_rights` with retroactive=True. Applicable: C1, C2. | | |

### Phase 2: Full Evaluator Implementations

- GOAL-002: Implement scoring logic for all 4 criteria with
  human-readable explanations.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Implement `evaluate_c2_schema_valid_args(tool_calls: list[dict], expected: dict) -> tuple[bool, str]`. Logic: for each expected tool call in `tool_calls_ordered`, find the matching actual call and verify (a) all `args_must_contain` keys are present with matching values (case-insensitive string match for strings, exact match for booleans/numbers), (b) no required parameters are missing (based on tool schema), (c) values in `must_not_hallucinate` fields were not invented (cross-reference with scenario user_message — if a value like email appears in args but not in user_message and not in synthetic_results, flag as hallucinated). Return explanation listing each check. | | |
| TASK-014 | Implement `evaluate_c3_multi_step_sequencing(tool_calls: list[dict], expected: dict) -> tuple[bool, str]`. Logic: extract the ordered list of expected tool names from `tool_calls_ordered`; verify that the actual tool calls appear in the same relative order (not necessarily contiguous — other calls may be interleaved). Specifically: lookup before create, get_delegation_info before create_document_access_rights. Return explanation showing expected vs actual order. | | |
| TASK-015 | Implement `evaluate_c4_asks_vs_invents(tool_calls: list[dict], agent_response: str, expected: dict) -> tuple[bool, str]`. Logic: if `should_ask_user` is True, pass if no write tool (`create_delegate`, `create_document_access_rights`) was called AND the agent_response contains a question (heuristic: ends with "?" or contains "could you", "please provide", "what is", etc.). If `should_ask_user` is False, check `must_not_hallucinate` fields — for each listed field, verify the value in the actual tool call matches a value present in the user_message or synthetic_results (not invented). Return explanation. | | |
| TASK-016 | Update `score_scenario` to call all 4 real evaluators instead of stubs. Verify backward compatibility: A1, B1, C1 scenarios still score correctly. | | |

### Phase 3: Score Aggregation

- GOAL-003: Implement per-model and per-criterion aggregation with
  pass/fail thresholds from the spec.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Implement `aggregate_model_scores(scenario_scores: list[ScenarioScore]) -> ModelScore` dataclass. `ModelScore` fields: `model: str`, `aggregate_score: float`, `criterion_pass_rates: dict[str, float]` (C1-C4), `per_prompt_scores: dict[str, float]`, `passes_aggregate: bool` (>= 0.85), `passes_all_criteria: bool` (each >= 0.75), `overall_pass: bool` (both True). | | |
| TASK-018 | Implement `compute_prompt_score(scenario_score: ScenarioScore) -> float`. Logic: count passing criteria / applicable criteria for that prompt. | | |
| TASK-019 | Implement `compute_criterion_pass_rate(scenario_scores: list[ScenarioScore], criterion: str) -> float`. Logic: count scenarios where criterion passes / scenarios where criterion is applicable. | | |

### Phase 4: CLI Interface

- GOAL-004: Add command-line argument parsing to the harness for
  flexible evaluation runs.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-020 | Add `argparse` to `eval/harness.py`. Arguments: `--all` (run all models x all scenarios), `--model <name>` (run one model, all scenarios), `--category <name>` (filter scenarios by category: single_tool_read, multi_step, missing_info, business_rule), `--output <path>` (write results to file instead of stdout), `--verbose` (print full tool call traces). | | |
| TASK-021 | Define `MODELS` list: `["gpt-5.4-nano", "gpt-4.1-nano", "gpt-5.4-mini", "gpt-4.1-mini", "o4-mini", "grok-3-mini"]`. When `--model` is specified, validate it's in the list. | | |
| TASK-022 | Implement scenario filtering by category. Categories derived from scenario `"category"` field. | | |
| TASK-023 | Add progress logging with loguru: print model name, scenario ID, and pass/fail as each scenario completes. On `--verbose`, also print the full tool call trace. | | |

### Phase 5: Results Output

- GOAL-005: Generate structured JSON results and a human-readable
  markdown summary with the decision matrix.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-024 | Implement `write_json_results(results: list[dict], path: str)`. Output format: `{"run_date": "YYYY-MM-DD", "models": [...], "scenarios": [...], "results": [...]}`. Each result entry includes model, scenario_id, tool_calls (full trace), agent_response, scores (per-criterion pass/fail + explanation). Default path: `eval/results/results_YYYY-MM-DD.json`. | | |
| TASK-025 | Implement `write_markdown_summary(model_scores: list[ModelScore], path: str)`. Generate markdown with: (1) header with run date, (2) decision matrix table (model, C1%, C2%, C3%, C4%, aggregate%, cost tier, pass/fail), (3) per-model detail sections showing failing scenarios, (4) recommendation paragraph identifying the cheapest passing model. Default path: `eval/results/summary_YYYY-MM-DD.md`. | | |
| TASK-026 | Add `eval/results/` to `.gitignore` (keep `.gitkeep` but ignore all other contents). | | |

### Phase 6: Full Evaluation Run & Analysis

- GOAL-006: Execute the complete evaluation across all 6 models, analyze
  results, document the model decision.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-027 | Run `python -m eval.harness --all --output eval/results/`. Verify all 6 models x 15 scenarios complete without errors. If a model is not deployed in Foundry, document which models were skipped and why. | | |
| TASK-028 | Review `summary_YYYY-MM-DD.md`. Identify: (a) which models pass the 85% aggregate threshold, (b) which models pass all per-criterion 75% thresholds, (c) the cheapest qualifying model. | | |
| TASK-029 | Update `docs/DECISIONS.md` with the model selection decision, including: chosen model, aggregate score, per-criterion scores, cost tier, and any noted weaknesses. Reference the results file. | | |
| TASK-030 | Update `docs/BACKLOG.md` Phase 0 tasks to reflect completion. Check off completed items, note any deferred items. | | |
| TASK-031 | If any criterion is borderline (75-80%) on the chosen model, create specific test prompts in the scenario catalog as regression monitors for later phases. Document these in the summary. | | |

## 3. Alternatives

- **ALT-001**: Manual evaluation (read model output, score by hand).
  Rejected: not reproducible, doesn't scale to 6 models x 15 scenarios,
  and doesn't produce a reusable regression suite.
- **ALT-002**: LLM-as-judge for scoring (use a stronger model to grade
  the candidate model's output). Rejected for Phase 0: adds cost and
  complexity. The criteria are objective enough for rule-based evaluation.
  Could revisit for C4 (asks vs invents) if heuristic scoring proves
  insufficient.
- **ALT-003**: Skip nano-tier models. Rejected: they set the baseline.
  If a nano model passes, it saves significant cost for the entire PoC.

## 4. Dependencies

- **DEP-001**: Phase 0a completed — all infrastructure files (tools,
  middleware, evaluators, harness) exist and are validated.
- **DEP-002**: All 6 models deployed in Azure AI Foundry project. If
  some models are unavailable, the harness should skip them gracefully
  and note the gap in the summary.
- **DEP-003**: `agent-framework>=1.0.0`, `agent-framework-foundry>=1.0.0`,
  `azure-identity>=1.19.0` (already installed in Phase 0a).
- **DEP-004**: Sufficient Azure credits for ~90 model calls (6 models x
  15 scenarios). Nano/mini-tier models are cheap; o4-mini may use more
  tokens due to chain-of-thought.

## 5. Files

- **FILE-001**: `eval/scenarios/scenarios.json` — Extended from 3 to 15
  scenarios (modify existing file from Phase 0a).
- **FILE-002**: `eval/evaluators.py` — Replace C2-C4 stubs with full
  implementations. Add `ModelScore` dataclass and aggregation functions.
  (Modify existing file from Phase 0a.)
- **FILE-003**: `eval/harness.py` — Add CLI parsing, multi-model loop,
  results output. (Modify existing file from Phase 0a.)
- **FILE-004**: `eval/results/results_YYYY-MM-DD.json` — Generated output.
- **FILE-005**: `eval/results/summary_YYYY-MM-DD.md` — Generated output.
- **FILE-006**: `docs/DECISIONS.md` — Updated with model selection decision.
- **FILE-007**: `docs/BACKLOG.md` — Updated with Phase 0 completion status.

## 6. Testing

- **TEST-001**: Unit test `evaluate_c2_schema_valid_args` with: (a) all
  args present and matching (pass), (b) missing required arg (fail),
  (c) hallucinated email not in user_message (fail), (d) correct email
  from user_message (pass).
- **TEST-002**: Unit test `evaluate_c3_multi_step_sequencing` with: (a)
  correct order (pass), (b) reversed order — create before lookup (fail),
  (c) interleaved but correct relative order (pass), (d) missing
  prerequisite step (fail).
- **TEST-003**: Unit test `evaluate_c4_asks_vs_invents` with: (a)
  should_ask=True and model asks question (pass), (b) should_ask=True
  but model calls create_delegate (fail), (c) should_ask=False and no
  hallucinated values (pass), (d) should_ask=False but email invented
  (fail).
- **TEST-004**: Unit test `aggregate_model_scores` with synthetic
  ScenarioScores verifying aggregate >= 0.85 and per-criterion >= 0.75
  thresholds.
- **TEST-005**: Integration test — run full harness with `--all` flag
  against live Azure AI Foundry. Verify JSON and markdown output files
  are generated with correct structure. (Manual, requires Azure
  credentials + all model deployments.)

## 7. Risks & Assumptions

- **RISK-001**: Some models may not be deployed in the Foundry project
  (e.g., `grok-3-mini` may not be available via Azure AI Foundry).
  Mitigation: harness catches deployment errors gracefully, logs the
  skip, and continues with remaining models. Summary notes which models
  were evaluated.
- **RISK-002**: `o4-mini` (reasoning model) may behave differently with
  tool calling (chain-of-thought before tool selection). Mitigation:
  evaluators check tool calls regardless of intermediate reasoning.
  The recorder captures all tool calls in order.
- **RISK-003**: C4 (asks vs invents) heuristic may produce false
  positives/negatives. Mitigation: the evaluator returns detailed
  explanations. Review flagged cases manually. If heuristic is
  insufficient, consider LLM-as-judge for C4 in a future iteration.
- **RISK-004**: Azure credit consumption. Mitigation: nano and mini
  models are cheap. Run one model at a time during development (`--model`
  flag). Full `--all` run only for final evaluation.
- **ASSUMPTION-001**: Phase 0a infrastructure works correctly — tools,
  middleware, and harness core loop are validated.
- **ASSUMPTION-002**: All 6 models support function calling via
  Azure AI Foundry's tool-calling protocol.
- **ASSUMPTION-003**: Synthetic tool results are sufficient for models
  to reason through multi-step scenarios (the model doesn't need "real"
  data to demonstrate correct sequencing).

## 8. Related Specifications / Further Reading

- [Phase 0 Specification](../docs/PHASE0-MODEL-EXPLORATION.md) — Source
  of truth for scenarios (S3.3), criteria (S4), and decision rules.
- [Phase 0a Implementation Plan](feature-phase0a-eval-infrastructure-1.md)
  — Prerequisite plan.
- [Architecture Overview](../docs/DESIGN.md)
- [Decision Log](../docs/DECISIONS.md)
