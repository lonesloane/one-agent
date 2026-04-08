---
goal: "Phase 0d: Fix Remaining Eval Design Gaps & Final Model Selection"
version: 1.0
date_created: 2026-04-08
last_updated: 2026-04-08
owner: Stephane
status: Planned
tags:
  - feature
  - evaluation
  - phase-0
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 0c ran all 6 models × 15 scenarios after fixing B2 (proactive trigger)
and D1–D5 (`lookup_delegate` synthetic data). No model passed. Root cause
analysis identified three additional eval design gaps — not model capability
failures — that cause universal or near-universal failures. This plan fixes
those gaps, re-runs the evaluation, and makes the final model selection.

**Closest model from Phase 0c:** `gpt-4.1-nano` at 77% aggregate (needs 85%),
failing on C4 (60%, needs 75%) and aggregate threshold.

**Prerequisite**: Phase 0c completed — all code changes merged to `main`.
Worktree is a fresh checkout of `main` via `.worktrees/phase-0d`.

**Exit criterion**: `python -m eval.harness --all` runs cleanly, at least one
model passes ≥ 85% aggregate and ≥ 75% per criterion, and `docs/DECISIONS.md`
records the chosen model with full justification.

## 1. Requirements & Constraints

- **REQ-001**: D1–D3 must pass both C1 and C2 for at least 4/6 models.
  The fix is to enrich the existing `get_delegation_info` synthetic results
  with committee name→code mappings. No other D scenario fields change.
- **REQ-002**: A5 must pass C1, C2, and C3 for at least 4/6 models. The
  fix requires updating `expected.tool_calls_ordered` and
  `applicable_criteria` — the only scenario whose `expected` fields change
  in this plan (the stale-context assumption makes the current spec
  unreachable without prior conversational context).
- **REQ-003**: C1 and C3 missing-information scenarios must pass C4 for at
  least 4/6 models. The fix is a system prompt write-guard. It must not
  break B1 or B2, which legitimately call write tools when all info is
  present.
- **REQ-004**: After fixes, all 15 scenarios must pass `pytest` (40 unit
  tests) without modification to the test suite.
- **REQ-005**: Decision rule unchanged from Phase 0 spec: cheapest model
  passing ≥ 85% aggregate AND ≥ 75% per criterion (C1–C4).
- **CON-001**: Only A5's `expected` fields may change. D1–D5, B1, B2, and
  all other scenario `expected` fields remain frozen ground-truth.
- **CON-002**: System prompt additions must generalise. No specific
  scenario IDs, delegate IDs, or argument values. Tool names are
  acceptable (they are real production tool names, not test artefacts).
- **CON-003**: All code changes are in the worktree at `.worktrees/phase-0d`
  on branch `feature/phase-0d-eval-fix-and-model-selection`. Run commands
  from that directory.
- **GUD-001**: Run targeted single-model, single-category checks before the
  full `--all` run to catch regressions cheaply.
- **GUD-002**: After adding the write-guard to SYSTEM_PROMPT, run the
  multi_step_sequencing category first to confirm B1 and B2 still pass.

## 2. Implementation Steps

### Phase 1: Fix D1–D3 — committee_id Mapping

- **GOAL-001**: Enrich the `get_delegation_info` synthetic results in D1,
  D2, and D3 with a `committees` array so models can resolve human-readable
  committee names to internal codes.

**Root cause**: `get_delegation_info` synthetic data (added in Phase 0c)
returns delegation type and framework agreements but no committee code
mapping. Models use the human-readable name from the user message
("Education Policy Committee", "Trade Committee") rather than the internal
code ("EDU-POL", "TRADE"), causing universal C2 failures on D1–D3.

**Current values in `eval/scenarios/scenarios.json`:**

| Scenario | Current `get_delegation_info` |
|----------|-------------------------------|
| D1 | `{"id": "FRA", "name": "France", "type": "member", "delegates": 45}` |
| D2 | `{"id": "PARTNER-ORG", ..., "framework_agreements": []}` |
| D3 | `{"id": "PARTNER-ORG", ..., "framework_agreements": ["Trade"]}` |

**New values (add `committees` key only, all other keys unchanged):**

| Scenario | `committees` value to add |
|----------|--------------------------|
| D1 | `[{"name": "Education Policy Committee", "id": "EDU-POL"}]` |
| D2 | `[{"name": "Trade Committee", "id": "TRADE"}]` |
| D3 | `[{"name": "Trade Committee", "id": "TRADE"}]` |

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `eval/scenarios/scenarios.json`, update D1's `get_delegation_info` synthetic result. Replace current value with: `"{\"id\": \"FRA\", \"name\": \"France\", \"type\": \"member\", \"delegates\": 45, \"committees\": [{\"name\": \"Education Policy Committee\", \"id\": \"EDU-POL\"}]}"`. No other fields change. | | |
| TASK-002 | Update D2's `get_delegation_info` synthetic result. Replace with: `"{\"id\": \"PARTNER-ORG\", \"name\": \"Partner Organization\", \"type\": \"partner\", \"delegates\": 5, \"framework_agreements\": [], \"committees\": [{\"name\": \"Trade Committee\", \"id\": \"TRADE\"}]}"`. | | |
| TASK-003 | Update D3's `get_delegation_info` synthetic result. Replace with: `"{\"id\": \"PARTNER-ORG\", \"name\": \"Partner Organization\", \"type\": \"partner\", \"delegates\": 5, \"framework_agreements\": [\"Trade\"], \"committees\": [{\"name\": \"Trade Committee\", \"id\": \"TRADE\"}]}"`. | | |

### Phase 2: Fix A5 — Stale Context Assumption

- **GOAL-002**: Rewrite the A5 scenario so the meeting ID is discoverable
  at runtime (via `get_upcoming_meetings`) rather than assumed from a
  non-existent prior session context.

**Root cause**: A5's `system_context` states "Meeting ID MTG-EDU-2026-04
is known from prior context" — but in a fresh agent session no prior
context exists. Models cannot infer the meeting ID and skip
`get_agenda_documents`. This causes near-universal C1 failure on A5.

**A5 before (current state):**
```json
"system_context": "Meeting ID MTG-EDU-2026-04 is known from prior
  context. User's last login was 2026-03-15.",
"synthetic_results": {
  "get_agenda_documents": "..."
},
"expected": {
  "tool_calls_ordered": [
    {"name": "get_agenda_documents",
     "args_must_contain": {"meeting_id": "MTG-EDU-2026-04",
                           "since": "2026-03-15"}}
  ],
  "applicable_criteria": ["C1", "C2"]
}
```

**A5 after (target state):**
```json
"system_context": "User is delegate DEL-2026-0042, last login
  2026-03-15.",
"synthetic_results": {
  "get_upcoming_meetings": "{\"meetings\": [{\"id\":
    \"MTG-EDU-2026-04\", \"committee\": \"Education Policy\",
    \"date\": \"2026-04-15\"}]}",
  "get_agenda_documents": "..."
},
"expected": {
  "tool_calls_ordered": [
    {"name": "get_upcoming_meetings",
     "args_must_contain": {"delegate_id": "DEL-2026-0042"}},
    {"name": "get_agenda_documents",
     "args_must_contain": {"meeting_id": "MTG-EDU-2026-04",
                           "since": "2026-03-15"}}
  ],
  "applicable_criteria": ["C1", "C2", "C3"]
}
```

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | In `eval/scenarios/scenarios.json`, update scenario A5: (a) set `system_context` to `"User is delegate DEL-2026-0042, last login 2026-03-15."`, (b) add `"get_upcoming_meetings": "{\"meetings\": [{\"id\": \"MTG-EDU-2026-04\", \"committee\": \"Education Policy\", \"date\": \"2026-04-15\"}]}"` to `synthetic_results`, (c) update `expected.tool_calls_ordered` to `[{"name": "get_upcoming_meetings", "args_must_contain": {"delegate_id": "DEL-2026-0042"}}, {"name": "get_agenda_documents", "args_must_contain": {"meeting_id": "MTG-EDU-2026-04", "since": "2026-03-15"}}]`, (d) update `expected.applicable_criteria` to `["C1", "C2", "C3"]`. The `description`, `category`, `user_message`, `must_not_hallucinate`, and `should_ask_user` fields are unchanged. | | |

### Phase 3: Fix C4 — Write-Before-Asking System Prompt Guard

- **GOAL-003**: Add an explicit write-guard sentence to SYSTEM_PROMPT in
  `eval/harness.py` so models ask for missing required fields before
  calling any creation tool.

**Root cause**: SYSTEM_PROMPT says to ask when info is missing, but does
not explicitly prohibit calling write tools first. Models (notably
`gpt-4.1-nano`) call `create_delegate` or `create_document_access_rights`
before asking for missing email or delegation context, failing C4.

**Sentence to append** (after the proactive-brief sentence added in
Phase 0c, before the closing `)`):

```
" Before calling any tool that creates or modifies data, confirm that
  all required information has been provided by the user; if any
  required field is missing, ask for it before proceeding."
```

Line-length constraint: each continuation string ≤ 79 chars (including
4-space indent and surrounding quotes).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | In `eval/harness.py`, append to SYSTEM_PROMPT (after the proactive-brief sentence, before the closing `)`): `" Before calling any tool that creates or modifies data,"` / `" confirm that all required information has been provided by the"` / `" user; if any required field is missing, ask for it before"` / `" proceeding."` (split across 4 continuation strings to stay ≤ 79 chars/line). Verify line lengths after edit. | | |

### Phase 4: Regression Check

- **GOAL-004**: Verify unit tests still pass and targeted live runs confirm
  each fix works before spending credits on the full `--all` run.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | From `.worktrees/phase-0d`, run `source /home/stephane/Playground/GenAI/copilot/.venv/bin/activate && python -m pytest tests/ -q`. All 40 tests must pass. | | |
| TASK-007 | Run `python -m eval.harness --model gpt-4.1-nano --category multi_step_sequencing --output eval/results/`. Confirm B1 and B2 still PASS (write-guard must not block B1 when all info is present). If B1 or B2 regresses, diagnose SYSTEM_PROMPT wording and adjust (CON-002 still applies). | | |
| TASK-008 | Run `python -m eval.harness --model gpt-4.1-nano --category single_tool_read --output eval/results/`. Confirm A5 passes C1, C2, and C3. If A5 still fails C1, inspect model response — model may not be calling `get_upcoming_meetings` first; adjust `system_context` wording if needed. | | |
| TASK-009 | Run `python -m eval.harness --model gpt-4.1-nano --category missing_information --output eval/results/`. Confirm C1 and C3 pass C4 (model asks rather than acts). If either still fails C4, strengthen write-guard wording. | | |
| TASK-010 | Run `python -m eval.harness --model gpt-4.1-nano --category business_rule --output eval/results/`. Confirm D1, D2, D3 now pass C2 (`committee_id` matches). Remaining C2 failures on D4/D5 (`classification_level`) are real model weaknesses — do not fix. | | |

### Phase 5: Full Evaluation Run

- **GOAL-005**: Execute the complete evaluation across all 6 models with
  the fixed scenarios and system prompt.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Commit all changes with message `"Fix eval design gaps: D1-D3 committee mapping, A5 context, C4 write-guard"`. | | |
| TASK-012 | From `.worktrees/phase-0d`, run `python -m eval.harness --all --output eval/results/ 2>&1 \| tee eval/results/run_log_2026-04-08b.txt`. Expected duration: 30–60 min. Note: `eval/results/` is gitignored. | | |
| TASK-013 | Verify output files exist: `eval/results/results_*.json` and `eval/results/summary_*.md`. Inspect for TIMEOUT or ERROR lines — if more than 3 scenarios per model were skipped, note that model's score as unreliable in DECISIONS.md. | | |

### Phase 6: Model Selection & Documentation

- **GOAL-006**: Apply the decision rule, select the model, and document
  the decision.

**Decision rule** (unchanged from Phase 0 spec):
1. `aggregate_score >= 0.85` (85%)
2. All criterion pass rates `>= 0.75` (75%) individually
3. Among qualifying models, select cheapest tier (nano < mini < reasoning)
4. Within same tier, prefer higher aggregate score

**Cost tiers** (from `eval/results_writer.py`):
- nano: `gpt-5.4-nano`, `gpt-4.1-nano`
- mini: `gpt-5.4-mini`, `gpt-4.1-mini`, `grok-3-mini`
- reasoning: `o4-mini`

**Expected leading candidates** (based on Phase 0c closeness):
- `gpt-4.1-nano` (nano tier): was 77% overall, 92% C1, 75% C2, 100% C3,
  60% C4. The write-guard fix targets its C4 weakness directly.
- `gpt-5.4-nano` (nano tier): was 67% overall; its A5/D committee
  failures are now addressed.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Read `eval/results/summary_*.md`. List: (a) which models pass ≥ 85% aggregate, (b) which of those also pass ≥ 75% per criterion, (c) the cheapest qualifying model by tier. If no model qualifies, go to TASK-017. | | |
| TASK-015 | Update `docs/DECISIONS.md`. Append a new dated entry: chosen model, aggregate score, per-criterion scores (C1–C4), cost tier, noted weaknesses, results file path. | | |
| TASK-016 | Update `docs/BACKLOG.md`. Mark Phase 0d complete. Add note that Phase 1 can begin with selected model. | | |
| TASK-017 | **Fallback (if no model qualifies)**: Document closest model and remaining gaps. Add Phase 0e entry to BACKLOG.md. Do not invent a passing model. | | |
| TASK-018 | Mark all Phase 0d tasks complete in this plan file. Commit: `"Complete Phase 0d: [model name] selected for Phase 1"` (or fallback message). | | |

## 3. Alternatives

- **ALT-001**: Provide committee codes in the user message rather than in
  `get_delegation_info`. Rejected: real users don't know internal codes;
  the agent must resolve them from delegation info. Making the scenario
  trivial defeats the purpose of testing C2.
- **ALT-002**: Relax `args_must_contain` for `committee_id` to accept
  fuzzy matching (e.g., "Trade" matches "TRADE"). Rejected: CON-001 —
  expected fields are frozen ground truth. Fuzzy matching in the evaluator
  would require code changes and inflate all models' C2 scores.
- **ALT-003**: Move A5 to the `multi_step_sequencing` category since it
  now requires two sequential calls. Deferred: the category field does not
  affect scoring (evaluators use `applicable_criteria`). A rename is a
  cosmetic change; leaving it in `single_tool_read` is acceptable for now.
- **ALT-004**: Strengthen the write-guard by naming specific tools
  (`create_delegate`, `create_document_access_rights`). Deferred: the
  general phrasing ("any tool that creates or modifies data") is cleaner
  and more production-realistic. Name-specific guards risk over-fitting to
  the eval suite.

## 4. Dependencies

- **DEP-001**: Phase 0c branch `feature/phase-0c-eval-fix-and-model-selection`
  merged to `main` — all infrastructure and Phase 0c fixes in place.
- **DEP-002**: Azure AI Foundry project with all 6 models deployed.
- **DEP-003**: Azure CLI credentials active (`az login` done in session).

## 5. Files

- **FILE-001**: `eval/harness.py` — SYSTEM_PROMPT constant extended with
  write-guard sentence (TASK-005).
- **FILE-002**: `eval/scenarios/scenarios.json` — D1, D2, D3
  `get_delegation_info` synthetic results enriched with `committees` key
  (TASK-001–003); A5 `system_context`, `synthetic_results`, and
  `expected` fields updated (TASK-004).
- **FILE-003**: `eval/results/results_*.json` — generated output,
  gitignored.
- **FILE-004**: `eval/results/summary_*.md` — generated output, gitignored.
- **FILE-005**: `docs/DECISIONS.md` — updated with final model selection
  (TASK-015).
- **FILE-006**: `docs/BACKLOG.md` — Phase 0d marked complete (TASK-016).

## 6. Testing

- **TEST-001**: `python -m pytest tests/ -q` — all 40 existing unit tests
  must pass. Changing `scenarios.json` does not affect unit tests (they
  use mock data); changing `SYSTEM_PROMPT` does not affect unit tests
  (they test evaluator logic). This validates no regression in scoring
  code.
- **TEST-002**: Targeted multi_step_sequencing run (TASK-007) — B1 and B2
  still PASS with `gpt-4.1-nano`. Guards B1 against the write-guard
  regression risk.
- **TEST-003**: Targeted single_tool_read run (TASK-008) — A5 passes C1,
  C2, C3 with `gpt-4.1-nano`.
- **TEST-004**: Targeted missing_information run (TASK-009) — C1 and C3
  pass C4 with `gpt-4.1-nano`.
- **TEST-005**: Targeted business_rule run (TASK-010) — D1, D2, D3 pass
  C2 with `gpt-4.1-nano`. Remaining D4/D5 C2 failures acceptable.

## 7. Risks & Assumptions

- **RISK-001**: The write-guard may cause B1 to regress if models ask for
  confirmation even when all info is present. Mitigation: TASK-007
  (targeted B1/B2 check) catches this before the full `--all` run.
  Mitigation: the write-guard only applies when info is _missing_, not as
  a blanket confirmation request.
- **RISK-002**: Adding `committees` to `get_delegation_info` may not be
  sufficient for all models — some may not notice or use the committee
  codes from the response. These become real C2 failures (model weakness),
  not design gaps. Per REQ-001, 4/6 models must improve; not all 6.
- **RISK-003**: A5's redesign as a two-step scenario may still fail on
  models that don't spontaneously call `get_upcoming_meetings` when asked
  "any new documents since my last login?". Mitigation: if the wording
  causes broad failure, adjust `user_message` to hint at meetings (e.g.,
  "Any new meeting documents since my last login?").
- **RISK-004**: No model qualifies after fixes. Mitigation: TASK-017
  (fallback path) — document gaps and plan Phase 0e.
- **ASSUMPTION-001**: The three identified gaps are the primary blockers.
  `gpt-4.1-nano` at 77% is close enough that fixing committee_id (D1–D3
  C2) and C4 (write-guard) should push it past 85% aggregate.
- **ASSUMPTION-002**: The 40 unit tests do not hard-code A5's expected
  values and will continue to pass after TASK-004.

## 8. Related Specifications / Further Reading

- [Phase 0c Results Summary](../eval/results/summary_2026-04-08.md) —
  decision matrix from the Phase 0c run (local, gitignored).
- [Phase 0 Specification](../docs/PHASE0-MODEL-EXPLORATION.md) —
  source of truth for criteria (S4) and decision rules.
- [Phase 0c Implementation Plan](feature-phase0c-eval-fix-and-model-selection-1.md)
  — predecessor plan; all three Phase 0c fixes are in place on `main`.
- [Decision Log](../docs/DECISIONS.md) — Phase 0c findings documented;
  Phase 0d decision will be added here.
- [Backlog](../docs/BACKLOG.md) — Phase 0d task list tracked here.
