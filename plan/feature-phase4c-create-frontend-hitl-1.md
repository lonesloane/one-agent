---
goal: Phase 4C — create-side frontend HITL dialog implementation and verification
version: 1.1
date_created: 2026-04-24
date_revised: 2026-04-25
owner: Stephane
status: 'Planned'
tags: [feature, phase4, frontend, copilotkit, hitl]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

> **⚠️ Scope revised 2026-04-25** — Dry-run confirmed ASSUMPTION-001 is
> **false**: CopilotKit v2 `V2Provider` does NOT auto-render
> `function_approval_request` HITL dialogs. Frontend wiring is required
> before Phase 4D. CON-001 (no new components) may need relaxing depending
> on the v2 hook API (query Context7 first — TASK-001 is now mandatory, not
> advisory). See FINDING-4C-002 in `docs/BACKLOG.md` for full dry-run notes.

Phase 4C implements and verifies the CopilotKit v2 HITL approval dialog for
`approval_mode="always_require"` tools on the create side. The `V2Provider`
does not auto-render these dialogs — explicit hook or component wiring is
needed. Captures dry-run feedback on dialog UX and files polish follow-ups
as a separate backlog item.

Spec: `docs/prd-phase4-write-agent.md` §2 (US-1 AC: HITL dialogs), §4
(Sub-phase 4C), §5 RISK "HITL dialog UX".

## 1. Requirements & Constraints

- **REQ-001**: With the Phase 4B server running (`uvicorn` on 8001) and the
  Next.js dev server running (`npm run dev` on 3000), a user who picks a
  `DELEGATION_EDITOR` persona and asks the agent to create a delegate must
  see a CopilotKit-rendered HITL approval dialog before the tool fires.
- **REQ-002**: Dialog must display the tool name + serialized arguments
  (at minimum `full_name`, `email`, `delegation_id`, `role`) so the user
  can review before approving.
- **REQ-003**: Approving the dialog must trigger the DB write; denying must
  abort with no write.
- **REQ-004**: The same behavior must hold for
  `create_document_access_rights` — separate HITL dialog per tool call.
- **CON-001**: ~~No new React components~~ **REVISED** — New hook/component
  wiring IS required (FINDING-4C-002 confirmed `V2Provider` does not
  auto-render). Query Context7 first (TASK-001) to determine whether this
  is a hook call in `page.tsx` or a new component. Prefer minimal changes;
  only `page.tsx`, `page.module.css`, and `DelegatePicker.module.css` in
  scope unless Context7 mandates otherwise.
- **CON-002**: CopilotKit v2 `V2Provider` import path (per
  `reference_copilotkit_v2_migration.md`) must not change.
- **GUD-001**: Respect the `agent_app/frontend/AGENTS.md` warning: this is
  Next.js 16 with breaking changes — check `node_modules/next/dist/docs/`
  before touching frontend config.
- **PAT-001**: Use Context7 `/copilotkit/copilotkit` before writing any new
  CopilotKit hook or provider prop (per project policy + memory).

## 2. Implementation Steps

### Implementation Phase 1 — Research: find the correct v2 HITL hook

- GOAL-001: Identify what frontend wiring is needed to render `function_approval_request` events in CopilotKit v2.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Query Context7 `/copilotkit/copilotkit` for: (a) how `function_approval_request` interrupt events are rendered in v2; (b) whether `useCopilotAction` with `renderAndWaitForResponse` or a dedicated HITL hook is the correct API; (c) what props/options are required. FINDING-4C-002 confirmed `V2Provider` alone is insufficient — this task determines the exact implementation path before any code is written. | ✅ | 2026-04-25 |

### Implementation Phase 2 — Implement HITL frontend wiring

- GOAL-002: Wire the correct v2 hook/component into `page.tsx` so the approval dialog renders for `create_delegate_access_request` and `create_document_access_rights`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-002 | Based on TASK-001 findings, implement the minimal frontend change required. Scope limited to `agent_app/frontend/src/app/page.tsx` and CSS modules unless Context7 mandates otherwise. Run full TypeScript check after. | | |
| TASK-003 | Start server + frontend; pick a `DELEGATION_EDITOR` persona; say "Create a new delegate named Test User, email test@example.com, in delegation FRA, role DELEGATE." Confirm the HITL approval dialog appears BEFORE any DB write. | | |
| TASK-004 | Approve the dialog; verify the new delegate appears in `/api/delegates`. | | |
| TASK-005 | Repeat the flow but deny the dialog. Confirm no new delegate row; agent surfaces acknowledgement. | | |
| TASK-006 | Drive the follow-up `create_document_access_rights` call; confirm a second independent HITL dialog appears for the DAR. | | |

### Implementation Phase 3 — Polish capture

- GOAL-003: Note cosmetic issues without acting on them; file as backlog.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Record any HITL dialog UX problems to `docs/BACKLOG.md`. Do NOT fix in 4C — route to the existing polish track if needed. | | |
| TASK-008 | If polish is critical-blocker (dialog unreadable, buttons unclickable), halt and spin a separate `feature-ui-polish-phase4c-hitl-*.md` plan before proceeding to 4D. Otherwise proceed. | | |

## 3. Alternatives

- **ALT-001**: Use CopilotKit's stock HITL rendering via the correct v2 hook (preferred — investigate via TASK-001).
- **ALT-002**: Build a custom HITL React component via `useCopilotAction` generativeUI. Use only if the stock v2 hook cannot render `function_approval_request` adequately.

## 4. Dependencies

- **DEP-001**: Phase 4A + 4B merged.
- **DEP-002**: Foundry `.env` present; `FOUNDRY_MODEL=gpt-4.1-mini`.
- **DEP-003**: `node_modules` installed in `agent_app/frontend/`
  (Turbopack symlink bug — no shared symlinks).

## 5. Files

- **FILE-001**: `agent_app/frontend/src/app/page.tsx` — HITL hook wiring
- **FILE-002**: `docs/BACKLOG.md` — dry-run findings update
- **FILE-003**: `docs/phase4c-hitl-dialog.png` — optional screenshot, delete after review

## 6. Testing

- **TEST-001**: Manual browser dry-run (TASK-003 through TASK-006). No
  automated tests in 4C — Playwright HITL e2e deferred to 4D or later
  unless trivial to add.

## 7. Risks & Assumptions

- **RISK-001**: CopilotKit stock HITL dialog may not render payloads
  usefully. Mitigation: document in BACKLOG, polish phase addresses.
- **RISK-002**: The correct v2 HITL hook may require a new provider wrapper
  or a structural change to `page.tsx` beyond a simple hook call. Mitigation:
  TASK-001 (Context7) must be completed before any code is written; if the
  API requires structural changes, revise the plan before implementing.
- **ASSUMPTION-001**: ~~The `V2Provider` already picks up `always_require`
  tool schemas from the AG-UI runtime without extra config.~~ **INVALIDATED
  2026-04-25** — Dry-run confirmed `V2Provider` does NOT auto-render
  `function_approval_request`. Explicit hook wiring required. See
  FINDING-4C-002 in `docs/BACKLOG.md`.

## 8. Related Specifications / Further Reading

- `docs/prd-phase4-write-agent.md` §2 US-1 AC
- `agent_app/frontend/AGENTS.md` — Next.js 16 warning
- Phase 4B plan: `plan/feature-phase4b-create-server-prompt-1.md`
- Phase 4D plan: `plan/feature-phase4d-create-integration-tests-1.md`
