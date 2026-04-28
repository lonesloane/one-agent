---
goal: Phase 3D — proactive brief integration tests, grounding assertion, system prompt refinement, and doc closure
version: 1.0
date_created: 2026-04-20
owner: Stephane
status: 'Planned'
tags: [feature, phase3, tests, brief-logic, integration, docs]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 3D locks in correctness and closes Phase 3. It delivers integration
tests for the proactive brief trigger/suppress logic, a grounding assertion
that the agent never invents document titles not in tool results, a final
system prompt review, and closure of all documentation (`docs/DESIGN.md`,
`docs/BACKLOG.md`, `docs/DECISIONS.md`). Exit criterion: ≥ 20 new tests
total across Phase 3; full suite (188 baseline + all new) green;
`docs/DESIGN.md` "Current state" updated to Phase 3.

Spec: `docs/prd-phase3-read-agent.md` §3 (Evaluation Strategy), §5
(3D exit criterion), and the "Phase 3 is done" checklist.

## 1. Requirements & Constraints

- **REQ-001**: `tests/agent_app/test_brief_logic.py` must include:
  (a) brief fires when ≥ 1 new document exists within lookback;
  (b) brief suppressed (greeting only) when no new documents exist;
  (c) brief suppressed when no upcoming meetings exist for delegate.
- **REQ-002**: Grounding test: assert agent response mentions only
  document titles present in the mocked `get_agenda_documents` result;
  assert no document title absent from mock appears in the response.
- **REQ-003**: Document visibility test (integration level): assert a
  delegate lacking a DAR for a RESTRICTED document does not receive that
  document in the brief, even when the meeting has upcoming items.
- **REQ-004**: Final test count: ≥ 20 new tests added across all of
  Phase 3 (3A contributes ≥ 10; 3D contributes ≥ 10).
- **REQ-005**: `docs/DESIGN.md` "Current state" section updated to reflect
  Phase 3 completion (agent_app package, FastAPI server, CopilotKit
  frontend).
- **REQ-006**: `docs/BACKLOG.md` Phase 3 items checked off with date
  2026-04-XX.
- **CON-001**: Integration tests use a mock agent client (not live Azure
  AI Foundry calls). Use `unittest.mock.patch` to mock the LLM call;
  assert tool sequence and output shape, not exact LLM text.
- **CON-002**: Do NOT rewrite the system prompt from scratch. Review it
  and make targeted edits only.
- **GUD-001**: Follow CLAUDE.md: Google docstrings, type hints, PEP 8,
  79-char lines.

## 2. Implementation Steps

### Implementation Phase 1 — System Prompt Review

- GOAL-001: Confirm SYSTEM_PROMPT in `agent_app/agent.py` encodes all
  five required sections from PRD §3 and is accurate after Phase 3A/3B/3C.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Open `agent_app/agent.py`. Verify `SYSTEM_PROMPT` contains all five required sections: (1) domain model, (2) access-classification rule, (3) proactive brief instruction with `BRIEF_LOOKBACK_DAYS` reference, (4) write-guard, (5) grounding rule. Add or sharpen any section that is missing or vague. | | |
| TASK-002 | Verify the proactive brief instruction in `SYSTEM_PROMPT` explicitly states the tool call sequence: `lookup_delegate` → `get_upcoming_meetings` → `get_agenda_documents` per meeting → filter by lookback → stream or greet. | | |

### Implementation Phase 2 — Brief Trigger / Suppress Tests

- GOAL-002: Programmatic assertion that brief fires only when new documents
  exist within the lookback window.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Create `tests/agent_app/test_brief_logic.py`. Add module docstring and `conftest`-compatible in-memory DB fixture (reuse pattern from `tests/shared/conftest.py` with `get_engine("sqlite:///:memory:")` + `init_db` + `seed_data`). | | |
| TASK-004 | Add `TestBriefFiresWithNewDocuments`: set up a delegate, upcoming meeting, and an agenda document with `last_modified = datetime.now(UTC)` (within lookback). Mock `get_agenda_documents` to return this document. Mock the LLM response. Assert: (a) `get_upcoming_meetings` tool was called, (b) `get_agenda_documents` tool was called for each meeting, (c) the agent response includes the document title. | | |
| TASK-005 | Add `TestBriefSuppressedNoNewDocuments`: same setup but document `last_modified` is 30 days ago (outside `BRIEF_LOOKBACK_DAYS=7`). Assert: agent response is greeting only and does NOT include any document title. | | |
| TASK-006 | Add `TestBriefSuppressedNoMeetings`: delegate has no committee participations (or no upcoming meetings). Assert: `get_agenda_documents` is never called; agent response is greeting only. | | |

### Implementation Phase 3 — Grounding & Visibility Tests

- GOAL-003: Agent cannot invent document titles; DAR enforcement verified
  at the integration boundary.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add `TestGrounding`: mock `get_agenda_documents` to return exactly two documents with known titles `["Alpha Report", "Beta Minutes"]`. Mock LLM to respond with the exact tool-returned titles. Assert none of `["Gamma Policy", "Delta Brief"]` (titles not in the mock) appear in the response. (This tests the grounding rule is respected by checking the test fixture, not the model — model grounding is validated manually in Phase 3C.) | | |
| TASK-008 | Add `TestDARVisibilityEnforcement`: create two delegates — Delegate A has a RESTRICTED DAR; Delegate B has no DAR. Seed one RESTRICTED document and one GENERAL document on the same meeting. Call `get_agenda_documents` directly for each delegate (not via mock). Assert Delegate A receives both documents; Delegate B receives only the GENERAL document. This is a tool-layer integration test, not an agent test. | | |

### Implementation Phase 4 — Additional Edge Cases

- GOAL-004: Reach ≥ 20 new tests for Phase 3; cover remaining edge cases.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Add `TestMultipleMeetingsBrief`: delegate participates in 2 committees, each with an upcoming meeting; both have new documents. Assert both meetings appear in the brief. | | |
| TASK-010 | Add `TestDelegateNotFound`: `lookup_delegate` called with unknown ID returns JSON indicating not found; agent response is a polite "delegate not found" message (no crash). | | |
| TASK-011 | Count total new tests across `tests/agent_app/test_tools.py` (Phase 3A) and `tests/agent_app/test_brief_logic.py` (Phase 3D). If total < 20, add missing tests for uncovered paths (e.g., `get_delegation_info` with partner + active FA, `get_upcoming_meetings` past meetings excluded). | | |

### Implementation Phase 5 — Full Suite Run & Doc Closure

- GOAL-005: Green suite; documentation closed.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Run `pytest` from project root with `.venv` active. All tests must pass. Record final count. | | |
| TASK-013 | Update `docs/DESIGN.md`: add Phase 3 to "Current state" section. Describe `agent_app/` package, FastAPI AG-UI server, CopilotKit frontend, and AG-UI identity threading pattern. | | |
| TASK-014 | Update `docs/BACKLOG.md`: check off all Phase 3 items with completion date 2026-04-XX. | | |
| TASK-015 | Update `docs/DECISIONS.md`: confirm OQ-7 (frontend technology) is marked resolved with AG-UI + CopilotKit rationale if not already done. | | |

## 3. Alternatives

- **ALT-001**: Use live Azure AI Foundry calls in integration tests. Rejected
  — non-deterministic, slow, requires network; mock-client tests are
  sufficient to verify tool sequence and output shape.
- **ALT-002**: Test grounding by asserting LLM output contains no invented
  data via regex on real LLM calls. Rejected in Phase 3; deferred to
  Phase 3's eval harness extension (post-PoC).

## 4. Dependencies

- **DEP-001**: Phase 3A complete — tools and agent importable; ≥ 10 tests
  already in `tests/agent_app/test_tools.py`.
- **DEP-002**: Phase 3B complete — server confirmed working end-to-end.
- **DEP-003**: Phase 3C complete — streaming brief visually confirmed.
- **DEP-004**: `pytest>=8.0`, `pytest-asyncio>=0.24` — already in
  `pyproject.toml` dev extras.

## 5. Files

- **FILE-001**: `agent_app/agent.py` — targeted SYSTEM_PROMPT edits only
- **FILE-002**: `tests/agent_app/test_brief_logic.py` — new, ≥ 10 tests
- **FILE-003**: `docs/DESIGN.md` — Phase 3 "Current state" update
- **FILE-004**: `docs/BACKLOG.md` — Phase 3 items checked off
- **FILE-005**: `docs/DECISIONS.md` — OQ-7 confirmed resolved

## 6. Testing

- **TEST-001**: `TestBriefFiresWithNewDocuments` — brief fires when
  new docs exist
- **TEST-002**: `TestBriefSuppressedNoNewDocuments` — greeting only when
  no new docs
- **TEST-003**: `TestBriefSuppressedNoMeetings` — greeting only when no
  upcoming meetings
- **TEST-004**: `TestGrounding` — response contains only tool-returned
  document titles
- **TEST-005**: `TestDARVisibilityEnforcement` — tool-layer integration;
  RESTRICTED blocked for delegate without DAR
- **TEST-006**: `TestMultipleMeetingsBrief` — both meetings appear in brief
- **TEST-007**: `TestDelegateNotFound` — graceful not-found handling
- **TEST-008**: Full suite green (`pytest`) with ≥ 20 new tests total

## 7. Risks & Assumptions

- **RISK-001**: Mock agent client API for the brief trigger tests may not
  be available if `agent_framework` does not expose a test-friendly
  client. Mitigation: test the tool sequence directly (call tools with
  mock DB; assert output shape) rather than running the full agent loop.
- **ASSUMPTION-001**: Phase 3A delivers ≥ 10 tests; Phase 3D needs ≥ 10
  more to reach the 20-test requirement.
- **ASSUMPTION-002**: `docs/DESIGN.md`, `docs/BACKLOG.md`, and
  `docs/DECISIONS.md` exist and follow the same format as Phase 2D
  closures.

## 8. Related Specifications / Further Reading

- `docs/prd-phase3-read-agent.md` — §3 Evaluation Strategy, §5 checklist
- Phase 3A plan: `plan/feature-phase3a-tools-agent-1.md`
- `shared/business_rules.py` — `get_new_documents_since` (lookback logic)
- `tests/shared/conftest.py` — in-memory DB fixture pattern
- `plan/completed/feature-phase2d-tests-and-demo-smoke-1.md` — Phase 2D
  doc-closure precedent
