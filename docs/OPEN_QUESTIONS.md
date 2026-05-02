# Open Questions

Questions deferred from design, tracked here until resolved.

---

### OQ-1: Full permission/role model beyond delegation editor and secretariat
**Relevant phase**: Phase 4+
**Context**: The PoC uses two actor types (delegation editor, OECD secretariat). Production ONE MP likely has additional roles (delegation head, committee secretary, etc.) with distinct permissions. What is the full RBAC model?

### OQ-2: Existing APIs, authentication, and audit infrastructure
**Relevant phase**: Post-PoC
**Context**: The PoC uses simulated backends (shared SQLite layer). Production integration requires understanding what APIs exist, how authentication works (SSO, OAuth, etc.), and whether there's an existing audit infrastructure to plug into.

### OQ-3: Production data volumes
**Relevant phase**: Post-PoC
**Context**: PoC operates at demo scale (6-8 delegations, 30-50 delegates, 40-60 documents). What are real production volumes? This affects database choice, vector store scaling, and response latency.

### OQ-4: GDPR/compliance requirements for delegate personal data
**Relevant phase**: Post-PoC
**Context**: Delegate records contain personal data (name, email). What are the GDPR obligations? What data retention rules apply? Does the audit trail (which logs user actions and agent reasoning) raise additional compliance concerns?

### OQ-5: Full scope of document visibility rules
**Relevant phase**: Post-PoC
**Context**: The PoC uses three axes for document visibility (classification level, membership type, committee participation). The production system may have additional visibility rules (embargo dates, distribution lists, national-eyes-only markings, etc.).

### OQ-6: Mini-tier model sufficiency for KB-guided tool selection
**Relevant phase**: Phase 0 (Model Exploration)
**Context**: Adding an MCP KB round-trip increases pressure on model quality — the model must correctly decide *when* to query the KB, interpret confidence signals, and then select the right backend tool. Mini-tier models (`gpt-4o-mini`, `gpt-4.1-mini`) must be validated specifically on KB-guided tool selection, not just plain tool use.
**Update (2026-04-06)**: Phase 0a harness infrastructure is complete. Plain tool selection (without KB) is being evaluated first. KB-guided evaluation will be added once a base model is selected.

### OQ-7: Agent frontend technology choice ✓ Resolved (2026-05-01)
**Relevant phase**: Phase 3
**Context**: The brainstorming docs suggest Next.js + Vercel AI SDK for the agent frontend (streaming, tool call display). Is this confirmed, or should a simpler alternative (e.g., a terminal/CLI interface) suffice for the PoC demo?
**History**:
- Initial resolution (AG-UI + CopilotKit on Python, 2026-04-19) archived
  2026-04-28 under `docs/_archived/failed-attempt-2026-04/` after the Python
  AG-UI HITL contract proved fragile (multi-turn tool-call ordering,
  denied-approval orphans, V2Provider not rendering `function_approval_request`).
- Second resolution (CopilotKit React via AG-UI on C# / .NET server, 2026-04-29)
  superseded 2026-05-01 after Step B falsified the documented .NET AG-UI HITL
  contract — `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` 1.3.0-preview.260423.1
  has no approval-translation middleware; `MapAGUI` swallows
  `ToolApprovalRequestContent`. Live four-turn curl trace recorded in
  `docs/agent-stack-decision-2026-04-29.md` §9.
**Decision (2026-05-01)**: **Chainlit (C4 stack)** — Python `agent-framework`
agent fronted by Chainlit's WebSocket UI; HITL via
`@tool(approval_mode="always_require")` rendered through Chainlit's native
`cl.AskActionMessage` action UI; identity threaded via `cl.user_session`. No
AG-UI wire protocol, no CopilotKit. Validated by `spikes/c4_chainlit/`. Full
record: `docs/agent-stack-decision-2026-04-29.md` §9.4; DECISIONS entry
`[2026-05-01] Agent app stack reversal`. Phase 3 scaffold plan:
`plan/phase3-agent-app-scaffold-1.md`. Re-evaluation trigger for the C# path
documented in `[2026-05-01]` DECISIONS entry.

### OQ-8: Test data generation strategy ✓ Resolved (2026-04-12)
**Relevant phase**: Phase 1
**Context**: Test data must cover all demo scenarios (member + partner delegations, Framework Agreements, various meeting/document states, delegate login history). Manual crafting vs. scripted generation? What level of realism is needed for stakeholder demos?
**Decision**: Hardcoded Python in `shared/seed_data.py` (no Faker, no JSON fixtures) with domain-realistic content (OECD-flavored delegation names, real-ish committee names, document titles that sound like OECD output). One-liner placeholder summaries are acceptable — full briefing-language summaries are out of scope. See `docs/DECISIONS.md`.

### OQ-9: Delegation head approval workflow implementation ✓ Resolved (2026-05-01)
**Relevant phase**: Phase 2 (status flag) + Phase 4 (approver UX)
**Context**: Restricted DAR creation routes to "pending delegation head approval." How is this modeled in the PoC? A status flag only (no actual notification), or a minimal approval UI?
**Phase 2 decision (2026-04-19) — STILL VALID**: Status flag only —
`DocumentAccessRight.approval_status` is set (`PENDING_DELEGATION_HEAD`,
`PENDING_SECRETARIAT`, `AUTO_APPROVED`). No notification, no approval inbox, no
approver UI in the classical app. Phase 2 shipped this way and remains correct.
**Phase 4 history**:
- Initial agent-centric resolution (2026-04-24) archived under
  `docs/_archived/failed-attempt-2026-04/` 2026-04-28 — rested on Python AG-UI
  HITL contract that proved unusable.
- Second resolution (CopilotKit React route inside C# `agent_app/`,
  2026-04-29) superseded 2026-05-01 with the rest of the C# pivot reversal.
**Phase 4 decision (2026-05-01)**: **Approver UX hosted as a separate
Chainlit session / page inside the Python `agent_app/`** (UC3), distinct from
the UC2 wizard session. Served by ordinary `@tool`-decorated functions that
read/write `DocumentAccessRight.approval_status` against the shared SQLite
database. **Not** the in-session `@tool(approval_mode="always_require")`
mechanism — UC3 is an asynchronous queue, not an in-flight HITL handshake.
Sequencing: UC1 → UC2 → UC3 per `plan/phase3-agent-app-scaffold-1.md` §3.
Full record: `docs/agent-stack-decision-2026-04-29.md` §9.5; DECISIONS entry
`[2026-05-01] Agent app stack reversal`.
OQ-1 (full RBAC model) remains open.
