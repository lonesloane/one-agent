---
goal: Phase 4D — create-side integration tests (5 DAR scenarios) + docs closure
version: 1.0
date_created: 2026-04-24
owner: Stephane
status: 'Deprecated'
tags: [feature, phase4, agent, integration-tests, docs]
---

# Introduction

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red) — superseded by plan/spike-stock-stack-validation-1.md (2026-04-28)

Phase 4D closes the create side with integration tests that drive the agent
end-to-end across all 5 DAR scenarios using a mock chat client (same
`eval/` harness pattern if applicable), verifies HITL observation through
the middleware, and updates `docs/BACKLOG.md` + `docs/DESIGN.md` +
`docs/DECISIONS.md`.

Spec: `docs/prd-phase4-write-agent.md` §3 (Evaluation Strategy), §4
(Sub-phase 4D), "Phase 4 done" create-side checklist.

## 1. Requirements & Constraints

- **REQ-001**: Add `tests/agent_app/test_create_integration.py` driving the
  agent through the 5 PRD DAR scenarios using a mock chat client (pattern
  reuse from Phase 3E or the existing `eval/` harness — whichever is
  lightest).
- **REQ-002**: Each scenario test must assert: (a) tool call events for
  `create_delegate` + `create_document_access_rights` observed;
  (b) HITL approval events observed before each write; (c) final
  `classification_level` + `approval_status` persisted to DB match the
  PRD scenario expectation.
- **REQ-003**: Add `tests/agent_app/test_audit_trail.py` verifying the
  existing `AuditMiddleware` logs the create-tool calls with tool name,
  arguments, and result (pattern from Phase 3A `TestAuditMiddleware`).
- **REQ-004**: `docs/BACKLOG.md` Phase 4 create-side items checked with
  today's date.
- **REQ-005**: `docs/DESIGN.md` "Current state" section mentions create-
  side write tools + HITL, with one-sentence reference to the prompt's
  Create Side section.
- **REQ-006**: `docs/DECISIONS.md` new entry if any 4A/4B/4C decision
  deviated from the PRD (e.g. alternative ID-generation strategy). If
  nothing deviated, skip.
- **CON-001**: Integration tests must not require Foundry credentials.
  Use a mock chat client that returns canned tool-call sequences.
- **PAT-001**: Reuse `eval/` harness if it already drives the agent; do
  not add a new client abstraction unless forced.

## 2. Implementation Steps

### Implementation Phase 1 — Scenario integration tests

- GOAL-001: All 5 scenarios green end-to-end.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Audit whether `eval/` harness can replay canned tool-call sequences against the full `agent_app.agent.create_agent()` pipeline. If yes, adopt; if no, build a minimal `FakeChatClient` that emits a predetermined sequence of `FunctionCall` items. | | |
| TASK-002 | Create `tests/agent_app/test_create_integration.py`. Fixture: `seeded_engine` (member + partner + partner-with-FA delegations), `editor_delegate` (role=DELEGATION_EDITOR). | | |
| TASK-003 | Implement `TestCreateScenarios` parametrised over the 5 PRD cases. Each parametrisation: input conversation snippet, expected `(classification_level, approval_status)` tuple, expected HITL approval events observed. | | |
| TASK-004 | Assert HITL observation: mock the HITL responder to auto-approve; capture emitted events via middleware or AG-UI replay; assert an approval-request event precedes the tool execution for each of the 2 write tools per scenario. | | |

### Implementation Phase 2 — Audit trail + HITL denial path

- GOAL-002: Audit middleware captures, denial paths covered.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `tests/agent_app/test_audit_trail.py`. Run one create-delegate scenario; capture loguru output via `caplog` or custom sink; assert log lines contain `tool=create_delegate`, the serialized args, and the returned ID. | | |
| TASK-006 | Add `TestHITLDenial`: auto-deny the HITL event; assert no `Delegate` row persists; assert agent final message surfaces an acknowledgement (not an exception). | | |

### Implementation Phase 3 — Docs closure

- GOAL-003: BACKLOG / DESIGN / DECISIONS reflect shipped create side.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Edit `docs/BACKLOG.md`: check every Phase 4 create-side item. Add a "Create side merged YYYY-MM-DD" entry with the merge commit hash. | | |
| TASK-008 | Edit `docs/DESIGN.md` "Current state": append one paragraph covering create-side write tools, HITL gating, and audit-middleware coverage. | | |
| TASK-009 | Edit `docs/DECISIONS.md` only if a deviation landed (e.g. ID-generator path); otherwise leave untouched. | | |
| TASK-010 | Run full suite: `pytest` — all previous + new tests green. Record final test count. | | |

## 3. Alternatives

- **ALT-001**: Drive integration tests via Playwright. Rejected — too slow,
  too flaky, and duplicates the Phase 3E e2e harness; unit-level
  integration with FakeChatClient is sufficient for scenario coverage.

## 4. Dependencies

- **DEP-001**: Phase 4A + 4B + 4C merged.
- **DEP-002**: `eval/` harness or equivalent mock-client pattern available.

## 5. Files

- **FILE-001**: `tests/agent_app/test_create_integration.py` — new, ~300
  lines
- **FILE-002**: `tests/agent_app/test_audit_trail.py` — new, ~80 lines
- **FILE-003**: `docs/BACKLOG.md` — check items + merge entry
- **FILE-004**: `docs/DESIGN.md` — current-state paragraph
- **FILE-005**: `docs/DECISIONS.md` — only if a deviation landed

## 6. Testing

- **TEST-001**: `TestCreateScenarios` — 5-scenario integration matrix
- **TEST-002**: `TestHITLDenial` — denial path aborts write
- **TEST-003**: `test_audit_trail` — logs captured for write tools

## 7. Risks & Assumptions

- **RISK-001**: FakeChatClient drift from real Foundry client behavior.
  Mitigation: keep scenario conversations minimal; cover real-model drift
  in the separate demo dry-run.
- **ASSUMPTION-001**: `docs/BACKLOG.md` Phase 4 create-side items exist to
  be checked; if not, TASK-007 also adds them.

## 8. Related Specifications / Further Reading

- `docs/prd-phase4-write-agent.md` §3 Evaluation Strategy + "done" list
- `eval/` harness — pattern source
- Phase 3E e2e plan — integration-test reference
- Phase 4E plan: `plan/feature-phase4e-approver-seed-list-tool-1.md`
