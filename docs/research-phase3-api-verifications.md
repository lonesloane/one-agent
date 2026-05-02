# Phase 3 — API verifications for UC2 / UC3 PRD TBDs

> Status: research note, do not commit. Resolves five
> API-verifiable TBDs raised in `prd-uc2-delegate-creation.md`
> and `prd-uc3-approver-inbox.md`. Each section gives:
> question / answer / evidence / caveat.
>
> Repo state at time of writing:
> - `agent_framework` installed: **1.2.1**
>   (`.venv/lib/python3.12/site-packages/agent_framework-1.2.1.dist-info/`)
> - `chainlit` installed: **2.11.1**
>   (`.venv/lib/python3.12/site-packages/chainlit-2.11.1.dist-info/`)
> - Spike validated on this same install:
>   `spikes/c4_chainlit/app.py`, `spikes/_shared/agent.py`.

---

## TBD-A1 (UC2) — `Agent.create_session()` vs `AgentThread`

### Question
Is the per-conversation session API in the current `agent-framework`
Python release `Agent.create_session()` (used by `spikes/c4_chainlit/`)
or `AgentThread` (mentioned in `.claude/CLAUDE.md`)?

### Answer
**`Agent.create_session()` returning `AgentSession`** is canonical.
`AgentThread` and `agent.get_new_thread()` were **removed** in the
2026 Python migration. The CLAUDE.md mention of `AgentThread` is
stale and should be corrected.

### Evidence

Context7 — library `/websites/learn_microsoft_en-us_agent-framework`,
topic "Agent.create_session vs AgentThread Python AgentSession" —
returned the explicit migration note:

> **Migrate AgentThread to AgentSession**
> Source: `learn.microsoft.com/.../support/upgrade/python-2026-significant-changes`
> "The Python session and context-provider migration is complete.
> `AgentThread` and old context-provider types are removed. Use
> `agent.create_session()` instead of `agent.get_new_thread()` and
> `agent.get_session()` instead of
> `agent.get_new_thread(service_thread_id=...)`."

Installed-source cross-check:

- `.venv/lib/python3.12/site-packages/agent_framework/_agents.py:302`
  protocol declares
  `def create_session(self, *, session_id: str | None = None) -> AgentSession`.
- `.venv/.../agent_framework/_agents.py:407-428` — `BaseAgent.create_session`
  implementation returns `AgentSession(session_id=session_id)`.
- `.venv/.../agent_framework/_sessions.py:714` — `class AgentSession:` is
  the lightweight session dataclass. No `class AgentThread` exists in
  `_agents.py`, `_sessions.py`, or `__init__.py`.

Spike usage:

- `spikes/c4_chainlit/app.py:33` — `session = agent.create_session()`
- `spikes/c4_chainlit/app.py:102` — `agent.run(current_input, session=session, stream=True)`

### Caveat
`.claude/CLAUDE.md` (Agent Framework Policy section) currently lists
`AgentThread` as a canonical entry-point example — that line should
be replaced with `Agent.create_session() / AgentSession` to align
with the spike and the 1.2.1 release. Out of scope for this research
note (the user asked us not to edit). Flag for follow-up.

---

## TBD-A2 (UC2) — `cl.AskActionMessage` timeout default + recommendation

### Question
What is the default timeout for `cl.AskActionMessage`, and what value
should the UC2 HITL approval prompt set?

### Answer
**Default = 90 seconds** (`raise_on_timeout=False`, returns `None`).
**Recommended override = 300 seconds (5 min)** for the DAR-creation
approval prompt in UC2. The spike already uses `timeout=300`.

### Evidence

Context7 — library `/chainlit/docs`, topic "AskActionMessage timeout
default" — returned the API doc page:

> **AskActionMessage**
> Source: `github.com/chainlit/docs/blob/main/api-reference/ask/ask-for-action.mdx`
> "**timeout** (int, optional, default=90) — The time in seconds to
> wait for a user response before timing out.
> **raise_on_timeout** (bool, optional, default=false) — If true, a
> `TimeoutError` is raised when the timeout is reached. Otherwise,
> `None` is returned."

Installed-source cross-check:

- `.venv/.../chainlit/message.py:494-512` — `class AskActionMessage`,
  `__init__(..., timeout=90, raise_on_timeout=False)`.

Spike usage:

- `spikes/c4_chainlit/app.py:72-78` —
  `cl.AskActionMessage(content=..., actions=actions, timeout=300).send()`.

### Recommendation
Use **`timeout=300`** for the UC2 approval prompt. Rationale:
- The approver may switch tabs to read the DAR preview (delegate
  name, scope, dates). 90 s is too tight for review-then-decide.
- `raise_on_timeout=False` (default) is correct — on stale approval
  we want a polite "approval window expired, please re-issue" path,
  not a Python exception bubbling into the chat.
- 5 min is also the value the C4 spike empirically validated against
  the real Foundry roundtrip.

### Caveat
If the DAR preview ever grows to require an external policy lookup
(e.g., HR system out-of-office check), revisit. For the current UC2
scope (preview only), 300 s is comfortable.

---

## TBD-A3 (UC3) — `chat_profile` persistence across hard refresh

### Question
When a user picks a profile via `@cl.set_chat_profiles` and then hard-
refreshes the browser, is the selected profile retained, or do they
pick again?

### Answer
**The selected profile IS retained across hard refresh, because it
travels in the URL** (the Chainlit React app encodes the chosen
profile name as a query parameter and as socket.io auth payload, and
both survive a page reload of the same URL). It is NOT stored in a
cookie or in the server-side `cl.user_session` between sockets — so
loss of the URL (e.g., navigating to bare `/`) loses the profile and
prompts re-selection.

Context7 does not document the persistence behavior directly; the
answer is grounded in installed-source evidence (the wire shape of
`chatProfile`) and on the standard React-app behavior of preserving
URL on reload.

### Evidence

Installed-source — primary signals:

- `.venv/.../chainlit/server.py:805-814` — HTTP endpoint
  `/project/settings` accepts `chat_profile: Optional[str] = Query(...)`.
  This is the call the React app makes on every page load to bootstrap
  the UI; the profile is read from the URL.
- `.venv/.../chainlit/socket.py:185-187` — on socket connect, the
  client sends `auth.get("chatProfile", None)` and the server
  unquotes it to set `session.chat_profile`. The React app holds the
  profile in URL state and forwards it to the socket handshake, so a
  reload of the same URL re-establishes the same profile.
- `.venv/.../chainlit/socket.py:96-97` — for thread-resume metadata
  paths the profile is also rehydrated from `metadata.get("chat_profile")`.
- `.venv/.../chainlit/user_session.py:31` —
  `user_session["chat_profile"] = context.session.chat_profile`. This
  populates `cl.user_session.get("chat_profile")` per socket; on
  refresh a new socket is opened and the user_session is re-populated
  from the URL-supplied profile.

Context7 confirms the **read API** is stable on 2.11.1:

> **Define Chat Profiles** (Source: `github.com/chainlit/docs/blob/main/api-reference/chat-profiles.mdx`)
> ```python
> @cl.on_chat_start
> async def on_chat_start():
>     chat_profile = cl.user_session.get("chat_profile")
> ```

### Caveat & repro pattern
The behavior is **URL-driven**, not cookie/localStorage-driven.
Implications for UC3 wiring:
- Bookmarking `…/?chatProfile=Approver` deep-links straight into the
  approver page — useful for the approver inbox.
- A user who clears the URL (e.g., types the bare host) will see the
  profile picker again. UC3 should document this as expected — it
  is *not* a session bug.
- A switch from Approver to Editor tab while a HITL prompt is
  pending is **destructive**: the URL change rebuilds the socket and
  fires `@cl.on_chat_start` again, dropping pending `AskActionMessage`
  state. UC3 should call this out as "do not switch profiles
  mid-approval".

Minimal repro to validate before UC3 sign-off (run after profile-
aware spike exists):

```python
# spikes/c4_chainlit/profile_repro.py
import chainlit as cl

@cl.set_chat_profiles
async def profiles(_user=None):
    return [
        cl.ChatProfile(name="Approver",
                       markdown_description="Approver page"),
        cl.ChatProfile(name="Editor",
                       markdown_description="Editor page"),
    ]

@cl.on_chat_start
async def start():
    p = cl.user_session.get("chat_profile")
    await cl.Message(content=f"profile = {p}").send()
```

Steps: pick "Approver" → see "profile = Approver" → hard-refresh
(Ctrl+Shift+R) → expect "profile = Approver" again, no picker. Then
navigate to bare `/` → expect picker.

---

## TBD-A4 (UC3) — Chainlit version pin alignment

### Question
Does the Chainlit version pinned in `pyproject.toml` match the validated
`chat_profiles` API surface (`set_chat_profiles` decorator;
`ChatProfile(name, markdown_description, icon)`)?

### Answer
**The API surface is stable on the installed version (2.11.1) — but
the pin is loose** (`chainlit>=2.0`, in the `[project.optional-
dependencies].spikes` extra). Recommend tightening to
`chainlit>=2.11,<3` for the `agent_app` dep group when Phase 3
production code lands.

### Evidence

`pyproject.toml:30` —
```
spikes = [
    "agent-framework-ag-ui>=1.0.0b260428",
    "chainlit>=2.0",
    ...
]
```

Context7 — library `/chainlit/docs`, topic "set_chat_profiles
ChatProfile" — returned the live API page (sourced from
`chainlit/docs` repo, current `main` branch):

> **@cl.set_chat_profiles** — Decorator to define the list of chat
> profiles available in the application.
>
> **Response: `List[ChatProfile]`** — A list of ChatProfile objects
> containing `name`, `markdown_description`, `icon`, and optional
> `config_overrides`.

Installed-source cross-check (2.11.1):

- `.venv/.../chainlit/types.py:312-322` — `@dataclass class ChatProfile`
  with `name: str`, `markdown_description: str`,
  `icon: Optional[str] = None`, plus newer optional fields
  (`display_name`, `default`, `starters`, `config_overrides`). All
  fields used in UC3 (`name`, `markdown_description`, `icon`) match.
- `.venv/.../chainlit/callbacks.py:226-250` — `set_chat_profiles`
  decorator with two valid signatures (`User` or `User + language`),
  matching the Context7 doc.

### Caveat — the pin is too loose
- `chainlit>=2.0` will resolve to whatever is current at install time.
  Chainlit 3.x is not out yet but a major-version bump could break
  the `ChatProfile` dataclass shape or the `cl.user_session` key.
- **Recommendation**: when Phase 3 graduates from spike to production
  in `agent_app/`, move Chainlit out of the `spikes` extra and into
  the main `dependencies` block with `chainlit>=2.11,<3`. Same logic
  for `agent-framework`: pin `>=1.2,<2` to lock the AgentSession API.

---

## TBD-A5 (UC3) — `agent-framework` introspection for `approval_mode`

### Question
What's the right way to mechanically assert (in a unit test) that a
given tool is NOT approval-gated, satisfying UC3 acceptance criterion
AC-8?

### Answer
**Use the `approval_mode` attribute of the `FunctionTool` instance**.
The `@agent_framework.tool` decorator (with or without arguments)
returns a `FunctionTool` — not the raw function. The instance carries
`tool.approval_mode in {"never_require", "always_require"}` as a
plain string attribute. No unwrapping or `_tool_meta` dance is needed.

### Evidence

Installed-source — primary (Context7 was not consulted because the
task explicitly allows installed-source fallback for A5):

- `.venv/.../agent_framework/_tools.py:93` —
  `ApprovalMode: TypeAlias = Literal["always_require", "never_require"]`.
- `.venv/.../agent_framework/_tools.py:240` — `class FunctionTool(SerializationMixin)`.
- `.venv/.../agent_framework/_tools.py:297-393` — `__init__` accepts
  `approval_mode: ApprovalMode | None = None` and at line 393 sets
  `self.approval_mode = approval_mode or "never_require"`.
- `.venv/.../agent_framework/_tools.py:1166-1325` — the `tool`
  decorator's `decorator()` inner function returns
  `FunctionTool(name=..., approval_mode=approval_mode, func=f, ...)`.
  No proxy / wrapper layer. `@tool` (bare) and `@tool(...)` both
  yield a `FunctionTool` with `.approval_mode` set.
- `.venv/.../agent_framework/_tools.py:1630` — internal usage
  `[t.approval_mode == "always_require" for t in tool_map.items()]`
  confirms `.approval_mode` is the public attribute the framework
  itself reads.

Spike confirms the shape end-to-end:
- `spikes/_shared/agent.py:31-34` — `@tool` (no parens) on `list_records`
  → `FunctionTool` with `.approval_mode == "never_require"` (default).
- `spikes/_shared/agent.py:37-46` — `@tool(approval_mode="always_require")`
  on `create_record` → `FunctionTool` with `.approval_mode == "always_require"`.

### Test snippet for AC-8

```python
# tests/agent_app/test_tools_approval_mode.py
from agent_app.tools import (
    list_dars,            # read tool — must NOT be approval-gated
    create_dar,           # write tool — MUST be approval-gated
)


def test_list_dars_is_not_approval_gated() -> None:
    """AC-8: read tools execute auto-invoke, no approval prompt."""
    assert list_dars.approval_mode == "never_require"


def test_create_dar_is_approval_gated() -> None:
    """Mirror assertion: write tool MUST be HITL-gated."""
    assert create_dar.approval_mode == "always_require"
```

For a more defensive variant that also checks the wrapping shape:

```python
from agent_framework import FunctionTool

def test_list_dars_shape() -> None:
    assert isinstance(list_dars, FunctionTool)
    assert list_dars.approval_mode != "always_require"
```

### Caveat
- `approval_mode` is a string, not an enum, so use string equality
  (`== "never_require"`) or the negative form (`!= "always_require"`).
  Don't import `ApprovalMode` — it's a `Literal` alias, not a class
  with members.
- If Phase 3 ever uses raw `FunctionTool(...)` instantiation (instead
  of the `@tool` decorator) and forgets to pass `approval_mode`, the
  default at `_tools.py:393` is `"never_require"` — meaning a missing
  flag is silently a non-gated tool. The unit test above protects
  against that drift on read tools, but for write tools you should
  *also* assert `== "always_require"` (positive assertion), not just
  trust the default.
