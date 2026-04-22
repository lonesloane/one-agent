# PRD: Phase 1 — Shared Data Layer + Classical App (Read Flows)

## 1. Executive Summary

### Problem Statement

Phase 0 validated that `gpt-4.1-mini` can reliably select the right tools
for ONE MP domain tasks (100% across all evaluation criteria). Before
building the agent app, we need the foundation it will sit on: a shared
data layer (database, business rules, seed data) and a classical Flask
app that demonstrates the click-heavy status quo for read flows. The
classical app is a **contrast tool** — it makes the agent's value
self-evident in side-by-side demos.

### Proposed Solution

Build three deliverables that together form the foundation for all
subsequent phases:

1. **Shared data layer** (`shared/`) — SQLAlchemy models, business rule
   functions, and seed data covering all entities needed for read flows.
2. **Classical web app** (`classical_app/`) — Flask + Jinja2 + Bootstrap 5
   app with 6 read-only screens demonstrating Use Case 1 (meeting brief
   discovery).
3. **Initialized database** (`one_agent.db`) — SQLite database populated
   with seed data sufficient for a walkable UC1 demo.

### Success Criteria

- SC-1: All 6 read screens render correctly with seed data — no empty
  states, no broken links.
- SC-2: Document visibility is enforced — a delegate only sees documents
  at or below their DAR classification level for each committee.
- SC-3: User impersonation works — switching delegates changes what
  committees, meetings, and documents are visible.
- SC-4: A stakeholder can walk through the UC1 flow (Dashboard → My
  Committees → Committee Detail → Upcoming Meetings → Meeting Detail →
  Document Detail) in 6 screens / 5 clicks.
- SC-5: All unit tests pass (`pytest`) — models, business rules, seed
  data, and visibility logic are tested.
- SC-6: Seed data can be extended incrementally — Phase 2+ can add new
  delegations, delegates, and DARs without rebuilding the database from
  scratch.

---

## 2. User Experience & Functionality

### User Personas

**Delegate** (primary for Phase 1 read screens): An individual
representing their country or organization at OECD committees. Wants to
quickly find their next meeting, see what documents are on the agenda,
and check if anything changed since they last visited. In the classical
app, they must navigate 6 screens to get this information.

**Delegation editor** (introduced in Phase 2): Administrative user who
manages delegates within their delegation. Not directly relevant to
Phase 1 read screens but will consume the same shared data layer.

**Demo operator** (implicit): The person running the stakeholder demo.
Needs a way to switch which delegate they are impersonating to show
different data (member vs. partner, different committees, varying
document visibility).

### User Stories

**US-1: View my committees**
As a delegate, I want to see which OECD committees I participate in, so
that I can navigate to the right committee for meeting preparation.

*Acceptance criteria:*
- Dashboard shows a welcome message with the impersonated delegate's name
  and delegation
- "My Committees" screen lists only the committees the current delegate
  participates in (filtered via the delegate-committee M2M relationship)
- Each committee row shows the committee name and the date of the next
  upcoming meeting (if any)

**US-2: View upcoming meetings for a committee**
As a delegate, I want to see upcoming meetings for a committee I
participate in, so that I can plan my preparation.

*Acceptance criteria:*
- Committee detail screen shows committee name and description
- "Upcoming Meetings" screen lists meetings ordered by date (future
  meetings only)
- Each meeting row shows date, title, location, and agenda document count

**US-3: View meeting agenda documents**
As a delegate, I want to see the documents on a meeting's agenda, so
that I can prepare for the meeting.

*Acceptance criteria:*
- Meeting detail screen shows meeting title, date, location, and
  committee name
- Agenda documents are listed in agenda item order
- Each document row shows title, classification level, and last modified
  date
- Only documents the current delegate is allowed to see (per their DAR)
  are shown
- Documents the delegate cannot see are not shown at all (no "access
  denied" rows — they simply don't appear)

**US-4: View document detail**
As a delegate, I want to see the metadata of a specific document, so
that I can understand its context before reading it.

*Acceptance criteria:*
- Document detail screen shows title, classification level, committee,
  publication date, last modified date, and summary
- A "[Download PDF]" placeholder link is shown (no actual file — out of
  scope)
- The screen is only accessible if the delegate's DAR permits viewing
  documents at this classification level for this committee; otherwise
  return 403

**US-5: Switch impersonated delegate**
As a demo operator, I want to switch which delegate I am viewing the app
as, so that I can demonstrate different visibility scenarios.

*Acceptance criteria:*
- A delegate picker is available (e.g., dropdown in the navbar or a
  dedicated page)
- Selecting a different delegate updates the Flask session
- All subsequent screen renders reflect the newly selected delegate's
  committees, meetings, and document visibility
- The currently impersonated delegate's name and delegation are shown in
  the navbar

### Non-Goals

- **No proactive intelligence**: The dashboard deliberately shows no
  upcoming-meeting summary, no "new since last visit" markers, no
  highlighted changes. This is by design — the classical app is a
  contrast tool that demonstrates the absence of proactive features.
- **No write operations**: No delegate creation, no DAR creation, no
  form submissions. These are Phase 2.
- **No agent app**: No conversational interface, no tool calls, no
  streaming. These are Phase 3+.
- **No authentication/authorization**: The delegate picker is a demo
  convenience, not a security feature. No login form, no passwords, no
  RBAC enforcement beyond document visibility filtering.
- **No MCP knowledge base**: Business rules are Python functions in the
  shared layer, not MCP-exposed. MCP is Phase 5.
- **No custom CSS or frontend polish**: Bootstrap 5 via CDN is
  sufficient. The app should look functional, not beautiful.
- **No search or filtering beyond what the screens require**: No
  full-text search, no advanced document filtering.

---

## 3. Technical Specifications

### Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                Classical App (Phase 1)                │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Flask routes (classical_app/app.py)           │  │
│  │  6 read-only screens + delegate picker         │  │
│  │  Jinja2 templates + Bootstrap 5                │  │
│  └───────────────────────┬────────────────────────┘  │
│                          │                           │
│                          ▼                           │
│  ┌────────────────────────────────────────────────┐  │
│  │  Shared Data & Logic Layer (shared/)           │  │
│  │                                                │  │
│  │  database.py        SQLAlchemy models + enums  │  │
│  │  business_rules.py  Visibility, access level,  │  │
│  │                     approval routing           │  │
│  │  seed_data.py       Demo data population       │  │
│  └───────────────────────┬────────────────────────┘  │
│                          │                           │
│                          ▼                           │
│                   ┌──────────────┐                    │
│                   │  SQLite DB   │                    │
│                   │ one_agent.db │                    │
│                   └──────────────┘                    │
└──────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 3.1 Shared Data Layer (`shared/`)

**`shared/database.py`** — SQLAlchemy ORM models

All entity models as defined in the brainstorming docs:

| Model | Table | Key Columns |
|---|---|---|
| `Delegation` | `delegations` | `id` (PK, e.g. "FRA"), `name`, `membership_type` (member/partner) |
| `Committee` | `committees` | `id` (PK, e.g. "EDU"), `name`, `description` |
| `Delegate` | `delegates` | `id` (PK), `full_name`, `email`, `function`, `delegation_id` (FK), `accreditation_date`, `is_active`, `last_login` |
| `delegate_committees` | `delegate_committees` | M2M association: `delegate_id` ↔ `committee_id` |
| `FrameworkAgreement` | `framework_agreements` | `delegation_id` (FK), `committee_id` (FK), `start_date`, `end_date` |
| `Document` | `documents` | `id` (PK), `title`, `classification` (Public/General/Restricted/Confidential), `committee_id` (FK), `publication_date`, `last_modified`, `summary` |
| `DocumentAccessRight` | `document_access_rights` | `delegate_id` (FK), `committee_id` (FK), `classification_level`, `retroactive`, `approval_status`, `created_by` |
| `Meeting` | `meetings` | `id` (PK), `committee_id` (FK), `title`, `date`, `location` |
| `MeetingAgendaItem` | `meeting_agenda_items` | `meeting_id` (FK), `document_id` (FK), `item_order` |

Enums: `MembershipType`, `ClassificationLevel`, `ApprovalStatus`

Utility functions: `get_engine(db_path)`, `init_db(engine)`

**`shared/business_rules.py`** — Domain logic as Python functions

| Function | Purpose | Phase 1 Usage |
|---|---|---|
| `compute_default_access_level(membership_type, committee_id, framework_agreements)` | Determine default DAR classification for a delegate | Seed data generation |
| `determine_approval_route(classification_level, retroactive)` | Determine approval status for a new DAR | Seed data generation |
| `is_document_visible(delegate_id, document, db)` | Check if a delegate can see a specific document based on their DARs (only considers DARs with `approval_status` AUTO_APPROVED or APPROVED — pending DARs do not grant visibility) | Runtime — meeting agenda filtering, document detail access control |
| `get_visible_agenda_documents(delegate_id, meeting_id, db)` | Return only the agenda documents the delegate is allowed to see | Runtime — meeting detail screen |
| `get_new_documents_since(delegate_last_login, meeting_id, db)` | Return agenda docs added/modified since last login | Not used in classical app (by design); available for Phase 3 agent |

Document visibility rule: A delegate can see a document if they have an
approved DAR for the document's committee at a classification level ≥ the
document's classification. Classification hierarchy:
Public < General < Restricted < Confidential. A DAR at "Restricted" level
grants access to Public, General, and Restricted documents for that
committee.

**`shared/seed_data.py`** — Demo data population

The seed script must be **idempotent** (safe to re-run) and
**incremental** (Phase 2+ will add additional seed data for write-flow
scenarios without rebuilding existing records). Design: use
`merge`/upsert patterns keyed on entity IDs.

Minimum seed data for Phase 1 (UC1 read flows):

| Entity | Count | Coverage |
|---|---|---|
| Delegations | 4 | 2 member (e.g. France, Germany), 2 partner (e.g. Brazil, India) |
| Committees | 5 | Education Policy, Trade, Development Assistance, Environment Policy, Skills & Employment |
| Delegates | 8–10 | 2–3 per delegation, with varying committee participations |
| Framework Agreements | 1–2 | At least one partner delegation with a FA on one committee |
| Documents | 15–20 | Mix of Public, General, Restricted, Confidential across committees |
| DARs | ~20–30 | Pre-created for all seeded delegates (auto-approved General/Restricted for members; General for partners; Restricted where FA applies) |
| Meetings | 4–6 | At least one upcoming meeting per major committee; at least one past meeting |
| Agenda Items | 30–40 | 3–8 documents per meeting agenda |

The seed data must produce at least these demonstrable scenarios:

- A member delegate sees Restricted documents; a partner delegate on the
  same committee sees only General
- A partner delegate with a Framework Agreement sees Restricted documents
  on that committee
- Switching delegate shows different committee lists and different
  document visibility
- At least one meeting has documents the current delegate cannot see
  (to verify filtering works — the hidden documents simply don't appear)

#### 3.2 Classical Web App (`classical_app/`)

**Tech stack**: Flask, Jinja2, Bootstrap 5 (CDN), WTForms (for delegate
picker form), SQLAlchemy (via shared layer).

**Routes**:

| Route | Screen | Method |
|---|---|---|
| `GET /` | Dashboard | Welcome message, navigation links |
| `GET /committees` | My Committees | Filtered to current delegate's committees |
| `GET /committees/<id>` | Committee Detail | Committee name, description, links |
| `GET /committees/<id>/meetings` | Upcoming Meetings | Future meetings for this committee |
| `GET /meetings/<id>` | Meeting Detail + Agenda | Meeting info + visible agenda documents |
| `GET /documents/<id>` | Document Detail | Document metadata (403 if not visible) |
| `GET /switch-delegate` | Delegate Picker | List all delegates, select one |
| `POST /switch-delegate` | (redirect) | Set session, redirect to dashboard |

**Template layout**: Base template with Bootstrap 5 navbar showing:
- App name ("ONE MP — Delegation Management Portal")
- Current delegate name + delegation name
- "Switch Delegate" link

**Session management**: Flask session stores `delegate_id` of the
currently impersonated delegate. All routes read this to filter data.
If no delegate is selected, redirect to the delegate picker.

#### 3.3 Database Initialization

A `scripts/init_db.py` script (or `python -m shared.seed_data`) that:
1. Creates all tables via `Base.metadata.create_all(engine)`
2. Populates seed data via `shared/seed_data.py`
3. Can be re-run safely (idempotent)

### Integration Points

- **SQLite database** (`one_agent.db`): Shared between classical app
  (Phase 1–2), agent tools (Phase 3–4), and MCP KB server (Phase 5).
  Single file, zero infrastructure.
- **Business rules** (`shared/business_rules.py`): Called by Flask routes
  (Phase 1–2), agent tool implementations (Phase 3–4), and MCP server
  (Phase 5). Single source of truth.

### Dependencies (additions to `pyproject.toml`)

| Package | Purpose |
|---|---|
| `sqlalchemy>=2.0` | ORM for shared data layer |
| `flask>=3.0` | Classical web app framework |
| `flask-wtf>=1.2` | Form handling (delegate picker, future write forms) |

The `[tool.setuptools] packages` list must be updated to include
`shared` and `classical_app` alongside `eval`.

### Security & Privacy

- No real authentication — delegate picker is a demo convenience
- No personal data beyond fictional names and emails in seed data
- Document visibility enforcement is functional (filters query results),
  not a security boundary
- No external API calls — all data is local SQLite

---

## 4. Risks & Roadmap

### Phased Rollout

**Phase 1 MVP (this PRD):**
- Shared data layer with all models, enums, and business rule functions
- Seed data for read-flow demo scenarios
- 6 read-only classical app screens + delegate picker
- Document visibility enforcement
- Unit tests for models, business rules, and visibility logic

**Phase 2 (next — classical app write flows):**
- 8 write screens for UC2 (delegate creation wizard)
- Additional seed data for write-flow scenarios
- WTForms for multi-step delegate creation
- Business rule application in the create flow

**Phase 3+ (agent app):**
- Agent tools as thin wrappers over the shared data layer
- System prompt encoding domain rules
- Streaming UI for real-time feedback

### Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Seed data doesn't cover edge cases needed for later phases | Delays Phase 2+ | Design seed_data.py as incremental — Phase 2 adds data, doesn't rebuild |
| Document visibility logic is more complex than anticipated | Scope creep in Phase 1 | Implement the three-axis rule (classification level, membership type, committee) only — defer additional axes (OQ-5) to post-PoC |
| SQLAlchemy model changes required in later phases | Migration overhead | Use Alembic for schema migrations if needed; Phase 1 models are designed from the complete entity list in brainstorming docs |
| Flask session-based impersonation doesn't scale to concurrent demo users | Demo friction | Acceptable for PoC — single-user demo. If needed, add query-param override |

---

## 5. Reference: Classical App Screen Flow (UC1)

For the complete screen-by-screen wireframes, see
[`docs/brainstorming/ONE-Agent-PoC-dual-demo.md`](brainstorming/ONE-Agent-PoC-dual-demo.md),
section "Screen Flow: Use Case 1 — Meeting Brief (6 screens)."

Summary:

```
Dashboard → My Committees → Committee Detail → Upcoming Meetings
    → Meeting Detail + Agenda → Document Detail
```

**6 screens, 5 clicks, zero proactive intelligence.** The delegate must
navigate to the information themselves. No "what's new" indicators, no
upcoming-meeting summary on the dashboard, no highlighted changes. This
is the deliberate contrast with the agent app (Phase 3).
