---
goal: Fix BUG-4C-007 — model loops on extra text-confirm step before HITL dialog; and BUG-4C-008 — model batches dependent write tool calls (create_delegate + create_document_access_rights) in one parallel turn, hallucinating delegate_id and stranding the third approval card on "Preparing…"
version: 1.0
date_created: 2026-04-26
owner: Stephane
status: 'Deprecated'
tags: [bug, phase4, agent_app, prompt, frontend, hitl, copilotkit]
---

# Introduction

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red) — superseded by plan/spike-stock-stack-validation-1.md (2026-04-28)

After all server-side HITL plumbing fixes (BUG-4C-001..006) are
in place, two remaining defects make the create-delegate +
DAR-assignment flow feel broken to users:

**BUG-4C-007 — Extra confirmation round.** When a user provides all
required delegate fields and answers `Yes all correct, membership
type is member`, the model often replies with a *text* "Please confirm
to proceed with the creation" instead of calling `create_delegate`.
A third explicit message ("Yes please proceed and call the
create_delegate tool now") is then required before the tool fires
and the HITL dialog finally renders. The system prompt's `## HITL
Write Guard` section instructs the model to "Present a clear summary
of the proposed write … before the confirmation step", which the
model interprets as a *separate* text-confirm round on top of the
dialog card — duplicating the confirmation.

**BUG-4C-008 — Batched dependent writes.** When the user asks for
a delegate AND DARs in a single message (e.g. `Create Jean-Jacques
ROUSSEAU and assign him EDU/TRADE access`), the model fires
`create_delegate` AND multiple `create_document_access_rights`
calls in one parallel tool batch. The DAR calls require a
`delegate_id` that doesn't exist yet (the new delegate hasn't been
created, much less approved), so the model hallucinates an existing
delegate id (e.g. `DEL-2026-0002`). The frontend then renders 3
approval cards stacked; the third often sits on "Preparing…" with
a disabled Approve button (a render race when multiple
`confirm_changes` synthetic tool-calls arrive simultaneously).

**Fix**: rewrite the `## HITL Write Guard` and `## Create Side`
sections of the system prompt to (a) forbid an extra text-confirm
round once all elicitation fields are collected, treating the HITL
dialog AS the confirmation; and (b) mandate strict sequencing —
`create_delegate` must complete (tool result observed) before any
`create_document_access_rights` call may be issued. As a defensive
follow-up, queue approval cards on the frontend so even a
mistakenly-batched response renders one card at a time.

Spec: this plan; live diagnosis 2026-04-26 from chrome-devtools
dry-run captured in run63 (extra-confirm loop) and the user
screenshot `Capture18-15-28.png` (batched approvals with the third
card stuck "Preparing…").

## 1. Requirements & Constraints

- **REQ-001**: When the user supplies the final required
  elicitation field (e.g. membership type) and confirms accuracy in
  one message, the very next assistant turn MUST emit a
  `create_delegate` tool_call (no intermediate text-only "Please
  confirm" reply).
- **REQ-002**: The model MUST NOT issue a `create_document_access_rights`
  tool_call in the same turn as a `create_delegate` whose result
  has not yet been observed. A `create_delegate` tool_result must
  precede any DAR call that references the new delegate.
- **REQ-003**: The frontend MUST render at most one
  `confirm_changes` approval card in an "actionable" state at any
  given time. Subsequent cards in the same turn queue and become
  actionable only after the previous one is resolved (approved or
  denied).
- **REQ-004**: REQ-001 and REQ-002 must hold across both
  `gpt-4.1-mini` (current `FOUNDRY_MODEL`) and the next-tier model
  the project may switch to. Verify by manual dry-run with both if
  available; otherwise document the verified model in the plan
  closure note.
- **REQ-005**: Full unit suite (≥ 243 + new) must remain green;
  any new prompt regression test must lock the new sequencing rule
  as a string-match (or section-presence) check.
- **CON-001**: Prompt changes live in `agent_app/agent.py`
  `SYSTEM_PROMPT`. No tool-schema changes, no `tools.py` changes.
- **CON-002**: Frontend queueing change lives in
  `agent_app/frontend/app/page.tsx` (or a small helper in the same
  directory). No CopilotKit library changes.
- **GUD-001**: Before editing the prompt, query Context7
  (`/websites/learn_microsoft_en-us_agent-framework`) for the
  current preview-release guidance on tool-sequencing /
  parallel-tool-call control. The Agent Framework may already
  expose a config knob (e.g. `parallel_tool_calls=False`) that
  achieves REQ-002 without prompt acrobatics.

## 2. Implementation Steps

### Implementation Phase 1 — Prompt rewrite

- GOAL-001: Tighten the system prompt so the HITL dialog IS the
  confirmation, and dependent writes are strictly sequential.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Query Context7 (`/websites/learn_microsoft_en-us_agent-framework`) for current guidance on `parallel_tool_calls`, tool-sequencing, and HITL prompt patterns. Record findings (under 200 words) at the top of TASK-002 as a comment block. If a config flag exists (`parallel_tool_calls=False` or equivalent), prefer using it for REQ-002 over prompt-only enforcement. | | |
| TASK-002 | Rewrite `## HITL Write Guard` in `agent_app/agent.py` `SYSTEM_PROMPT`. Replace the current "Present a clear summary … before the confirmation step" wording with: <br>1. "When all required fields are collected, immediately call the write tool. Do NOT emit an additional text-only confirmation round; the HITL dialog rendered by the framework IS the confirmation." <br>2. "Only present a text summary if the user has not yet provided all required fields and you need to ask for the missing one." | | |
| TASK-003 | Rewrite `## Create Side (Delegation Editor)` to add an explicit sequencing rule: <br>"You must NEVER call `create_document_access_rights` in the same turn as `create_delegate`. After calling `create_delegate`, wait for the tool result (containing the new `delegate_id`), and only then issue any `create_document_access_rights` calls in a subsequent turn." Add a worked example showing one tool_call per turn. | | |
| TASK-004 | If TASK-001 surfaced a `parallel_tool_calls=False` (or equivalent) flag, set it on the agent in `agent_app/agent.py` `create_agent`. This is a belt-and-suspenders enforcement of REQ-002 even if the prompt is ignored. Document the choice in a `# Reason:` comment. | | |

### Implementation Phase 2 — Prompt regression tests

- GOAL-002: Lock the new wording so future prompt edits don't
  silently re-introduce the loop.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | In `tests/agent_app/test_agent.py`, add a regression test that asserts `SYSTEM_PROMPT` contains both new clauses (string match): <br>- "the HITL dialog rendered by the framework IS the confirmation" <br>- "NEVER call `create_document_access_rights` in the same turn as `create_delegate`" <br>(use the exact substrings TASK-002/003 produced.) | | |
| TASK-006 | Run `pytest tests/agent_app/test_agent.py -v`; full suite (`pytest --ignore=tests/e2e_agent --ignore=tests/e2e -q`) must remain green. | | |

### Implementation Phase 3 — Frontend approval-card queueing

- GOAL-003: Even if the model mistakenly batches multiple
  `confirm_changes` synthetic tool-calls in one turn, the user sees
  one actionable card at a time.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Query Context7 (`/copilotkit/copilotkit`) for current guidance on rendering multiple `useCopilotAction` / `confirm_changes` cards from a single turn. Confirm whether v2 already supports a queue / sequential-render mode out of the box. Under 150 words. | | |
| TASK-008 | In `agent_app/frontend/app/page.tsx` (the `confirm_changes` handler), implement: track in a React `useRef` set the `function_call_id`s already resolved this run. When a new `confirm_changes` card mounts, check whether ANY previous card from the same run is still unresolved (Approve/Deny not yet clicked). If yes, render the card in a "Queued — waiting for previous step" disabled state with no Approve/Deny buttons. When the previous card resolves (`respond({accepted:…})` fires), promote the next queued card to actionable state. | | |
| TASK-009 | Add a frontend unit/component test (Jest or Vitest) covering: 2 `confirm_changes` cards in one render → first card actionable, second card queued; after `respond({accepted:true})` on first → second card becomes actionable. | | |

### Implementation Phase 4 — Dry-run verification

- GOAL-004: Confirm BUG-4C-007 + BUG-4C-008 are resolved end-to-end
  in the browser.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Start backend + frontend (per project README). Pick `Marie Dupont (France — DELEGATION_EDITOR)`, wait for brief. Send a single message: `Please create a new delegate: full name X, email …, function delegate, delegation FRA, role DELEGATE.` Reply `Yes all correct, membership type is member` ONCE. Confirm: the next assistant turn fires the `create_delegate` tool_call directly (no extra "Please confirm" text round). HITL dialog appears. Approve. Delegate created in DB. | | |
| TASK-011 | In the same session, send: `Now create EDU and TRADE access for that delegate, both at GENERAL level.` Confirm: model issues a SINGLE `create_document_access_rights` per turn (not two in parallel). Walk through both HITL approvals sequentially. Both DAR rows present in `document_access_rights`. | | |
| TASK-012 | Stress test: send a single combined message — `Create delegate Y (full data) AND assign EDU GENERAL access to them.` Confirm the model issues `create_delegate` first; only after the user approves and the tool_result lands does the model issue `create_document_access_rights`. If TASK-004 set `parallel_tool_calls=False`, expect this to hold even on adversarial phrasing. | | |
| TASK-013 | Frontend race regression — patch the prompt temporarily to allow a parallel batch (or send a hand-crafted message that historically produces 3 cards). Confirm only the first card is actionable; subsequent cards show "Queued — waiting for previous step" and never reach the "Preparing…" stuck state from the original screenshot. Revert the prompt patch. | | |
| TASK-014 | Update `docs/BACKLOG.md` § "Phase 4C dry-run findings": add BUG-4C-007 (extra-confirm loop) and BUG-4C-008 (batched dependent writes + UI race) with fix summaries. | | |

## 3. Alternatives

- **ALT-001**: Backend serialisation — add a server-side guard
  that rejects a `create_document_access_rights` call if the
  referenced `delegate_id` was created in the same conversation
  but its tool_result is not yet present in history. Rejected —
  push the constraint to the model via the prompt + framework
  flag; backend should remain stateless about turn-ordering.
- **ALT-002**: Hide the elicitation entirely behind a typed
  Pydantic input model + structured form UI. Rejected for now —
  larger UX scope; revisit in Phase 4 polish.
- **ALT-003**: Rely on prompt only, skip the frontend queue.
  Rejected — the prompt is best-effort; the queue is a defensive
  guarantee. With both, even prompt drift on a model upgrade
  doesn't reproduce the "Preparing…" stuck card.

## 4. Dependencies

- **DEP-001**: BUG-4C-005 / BUG-4C-006 server-side fixes merged
  (separate plan: `plan/bug-phase4c-hitl-orphan-tool-result-1.md`).
  Without those, REQ-001 cannot be verified end-to-end because
  the follow-up turn fails before the model gets a chance to
  comply with the new prompt.
- **DEP-002**: `.env` with `FOUNDRY_MODEL=gpt-4.1-mini` and
  `DATABASE_PATH` present.
- **DEP-003**: Context7 access for TASK-001 / TASK-007.

## 5. Files

- **FILE-001**: `agent_app/agent.py` — rewrite `## HITL Write
  Guard` and `## Create Side` sections of `SYSTEM_PROMPT`;
  optional `parallel_tool_calls=False` on agent construction.
- **FILE-002**: `agent_app/frontend/app/page.tsx` — approval-card
  queue logic in the `confirm_changes` handler.
- **FILE-003**: `tests/agent_app/test_agent.py` — prompt
  regression test.
- **FILE-004**: `agent_app/frontend/__tests__/…` (new file or
  existing test directory) — queue-render unit/component test.
- **FILE-005**: `docs/BACKLOG.md` — BUG-4C-007 + BUG-4C-008
  entries.

## 6. Testing

- **TEST-001**: `tests/agent_app/test_agent.py` — prompt
  string-match regression for the two new clauses.
- **TEST-002**: Frontend component test — 2-card queue scenario.
- **TEST-003**: Full unit suite (`pytest --ignore=tests/e2e_agent
  --ignore=tests/e2e -q`) — ≥ baseline + new tests green.
- **TEST-004**: Manual dry-run (TASK-010..013) — single-confirm
  flow, sequential dependent writes, frontend queue defends
  against batched writes.

## 7. Risks & Assumptions

- **RISK-001**: Model may still emit a brief text-only response
  before the tool_call (e.g. "Calling create_delegate now…").
  This is acceptable as long as the same turn ALSO carries the
  tool_call. Mitigation: TASK-010 acceptance criterion is "tool
  call fires in the next turn" not "no text emitted at all".
- **RISK-002**: `parallel_tool_calls=False` (if available) may
  also disable legitimate parallelism in the read-only brief
  flow (whoami + get_upcoming_meetings + get_agenda_documents).
  Mitigation: confirm via Context7 (TASK-001) that the flag
  applies per-turn / per-call, not globally; if it disables the
  brief, fall back to prompt-only enforcement and rely on
  REQ-002 testing in TASK-012.
- **RISK-003**: Frontend queue logic changes the user's mental
  model from "see all pending writes at once" to "approve in
  sequence". For a future complex flow (10 DARs at once), users
  may prefer the batch view. Mitigation: the fix only queues
  *within the same turn*; once the model is forbidden from
  batching dependent writes (REQ-002), this should be rare.
- **ASSUMPTION-001**: `gpt-4.1-mini` is responsive to direct
  imperative system-prompt rules ("immediately call …", "NEVER
  call X in the same turn as Y"). Confirmed by past iterations
  on this prompt.
- **ASSUMPTION-002**: The frontend queueing approach is
  compatible with CopilotKit v2's `useCopilotAction`-based
  rendering of `confirm_changes` cards. TASK-007 verifies via
  Context7 before TASK-008 codes against it.

## 8. Related Specifications / Further Reading

- `plan/bug-phase4c-hitl-orphan-tool-result-1.md` — server-side
  prerequisite (BUG-4C-005 / BUG-4C-006)
- `plan/feature-phase4c-create-frontend-hitl-1.md` — original
  HITL frontend wiring (BUG-4C-002..004)
- `agent_app/agent.py` — `SYSTEM_PROMPT` (the file this plan
  edits the most)
- `agent_app/frontend/app/page.tsx` — `confirm_changes` handler
- Live diagnosis 2026-04-26: chrome-devtools dry-run, runs 61–63
  (extra-confirm loop with `gpt-4.1-mini`); user screenshot
  `Capture18-15-28.png` (batched approval cards with third stuck
  on "Preparing…").
- Context7 IDs:
  - Microsoft Agent Framework: `/websites/learn_microsoft_en-us_agent-framework`
  - CopilotKit: `/copilotkit/copilotkit`
