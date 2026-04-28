---
goal: Phase 3C — CopilotKit Next.js frontend with delegate picker and streaming chat UI
version: 1.0
date_created: 2026-04-20
owner: Stephane
status: 'Planned'
tags: [feature, phase3, frontend, nextjs, copilotkit]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 3C delivers `agent_app/frontend/`: a Next.js 14 (App Router) app
using CopilotKit that connects to the FastAPI AG-UI server from Phase 3B.
The UI shows a delegate picker in the header (fetches from
`GET /api/delegates`) and a streaming `<CopilotChat />` that triggers the
proactive meeting brief automatically on session start. Switching delegate
resets the thread (new brief). Exit criterion: streaming brief visible in
browser within 5 seconds of session open; tool call events shown as
collapsible blocks; delegate switch resets thread.

Spec: `docs/prd-phase3-read-agent.md` §2 (US-3) and §4 (Frontend Spec).

> **Note**: This is a Node.js/TypeScript sub-project. CLAUDE.md Python
> conventions (PEP 8, loguru, pytest) do not apply here. Testing is
> browser-based; no pytest suite is expected for the frontend.

## 1. Requirements & Constraints

- **REQ-001**: `agent_app/frontend/` is a Next.js 14+ App Router project.
  Dev server runs on port 3000 (`npm run dev`).
- **REQ-002**: CopilotKit integration uses
  `@copilotkit/react-core` + `@copilotkit/react-ui`. Backend registered
  as `HttpAgent` pointing to the FastAPI AG-UI endpoint
  (`http://localhost:8000/<ag-ui-path>`).
- **REQ-003**: Header delegate picker fetches
  `GET http://localhost:8000/api/delegates` and renders a `<select>`
  dropdown showing `full_name (delegation_name — role)`. Defaults to
  first delegate on load.
- **REQ-004**: Switching delegate resets `threadId` (new UUID or
  `crypto.randomUUID()`), triggering a new session and fresh proactive
  brief.
- **REQ-005**: `<CopilotChat />` renders streaming text in real time;
  tool call events shown as collapsible "thinking" blocks during
  execution.
- **REQ-006**: Selected delegate's `id` is passed to the agent as
  `delegate_id` in the AG-UI session context (per the identity threading
  pattern established in Phase 3A/3B).
- **CON-001**: No authentication. Delegate identity set via picker only.
- **CON-002**: Desktop browser only. No mobile layout required.
- **CON-003**: No backend calls other than `GET /api/delegates` and the
  AG-UI SSE endpoint.
- **GUD-001**: TypeScript strict mode. Functional components + hooks only.
  No class components.
- **GUD-002**: No custom CSS framework; use CopilotKit's default styles
  with minimal overrides for the picker header.

## 2. Implementation Steps

### Implementation Phase 1 — Next.js App Bootstrap

- GOAL-001: Runnable Next.js skeleton that can reach the FastAPI server.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Scaffold `agent_app/frontend/` with `npx create-next-app@latest . --typescript --app --no-tailwind --no-eslint --no-src-dir` from inside `agent_app/frontend/`. Confirm `npm run dev` starts on port 3000. | | |
| TASK-002 | Install CopilotKit: `npm install @copilotkit/react-core @copilotkit/react-ui`. Confirm install with no peer-dependency errors. | | |
| TASK-003 | Create `app/copilotkit-provider.tsx`: wrap children in `<CopilotKit runtimeUrl="http://localhost:8000/<ag-ui-path>" agent="ONEMPReadAgent">`. Export as `CopilotKitProvider`. (Resolve `<ag-ui-path>` from Phase 3B output.) | | |
| TASK-004 | Wrap `app/layout.tsx` root with `<CopilotKitProvider>` so all pages have access. | | |

### Implementation Phase 2 — Delegate Picker

- GOAL-002: Header dropdown fetches delegates from FastAPI, persists
  selection in React state, and resets thread on change.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `app/components/DelegatePicker.tsx`. Use `useEffect` + `fetch("http://localhost:8000/api/delegates")` to load the delegate list. Render a `<select>` with option labels `{full_name} ({delegation_name} — {role})`. Lift `selectedDelegateId` and `threadId` to page-level state via props or context. | | |
| TASK-006 | On `<select>` change: update `selectedDelegateId` state; set `threadId` to `crypto.randomUUID()` to reset the agent session. Pass `selectedDelegateId` as `delegate_id` in the CopilotKit session context (via `agentState` or runtime prop — resolve from CopilotKit docs). | | |

### Implementation Phase 3 — Chat UI

- GOAL-003: Streaming chat with tool call visibility and proactive brief
  on load.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | In `app/page.tsx`, compose `<DelegatePicker />` in a header `<div>` and `<CopilotChat />` filling the remaining viewport height. Pass `threadId` to `<CopilotChat threadId={threadId} />`. | | |
| TASK-008 | Configure `<CopilotChat />` to show tool call events as collapsible blocks. Check CopilotKit docs for `showToolCallsInChat` prop or equivalent. Enable it. | | |
| TASK-009 | Confirm proactive brief behavior: open the browser at `http://localhost:3000`; within 5 seconds the agent should stream the meeting brief without any user message. Verify tool call blocks are visible. | | |

### Implementation Phase 4 — Smoke Testing

- GOAL-004: Golden-path and persona-switch scenarios verified in browser.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Golden path: select a delegate with new agenda documents (within `BRIEF_LOOKBACK_DAYS`). Confirm brief names correct meeting, committee, and document titles. Confirm no documents the delegate lacks a DAR for appear. | | |
| TASK-011 | No-new-docs path: select a delegate with no upcoming meetings or no new documents. Confirm greeting-only response (no document titles mentioned). | | |
| TASK-012 | Persona switch: switch to a second delegate mid-session. Confirm thread resets and new brief fires for the new persona within 5 seconds. | | |

## 3. Alternatives

- **ALT-001**: Use CopilotKit's `useChat` hook instead of `<CopilotChat />`
  for a fully custom chat UI. Rejected — adds UI complexity for no
  demo benefit; `<CopilotChat />` provides streaming + tool call blocks
  out of the box.
- **ALT-002**: Serve the frontend from FastAPI (static export). Rejected —
  separate dev servers (`npm run dev` / `uvicorn`) are simpler for the
  PoC and match the PRD spec.

## 4. Dependencies

- **DEP-001**: Phase 3B complete — FastAPI server running on port 8000;
  AG-UI endpoint verified; `/api/delegates` returns data.
- **DEP-002**: Node.js ≥ 18 on the dev machine (required for Next.js 14).
- **DEP-003**: `@copilotkit/react-core` + `@copilotkit/react-ui` (latest).
- **DEP-004**: `next@^14`, `react@^18`, `react-dom@^18`.

## 5. Files

- **FILE-001**: `agent_app/frontend/package.json` — new
- **FILE-002**: `agent_app/frontend/app/layout.tsx` — root layout with
  `CopilotKitProvider`
- **FILE-003**: `agent_app/frontend/app/page.tsx` — main page
- **FILE-004**: `agent_app/frontend/app/copilotkit-provider.tsx` — provider
- **FILE-005**: `agent_app/frontend/app/components/DelegatePicker.tsx` —
  delegate picker component

## 6. Testing

- **TEST-001**: Browser golden path — brief fires within 5 s for delegate
  with new documents (manual verification).
- **TEST-002**: Browser no-new-docs path — greeting only, no document titles
  (manual verification).
- **TEST-003**: Browser persona switch — thread resets, new brief fires
  (manual verification).
- **TEST-004**: Verify tool call events rendered as collapsible blocks in
  chat UI (manual verification).

## 7. Risks & Assumptions

- **RISK-001**: CopilotKit ↔ Agent Framework AG-UI integration gaps
  (unverified pairing). Mitigation: test AG-UI endpoint with `curl` in
  Phase 3B before wiring CopilotKit; consult AG-UI Dojo sample app.
- **RISK-002**: `delegate_id` session context injection API in CopilotKit
  may differ from Phase 3A's Python-side pattern. Mitigation: resolve from
  CopilotKit docs (`agentState`, custom headers, or initial message injection).
- **ASSUMPTION-001**: Node.js ≥ 18 available on dev machine.
- **ASSUMPTION-002**: AG-UI path registered by `add_agent_framework_fastapi_endpoint`
  is known before TASK-003 (from Phase 3B TASK-004 output).

## 8. Related Specifications / Further Reading

- `docs/prd-phase3-read-agent.md` — §2 US-3, §4 Frontend Spec
- Phase 3B plan: `plan/feature-phase3b-ag-ui-server-1.md`
- Phase 3D plan: `plan/feature-phase3d-brief-logic-and-tests-1.md`
- CopilotKit docs (resolve via context7 MCP or https://docs.copilotkit.ai)
