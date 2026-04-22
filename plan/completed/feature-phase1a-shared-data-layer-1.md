---
goal: "Phase 1A: Shared Data Layer — SQLAlchemy Models, Business Rules, Seed Data, DB Init"
version: 1.0
date_created: 2026-04-11
owner: stephane
status: 'Completed'
tags: [feature, data-layer, phase-1]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Build the shared data layer (`shared/`) that underpins both the classical
Flask app (Phase 1B) and the agent app (Phase 3+). Deliverables:
SQLAlchemy ORM models with enums, business rule functions (visibility,
access level, approval routing), idempotent seed data covering all UC1
read-flow demo scenarios, and a DB init script that produces a ready-to-use
`one_agent.db`.

This plan deliberately excludes the classical Flask app — that is Plan B
(`feature-phase1b-classical-app`). The shared layer must be fully tested
and functional before the Flask routes can consume it.

## 1. Requirements & Constraints

- **REQ-001**: All entity models defined in the PRD Section 3.1
  (`Delegation`, `Committee`, `Delegate`, `delegate_committees`,
  `FrameworkAgreement`, `Document`, `DocumentAccessRight`, `Meeting`,
  `MeetingAgendaItem`) must be implemented as SQLAlchemy ORM classes.
- **REQ-002**: Three enums — `MembershipType`, `ClassificationLevel`,
  `ApprovalStatus` — must be implemented. `ClassificationLevel` must
  support ordered comparison (`Public < General < Restricted <
  Confidential`) for visibility checks.
- **REQ-003**: Five business rule functions as specified in PRD Section 3.1
  (`compute_default_access_level`, `determine_approval_route`,
  `is_document_visible`, `get_visible_agenda_documents`,
  `get_new_documents_since`).
- **REQ-004**: `is_document_visible` must only consider DARs with
  `approval_status` in (`AUTO_APPROVED`, `APPROVED`) — pending DARs do
  not grant visibility.
- **REQ-005**: Seed data must produce at least these demonstrable
  scenarios:
  - A member delegate sees Restricted documents; a partner delegate on the
    same committee sees only General.
  - A partner delegate with a Framework Agreement sees Restricted documents
    on that committee.
  - Switching delegate shows different committee lists and different
    document visibility.
  - At least one meeting has documents the current delegate cannot see
    (they simply don't appear).
- **REQ-006**: Seed data script must be idempotent (safe to re-run) and
  incremental (Phase 2+ adds data without rebuilding).
- **REQ-007**: Minimum entity counts — 4 delegations, 5 committees, 8–10
  delegates, 1–2 framework agreements, 15–20 documents, ~20–30 DARs, 4–6
  meetings, 30–40 agenda items.
- **SEC-001**: No real personal data — use fictional names and emails.
- **CON-001**: SQLite only — `one_agent.db`, single file, zero
  infrastructure.
- **CON-002**: Only `sqlalchemy>=2.0` added as a dependency in this plan.
  Flask dependencies belong to Plan B.
- **CON-003**: Python 3.11+ compatibility. Use `dict` not `typing.Dict`,
  `list` not `typing.List`, etc.
- **GUD-001**: Follow PEP 8, Google-style docstrings, type hints on all
  public functions per `CLAUDE.md`.
- **GUD-002**: No file over 500 lines. If `seed_data.py` approaches this,
  split entity-creation helpers into a submodule.
- **PAT-001**: Use `session.merge()` for string-PK entities (idempotent
  upsert). For auto-increment-PK entities (`FrameworkAgreement`,
  `DocumentAccessRight`, `MeetingAgendaItem`), use check-then-insert or
  assign explicit IDs to support re-runnability.
- **PAT-002**: Tests use in-memory SQLite (`sqlite:///:memory:`) with real
  schema creation — no mocks for DB-dependent logic.

## 2. Implementation Steps

### Phase 1: Project Scaffolding

- GOAL-001: Create the `shared` package, update project config, prepare
  directories.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `shared/__init__.py` (empty or with package docstring) | ✅ | 2026-04-12 |
| TASK-002 | Create `scripts/` directory (for `init_db.py`) | ✅ | 2026-04-12 |
| TASK-003 | Update `pyproject.toml`: add `sqlalchemy>=2.0` to `dependencies`; add `"shared"` to `[tool.setuptools] packages` list | ✅ | 2026-04-12 |
| TASK-004 | Update `.gitignore`: add `*.db` to exclude generated SQLite databases | ✅ | 2026-04-12 |
| TASK-005 | Run `pip install -e ".[dev]"` to install new dependency | ✅ | 2026-04-12 |

### Phase 2: SQLAlchemy Models & Enums

- GOAL-002: Implement all ORM models and enums in `shared/database.py`,
  following the schema defined in the brainstorming doc
  (`docs/brainstorming/ONE-Agent-PoC-dual-demo.md` lines 76–236) and
  refined in the PRD.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Implement `MembershipType` enum (`MEMBER`, `PARTNER`) | ✅ | 2026-04-12 |
| TASK-007 | Implement `ClassificationLevel` enum (`PUBLIC`, `GENERAL`, `RESTRICTED`, `CONFIDENTIAL`) with an ordering mechanism — either an `_order` dict or a custom `__ge__`/`__le__` on a wrapper, so that `RESTRICTED >= GENERAL` evaluates correctly. This is critical for `is_document_visible`. | ✅ | 2026-04-12 |
| TASK-008 | Implement `ApprovalStatus` enum (`AUTO_APPROVED`, `PENDING_DELEGATION_HEAD`, `PENDING_SECRETARIAT`, `APPROVED`, `REJECTED`) | ✅ | 2026-04-12 |
| TASK-009 | Implement `Delegation` model — PK `id` (str, e.g. "FRA"), `name`, `membership_type`, relationships to `delegates` and `framework_agreements` | ✅ | 2026-04-12 |
| TASK-010 | Implement `Committee` model — PK `id` (str, e.g. "EDU"), `name`, `description` | ✅ | 2026-04-12 |
| TASK-011 | Implement `delegate_committees` M2M association table (`delegate_id` FK → `delegates.id`, `committee_id` FK → `committees.id`) | ✅ | 2026-04-12 |
| TASK-012 | Implement `Delegate` model — PK `id` (str, e.g. "DEL-2026-0001"), `full_name`, `email`, `function`, `title` (optional), `delegation_id` (FK), `accreditation_date`, `is_active`, `last_login`, relationships to `delegation`, `committees` (via M2M), `document_access_rights` | ✅ | 2026-04-12 |
| TASK-013 | Implement `FrameworkAgreement` model — PK `id` (int, autoincrement), `delegation_id` (FK), `committee_id` (FK), `start_date`, `end_date` (nullable = ongoing), relationships | ✅ | 2026-04-12 |
| TASK-014 | Implement `Document` model — PK `id` (str, e.g. "DOC-2026-0042"), `title`, `classification` (ClassificationLevel enum), `committee_id` (FK), `publication_date`, `last_modified`, `summary`, relationship to `committee` | ✅ | 2026-04-12 |
| TASK-015 | Implement `DocumentAccessRight` model — PK `id` (int, autoincrement), `delegate_id` (FK), `committee_id` (FK), `classification_level` (ClassificationLevel enum), `retroactive`, `approval_status` (ApprovalStatus enum), `created_at`, `created_by`, relationships | ✅ | 2026-04-12 |
| TASK-016 | Implement `Meeting` model — PK `id` (str, e.g. "MTG-EDU-2026-04"), `committee_id` (FK), `title`, `date` (DateTime), `location`, relationships to `committee` and `agenda_items` (ordered by `item_order`) | ✅ | 2026-04-12 |
| TASK-017 | Implement `MeetingAgendaItem` model — PK `id` (int, autoincrement), `meeting_id` (FK), `document_id` (FK), `item_order`, relationships | ✅ | 2026-04-12 |
| TASK-018 | Implement `get_engine(db_path)` and `init_db(engine)` utility functions | ✅ | 2026-04-12 |

### Phase 3: Business Rules

- GOAL-003: Implement the five business rule functions in
  `shared/business_rules.py`. These are the single source of truth for
  domain logic consumed by the classical app, agent tools, and MCP server.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-019 | Implement `compute_default_access_level(membership_type, committee_id, framework_agreements) -> ClassificationLevel`. Rules: member → Restricted; partner → General; partner + active FA on committee → Restricted. | ✅ | 2026-04-12 |
| TASK-020 | Implement `determine_approval_route(classification_level, retroactive) -> ApprovalStatus`. Rules: retroactive → PENDING_SECRETARIAT; Confidential → PENDING_SECRETARIAT; Restricted → PENDING_DELEGATION_HEAD; General/Public → AUTO_APPROVED. | ✅ | 2026-04-12 |
| TASK-021 | Implement `is_document_visible(delegate_id, document, session) -> bool`. Logic: find DARs for delegate on document's committee where `approval_status` in (AUTO_APPROVED, APPROVED), check if DAR's `classification_level >= document.classification` using the ordering from TASK-007. | ✅ | 2026-04-12 |
| TASK-022 | Implement `get_visible_agenda_documents(delegate_id, meeting_id, session) -> list[Document]`. Query `meeting_agenda_items` for the meeting, join to `documents`, filter through `is_document_visible`, return in `item_order`. | ✅ | 2026-04-12 |
| TASK-023 | Implement `get_new_documents_since(delegate_last_login, meeting_id, session) -> list[Document]`. Return agenda docs where `last_modified > delegate_last_login`. Return empty list if `delegate_last_login is None`. Not used by classical app — available for Phase 3 agent. | ✅ | 2026-04-12 |

### Phase 4: Seed Data Design & Implementation

- GOAL-004: Design the seed data matrix to cover all PRD demo scenarios,
  then implement `shared/seed_data.py` and `scripts/init_db.py`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-024 | **Design seed data matrix** (before writing code). Define the exact entities and their relationships in a comment block or docstring at the top of `seed_data.py`. Must cover: (a) 2 member delegations (France "FRA", Germany "DEU") + 2 partner (Brazil "BRA", India "IND"); (b) 5 committees (EDU, TRADE, DAC, ENV, SKILLS); (c) 8–10 delegates with varying committee participations; (d) 1–2 framework agreements (e.g. Brazil on EDU); (e) 15–20 documents across classification levels and committees; (f) ~20–30 DARs using `compute_default_access_level` + `determine_approval_route`; (g) 4–6 meetings (mix of upcoming and past); (h) 30–40 agenda items. Verify the matrix produces all REQ-005 scenarios. | ✅ | 2026-04-12 |
| TASK-025 | Implement `seed_delegations(session)` — create 4 delegations. Use `session.merge()` for idempotency. | ✅ | 2026-04-12 |
| TASK-026 | Implement `seed_committees(session)` — create 5 committees. Use `session.merge()`. | ✅ | 2026-04-12 |
| TASK-027 | Implement `seed_delegates(session)` — create 8–10 delegates with committee associations. Use `session.merge()` for delegates; handle M2M associations carefully (clear and re-add on re-run, or check before insert). | ✅ | 2026-04-12 |
| TASK-028 | Implement `seed_framework_agreements(session)` — create 1–2 FAs. For autoincrement PKs, assign explicit IDs and use check-then-insert or `session.merge()` with explicit PK. | ✅ | 2026-04-12 |
| TASK-029 | Implement `seed_documents(session)` — create 15–20 documents. Use `session.merge()`. Ensure mix: Public, General, Restricted, Confidential across multiple committees. | ✅ | 2026-04-12 |
| TASK-030 | Implement `seed_document_access_rights(session)` — create ~20–30 DARs using `compute_default_access_level` and `determine_approval_route` from business rules. Use explicit IDs for idempotency. | ✅ | 2026-04-12 |
| TASK-031 | Implement `seed_meetings(session)` — create 4–6 meetings. Use `session.merge()`. At least 1 upcoming per major committee, at least 1 past. Use future dates relative to a fixed reference (e.g. 2026-04-18 onwards for upcoming). | ✅ | 2026-04-12 |
| TASK-032 | Implement `seed_agenda_items(session)` — create 30–40 agenda items linking documents to meetings. Use explicit IDs for idempotency. 3–8 documents per meeting agenda. Include Confidential docs on agendas (they'll be filtered by visibility at runtime). | ✅ | 2026-04-12 |
| TASK-033 | Implement `seed_all(session)` — orchestrator calling all seed functions in FK-respecting order (delegations → committees → delegates → FAs → documents → DARs → meetings → agenda items). | ✅ | 2026-04-12 |
| TASK-034 | Implement `scripts/init_db.py`: create engine, call `init_db(engine)`, open session, call `seed_all(session)`, commit. Also support `python -m shared.seed_data` as an alternative entry point (add `if __name__ == "__main__"` block to `seed_data.py`). | ✅ | 2026-04-12 |

### Phase 5: Unit Tests

- GOAL-005: Comprehensive test coverage for models, business rules,
  visibility logic, and seed data. All tests use in-memory SQLite.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-035 | Create `tests/shared/__init__.py` and a shared test fixture (`conftest.py`) providing an in-memory SQLAlchemy session with `init_db()` already called. | ✅ | 2026-04-12 |
| TASK-036 | `tests/shared/test_database.py` — test model creation and relationships: create a Delegation + Delegate, verify FK relationship; create Committee + Document, verify FK; test M2M delegate ↔ committees; test enum column storage and retrieval. | ✅ | 2026-04-12 |
| TASK-037 | `tests/shared/test_business_rules.py` — test `compute_default_access_level`: member → Restricted; partner → General; partner + active FA → Restricted; partner + expired FA → General. | ✅ | 2026-04-12 |
| TASK-038 | `tests/shared/test_business_rules.py` — test `determine_approval_route`: General → AUTO_APPROVED; Restricted → PENDING_DELEGATION_HEAD; Confidential → PENDING_SECRETARIAT; retroactive General → PENDING_SECRETARIAT. | ✅ | 2026-04-12 |
| TASK-039 | `tests/shared/test_business_rules.py` — test `is_document_visible`: delegate with Restricted DAR sees Public, General, Restricted docs; does NOT see Confidential. Delegate with General DAR sees Public, General; does NOT see Restricted. Delegate with PENDING DAR at Restricted level does NOT see Restricted docs (REQ-004). Delegate with no DAR for that committee sees nothing. | ✅ | 2026-04-12 |
| TASK-040 | `tests/shared/test_business_rules.py` — test `get_visible_agenda_documents`: create a meeting with 4 docs (Public, General, Restricted, Confidential), verify a delegate with Restricted DAR sees 3, a delegate with General DAR sees 2, results are in `item_order`. | ✅ | 2026-04-12 |
| TASK-041 | `tests/shared/test_business_rules.py` — test `get_new_documents_since`: docs modified after last_login are returned; docs modified before are not; `None` last_login returns empty list. | ✅ | 2026-04-12 |
| TASK-042 | `tests/shared/test_seed_data.py` — test seed data completeness: run `seed_all()`, verify entity counts match REQ-007 minimums. | ✅ | 2026-04-12 |
| TASK-043 | `tests/shared/test_seed_data.py` — test idempotency: run `seed_all()` twice on the same session, verify no duplicate rows, no integrity errors. | ✅ | 2026-04-12 |
| TASK-044 | `tests/shared/test_seed_data.py` — test demo scenarios (REQ-005): after seeding, verify that `get_visible_agenda_documents` returns different document sets for a member delegate vs. a partner delegate on the same committee. | ✅ | 2026-04-12 |
| TASK-045 | Run `pytest` — all tests pass. Run `python scripts/init_db.py` — `one_agent.db` created successfully with expected row counts. | ✅ | 2026-04-12 |

## 3. Alternatives

- **ALT-001**: Use Alembic for schema migrations from the start. Rejected:
  adds complexity to PoC. Phase 1 has no existing schema to migrate from.
  If model changes are needed in later phases, Alembic can be added then.
- **ALT-002**: Use dataclasses or Pydantic models instead of SQLAlchemy
  ORM. Rejected: SQLAlchemy provides the ORM layer needed for direct DB
  queries in Flask routes and agent tools.
- **ALT-003**: Use a single monolithic seed_data function. Rejected:
  splitting by entity type supports incremental extension (Phase 2 can
  call additional seed functions) and easier testing.
- **ALT-004**: Store classification level ordering in the database.
  Rejected: classification hierarchy is a fixed business rule, not data.
  A Python-level ordering mechanism is simpler and more testable.

## 4. Dependencies

- **DEP-001**: `sqlalchemy>=2.0` — ORM for shared data layer (new
  dependency to add to `pyproject.toml`)
- **DEP-002**: `pytest>=8.0` — already in dev dependencies
- **DEP-003**: Python `enum`, `datetime`, `pathlib` — stdlib, no install
  needed

## 5. Files

- **FILE-001**: `shared/__init__.py` — package init (new)
- **FILE-002**: `shared/database.py` — SQLAlchemy models, enums, engine
  setup (new, ~200–300 lines)
- **FILE-003**: `shared/business_rules.py` — domain logic functions (new,
  ~100–150 lines)
- **FILE-004**: `shared/seed_data.py` — idempotent seed data population
  (new, ~300–400 lines)
- **FILE-005**: `scripts/init_db.py` — DB initialization entry point (new,
  ~20–30 lines)
- **FILE-006**: `tests/shared/__init__.py` — test package init (new)
- **FILE-007**: `tests/shared/conftest.py` — shared test fixtures (new)
- **FILE-008**: `tests/shared/test_database.py` — model tests (new)
- **FILE-009**: `tests/shared/test_business_rules.py` — business rule
  tests (new)
- **FILE-010**: `tests/shared/test_seed_data.py` — seed data tests (new)
- **FILE-011**: `pyproject.toml` — updated dependencies and packages
  (existing)
- **FILE-012**: `.gitignore` — add `*.db` pattern (existing)

## 6. Testing

- **TEST-001**: Model CRUD — create each entity type, read it back, verify
  all columns and relationships (in-memory SQLite).
- **TEST-002**: Enum storage — verify enum values round-trip through the
  DB correctly.
- **TEST-003**: Classification ordering — verify
  `CONFIDENTIAL > RESTRICTED > GENERAL > PUBLIC` comparison works.
- **TEST-004**: `compute_default_access_level` — 4 cases (member,
  partner, partner+FA, partner+expired FA).
- **TEST-005**: `determine_approval_route` — 4 cases (General, Restricted,
  Confidential, retroactive).
- **TEST-006**: `is_document_visible` — 5 cases (Restricted DAR sees
  lower levels, doesn't see higher; General DAR sees lower, doesn't see
  Restricted; pending DAR grants no access; no DAR grants no access;
  APPROVED DAR grants access same as AUTO_APPROVED).
- **TEST-007**: `get_visible_agenda_documents` — filtering by visibility,
  ordering by `item_order`.
- **TEST-008**: `get_new_documents_since` — modified-after filter, null
  last_login edge case.
- **TEST-009**: Seed data completeness — entity count verification.
- **TEST-010**: Seed data idempotency — double-run produces no errors
  and no duplicates.
- **TEST-011**: Seed data scenario verification — member vs. partner
  visibility on same committee.

## 7. Risks & Assumptions

- **RISK-001**: Seed data doesn't cover edge cases needed for Phase 2
  write flows. Mitigation: `seed_data.py` is designed as incremental —
  Phase 2 adds data, doesn't rebuild. The `seed_all()` function can be
  extended with new calls.
- **RISK-002**: `ClassificationLevel` ordering mechanism breaks if a new
  level is added. Mitigation: the ordering is defined once in
  `database.py` and tested; adding a level requires updating both the
  enum and the ordering.
- **RISK-003**: Auto-increment PK entities cause duplicate rows on re-run.
  Mitigation: use explicit IDs or check-then-insert pattern per PAT-001.
- **ASSUMPTION-001**: All seed data dates can use fixed values (not
  relative to `date.today()`). Meetings dated 2026-04-18 onwards are
  "upcoming" for demo purposes. If the demo runs after these dates,
  seed data may need updating — acceptable for a PoC.
- **ASSUMPTION-002**: The schema from
  `docs/brainstorming/ONE-Agent-PoC-dual-demo.md` is authoritative.
  The PRD references it and the models match.

## 8. Related Specifications / Further Reading

- [PRD: Phase 1 — Shared Data Layer + Classical App (Read Flows)](../docs/prd-phase1-shared-layer-and-classical-read.md)
- [Brainstorming: Dual-Demo Architecture](../docs/brainstorming/ONE-Agent-PoC-dual-demo.md) — canonical schema (lines 76–236) and business rules (lines 238–306)
- [Brainstorming: ONE-Agent Concept](../docs/brainstorming/ONE-Agent-concept.md)
- [Backlog](../docs/BACKLOG.md) — Phase 1 items
