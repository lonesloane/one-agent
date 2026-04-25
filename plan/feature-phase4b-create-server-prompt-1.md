---
goal: Phase 4B — server wiring for create side + system prompt create-side branch
version: 1.0
date_created: 2026-04-24
owner: Stephane
status: 'Planned'
tags: [feature, phase4, agent, server, prompt]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 4B wires the two 4A write tools into the running agent instance and
extends the system prompt with a create-side branch that encodes the DAR
rules, the HITL guard, and the elicitation protocol. Exit criterion: full
create flow drivable end-to-end via `curl` / mock client hitting the AG-UI
endpoint; agent correctly elicits missing fields, computes routing, and
requests HITL confirmation before any write.

Spec: `docs/prd-phase4-write-agent.md` §3 (System Prompt Requirements),
§4 (Sub-phase 4B).

## 1. Requirements & Constraints

- **REQ-001**: `agent_app/agent.py` `SYSTEM_PROMPT` must extend with a
  `## Create Side (Delegation Editor)` section covering: elicitation order
  (full_name → email → delegation_id → membership_type → committees →
  desired access levels → retroactive flag), the DAR access-classification
  rule (already present in Phase 3 prompt — reuse), the approval-routing
  rule (`General` auto-approved; `Restricted` → `PENDING_DELEGATION_HEAD`;
  `Confidential` or `retroactive=true` → `PENDING_SECRETARIAT`), and a HITL
  write-guard ("Do not claim a write happened until you observe a
  confirmation event").
- **REQ-002**: `SYSTEM_PROMPT` must include a `## Persona Mode Selection`
  section gating create-side behavior on `DelegateRole.DELEGATION_EDITOR`.
  Approver-side branch is added in Phase 4G.
- **REQ-003**: `create_agent()` must already pick up the extended
  `ALL_TOOLS` list from 4A — no extra wiring needed because
  `agent_app/tools.py::ALL_TOOLS` is the single source of truth.
- **REQ-004**: `agent_app/server.py::/` POST endpoint must continue to
  thread `delegate_id` into `function_invocation_kwargs` (Phase 3B
  `_BoundAgent`). No changes required if 4A uses the same kwarg name.
- **REQ-005**: Add a tiny smoke script `scripts/curl_create_flow.sh` (or
  document inline in plan if script is declined) that POSTs a scripted
  conversation driving the agent through one create scenario.
- **CON-001**: No changes to `agent_app/server.py` routing code (only prose
  docstring touch-ups allowed if necessary).
- **GUD-001**: Keep `SYSTEM_PROMPT` under 300 lines; factor repetitive rule
  prose into bullet lists.
- **PAT-001**: Mirror Phase 3 prompt structure — headed sections, imperative
  voice, numbered steps where ordering matters.

## 2. Implementation Steps

### Implementation Phase 1 — System prompt extension

- GOAL-001: Prompt encodes persona mode + create-side behavior + HITL guard.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `agent_app/agent.py` add `## Persona Mode Selection` section to `SYSTEM_PROMPT`. Text: enumerate `DELEGATION_EDITOR`, `DELEGATION_HEAD`, `SECRETARIAT`; state that the current persona's role is available via the `role` field of `lookup_delegate(current_delegate_id)`; instruct the agent to branch create-side vs approver-side off that role. Note that approver-side detail is specified later. | ✅ | 2026-04-25 |
| TASK-002 | Add `## Create Side (Delegation Editor)` section: elicitation steps, DAR rules, routing rules, HITL guard, failure-reporting rule ("If a write tool returns an error, surface the message and do not retry"). | ✅ | 2026-04-25 |
| TASK-003 | Replace the Phase 3 `## Write Guard` block ("This agent has no write tools") with a new `## HITL Write Guard` block permitting write tools but mandating explicit HITL confirmation language. | ✅ | 2026-04-25 |
| TASK-004 | Re-read `BRIEF_LOOKBACK_DAYS` constant — unchanged. | ✅ | 2026-04-25 |

### Implementation Phase 2 — End-to-end smoke

- GOAL-002: Scripted create flow proven via curl against a running server.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Start server: `uvicorn agent_app.server:app --port 8001`. Hit `GET /api/delegates`; pick a `DELEGATION_EDITOR` persona ID. | | |
| TASK-006 | POST to `/` with an AG-UI request whose `state.delegate_id` is the editor ID and whose messages drive the agent to create a delegate. Capture the SSE stream; confirm a tool-call event for `create_delegate` plus an HITL approval-request event appears before any actual DB write. | | |
| TASK-007 | Approve the HITL event via the AG-UI protocol; confirm `create_delegate` result event streams back; query `/api/delegates` again and verify the new row. | | |
| TASK-008 | Repeat TASK-006 + TASK-007 for `create_document_access_rights` on the newly created delegate, covering one `PENDING_DELEGATION_HEAD` scenario. | | |
| TASK-009 | Document the smoke steps in `docs/BACKLOG.md` Phase 4B exit notes (or keep as plan appendix if BACKLOG updates happen in 4D). | | |

### Implementation Phase 3 — Prompt regression test

- GOAL-003: Guard against accidental prompt removal.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Add `tests/agent_app/test_system_prompt.py` asserting required substrings in `SYSTEM_PROMPT`: `"Persona Mode Selection"`, `"Create Side"`, `"HITL Write Guard"`, `"PENDING_DELEGATION_HEAD"`, `"PENDING_SECRETARIAT"`. | ✅ | 2026-04-25 |
| TASK-011 | Run full suite: `pytest`. | ✅ | 2026-04-25 |

## 3. Alternatives

- **ALT-001**: Split `SYSTEM_PROMPT` into multiple files (e.g. `prompts/`).
  Rejected — premature abstraction; Phase 4 is still a single prompt.
- **ALT-002**: Gate create-side behavior in Python (e.g. swap `ALL_TOOLS`
  list per persona). Rejected — adds per-session branching in server code
  when the prompt can self-gate cleanly.

## 4. Dependencies

- **DEP-001**: Phase 4A merged (write tools present in `ALL_TOOLS`).
- **DEP-002**: Running Foundry creds (`.env` `FOUNDRY_MODEL`,
  `FOUNDRY_PROJECT_ENDPOINT`).

## 5. Files

- **FILE-001**: `agent_app/agent.py` — extend `SYSTEM_PROMPT` (~+100 lines)
- **FILE-002**: `tests/agent_app/test_system_prompt.py` — new, ~40 lines
- **FILE-003**: `scripts/curl_create_flow.sh` (optional) or plan appendix

## 6. Testing

- **TEST-001**: `test_system_prompt` — required substring assertions
- **TEST-002**: Manual curl smoke (TASK-006/007/008) — not automated in 4B;
  full integration tests land in 4D

## 7. Risks & Assumptions

- **RISK-001**: Model may ignore HITL prompt instruction and attempt writes
  without confirmation. Mitigation: framework-level `approval_mode` enforces
  regardless; test in 4D.
- **ASSUMPTION-001**: CopilotKit frontend renders `always_require` HITL
  dialog automatically (to be verified in 4C).

## 8. Related Specifications / Further Reading

- `docs/prd-phase4-write-agent.md` §3 System Prompt Requirements
- `agent_app/agent.py` — Phase 3 prompt baseline
- Phase 4A plan: `plan/feature-phase4a-create-write-tools-1.md`
- Phase 4C plan: `plan/feature-phase4c-create-frontend-hitl-1.md`
