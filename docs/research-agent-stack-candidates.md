# Agent Frontend Stack — Candidate Survey (Step 2)

> Companion to `docs/research-agent-stack.md`. Criteria live there.
> This file holds the discovery log, longlist, hard-gate results, and
> per-candidate writeups.

## §1. Discovery Log (Step 2.0)

Date: 2026-04-28. Training cutoff: 2026-01. Web search executed because the
agent UI space is bleeding-edge and ~3 months of changes are blind spots.

### §1.1 Queries Run

| # | Query |
|---|---|
| 1 | `microsoft agent framework python frontend integration 2026` |
| 2 | `AG-UI protocol alternative agent UI 2026` |
| 3 | `CopilotKit human in the loop approval 2026 update` |
| 4 | `agent chat UI streaming tool calls framework 2026` |
| 5 | `Chainlit Streamlit Gradio agent framework 2026 release` |
| 6 | `agent UI human in the loop approval pattern multi-turn 2026` |

### §1.2 Headline Findings

1. **Microsoft Agent Framework 1.0 GA shipped 2026-04-03** — production-ready,
   .NET + Python, unifies Semantic Kernel + AutoGen, MCP + A2A first-class.
   Source: Microsoft devblogs, Visual Studio Magazine, PyPI `agent-framework`.
2. **AG-UI is the Microsoft-recommended frontend protocol.** Official MS Learn
   integration docs at `learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/`
   including a dedicated Human-in-the-Loop page. `agent_framework_ag_ui` Python
   package is still beta (requires `--pre` install flag). MS-published demo
   uses FastAPI backend + Vite/React frontend.
3. **CopilotKit remains the AG-UI reference frontend.** Active 2026 docs;
   `useHumanInTheLoop` hook; recent emphasis on LangGraph interrupt-style
   pause/resume. CopilotKit is "the makers of the AG-UI Protocol" per their
   GitHub bio.
4. **Tension to resolve in deep-dive:** the archived attempt was abandoned
   2026-04-28 but MAF 1.0 GA shipped 2026-04-03 — 25 days earlier. GA either
   did not fix the AG-UI HITL contract bugs the attempt encountered, or the
   attempt used patterns that the GA docs no longer recommend. Must compare
   the current MS Learn HITL guidance against what the archived attempt
   implemented before deciding whether to re-evaluate AG-UI.
5. **A2UI (Google)** — new declarative-component protocol (agent ships UI
   descriptions; client renders native widgets). Positioned as a complementary
   layer to AG-UI, not a replacement. Not obviously useful for PoC but worth
   one-sentence triage.
6. **assistant-ui** — surfaced as a 2026 "standard for React projects"
   alongside CopilotKit. Not yet investigated in detail.
7. **Vercel AI SDK 6** — introduced an `Agent` abstraction with type-safe
   streaming for multi-step workflows, tool calls, structured outputs.
   No custom WebSocket/SSE plumbing required. JS/TS only.
8. **Agent Chat UI (langchain-ai/agent-chat-ui)** — open-source Next.js app
   for LangGraph agents; renders tool calls and results. LangGraph-native;
   would require a bridge to MAF.
9. **Chainlit** — Python-native, purpose-built conversational UI; native
   streaming, step-by-step agent reasoning display, persistent conversation
   history, authentication. Not Next.js, not React-component-driven; opinionated
   chat surface.
10. **Streamlit / Gradio** — general-purpose Python UI (dashboards, ML demos),
    not chat-first. Likely fail multi-route + structured rendering must-haves
    but cheap to confirm.
11. **Cloudflare Agents** has a durable `waitForApproval()` HITL primitive;
    OpenAI Agents SDK lists 5 HITL patterns. Both are agent-runtime features,
    not frontend stacks — informational only.
12. **Thesys / Crayon** — mentioned for "rapid prototyping" of generative UI.
    Not yet investigated.

### §1.3 Path A Verification — AG-UI Revisit Tension Resolved (2026-04-28)

Per user direction, fetched the current MS Learn HITL-with-AG-UI page and the
PyPI page for `agent-framework-ag-ui` to determine whether GA-era guidance
changes the AG-UI viability calculus.

**MS Learn `integrations/ag-ui/human-in-the-loop` (created 2026-04-01,
updated 2026-04-09):**

- **C# section** is polished, explicit, and documents the *exact* multi-turn
  bug the archived attempt hit, with a documented fix:
  > "After converting approval responses, both the `request_approval` tool
  > call and its result must be removed from the message history. Otherwise,
  > Azure OpenAI will return an error: `tool_calls must be followed by tool
  > messages responding to each 'tool_call_id'`."
- **Python section** is structurally **broken** as published. The client code
  sample references variables that are never assigned (`event_type`,
  `pending_approval`), conflates `update` (Python iterator) with `event`
  (raw dict), and would not run unmodified. The Python equivalent of the C#
  message-history cleanup is **not shown** — either `AgentFrameworkAgent` /
  `AGUIChatClient` handle it implicitly (opaque) or the Python integration
  silently inherits the bug.
- **Documented Python pattern (when working):** `@tool(approval_mode=
  "always_require")` → `AgentFrameworkAgent(agent=agent,
  require_confirmation=True)` → `add_agent_framework_fastapi_endpoint(app,
  wrapped_agent, "/")`. Approval events: `APPROVAL_REQUEST` (server →
  client) and `APPROVAL_RESPONSE` (client → server) carrying `approvalId`,
  `steps[]`, `approved: bool`. Approval response is sent via separate
  `AGUIChatClient.send_approval_response(approval_id, approved)` call,
  not in-stream.
- **CopilotKit integration claim** (from `integrations/ag-ui/index`):
  registering the endpoint as `HttpAgent` in CopilotKit runtime makes
  "all AG-UI features (streaming, approvals, state sync) work
  automatically." The archived attempt's V2Provider non-render
  empirically refutes this for `function_approval_request`.

**PyPI `agent-framework-ag-ui`:**

- Latest version: `1.0.0b260428`, published **2026-04-28 (today)**.
  Coincides with the day the archived attempt was abandoned.
- Status: Beta (`Development Status :: 4 - Beta`).
- Install: `pip install agent-framework-ag-ui` (or with `--pre` per MS
  Learn integration overview).
- Python ≥ 3.10.
- Changelog detail: not on the PyPI page. Must check GitHub releases /
  CHANGELOG to know whether today's beta includes fixes for the attempt's
  failure modes.

**Resolution:**

AG-UI revisit is justified — it is the Microsoft-blessed path and the HITL
pattern is documented. But the Python integration is **not yet GA-quality**:
official sample code is broken, the package is beta, the multi-turn
message-history pitfall is documented for C# only, and the "automatic"
CopilotKit claim was empirically refuted by the archived attempt.

**Decision:** include AG-UI (with `agent-framework-ag-ui` + CopilotKit React
frontend) in the longlist, but **do not default to it**. Require a Step 3
HITL spike that exercises (a) approval render, (b) approval response
delivery, (c) denial path closing the tool-call cleanly, (d) three or more
turns with at least one denied approval. Pass criterion: no 400, no orphan
tool_call, no manual message-history surgery beyond what the Python package
handles internally. If today's beta release notes reveal fixes for these
specific issues, spike confidence is higher; otherwise treat as high-risk.

Open discovery item created: **fetch `agent-framework-ag-ui` GitHub release
notes / CHANGELOG for the `1.0.0b260428` build** (deferred to deep-dive).

### §1.4 Sources Added During Path A Verification

- [MS Learn — HITL with AG-UI (verified 2026-04-28)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/human-in-the-loop)
- [MS Learn — AG-UI Integration overview (verified 2026-04-28)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/)
- [PyPI — agent-framework-ag-ui 1.0.0b260428](https://pypi.org/project/agent-framework-ag-ui/)

### §1.5 Open Discovery Items (deferred to longlist deep-dive — pre-existing, augmented by §1.3)

- Verify current MS Learn HITL with AG-UI page content vs archived attempt's
  approach. Critical for the AG-UI revisit decision.
- Pull `agent_framework_ag_ui` package release notes / changelog (PyPI + GH).
- Check assistant-ui primary docs (positioning, HITL support, framework
  compatibility).
- Check Vercel AI SDK 6 Python-backend story (it's a TS SDK; what's the
  Python-server contract?).
- Check Chainlit's HITL story specifically (do they have an approval primitive,
  or is it user-implemented?).

### §1.6 Sources (initial discovery sweep)

- [microsoft/agent-framework GitHub](https://github.com/microsoft/agent-framework)
- [Microsoft Agent Framework 1.0 GA blog](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/)
- [VS Magazine — MAF 1.0 ships](https://visualstudiomagazine.com/articles/2026/04/06/microsoft-ships-production-ready-agent-framework-1-0-for-net-and-python.aspx)
- [MS Learn — Agent Framework Overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [MS Learn — Python 2026 Significant Changes](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes)
- [MS Learn — AG-UI Integration](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/)
- [MS Learn — Human-in-the-Loop with AG-UI](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/human-in-the-loop)
- [MS DevBlogs — AG-UI Multi-Agent Workflow Demo](https://devblogs.microsoft.com/agent-framework/ag-ui-multi-agent-workflow-demo/)
- [MS Tech Community — Building Interactive Agent UIs with AG-UI and MAF](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/building-interactive-agent-uis-with-ag-ui-and-microsoft-agent-framework/4488249)
- [PyPI — agent-framework](https://pypi.org/project/agent-framework/)
- [DEV — Build a Frontend for MAF Python Agents with AG-UI](https://dev.to/copilotkit/build-a-frontend-for-your-microsoft-agent-framework-python-agents-with-ag-ui-4ghk)
- [AG-UI Protocol homepage (CopilotKit)](https://www.copilotkit.ai/ag-ui)
- [AG-UI docs](https://docs.ag-ui.com/introduction)
- [ag-ui-protocol/ag-ui GitHub](https://github.com/ag-ui-protocol/ag-ui)
- [CopilotKit GitHub](https://github.com/CopilotKit/CopilotKit)
- [CopilotKit — Human-in-the-Loop docs](https://docs.copilotkit.ai/human-in-the-loop)
- [CopilotKit — CoAgents HITL](https://docs.copilotkit.ai/coagents/human-in-the-loop)
- [CopilotKit — useHumanInTheLoop hook](https://docs.copilotkit.ai/reference/hooks/useHumanInTheLoop)
- [CopilotKit Blog — Buildtime and Runtime HITL](https://www.copilotkit.ai/blog/buildtime-and-runtime)
- [Google Developers — A2UI](https://developers.googleblog.com/introducing-a2ui-an-open-project-for-agent-driven-interfaces/)
- [A2UI homepage](https://a2ui.org/)
- [Google Developers — AI Agent Protocols Guide](https://developers.googleblog.com/developers-guide-to-ai-agent-protocols/)
- [langchain-ai/agent-chat-ui GitHub](https://github.com/langchain-ai/agent-chat-ui)
- [LangChain docs — Agent Chat UI](https://docs.langchain.com/oss/python/langchain/ui)
- [Cloudflare Agents — Human in the Loop](https://developers.cloudflare.com/agents/concepts/human-in-the-loop/)
- [OpenAI Agents SDK — Human-in-the-Loop](https://openai.github.io/openai-agents-js/guides/human-in-the-loop/)
- [Medium — Streamlit vs Gradio vs Chainlit (Mar 2026)](https://medium.com/@atnoforgenai/streamlit-vs-gradio-vs-chainlit-building-quick-uis-for-your-ai-applications-138e3baa5317)
- [Fastio — 7 Best UI Frameworks for AI Agents (2026)](https://fast.io/resources/best-ui-frameworks-ai-agents/)
- [Medium — Generative UI Frameworks 2026](https://medium.com/@akshaychame2/the-complete-guide-to-generative-ui-frameworks-in-2026-fde71c4fa8cc)

## §2. Longlist (Step 2.1)

Approved 2026-04-28. Nine candidates carried to hard-gate.

| # | Candidate | One-line description |
|---|---|---|
| C1 | AG-UI + CopilotKit React | Microsoft-blessed path. `agent-framework-ag-ui` server + CopilotKit `HttpAgent` client. Revisit despite archived failure. |
| C2 | AG-UI + custom React/Next.js client | Same server, custom AG-UI consumer. Drops CopilotKit's V2Provider opacity. |
| C3 | AG-UI + assistant-ui | React component library named alongside CopilotKit in 2026 surveys. AG-UI compatibility unverified. |
| C4 | Chainlit + custom MAF bridge | Python-native conversational UI. Bypass AG-UI; call MAF directly from Chainlit handlers. |
| C5 | Custom FastAPI + SSE + minimal Next.js client | No protocol layer. Define our own event shapes. Highest control, highest implementation cost. |
| C6 | Vercel AI SDK 6 frontend + custom Python server | TS Agent abstraction; Python backend must implement Vercel's wire protocol. |
| C7 | Agent Chat UI (LangChain) adapted to MAF | Open-source Next.js app; LangGraph-native, MAF adapter would be substantial work. |
| C8 | Streamlit / Gradio | General-purpose Python UI. Cheap-confirm bucket; expect failure on multi-route. |
| C9 | A2UI (Google) | Bleeding-edge declarative-component protocol; positioned as complementary to AG-UI, not replacement. |

## §3. Hard-Gate Results (Step 2.2)

Each candidate scored against `docs/research-agent-stack.md` §3 must-haves.
Legend: **✅** pass (confident from primary sources or first principles),
**❓** unclear (resolve in Step 2.3 primary-source check), **❌** fail
(disqualifying).

### §3.1 Score Matrix

| Criterion | C1 AG-UI+CopilotKit | C2 AG-UI+custom | C3 AG-UI+assistant-ui | C4 Chainlit | C5 Custom FastAPI+Next | C6 Vercel AI SDK 6 | C7 LC Agent Chat UI | C8 Streamlit/Gradio | C9 A2UI |
|---|---|---|---|---|---|---|---|---|---|
| 3.1 Streaming | ✅ | ✅ | ❓ | ✅ | ✅ | ✅ | ✅ | ✅ | ❓ |
| 3.2 In-session HITL render+resolve | ❓ | ❓ | ❓ | ❓ | ✅ | ❓ | ❓ | ❓ | ❓ |
| 3.3 Denied-approval clean close | ❓ | ❓ | ❓ | ❓ | ✅ | ❓ | ❓ | ❓ | ❓ |
| 3.4 Multi-turn ordering preserved | ❓ | ❓ | ❓ | ✅ | ✅ | ❓ | ❓ | ✅ | ❓ |
| 3.5 Identity threading | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3.6 Server-authoritative session | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❓ | ❓ |
| 3.7 MAF Python compat | ✅ | ✅ | ❓ | ✅ | ✅ | ❓ | ❌ | ✅ | ❌ |
| 3.8 Multi-route shared session | ❓ | ✅ | ❓ | ❓ | ✅ | ✅ | ❓ | ❌ | ❓ |
| 3.9 Async approval queue (UC3) | ✅ | ✅ | ❓ | ❓ | ✅ | ✅ | ✅ | ✅ | ❓ |
| 3.10 5-min demoability | ✅ | ⚠️ medium effort | ❓ | ✅ | ⚠️ medium effort | ⚠️ medium effort | ⚠️ adapter cost | ✅ | ❓ |

### §3.2 Disqualifications and Cuts

- **C7 (LangChain Agent Chat UI)** — fail 3.7. The app is LangGraph-native;
  adapting it to consume MAF events without rewriting the chat layer is
  substantial work that competes against C5 (custom from scratch) on cost
  while inheriting LangGraph assumptions we don't want. **Drop.**
- **C8 (Streamlit / Gradio)** — fail 3.8. Both are single-app dashboard
  frameworks; multi-route with shared agent session per delegate is at best
  brittle (Streamlit reruns the whole script on interaction; state survives
  via `st.session_state` but cross-route session continuity is awkward).
  Acknowledged out of the gate; cheap-confirm step done. **Drop.**
- **C9 (A2UI)** — fail 3.7. Bleeding-edge protocol; no documented MAF
  integration; positioned as complementary to AG-UI, not as a frontend stack.
  Wrong abstraction layer for this decision. **Drop.**
- **C6 (Vercel AI SDK 6 + Python server)** — borderline. Provisional **drop**:
  the SDK's Agent abstraction expects a TS-shaped wire protocol bound to
  Next.js route handlers; pairing it with a MAF Python backend means
  re-implementing Vercel's protocol on the Python side, while losing the
  SDK's ergonomic wins (its Agent abstraction lives in the TS server).
  This is parallel work to C5 with extra friction, no clear advantage.
  Reopen if a candidate-of-last-resort scenario emerges.

### §3.3 Survivors → Step 2.3 Primary-Source Check

Five candidates carry forward: **C1, C2, C3, C4, C5**. Required checks:

- **C1 / C2 / agent-framework-ag-ui server behavior:** does the
  `1.0.0b260428` (today's beta) release fix the multi-turn message-history
  cleanup that the C# docs document but the Python sample does not? If yes,
  C1 ❓ → ✅ on 3.4. If no, both C1 and C2 inherit a backend-side bug that
  no client choice can fix. Action: fetch GitHub releases / CHANGELOG for
  `microsoft/agent-framework` repo, scope to `agent-framework-ag-ui`
  package.
- **C1 specifically:** does CopilotKit's current React provider render
  `function_approval_request` events automatically, given the registered
  `HttpAgent`? Action: fetch
  [docs.copilotkit.ai/microsoft-agent-framework](https://docs.copilotkit.ai/microsoft-agent-framework)
  + `useHumanInTheLoop` reference.
- **C2 specifically:** confirm AG-UI client protocol allows direct
  consumption without CopilotKit. Action: fetch
  [docs.ag-ui.com/introduction](https://docs.ag-ui.com/introduction)
  client implementation guide.
- **C3 (assistant-ui):** confirm AG-UI compatibility, HITL pattern, MAF
  story (if any). Action: fetch assistant-ui homepage + docs;
  determine whether it speaks AG-UI or expects its own protocol.
- **C4 (Chainlit):** confirm (a) HITL primitive (does
  `cl.AskActionMessage` map cleanly onto MAF `approval_mode`?),
  (b) multi-route story (Chat Profiles vs separate apps for UC3 approver),
  (c) tool-call streaming display. Action: fetch
  [docs.chainlit.io](https://docs.chainlit.io) sections on actions, chat
  profiles, async messages.
- **C5 (custom):** no primary-source check needed — by construction we
  meet all must-haves, the question is implementation cost. Set baseline
  for "scope" comparison against C1–C4.

After Step 2.3, ❓ cells flip to ✅ or ❌. Anything still ❓ on a must-have
fails the gate.

## §4. Primary-Source Notes (Step 2.3)

Primary-source verification round 1, 2026-04-28.

### §4.1 Headline Finding — AG-UI Protocol Has No Standard HITL

`docs.ag-ui.com/concepts/events` enumerates all protocol events. The complete
list: `TextMessageStart/Content/End/Chunk`, `ToolCallStart/Args/End/Result/
Chunk`, `RunStarted/Finished/Error`, `StepStarted/Finished`. There is **no**
`APPROVAL_*` or `FUNCTION_APPROVAL_*` event in the AG-UI protocol. HITL is
explicitly unspecified — left to implementers.

**Implications:**

- The MS Python Agent Framework's HITL flow is layered on top of the standard
  AG-UI tool-call events. Per the C# sample on
  `learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/human-in-the-loop`:
  approval requests are encoded as a synthetic tool call named
  `request_approval` whose arguments contain the original function call
  details; the user's decision is sent back as a `ToolCallResult` carrying
  the approval payload. The Python sample's `APPROVAL_REQUEST` /
  `APPROVAL_RESPONSE` event types appear to be a higher-level wrapper over
  this same wire mechanism inside `agent-framework-ag-ui`.
- CopilotKit's `useHumanInTheLoop` hook (per deepwiki extract dated
  2026-03-28) is built around **LangGraph interrupts** — events
  `on_copilotkit_interrupt` / `LangGraphInterruptEvent`. There is no
  evidence that the hook recognizes the MS `request_approval` tool-call
  shape.

**This is a plausible root cause for the archived attempt's
"V2Provider not rendering function_approval_request" symptom**: CopilotKit
was waiting for LangGraph-shaped interrupts; the MS AG-UI server was
emitting `request_approval` tool-calls. The two mechanisms passed each
other without colliding.

### §4.2 Per-Candidate Findings

#### C1 — AG-UI + CopilotKit React

- CopilotKit `useHumanInTheLoop` is LangGraph-interrupt-flavored. The
  developer is expected to render approval UI manually inside the hook's
  handler — it is not auto-rendered by a provider.
- No documented support for the MS `request_approval` tool-call HITL shape
  in CopilotKit's MAF integration page (page returned empty content —
  client-side rendered; could not verify directly, but deepwiki docs limit
  HITL coverage to `LangGraphAgent`).
- Bridging CopilotKit HITL onto MS Agent Framework's approval mechanism
  requires a custom adapter (intercept `request_approval` tool calls
  on the React side and translate them into CopilotKit's HITL state).
- Risk **higher** than first scored. 3.2/3.3 stay ❓ but the path to ✅
  is now known to require glue code.

#### C2 — AG-UI + custom React/Next.js client

- AG-UI introduction page explicitly supports direct client implementation:
  > "Build new clients for AG-UI-compatible agents (web, mobile, slack,
  > messaging, etc.)"
- A custom client receives `request_approval` as ordinary
  `ToolCallStart/Args/End` events. Render: developer's choice. Denial:
  send a `ToolCallResult` event with `{approved: false}`. Approval: send
  `{approved: true}`.
- Backend-side message-history cleanup risk persists. The Python
  `agent-framework-ag-ui` package may or may not internally clean up
  the `request_approval` tool-call from history before the next turn —
  no documented behavior, no relevant changelog entry in 1.1.x or 1.2.x.
- 3.4 verdict still ❓ pending spike. 3.2/3.3 ✅-trajectory (we control
  the render and the response shape).

#### C3 — AG-UI + assistant-ui

- assistant-ui supports AG-UI via a dedicated `useAgUiRuntime` adapter.
- HITL primitive surfaced in docs is LangGraph-flavored ("human-in-the-
  loop approval for tool calls" in LangGraph tutorial) plus Google ADK
  ("Tool confirmations, auth, input requests"). Same wire mismatch as
  CopilotKit.
- **No documented integration with Microsoft Agent Framework Python.**
- Verdict: provisional **drop**. assistant-ui inherits the same protocol
  mismatch as CopilotKit while adding "no documented MAF story" on top.
  Reopen only if C1/C2/C4/C5 all fail.

#### C4 — Chainlit + custom MAF bridge

- `cl.AskActionMessage`: blocking `await .send()` pattern, action buttons
  with payloads, `AskActionResponse | None` return, default 90s timeout.
  This is structurally correct for in-session HITL — pause MAF run, show
  buttons, capture response, resume.
- Multi-turn ordering: not addressed in docs but Chainlit is a Python
  process that drives MAF directly; message history lives in MAF's
  `AgentSession`, not on a wire. No protocol-level cleanup risk.
- Multi-route story: `docs.chainlit.io/concepts/chat-profiles` returned
  404. Chainlit is fundamentally a single-app chat-first framework.
  Chat profiles (if they exist under a different URL) are different
  starting configurations within one chat surface, not separate routes.
  Multi-route via separate Chainlit apps is possible but breaks the
  "one shared session per delegate" requirement.
- 3.8 risk **high**. Likely FAIL unless Chainlit's chat-profile or
  multi-page features have evolved (open item).

#### C5 — Custom FastAPI + SSE + minimal Next.js client

- No primary-source check needed. By construction passes all must-haves;
  the question is implementation cost and time-to-demo.
- Implementation footprint estimate (rough): ~300 lines server (FastAPI
  endpoint streaming MAF events, identity middleware, session keying),
  ~500 lines Next.js (chat surface, structured panels for UC1 brief,
  approval modal, approver inbox), plus ad-hoc plumbing. Single-developer
  tractable for PoC.
- Trade-off: zero protocol leverage. Every event shape we define is one
  we maintain.

### §4.3 Updated Score Matrix

| Criterion | C1 CopilotKit | C2 custom AG-UI | C3 assistant-ui | C4 Chainlit | C5 custom |
|---|---|---|---|---|---|
| 3.1 Streaming | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3.2 In-session HITL render+resolve | ⚠️ adapter | ❓ spike | ⚠️ adapter | ✅ | ✅ |
| 3.3 Denied-approval clean close | ❓ spike | ❓ spike | ❓ spike | ✅ | ✅ |
| 3.4 Multi-turn ordering | ❓ backend | ❓ backend | ❓ backend | ✅ | ✅ |
| 3.5 Identity threading | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3.6 Server-authoritative session | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3.7 MAF Python compat | ✅ | ✅ | ❌ undocumented | ✅ | ✅ |
| 3.8 Multi-route shared session | ❓ HMR risk | ✅ | ❓ | ❌ likely | ✅ |
| 3.9 Async approval queue (UC3) | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3.10 5-min demoability | ✅ | ⚠️ medium | ❓ | ✅ | ⚠️ medium |

Drops after Step 2.3:
- **C3 assistant-ui** — fails 3.7 (no documented MAF integration) plus
  inherits C1's wire-mismatch. Drop.
- **C4 Chainlit** — fails 3.8 (single-page framework, no multi-route).
  Drop with reopen-clause if PoC scope shrinks to single chat surface.

Carrying forward to Step 2.5 (writeups) and Step 2.6 (finalists):
- **C1 AG-UI + CopilotKit** — possible but adapter-heavy.
- **C2 AG-UI + custom client** — cleanest AG-UI path; backend risk
  remains.
- **C5 Custom FastAPI + Next.js** — strongest control; highest scope.

## §5. Spike Results (Step 3)

Spike code: `spikes/`. Branch: `research/agent-stack-spikes`. Plan:
`plan/research-agent-stack-spike.md`. Each spike runs the same four-turn
scenario (T1 list / T2 create-approve gamma / T3 create-deny delta / T4
list-again) against an identical MAF agent (`spikes/_shared/agent.py`).

### §5.1 C4 — Chainlit + MAF direct (2026-04-29)

**Result: FULL PASS.** All four turns clean.

| Turn | Outcome |
|---|---|
| T1 | "The records currently stored are: alpha, beta." |
| T2 | Approval prompt rendered with function name + arguments. User approved. Agent: "The record named 'gamma' has been created." |
| T3 | Approval prompt rendered. User denied. Agent: "It seems the creation of the record named 'delta' was not approved by the system. Let me know if you'd like to try something else." |
| T4 | "The records currently stored are: alpha, beta, gamma." Delta correctly absent. |

Failure modes watched:
- **F1 (approval not rendered)** — did not fire. `cl.AskActionMessage`
  rendered immediately on `user_input_requests` emission.
- **F2 (multi-turn 400 from out-of-order tool history)** — did not fire.
  T3→T4 transition succeeded despite the denial. The MAF `AgentSession`
  held history correctly across the approval round-trip without a
  protocol-layer middleman.

Implementation cost: ~120 LOC including shared scaffold and per-spike
plumbing. Two wiring fixes during build:
1. Initial run had no `AgentSession`; agent forgot prior turns. Fix:
   `session = agent.create_session()` in `on_chat_start`,
   `agent.run(..., session=session)` in `on_message`.
2. Initial system prompt instructed the model to "confirm the name
   before calling create_record" — caused verbal pre-confirmation that
   bypassed `approval_mode`. Fix: instruct the model to call the tool
   immediately and let the system handle approval.

**Verdict for C4:** passes all must-haves on the empirical contract
test. With multi-route relaxed (Q3 reframe accepted), this is the
cleanest stack on the table.

### §5.2 C2 — AG-UI server + thin Python client (2026-04-29)

Strategy pivot: built a Python `AGUIChatClient` driver instead of a
bespoke JS/TS client. The hypothesis under test (F2 — backend
message-history cleanup gap) is server-side; frontend language does
not change the test, and C4 already winning made the JS-toolchain
investment unjustified.

**Result: F1 fires — approval not surfaced on the client side.**

| Turn | Outcome |
|---|---|
| T1 | "The current records are: alpha, beta." Streaming + tool call + result all worked over the AG-UI wire. |
| T2 | **Empty response.** No approval prompt rendered. Agent did not fire `create_record`; gamma was not created. |
| T3 | Asked to list, agent reported gamma absent and acknowledged "The record 'gamma' was not created." Server state consistent with T2 hanging mid-approval. |
| T4 | Not exercised (T2/T3 already disqualified the candidate). |

**Root cause confirmed empirically:**

The AG-UI protocol has no `APPROVAL_*` events. The server encodes
approval requests as a regular tool call: `TOOL_CALL_START` with
`toolName="request_approval"` followed by streamed `TOOL_CALL_ARGS`
carrying the ApprovalRequest payload (approvalId, function name,
function arguments). The client-side `Agent + AGUIChatClient` pipeline
treats this as an ordinary tool call — `_event_converters.py` confirmed
to have no special handling for `request_approval`. `chunk.user_input_requests`
is never populated; the application loop sees nothing to render.

To make C2 work, the client must add custom logic: intercept tool-call
events with `toolName == "request_approval"`, parse the streamed
arguments, render an approval UI, and post back a `TOOL_CALL_RESULT`
message containing `{"accepted": bool}`. This is significantly more
than "super simple" — it is exactly the bespoke wire-handling that the
C2 design proposed to avoid by talking AG-UI directly.

**Implication for C1 (CopilotKit):**

The architecture-level wire-mismatch is now confirmed at the protocol
layer, not just CopilotKit-specifically. Any AG-UI frontend (CopilotKit,
custom JS, Python AGUIChatClient) that wants to render MS Agent
Framework `approval_mode` approvals must implement custom logic to
recognize `request_approval` tool calls and render UI. CopilotKit's
`useHumanInTheLoop` is for *frontend-registered* HITL tools, not
backend-emitted approval requests, so the bridging code would have to
sit alongside (not on) `useHumanInTheLoop`.

**F2 status:** Untested. Spike never reached the multi-turn-after-denial
state because T2 hung on the unrendered approval. Cannot empirically
confirm or refute the message-history cleanup gap.

**Verdict for C2:** Falsifies the "skip CopilotKit and AG-UI is
straightforward" framing of the candidate. AG-UI's protocol-layer
absence of HITL semantics pushes meaningful adapter work onto every
frontend. C2 is technically feasible with adapter code; not "super
simple" and offers no path that C5 (custom FastAPI + custom client) does
not also offer with less protocol baggage.

### §5.3 C1 — AG-UI server + CopilotKit React

TBD.

### §5.4 Decision

After C4 passing the spike, the plan's decision rule already
selects C4 regardless of C1 / C2 outcomes (lower scope, no AG-UI
risk, no JS toolchain). C1 and C2 spikes carry forward as
**falsification-only** to honour the "extra sure" framing — they no
longer affect finalist selection.

## §6. Finalists (Step 2.6)

TBD.
