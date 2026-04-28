# PRD — Phase 4: Agent App (Write Agent — UC2)

**Status**: Draft
**Owner**: Stephane
**Target phase**: Phase 4 (per `docs/BACKLOG.md`)
**Depends on**: Phase 3 (read agent, merged 2026-04-22); Phase 2 (classical write flows + business rules)
**Blocks**: Phase 5 (MCP KB); Phase 6 (combined demo)

---

## 1. Executive Summary

### Problem Statement
Classical app (Phase 2) takes 8 screens to create a delegate + DAR. No approver workflow exists yet — DARs sit with `PENDING_*` status and no one acts on them. UC2 must show agent can collapse both sides (create + approve) into conversational flows with HITL confirmation.

### Proposed Solution
Write Agent with two operating modes driven by current persona:
- **Create side** (delegation editor persona): agent reasons DAR rules, creates delegate + DARs via HITL-confirmed write tools.
- **Approver side** (delegation head / secretariat persona): agent proactively lists pending DARs scoped to approver, offers approve/reject via HITL-confirmed write tools.

No classical inbox, no email (per OQ-9 option B). Same AG-UI + CopilotKit stack as Phase 3.

### Success Criteria
1. Create-side agent produces correct access level + approval route for all 5 DAR scenarios (member General/Restricted, partner General, partner+FA, Confidential, retroactive).
2. All write tools require explicit user confirmation (`approval_mode="always_require"`); no write occurs without approved HITL event.
3. Approver-side agent on session start proactively surfaces count + summary of pending DARs scoped to current approver identity within 5 seconds.
4. Approver cannot act on DARs outside scope — enforced in tool, verified by test.
5. Approved DAR flips status `PENDING_*` → `APPROVED`; document becomes visible via existing `is_document_visible`; rejected DAR flips to `REJECTED`, stays invisible.
6. Full project suite remains green; new tests emerge from implementation (no upfront count target).
7. Delegate picker shows pending-DAR count badge for approver personas.

---

## 2. User Experience & Functionality

### User Personas

| Persona | Role | Phase 4 access |
|---|---|---|
| **Delegation editor** | Existing (Phase 2B) | Create delegate + DARs via agent; cannot approve |
| **Delegation head** (new) | Approves PENDING_DELEGATION_HEAD DARs in their delegation | Approve/reject in-scope DARs only |
| **OECD secretariat** (new) | Approves PENDING_SECRETARIAT DARs (Confidential, retroactive) | Approve/reject secretariat-scope DARs only |
| **Demo observer** | Watches side-by-side vs classical app | Sees 8-screen → 3-turn collapse |

Picker displays role badge + pending-DAR count for approver personas.

### User Stories

**US-1 — Create delegate + DARs via agent**
> As delegation editor, I want to describe new delegate in chat and have agent handle delegate + DAR creation so I skip 8-screen wizard.

**AC:**
- Agent elicits: name, email, delegation, membership type, committee(s), desired access levels.
- Agent computes default access level via `compute_default_access_level` + routes via `determine_approval_route`.
- Before `create_delegate` fires, HITL confirmation shows full payload to user.
- Each `create_document_access_rights` call fires separate HITL confirmation.
- On approval → rows written, status flags set correctly, audit trail captures reasoning chain.
- On denial → no rows written, agent acknowledges.

**US-2 — Proactive approver brief on session start**
> As delegation head or secretariat, when I open agent, I want to immediately see my pending DARs so I don't have to ask.

**AC:**
- On session start, agent calls `list_pending_dars(approver_id)` automatically.
- If pending DARs exist → streams summary (delegate, document, access level, reason routed).
- If none → greeting + "No pending approvals."
- First tokens within 5 seconds.

**US-3 — Approve/reject individual DAR**
> As approver, I want to approve or reject each DAR with optional reason so decisions captured in audit.

**AC:**
- Agent offers per-DAR action; user says "approve DAR-123" or "reject DAR-123, reason=…"
- `approve_dar` / `reject_dar` fire HITL confirmation showing DAR details + reason.
- On approval → status → `APPROVED`, document visible to delegate on next query.
- On rejection → status → `REJECTED`, document stays invisible; reason stored.
- Approver acting on out-of-scope DAR → tool raises; agent surfaces error; no write.

**US-4 — Picker pending-count badge**
> As demo observer, I want picker to show pending count next to approver personas so switch to approver is visually motivated.

**AC:**
- `/api/delegates` response includes `pending_dar_count` for DELEGATION_HEAD + SECRETARIAT roles.
- Badge renders next to persona name in dropdown.
- Count updates on refresh (not live — poll acceptable).

### Non-Goals
- **No classical approver screen.** Approver flow agent-only.
- **No email/notification.** Out of scope.
- **No edit of existing delegate/DAR.** Create + approve only.
- **No delete flow.** Out of scope.
- **No additional approver roles beyond delegation head + secretariat.** OQ-1 stays open.
- **No live badge updates.** Refresh on picker open is sufficient.
- **No MCP KB.** Phase 5.
- **No extra UI polish beyond badge.** Separate polish session if needed.

---

## 3. AI System Requirements

### Tool Requirements

| Tool | Side | Mode | Inputs | Returns |
|---|---|---|---|---|
| `create_delegate` | create | `always_require` | name, email, delegation_id, membership_type, role | delegate_id |
| `create_document_access_rights` | create | `always_require` | delegate_id, document_id (or committee scope), access_level, retroactive | dar_id, status |
| `list_pending_dars` | approver | `never_require` | (approver_id via ctx) | list of pending DARs scoped to approver |
| `approve_dar` | approver | `always_require` | dar_id, reason? | new status |
| `reject_dar` | approver | `always_require` | dar_id, reason | new status |

Identity threading: approver_id / editor_id injected via `FunctionInvocationContext` (Phase 3A pattern).

Scope enforcement in `list_pending_dars` + approve/reject tools:
- DELEGATION_HEAD: only DARs where `approval_status == PENDING_DELEGATION_HEAD` **and** delegate belongs to same delegation.
- SECRETARIAT: only DARs where `approval_status == PENDING_SECRETARIAT`.

### System Prompt Requirements

Extend Phase 3 prompt with:
- **Persona-aware mode selection**: detect current persona role → switch between create-side and approver-side behavior.
- **DAR rule encoding**: access-classification rule (already present) + approval-routing rule (Restricted → delegation head; Confidential/retroactive → secretariat; General → auto-approved).
- **HITL write-guard**: "All writes require explicit user confirmation via HITL. Do not claim write happened until you see confirmation event."
- **Proactive approver brief**: "If persona is DELEGATION_HEAD or SECRETARIAT, on session start call `list_pending_dars` and summarize."
- **Scope-error handling**: "If a scope error is returned, report to user; do not retry."

### Evaluation Strategy
- Functional: unit tests per tool for scope, status transitions, rollback on error.
- Integration: mock client drives end-to-end create flow + approve flow.
- Grounding: approver brief cites only DARs returned by `list_pending_dars`.
- Manual: demo dry-run script covering 5 create scenarios + approve + reject + out-of-scope attempt.

---

## 4. Technical Specifications

### Architecture Overview

Same topology as Phase 3. New files:

```
agent_app/
  tools.py              — extend: +5 tools (create_delegate, create_dar,
                          list_pending_dars, approve_dar, reject_dar)
  agent.py              — extend: SYSTEM_PROMPT with persona mode + DAR rules
  server.py             — extend: /api/delegates response with pending_dar_count
  frontend/
    app/page.module.css — pending-count badge styles
    components/DelegatePicker.tsx — render badge
shared/
  database.py           — +DelegateRole.DELEGATION_HEAD, +DelegateRole.SECRETARIAT
  seed_data.py          — +1 delegation-head persona, +1 secretariat persona,
                          +pre-seeded pending DARs across both approval statuses
  business_rules.py     — new helper: count_pending_dars_for_approver(approver)
tests/
  agent_app/
    test_write_tools.py
    test_approver_tools.py
    test_approver_brief.py
```

### Sub-phase Split

One pass on create side, one pass on approver side; each pass has its own A/B/C/D slices.

| Sub-phase | Side | Deliverable | Exit criterion |
|---|---|---|---|
| **4A** | create | Write tools (`create_delegate`, `create_document_access_rights`) + `FunctionInvocationContext` identity + unit tests | Tools callable; HITL `always_require` set; scope test passes |
| **4B** | create | Server wiring (`/api/delegates` picker already exposes editor); system prompt create-side branch | AG-UI endpoint drives full create flow end-to-end via `curl`/mock |
| **4C** | create | Frontend HITL dialog styling via existing CopilotKit (no new components needed, verify render) | Streaming create flow visible in browser; HITL dialog blocks write until confirmed |
| **4D** | create | Integration tests (5 DAR scenarios) + docs closure for create side | All 5 scenarios green; BACKLOG create-side items checked |
| **4E** | approver | Seed approver personas + extend schema/seed; read tool `list_pending_dars` + unit tests | Picker shows approver personas with pending-count; tool returns scoped rows |
| **4F** | approver | Write tools `approve_dar`, `reject_dar` + scope enforcement + unit tests | Status transitions correct; out-of-scope raises |
| **4G** | approver | System prompt approver-side branch + proactive brief on session start + frontend badge | Brief auto-fires for approver persona; badge renders in picker |
| **4H** | approver | Integration tests (approve, reject, scope violation, visibility propagation) + docs closure | Approve flips status + visibility; reject flips status, stays invisible; docs updated |

### Integration Points
- Database: extend `shared/database.py` with new `DelegateRole` enum values; idempotent seed extension.
- `/api/delegates`: extend response with `role` + `pending_dar_count`.
- Audit: existing `AuditMiddleware` captures all tool calls incl. approvals.
- HITL: CopilotKit renders `approval_mode="always_require"` dialog out of box.

### Security & Privacy
- No new PII categories.
- Scope enforcement at tool boundary prevents cross-delegation approval.
- HITL prevents accidental writes.
- Audit trail mandatory for all state changes (already via `AuditMiddleware`).

---

## 5. Risks & Roadmap

### Phased Rollout
Sequential 4A → 4H. Create side (4A-4D) ships first, then approver side (4E-4H). Each slice merges to main independently.

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HITL dialog UX confusing under streaming | Medium | Medium | Dry-run early in 4C; capture feedback; restyle in separate polish session if needed |
| Scope-enforcement bug lets approver act cross-delegation | Low | High | Tool-layer enforcement + dedicated test; never rely on prompt alone |
| Agent skips HITL confirmation on write tool | Low | High | `approval_mode="always_require"` is framework-enforced; unit test verifies decorator arg |
| Pending-count badge drifts from reality | Low | Low | Poll on picker open; note in docs as non-live |
| Approver brief fires for non-approver persona | Low | Low | System prompt gates on role; test covers editor persona produces no brief |
| Seed DAR fixtures make approver inbox overwhelming | Low | Low | Seed ~3-5 pending DARs spread across both statuses |

### Open Questions Carried
- **OQ-1** (full RBAC model) — stays open; Phase 4 seeds only 2 new roles.

---

## Acceptance — "Phase 4 done" checklist

Create side:
- [ ] `create_delegate` + `create_document_access_rights` implemented, `approval_mode="always_require"`
- [ ] All 5 DAR scenarios produce correct access level + routing
- [ ] HITL confirmation enforced via test
- [ ] Full create flow demoable end-to-end in browser

Approver side:
- [ ] Seed delegation-head + secretariat personas
- [ ] `/api/delegates` includes role + `pending_dar_count`
- [ ] Picker renders approver badge + count
- [ ] `list_pending_dars` scope-enforced
- [ ] `approve_dar` / `reject_dar` implemented, HITL enforced
- [ ] Proactive approver brief on session start
- [ ] Approved DAR → doc visible; rejected → stays invisible
- [ ] Out-of-scope attempt raises + tested

Cross-cutting:
- [ ] Full project suite green
- [ ] `docs/BACKLOG.md` Phase 4 items checked with completion date
- [ ] `docs/DESIGN.md` "Current state" updated
- [ ] `docs/DECISIONS.md` logs any Phase-4 decisions
