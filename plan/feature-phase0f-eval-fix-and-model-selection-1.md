---
goal: "Phase 0f: Add Access-Classification Rule & Final Model Selection"
version: 1.0
date_created: 2026-04-09
last_updated: 2026-04-10
owner: Stephane
status: Complete
tags:
  - feature
  - evaluation
  - phase-0
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 0e ran all 6 models × 15 scenarios after rewording the write-guard.
No model passed. The write-guard reword itself was confirmed correct (B1
passed C1/C2/C3 in targeted check), but the full run exposed a different
root cause: the `classification_level` business rule is never encoded
anywhere, so models consistently guess wrong for D1, D3, and D5. This is
the ALT-004 gap flagged in Phase 0d and deferred. It is now the primary
blocker.

**Closest model from Phase 0e:** `gpt-4.1-mini` at 79% aggregate
(needs 85%), C2=73% (needs 75%). Core failures: D1/D3/D5 wrong
`classification_level`; D4 timeout; C1 scenario calls write tools
despite missing email.

**Prerequisite**: Phase 0e merged to `main`.
Worktree is a fresh checkout of `main` via `.worktrees/phase-0f`.

**Exit criterion**: `python -m eval.harness --all` runs cleanly, at
least one model passes ≥ 85% aggregate and ≥ 75% per criterion, and
`docs/DECISIONS.md` records the chosen model with full justification.

## 1. Requirements & Constraints

- **REQ-001**: After the fix, D1, D3, and D5 must produce correct
  `classification_level` values for `gpt-4.1-mini`. D1 and D3 expect
  `'Restricted'` (member delegation); D5 expects `'Restricted'`
  (partner + framework agreement).
- **REQ-002**: After the fix, B1 must still pass C1, C2, and C3 for
  all 6 models. The write-guard must not be inadvertently tightened.
- **REQ-003**: After the fix, C1 and C3 must still pass C4 for at
  least 4/6 models. The missing-info guard must remain functional.
- **REQ-004**: All 40 unit tests must pass without modification.
- **REQ-005**: Decision rule unchanged — cheapest model passing
  ≥ 85% aggregate AND ≥ 75% per criterion (C1–C4). Nano < mini <
  reasoning tier ordering.
- **CON-001**: No scenario `expected` fields may change. All scenario
  ground truth frozen after Phase 0d.
- **CON-002**: All code changes are in the worktree at
  `.worktrees/phase-0f` on branch
  `feature/phase-0f-eval-fix-and-model-selection`. Run commands from
  that directory.
- **CON-003**: SYSTEM_PROMPT additions must fit within the existing
  string continuation structure. Each line ≤ 79 characters (including
  4-space indent and surrounding quotes).
- **CON-004**: The classification rule must use general language.
  No scenario IDs or specific delegate names. Tool argument names
  (`classification_level`) and value strings (`'Restricted'`,
  `'General'`) are acceptable — they are real production values.
- **GUD-001**: Run the targeted D-category check immediately after
  adding the rule to confirm D1/D3/D5 pass before the full `--all`
  run.
- **GUD-002**: Run the targeted B1/C1 check to confirm the write-guard
  and permit cases are unaffected.

## 2. Implementation Steps

### Phase 1: Add Access-Classification Rule to SYSTEM_PROMPT

- **GOAL-001**: Encode the delegation-type → classification_level
  mapping in SYSTEM_PROMPT so models can infer the correct value from
  `get_delegation_info` results.

**Root cause**: Models fail D1/D3/D5 C2 because `classification_level`
is set from business knowledge not available to the model. The mapping
is:
- Member delegation → `'Restricted'`
- Partner delegation, no framework agreement → `'General'`
- Partner delegation, framework agreement active → `'Restricted'`

This rule must be added to SYSTEM_PROMPT so it is present at inference
time.

**Current SYSTEM_PROMPT** (condensed, `eval/harness.py` lines 25–48):
```
...
" delegation's membership type."          ← line 38
" When a user's opening message is..."    ← line 39
...
" making the tool call."                  ← line 47
)                                         ← line 48
```

**Insertion point**: after line 38 (end of the delegate-creation
sequence rule), before line 39 (proactive login rule). The new block
logically extends the delegate-creation guidance.

**New block** (4 lines, inserted between current lines 38 and 39):
```python
    " Document access classification follows delegation membership:"
    " member delegates use classification_level='Restricted'; partner"
    " delegates use 'General' unless a framework agreement is active,"
    " in which case use 'Restricted'."
```

Line-length check (including 4-space indent + quotes):
- Line A: `    " Document access classification follows delegation membership:"` = 66 chars ✓
- Line B: `    " member delegates use classification_level='Restricted'; partner"` = 70 chars ✓
- Line C: `    " delegates use 'General' unless a framework agreement is active,"` = 70 chars ✓
- Line D: `    " in which case use 'Restricted'."` = 37 chars ✓

After insertion, the write-guard (currently lines 44–47) shifts to
lines 48–51. The closing `)` shifts to line 52.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `eval/harness.py`, insert the 4 classification-rule continuation strings after the delegate-creation sequence line (current line 38). Verify line lengths ≤ 79 chars. Verify Python syntax (`py_compile`). Commit: `"Add access-classification rule to SYSTEM_PROMPT: member→Restricted, partner→General/Restricted"`. | | |

### Phase 2: Investigate D4 Timeout

- **GOAL-002**: Understand why D4 times out for `gpt-4.1-mini` and
  fix if it is an eval design issue, or document if it is a model
  limitation.

D4 is "Confidential DAR — requires secretariat approval". The scenario
involves a delegate requiring Confidential access level. The timeout
may be caused by the model entering a reasoning or tool-call loop
when it cannot determine the approval route.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-002 | Run `python -m eval.harness --model gpt-4.1-mini --category document_access_rights --output eval/results/` with verbose logging. Capture the full tool-call sequence and agent response for D4. If the timeout is caused by missing synthetic data (e.g., no approval-route tool response), add it to the scenario. If it is a model reasoning loop, document it as a model limitation. | | |

### Phase 3: Regression Check

- **GOAL-003**: Confirm the classification rule fixes D-category C2
  failures without breaking the write-guard or missing-info guard.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Run `python -m pytest tests/ -q`. All 40 tests must pass. | | |
| TASK-004 | Run `python -m eval.harness --model gpt-4.1-mini --category document_access_rights --output eval/results/`. Confirm D1 and D3 PASS C2 (correct `classification_level`). Confirm D5 PASS C2. If any D scenario still fails C2, inspect the agent response — the model may need the rule stated more explicitly. | | |
| TASK-005 | Run `python -m eval.harness --model gpt-4.1-mini --category multi_step_sequencing --output eval/results/`. Confirm B1 still PASSES C1, C2, C3. | | |
| TASK-006 | Run `python -m eval.harness --model gpt-4.1-mini --category missing_information --output eval/results/`. Confirm C1 and C3 still pass C4. | | |

### Phase 4: Full Evaluation Run

- **GOAL-004**: Execute the complete evaluation across all 6 models.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | From `.worktrees/phase-0f`, run `python -m eval.harness --all --output eval/results/ 2>&1 \| tee eval/results/run_log_2026-04-09d.txt`. Expected duration: 30–60 min. | | |
| TASK-008 | Verify output files: `eval/results/results_*.json` and `eval/results/summary_*.md`. Check for TIMEOUT or ERROR lines — if > 3 scenarios skipped per model, flag that model's score as unreliable. | | |

### Phase 5: Model Selection & Documentation

- **GOAL-005**: Apply the decision rule, select the model, and
  document the decision.

**Decision rule** (unchanged from Phase 0 spec):
1. `aggregate_score >= 0.85` (85%)
2. All criterion pass rates `>= 0.75` (75%) individually (C1–C4)
3. Among qualifying models, select cheapest tier
   (nano < mini < reasoning)
4. Within same tier, prefer higher aggregate score

**Cost tiers:**
- nano: `gpt-5.4-nano`, `gpt-4.1-nano`
- mini: `gpt-5.4-mini`, `gpt-4.1-mini`, `grok-3-mini`
- reasoning: `o4-mini`

**Expected leading candidate:** `gpt-4.1-mini` (mini tier). Phase 0e
showed 79% aggregate and C2=73%, both driven by D-category
`classification_level` failures. After adding the rule: D1/D3/D5
should pass C2, lifting C2 above 75% and aggregate above 85%.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Read `eval/results/summary_*.md`. Apply decision rule: (a) list models with aggregate ≥ 85%, (b) filter to those with all per-criterion rates ≥ 75%, (c) select cheapest qualifying tier. If no model qualifies, go to TASK-012. | | |
| TASK-010 | Update `docs/DECISIONS.md`. Append a new dated entry with: chosen model, aggregate score, per-criterion scores (C1–C4), cost tier, noted weaknesses, results file path. | | |
| TASK-011 | Update `docs/BACKLOG.md`. Mark Phase 0f complete. Add note that Phase 1 can begin with the selected model. | | |
| TASK-012 | **Fallback (if no model qualifies)**: Document closest model and remaining gaps in `docs/DECISIONS.md`. Add Phase 0g entry to `docs/BACKLOG.md`. Do not invent a passing model. | | |
| TASK-013 | Update this plan: mark all tasks complete. Commit: `"Complete Phase 0f: [model name] selected for Phase 1"` (or fallback message). | | |

## 3. Alternatives

- **ALT-001**: Encode the classification rule as a synthetic tool
  result in each D scenario's `lookup_delegate` or
  `get_delegation_info` response. Rejected for D1/D3/D5 because the
  rule is already derivable from the `membership_type` field returned
  by `get_delegation_info` — the model just doesn't know the mapping.
  Better to teach the model the mapping once in SYSTEM_PROMPT than to
  embed it in every scenario.
- **ALT-002**: Move the classification rule to the MCP KB (Phase 5)
  and add a `get_classification_rule` tool. Deferred — adds tool-call
  overhead and MCP KB is not built yet. SYSTEM_PROMPT encoding is
  simpler and sufficient for Phase 0 evaluation.
- **ALT-003**: Add a stronger negative write-guard for C1 (missing
  email). The residual C1 failures are real model weakness. If
  classification_level fix alone does not push gpt-4.1-mini above
  85%, consider adding "Required fields for delegate creation: full
  name, email address, role, and committee assignment." to SYSTEM_PROMPT.
  Deferred until Phase 4 results are reviewed.

## 4. Dependencies

- **DEP-001**: Phase 0e branch merged to `main` — write-guard reword
  in place.
- **DEP-002**: Azure AI Foundry project with all 6 models deployed.
- **DEP-003**: Azure CLI credentials active (`az login` done).

## 5. Files

- **FILE-001**: `eval/harness.py` — SYSTEM_PROMPT classification rule
  inserted after delegate-creation sequence (TASK-001).
- **FILE-002**: `eval/results/results_*.json` — generated output,
  gitignored.
- **FILE-003**: `eval/results/summary_*.md` — generated output,
  gitignored.
- **FILE-004**: `eval/results/run_log_2026-04-09d.txt` — full run
  log, gitignored.
- **FILE-005**: `docs/DECISIONS.md` — updated with final model
  selection or fallback (TASK-010).
- **FILE-006**: `docs/BACKLOG.md` — Phase 0f marked complete
  (TASK-011).

## 6. Testing

- **TEST-001**: `python -m pytest tests/ -q` — all 40 unit tests
  pass. SYSTEM_PROMPT changes do not affect evaluator logic.
- **TEST-002**: Targeted `document_access_rights` run (TASK-004) —
  D1/D3/D5 pass C2 for `gpt-4.1-mini`.
- **TEST-003**: Targeted `multi_step_sequencing` run (TASK-005) —
  B1 still passes C1/C2/C3 for `gpt-4.1-mini`.
- **TEST-004**: Targeted `missing_information` run (TASK-006) —
  C1 and C3 still pass C4 for `gpt-4.1-mini`.

## 7. Risks & Assumptions

- **RISK-001**: Adding the classification rule may confuse models
  on D2 (partner without FA → General), causing them to over-apply
  `'Restricted'`. Mitigation: TASK-004 checks all D scenarios, not
  just D1/D3/D5.
- **RISK-002**: D4 timeout may be a genuine model limitation
  (reasoning loop on Confidential approval). If so, it stays a known
  weakness and scores are computed with D4 as a fail/skip. This does
  not block model selection if aggregate clears 85%.
- **RISK-003**: No model qualifies after the fix. Mitigation:
  TASK-012 fallback path. If gpt-4.1-mini still fails after encoding
  the classification rule, the remaining gaps are genuine model
  weaknesses that require Phase 1 MCP KB support.
- **ASSUMPTION-001**: `gpt-4.1-mini`'s D1/D3/D5 C2 failures in
  Phase 0e are caused solely by the missing classification rule.
  Evidence: the rule is present in no eval artifact, and D1/D3/D5
  are the only scenarios requiring it; all other scenarios pass C2
  for gpt-4.1-mini.
- **ASSUMPTION-002**: The 40 unit tests do not hard-code SYSTEM_PROMPT
  content and will pass after TASK-001.

## 8. Related Specifications / Further Reading

- [Phase 0e Results Summary](../eval/results/summary_2026-04-09.md)
  — decision matrix from the Phase 0e run (local, gitignored).
- [Phase 0 Specification](../docs/PHASE0-MODEL-EXPLORATION.md)
  — source of truth for criteria (S4) and decision rules.
- [Phase 0e Implementation Plan](feature-phase0e-eval-fix-and-model-selection-1.md)
  — predecessor plan; all Phase 0e fixes in place on `main`.
- [Decision Log](../docs/DECISIONS.md) — Phase 0e findings documented;
  Phase 0f decision will be added here.
- [Backlog](../docs/BACKLOG.md) — Phase 0f task list tracked here.
