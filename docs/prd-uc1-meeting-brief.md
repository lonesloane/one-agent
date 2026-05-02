---
prd: UC1 — Proactive Meeting Brief
version: 1.0
date_created: 2026-05-02
owner: stephane.varin@gmail.com
status: Drafted
stack: C4 (Chainlit + agent-framework Python + FoundryChatClient + AzureCliCredential)
depends_on: plan/phase3-agent-app-scaffold-1.md
supersedes: plan/_archived/failed-attempt-2026-04/feature-phase3a-tools-agent-1.md, plan/_archived/failed-attempt-2026-04/feature-phase3d-brief-logic-and-tests-1.md
tags: [phase3, agent_app, uc1, brief, read-only, chainlit, agent-framework]
---

# PRD — UC1: Proactive Meeting Brief

## 1. Executive Summary

### Problem Statement

Today a delegate must click through four classical-app screens (Dashboard
→ committee picker → Upcoming Meetings → Meeting detail → per-document
visibility check) just to learn whether anything new was added to an
upcoming meeting since their last visit. The form-based UI is reactive —
it tells you nothing until you ask. There is no path that surfaces
"what changed for me" without explicit navigation.

### Proposed Solution

UC1 ships the agent app's first user-facing capability: a **proactive
meeting brief** delivered the moment the delegate opens a chat session.
The agent reads its identity from `cl.user_session`, calls three
read-only tools that wrap `shared/business_rules.py`, and streams a
compact brief covering (a) upcoming meetings within a configurable
window and (b) new or modified agenda documents since the delegate's
last login — all DAR-filtered. No user prompt is required to trigger
the brief; structurally impossible in the form app.

### Success Criteria

1. **Proactive trigger works.** Brief is rendered on `@cl.on_chat_start`
   without any user message. Manual smoke: log in → brief streams within
   the first agent turn. (Pass/fail; testable in the Chainlit UI.)
2. **Tool routing is correct.** Across at least 5 seeded delegates, the
   agent calls `get_upcoming_meetings` once and `get_agenda_documents`
   once per upcoming meeting in the window. (Verified in tool-trace
   logs and integration tests; ≥ 90% of runs against seeded fixtures.)
3. **DAR filtering is honoured.** A delegate without DAR for a
   `RESTRICTED` document never sees that document mentioned in the
   brief — even when the meeting is in scope. (Hard pass — 100% on
   integration test `test_brief_respects_dar_visibility`.)
4. **Latency budget.** First streamed token to the user within
   **≤ 3 s p50 / ≤ 6 s p95** on the demo network with `gpt-4.1-mini`
   via Azure AI Foundry.
5. **Grounding.** Document titles in the brief must match titles
   returned by the tool exactly (no hallucinated documents). Verified
   by the grounding integration test.

---

## 2. User Experience & Functionality

### User Personas

- **Primary — Delegate** (`DelegateRole.DELEGATE`): an OECD committee
  representative who logs in to prepare for upcoming meetings. Cares
  about: what is coming up, what changed since last login, which
  documents they can actually open. Time-constrained, scanning.
- **Secondary — Delegation Editor** (`DelegateRole.DELEGATION_EDITOR`):
  same brief on login. UC1 does not differentiate behaviour by role.
  Editors get UC2/UC3 entry points later in the same session.
- **Out-of-persona — Approver / Secretariat staff:** UC3 territory.
  Not addressed here.

**Demo audience:** internal OECD demonstrator — internal stakeholders
comparing classical and agent flows side-by-side. No external-facing
prose adaptation required for UC1.

### User Stories

1. **US-001 — Proactive welcome.**
   *As a delegate, when I open the agent chat, I want to see a brief of
   my upcoming meetings without typing anything, so I can orient myself
   immediately.*

2. **US-002 — New documents callout.**
   *As a delegate, I want the brief to highlight which agenda documents
   are new or modified since my last login, so I don't have to compare
   meeting pages across visits.*

3. **US-003 — DAR-respecting visibility.**
   *As a delegate, I want the brief to show only documents I am
   permitted to read, so I am not teased by titles I cannot open.*

4. **US-004 — Empty state.**
   *As a delegate with no upcoming meetings in the window, I want a
   short greeting that explicitly says "nothing on the calendar", so I
   know the system has actually run and isn't broken.*

5. **US-005 — Meeting drill-down (reactive follow-up).**
   *As a delegate, I want to ask "tell me more about the Trade meeting"
   and get the agenda items + my visible documents, so I can prepare
   without leaving the chat.*

### Acceptance Criteria

#### US-001 Proactive welcome

- [ ] On `@cl.on_chat_start`, the agent sends a streamed `cl.Message`
      containing the brief, **before** any user input is required.
- [ ] The brief opens with a one-line greeting that includes the
      delegate's `full_name` and `delegation.name`.
- [ ] No `cl.AskActionMessage` (approval prompt) is rendered for any
      UC1 tool. (UC1 is read-only.)

#### US-002 New documents callout

- [ ] For each upcoming meeting in scope, documents whose
      `last_modified > delegate.last_login` are listed under a "New or
      modified since your last visit" sub-section.
- [ ] If `delegate.last_login is None`, the agent treats this as a
      first login and lists the full visible agenda **with** a soft
      one-line "first login — full agenda below" lead-in (no "new
      since" framing on individual documents). Locked in test.
- [ ] The "since last login" cutoff uses the value of
      `delegate.last_login` *at the moment the brief tool is called*
      (i.e., the just-completed login MUST NOT be used to update
      `last_login` until **after** the brief tool reads it).

#### US-003 DAR-respecting visibility

- [ ] Documents in the brief are filtered through
      `shared.business_rules.get_visible_agenda_documents(delegate_id,
      meeting_id, session)` (single source of truth).
- [ ] For a delegate without DAR on a committee, that committee's
      meetings are still listed (delegate may attend), but document
      titles are suppressed; agent shows the meeting with a "no
      documents available to you" placeholder line in place of titles.
      The meeting is **never** suppressed entirely on zero-visible-docs.

#### US-004 Empty state

- [ ] When `get_upcoming_meetings` returns an empty list, the agent
      streams a short greeting only, with no document section, no
      tool errors, no fabricated meeting names.

#### US-005 Drill-down follow-up

- [ ] On a follow-up message naming a committee or meeting,
      the agent calls `get_meeting_brief(meeting_id)` (or
      `get_agenda_documents`) and streams the per-meeting agenda.
- [ ] Drill-down still respects DAR; the same suppression rule from
      US-003 applies.

### Non-Goals

- **Write actions.** UC1 never modifies the database. No
  `@tool(approval_mode="always_require")` tools are introduced — those
  belong to UC2 (delegate creation) and UC3 (approver inbox).
- **AG-UI / CopilotKit / .NET.** Stack is locked to C4 (Chainlit +
  `agent-framework` Python). See `docs/DECISIONS.md` `[2026-05-01]`.
  Do not introduce `agent-framework-ag-ui`, CopilotKit React, or
  `*.csproj` projects.
- **Real authentication.** Identity is read from `cl.user_session`
  populated by a development bypass (env var or chat-start arg) per
  scaffold plan TASK-007. Production auth is out of scope.
- **MCP KB integration.** Business rules are called as direct Python
  functions. The MCP KB plumb-through is Phase 5.
- **Eval-suite extension.** UC1 does not modify the Phase 0
  `eval/scenarios/` set. The harness is rerun against the new SYSTEM
  prompt to detect regressions, but no new scenarios are required.
- **Multi-tab / page-refresh persistence.** Per scaffold RISK-003, the
  `cl.user_session` durability across refresh is not solved here.
- **(Previously TBD) Last-login persistence write.** Now **in scope** —
  UC1 updates `Delegate.last_login` at the end of brief rendering
  (after the brief tool has read the previous value). The write goes
  through the same code path the classical app uses (or a tiny shared
  helper) to keep cross-app behaviour consistent. Listed here for
  traceability against the original non-goal framing.

---

## 3. AI System Requirements

### Tool Requirements

All tools live in `agent_app/tools/` as `@tool`-decorated functions
returning JSON-serializable payloads. `delegate_id` is **never** a
model-visible parameter — it is captured by closure from a factory
function bound at `@cl.on_chat_start`, per scaffold plan PAT-001.

> Verified via Context7 ID `/websites/learn_microsoft_en-us_agent-framework`
> (`?pivots=programming-language-python`) on 2026-05-02 — `@tool` accepts
> `approval_mode="never_require"` (default for read-only tools).

| Tool | Module (proposed) | Purpose | Approval mode | Closure-bound args |
|---|---|---|---|---|
| `get_upcoming_meetings` | `agent_app/tools/meetings.py` | List meetings within window for delegate's committees, sorted ascending by date. | `never_require` | `delegate_id` |
| `get_meeting_brief` | `agent_app/tools/meetings.py` | For one `meeting_id`, return DAR-filtered agenda documents + flag those modified since `delegate.last_login`. | `never_require` | `delegate_id` |
| `get_new_documents` | `agent_app/tools/meetings.py` | Cross-meeting helper: documents modified since last login across all in-scope upcoming meetings. | `never_require` | `delegate_id` |

The existing scaffold tool `get_current_delegate_summary`
(`agent_app/tools/delegate.py`, scaffold TASK-004) is retained.

#### Tool signatures (closure-bound shape)

```python
def make_get_upcoming_meetings(
    delegate_id: str,
    window_days: int,
):
    """Build a closure-bound get_upcoming_meetings tool.

    Args:
        delegate_id: Delegate identifier; bound at chat-start, never
            visible to the model.
        window_days: Lookahead window in days for "upcoming".

    Returns:
        A @tool-decorated callable suitable for an agent's tool list.
    """

    @tool(approval_mode="never_require")
    def get_upcoming_meetings() -> str:
        """Return upcoming meetings for the current delegate."""
        # Calls shared.business_rules + shared.database directly.
        ...

    return get_upcoming_meetings
```

#### Direct calls into `shared/business_rules.py` (no porting, no shim)

- `get_visible_agenda_documents(delegate_id, meeting_id, session)` —
  source of truth for DAR-filtered agenda items.
- `get_new_documents_since(delegate_last_login, meeting_id, session)` —
  source of truth for "what's new since last login".
- `is_document_visible(...)` is called transitively through the two
  helpers above; UC1 tools must not call `is_document_visible`
  directly (avoids drift).

### "Upcoming window" semantics

- **Window length:** forward window = **30 days**, exposed as the
  `UC1_UPCOMING_WINDOW_DAYS` constant in `agent_app/agent.py` (the
  archived plan's `BRIEF_LOOKBACK_DAYS = 7` was a backward
  *new-documents* lookback, not a forward meeting window — kept
  separate).
- **"Since last login" semantics:** the `delegate.last_login`
  timestamp from the `delegates` table is the cutoff. If `None`, see
  US-002 acceptance criterion.

### System prompt additions

The scaffold's placeholder instructions string is replaced by a UC1
SYSTEM_PROMPT that encodes:

1. **Role.** "You are the ONE-MP delegate assistant. The current user
   is a delegate. Identity is already known to you; do not ask for it."
2. **Proactive trigger.** "On the very first turn of every session,
   call `get_upcoming_meetings` and produce a meeting brief without
   waiting for the user to ask."
3. **Tool sequence.** "Call `get_upcoming_meetings` first. For each
   returned meeting within the window, call `get_meeting_brief` to
   retrieve DAR-filtered agenda documents. Aggregate results into a
   single brief."
4. **Grounding rule.** "Only mention meeting titles, dates, and
   document titles that appear verbatim in tool results. Do not
   invent IDs, dates, or titles."
5. **DAR rule.** "If a tool result omits a document, you must not
   mention it. Visibility is enforced server-side; trust the tool."
6. **Empty-state rule.** "If `get_upcoming_meetings` returns empty,
   greet briefly and stop."

### Evaluation Strategy

- **Unit (`tests/agent_app/test_tools_meetings.py`)** — direct calls to
  the closure-bound tools against an in-memory SQLite seeded via
  `shared.seed_data.seed_all`. Covers: upcoming-only filtering,
  ascending date sort, DAR enforcement, lookback boundary
  (last_modified == cutoff is **excluded**, i.e., strictly greater).
- **Integration (`tests/agent_app/test_brief_logic.py`)** — mock the
  `agent_framework` LLM call (no live Foundry round-trip in CI);
  assert the *tool-call sequence* and *response shape* against fixed
  fixtures. Mirrors the archived plan's `TestBriefFiresWith…` /
  `TestBriefSuppressed…` patterns (see §6 mining notes).
- **Grounding test** — fixture returns 2 known documents; assert the
  rendered response contains *only* those titles (string membership).
- **Manual smoke (Chainlit)** — run `chainlit run agent_app/app.py`,
  log in as delegate `1` (or whichever the dev bypass selects);
  confirm brief streams within latency budget; confirm DAR filtering
  visually for a delegate without RESTRICTED access.
- **Re-run Phase 0 eval suite** against the new SYSTEM_PROMPT to detect
  regressions on the existing 15-scenario harness.

### Test count target

Minimum **10 new tests** added under `tests/agent_app/`. Lower than
the archived plan's "≥ 20" because UC1 here is read-only and scoped to
one feature; UC2 and UC3 will pull the cumulative count up.

---

## 4. Technical Specifications

### Architecture Overview

```
   Chainlit WebSocket UI
            │
            ▼
   agent_app/app.py
   ├─ @cl.on_chat_start
   │     ├─ load delegate_id (dev bypass)
   │     ├─ stash credential, agent, session in cl.user_session
   │     └─ trigger proactive brief turn (no user input)
   │
   └─ @cl.on_message
         └─ runs the agent loop verbatim from spikes/c4_chainlit/app.py
            (minus the approval branch — UC1 is read-only)
            │
            ▼
   agent_framework.Agent (FoundryChatClient + AzureCliCredential)
            │
            ▼
   tools (closure-bound) ── shared/business_rules.py ── shared/database.py
                                                              │
                                                              ▼
                                                         one_agent.db
```

**Verified via Context7 ID `/websites/learn_microsoft_en-us_agent-framework`
(`?pivots=programming-language-python`) on 2026-05-02:**
- `FoundryChatClient(project_endpoint=..., model=..., credential=AzureCliCredential())`
  is the canonical Python construction.
- `chat_client.as_agent(instructions=..., name=...)` builds an `Agent`.
- `agent.run(input, session=session, stream=True)` is the streaming
  entry point — confirmed in `spikes/c4_chainlit/app.py` (parity).

**Verified via Context7 ID `/chainlit/docs` on 2026-05-02:**
- `@cl.on_chat_start` is the welcome hook; sending a `cl.Message` from
  inside it streams a proactive message before any user input.
- `cl.user_session.set` / `cl.user_session.get` is the per-session
  state primitive.
- `cl.Message(content="").send()` followed by `await
  msg.stream_token(token)` is the streaming pattern; final
  `await msg.update()` finalizes.

### Proactive brief trigger pattern

```python
@cl.on_chat_start
async def on_chat_start() -> None:
    """Boot the agent and stream the proactive brief."""
    delegate_id = _resolve_delegate_id()  # dev bypass per scaffold
    credential = AzureCliCredential()
    agent = build_agent(credential=credential, delegate_id=delegate_id)
    session = agent.create_session()
    cl.user_session.set("credential", credential)
    cl.user_session.set("agent", agent)
    cl.user_session.set("session", session)
    cl.user_session.set("delegate_id", delegate_id)

    # Reason: UC1 fires the brief without waiting for a user message;
    # the agent's SYSTEM_PROMPT instructs it to call get_upcoming_meetings
    # on turn 1. The "input" here is a synthetic kickoff string.
    await _stream_agent_turn(
        agent=agent,
        session=session,
        user_input="__SESSION_START__",
    )
```

`_stream_agent_turn` reuses the streaming/approval loop from
`spikes/c4_chainlit/app.py` lines 82–132, **minus** the approval
branch (UC1 has no approval-gated tools — `user_input_requests` will
always be empty for UC1).

### Identity threading (PAT-001 from scaffold)

- `delegate_id` is read **once** at `on_chat_start` from a development
  bypass (env var `ONE_MP_DELEGATE_ID` or Chainlit chat-start arg) and
  stored in `cl.user_session`.
- `build_agent(credential, delegate_id)` is the only place that knows
  the value. It calls each tool factory (`make_get_upcoming_meetings`,
  `make_get_meeting_brief`, `make_get_new_documents`) and assembles
  the agent's tool list from the closure-bound results.
- The model's prompt **never contains** `delegate_id`. The model never
  sees a tool parameter named `delegate_id`. This is non-negotiable
  per scaffold SEC-001 and PAT-001.

### File map (proposed)

| File | Status | Purpose |
|---|---|---|
| `agent_app/app.py` | edit | Add proactive-brief trigger in `on_chat_start`. |
| `agent_app/agent.py` | edit | Replace placeholder instructions with UC1 SYSTEM_PROMPT; expose `UC1_UPCOMING_WINDOW_DAYS` constant; wire 3 new tool factories. |
| `agent_app/tools/meetings.py` | new | `make_get_upcoming_meetings`, `make_get_meeting_brief`, `make_get_new_documents`. |
| `agent_app/tools/delegate.py` | retain | Scaffold-era tool kept; brief does not depend on it but it remains useful for follow-ups. |
| `tests/agent_app/test_tools_meetings.py` | new | Closure tools — direct calls. |
| `tests/agent_app/test_brief_logic.py` | new | Brief trigger + suppression + grounding + DAR. |
| `docs/DESIGN.md` | edit | Mark UC1 implemented in "Current state". |
| `docs/BACKLOG.md` | edit | Tick UC1 line. |

### Integration Points

- **Database.** SQLite (`one_agent.db`) shared with `classical_app/`.
  Reads only for UC1; the agent uses the session helper from
  `agent_app/session.py` (scaffold FILE-004).
- **Auth / Identity.** Development bypass via env or chat-start arg.
  `cl.user_session` carries the delegate identity for the session.
- **Foundry / model.** `gpt-4.1-mini` via `FoundryChatClient` with
  `FOUNDRY_PROJECT_ENDPOINT` from `.env`. `AzureCliCredential` requires
  an active `az login`.

### Security & Privacy

- **No secrets in code.** `.env` carries `FOUNDRY_PROJECT_ENDPOINT`
  and `FOUNDRY_MODEL=gpt-4.1-mini`; not committed.
- **No identity leak to the model.** `delegate_id` is closure-bound,
  not in tool signatures, not in the system prompt, not in
  conversation history. The model sees only delegate name and
  delegation name (which it could in principle hallucinate without DB
  grounding — that is what the grounding test catches).
- **DAR enforcement is server-side.** Even if the model is asked to
  reveal a `RESTRICTED` document title, it cannot — the document never
  enters the tool result.
- **Audit trail.** Function-invocation middleware (scaffold-era;
  retained) logs every tool call (delegate_id, tool name, args,
  result-summary, timestamp) via loguru. UC1 does not introduce new
  audit channels.
- **Cross-app consistency.** `last_login` reads must match the
  classical app's behaviour. If UC1 chooses to update `last_login`
  (see Non-Goals), the write goes through the same code path the
  classical app uses (or via a tiny shared helper) — no agent-only
  divergence.

---

## 5. Risks & Roadmap

### Phased Rollout

| Phase | Scope |
|---|---|
| **MVP (this PRD)** | Proactive brief on chat-start, three read-only tools, DAR-filtered output, drill-down on follow-up, dev-bypass identity. Manual smoke + automated tool/brief-logic tests. |
| **v1.1 (post UC2)** | Once UC2's HITL is solid, revisit UC1 prompt for any cross-UC tone consistency. (`last_login` write-back already in MVP scope per §2 Non-Goals reclassification.) |
| **v2.0 (Phase 5)** | Replace direct `shared/business_rules.py` calls in tools with MCP KB lookups for the rule-explanatory text (titles/visibility stay direct). Out of UC1 scope — flagged for traceability only. |

### Technical Risks

- **R-1: `agent.run(stream=True)` semantics drift.** The C4 spike
  validated the loop on 2026-04-29; `agent-framework` is preview and
  may have shifted. Mitigation: scaffold TASK-011 manual smoke is the
  early-warning system; if the streaming contract changed, fix in
  `app.py` before UC1 work commits.
- **R-2: Latency on first proactive turn.** Cold connection to Foundry
  + tool-call → tool-call sequence may exceed comfort. Mitigation:
  parallelize per-meeting `get_meeting_brief` calls *only if* the
  agent supports parallel tool calls; otherwise accept serial latency
  and document the budget. Verify approach via Context7 before
  optimizing.
- **R-3: `delegate.last_login` seed values.** `shared/seed_data.py`
  is extended (additive, idempotent — same pattern as existing seed
  functions) to **backdate `last_login` to 7 days ago for one demo
  persona** and leave it `None` for the others. This exercises both
  the "new since" branch (backdated persona) and the first-login
  branch (null personas) without ad-hoc demo-prep helpers.
- **R-4: Multi-tab / refresh.** `cl.user_session` is per-WebSocket;
  refreshing the page rebuilds the session and re-fires the brief.
  Acceptable for demo; flagged for future hardening.
- **R-5: Identity leak via tool errors.** If a tool raises a
  `ValueError` mentioning `delegate_id` in its message, the agent may
  echo it. Mitigation: tools must catch domain errors and return a
  scrubbed JSON payload (no PII, no IDs other than meeting/document).
- **R-6: Re-introducing archived stack assumptions.** The failed
  attempt's plans baked AG-UI / CopilotKit / `function_invocation_kwargs`
  assumptions into both the prompt and the tool signatures. Mitigation:
  reviewers must reject any PR that re-imports `agent-framework-ag-ui`
  or references `function_invocation_kwargs` (closure pattern is the
  C4-validated alternative).
- **R-7: Eval-suite regression on B2.** The Phase 0 eval scenarios
  include B2 (proactive login flow). The new SYSTEM_PROMPT must keep
  B2 green. Mitigation: rerun the eval harness after the prompt lands
  and before UC1 PR merges.

### Assumptions

- **A-1:** Phase 3 scaffold plan TASK-001..TASK-012 is merged before
  UC1 implementation begins.
- **A-2:** `gpt-4.1-mini` retains its Phase 0f tool-selection quality
  (100% aggregate). Carries over from the C4 spike pass.
- **A-3:** `shared/business_rules.py` helpers are signature-stable;
  no edits required to land UC1.
- **A-4:** `one_agent.db` is seeded via `shared.seed_data.seed_all`
  before any manual smoke test (per scaffold DEP-006).

---

## 6. Related Specifications / Further Reading

### Active references (load-bearing)

- `plan/phase3-agent-app-scaffold-1.md` — Phase 3 scaffold plan; UC1
  PRD is consistent with REQ-002 (closure-bound `delegate_id`),
  PAT-001 (factory + closure DI), CON-002 (no `agent-framework-ag-ui`),
  §3 UC sequencing (UC1 read-only, no HITL).
- `spikes/c4_chainlit/app.py` — parity reference for the
  `@cl.on_chat_start` / `@cl.on_message` / `agent.run(stream=True)`
  / `cl.user_session` pattern. UC1's `_stream_agent_turn` is this
  loop minus the approval branch.
- `shared/business_rules.py` — single source of truth. UC1 calls
  `get_visible_agenda_documents` and `get_new_documents_since`
  directly; no porting, no duplication.
- `shared/database.py` — entity shapes (`Meeting`, `MeetingAgendaItem`,
  `Document`, `Delegate`, `DocumentAccessRight`).
- `classical_app/app.py` `dashboard` / `upcoming_meetings` /
  `meeting_detail` / `document_detail` routes — define the
  *equivalent* information UC1 delivers conversationally.
- `docs/DESIGN.md` — architecture, stack, UC scope.
- `docs/DECISIONS.md` `[2026-05-01]` — the C# pivot reversal that
  locks the C4 stack.
- `docs/agent-stack-decision-2026-04-29.md` §9 — falsification record;
  rationale for not reintroducing AG-UI / .NET.
- `.claude/CLAUDE.md` "Agent Framework & Chainlit Policy" — Context7
  IDs and the mandatory `?pivots=programming-language-python`.

### Mined research input (archived, stack-agnostic content only)

- `plan/_archived/failed-attempt-2026-04/feature-phase3a-tools-agent-1.md`
  — **Survived:** the read-only tool list shape (`get_upcoming_meetings`,
  `get_agenda_documents`, identity-as-non-model-parameter), the
  visibility-via-`shared.business_rules` rule, the JSON-string return
  contract, the AuditMiddleware idea. **Dropped:** AG-UI / FastAPI /
  uvicorn deps, `function_invocation_kwargs` injection mechanism
  (replaced by closure-bound DI per scaffold PAT-001), `lookup_delegate`
  as a top-level UC1 tool (covered by scaffold's
  `get_current_delegate_summary`), `agent-framework-ag-ui` package.
- `plan/_archived/failed-attempt-2026-04/feature-phase3d-brief-logic-and-tests-1.md`
  — **Survived:** brief-trigger / brief-suppress / grounding / DAR
  test scenarios; the in-memory SQLite + `seed_all` fixture pattern;
  the "mock the LLM, assert the tool sequence" stance for CI; the
  "≥ 20 tests" precedent (we relax to ≥ 10 for UC1 alone). **Dropped:**
  CopilotKit-frontend doc-closure tasks, AG-UI server confirmation,
  `BRIEF_LOOKBACK_DAYS=7` as the *forward* meeting window (it was
  always a *backward* "new docs since" window — see §3 "Upcoming
  window semantics").
- `plan/_archived/failed-attempt-2026-04/feature-phase3-chat-typography-fix-1.md`
  — **Dropped entirely.** CopilotKit-CSS-specific. Chainlit's
  default markdown rendering supersedes; no custom CSS needed for
  UC1 MVP.

### TBD register (all resolved 2026-05-02 by user)

| ID | Question | Settled value | Status |
|---|---|---|---|
| TBD-1 | Latency target for first streamed token | ≤ 3 s p50 / ≤ 6 s p95 | resolved — Resolved 2026-05-02 by user. |
| TBD-2 | Demo audience (internal-only or external OECD demonstrator) | internal OECD demonstrator | resolved — Resolved 2026-05-02 by user. |
| TBD-3 | First-login behaviour when `delegate.last_login is None` | full agenda + soft "first login" lead-in line | resolved — Resolved 2026-05-02 by user. |
| TBD-4 | Suppress whole meeting when delegate has zero visible docs? | No — show meeting + "no documents available to you" placeholder | resolved — Resolved 2026-05-02 by user. |
| TBD-5 | Forward "upcoming" window length | 30 days | resolved — Resolved 2026-05-02 by user. |
| TBD-6 | Should UC1 update `delegate.last_login` after rendering? | Yes — at end of brief render | resolved — Resolved 2026-05-02 by user. |
| TBD-7 | Is `delegate.last_login` populated in the seed corpus? | Backdate to 7 days ago for one demo persona; null for others (idempotent extension to `shared/seed_data.py`) | resolved — Resolved 2026-05-02 by user. |

---

*End of PRD — UC1 Proactive Meeting Brief.*
