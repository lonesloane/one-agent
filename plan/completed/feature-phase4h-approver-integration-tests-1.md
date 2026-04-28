---
goal: Phase 4H — approver-side integration tests (approve, reject, scope violation, visibility propagation) + docs closure
version: 1.0
date_created: 2026-04-24
owner: Stephane
status: 'Deprecated'
tags: [feature, phase4, agent, integration-tests, docs]
---

# Introduction

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red) — superseded by plan/spike-stock-stack-validation-1.md (2026-04-28)

Phase 4H closes Phase 4 with approver-side integration tests driving the
full stack (FakeChatClient + real agent pipeline) through approve, reject,
scope-violation, and visibility-propagation flows, and updates
`docs/BACKLOG.md` + `docs/DESIGN.md` + `docs/DECISIONS.md`.

Spec: `docs/prd-phase4-write-agent.md` §3 Evaluation Strategy, §4
Sub-phase 4H, "Phase 4 done" checklist (approver + cross-cutting).

## 1. Requirements & Constraints

- **REQ-001**: Add `tests/agent_app/test_approver_integration.py` with
  four parametrised integration tests: approve flow, reject flow,
  out-of-scope flow, visibility propagation flow.
- **REQ-002**: Each test uses the FakeChatClient pattern introduced in 4D
  and real `create_agent()` pipeline; asserts tool-call ordering, HITL
  events observed, and resulting DB state.
- **REQ-003**: Out-of-scope flow must assert the tool raises
  `PermissionError("out_of_scope")`, the agent surfaces the error to the
  user, and no DB state changes.
- **REQ-004**: Visibility propagation flow: approve a PENDING_* DAR for a
  Restricted document; assert `is_document_visible(delegate, doc,
  session) == True` post-approval. Reject scenario: assert `False` post-
  rejection.
- **REQ-005**: Playwright e2e (`tests/e2e/`) gets one optional happy-path
  spec: approver persona → picker shows badge → brief shows pending DAR →
  click approve → HITL dialog → approve → DAR reflected. Only add if
  trivially extendable from Phase 3E harness; otherwise defer.
- **REQ-006**: `docs/BACKLOG.md` Phase 4 approver items checked; add
  "Phase 4 merged YYYY-MM-DD" entry with commit hash.
- **REQ-007**: `docs/DESIGN.md` "Current state" updated to reflect full
  Phase 4 delivery (create + approve flows, approver personas, badge).
- **REQ-008**: `docs/DECISIONS.md` appended with any 4E-4G decision that
  deviated from PRD (e.g. inline `(N pending)` label vs HTML badge;
  sentinel secretariat delegation placement).
- **CON-001**: No new production code — 4H is tests + docs only.

## 2. Implementation Steps

### Implementation Phase 1 — Integration tests

- GOAL-001: Four end-to-end flows green.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `tests/agent_app/test_approver_integration.py`. Reuse FakeChatClient + seeded engine fixtures from 4D. | | |
| TASK-002 | `TestApproveFlow`: head persona → observes `list_pending_dars` tool call (from brief) → user says "approve DAR-XXXX" → `approve_dar` tool call → HITL approval event → DB status flip assertion. | | |
| TASK-003 | `TestRejectFlow`: same but rejection, including reason capture in DB. | | |
| TASK-004 | `TestOutOfScopeFlow`: head persona attempts to approve a DAR from another delegation → tool raises `PermissionError` → agent surfaces the error message → no DB state change. | | |
| TASK-005 | `TestVisibilityPropagation`: approve a Restricted-doc DAR → assert `is_document_visible` returns True → then run `get_agenda_documents` tool for the same delegate and meeting, confirm the document now appears in the result JSON. | | |

### Implementation Phase 2 — Optional Playwright happy path

- GOAL-002: One e2e smoke if cheap; otherwise skip.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Evaluate cost of extending `tests/e2e/` (Phase 3E) with an approver happy-path spec. If framework already exposes the hooks needed to auto-approve the HITL dialog, add `test_approver_happy_path.py`. Otherwise record as "deferred" in BACKLOG. | | |

### Implementation Phase 3 — Docs closure

- GOAL-003: All Phase 4 docs reconciled.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Edit `docs/BACKLOG.md`: check every Phase 4 approver + cross-cutting item. Add merge entry. | | |
| TASK-008 | Edit `docs/DESIGN.md` "Current state": one paragraph covering approver personas, `list_pending_dars`, approve/reject HITL, pending-count badge, scope enforcement. | | |
| TASK-009 | Edit `docs/DECISIONS.md`: log deviations from PRD (e.g. inline badge text, sentinel delegation, DAR audit columns) with date + rationale. | | |
| TASK-010 | Run full suite: `pytest`. Record final test count in the merge commit message. | | |
| TASK-011 | Spot-check the demo dry-run script: 5 create scenarios + approve + reject + out-of-scope. Update `plan/completed/` once merged. | | |

## 3. Alternatives

- **ALT-001**: Replace FakeChatClient integration tests with full-stack
  Playwright-only e2e. Rejected — slow, flaky; FakeChatClient gives
  deterministic ordering assertions that Playwright cannot express
  cleanly.

## 4. Dependencies

- **DEP-001**: Phases 4A–4G merged.
- **DEP-002**: 4D's FakeChatClient harness present and reusable.

## 5. Files

- **FILE-001**: `tests/agent_app/test_approver_integration.py` — new,
  ~400 lines
- **FILE-002**: `tests/e2e/test_approver_happy_path.py` — optional, only
  if cheap
- **FILE-003**: `docs/BACKLOG.md` — checks + merge entry
- **FILE-004**: `docs/DESIGN.md` — current-state paragraph
- **FILE-005**: `docs/DECISIONS.md` — Phase 4 deviations log

## 6. Testing

- **TEST-001**: `TestApproveFlow`
- **TEST-002**: `TestRejectFlow`
- **TEST-003**: `TestOutOfScopeFlow`
- **TEST-004**: `TestVisibilityPropagation`
- **TEST-005**: (optional) e2e approver happy path

## 7. Risks & Assumptions

- **RISK-001**: FakeChatClient cannot accurately model Foundry streaming
  quirks. Mitigation: keep assertions at the level of tool-call sequence
  + DB state, not streaming timing.
- **ASSUMPTION-001**: Phase 3E e2e harness supports auto-approving HITL
  dialogs via Playwright locators. To be verified in TASK-006.

## 8. Related Specifications / Further Reading

- `docs/prd-phase4-write-agent.md` §3 Evaluation Strategy + "done" list
- Phase 4D plan: `plan/feature-phase4d-create-integration-tests-1.md`
- Phase 3E plan: `plan/completed/feature-phase3e-copilotkit-e2e-playwright-1.md`
