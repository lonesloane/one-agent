---
goal: Phase 4G — approver-side system prompt branch, proactive brief on session start, picker pending-count badge
version: 1.0
date_created: 2026-04-24
owner: Stephane
status: 'Deprecated'
tags: [feature, phase4, agent, prompt, frontend, badge]
---

# Introduction

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red) — superseded by plan/spike-stock-stack-validation-1.md (2026-04-28)

Phase 4G extends `SYSTEM_PROMPT` with the approver-side branch and a
proactive-brief instruction that auto-fires `list_pending_dars` on session
start for `DELEGATION_HEAD` / `SECRETARIAT` personas, extends
`/api/delegates` to include `pending_dar_count`, and renders the count
badge next to approver personas in the frontend picker. Exit criterion:
brief auto-fires for approver personas; picker badge shows the correct
count; non-approver personas get no brief and no badge.

Spec: `docs/prd-phase4-write-agent.md` §2 US-2 + US-4, §3 System Prompt
Requirements, §4 Sub-phase 4G, §5 RISK "brief fires for non-approver".

## 1. Requirements & Constraints

- **REQ-001**: `agent_app/agent.py::SYSTEM_PROMPT` must gain an
  `## Approver Side (Delegation Head / Secretariat)` section covering:
  proactive brief protocol (on session start, if persona role is
  `DELEGATION_HEAD` or `SECRETARIAT`, call `list_pending_dars` immediately
  and stream a grouped-by-delegate summary; if empty, greet and say
  "No pending approvals"), per-DAR approve/reject offer, HITL write-guard
  reminder, scope-error handling ("If a write returns `out_of_scope`,
  report it to the user and do not retry").
- **REQ-002**: `## Proactive Session Brief` (Phase 3 block) must be
  restructured to branch on persona role: editor → existing new-documents
  brief (unchanged); head / secretariat → pending-DAR brief (new).
- **REQ-003**: `agent_app/server.py::DelegateOut` must gain
  `pending_dar_count: int` populated via
  `count_pending_dars_for_approver` (Phase 4E). Field is `0` for
  non-approver personas.
- **REQ-004**: `/api/delegates` query must be efficient — one subquery or
  a per-row count; no N+1.
- **REQ-005**: `agent_app/frontend/app/components/DelegatePicker.tsx` must
  render a count badge after the role label for approver personas when
  `pending_dar_count > 0`. Badge hidden for editors / zero counts.
- **REQ-006**: `DelegatePicker.module.css` must get a `.badge` class with
  OECD-corporate palette (reuse Phase 3.5 CSS vars).
- **REQ-007**: The `Delegate` interface in `DelegatePicker.tsx` gains
  `pending_dar_count: number`.
- **CON-001**: No new API endpoint — reuse `/api/delegates`.
- **CON-002**: Badge is poll-on-open only (no WebSocket); PRD explicitly
  accepts non-live.
- **PAT-001**: Respect `agent_app/frontend/AGENTS.md` — Next.js 16
  breaking-change warning; verify any CopilotKit hook usage via Context7.

## 2. Implementation Steps

### Implementation Phase 1 — System prompt approver branch

- GOAL-001: Persona-gated brief, per-DAR offer, scope-error handling.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Edit `agent_app/agent.py::SYSTEM_PROMPT`: split the existing `## Proactive Session Brief` into two role branches (editor-side vs approver-side). Add explicit instruction: "If role is DELEGATION_HEAD or SECRETARIAT, call list_pending_dars FIRST and summarise before anything else." | | |
| TASK-002 | Add `## Approver Side (Delegation Head / Secretariat)` section: per-DAR action offers, scope-error handling, HITL guard reminder. | | |
| TASK-003 | Extend `tests/agent_app/test_system_prompt.py` with assertions for substrings: `"Approver Side"`, `"list_pending_dars"`, `"out_of_scope"`, `"No pending approvals"`. | | |

### Implementation Phase 2 — /api/delegates pending-count

- GOAL-002: API returns `pending_dar_count` for all personas.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Edit `agent_app/server.py::DelegateOut`: add `pending_dar_count: int`. | | |
| TASK-005 | Edit `get_delegates()`: for each delegate call `count_pending_dars_for_approver(delegate, session)` within the existing session. If profiling shows N-query concern, refactor to a single GROUP BY query; otherwise accept per-row cost for seed-scale data. | | |
| TASK-006 | Add `tests/agent_app/test_server_delegates.py` covering: editor delegate returns `pending_dar_count == 0`; head returns the count of own-delegation pending DARs; secretariat returns count of all PENDING_SECRETARIAT DARs. Use FastAPI `TestClient`. | | |

### Implementation Phase 3 — Frontend badge

- GOAL-003: Picker renders count next to approver personas.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Edit `agent_app/frontend/app/components/DelegatePicker.tsx`: extend `Delegate` interface with `pending_dar_count: number`. Render `{d.pending_dar_count > 0 ? ` (${d.pending_dar_count} pending)` : ""}` at the end of each option label. | | |
| TASK-008 | Edit `agent_app/frontend/app/components/DelegatePicker.module.css`: add `.badge` style using OECD-corporate CSS vars from Phase 3.5 polish; ensure the `<option>` rendering shows the count legibly in the native `<select>` (if CSS cannot style option text, keep the inline parenthesis approach — note as tradeoff). | | |
| TASK-009 | Run Next.js dev server + pick an approver persona; confirm count visible. Screenshot into BACKLOG dry-run findings if UX is off. | | |

### Implementation Phase 4 — Proactive-brief regression test

- GOAL-004: Brief gates on persona role; editor persona produces no brief.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Add `tests/agent_app/test_approver_brief.py`: drive agent with a FakeChatClient-style harness (4D pattern) to observe that for a `DELEGATION_HEAD` persona the first tool call is `list_pending_dars`; for a `DELEGATION_EDITOR` persona it is NOT `list_pending_dars`. | | |
| TASK-011 | Run full suite: `pytest`. | | |

## 3. Alternatives

- **ALT-001**: Custom React badge component. Rejected — native `<select>`
  doesn't style `<option>` children meaningfully; the inline `(N pending)`
  approach is robust and zero-risk.
- **ALT-002**: Compute `pending_dar_count` client-side by fetching all
  DARs. Rejected — server-side is cheaper and matches scope enforcement.

## 4. Dependencies

- **DEP-001**: Phase 4E + 4F merged.
- **DEP-002**: `count_pending_dars_for_approver` helper (4E REQ-004).

## 5. Files

- **FILE-001**: `agent_app/agent.py` — prompt extension (~+80 lines)
- **FILE-002**: `agent_app/server.py` — `DelegateOut` +
  `get_delegates()` extension
- **FILE-003**: `agent_app/frontend/app/components/DelegatePicker.tsx`
- **FILE-004**: `agent_app/frontend/app/components/DelegatePicker.module.css`
- **FILE-005**: `tests/agent_app/test_server_delegates.py` — new
- **FILE-006**: `tests/agent_app/test_approver_brief.py` — new
- **FILE-007**: `tests/agent_app/test_system_prompt.py` — extensions

## 6. Testing

- **TEST-001**: `/api/delegates` count correctness per role
- **TEST-002**: Approver brief fires for heads/secretariat, NOT for
  editors
- **TEST-003**: Prompt substring guard

## 7. Risks & Assumptions

- **RISK-001**: Native `<select>` styling limits force inline `(N pending)`
  string, not a visually distinct badge. Acceptable; PRD accepts polish as
  separate session.
- **RISK-002**: Model may still auto-fire `list_pending_dars` for editors
  despite prompt guard. Mitigation: prompt test in 4G; integration test in
  4H.
- **ASSUMPTION-001**: Phase 3.5 OECD-corporate CSS vars remain the source
  of truth for frontend styling.

## 8. Related Specifications / Further Reading

- `docs/prd-phase4-write-agent.md` §2 US-2 + US-4, §3 System Prompt
- Phase 4E plan: `plan/feature-phase4e-approver-seed-list-tool-1.md`
- Phase 4H plan: `plan/feature-phase4h-approver-integration-tests-1.md`
