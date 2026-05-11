---
goal: Phase 3 — scaffold agent_app/ as a Chainlit + agent-framework Python module on the C4 stack validated by spikes/c4_chainlit/, and define the UC1→UC2→UC3 sequence the PRDs will follow
version: 1.0
date_created: 2026-05-01
last_updated: 2026-05-01
owner: stephane.varin@gmail.com
status: 'Planned'
tags: [phase3, agent_app, chainlit, agent-framework, scaffold]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 3 scaffold work for `agent_app/` after the 2026-05-01 reversal of
the C# / .NET pivot (see `docs/agent-stack-decision-2026-04-29.md` §9).
Delivers a runnable but feature-empty agent app on the validated C4 stack
(Chainlit + `agent-framework` Python + `FoundryChatClient` +
`AzureCliCredential`) and locks the implementation order for UC1 / UC2
/ UC3 PRDs that follow this plan in separate sessions.

**Out of scope:** UC1 / UC2 / UC3 implementation — those are PRD-driven
in subsequent plans. This plan only ships the empty room with the
right load-bearing walls.

## 1. Requirements & Constraints

- **REQ-001**: Replicate the C4 spike's loop pattern (`@cl.on_chat_start`,
  `@cl.on_message`, `cl.user_session`, `agent.run(stream=True)` with
  approval polling via `cl.AskActionMessage`) — `spikes/c4_chainlit/app.py`
  is the parity reference.
- **REQ-002**: Single delegate-as-current-user identity model — read
  `delegate_id` from `cl.user_session` (set at `on_chat_start`),
  thread it into tool function parameters via `Annotated` defaults
  or a wrapper, never expose it to the model.
- **REQ-003**: One read-only tool registered at scaffold time
  (`get_current_delegate_summary` or similar) so the smoke test
  exercises the tool path. Picks a tool that doesn't require HITL —
  approval-gated tools wait for UC2.
- **REQ-004**: `shared/business_rules.py` is single-source: the agent
  imports and calls those functions directly. No port, no copy, no
  shim layer.
- **REQ-005**: Use existing seeded SQLite (`one_agent.db`) — same
  database the classical app reads/writes. Cross-app behavior must
  remain consistent.
- **CON-001**: Hand-written code budget for this plan ≤ 200 LOC
  (Chainlit boilerplate + tool skeleton + identity wiring).
- **CON-002**: No new top-level packages — only what `pyproject.toml`
  already lists (`chainlit`, `agent-framework`, `agent-framework-foundry`,
  `loguru`, `azure-identity`). `agent-framework-ag-ui` is NOT used.
- **CON-003**: Python 3.11, ruff format + check clean, pytest green.
- **CON-004**: Tools must be `@tool`-decorated functions in their own
  module; `app.py` only orchestrates Chainlit handlers.
- **GUD-001**: Before writing any code touching `agent_framework`
  APIs, query Context7 (`/websites/learn_microsoft_en-us_agent-framework`
  with `?pivots=programming-language-python`). Cross-language pattern
  leakage caused the multi-week derail and Step B FAIL — Python
  pivot is mandatory.
- **GUD-002**: Mirror `spikes/c4_chainlit/app.py` shape verbatim
  where the contract is identical (the approval-loop pattern works,
  do not re-invent it).
- **PAT-001**: Identity threading — store `delegate_id: int` in
  `cl.user_session` at chat-start; tools accept it via a Python
  closure or default-arg dependency injection so the model never
  sees it. Reference shape:
  ```python
  def make_get_current_delegate(delegate_id: int):
      @tool
      def get_current_delegate() -> str:
          # uses delegate_id from closure
          ...
      return get_current_delegate
  ```
- **SEC-001**: No secrets in code; rely on `az login` for
  `AzureCliCredential`. `.env` carries `FOUNDRY_PROJECT_ENDPOINT`
  + `FOUNDRY_MODEL=gpt-4.1-mini`.

## 2. Implementation Steps

### Implementation Phase 1 — Module scaffold

- GOAL-001: Create `agent_app/` Python package with the file layout
  the rest of the plan + future PRDs assume; verify it imports cleanly.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Verify worktree branch + `.env`. Check `pyproject.toml` lists `chainlit`, `agent-framework`, `agent-framework-foundry`, `loguru`, `azure-identity`. If `agent-framework-ag-ui` is still listed, remove it (no longer used). | ✅ | 2026-05-11 |
| TASK-002 | Create `agent_app/__init__.py` (empty) and `agent_app/app.py` (Chainlit entrypoint stub with `@cl.on_chat_start` + `@cl.on_message` returning a placeholder message). Verify `chainlit run agent_app/app.py` boots without error. | ✅ | 2026-05-11 |
| TASK-003 | Create `agent_app/agent.py` — `build_agent(credential, delegate_id) -> Agent` factory. Constructs `FoundryChatClient` from `FOUNDRY_PROJECT_ENDPOINT` + `gpt-4.1-mini` + `AzureCliCredential`. Tools list initially empty. Instructions string: TBD per UC1 PRD; for scaffold use a one-liner placeholder ("You assist a delegate. Tools added in subsequent phases."). | ✅ | 2026-05-11 |
| TASK-004 | Create `agent_app/tools/__init__.py` and `agent_app/tools/delegate.py` — placeholder module with the read-only tool `get_current_delegate_summary` factory function (closure-bound `delegate_id`). Stub returns one-line summary using `shared.database` queries (delegate name + delegation name). No write tools yet. | ✅ | 2026-05-11 |
| TASK-005 | Wire `app.py` end-to-end: `on_chat_start` reads `delegate_id` from `cl.user_session` (default `1` for spike-mode), constructs agent + session, stores them; `on_message` drives the loop verbatim from `spikes/c4_chainlit/app.py` minus the approval branch (no HITL tools yet, branch is dead but present for future UC2). | ✅ | 2026-05-11 |

### Implementation Phase 2 — Identity & DB session

- GOAL-002: Thread the current `delegate_id` from `cl.user_session`
  into tools without exposing it to the model; reuse classical app's
  SQLAlchemy session pattern.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Add `agent_app/session.py` — context-manager / dependency providing a SQLAlchemy session bound to `one_agent.db` (mirror `classical_app/`'s pattern). Tools acquire DB sessions through this helper, not raw connections. | | |
| TASK-007 | In `app.py`, accept `delegate_id` from a Chainlit chat-start arg or environment variable (development-only login bypass). Document that production identity wiring (real auth) is out of scope for Phase 3 scaffold but the `cl.user_session` slot is ready. | | |
| TASK-008 | Implement the closure-based DI in `agent_app/agent.py` `build_agent`: every tool factory receives `delegate_id` and returns a `@tool`-decorated callable. The agent's tool list is built from the factory outputs. Verify the agent can find tools by name through reflection. | | |

### Implementation Phase 3 — Smoke + tests

- GOAL-003: Prove the scaffold runs end-to-end against a live model
  with one read-only tool, before any UC PRD lands.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create `tests/agent_app/test_tools_delegate.py` — pytest covering `get_current_delegate_summary` against the seeded DB. Asserts the closure reads the right delegate. No Chainlit / agent-framework mocking — directly call the tool function. | | |
| TASK-010 | Create `tests/agent_app/test_agent_factory.py` — instantiate `build_agent` with a fake credential and `delegate_id`, assert the resulting `Agent` has the expected name, instructions, and tool count. No live HTTP calls. | | |
| TASK-011 | Manual smoke: `chainlit run agent_app/app.py`, log in as delegate `1`, type "Who am I?". Expected: agent calls `get_current_delegate_summary`, replies with delegate name + delegation. Capture output in plan notes. | | |
| TASK-012 | `ruff format . && ruff check --fix .` clean. `pytest` exits 0. Commit each task as a separate Conventional Commit. | | |

## 3. UC sequencing (Phase 3+ → Phase 5)

The PRDs that follow this plan land one per session. Order is fixed
by dependency, not preference.

### UC1 — Proactive Meeting Brief (first)

- **Why first:** read-only. No HITL, no approval gate. Validates the
  scaffold's agent + tool + Chainlit streaming pipeline against a
  realistic prompt. If UC1 doesn't work, UC2 / UC3 won't either.
- **Reads:** `Delegate`, `Meeting`, `Document`, `DocumentAccessRights`
  via `shared/business_rules.py` (`is_document_visible`,
  `get_visible_agenda_documents`, `get_new_documents_since`).
- **Writes:** none.
- **Tools added:** `get_upcoming_meetings`, `get_meeting_brief`,
  `get_new_documents`.
- **Exit criterion:** delegate logs in, asks "what do I have coming
  up?", agent surfaces meetings + new agenda docs since last visit.
- **PRD:** `docs/prd-uc1-meeting-brief.md` (drafted 2026-05-02).

### UC2 — Delegate Creation with Document Access Rights (second)

- **Why second:** validates HITL contract end-to-end, exercises
  approval-loop pattern from `spikes/c4_chainlit/app.py`. Heaviest
  business-rule load (membership type, committees, Framework
  Agreements, approval routing) — payoff of `shared/business_rules.py`
  staying single-source.
- **Reads:** existing delegations + committees.
- **Writes:** new `Delegate` + new `DocumentAccessRights` rows in a
  single transaction, gated by one `@tool(approval_mode="always_require")`
  call.
- **Tools added:** `create_delegate_with_access_rights` (approval-gated,
  combined transaction — delegate + DARs commit atomically; one
  approval prompt, one rollback boundary), `compute_default_dar_preview`
  (read-only computation tool — shows the rule output before the
  write fires). Note: committee assignment is implicit — DAR rows
  carry `committee_id`, so DAR creation establishes committee
  membership. Modifying an existing delegate's committee membership
  is out of UC2 scope (deferred to a later UC).
- **Why combined, not split:** two separate approval-gated tools
  (delegate + DARs) cannot satisfy atomicity — user could approve
  the delegate write, deny the DAR write, leaving an orphan
  delegate. One tool = one transaction = one approval = one
  rollback boundary. Mirrors the classical wizard's commit shape.
- **Exit criterion:** delegation editor types "create delegate Marie
  Dubois on the FRA delegation, member of EPC and TC", agent walks
  through reasoning, shows DAR preview, asks for approval, fires the
  write only on Approve. Identical outcome to classical app's wizard
  but in 3 conversational turns.
- **PRD:** `docs/prd-uc2-delegate-creation.md` (drafted 2026-05-02).

### UC3 — Approver Inbox (third)

- **Why third:** different role / different Chainlit profile.
  UC3 is **not** a re-use of UC2's HITL pattern — it is an
  asynchronous queue over `DocumentAccessRight.approval_status`,
  per OQ-9 Phase 4. The approver IS the human in the loop; the
  agent simply mediates the queue.
- **Reads:** pending DAR change requests filtered by approver scope
  (delegation-head sees own delegation; secretariat sees all).
- **Writes:** approval / denial of pending requests by direct
  state transition (`PENDING_*` → `APPROVED` / `REJECTED`).
- **Tools added:** `list_pending_approvals`, `approve_dar_request`,
  `reject_dar_request`. **None approval-gated.** Rationale: the
  approver typing "approve item 3" already carries intent; an extra
  `cl.AskActionMessage` confirm-before-write adds friction without
  safety. Cross-cutting audit middleware logs every approve/reject
  (actor, target DAR, decision, reason, timestamp).
- **Exit criterion:** approver logs in, agent proactively briefs
  pending count + breakdown, approver says "approve item 3", agent
  fires the write directly and confirms in chat.
- **PRD:** `docs/prd-uc3-approver-inbox.md` (drafted 2026-05-02).

### Sequencing gates between UCs

- UC1 → UC2: UC1 PR merged + Chainlit smoke green + 0 ruff / pytest
  regressions.
- UC2 → UC3: UC2 PR merged + at least one full HITL approve + deny
  flow exercised manually + parity check against classical-app
  wizard outputs (same delegate, same DARs, identical SQLite state).
- UC3 → Phase 4: UC3 PR merged + the three roles (delegate / editor
  / approver) demonstrably round-trip through their respective
  Chainlit entry points. After UC3, the PoC is feature-complete and
  Phase 4 (MCP KB integration, polish, demo prep) begins.

## 4. Alternatives

- **ALT-001**: Use `agent_app/` mirroring the *quarantined* failed
  attempt's layout (`docs/_archived/`). Rejected: that attempt was
  abandoned for HITL contract reasons that no longer apply on C4,
  but reusing its file shape risks reintroducing pattern leakage.
  Fresh scaffold, validated by `spikes/c4_chainlit/`.
- **ALT-002**: Build UC1 + UC2 + UC3 in parallel branches. Rejected:
  UC2's HITL pattern is the riskiest; a UC2 issue affects UC3.
  Sequential (UC1 → UC2 → UC3) gates the riskiest contract behind
  a working baseline.
- **ALT-003**: Bypass `cl.user_session` for identity, pass
  `delegate_id` via tool args. Rejected: the model would see
  identity, which violates SEC-001 / PAT-001. Closure-bound DI is
  the documented pattern.

## 5. Dependencies

- **DEP-001**: `chainlit>=2.0` already in `pyproject.toml`.
- **DEP-002**: `agent-framework>=1.0.0` + `agent-framework-foundry>=1.0.0`
  already in `pyproject.toml`.
- **DEP-003**: `azure-identity` (transitive via foundry, verify direct).
- **DEP-004**: `loguru>=0.7.0` for structured logging.
- **DEP-005**: `FOUNDRY_PROJECT_ENDPOINT` + `FOUNDRY_MODEL=gpt-4.1-mini`
  in `.env`. Active `az login` session.
- **DEP-006**: `one_agent.db` populated via `shared.seed_data` (already
  the case after Phase 2).
- **DEP-007**: `spikes/c4_chainlit/app.py` retained as parity reference.

## 6. Files

- **FILE-001**: `agent_app/__init__.py` — empty package marker.
- **FILE-002**: `agent_app/app.py` — Chainlit entrypoint
  (`@cl.on_chat_start`, `@cl.on_message`, approval-loop scaffold).
- **FILE-003**: `agent_app/agent.py` — `build_agent` factory.
- **FILE-004**: `agent_app/session.py` — DB session helper.
- **FILE-005**: `agent_app/tools/__init__.py` — empty package marker.
- **FILE-006**: `agent_app/tools/delegate.py` — first read-only tool
  (`get_current_delegate_summary`).
- **FILE-007**: `tests/agent_app/__init__.py` — test package marker.
- **FILE-008**: `tests/agent_app/test_tools_delegate.py` — tool-level
  pytest.
- **FILE-009**: `tests/agent_app/test_agent_factory.py` — factory
  pytest.
- **FILE-010**: `pyproject.toml` — remove `agent-framework-ag-ui`
  if still listed.

## 7. Testing

- **TEST-001**: `test_tools_delegate.py::test_get_current_delegate_summary`
  — closure returns the right delegate against seeded DB.
- **TEST-002**: `test_agent_factory.py::test_build_agent_assembles_tools`
  — factory returns an `Agent` with the expected tool count and
  instructions.
- **TEST-003**: Manual smoke — `chainlit run agent_app/app.py`,
  delegate `1`, "Who am I?", expect tool call + summary.
- **TEST-004**: `ruff format --check . && ruff check .` clean.
- **TEST-005**: `pytest` exits 0 (full suite incl. existing
  classical / shared tests).

## 8. Risks & Assumptions

- **RISK-001**: Chainlit 2.x API may have shifted vs C4 spike's
  validated 2026-04-29 surface. Mitigation: TASK-002 boots Chainlit
  before any agent code lands; if API drift, fix or pin in TASK-001.
- **RISK-002**: `agent-framework` Python package version drift since
  C4 spike. Same mitigation: smoke before code commits; pin if
  drift.
- **RISK-003**: Identity wiring via `cl.user_session` may not survive
  page refresh / multi-tab scenarios. Out of scope for scaffold;
  flag for the UC1 PRD.
- **RISK-004**: `shared/business_rules.py` may need minor signature
  tweaks to be ergonomic for closure-bound calls; mitigation —
  document in UC1 PRD if real, fix at UC1 time, not now.
- **ASSUMPTION-001**: C4 spike behavior (passing T1–T4 on 2026-04-29)
  is preserved in current `agent-framework` version. Re-validate
  via TASK-011 manual smoke before UC1 work begins.
- **ASSUMPTION-002**: `gpt-4.1-mini` retains its model-tested
  tool-selection quality. Carries over from Phase 0f / C4 spike.

## 9. Related Specifications / Further Reading

- `docs/agent-stack-decision-2026-04-29.md` §9 — Step B closure +
  pivot reversal context.
- `docs/research-agent-stack-candidates.md` §5.1 — C4 spike pass.
- `spikes/c4_chainlit/app.py` — parity reference (READ FIRST when
  starting work on this plan).
- `spikes/_shared/agent.py` — shared agent definition, pattern for
  `build_agent` factory.
- `shared/business_rules.py` — single-source business rules consumed
  by both apps.
- `classical_app/` — DB session pattern + delegate auth pattern to
  mirror.
- `.claude/CLAUDE.md` — Agent Framework & Chainlit Policy
  (Context7 ID, MS Learn `?pivots=programming-language-python`
  mandate).
