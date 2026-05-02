# PRD — UC3: Approver Inbox (Asynchronous Queue over `DocumentAccessRight.approval_status`)

> **Status:** Draft (2026-05-02) · **Owner:** stephane.varin@gmail.com
> **Phase:** 3 (post-UC1, post-UC2) · **Stack:** Chainlit 2.x + `agent-framework` (Python)
> **Related plan:** `plan/phase3-agent-app-scaffold-1.md` §3 — UC3 (third in the UC1 → UC2 → UC3 sequence)
> **Resolves:** OQ-9 Phase 4 portion (asynchronous approver UX, separate Chainlit session/page)

---

## 1. Executive Summary

### Problem Statement

Today, restricted and confidential `DocumentAccessRight` (DAR) rows
created via the classical wizard or the UC2 agent land in
`approval_status = PENDING_DELEGATION_HEAD` or `PENDING_SECRETARIAT`
with **no UI to action them**. The status flag was deliberately
shipped without an inbox in Phase 2 (DECISIONS `[2026-04-19]`,
OQ-9 Phase 2 portion). The PoC narrative is incomplete until an
approver can see and decide pending requests.

### Proposed Solution

A **separate Chainlit chat profile** inside the same `agent_app/`
Python process, exposing a small set of `@tool`-decorated functions
that read and mutate `DocumentAccessRight.approval_status` directly.
The approver is the human in the loop — the agent mediates the queue,
it does **not** issue `cl.AskActionMessage` approval prompts on the
approver's writes. UC3 is an **asynchronous queue over a status
field**, not an in-flight HITL handshake. (OQ-9 Phase 4 decision,
2026-05-01.)

### Success Criteria

| KPI | Target |
|---|---|
| K1. End-to-end approve flow | Delegation head logs into the approver profile, asks "what's in my queue?", says "approve DAR 17 — looks fine". DAR row's `approval_status` flips to `APPROVED` within one conversational turn. |
| K2. Scope enforcement (zero leakage) | A delegation head **cannot** see or mutate a DAR belonging to a different delegation. 100% of seeded cross-delegation DARs are filtered out of `list_pending_dars`; 100% of cross-scope `approve_dar` / `reject_dar` calls raise `PermissionError("out_of_scope")`. |
| K3. Audit completeness | Every approve/reject tool invocation produces one structured audit log line (actor, target DAR id, decision, reason, ISO-8601 timestamp). 0 missing entries across the integration test suite. |
| K4. Proactive brief on `on_chat_start` | For an authenticated approver, the first agent message contains: pending count, breakdown by classification level, breakdown by delegation, oldest pending age in days. No tool call needed from the user to see the brief. |
| K5. Profile separation | Selecting the **Approver Inbox** chat profile registers approver-side tools only; the **Delegation Editor** profile (UC1 + UC2) does not see `list_pending_dars` / `approve_dar` / `reject_dar` in its tool list. |

---

## 2. User Experience & Functionality

### Personas

- **Delegation Head** (new role — `DelegateRole.DELEGATION_HEAD`,
  added to the enum per TBD-SCHEMA-1, *Resolved 2026-05-02 by user*).
  Approves DARs for delegates of their own delegation, scoped to
  `PENDING_DELEGATION_HEAD`. Real-world analog: head of the FRA
  delegation reviewing access requests for FRA delegates.
- **Secretariat Staff** (new role — `DelegateRole.SECRETARIAT`,
  added to the enum per TBD-SCHEMA-1, *Resolved 2026-05-02 by user*).
  Approves DARs scoped to `PENDING_SECRETARIAT` across all
  delegations (CONFIDENTIAL or any retroactive request). Real-world
  analog: OECD central staff.
- **Out-of-scope (negative persona):** Delegation editors and plain
  delegates. They should not be able to select the Approver Inbox
  profile, and even if they reach the tools the role guard returns
  `[]` / raises `PermissionError`.

### User Stories

- **US-1 (read).** As a delegation head, I want to open the inbox and
  immediately see how many requests wait, what they're for, and which
  are oldest, so I can prioritise.
- **US-2 (read).** As an approver, I want to ask "tell me more about
  DAR 17" and get delegate, delegation, committee, classification,
  retroactive flag, creator, and creation time.
- **US-3 (write).** As an approver, I want to say "approve DAR 17,
  looks fine" and have the agent flip to `APPROVED`, capture my
  optional comment, and confirm. No second prompt.
- **US-4 (write).** As an approver, I want to say "reject DAR 18 —
  wrong classification" and have the agent flip to `REJECTED`, store
  the reason verbatim. Empty reason must be refused.
- **US-5 (safety).** Out-of-scope approve/reject must be refused
  with an explanation; DB must not change.

### Acceptance Criteria

- AC-1 (US-1): On `@cl.on_chat_start` after Approver Inbox profile
  selection, the agent posts a brief: pending count, breakdown by
  `classification_level`, breakdown by delegation, oldest pending age
  in whole days. Empty queue reads *"No pending approvals in your
  queue."*.
- AC-2 (US-2): `get_dar_details(dar_id)` returns delegate full name +
  delegation, committee, `classification_level`, `retroactive`,
  `approval_status`, `created_at`, `created_by`, plus a one-line
  human summary.
- AC-3 (US-3): `approve_dar(dar_id, comment)` flips `PENDING_*` →
  `APPROVED`, stamps `approved_by` + `approved_at` (naive UTC), stores
  `comment` verbatim into `decision_comment` (may be empty).
  Idempotent on already-`APPROVED`; raises
  `ValueError("invalid_state")` on `REJECTED` / `AUTO_APPROVED`.
- AC-4 (US-4): `reject_dar(dar_id, reason)` flips to `REJECTED`,
  stamps `rejected_by` + `rejected_at`, stores `reason` verbatim into
  `decision_comment` (non-empty — empty raises
  `ValueError("reason_required")`, enforced at the tool layer not the
  DB schema). Idempotent on already-`REJECTED`; invalid on
  `APPROVED` / `AUTO_APPROVED`.
- AC-5 (US-5): Cross-scope `approve_dar` / `reject_dar` raises
  `PermissionError("out_of_scope")` **before** any DB mutation; the
  agent surfaces the error and does not retry.
- AC-6: `list_pending_dars()` never returns out-of-scope rows; editors
  / plain delegates get `[]`.
- AC-7: Audit middleware logs each approve/reject with
  `actor_delegate_id`, `tool_name`, `dar_id`, `decision`,
  `reason_or_comment`, `timestamp_utc`, `outcome` (`success` |
  `permission_error` | `value_error`).
- AC-8: Approver Inbox reachable only via the dedicated Chainlit chat
  profile; editor profile's `agent.tools` excludes approver tools.

### Non-Goals

- **No in-session HITL on approver writes.** No
  `@tool(approval_mode="always_require")` on UC3 tools — the approver
  IS the human in the loop. (OQ-9 Phase 4, DECISIONS `[2026-05-01]`.)
- **No DAR field edits beyond approval status.** One-way transition
  `PENDING_*` → `APPROVED` | `REJECTED`. No mutation of
  `classification_level`, `retroactive`, `delegate_id`,
  `committee_id`, `created_at`. Reshape = reject + recreate.
- **No DAR delete.** Rejected rows retained as audit history.
- **No notification system.** Polling-on-open only — no email,
  push, or cross-profile badge.
- **No bulk approve/reject.** One DAR per tool call.
- **No real RBAC.** Role from `Delegate.role` (post the
  TBD-SCHEMA-1 enum extension, *Resolved 2026-05-02*); OQ-1 remains
  open.
- **No multi-approver / two-of-N workflow.**
- **No production identity wiring.** Dev-mode login bypass via
  `cl.user_session`; same caveat as UC1/UC2.

---

## 3. AI System Requirements

### Tool Set (registered only on Approver Inbox profile)

All four tools are **plain `@tool`-decorated functions, no
`approval_mode`**. Identity (`approver_delegate_id`) is closure-bound
per the PAT-001 pattern from `plan/phase3-agent-app-scaffold-1.md`.

| Tool | Signature | Side effect | Returns |
|---|---|---|---|
| `list_pending_dars` | `() -> list[dict]` | none | List of in-scope pending DARs. Each entry: `{id, delegate_id, delegate_full_name, delegation_id, delegation_name, committee_id, committee_name, classification_level, retroactive, approval_status, created_at, created_by, age_days}`. Sorted by `created_at` ascending. |
| `get_dar_details` | `(dar_id: int) -> dict` | none | Single DAR detail dict (superset of list entry plus a one-line `summary` field the agent can read aloud). Raises `LookupError("not_found")` for unknown id. Raises `PermissionError("out_of_scope")` if DAR not in caller scope. |
| `approve_dar` | `(dar_id: int, comment: str = "") -> dict` | DB write: `approval_status = APPROVED`, `approved_by`, `approved_at`, `decision_comment`. Audit log line. | `{id, approval_status, approved_by, approved_at, decision_comment}`. Idempotent on `APPROVED`. Raises `ValueError("invalid_state")` for `REJECTED` / `AUTO_APPROVED`. Raises `PermissionError` for out-of-scope. |
| `reject_dar` | `(dar_id: int, reason: str) -> dict` | DB write: `approval_status = REJECTED`, `rejected_by`, `rejected_at`, `decision_comment`. Audit log line. Required-on-reject guard enforced at the tool layer (not in the schema). | `{id, approval_status, rejected_by, rejected_at, decision_comment}`. Idempotent on `REJECTED`. Raises `ValueError("reason_required")` if `reason.strip() == ""`. Raises `ValueError("invalid_state")` for `APPROVED` / `AUTO_APPROVED`. Raises `PermissionError` for out-of-scope. |

#### Scope predicate (single source — implemented as a private helper)

```
def _dar_in_scope(dar: DocumentAccessRight, approver: Delegate) -> bool:
    if approver.role == DelegateRole.SECRETARIAT:
        return dar.approval_status == ApprovalStatus.PENDING_SECRETARIAT
    if approver.role == DelegateRole.DELEGATION_HEAD:
        return (
            dar.approval_status == ApprovalStatus.PENDING_DELEGATION_HEAD
            and dar.delegate.delegation_id == approver.delegation_id
        )
    return False
```

Same predicate used by `list_pending_dars` (as a SQL `WHERE` clause —
do not post-filter), `get_dar_details`, `approve_dar`, `reject_dar`.

### System Prompt (approver branch)

The agent is constructed in `agent_app/agent.py` with a profile-aware
`instructions` string. Approver branch must:

1. State the role explicitly: *"You are assisting an approver
   reviewing pending document access right requests."*
2. List the four tools and when to call each.
3. **Forbid retry on `PermissionError("out_of_scope")`** — surface it
   verbatim to the user and stop.
4. **Forbid retry on `ValueError("invalid_state")`** — explain that
   the DAR was already actioned and stop.
5. Mandate proactive brief on session start: call
   `list_pending_dars()` immediately, then summarise as count +
   breakdown + oldest age. If empty, say so plainly.
6. For approve flows where the user gives a one-liner, treat the
   message itself as the approval intent. Do not ask "are you sure?".

### Evaluation Strategy

- **Unit (tool layer):** `tests/agent_app/test_uc3_approver_tools.py`
  covers status transitions, scope, idempotency, audit-column stamps,
  and `LookupError` / `ValueError` / `PermissionError` paths. Use
  seeded test fixtures (delegation heads FRA + DEU, secretariat
  OECD, 4 pending DARs across `PENDING_DELEGATION_HEAD` and
  `PENDING_SECRETARIAT` scopes — including one `retroactive=True`
  and one `CONFIDENTIAL` row).
- **Integration (FakeChatClient pattern):**
  `tests/agent_app/test_uc3_approver_integration.py` drives the agent
  end-to-end through (a) approve flow, (b) reject flow, (c)
  out-of-scope flow, (d) visibility propagation (post-approval,
  `is_document_visible` from `shared.business_rules` flips to
  `True` for the underlying document). Mirrors the four flows
  specified in the archived `feature-phase4h` plan.
- **Manual smoke:** `chainlit run agent_app/app.py`; pick the
  Approver Inbox profile as `DEL-2026-HEAD-FRA`; ask "what's in my
  queue?"; ask "approve DAR <n>"; ask "reject DAR <m> — wrong
  committee"; verify SQLite state via the classical app's read pages.
- **Parity check:** approving via UC3 produces the same final
  `is_document_visible` outcome as the classical app would (when /
  if it exposes an approver page — currently it does not, so this
  parity is via DB state only).

---

## 4. Technical Specifications

### Profile-Based Separation (Chainlit `chat_profiles`)

UC1+UC2 (Delegation Editor) and UC3 (Approver Inbox) live in the same
`agent_app/app.py` process but as **two distinct Chainlit chat
profiles** (verified via Context7 `/chainlit/docs`,
`@cl.set_chat_profiles` API).

```python
@cl.set_chat_profiles
async def chat_profiles() -> list[cl.ChatProfile]:
    return [
        cl.ChatProfile(
            name="Delegation Editor",
            markdown_description="Create delegates and assign access rights.",
        ),
        cl.ChatProfile(
            name="Approver Inbox",
            markdown_description="Review and decide pending DAR requests.",
        ),
    ]

@cl.on_chat_start
async def on_chat_start() -> None:
    profile = cl.user_session.get("chat_profile")  # str
    delegate_id = _resolve_delegate_id_for_dev(profile)  # bypass; see SEC
    agent = build_agent_for_profile(profile, delegate_id)
    cl.user_session.set("agent", agent)
    if profile == "Approver Inbox":
        await _post_proactive_brief(agent, delegate_id)
```

`build_agent_for_profile(profile, delegate_id)` returns an `Agent`
whose `tools=[...]` list is profile-specific — editor profile gets
UC1+UC2 tools, approver profile gets the four UC3 tools. The two
agents share the same `FoundryChatClient` and credential, only the
tool set + `instructions` differ.

**Verified:** `@cl.set_chat_profiles` decorator + `cl.ChatProfile`
constructor (name, markdown_description, icon) — Context7
`/chainlit/docs`, examples retrieved 2026-05-02. Profile selection
populates `cl.user_session.get("chat_profile")` as a string before
`@cl.on_chat_start` runs.

**Profile persistence (TBD-CHAINLIT-1, *Resolved 2026-05-02 by
user*).** `chat_profile` survives a hard refresh / new tab via the
`/project/settings?chat_profile=...` URL query param and the socket
auth payload (sources: `chainlit/server.py:811`,
`chainlit/socket.py:185-187`, `chainlit/user_session.py:31`). The
defence-in-depth role check in `on_chat_start` is still recommended
(see R3) but no longer load-bearing.

### Identity & Role Resolution

The PAT-001 closure pattern from
`plan/phase3-agent-app-scaffold-1.md` applies verbatim. Each tool is
produced by a factory that captures `approver_delegate_id`. Inside
the tool body, the approver record is reloaded from SQLite each call
(role + delegation_id), to avoid stale-cache bugs if a role changes
mid-session.

```python
def make_approve_dar(approver_delegate_id: int):
    @tool
    def approve_dar(dar_id: int, comment: str = "") -> dict:
        with session_scope() as s:
            approver = s.get(Delegate, approver_delegate_id)
            dar = s.get(DocumentAccessRight, dar_id)
            if dar is None:
                raise LookupError("not_found")
            if not _dar_in_scope(dar, approver):
                raise PermissionError("out_of_scope")
            ...
    return approve_dar
```

### Schema Changes Required (Prerequisite to Implementation)

**Schema deltas block UC3 implementation.** This PRD specifies them;
edits land in a small prerequisite plan merged before UC3
implementation opens.

1. **TBD-SCHEMA-1: `DelegateRole` enum extension** (*Resolved
   2026-05-02 by user — Proposal A*). Extend the enum currently
   carrying `DELEGATE`, `DELEGATION_EDITOR` (`shared/database.py`
   line 116) with two additive members: `DELEGATION_HEAD` and
   `SECRETARIAT`. Single-line change, matches archived
   `feature-phase4e` REQ-001. Proposal B (separate `Approver` table
   keyed on `delegate_id`) is the production landing path and stays
   deferred under OQ-1. The permission helper added with this change
   mirrors the shape of `editor_of_delegation_required` from Phase 2B.
   Full proposal: `docs/research-uc3-schema-deltas.md`.
2. **TBD-SCHEMA-2: `DocumentAccessRight` audit columns** (*Resolved
   2026-05-02 by user*). Add five nullable columns to the model in
   `shared/database.py` (lines 334–381):
   - `approved_by` — FK → `delegates.id`
   - `approved_at` — naive UTC `DateTime` (matching the existing
     model convention, no `tzinfo`)
   - `rejected_by` — FK → `delegates.id`
   - `rejected_at` — naive UTC `DateTime`
   - `decision_comment` — single free-text column used on both
     approve and reject (replaces the earlier split `comment` +
     `reason` proposal)
   The required-on-reject guard lives at the tool layer (raises
   `ValueError("reason_required")`), not in the DB schema. SQLite
   dev DB rebuilt from seed; no Alembic.
3. **TBD-SCHEMA-3: Seed extension** (*Resolved 2026-05-02 by user*).
   `shared/seed_data.py` adds, idempotently:
   - One sentinel `OECD` delegation with `MembershipType.MEMBER`
     (least-wrong existing enum value — `MembershipType.SECRETARIAT`
     does not exist).
   - Two delegation-head personas: `DEL-2026-HEAD-FRA` (FRA),
     `DEL-2026-HEAD-DEU` (DEU). Two heads so the empty-queue case
     is demonstrable without first acting on a row.
   - One secretariat persona: `DEL-2026-SEC-001` (in `OECD`).
   - Four pending DARs (ids 25–28) spanning
     `PENDING_DELEGATION_HEAD` and `PENDING_SECRETARIAT`, across at
     least two delegations, including one `retroactive=True` row
     and one `CONFIDENTIAL` row (which routes to
     `PENDING_SECRETARIAT` via `determine_approval_route`).
   - **Persona ID convention:** semantic IDs
     (`DEL-2026-HEAD-FRA`, `DEL-2026-SEC-001`, etc.) are an additive
     convention for approver personas; the existing numeric
     `DEL-2026-NNNN` format is preserved for non-approver personas.
4. **No `ApprovalStatus` enum extension.** `APPROVED` / `REJECTED`
   already exist (lines 109–113).

### Business-Rule Helpers

Add a small helper to `shared/business_rules.py` so the brief can
compute aggregates without duplicating the scope predicate:

- `count_pending_dars_for_approver(approver: Delegate, session) -> int`
- `summarise_pending_for_approver(approver: Delegate, session) -> dict`
  returning `{count, by_classification, by_delegation, oldest_age_days}`.

These wrap the same `_dar_in_scope` predicate logic. The agent's
proactive brief consumes `summarise_pending_for_approver` directly
(server-side) and streams it as the first message — no model tool
call needed for the brief itself, in contrast to UC1's
agent-driven brief. Rationale: deterministic content for the
PoC demo; one less round-trip per chat-start.

### Architecture (UC3 Slice)

```
┌─────────────────────────────────────────────────────────────────┐
│  Chainlit (single process, two chat profiles)                  │
│                                                                 │
│  Profile: Delegation Editor       Profile: Approver Inbox       │
│   ├─ on_chat_start                 ├─ on_chat_start             │
│   ├─ tools: UC1 + UC2              ├─ tools: UC3 (4 tools)      │
│   └─ instructions: editor branch   ├─ proactive brief (server)  │
│                                    └─ instructions: approver    │
│                                                                 │
│  Both share: AzureCliCredential, FoundryChatClient,             │
│              audit middleware, session_scope() DB helper        │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
              ┌──────────────────────┐
              │  shared/             │
              │   database.py (+Δ)   │
              │   business_rules.py  │
              │   seed_data.py (+Δ)  │
              └──────────┬───────────┘
                         ▼
                   one_agent.db
```

### Audit Middleware

Same `agent-framework` function-invocation middleware UC2 wires.
Approver tool calls produce structured logs with the same shape;
`tool_name` discriminates `approve_dar` / `reject_dar` from UC2's
`create_delegate` / `assign_delegate_to_committee`. No new
middleware module — the existing one observes both profiles'
agents.

### Integration Points

- **DB:** SQLite `one_agent.db`, accessed via the existing
  `session_scope()` helper (Phase 3 scaffold FILE-004).
- **Identity:** `cl.user_session` `delegate_id` slot, populated at
  `on_chat_start` via the dev-mode login bypass (same pattern as
  UC1+UC2). Production identity is post-PoC.
- **Classical app interop:** UC3 writes are visible to the classical
  app's read pages immediately (shared DB). The classical app does
  not yet expose an approver UI; UC3 is the only approver UX in the
  PoC.

### Security & Privacy

- **No secrets in code.** `AzureCliCredential` via `az login`.
- **Identity never visible to the model.** `approver_delegate_id`
  is closure-bound; tool signatures expose only `dar_id` (+
  `comment` / `reason`) to the model. This is the same SEC-001
  posture as UC1/UC2.
- **Scope enforced at the tool layer, not the prompt.** A
  jailbroken or misled model still cannot mutate cross-scope DARs —
  the predicate runs in Python before any DB write.
- **Audit log includes actor and reason.** Sufficient for
  after-the-fact reconstruction even if the chat transcript is
  lost.
- **GDPR / PII:** unchanged from baseline. DARs reference delegate
  PII (name, email) by foreign key; the audit log stores delegate
  *ids*, not names. OQ-4 (production GDPR model) remains open.

---

## 5. Risks & Roadmap

### Phased Rollout

- **MVP (this PRD):** profile separation + 4 tools + audit + brief;
  one head (FRA) + one secretariat persona; manual smoke + integration
  tests green.
- **v1.1 (post-PoC):** bulk approve/reject; multi-approver workflows;
  Chainlit profile-badge if/when the framework grows the primitive.
- **v2.0 (post-PoC):** real RBAC (OQ-1); production SSO; Alembic
  migrations for the schema deltas.

### Technical Risks

- **R1 — Schema TBDs land late.** UC3 blocked until `DelegateRole` is
  extended + DAR audit columns exist. Mitigation: tiny prerequisite
  plan merged before the UC3 implementation plan opens.
- **R2 — Chainlit `chat_profiles` API drift.** Validated via Context7
  2026-05-02 against `/chainlit/docs`. `ChatProfile(name,
  markdown_description, icon)` is stable on Chainlit 2.11.1
  (TBD-CHAINLIT-2 *Resolved 2026-05-02 by user*); `pyproject.toml`
  will be tightened to `chainlit>=2.11,<3` and moved out of the
  `[spikes]` extra into main deps as a separate cross-cutting fix
  tracked outside this PRD. Mitigation: smoke-boot two profiles
  before any UC3 tool code lands.
- **R3 — Profile choice does not survive refresh** (TBD-CHAINLIT-1
  *Resolved 2026-05-02 by user* — empirically false: profile
  persists via URL query param + socket auth payload). Risk
  downgraded; defence-in-depth role check in `on_chat_start` retained
  but no longer load-bearing.
- **R4 — Model retries `out_of_scope` errors.** System prompt forbids
  retry; integration test asserts single tool invocation per
  scope-violation. Tighten prompt guardrail if the model misbehaves.
- **R5 — Brief fires for the wrong profile.** Gated by `profile ==
  "Approver Inbox"` in `on_chat_start`, not by prompt — eliminates the
  archived 4G regression risk by construction.
- **R6 — Concurrent-approver race.** SQLite serial writes plus
  `invalid_state` guard make the second call a no-op with a clear
  error. Acceptable at PoC scale.
- **R7 — `cl.user_session` bleed across profiles.** Mitigation: clear
  all session keys in `on_chat_start` before re-populating.

### Open Caveats

- **Profile-switch mid-`AskActionMessage`.** Switching Chainlit chat
  profiles while a `cl.AskActionMessage` action UI is pending drops
  the pending action state (verified 2026-05-02 against Chainlit
  2.11.1). UC3's approver tools are **not** approval-gated, so this
  caveat does not affect UC3 directly. It is documented here as a
  reminder for any future HITL surface that borrows UC3's profile
  shape — notably UC2, which does use `cl.AskActionMessage` for
  approval prompts.

### Assumptions

- A1. UC1 and UC2 are merged and stable — UC3 inherits the
  identity wiring, audit middleware, and `session_scope()` helper
  established there.
- A2. `gpt-4.1-mini` retains its tool-selection quality from
  Phase 0f / C4 spike (carried over from Phase 3 scaffold
  ASSUMPTION-002).
- A3. SQLite dev DB is rebuilt from seed during development; no
  Alembic migration needed for the schema TBDs (matches
  `reference_db_reset.md`).

---

## 6. Related Specifications / Further Reading

### Foundational

- `plan/phase3-agent-app-scaffold-1.md` §1 — closure DI (PAT-001),
  identity threading (REQ-002, SEC-001). UC3 inherits verbatim.
- `plan/phase3-agent-app-scaffold-1.md` §3 — sequencing context.
  Earlier draft contradicted OQ-9 Phase 4 (2026-05-01) by saying
  UC3 tools were approval-gated; resolved upstream by commit
  `0946c9f` (2026-05-02). TBD-PLAN-1 closed.
- `docs/DESIGN.md` §"Use Cases" — currently UC1 + UC2 only; append
  UC3 post-merge.
- `docs/DECISIONS.md` `[2026-05-01]` — stack reversal + OQ-9 Phase 4.
- `docs/OPEN_QUESTIONS.md` OQ-9 (Phase 4 portion — UC3 resolves it),
  OQ-1 (full RBAC remains open).
- `spikes/c4_chainlit/app.py` — agent loop reference; UC3 reuses
  everything except the `_prompt_for_approval` branch.
- `shared/database.py` — `DocumentAccessRight` (l. 334),
  `ApprovalStatus` (l. 94), `DelegateRole` (l. 116). Schema TBDs
  target lines 116, 334–381.
- `shared/business_rules.py` — `determine_approval_route` (l. 59) is
  the routing rule UC3 mirrors. UC3 adds
  `count_pending_dars_for_approver` + `summarise_pending_for_approver`.

### Mined from the 2026-04 archived attempt (cite-don't-copy)

The earlier AG-UI / CopilotKit attempt produced four phase-4 plans.
The tool layer was always agent-driven, so portability is high. Drop
all CopilotKit React route + HITL-on-approver-write specifics; map to
Chainlit `chat_profiles`.

- `plan/_archived/failed-attempt-2026-04/feature-phase4e-approver-seed-list-tool-1.md`
  — **Survives:** scope predicate, seed-extension shape,
  `count_pending_dars_for_approver` helper, idempotency rule.
  **Drop:** flat `agent_app/tools.py` layout (UC3 follows the Phase 3
  scaffold's `agent_app/tools/<feature>.py` structure).
- `plan/_archived/failed-attempt-2026-04/feature-phase4f-approver-write-tools-1.md`
  — **Survives:** `_assert_dar_in_scope` helper extraction,
  approve/reject happy-path + audit-column writes, required reject
  reason, rollback on commit failure, visibility-propagation test.
  **Drop:** `@tool(approval_mode="always_require")` on writes —
  removed per OQ-9 Phase 4.
- `plan/_archived/failed-attempt-2026-04/feature-phase4g-approver-prompt-brief-badge-1.md`
  — **Survives:** approver-side system-prompt branch (no retry on
  `out_of_scope`, list-first behaviour, scope-error surfacing),
  proactive brief content (count + breakdown + oldest age).
  **Drop:** `/api/delegates` count field, `DelegatePicker.tsx` badge,
  CSS — Chainlit `chat_profiles` has no native badge analog
  (**TBD-FUTURE-1**).
- `plan/_archived/failed-attempt-2026-04/feature-phase4h-approver-integration-tests-1.md`
  — **Survives:** the four integration scenarios + FakeChatClient
  pattern. **Drop:** Next.js Playwright e2e — Chainlit selector model
  differs; e2e tracked separately if cheap to extend.

### External / verified APIs

- Chainlit `@cl.set_chat_profiles` + `cl.ChatProfile` — Context7
  `/chainlit/docs`, retrieved 2026-05-02. Verified: decorator returns
  `list[cl.ChatProfile]`; selection lands in
  `cl.user_session.get("chat_profile")` as a string before
  `@cl.on_chat_start`.
- Chainlit `cl.user_session` — verified by `spikes/c4_chainlit/app.py`.
- `agent-framework` `@tool` decorator (no `approval_mode`) — verified
  by `spikes/_shared/agent.py` and Phase 3 scaffold PAT-001.
  **TBD-FRAMEWORK-1** *Resolved 2026-05-02 by user*. The `@tool`
  decorator returns a `FunctionTool` instance whose `.approval_mode`
  attribute is `Literal["never_require", "always_require"]` (source:
  `agent_framework/_tools.py:93,240,393,1166-1325`). AC-8 asserts
  via direct attribute access using **positive equality** — not
  inequality — because a missing `approval_mode` defaults silently
  to `"never_require"` and a negative test would let a misconfigured
  tool pass:
  ```python
  from agent_app.tools.approver import approve_dar_request, reject_dar_request
  assert approve_dar_request.approval_mode == "never_require"
  assert reject_dar_request.approval_mode == "never_require"
  ```
  Full evidence: `docs/research-phase3-api-verifications.md`.
- `agent-framework` function-invocation middleware (audit) — carried
  from UC2. Reference Context7
  `/websites/learn_microsoft_en-us_agent-framework`
  (`?pivots=programming-language-python`) at implementation time.

---

## TBD Inventory (consolidated)

| ID | Description | Blocks | Status |
|---|---|---|---|
| TBD-SCHEMA-1 | `DelegateRole` enum extension (`DELEGATION_HEAD`, `SECRETARIAT`). | All UC3 tools | **Resolved 2026-05-02** — Proposal A: extend enum additively. Production path (Proposal B, separate `Approver` table) deferred to OQ-1. Permission helper mirrors `editor_of_delegation_required` shape. |
| TBD-SCHEMA-2 | `DocumentAccessRight` audit columns. | `approve_dar`, `reject_dar` | **Resolved 2026-05-02** — Five nullable columns: `approved_by` (FK→`delegates.id`), `approved_at` (naive UTC `DateTime`), `rejected_by` (FK→`delegates.id`), `rejected_at` (naive UTC `DateTime`), `decision_comment` (single free-text column for both approve and reject). Required-on-reject guard at the tool layer, not the schema. |
| TBD-SCHEMA-3 | Seed extension. | Manual smoke + integration tests | **Resolved 2026-05-02** — Sentinel `OECD` delegation (`MembershipType.MEMBER`); two heads (`DEL-2026-HEAD-FRA`, `DEL-2026-HEAD-DEU`); one secretariat (`DEL-2026-SEC-001`); 4 pending DARs (ids 25–28) across both pending statuses and ≥2 delegations, including one `retroactive=True` and one `CONFIDENTIAL`. Semantic ID format additive; numeric `DEL-2026-NNNN` preserved for non-approver personas. |
| TBD-CHAINLIT-1 | `chat_profile` persistence across page refresh / new tab. | Profile-only access guarantee | **Resolved 2026-05-02** — Persists via URL query param (`/project/settings?chat_profile=...`) and socket auth payload (`chainlit/server.py:811`, `chainlit/socket.py:185-187`, `chainlit/user_session.py:31`). Caveat: profile-switch mid-`AskActionMessage` drops pending action state — captured under §5 Open Caveats; UC3 tools are not approval-gated so this affects only future HITL surfaces (e.g. UC2). |
| TBD-CHAINLIT-2 | Chainlit version pin matches `chat_profiles` API surface. | Profile separation | **Resolved 2026-05-02** — `ChatProfile(name, markdown_description, icon)` stable on Chainlit 2.11.1. `pyproject.toml` to be tightened to `chainlit>=2.11,<3` and moved out of `[spikes]` extra into main deps as a separate cross-cutting fix tracked outside this PRD. |
| TBD-FRAMEWORK-1 | `agent-framework` introspection API for asserting a tool is NOT approval-gated. | Test AC-8 mechanically | **Resolved 2026-05-02** — Direct attribute access on the `FunctionTool` returned by `@tool`: `tool.approval_mode` is `Literal["never_require", "always_require"]`. AC-8 uses **positive equality** (`== "never_require"`), not inequality, because a missing attribute defaults silently to `"never_require"`. Source: `agent_framework/_tools.py:93,240,393,1166-1325`; full evidence `docs/research-phase3-api-verifications.md`. |
| TBD-PLAN-1 | `plan/phase3-agent-app-scaffold-1.md` §3 UC3 entry contradiction. | Documentation consistency | **Resolved by upstream commit `0946c9f`** (2026-05-02). |
| TBD-FUTURE-1 | Chainlit profile-badge primitive (analog to archived 4G's frontend badge). | v1.1 polish | **Open** — deferred to post-MVP / v1.1. |
