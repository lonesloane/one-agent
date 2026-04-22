---
goal: "Phase 0e: Fix Write-Guard Wording & Final Model Selection"
version: 1.0
date_created: 2026-04-09
last_updated: 2026-04-09
owner: Stephane
status: Complete
tags:
  - feature
  - evaluation
  - phase-0
---

# Introduction

![Status: Complete](https://img.shields.io/badge/status-Complete-green)

Phase 0d ran all 6 models × 15 scenarios after fixing D1–D3 committee mappings,
A5 stale-context, and adding a write-guard to SYSTEM_PROMPT. No model passed.
Root cause: the write-guard wording is over-restrictive — `gpt-5.4-nano`
refuses to call write tools even in B1 where all information is present, causing
B1 to fail C1/C2/C3 and D4 to fail C1/C2. This drops C3 to 67% (needs 75%)
and aggregate to 84% (needs 85%). This plan fixes the single remaining wording
issue, re-runs the evaluation, and makes the final model selection.

**Closest model from Phase 0d:** `gpt-5.4-nano` at 84% aggregate (needs 85%),
C3=67% (needs 75%). Both failures are write-guard regressions on B1/D4.
Estimated score after fix: ~93% aggregate, C3=100%.

**Prerequisite**: Phase 0d merged to `main` — all fixes in place.
Worktree is a fresh checkout of `main` via `.worktrees/phase-0e`.

**Exit criterion**: `python -m eval.harness --all` runs cleanly, at least one
model passes ≥ 85% aggregate and ≥ 75% per criterion, and `docs/DECISIONS.md`
records the chosen model with full justification.

## 1. Requirements & Constraints

- **REQ-001**: After the fix, B1 must pass C1, C2, and C3 for all 6 models.
  B1 is the canonical "all info present" scenario — no model should refuse
  to call write tools when the user has provided name, email, role, and
  committee.
- **REQ-002**: After the fix, C1 and C3 must still pass C4 for at least 4/6
  models. The write-guard must continue to catch missing-information cases.
- **REQ-003**: No scenario's `expected` fields may change in this plan.
  All scenario ground truth is frozen after Phase 0d (CON-001 carries over).
- **REQ-004**: All 40 unit tests must pass without modification.
- **REQ-005**: Decision rule unchanged: cheapest model passing ≥ 85% aggregate
  AND ≥ 75% per criterion (C1–C4). Nano < mini < reasoning tier ordering.
- **CON-001**: The write-guard reword must use general language only. No
  specific scenario IDs, delegate IDs, or argument values. Tool names are
  acceptable (they are real production tool names).
- **CON-002**: All code changes are in the worktree at `.worktrees/phase-0e`
  on branch `feature/phase-0e-eval-fix-and-model-selection`. Run commands
  from that directory.
- **CON-003**: The reworded write-guard must fit within the existing 4-line
  continuation string structure in SYSTEM_PROMPT. Each line ≤ 79 characters
  (PEP 8 project rule, including 4-space indent and surrounding quotes).
- **GUD-001**: Run the targeted B1/B2 check immediately after rewording to
  confirm B1 passes before spending credits on the full `--all` run.
- **GUD-002**: Run the targeted C1/C3 missing_information check to confirm
  the write-guard still catches missing-info cases after rewording.

## 2. Implementation Steps

### Phase 1: Reword Write-Guard in SYSTEM_PROMPT

- **GOAL-001**: Replace the over-restrictive write-guard with a two-sentence
  form that explicitly permits write tools when info is present and prohibits
  them only when info is missing.

**Root cause**: The Phase 0d write-guard reads:
```
" Do not call any tool that creates or modifies data unless the"
" user has explicitly provided all required fields. If any"
" required information is missing, ask the user for it instead"
" of making the tool call."
```

The phrase "unless the user has *explicitly* provided" is interpreted too
strictly by `gpt-5.4-nano` — it refuses to call write tools even when all
fields are present in the user's message. The fix is to invert the logic:
lead with the permission case, then state the restriction.

**Current value** (lines 44–47 of `eval/harness.py`, before closing `)`):
```python
    " Do not call any tool that creates or modifies data unless the"
    " user has explicitly provided all required fields. If any"
    " required information is missing, ask the user for it instead"
    " of making the tool call."
```

**New value** (same 4 lines, same position):
```python
    " When all required information is available, call the"
    " appropriate creation or modification tool directly. If any"
    " required field is missing, ask the user for it before"
    " making the tool call."
```

Line-length check (including 4-space indent + quotes):
- Line 44: `    " When all required information is available, call the"` = 55 chars ✓
- Line 45: `    " appropriate creation or modification tool directly. If any"` = 63 chars ✓
- Line 46: `    " required field is missing, ask the user for it before"` = 58 chars ✓
- Line 47: `    " making the tool call."` = 25 chars ✓

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `eval/harness.py`, replace the 4 write-guard continuation strings (lines 44–47) with the new wording above. Verify line lengths ≤ 79 chars. Verify Python syntax (`py_compile`). Commit: `"Reword write-guard: permit write tools when info present, ask only when missing"`. | ✅ | 2026-04-09 |

### Phase 2: Regression Check

- **GOAL-002**: Confirm the reworded write-guard fixes B1/D4 regressions
  without breaking the missing-information guard on C1/C3.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-002 | Run `python -m pytest tests/ -q`. All 40 tests must pass. | ✅ | 2026-04-09 |
| TASK-003 | Run `python -m eval.harness --model gpt-5.4-nano --category multi_step_sequencing --output eval/results/`. Confirm B1 PASSES C1, C2, and C3. If B1 still fails C1/C2/C3 for `gpt-5.4-nano`, diagnose — the model may need a stronger positive permission signal; adjust wording and re-run. | ✅ | 2026-04-09 |
| TASK-004 | Run `python -m eval.harness --model gpt-5.4-nano --category missing_information --output eval/results/`. Confirm C1 and C3 still show C4 results consistent with Phase 0d (C3 passes C4; C1 may still fail C4 — that is acceptable). If C3 regresses on C4, strengthen the ask-first clause. | ✅ | 2026-04-09 |

### Phase 3: Full Evaluation Run

- **GOAL-003**: Execute the complete evaluation across all 6 models with the
  reworded write-guard.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | From `.worktrees/phase-0e`, run `python -m eval.harness --all --output eval/results/ 2>&1 \| tee eval/results/run_log_2026-04-09c.txt`. Expected duration: 30–60 min. | ✅ | 2026-04-09 |
| TASK-006 | Verify output files: `eval/results/results_*.json` and `eval/results/summary_*.md`. Check for TIMEOUT or ERROR lines — if > 3 scenarios skipped per model, note that model's score as unreliable. | ✅ | 2026-04-09 |

### Phase 4: Model Selection & Documentation

- **GOAL-004**: Apply the decision rule, select the model, and document
  the decision.

**Decision rule** (unchanged from Phase 0 spec):
1. `aggregate_score >= 0.85` (85%)
2. All criterion pass rates `>= 0.75` (75%) individually (C1–C4)
3. Among qualifying models, select cheapest tier (nano < mini < reasoning)
4. Within same tier, prefer higher aggregate score

**Cost tiers:**
- nano: `gpt-5.4-nano`, `gpt-4.1-nano`
- mini: `gpt-5.4-mini`, `gpt-4.1-mini`, `grok-3-mini`
- reasoning: `o4-mini`

**Expected leading candidate:** `gpt-5.4-nano` (nano tier). Phase 0d showed
84% aggregate and C3=67%, both caused by B1/D4 write-guard regressions.
After reword: B1 and D4 should pass, restoring C3 to ~100% and aggregate
to ~93%.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Read `eval/results/summary_*.md`. Apply decision rule: (a) list models with aggregate ≥ 85%, (b) filter to those with all per-criterion rates ≥ 75%, (c) select cheapest qualifying tier. If no model qualifies, go to TASK-010. | ✅ | 2026-04-09 |
| TASK-008 | Update `docs/DECISIONS.md`. Append a new dated entry with: chosen model, aggregate score, per-criterion scores (C1–C4), cost tier, noted weaknesses, results file path. | ✅ | 2026-04-09 |
| TASK-009 | Update `docs/BACKLOG.md`. Mark Phase 0e complete. Add note that Phase 1 can begin with the selected model. | ✅ | 2026-04-09 |
| TASK-010 | **Fallback (if no model qualifies)**: Document closest model and remaining gaps in `docs/DECISIONS.md`. Add Phase 0f entry to `docs/BACKLOG.md`. Do not invent a passing model. | ✅ | 2026-04-09 |
| TASK-011 | Update this plan: mark all tasks complete. Commit: `"Complete Phase 0e: [model name] selected for Phase 1"` (or fallback message). | ✅ | 2026-04-09 |

## 3. Alternatives

- **ALT-001**: Revert to the Phase 0c write-guard (softer "before calling…
  confirm" wording). Rejected: Phase 0d showed the softer wording failed to
  catch C4 violations for several models (C3 was failing C4). The new wording
  must be both permissive on B1 and restrictive on C1/C3.
- **ALT-002**: Remove the write-guard entirely and rely on model defaults.
  Rejected: Phase 0c showed universal C4 failures without any write-guard.
  The guard is necessary; only the wording needs adjustment.
- **ALT-003**: Add explicit tool names (`create_delegate`,
  `create_document_access_rights`) to the write-guard. Deferred: the general
  phrasing ("creation or modification tool") is cleaner and more
  production-realistic. Name-specific guards risk over-fitting to the eval.
- **ALT-004**: Add an access-classification rule to SYSTEM_PROMPT to fix
  D1/D3/D5 `classification_level` failures. Deferred to Phase 1 / MCP KB —
  these are genuine model knowledge gaps, not eval design issues. They do not
  block model selection if the aggregate clears 85%.

## 4. Dependencies

- **DEP-001**: Phase 0d branch merged to `main` — all Phase 0d fixes
  (D1–D3 committee mapping, A5 two-step, write-guard) in place.
- **DEP-002**: Azure AI Foundry project with all 6 models deployed.
- **DEP-003**: Azure CLI credentials active (`az login` done in session).

## 5. Files

- **FILE-001**: `eval/harness.py` — SYSTEM_PROMPT write-guard lines 44–47
  replaced with the two-sentence permission-then-restriction form (TASK-001).
- **FILE-002**: `eval/results/results_*.json` — generated output, gitignored.
- **FILE-003**: `eval/results/summary_*.md` — generated output, gitignored.
- **FILE-004**: `eval/results/run_log_2026-04-09c.txt` — full run log,
  gitignored.
- **FILE-005**: `docs/DECISIONS.md` — updated with final model selection
  (TASK-008).
- **FILE-006**: `docs/BACKLOG.md` — Phase 0e marked complete (TASK-009).

## 6. Testing

- **TEST-001**: `python -m pytest tests/ -q` — all 40 existing unit tests
  must pass. The write-guard reword does not affect unit tests (they test
  evaluator logic, not SYSTEM_PROMPT content). Validates no code regression.
- **TEST-002**: Targeted `multi_step_sequencing` run (TASK-003) — B1 passes
  C1, C2, C3 for `gpt-5.4-nano`. This is the primary regression guard for
  the write-guard reword.
- **TEST-003**: Targeted `missing_information` run (TASK-004) — C3 still
  passes C4 for `gpt-5.4-nano`. Ensures the ask-first behaviour is preserved.

## 7. Risks & Assumptions

- **RISK-001**: The reworded write-guard may cause a different model to
  over-apply or under-apply. Mitigation: TASK-003 and TASK-004 check
  `gpt-5.4-nano` (the leading candidate) before the full run.
- **RISK-002**: `gpt-5.4-nano` B1 failure may not be solely due to the
  write-guard — the model may also have a general reluctance to call write
  tools. Mitigation: if B1 still fails after the reword, diagnose the actual
  tool calls and agent response before adjusting wording further.
- **RISK-003**: No model qualifies after the fix. Mitigation: TASK-010
  (fallback path) — document gaps and plan Phase 0f. The write-guard is the
  only remaining eval design issue; if nano still fails after fixing it, the
  remaining gaps are genuine model weaknesses.
- **ASSUMPTION-001**: `gpt-5.4-nano`'s B1 and D4 failures in Phase 0d are
  caused solely by the over-restrictive write-guard wording, not by an
  inherent model refusal to call write tools. Evidence: B1 passed for
  `gpt-5.4-nano` in Phase 0b and 0c (before any write-guard); the failure
  appeared exactly when the stronger wording was introduced in Phase 0d.
- **ASSUMPTION-002**: The 40 unit tests do not hard-code SYSTEM_PROMPT
  content and will pass after TASK-001.

## 8. Related Specifications / Further Reading

- [Phase 0d Results Summary](../eval/results/summary_2026-04-09.md) —
  decision matrix from the Phase 0d run (local, gitignored).
- [Phase 0 Specification](../docs/PHASE0-MODEL-EXPLORATION.md) —
  source of truth for criteria (S4) and decision rules.
- [Phase 0d Implementation Plan](feature-phase0d-eval-fix-and-model-selection-1.md)
  — predecessor plan; all Phase 0d fixes are in place on `main`.
- [Decision Log](../docs/DECISIONS.md) — Phase 0d findings documented;
  Phase 0e decision will be added here.
- [Backlog](../docs/BACKLOG.md) — Phase 0e task list tracked here.
