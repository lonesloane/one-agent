# Plan — Agent Stack Spikes (C1, C2, C4)

> Step 3 of the agent frontend stack research (`docs/research-agent-stack.md`,
> `docs/research-agent-stack-candidates.md`). Empirically falsifies the
> hard-gate conclusions for the three remaining candidates before
> committing the agent_app rebuild to one stack.

## Goal

Build three throwaway minimum-viable spikes — one per candidate — and run
the same test scenario against each. Outcome: a small evidence table that
either confirms or contradicts the docs-archaeology verdict.

Candidates:

- **C1** AG-UI server (`agent-framework-ag-ui`) + CopilotKit React client.
  Hypothesis: wire-mismatch (CopilotKit's `useHumanInTheLoop` is
  frontend-registered; MS server emits backend `request_approval`).
  Approval prompt will not render without a custom adapter.
- **C2** AG-UI server (same package) + custom vanilla-TypeScript SSE
  client. Hypothesis: T1/T2/T3 work; T4 may 400 because Python
  `_message_adapters.py` does not strip `request_approval` history
  entries the way the C# documentation requires.
- **C4** Chainlit + MAF directly (no AG-UI). Hypothesis: clean pass on
  all four turns; `cl.AskActionMessage` is the right shape.

## Scope Constraints (read first)

- Each spike ≤ 200 LOC of hand-written code, excluding boilerplate.
- All three spikes share the same MAF agent definition + dummy tools.
- No real DB, no real auth, no real identity threading. Approval contract
  only.
- Spikes are throwaway. Code lives under `spikes/` (gitignored after
  decision) or on a dedicated `research/agent-stack-spikes` branch that
  is **not** merged.
- All three spikes use `gpt-4.1-mini` via `FoundryChatClient` per
  selected-model decision.

## Shared Scaffold

`spikes/_shared/agent.py` (~60 LOC):

```python
from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatCompletionClient
from azure.identity import AzureCliCredential
from typing import Annotated
from pydantic import Field
import os

_RECORDS: list[str] = ["alpha", "beta"]

@tool
def list_records() -> str:
    """Return a comma-separated list of records."""
    return ", ".join(_RECORDS)

@tool(approval_mode="always_require")
def create_record(
    name: Annotated[str, Field(description="Name of the record to create")],
) -> str:
    """Create a new record with the given name."""
    _RECORDS.append(name)
    return f"Record '{name}' created. Total: {len(_RECORDS)}."

def build_agent() -> Agent:
    client = OpenAIChatCompletionClient(
        model=os.environ["AZURE_OPENAI_CHAT_COMPLETION_MODEL"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        credential=AzureCliCredential(),
    )
    return Agent(
        name="SpikeAgent",
        instructions=(
            "You assist a user managing records. Use list_records for reads. "
            "Use create_record only when the user explicitly asks to create. "
            "Confirm the name with the user before calling create_record."
        ),
        client=client,
        tools=[list_records, create_record],
    )
```

This file is reused by every spike.

## Common Test Scenario

Run the same four-turn sequence against each spike, by hand:

| Turn | User input | Expected agent behavior | Pass criterion |
|---|---|---|---|
| T1 | "List the records" | Calls `list_records`, streams "alpha, beta" | Streaming visible; tool call rendered. |
| T2 | "Create a record named gamma" | Emits approval request for `create_record(name="gamma")` → user approves → tool fires | Approval prompt rendered; approve path works; result displayed. |
| T3 | "Create another one named delta" | Emits approval request → user **denies** → agent acknowledges and continues | Approval prompt rendered; deny path closes cleanly; no orphan tool call; agent emits a follow-up text. |
| T4 | "List the records again" | Calls `list_records`; result includes `gamma` (created in T2) but not `delta` (denied in T3) | Tool call fires without 400; result reflects T2 success and T3 denial; multi-turn history valid. |

Two failure modes to watch for explicitly:

- **F1 — Approval not rendered.** Symptom: client never shows an approval
  prompt for T2 or T3. Streams text or tool result directly without user
  intervention. (Predicted for C1.)
- **F2 — Multi-turn 400.** Symptom: T4 (or T3 follow-up message after
  denial) returns HTTP 400 from the model API with a "tool_calls must be
  followed by tool messages" error. (Predicted for C2.)

## Per-Spike Implementation

### Spike C1 — CopilotKit React

`spikes/c1_copilotkit/`:

- Server (`server.py`, ~40 LOC): import shared `build_agent`, wrap with
  `AgentFrameworkAgent(agent=agent, require_confirmation=True)`, mount
  via `add_agent_framework_fastapi_endpoint(app, wrapped_agent, "/")`.
- Client (`web/`): `npm create next-app@latest`, install
  `@copilotkit/react-core` and `@copilotkit/react-ui` (latest 2026-04
  versions). One page wrapped in `<CopilotKit>` provider with
  `runtimeUrl` pointing to a CopilotKitRuntime instance bridged to the
  AG-UI server via `HttpAgent`. Render `<CopilotChat />` for the chat
  surface. Add a `useHumanInTheLoop` hook with a render callback that
  draws Approve / Deny buttons.
- Run: server on `:8888`, runtime + Next on `:3001`. Walk through T1–T4
  manually.

**Spike succeeds if:** approvals render and T1–T4 all pass.
**Spike fails if:** F1 fires (predicted).

If F1 fires: try a second variant where we register the spike's
`create_record` as a CopilotKit *frontend tool* via `useHumanInTheLoop`
instead of as a backend MAF tool. If that variant succeeds, it confirms
CopilotKit only supports frontend-registered HITL — at the cost of
moving approval policy to the client (architecturally wrong for our
audit/identity goals; would not change the C1 verdict).

### Spike C2 — AG-UI server + vanilla TS client

`spikes/c2_custom_agui/`:

- Server: same as C1's server (shared).
- Client (`web/`): plain TypeScript + Vite, no framework. EventSource
  consumer for the AG-UI SSE stream. Render messages as `<div>`s; render
  `request_approval` tool calls as a `<button>Approve</button>
  <button>Deny</button>` pair. POST the approval response back via
  `fetch`. ~150 LOC.
- Run: server on `:8888`, Vite on `:5173`. Walk through T1–T4.

**Spike succeeds if:** all four turns pass cleanly.
**Spike fails if:** F2 fires on T3 → T4 transition (predicted by source
read of `_message_adapters.py`). If F2 fires, try a workaround: have the
client strip `request_approval` entries from the locally-tracked history
before sending the next user message. If that workaround unblocks T4,
the verdict is "C2 viable but requires client-side history hygiene"; if
not, the bug is server-internal and C2 is dead.

### Spike C4 — Chainlit + MAF direct

`spikes/c4_chainlit/`:

- One file `app.py`, ~100 LOC. Decorators: `@cl.on_chat_start` builds the
  agent and stores it in `cl.user_session`; `@cl.on_message` runs the
  agent with `stream=True`, iterates `AgentResponseUpdate`s, intercepts
  `FunctionApprovalRequestContent`, renders `cl.AskActionMessage` with
  Approve / Deny actions, awaits the response, sends it back to the
  agent loop.
- No AG-UI, no React, no separate frontend.
- Run: `chainlit run app.py`. Walk through T1–T4 in the Chainlit UI.

**Spike succeeds if:** all four turns pass.
**Spike fails if:** anything multi-turn breaks. (Not predicted; baseline
expectation.)

## Output

Append a `## §5 Spike Results` section to
`docs/research-agent-stack-candidates.md` with:

- One subsection per spike.
- A pass/fail table per turn.
- A 2-sentence narrative on what surprised us, if anything.
- A final-finalist call: which candidate becomes the agent_app stack.

## Decision Rule

After all three spikes:

1. If **C4 passes** and any one of {C1, C2} also passes — pick **C4**
   anyway (lower scope, no AG-UI risk, no JS toolchain). The 3.8
   relaxation has been accepted; the only reason to pick C1/C2 over C4
   is multi-route shared session, which we already deemed nice-to-have.
2. If **C4 passes** and both C1 and C2 fail — pick **C4**.
3. If **C4 fails** — escalate. Either fix C4 (Chainlit issue is
   probably tractable) or fall back to **C5 (custom FastAPI + Next.js)**,
   which we did not spike but which by construction satisfies all
   must-haves.

The spikes' purpose is therefore **falsification of the docs-archaeology
verdict**, not horse-race comparison. C4 is the favorite; the spikes
guard against being wrong about C1/C2 in a way that should reverse the
favorite.

## Out of Scope

- UC1 brief streaming format, UC2 wizard ergonomics, UC3 inbox
  rendering, identity threading, MCP KB, audit middleware. All deferred
  to the post-spike PRD.
- Performance, cost, observability.
- Prettiness — buttons and text only.

## Rough Effort

- Shared scaffold: 1–2 h.
- Per spike: 0.5–1 day, dominated by setup (npm, Vite, CopilotKit
  runtime config). Each spike should run T1–T4 within minutes once
  built.
- Total: ~2–3 working days.
