# Agent Stack Decision — 2026-04-29

> Hand-off document. Captures the rationale, evidence, and next steps for
> the agent_app stack pivot decided on 2026-04-29 so a fresh conversation
> can pick up without rebuilding context.
>
> Companion documents (read in this order if you want the full story):
> 1. `docs/research-agent-stack.md` — criteria
> 2. `docs/research-agent-stack-candidates.md` — survey, hard-gate, spike results
> 3. **This document** — decision + path forward

## 1. Context

Phase 0 (model selection — `gpt-4.1-mini`), Phase 1 (shared data layer),
and Phase 2 (classical Flask app, read + write flows including the
8-screen add-delegate wizard) shipped to `main`. 188 tests passing.

The first attempt at `agent_app/` (Phase 3 / 3.5 / 4 + spikes), which
used Python + Microsoft Agent Framework + AG-UI + CopilotKit + Next.js,
was abandoned 2026-04-28 after multi-week struggle with HITL contract
fragility (multi-turn 400 from out-of-order tool history; V2Provider
not auto-rendering `function_approval_request`; denied-approval orphan
tool_call; HMR-induced state loss; brittle replay behaviour). All
artefacts moved to `_archived/` (gitignored).

Two open questions reopened: OQ-7 (frontend stack) and OQ-9 Phase-4
portion (approver UX).

## 2. Research Done (2026-04-28 → 2026-04-29)

Criteria-first survey. Highlights captured here; full record is in the
companion documents.

### 2.1 Criteria (must-haves)

`docs/research-agent-stack.md` defines ten must-haves. The decisive ones
turned out to be:

- **3.2** In-session HITL approval round-trip — guaranteed render,
  deterministic resolve.
- **3.3** Denied-approval path closes cleanly (no orphan tool_call, no
  multi-turn 400).
- **3.4** Multi-turn tool-call/result ordering preserved across the
  session.
- **3.7** Compatible with Microsoft Agent Framework (no Node/TS server
  in front of the agent).
- **3.10** Demoable on a laptop in under 5 minutes.

### 2.2 Use cases scoped on top of the criteria

- **UC1** — Proactive Meeting Brief (read-only, streamed brief on
  login).
- **UC2** — Delegate Creation with DAR (multi-turn write, in-session
  HITL via `approval_mode="always_require"`).
- **UC3** — Approver triage (Phase 4): delegation head and secretariat
  review pending DARs (`PENDING_DELEGATION_HEAD`,
  `PENDING_SECRETARIAT`) and approve or reject. Distinct from UC2 — UC3
  is an asynchronous queue served by ordinary agent tools, not the
  approval_mode mechanism.

### 2.3 Hard-gate survivors

After Step 2.3 primary-source verification, three candidates carried to
spike:

- **C1** — AG-UI server (Python `agent-framework-ag-ui`) + CopilotKit
  React client.
- **C2** — AG-UI server + custom client (Python AGUIChatClient or
  bespoke).
- **C4** — Chainlit + Microsoft Agent Framework Python directly (no
  AG-UI).

Plus C5 (custom FastAPI + custom Next.js, no AG-UI) held as last-resort
fallback.

Q3 was reframed during spike: the original "shared session across
routes" requirement was relaxed to "fresh session per workflow, identity
persists via auth." Each use case is workflow-scoped, not
history-scoped — tools read DB state, agent memory across UC1→UC2→UC3
is a nice-to-have not a must-have.

## 3. Spike Results

Spike code lives on the `research/agent-stack-spikes` branch. Plan:
`plan/research-agent-stack-spike.md`. Each spike ran the same four-turn
scenario:

- T1 — list records → expect "alpha, beta"
- T2 — create gamma → approve → expect "gamma created"
- T3 — create delta → **deny** → expect agent acknowledges denial
- T4 — list again → expect "alpha, beta, gamma" (delta absent)

### 3.1 C4 (Chainlit) — FULL PASS

All four turns passed cleanly. Approval prompt rendered immediately on
each `user_input_requests` emission via `cl.AskActionMessage`. Denial
path closed cleanly — agent acknowledged in natural language ("It seems
the creation of the record named 'delta' was not approved by the
system. Let me know if you'd like to try something else.") and T4
succeeded. Multi-turn ordering preserved via `agent.create_session()`.

Implementation cost: ~120 LOC including shared scaffold.

Two wiring fixes during build:
- Initial run had no `AgentSession`; agent forgot prior turns.
  Fix: `session = agent.create_session()` in `on_chat_start`,
  `agent.run(..., session=session)` in `on_message`.
- Initial system prompt told the model to "confirm the name before
  calling create_record" — caused verbal pre-confirmation that bypassed
  `approval_mode`. Fix: instruct the model to call the tool immediately
  and let the system handle approval.

### 3.2 C2 (Python AG-UI client) — empirically blocked

Tried three client implementations:
1. `Agent` + `AGUIChatClient` + `session=session`. Approval not
   surfaced via `chunk.user_input_requests`. T2 produced empty
   response.
2. Same with debug instrumentation — confirmed approval arrives via
   `chunk.additional_properties.ag_ui_custom_event` with
   `name="function_approval_request"`, NOT via `user_input_requests`.
3. Raw httpx + SSE direct against the server. Approval prompt rendered
   correctly on T2. Approval response sent back as a tool result
   message. Server logged
   `Rejected approval response id=<call_id>: no matching pending approval request`
   and OpenAI 400'd with `No tool output found for function call <id>`.

Tried two synthetic-tool-name conventions:
- `request_approval` (the C# convention from the C# zone of MS Learn)
  — server rejected.
- `confirm_changes` (the actual Python convention found by reading
  `_message_adapters.py` source) — server accepted but re-emitted the
  same approval, producing an endless loop.

Could not drive the round-trip to completion within the spike budget.

### 3.3 C1 (CopilotKit) — not built

Per the plan's decision rule, C4 passing made C1 falsification-only.
Given C2 ran into protocol-layer issues that would also affect C1
(both consume the same AG-UI Python wire), C1 was not built — would
add JS toolchain effort to confirm what C2 already showed.

## 4. Methodology Lesson

The deepest cause of confusion in C1/C2 spikes was a methodology error
on my (Claude's) part:

**MS Learn pages with `zone_pivot_groups: programming-languages`
default to C# unless the URL explicitly carries
`?pivots=programming-language-python`.** WebFetch and Context7 both
return the full markdown source which contains both languages, but the
*default-rendered* content is C#-flavoured.

I implicitly assumed the default content was language-neutral and
applied C# patterns (`request_approval` synthetic tool name, explicit
bidirectional middleware, message-history cleanup) to a Python
implementation that uses different conventions (`confirm_changes`
synthetic tool name, internal `_sanitize_tool_history` doing the
cleanup).

Independently — and verified across two fetches — the
`integrations/ag-ui/human-in-the-loop` Python zone was published with
**multiple structural bugs** in the client code sample:
- `chat_client = AGUIChatClient(server_url=server_url)` — wrong kwarg;
  actual API takes `endpoint=`.
- `event_type` referenced inside an `async for` loop but never assigned.
- `pending_approval` referenced after assignment to
  `pending_approval_update`.
- `client.send_approval_response(approval_id, approved)` called — the
  method does not exist on `AGUIChatClient` (verified via Python
  introspection on the installed `1.0.0b260428` build).

So the Python sample is **non-functional as published**. The wire
protocol works, but the client-side high-level Python API for HITL is
not yet usable as documented.

## 5. Decision

**Pivot the agent app to C# / .NET.** Keep everything else in Python.

### 5.1 What changes

- New `agent_app/` will be a C# / .NET project.
  - Hosts the AG-UI server (`Microsoft.Agents.AI.Hosting.AGUI.AspNetCore`).
  - Implements UC1 / UC2 / UC3 against the same SQLite database.
  - Frontend: CopilotKit React (per MS Learn quickstart and dojo
    samples) connected via `HttpAgent` runtime registration.
  - HITL via the documented C# bidirectional-middleware +
    `request_approval` client-tool pattern.
- `shared/business_rules.py` (compute_default_access_level,
  determine_approval_route, is_document_visible,
  get_visible_agenda_documents, get_new_documents_since) ported to C#.
  Small, stable surface (~200 LOC). Parity tests against the Python
  originals to catch drift.
- `shared/database.py` schema becomes the cross-language contract.
  Agent app reads via Microsoft.Data.Sqlite or EF Core (decide during
  spike). `shared/seed_data.py` stays Python; agent app reads what
  Python writes.

### 5.2 What stays the same

- `classical_app/` — unchanged. Python / Flask / WTForms / Bootstrap.
  Contrast tool. 102 baseline tests + 86 net-new from Phase 2 still
  green on `main`.
- `shared/database.py`, `shared/seed_data.py` — unchanged. SQLite is
  the integration surface.
- `eval/` — unchanged. Phase 0 evaluation harness retained for any
  future model-selection work.
- Selected model — `gpt-4.1-mini` via `FoundryChatClient`
  (`agent-framework-foundry` C# package).
- Phase 0 / 1 / 2 docs and decisions — unchanged. Phase 3+ plans get
  rewritten against the C# stack.

### 5.3 What we're explicitly rejecting

- **C2 (Python AG-UI custom client)** — protocol works on the wire but
  Python client-side surface is empirically under-baked; documented
  sample is broken; getting approvals to round-trip required
  reverse-engineering of `_message_adapters.py` and was not completable
  within the spike budget.
- **C1 (Python AG-UI + CopilotKit)** — inherits C2's wire-layer
  difficulties plus a heavier JS toolchain. Not worth a separate
  spike given C2's findings.
- **C4 (Chainlit) as the long-term pick** — passed the spike cleanly
  and remains a viable fallback if the C# pivot encounters surprises,
  but accepts a less-polished UI shell and no path to the documented
  HITL/approver-UX patterns Microsoft invests in for .NET.
- **C5 (custom FastAPI + custom Next.js)** — viable but offers no
  ecosystem leverage; only justified if both C4 and the C# pivot fail.

## 6. Open Items / Risks

- **CLAUDE.md** currently states "Project: ONE-MP Agent (Python 3.11,
  Microsoft Agent Framework)". Needs to be updated to reflect a
  cross-language project with Python for `classical_app/` + `shared/`
  and C# / .NET for `agent_app/`. Also needs a section on the C#
  conventions (probably a `dotnet format` / EditorConfig analogue to
  the ruff section).
- **Business-rules port** — port path needs an explicit parity-test
  scaffold so the two implementations cannot drift silently. Test
  cases live alongside the C# port; they should mirror the existing
  Python tests in `tests/shared/`.
- **Identity threading** — backend pattern in C# uses
  `function_invocation_kwargs` (or the .NET-side equivalent — verify
  during spike). The classical app uses
  Flask `session["delegate_id"]`; the agent app needs an analogous
  per-request identity propagation. Spike should make this explicit
  before PRD work.
- **Approver UX (UC3)** — agent-hosted (per OQ-1 resolution
  2026-04-29). Built as a separate route inside `agent_app/`. Uses
  ordinary agent tools against `DocumentAccessRight.approval_status`,
  not the in-session `approval_mode` mechanism.
- **`agent-framework-ag-ui` Python beta** — not used by us anymore
  but worth tracking. If Microsoft fixes the published Python sample
  and adds the missing `send_approval_response` API surface, the
  Python path becomes viable again. Set a calendar reminder for
  2026-Q3 to re-evaluate.
- **Spike code** — the `research/agent-stack-spikes` branch (Chainlit
  spike, Python AG-UI spike) stays unmerged but preserved as a
  falsification record. Do not delete.

## 7. Path Forward

Step-by-step plan from a fresh conversation:

### Step A — Update project conventions (small, do first)

- Update `CLAUDE.md`:
  - Header: "Project: ONE-MP Agent (Python 3.11 + .NET 8/9, Microsoft
    Agent Framework)".
  - Split style/format section into Python (existing ruff content) +
    C# (`dotnet format`, `.editorconfig`, target framework, nullable
    reference types).
  - Replace Phase 3+ Agent Framework + CopilotKit policy bullets with
    references to the .NET docs and CopilotKit MAF page.
- Update `docs/DESIGN.md`:
  - Stack table — Agent runtime: Microsoft Agent Framework (.NET).
    Agent frontend: CopilotKit React via AG-UI.
  - Project structure — add `agent_app/` (C# project layout) +
    `shared/csharp/` (or equivalent) for the ported business rules.
- Add `docs/DECISIONS.md` entry "Agent app pivots to C# / .NET
  (2026-04-29)" with a one-paragraph rationale and a link to this
  document.

### Step B — Scaffold and spike `agent_app/` in C# (≤ 1 day)

Create a minimal C# spike that runs the same T1–T4 scenario as the
Python spikes:

- `agent_app/` — `dotnet new web` (or `dotnet new console` for the
  client), .NET 8 or 9.
- Server: `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` +
  `Microsoft.Agents.AI` + `Microsoft.Agents.AI.Foundry` (`AsAIAgent`
  extension) + `Azure.Identity`. Two tools: `ListRecords` (no
  approval) + `CreateRecord` wrapped in `ApprovalRequiredAIFunction`.
  Bidirectional middleware per the C# zone of the MS Learn HITL doc.
  Mount via `app.MapAGUI("/", agent)`.
- Client (for the spike only): the `AGUIChatClient` console client
  from MS Learn `getting-started` page (.NET zone), extended to
  detect `FunctionApprovalRequestContent`, prompt approve/deny, and
  resume.
- Run T1–T4 with deny on T3. Pass criterion: matches C4's outcome
  (approve path works, deny path closes cleanly, T4 reflects T2
  success and T3 denial).

If the spike passes, the C# pivot is validated. If it fails on
something analogous to the Python issues, escalate before further
investment — fall back to C4 (Chainlit) for the PoC.

### Step C — Port `shared/business_rules.py` to C#

- Locations: `shared/csharp/BusinessRules.cs` (or a separate
  `BusinessRules.csproj` referenced by `agent_app/`).
- Port functions: `compute_default_access_level`,
  `determine_approval_route`, `is_document_visible`,
  `get_visible_agenda_documents`, `get_new_documents_since`.
- Tests: parity tests covering the same cases as
  `tests/shared/test_business_rules.py`. Both sides must produce
  identical outputs for the seeded data set.

### Step D — Rewrite the Phase 3+ plan and PRDs against the C# stack

- New PRDs:
  - `docs/prd-phase3-agent-uc1-brief.md` — UC1 (proactive meeting
    brief), C# / AG-UI / CopilotKit React.
  - `docs/prd-phase3-agent-uc2-delegate-creation.md` — UC2 with
    `ApprovalRequiredAIFunction` HITL.
  - `docs/prd-phase4-agent-uc3-approver-inbox.md` — UC3 approver
    triage as a separate CopilotKit route.
- Implementation plans per phase under `plan/`.

### Step E — Wire UC1 first, then UC2, then UC3

Each behind its own merge to `main`. Tests + visual-verify (Playwright)
per use case.

## 8. References

- `docs/research-agent-stack.md` — criteria
- `docs/research-agent-stack-candidates.md` — survey, hard-gate, spike
  results (§5)
- `plan/research-agent-stack-spike.md` — spike plan
- `spikes/_shared/agent.py` — shared Python scaffold (kept as
  reference)
- `spikes/c4_chainlit/app.py` — C4 spike (passed)
- `spikes/c2_custom_agui/server.py`, `client.py`, `raw_client.py` —
  C2 spike (blocked, kept as falsification record)
- MS Learn pages — always include `?pivots=programming-language-csharp`
  in the URL when verifying C# patterns; both languages are in the
  same markdown source but visual rendering depends on the pivot.

---

End of decision record. From a fresh conversation, the next concrete
action is **Step A** (update CLAUDE.md, DESIGN.md, DECISIONS.md), then
**Step B** (C# spike).
