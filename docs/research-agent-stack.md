# Agent Frontend Stack Research

> Criteria-first research for the `agent_app/` rebuild. Resolves OQ-7.
> Produced after the 2026-04-28 reset (see `docs/DECISIONS.md` and
> `docs/_archived/failed-attempt-2026-04/`). No candidates are evaluated in
> this document — Step 2 (candidate survey) and Step 3 (recommendation + spike)
> are tracked separately.

## 1. Scope

The agent frontend is the user-facing surface for the Microsoft Agent Framework
Python backend. It must support both PoC use cases plus the Phase 4 approver
flow:

- **UC1** — Proactive Meeting Brief (read-only, streamed text + structured
  references, agent-initiated on session start).
- **UC2** — Delegate Creation with Document Access Rights (multi-turn,
  multi-tool, write tools gated by in-session human approval, denial
  recoverable).
- **UC3 — Approver triage** (Phase 4, resolved in §7 Q1): delegation head and
  secretariat personas review pending DARs (`PENDING_DELEGATION_HEAD`,
  `PENDING_SECRETARIAT`) and approve or reject. Distinct from UC2's in-session
  HITL — this is an asynchronous queue served by ordinary agent tools, not
  the `approval_mode` mechanism.

Out of scope for this document:

- Agent runtime choice — fixed: Microsoft Agent Framework (Python), `gpt-4.1-mini`
  via `FoundryChatClient`. See `docs/DECISIONS.md`.
- Backend tool implementation, MCP KB, business rules — already shipped in
  `shared/` and unchanged.
- Production hardening (auth, RBAC, GDPR, multi-tenant). PoC only.
- Approver UX (Phase 4) — depends on this decision but does not constrain it.

## 2. Method

The criteria below are written **before** any candidate stack is named.
Candidates in Step 2 will be scored against this list, not the reverse.
Each criterion is phrased as a capability requirement, not a technology choice
— a stack that meets the requirement by any means qualifies.

Lessons from the abandoned AG-UI + CopilotKit attempt are folded in as
capability requirements (Sections 3.2, 3.3, 3.6) rather than as named-tech
exclusions. Re-evaluating those tools is permitted in Step 2 if a candidate
demonstrates the criteria are met.

## 3. Must-Have Criteria

Ranked. A stack failing any of these is disqualified.

### 3.1 Streaming display of model output and tool calls

The UI must render incremental model tokens and tool-call events as they
arrive. The user must see *what* tool the agent is calling and *with which
arguments* before the result returns. Required for transparency in a write
flow.

Backend produces these via `agent.run(stream=True)`. The transport (SSE, WS,
chunked HTTP) is unconstrained — only the user-visible behavior matters.

### 3.2 In-session HITL approval round-trip — guaranteed render, deterministic resolve

Applies to UC2 (the editor confirming their own write before the tool fires).
This is the *synchronous, same-session* approval pattern, not the async
approval queue (UC3, see 3.9).

Write tools use `approval_mode="always_require"`. When the backend emits a
`function_approval_request`, the UI must:

1. **Render an approval prompt unconditionally** — no client-side filter,
   provider state, or React tree condition can swallow it.
2. **Submit approve/deny back to the same agent invocation**, producing a
   matching `function_approval_response` that the backend correctly attributes
   to the pending tool call.
3. **Resume the run after approval** with the tool result in correct position
   in the message history.

Failure to satisfy any of (1)–(3) was the headline blocker in the abandoned
attempt and is the single highest-priority criterion.

### 3.3 Denied-approval path closes cleanly

When the user denies, the backend must receive a denial response that closes
the pending tool-call (no orphan), the agent must be able to continue
conversing (e.g. ask the user what to do instead), and a subsequent turn must
not 400 due to an unmatched tool-call id in history.

### 3.4 Multi-turn tool-call/result ordering preserved across the session

Across N turns and M tool calls (including approved, denied, and read-only),
the message history sent on the next turn must remain a valid OpenAI-style
sequence: every `tool_calls` entry has its matching `tool` result (or denial),
in order, with no interleaving that breaks the API contract. The UI must not
silently drop or reorder events.

### 3.5 Identity threading invisible to the model

The acting delegate's identity must reach tool implementations via
`function_invocation_kwargs` (or equivalent server-side mechanism), not as
chat content. The frontend supplies the identity per request; the model never
sees it. This is a backend concern, but the frontend must have a place to
attach it on the request envelope.

### 3.6 Server-authoritative session state

The conversation, tool history, and pending-approval state must be reconstructible
from the server (`AgentSession` persisted to SQLite) without depending on
client-only state. Hot reload, page refresh, or a second tab must not corrupt
or lose the run. Client may cache for responsiveness; server is the source of
truth.

### 3.7 Compatible with Microsoft Agent Framework Python backend

The stack must integrate with a Python service exposing the agent. Either:

- A first-class Python server integration, or
- A documented HTTP/SSE/WS protocol the Python backend can implement directly
  with FastAPI/Starlette plus the Agent Framework's own helpers
  (e.g. `add_agent_framework_fastapi_endpoint` if applicable).

Stacks that require a Node/TS backend in front of the Python agent are
disqualified — adds a network hop, a serialization boundary, and a second
codebase for a PoC.

### 3.8 Multi-route surface sharing one server-side session per delegate

Per §7 Q3 resolution, the agent app is split across routes (UC1 brief,
UC2 delegate creation, UC3 approver inbox). Route navigation **must not**
reset the agent session, thread, or message history. Each route is a view
over the same `AgentSession` keyed by delegate identity. The stack must
support either (a) client-side routing with a stable session/thread id, or
(b) server-rendered routes that all bind to the same persisted session.

### 3.9 Async approval queue for UC3

Delegation head and secretariat must be able to log in, view a queue of
pending DARs scoped to their role, and approve or reject. This flows through
ordinary agent tools (e.g. `list_pending_approvals`, `approve_dar`,
`reject_dar`) operating against `DocumentAccessRight.approval_status` — no
in-session HITL contract is involved. The frontend must render the queue as
a structured list (not free-form chat output) and let an approver act on a
specific row inside an agent conversation. Distinct from 3.2; does not depend
on the same mechanism.

### 3.10 Demoable on a laptop in under 5 minutes

`pip install`, `npm install` (if any), one config file, one or two start
commands. The dual-app demo (classical vs agent side-by-side) requires the
agent app to come up reliably for stakeholders. No Docker-only or
cloud-only setups for the PoC.

## 4. Nice-to-Have Criteria

Tie-breakers, not gates.

### 4.1 Structured rendering primitives for tool output

UC1's meeting brief reads better as a card with sections (meeting metadata,
agenda, "new since last visit") than as a wall of markdown. A stack that
makes structured rendering ergonomic — typed component slots, JSON-driven
panels, or similar — is preferred over one that forces everything through a
single markdown channel.

### 4.2 First-class TypeScript types for events

If the chosen client is TS-based, typed event schemas (tool call, tool result,
approval request, approval response, run-complete) reduce wiring bugs.
Generated from a backend schema is best.

### 4.3 Low ceremony for the second use case

UC2 introduces a write flow on top of UC1's read flow. The stack should not
require a second framework, a second routing layer, or a second deploy
target to support both.

### 4.4 Active maintenance and primary-source docs

A library released in the last 12 months with reachable maintainers and
versioned docs (queryable via Context7) is preferable to a popular-but-stale
project.

### 4.5 Low lock-in to a UI vendor

If the agent surface later needs to be embedded in another web app or a
desktop shell, the stack should not make that prohibitively expensive.
Open protocol > proprietary protocol; small dependency surface > large.

## 5. Explicit Non-Criteria

Listed to prevent scope creep in Step 2:

- **Visual polish / design system fidelity.** PoC; functional demo only.
- **Mobile responsiveness.** Out of scope.
- **Accessibility (WCAG).** Acknowledged gap; deferred post-PoC.
- **i18n.** Out of scope; English only.
- **Streaming partial tool arguments token-by-token.** Whole-call granularity
  is sufficient.
- **Voice / multimodal input.** Out of scope.

## 6. Pre-Decided Constraints (do not re-litigate)

These are inputs to Step 2, not questions:

- Backend: Python, Microsoft Agent Framework, `FoundryChatClient` with
  `gpt-4.1-mini`. ([DECISIONS.md, 2026-04-10])
- Shared data layer: `shared/database.py`, `shared/business_rules.py`,
  SQLite `one_agent.db`. ([DECISIONS.md, 2025-04])
- Session persistence: `AgentSession` serialized to SQLite.
  ([DESIGN.md])
- HITL mechanism on backend: `approval_mode="always_require"` on write tools.
  ([DECISIONS.md, 2025-04])
- Two PoC use cases (UC1 read, UC2 write) — no third surface.
  ([DECISIONS.md, 2025-04])

## 7. Resolved Questions

### Q1 — Approver UX hosted in the agent frontend (resolved 2026-04-28)

The Phase 4 approver flow lives in the agent frontend, not a separate
surface. Resolution adds **UC3** to scope (§1) and introduces criterion **3.9
async approval queue**.

Important distinction surfaced during resolution: UC2's in-session HITL (3.2)
and UC3's async approval queue (3.9) are **two different mechanisms** despite
both being "approvals." UC2 pauses the editor's own run waiting for the
editor's confirm/deny via `approval_mode="always_require"`. UC3 is a separate
delegate (delegation head or secretariat) logging in later, viewing a queue
of pending DARs, and acting via ordinary agent tools. Conflating them was
implicit in the archived 2026-04-24 decision and is now explicit.

### Q2 — Login screen as landing, persona switching forbidden mid-session (resolved 2026-04-28, with caveat)

The agent app entry is a login screen. Successful login lands the user in
the agent app bound to one delegate identity. Mid-app persona switching is
**not** supported; switching requires logout, which fully tears down the
server-side `AgentSession` and thread. This eliminates a class of state-
corruption hazards (mid-session thread keyed to a different delegate, stale
approval state, mismatched identity in `function_invocation_kwargs`).

**Caveat — root-cause attribution:** the failed 2026-04 attempt's headline
issues (multi-turn 400, V2Provider not rendering approval, denied-approval
orphan tool_call, HMR-induced state loss, brittle replay) are HITL/contract
bugs, **not** persona-switcher bugs. Removing the switcher does not address
those. Step 2 candidates must still be evaluated against 3.2/3.3/3.4
regardless of how identity is sourced.

**Demo affordance:** to preserve fast persona-swap during stakeholder demos
(the classical app's switcher made this trivial), the login screen exposes
a row of one-click persona buttons (e.g. *Editor — DEL-2026-0001*,
*Editor — DEL-2026-0005*, *Approver — Delegation Head*, *Approver —
Secretariat*) that pre-fill and submit. Functionally equivalent to the
classical switcher, but routed through a clean login → server-side session
init path.

### Q3 — Multi-route agent app over one shared session per delegate (resolved 2026-04-28)

The agent app uses separate routes per use case (UC1 brief, UC2 delegate
creation, UC3 approver inbox). Each route is a tailored view, not a session
boundary. All routes bind to **one shared `AgentSession` per logged-in
delegate** so the agent retains continuity across navigation (e.g. it can
reference the brief seen on the landing page when the editor opens the
delegate-creation page minutes later).

This adds criterion **3.8 multi-route surface sharing one server-side
session per delegate**. The "shared session, multiple views" requirement is
the non-obvious part — naive multi-route designs reset the thread on every
navigation and quietly defeat the value proposition.

## 8. Next Steps

- **Step 2** — Candidate survey against §3–§4. One short section per
  candidate, primary-source-cited (Context7 for Microsoft Agent Framework,
  CopilotKit, and any other library with a Context7 ID; vendor docs
  otherwise). Output: `docs/research-agent-stack.md` extended with a
  Candidates section, or a sibling `docs/research-agent-stack-candidates.md`
  if length warrants.
- **Step 3** — Pick 1–2 finalists. Define a minimal HITL spike (one write
  tool, approval round-trip, denial path, two-turn replay) and run it
  before any PRD.
