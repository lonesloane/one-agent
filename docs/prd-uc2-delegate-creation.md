# PRD — UC2: Delegate Creation with Document Access Rights (HITL Write Flow)

> Phase 3 use case 2 of the ONE-MP Agent PoC. Compresses the classical
> 8-screen Add-Delegate wizard into a ~3-turn conversational flow with
> a single human-in-the-loop approval gate. Stack: **Chainlit +
> `agent-framework` Python (C4)**, validated by `spikes/c4_chainlit/`
> and locked-in by the 2026-05-01 reversal entry in
> `docs/DECISIONS.md`.

---

## 1. Executive Summary

### Problem Statement

The classical `classical_app/` wizard requires a Delegation Editor to
click through 8 screens (delegation picker → detail → 4 wizard steps →
review → confirmation) to onboard a single delegate. Most of those
screens exist to lay out *business rules* the editor would otherwise
have to memorise — default access levels per membership type, which
classification levels are selectable per committee, which routing
outcome each combination triggers. The wizard works but it is slow,
non-collaborative, and gives a poor first impression of the system to
newly-onboarded editors.

### Proposed Solution

A single-purpose conversational write flow inside `agent_app/` (the
Chainlit + Microsoft Agent Framework Python agent) that:

1. Collects personal info + committee selection in one turn.
2. Computes and previews the rule-derived defaults (access level per
   committee, projected approval routes) in plain language.
3. Fires a **single approval-gated combined write tool** — gated by
   `@tool(approval_mode="always_require")` and rendered as a Chainlit
   `cl.AskActionMessage` action prompt — that creates both the
   `Delegate` row and all `DocumentAccessRight` rows in **one
   transaction**.

The agent calls `shared/business_rules.py` directly. No port, no
duplication.

### Success Criteria

| KPI | Target |
|---|---|
| Conversational turns to create one delegate (happy path) | ≤ 3 turns (collect → preview/approve → result) |
| All three approval routes (`AUTO_APPROVED`, `PENDING_DELEGATION_HEAD`, `PENDING_SECRETARIAT`) reachable end-to-end | 100% (covered by integration scenarios D1–D5) |
| Parity with classical wizard outcome — same delegate row + same DAR rows for the same input | 100% — diff-asserted in integration tests |
| Identity leak rate — agent never sees `delegate_id` of acting editor in a tool argument or system prompt | 0 occurrences (audit-middleware regression test) |
| Atomicity on partial failure — orphan `Delegate` rows after a DAR write error | 0 (transactional rollback enforced) |

---

## 2. User Experience & Functionality

### 2.1 User Personas

- **Delegation Editor** (acting user). Authenticated `Delegate` row
  with `role == DelegateRole.DELEGATION_EDITOR`. Operates only within
  their own `delegation_id`. Wants to onboard a new delegate quickly
  without re-reading the OECD access-rules cheat-sheet every time.
- **Newly-created delegate** (target). Not present at the keyboard
  during UC2 — receives the resulting `Delegate` row + DARs as a
  consequence.

### 2.2 User Stories

**US-1 — Editor onboards a delegate from their own delegation in plain language.**
> As a delegation editor, I want to type "create delegate Marie Dubois,
> marie.dubois@example.fr, Policy Advisor, on EDU and TRADE committees"
> and have the agent prepare the full record, so I don't have to walk
> through 8 form screens.

**US-2 — Editor sees the routing consequence before approving.**
> As a delegation editor, before I approve the write, I want the agent
> to tell me what the access level for each committee will be and which
> approval queue each DAR will land in, so I can correct course before a
> bad request goes to the secretariat.

**US-3 — Editor confirms intent through a native, unambiguous UI affordance.**
> As a delegation editor, I want a single, native chat-side
> Approve / Deny prompt before any DB write, so I never wonder whether
> a tool fired or not.

**US-4 — Editor can deny the write and refine the request.**
> As a delegation editor, when I deny the proposed write I want the
> conversation to continue so I can change a committee or fix a typo
> without restarting the chat.

**US-5 — Editor is blocked from writing on a delegation they don't manage.**
> As an editor of FRA, when I try to create a delegate on BRA, I want
> the agent to refuse cleanly and not silently create the row, so cross-
> delegation tampering is impossible.

### 2.3 Acceptance Criteria

#### US-1 (happy path, member delegation, all-General DARs → AUTO_APPROVED)

- [ ] Agent collects `full_name`, `email`, `function`, optional
      `title`, `delegation_id`, and `committee_ids` in T1. If any
      required field is missing, agent asks before calling any write
      tool (write-guard rule, see §3).
- [ ] Agent calls `lookup_delegate_by_email` to verify no existing
      delegate in the target delegation has the same email
      (case-insensitive) — mirrors classical
      `_email_exists_in_delegation`.
- [ ] Agent calls `get_delegation_info(delegation_id)` and
      `compute_default_dar_preview(delegation_id, committee_ids,
      retroactive=False)` (read-only) and surfaces the proposed
      classification level and projected approval route per committee.
- [ ] Agent calls `create_delegate_with_access_rights(...)` —
      Chainlit renders `cl.AskActionMessage` with Approve / Deny.
- [ ] On Approve: `Delegate` row + N `DocumentAccessRight` rows
      committed in one transaction; agent reports the new
      `delegate_id` (e.g. `DEL-2026-0042`) and the per-committee
      routing label.
- [ ] All inserted DARs have `approval_status == AUTO_APPROVED`
      (when classification is GENERAL and `retroactive=False`).
- [ ] DAR `created_by` field is set to the acting editor's
      `delegate_id` for the audit trail.

#### US-2 / partner delegation with active FA → mixed routing

- [ ] For a `PARTNER` delegation with an active
      `FrameworkAgreement` on EDU but not on TRADE, the preview
      shows: EDU → RESTRICTED → `PENDING_DELEGATION_HEAD`; TRADE →
      GENERAL → `AUTO_APPROVED`.
- [ ] These exact routing outcomes are produced by
      `determine_approval_route` after the write commits — agent
      never derives them from the system prompt.

#### US-2b / retroactive request → PENDING_SECRETARIAT

- [ ] If the editor sets `retroactive=True` on any DAR row, the
      preview shows `PENDING_SECRETARIAT` for that row regardless of
      classification.
- [ ] CONFIDENTIAL classification routes to `PENDING_SECRETARIAT`
      (covers the `D4` eval scenario).

#### US-3 (HITL approval rendering)

- [ ] When `create_delegate_with_access_rights` is called, the
      Chainlit chat renders an `cl.AskActionMessage` with two
      actions (Approve / Deny) and a body that names the tool and
      lists the structured arguments. (See spike reference at
      `spikes/c4_chainlit/app.py` lines 48–79.)
- [ ] Approval timeout: UC2 sets `timeout=300` (5 min) on
      `cl.AskActionMessage` (Chainlit default is 90s; override
      balances DAR-preview review time against staleness).
      `raise_on_timeout=False` (default) gives a graceful expired
      path. Source: `chainlit/message.py:505`; spike at
      `spikes/c4_chainlit/app.py`.
- [ ] On Deny: no DB write occurs; the agent acknowledges the
      denial, **does not retry**, and resumes conversation.

#### US-4 (deny → refine)

- [ ] After a denial, the next user message can adjust any captured
      field (committee list, email, etc.). The agent must not commit
      the previously-collected state — collected fields are
      conversational state, not session-persistent state.

#### US-5 (cross-delegation refusal)

- [ ] Before any write tool fires, the agent's permission helper
      asserts both:
      `editor.role == DelegateRole.DELEGATION_EDITOR` **and**
      `editor.delegation_id == target_delegation_id`. If either
      fails, the tool raises `PermissionError("Only delegation
      editors of <delegation_id> can create delegates on it")`.
- [ ] The Chainlit UI surfaces this as a chat error message; no
      partial DB state.

### 2.4 Non-Goals

- **Editing or deleting** existing delegates / DARs — UC2 is
  create-only.
- **Approver workflow** — pending DARs are written with the right
  `approval_status` for UC3 to consume; UC2 does not wait for
  delegation-head or secretariat to approve. (Documented in
  `docs/DECISIONS.md` 2026-04-19, OQ-9 resolution: status flag only
  for Phase 2; full approver UX is UC3 / Phase 4.)
- **Bulk delegate import.**
- **Real-world authentication** — `delegate_id` is read from
  `cl.user_session`, set at chat-start; production identity wiring is
  Phase 4+. Inherited from `plan/phase3-agent-app-scaffold-1.md`
  RISK-003.
- **Live approval-route streaming via UC3 inbox** — UC2 finishes when
  the DARs are persisted; UC3 picks them up.
- **MCP KB integration** — business rules live in
  `shared/business_rules.py` as Python; MCP exposure is Phase 5.

---

## 3. AI System Requirements

### 3.1 Tool Surface

The full tool list registered with the UC2 agent. Every tool is built
by a **factory function closing over `delegate_id`** (the acting
editor) — see `plan/phase3-agent-app-scaffold-1.md` PAT-001. The model
never sees `delegate_id`.

#### Read-only tools (unwrapped — no approval gate)

| Tool | Signature (LLM-visible args) | Purpose |
|---|---|---|
| `lookup_delegate` | `delegate_id: str` | Look up *another* delegate by ID. |
| `lookup_delegate_by_email` | `delegation_id: str, email: str` | Returns existing delegate or `None`. Used to enforce uniqueness pre-write. |
| `whoami` | `()` | Returns the acting editor's profile (full_name, role, delegation_id). Resolves the identity-leak bug from `_archived/bug-delegate-identity-leak-1.md`. |
| `get_delegation_info` | `delegation_id: str` | Returns delegation name, membership_type, list of active framework agreements (committee_id + active flag). |
| `list_committees` | `()` | Returns all committees with `(id, name)`. Lets the model resolve human names ("Education Policy Committee") to internal codes ("EDU"). |
| `compute_default_dar_preview` | `delegation_id: str, committee_ids: list[str], retroactive: bool = False` | **Read-only computation tool.** Calls `compute_default_access_level` + `determine_approval_route` per committee and returns a list of `{committee_id, classification_level, projected_approval_status}`. Lets the model show the user what the write would produce before firing it. |

#### Write tool (approval-gated)

| Tool | Signature (LLM-visible args) | Decorator |
|---|---|---|
| `create_delegate_with_access_rights` | `full_name: str, email: str, function: str, title: str \| None, delegation_id: str, committee_ids: list[str], retroactive_per_committee: dict[str, bool] \| None = None` | `@tool(approval_mode="always_require")` |

**Why a single combined tool instead of `create_delegate` +
`create_document_access_rights`:**

The 2026-04-25 archived smoke (`_archived/feature-phase4b-create-server-prompt-1.md`,
TASK-007/008) showed the model populating
`create_document_access_rights(delegate_id="DEL-2026-0001")` — the
editor's *own* ID — before the create_delegate result returned. Two
separate approval-gated tools cannot satisfy atomicity: the user could
approve the delegate write and deny the DAR write, leaving an orphan
delegate. Combining the two into one tool, fired under one approval
prompt, gives:

1. **Atomicity** — both inserts happen inside one
   `db_session.commit()`; on `SQLAlchemyError` we rollback both.
2. **One approval, not two** — matches the user's mental model
   ("create this delegate with these access rights") and mirrors the
   classical wizard's single transactional commit at
   `wizard_helpers._handle_step4_post`.
3. **No model-sequencing bug** — the model cannot accidentally
   reference a not-yet-created `delegate_id` because it is generated
   inside the tool body via `_generate_delegate_id` (mirroring the
   classical helper).

**Tool body (high-level):**

```python
@tool(approval_mode="always_require")
def create_delegate_with_access_rights(
    full_name: str,
    email: str,
    function: str,
    title: str | None,
    delegation_id: str,
    committee_ids: list[str],
    retroactive_per_committee: dict[str, bool] | None = None,
) -> dict:
    # Identity + permission check (closure-bound editor_id)
    # Load Delegation + framework_agreements
    # For each committee_id:
    #     level = compute_default_access_level(...)
    #     status = determine_approval_route(level, retroactive)
    # Atomic transaction:
    #     insert Delegate (role=DelegateRole.DELEGATE,
    #                      created_by=editor_id)
    #     attach committees via delegate.committees = [...]
    #     insert N DocumentAccessRight rows (created_by=editor_id)
    #     commit; on SQLAlchemyError: rollback + reraise
    # Return:
    #     {delegate_id, committees: [
    #         {committee_id, classification_level, approval_status,
    #          retroactive}, ...]}
```

> **Default role:** the *created* delegate's
> `role = DelegateRole.DELEGATE` (mirrors classical
> `wizard_helpers._build_delegate` line 348). The acting user is an
> editor; the new delegate is an ordinary delegate. The archived 4A
> REQ-001 defaulted to `DELEGATION_EDITOR` — that was a defect in the
> archived plan and is not propagated here.

> **DAR id:** `DocumentAccessRight.id` is autoincrement int
> (`shared/database.py` line 354) — SQLAlchemy assigns it. No
> `_next_dar_id` generator.

### 3.2 System Prompt Requirements

The UC2 agent's system prompt must include:

1. **Persona statement.** "You assist a delegation editor onboarding
   a new delegate." Identity facts about the editor are obtained
   via `whoami()`, never assumed.
2. **Elicitation order.**
   `full_name → email → function → (title optional) → delegation_id
   → committee_ids → retroactive_per_committee (default all False)`.
3. **Write-guard (permissive).** Validated wording from Phase 0e
   (`docs/DECISIONS.md` 2026-04-09): *"When all required
   information is available, call the appropriate creation or
   modification tool directly. If any required field is missing, ask
   the user for it before making the tool call."* This wording must
   be reused verbatim — Phase 0f confirmed it.
4. **Preview-before-write rule.** *"Before calling
   `create_delegate_with_access_rights`, call
   `compute_default_dar_preview` and show the user the projected
   classification level and approval route for each committee, in
   plain language."*
5. **Access-classification rule (briefing only — authoritative
   computation lives in `shared/business_rules.py`).** Phrasing as
   in Phase 0f (`DECISIONS.md` 2026-04-10):
   - Member delegation → RESTRICTED on every committee.
   - Partner delegation with active framework agreement on the
     committee → RESTRICTED.
   - Partner delegation without active framework agreement on the
     committee → GENERAL.
6. **Approval-routing rule (briefing only).**
   - GENERAL + non-retroactive → AUTO_APPROVED.
   - RESTRICTED + non-retroactive → PENDING_DELEGATION_HEAD.
   - CONFIDENTIAL or any retroactive → PENDING_SECRETARIAT.
7. **HITL acknowledgement.** *"You do not handle approval in chat.
   When a write tool requires approval, the system renders a
   separate prompt; wait for its result. Do not claim a write
   happened until the tool returns."* (Reuse from
   `_archived/feature-phase4b-create-server-prompt-1.md` REQ-001 last
   bullet.)
8. **Failure-reporting rule.** *"If a write tool returns an error,
   surface its message and do not retry."*
9. **Identity rule.** *"Never ask the user for their own
   `delegate_id`. Use `whoami()` to discover the acting editor."*
   This is the resolution of the 2026-04-25 identity leak
   (`_archived/bug-delegate-identity-leak-1.md`).

The prompt should remain ≤ 300 lines; tool docstrings (Google style)
carry the per-tool detail rather than the prompt.

### 3.3 Evaluation Strategy

#### Integration scenarios

UC2 reuses the eval-suite's D-series scenario shape (see
`docs/DECISIONS.md` Phase 0a–0f). All five scenarios must pass on
`gpt-4.1-mini` (selected model — `DECISIONS.md` 2026-04-10):

| ID | Membership | Committee FA? | Retroactive? | Expected level | Expected route |
|---|---|---|---|---|---|
| D1 | MEMBER | n/a | False | RESTRICTED | PENDING_DELEGATION_HEAD |
| D2 | MEMBER | n/a | False | RESTRICTED | PENDING_DELEGATION_HEAD |
| D3 | PARTNER | No | False | GENERAL | AUTO_APPROVED |
| D4 | any | any | True | n/a (retroactive) | PENDING_SECRETARIAT |
| D5 | PARTNER | Yes (active FA) | False | RESTRICTED | PENDING_DELEGATION_HEAD |

Plus a new scenario covering `CONFIDENTIAL` non-retroactive →
`PENDING_SECRETARIAT` once a write path can name a CONFIDENTIAL level
explicitly (the default-level path never returns CONFIDENTIAL — see
`reference_schema_pitfalls`).

#### Test types

- **Unit** (`tests/agent_app/test_uc2_tools.py`): tool functions
  called directly against a seeded engine. Asserts (per scenario):
  exact `classification_level` + `approval_status` on returned dict
  *and* on persisted rows; rollback on commit failure (monkeypatch
  `session.commit` to raise); editor permission gate (non-editor
  raises `PermissionError`; editor-of-other-delegation raises).
- **HITL decorator regression**
  (`tests/agent_app/test_uc2_hitl.py`): introspects the tool's
  `approval_mode` attribute; asserts equality with
  `"always_require"`. Mirrors archived 4A TASK-011.
- **Integration** (`tests/agent_app/test_uc2_integration.py`): drives
  the agent with a `FakeChatClient` emitting a canned tool-call
  sequence; auto-approves the HITL prompt; asserts approval-request
  event observed before the write; asserts final DB state matches
  scenario expectations. Five scenario cases above. Mirrors archived
  4D plan, but with **AG-UI-specific assertions removed** — Chainlit
  events replace AG-UI SSE inspection.
- **Audit middleware regression**
  (`tests/agent_app/test_uc2_audit.py`): runs one create scenario;
  asserts loguru sink captured `tool=create_delegate_with_access_rights`,
  serialized args, and result.
- **Parity test** (`tests/agent_app/test_uc2_wizard_parity.py`):
  drive both the classical wizard and the agent flow with the same
  input; assert the resulting `Delegate` and `DocumentAccessRight`
  rows are equivalent (ignoring auto-generated IDs and timestamps).

#### Visual verification

After PR merge, run the `visual-verify-onemp` skill against UC2
(login as a `DELEGATION_EDITOR`, drive the conversation, check
Approve / Deny flow renders in Chainlit). See
`reference_visual_verify_skill`.

---

## 4. Technical Specifications

### 4.1 Architecture Overview

```
┌──────────────────────── Chainlit (browser) ────────────────────────┐
│  on_chat_start          on_message               cl.AskActionMessage│
│        │                    │                          ▲           │
│        ▼                    ▼                          │           │
│  cl.user_session    agent.run(stream=True) ──► user_input_requests │
│  delegate_id          │                                │           │
└───────┬───────────────┼────────────────────────────────┘           │
        │               ▼                                            │
        │   ┌───────────────────────────────┐                        │
        │   │  agent_framework.Agent         │                        │
        │   │  • FoundryChatClient           │                        │
        │   │  • AzureCliCredential          │                        │
        │   │  • tools=[lookup_delegate,…    │                        │
        │   │           create_delegate_with…│ (approval_mode)        │
        │   │  • middleware: AuditMiddleware │                        │
        │   └────────────┬───────────────────┘                        │
        │                ▼                                             │
        │   ┌───────────────────────────────┐                          │
        ▼   │ shared/business_rules.py       │                          │
   closure │   compute_default_access_level  │                          │
   binds   │   determine_approval_route       │                          │
delegate_id│ shared/database.py (ORM)         │                          │
        ───┴──► one_agent.db (SQLite, shared with classical_app)         │
```

**Loop pattern (mirrors `spikes/c4_chainlit/app.py:82–132` verbatim):**

1. `@cl.on_chat_start`: set `delegate_id` in `cl.user_session`,
   build agent via `build_agent(credential, delegate_id)`, create
   `session = agent.create_session()`, store both.
2. `@cl.on_message`: stream `agent.run(input, session=session,
   stream=True)`. While `chunk.user_input_requests` is non-empty,
   render `cl.AskActionMessage` per request, build approval response
   via `req.to_function_approval_response(approved=…)`, feed back as
   next `current_input = Message("user", approval_responses)`. Exit
   loop when `user_input_requests` is empty.

> **API surface:** `Agent.create_session()` returning `AgentSession` /
> `agent.run(session=…, stream=True)` is the canonical shape on
> `agent-framework` 1.0 (2026-04-29). `AgentThread` was removed in
> the 2026 Python migration of `agent-framework`. Source:
> `agent_framework/_agents.py:302,407`; spike at
> `spikes/c4_chainlit/app.py:33`.

### 4.2 Identity Threading (closure-based DI)

`plan/phase3-agent-app-scaffold-1.md` PAT-001 / REQ-002 mandate the
**closure** pattern. Every UC2 tool is built by a factory:

```python
def make_create_delegate_with_access_rights(editor_id: str):

    @tool(approval_mode="always_require")
    def create_delegate_with_access_rights(
        full_name: str,
        email: str,
        function: str,
        title: str | None,
        delegation_id: str,
        committee_ids: list[str],
        retroactive_per_committee: dict[str, bool] | None = None,
    ) -> dict:
        with session_scope() as db:
            _assert_editor_of(db, editor_id, delegation_id)
            ...

    return create_delegate_with_access_rights
```

`build_agent(credential, delegate_id)` calls every factory and
collects the resulting `@tool`-decorated callables into the agent's
tool list. The model-visible function signature **never includes
`editor_id`**.

> **Why closure, not `FunctionInvocationContext.kwargs`:** the
> archived attempt used `ctx.kwargs["delegate_id"]`. The scaffold plan
> deliberately switches to closure-bound DI (PAT-001) — simpler,
> spike-validated, no dependency on context-injection middleware.
> Mining note: do not import `FunctionInvocationContext` from
> archived 4A.

### 4.3 Permission Check (`_assert_editor_of`)

Mirrors `classical_app`'s `@editor_of_delegation_required` decorator
behavior:

```python
def _assert_editor_of(db, editor_id: str, delegation_id: str) -> None:
    editor = db.get(Delegate, editor_id)
    if editor is None or not editor.is_active:
        raise PermissionError("Editor not found or inactive")
    if editor.role != DelegateRole.DELEGATION_EDITOR:
        raise PermissionError(
            "Only delegation editors can create delegates"
        )
    if editor.delegation_id != delegation_id:
        raise PermissionError(
            f"Editor of {editor.delegation_id} cannot create "
            f"delegates on {delegation_id}"
        )
```

This is invoked **inside** the write tool body — before any insert.

### 4.4 Atomic Transaction (mirror classical wizard)

Mirrors `classical_app.routes.wizard_helpers._handle_step4_post`
(lines 386–464):

```python
try:
    new_id = _generate_delegate_id(db)              # DEL-YYYY-NNNN
    delegate = _build_delegate(...)
    delegate.committees = list(committees_loaded)
    dars = _build_dars(new_id, ..., created_by=editor_id)
    db.add(delegate)
    for dar in dars:
        db.add(dar)
    db.commit()
except SQLAlchemyError as exc:
    db.rollback()
    logger.error("UC2 commit failed: {}", exc)
    raise
```

`_generate_delegate_id` is moved to `shared/identifiers.py` as
`generate_delegate_id(delegation_code: str) -> str` (resolved
2026-05-02 — used by both `agent_app/` and `classical_app/`, so it
belongs in the shared layer). This is a v1.0 prerequisite for UC2
and is in-scope for the UC2 implementation plan: small refactor of
`classical_app/routes/wizard_helpers.py:297` to delegate to the
shared helper.

### 4.5 Audit Middleware

`agent_app/middleware/audit.py` (built in scaffold or UC1; reused
unchanged here). Function-invocation middleware emits one structured
loguru record per tool call:

```
{ts, editor_id (closure-resolved), tool, args (json), result_summary,
 duration_ms, error?}
```

UC2-specific assertion: the record for
`create_delegate_with_access_rights` must include
`approval_mode="always_require"` and `approval_outcome` ∈
{`approved`, `denied`, `timeout`}. The middleware reads the approval
outcome from the framework's invocation result.

### 4.6 Integration Points

- **Database:** SQLite (`one_agent.db`), shared with `classical_app`.
  Same SQLAlchemy session pattern — `agent_app/session.py`
  context-manager (scaffold FILE-004).
- **Foundry:** `FOUNDRY_PROJECT_ENDPOINT` + `FOUNDRY_MODEL=gpt-4.1-mini`
  via `.env` (see `reference_foundry_model_config`).
- **Identity:** `cl.user_session["delegate_id"]` set at
  `on_chat_start`. Real auth wiring is out of scope (Phase 4+).
- **No AG-UI, no CopilotKit, no .NET.** The whole AG-UI / CopilotKit
  layer is replaced by Chainlit — see `docs/DECISIONS.md` 2026-05-01.

### 4.7 Security & Privacy

- **No secrets in code.** `AzureCliCredential` (no API keys) — see
  scaffold SEC-001.
- **Identity invisible to model.** Closure-bound; no exposure via
  tool schema, tool docstring, or system prompt.
- **Permission check before insert.** Both role and
  delegation-scope. (See US-5 acceptance criteria.)
- **Email uniqueness within delegation** enforced via
  `lookup_delegate_by_email` pre-write — mirrors classical
  `_email_exists_in_delegation`.
- **Audit log immutable** within the loguru sink — write-only.

---

## 5. Risks & Roadmap

### 5.1 Phased Rollout

- **MVP (this PRD)** — combined create tool, 5 scenarios green,
  parity with classical wizard, manual visual-verify on
  `gpt-4.1-mini`. Hand-written code budget ≤ 350 LOC across
  `agent_app/tools/uc2.py` + system-prompt extension + tests stub.
- **v1.1** — extract write-tool helpers to a small
  `agent_app/tools/write_helpers.py` once UC3's approve / deny tools
  share the same audit + permission pattern. Add
  `override_levels` arg to expose CONFIDENTIAL classification (the
  default-level path never returns CONFIDENTIAL — see
  `reference_schema_pitfalls`); deferred from v1.0 (see §5.3).
- **v2.0** — push the access-classification rule into the MCP KB
  (Phase 5). Remove rule-briefing bullets from system prompt; agent
  queries KB at runtime instead.

### 5.2 Technical Risks

- **R1 — Model bypasses preview-before-write rule.** Mitigation: the
  framework's approval gate fires regardless of prompt compliance;
  worst case is a redundant approval prompt. Verified by
  `TestHITLEnforcement` regression.
- **R2 — Combined tool argument shape too large for the model to fill
  reliably.** `committee_ids` + `retroactive_per_committee` is a
  composite. Mitigation: rich `Field(description=…)` annotations;
  evaluate against D-series scenarios. If the model struggles, fall
  back to a two-stage flow with a dedicated "draft" preview tool —
  but the *write* must remain a single transactional call.
  *Implementation-time validation step:* run the D-series scenarios
  against `gpt-4.1-mini` during the UC2 implementation plan and
  confirm the combined-tool argument shape is filled reliably; this
  cannot be resolved from docs and does not block PRD sign-off.
- **R3 — Model hallucinates `committee_id` codes.** Phase 0c gap:
  models used "Trade Committee" instead of "TRADE". Mitigation:
  agent calls `list_committees()` before any write; system prompt
  also names the rule explicitly.
- **R4 — `cl.AskActionMessage` timeout too short / too long.**
  UC2 sets `timeout=300` (Chainlit default 90s); revisit on
  visual-verify feedback. Settled in §2.3.
- **R5 — Identity leak regression.** A dev wires `delegate_id` into
  a tool argument. Mitigation: regression test asserts no UC2 tool
  has `delegate_id` / `editor_id` in its schema.
- **R6 — Cross-app DB drift.** `agent_app` and `classical_app` both
  generate `DEL-YYYY-NNNN` IDs. Mitigation: parity test; use the
  same generator.
- **R7 — `agent-framework` Python preview drift.** Same risk as the
  scaffold plan RISK-002. Mitigation: smoke before code commits;
  pin if drift.
- **R8 — Atomicity breaks under concurrent writes.** SQLite has
  serialised writes; out-of-process editors are unlikely in a PoC
  but acceptance covers the single-tool case only.

### 5.3 Open Questions Tracked

- **Resolved — `cl.AskActionMessage` timeout policy.** Default is
  `90s`; UC2 overrides to `timeout=300` (5 min) to balance
  DAR-preview review time against staleness. `raise_on_timeout=False`
  (default) gives a graceful expired path. Source:
  `chainlit/message.py:505`; spike at `spikes/c4_chainlit/app.py`.
  Resolved 2026-05-02 by user.
- **Resolved — `Agent.create_session()` vs `AgentThread`.**
  `Agent.create_session()` returning `AgentSession` is canonical;
  `AgentThread` was removed in the 2026 Python migration of
  `agent-framework`. Source: `agent_framework/_agents.py:302,407`;
  spike at `spikes/c4_chainlit/app.py:33`. Resolved 2026-05-02 by
  user.
- **Resolved — `_generate_delegate_id` location.** Move to
  `shared/identifiers.py` with
  `generate_delegate_id(delegation_code: str) -> str`; used by both
  `agent_app/` and `classical_app/`. In-scope for the UC2
  implementation plan as a v1.0 prerequisite (small refactor of
  `classical_app/routes/wizard_helpers.py`). Resolved 2026-05-02 by
  user.
- **Resolved by deferral — CONFIDENTIAL classification override
  path.** `compute_default_access_level` never returns CONFIDENTIAL
  by design; an `override_levels` arg is a separate feature. Out of
  scope for v1.0; deferred to v1.1 (see §5.1). Resolved 2026-05-02
  by user.
- **Resolved by deferral — Combined-tool argument-shape empirical
  run on `gpt-4.1-mini`.** Cannot be resolved from docs; converted
  to an implementation-time validation step inside R2 (see §5.2).
  Does not block PRD sign-off. Resolved 2026-05-02 by user.
- **TBD — Whether UC2 should refuse to operate when the editor's
  session has not been freshly authenticated.** PoC-grade auth is
  out of scope; flag only.

---

## 6. Related Specifications / Further Reading

### Active references (live and load-bearing)

- `docs/DESIGN.md` — architecture, stack, UC2 framing.
- `docs/DECISIONS.md` — 2026-05-01 stack reversal (C# → C4); 2026-04-10
  model selection (gpt-4.1-mini); 2026-04-09 write-guard wording;
  2026-04-19 OQ-9 resolution (DAR routing as status flag, no approver
  workflow in Phase 2/3).
- `plan/phase3-agent-app-scaffold-1.md` — UC sequencing (UC1 → UC2 →
  UC3); identity-threading pattern (PAT-001, closure-based);
  scaffolded file layout; risks inherited.
- `spikes/c4_chainlit/app.py` — **parity reference for the approval
  loop.** Lines 28–45 (chat-start), 48–79 (`_prompt_for_approval`),
  82–132 (message loop). UC2 must mirror lines 95–132 verbatim.
- `spikes/_shared/agent.py` — reference pattern for
  `@tool(approval_mode="always_require")` declaration and
  `Agent` construction with `FoundryChatClient` +
  `AzureCliCredential`.
- `shared/business_rules.py` —
  `compute_default_access_level`,
  `determine_approval_route`. Single source of truth — UC2 imports
  and calls directly. Do not port.
- `shared/database.py` — `Delegate`, `Delegation`,
  `DocumentAccessRight`, `FrameworkAgreement`, `DelegateRole`,
  `ApprovalStatus`, `ClassificationLevel`, `MembershipType`.
- `classical_app/routes/wizard_helpers.py` — atomic transaction
  pattern (`_handle_step4_post`, lines 386–464),
  `_generate_delegate_id` (line 297),
  `_email_exists_in_delegation` (line 66), `_build_delegate`
  (line 322 — note role default is `DelegateRole.DELEGATE`),
  `_build_dars` (line 352).
- `classical_app/routes/wizard.py` — high-level flow + permission
  decoration (`@editor_of_delegation_required`).
- `tests/classical_app/test_wizard_approval_routing.py` — D-series
  scenario assertions UC2 must replicate against the agent flow.
- `tests/classical_app/test_wizard_rollback.py` — pattern for
  rollback assertions UC2 reuses.
- `.claude/CLAUDE.md` — Agent Framework & Chainlit Policy, including
  Context7 IDs and MS Learn pivot mandate.

### Mined archived plans (cite, do not copy)

- `plan/_archived/failed-attempt-2026-04/feature-phase4a-create-write-tools-1.md`
  — write-tool inventory + scenario matrix + rollback test pattern.
  **Survives:** scenario matrix (5 D-series cases), rollback test
  shape, `_generate_delegate_id` pattern (now lifted from classical),
  unit-test structure (function-scoped engine fixture, monkeypatch).
  **Drops:** `FunctionInvocationContext.kwargs["delegate_id"]`
  identity injection (replaced by closure DI per scaffold PAT-001),
  `role=DelegateRole.DELEGATION_EDITOR` default (defect — corrected
  to `DelegateRole.DELEGATE` per classical wizard line 348),
  `_next_dar_id` generator (DAR id is autoincrement int — see
  `reference_schema_pitfalls`), two separate write tools (replaced
  by single combined tool for atomicity).
- `plan/_archived/failed-attempt-2026-04/feature-phase4b-create-server-prompt-1.md`
  — system-prompt structure for the create-side branch.
  **Survives:** prompt section structure (Persona /
  Elicitation / Write-guard / HITL-guard / Failure-reporting),
  validated write-guard wording, the access-classification rule
  bullet, the approval-routing rule bullet, the
  "do-not-claim-write-happened-until-confirmation" guard.
  **Drops:** AG-UI `RUN_FINISHED.interrupt` framing (Chainlit
  surfaces `user_input_requests` differently — see spike); curl
  smoke script (Chainlit doesn't expose AG-UI SSE);
  `## Persona Mode Selection` heading split for approver-side
  (UC3 owns its own prompt — UC2's prompt is editor-only).
- `plan/_archived/failed-attempt-2026-04/feature-phase4d-create-integration-tests-1.md`
  — integration-test scenario shape + audit-trail pattern.
  **Survives:** 5-scenario parametrised matrix, denial-path test
  (auto-deny → no row + agent acknowledgement), audit-middleware
  capture via loguru sink.
  **Drops:** AG-UI replay-based event capture (replaced by Chainlit
  approval-response capture — agent re-driven with
  `Message("user", approval_responses)`).
- `plan/_archived/failed-attempt-2026-04/feature-phase4c-create-frontend-hitl-1.md`
  — **skipped entirely.** Stack-bound to AG-UI / CopilotKit. Chainlit
  + `cl.AskActionMessage` replaces every concern in this plan.
- `plan/_archived/failed-attempt-2026-04/feature-phase4c-fix-message-ordering-1.md`
  — **skipped entirely.** Out-of-order tool history was an AG-UI
  wire-protocol artifact (`docs/DECISIONS.md` 2026-04-28 quarantine
  entry). Chainlit's session model has no such failure mode in the
  C4 spike.
- `plan/_archived/failed-attempt-2026-04/bug-delegate-identity-leak-1.md`
  — **diagnosis carried forward, fix re-applied.** `whoami()` tool
  added to UC2's read-only surface; system prompt forbids the model
  from asking for the editor's `delegate_id`.

### Memory references

- `reference_foundry_model_config` — `.env` shape and gpt-4.1-mini
  default.
- `reference_schema_pitfalls` — DAR id is autoincrement int,
  `compute_default_access_level` never returns CONFIDENTIAL,
  `DelegateRole` only has DELEGATE / DELEGATION_EDITOR.
- `reference_flask_auth_session` — classical app's session-based
  delegate_id pattern (cited for parity; UC2 uses
  `cl.user_session` instead).
- `reference_visual_verify_skill` — used post-merge for end-to-end
  Chainlit UI check.
- `reference_python_agui_client_broken` — context for why the AG-UI
  Python path was not chosen.

### Context7 verification queue (TBD)

Before code lands, query Context7 with the project's mandated
`?pivots=programming-language-python` flag for:

| Topic | Context7 ID | Purpose |
|---|---|---|
| `cl.AskActionMessage` action API + timeout semantics | `/chainlit/chainlit` | Confirm `actions=[cl.Action(...)]`, payload shape, timeout default. |
| `agent_framework.Agent.create_session` + `agent.run(stream=True)` | `/websites/learn_microsoft_en-us_agent-framework` | Confirm `AgentSession` lifecycle (settled 2026-05-02 — see §5.3). |
| `@tool(approval_mode="always_require")` + `to_function_approval_response` | `/websites/learn_microsoft_en-us_agent-framework` | Confirm approval-response contract on the *with-session* path. |
| `agent_framework.Message("user", approval_responses)` shape | `/websites/learn_microsoft_en-us_agent-framework` | Confirm round-tripping approval responses. |

Until those queries are run, every API claim that is not directly
attributable to a line in `spikes/c4_chainlit/app.py` is marked
**TBD** in this document.
