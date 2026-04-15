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

### OQ-7: Agent frontend technology choice
**Relevant phase**: Phase 3
**Context**: The brainstorming docs suggest Next.js + Vercel AI SDK for the agent frontend (streaming, tool call display). Is this confirmed, or should a simpler alternative (e.g., a terminal/CLI interface) suffice for the PoC demo?

### OQ-8: Test data generation strategy ✓ Resolved (2026-04-12)
**Relevant phase**: Phase 1
**Context**: Test data must cover all demo scenarios (member + partner delegations, Framework Agreements, various meeting/document states, delegate login history). Manual crafting vs. scripted generation? What level of realism is needed for stakeholder demos?
**Decision**: Hardcoded Python in `shared/seed_data.py` (no Faker, no JSON fixtures) with domain-realistic content (OECD-flavored delegation names, real-ish committee names, document titles that sound like OECD output). One-liner placeholder summaries are acceptable — full briefing-language summaries are out of scope. See `docs/DECISIONS.md`.

### OQ-9: Delegation head approval workflow implementation
**Relevant phase**: Phase 4
**Context**: Restricted DAR creation routes to "pending delegation head approval." How is this modeled in the PoC? A status flag only (no actual notification), or a minimal approval UI?
