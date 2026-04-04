# ONE Agent PoC: Dual-Demo Architecture — Classical Baseline + Agent

> The PoC ships two applications that share the same database, the same business
> rules, and the same test data — but deliver radically different user experiences.
> The **classical app** (Flask + forms) demonstrates the multi-screen, click-heavy
> reality of the current ONE MP paradigm. The **agent app** (Microsoft Agent Framework)
> demonstrates the conversational, proactive alternative. Side-by-side, they make
> the case without a slide deck.
>
> Companion documents:
> - [`ONE-Agent-concept.md`](ONE-Agent-concept.md) — concept analysis, architecture, PoC strategy
> - [`ONE-Agent-MCP-knowledge-base.md`](ONE-Agent-MCP-knowledge-base.md) — MCP-based business knowledge base

---

## 1. Purpose & Demo Strategy

The classical app is not an end in itself — it is a **contrast tool**. Its purpose
is to make the agent's value self-evident by showing the same tasks completed in
both paradigms:

| Dimension | Classical App | Agent App |
|---|---|---|
| Meeting brief | 6 screens, user-initiated | 0 screens, agent-initiated greeting |
| Delegate creation + DAR | 8 screens, 4 form steps | ~3 conversational turns |
| Business rule application | User must know and apply rules | Agent reasons through rules |
| Error recovery | Back button, re-enter fields | Agent corrects in conversation |
| New document discovery | User navigates and scans | Agent highlights proactively |

**Demo format**: open the classical app in one browser tab, the agent app in
another. Both point to the same SQLite database. Walk through the same task in
both. Count the clicks vs conversational turns.

---

## 2. Shared Data Layer

### Design Principle

The database and business logic live in a shared Python package (`shared/`).
Three consumers sit on top of it, all thin wrappers:

```
┌─────────────────────────────────────────────────────────┐
│                    Consumers                             │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ Classical App │  │ Agent Tools  │  │ MCP KB Server │ │
│  │ Flask routes  │  │ @tool funcs  │  │ mcp SDK tools │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘ │
│         │                 │                  │          │
│         ▼                 ▼                  ▼          │
│  ┌─────────────────────────────────────────────────┐    │
│  │            Shared Data & Logic Layer             │    │
│  │                                                 │    │
│  │  SQLAlchemy models    Business rule functions    │    │
│  │  (database.py)        (business_rules.py)       │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         │                               │
│                         ▼                               │
│                  ┌──────────────┐                        │
│                  │  SQLite DB   │                        │
│                  │ one_agent.db │                        │
│                  └──────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

This architecture ensures:
- **Data consistency**: all three consumers see and modify the same data
- **Rule consistency**: business logic is defined once, not duplicated across apps
- **MCP readiness**: the MCP layer can be added on top of the shared layer at any point without restructuring

### Database Schema

```python
# shared/database.py
import enum
from datetime import date, datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, Date, DateTime,
    ForeignKey, Text, Table, Enum, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Session

class Base(DeclarativeBase):
    pass


# --- Enums ---

class MembershipType(enum.Enum):
    MEMBER = "member"
    PARTNER = "partner"

class ClassificationLevel(enum.Enum):
    PUBLIC = "Public"
    GENERAL = "General"
    RESTRICTED = "Restricted"
    CONFIDENTIAL = "Confidential"

class ApprovalStatus(enum.Enum):
    AUTO_APPROVED = "auto_approved"
    PENDING_DELEGATION_HEAD = "pending_delegation_head"
    PENDING_SECRETARIAT = "pending_secretariat"
    APPROVED = "approved"
    REJECTED = "rejected"


# --- Core entities ---

class Delegation(Base):
    __tablename__ = "delegations"

    id = Column(String, primary_key=True)                    # "FRA", "BRA", "IND"
    name = Column(String, nullable=False)                     # "France", "Brazil"
    membership_type = Column(Enum(MembershipType), nullable=False)

    delegates = relationship("Delegate", back_populates="delegation")
    framework_agreements = relationship("FrameworkAgreement", back_populates="delegation")


class Committee(Base):
    __tablename__ = "committees"

    id = Column(String, primary_key=True)                    # "EDU", "TRADE", "DAC"
    name = Column(String, nullable=False)                     # "Education Policy Committee"
    description = Column(Text)


# Association: delegates ↔ committees (many-to-many)
delegate_committees = Table(
    "delegate_committees", Base.metadata,
    Column("delegate_id", String, ForeignKey("delegates.id"), primary_key=True),
    Column("committee_id", String, ForeignKey("committees.id"), primary_key=True),
)


class Delegate(Base):
    __tablename__ = "delegates"

    id = Column(String, primary_key=True)                    # "DEL-2026-0001"
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    function = Column(String, nullable=False)                 # "Education Policy Advisor"
    title = Column(String)                                    # optional honorific/job title
    delegation_id = Column(String, ForeignKey("delegations.id"), nullable=False)
    accreditation_date = Column(Date, default=date.today)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)

    delegation = relationship("Delegation", back_populates="delegates")
    committees = relationship("Committee", secondary=delegate_committees)
    document_access_rights = relationship("DocumentAccessRight", back_populates="delegate")


class FrameworkAgreement(Base):
    """A partner delegation may have Framework Agreements that grant elevated
    document access for specific committees."""
    __tablename__ = "framework_agreements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delegation_id = Column(String, ForeignKey("delegations.id"), nullable=False)
    committee_id = Column(String, ForeignKey("committees.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)                                   # null = ongoing

    delegation = relationship("Delegation", back_populates="framework_agreements")
    committee = relationship("Committee")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)                    # "DOC-2026-0042"
    title = Column(String, nullable=False)
    classification = Column(Enum(ClassificationLevel), nullable=False)
    committee_id = Column(String, ForeignKey("committees.id"), nullable=False)
    publication_date = Column(Date)
    last_modified = Column(DateTime)
    summary = Column(Text)

    committee = relationship("Committee")


class DocumentAccessRight(Base):
    """What classification level a delegate can see, scoped per committee."""
    __tablename__ = "document_access_rights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delegate_id = Column(String, ForeignKey("delegates.id"), nullable=False)
    committee_id = Column(String, ForeignKey("committees.id"), nullable=False)
    classification_level = Column(Enum(ClassificationLevel), nullable=False)
    retroactive = Column(Boolean, default=False)
    approval_status = Column(Enum(ApprovalStatus), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(String)                               # user who initiated

    delegate = relationship("Delegate", back_populates="document_access_rights")
    committee = relationship("Committee")


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String, primary_key=True)                    # "MTG-EDU-2026-04"
    committee_id = Column(String, ForeignKey("committees.id"), nullable=False)
    title = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    location = Column(String)

    committee = relationship("Committee")
    agenda_items = relationship("MeetingAgendaItem", back_populates="meeting",
                                order_by="MeetingAgendaItem.item_order")


class MeetingAgendaItem(Base):
    """Links documents to a meeting agenda, with ordering."""
    __tablename__ = "meeting_agenda_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    item_order = Column(Integer, nullable=False)

    meeting = relationship("Meeting", back_populates="agenda_items")
    document = relationship("Document")


# --- Engine setup ---

def get_engine(db_path: str = "one_agent.db"):
    return create_engine(f"sqlite:///{db_path}", echo=False)

def init_db(engine):
    Base.metadata.create_all(engine)
```

### Business Rules Layer

Business rules are Python functions, not embedded in templates or prompts.
All three consumers call the same functions:

```python
# shared/business_rules.py
from shared.database import (
    MembershipType, ClassificationLevel, ApprovalStatus,
    Delegation, FrameworkAgreement, Session,
)


def compute_default_access_level(
    membership_type: MembershipType,
    committee_id: str,
    framework_agreements: list[FrameworkAgreement],
) -> ClassificationLevel:
    """Determine the default document access level for a delegate.

    Rules:
    - Member delegation → Restricted (includes General)
    - Partner delegation → General only
    - Partner + Framework Agreement covering this committee → Restricted
    """
    if membership_type == MembershipType.MEMBER:
        return ClassificationLevel.RESTRICTED

    # Partner: check for Framework Agreement covering this committee
    for fa in framework_agreements:
        if fa.committee_id == committee_id and (fa.end_date is None or fa.end_date >= date.today()):
            return ClassificationLevel.RESTRICTED

    return ClassificationLevel.GENERAL


def determine_approval_route(
    classification_level: ClassificationLevel,
    retroactive: bool,
) -> ApprovalStatus:
    """Determine the approval status for a new Document Access Right.

    Rules:
    - General → auto-approved
    - Restricted → pending delegation head approval
    - Confidential → pending OECD secretariat approval
    - Retroactive access → pending secretariat approval (regardless of level)
    """
    if retroactive:
        return ApprovalStatus.PENDING_SECRETARIAT
    if classification_level == ClassificationLevel.CONFIDENTIAL:
        return ApprovalStatus.PENDING_SECRETARIAT
    if classification_level == ClassificationLevel.RESTRICTED:
        return ApprovalStatus.PENDING_DELEGATION_HEAD
    return ApprovalStatus.AUTO_APPROVED


def get_new_documents_since(
    delegate_last_login: datetime | None,
    meeting_id: str,
    db: Session,
) -> list[Document]:
    """Return agenda documents added or modified since the delegate's last login."""
    if delegate_last_login is None:
        return []  # first login — everything is "new"
    # ... query meeting_agenda_items joined with documents
    # ... filter documents.last_modified > delegate_last_login
    pass
```

---

## 3. Classical Web Application

### Tech Stack

| Component | Choice | Rationale |
|---|---|---|
| Framework | Flask | Minimal boilerplate for form-based apps |
| Templates | Jinja2 | Built into Flask, native HTML form rendering |
| CSS | Bootstrap 5 (CDN) | Looks like a real app with zero custom CSS |
| ORM | SQLAlchemy (shared) | Same models the agent uses |
| Database | SQLite (shared) | `one_agent.db` — single file, zero infrastructure |
| Forms | WTForms + Flask-WTF | Declarative form classes with validation |

Total additional dependencies beyond shared layer: `flask`, `flask-wtf`.

### Navigation Structure

```
┌─────────────────────────────────────────────────┐
│  ONE MP — Delegation Management Portal          │
├─────────────────────────────────────────────────┤
│  Dashboard                                      │
│  ├── Delegations                                │
│  │   ├── [Delegation Detail]                    │
│  │   │   ├── Delegates List                     │
│  │   │   │   ├── [Add Delegate — Step 1/4]      │
│  │   │   │   ├── [Add Delegate — Step 2/4]      │
│  │   │   │   ├── [Add Delegate — Step 3/4]      │
│  │   │   │   ├── [Add Delegate — Review]        │
│  │   │   │   └── [Confirmation]                 │
│  │   │   └── [Delegate Detail]                  │
│  │   └── Framework Agreements                   │
│  ├── My Committees                              │
│  │   ├── [Committee Detail]                     │
│  │   │   ├── Upcoming Meetings                  │
│  │   │   │   └── [Meeting Detail + Agenda]      │
│  │   │   └── Documents                          │
│  │   └── ...                                    │
│  └── Delegate Registry                          │
└─────────────────────────────────────────────────┘
```

### Screen Flow: Use Case 1 — Meeting Brief (6 screens)

The delegate wants to know: *"What's on the agenda for my next committee meeting, and what's changed since I last checked?"*

In the classical app, the delegate must **navigate to the answer**:

```
Screen 1: Dashboard
  ┌─────────────────────────────────────────┐
  │  Welcome, Jean Dupont                   │
  │                                         │
  │  [Delegations]  [My Committees]         │
  │  [Delegate Registry]                    │
  │                                         │
  │  (no proactive information shown)       │
  └─────────────────────────────────────────┘
                    │ click "My Committees"
                    ▼
Screen 2: My Committees
  ┌─────────────────────────────────────────┐
  │  Your Committee Participations          │
  │                                         │
  │  ┌──────────────────────┬────────────┐  │
  │  │ Committee            │ Next mtg   │  │
  │  ├──────────────────────┼────────────┤  │
  │  │ Education Policy     │ 2026-04-18 │  │
  │  │ Skills & Employment  │ 2026-05-02 │  │
  │  │ Trade Committee      │ 2026-04-25 │  │
  │  └──────────────────────┴────────────┘  │
  └─────────────────────────────────────────┘
                    │ click "Education Policy"
                    ▼
Screen 3: Committee Detail
  ┌─────────────────────────────────────────┐
  │  Education Policy Committee             │
  │                                         │
  │  [Upcoming Meetings]  [Documents]       │
  │  [Members]                              │
  └─────────────────────────────────────────┘
                    │ click "Upcoming Meetings"
                    ▼
Screen 4: Upcoming Meetings
  ┌─────────────────────────────────────────┐
  │  Upcoming Meetings — Education Policy   │
  │                                         │
  │  ┌────────────┬──────────┬───────────┐  │
  │  │ Date       │ Title    │ Docs      │  │
  │  ├────────────┼──────────┼───────────┤  │
  │  │ 2026-04-18 │ Spring   │ 12 docs   │  │
  │  │ 2026-06-15 │ Summer   │ 3 docs    │  │
  │  └────────────┴──────────┴───────────┘  │
  │                                         │
  │  (no "what's new" indicator)            │
  └─────────────────────────────────────────┘
                    │ click "Spring" meeting
                    ▼
Screen 5: Meeting Detail + Agenda
  ┌─────────────────────────────────────────┐
  │  Spring Session — Education Policy      │
  │  Date: 2026-04-18  Location: Room CC12  │
  │                                         │
  │  Agenda Documents:                      │
  │  ┌───┬──────────────────┬─────────────┐ │
  │  │ # │ Document         │ Class.      │ │
  │  ├───┼──────────────────┼─────────────┤ │
  │  │ 1 │ Education at a   │ Restricted  │ │
  │  │   │ Glance 2026      │             │ │
  │  │ 2 │ PISA Results     │ General     │ │
  │  │   │ Analysis         │             │ │
  │  │...│ (10 more)        │             │ │
  │  └───┴──────────────────┴─────────────┘ │
  │                                         │
  │  (user must scan to spot changes —      │
  │   no "new since last visit" marker)     │
  └─────────────────────────────────────────┘
                    │ click a document row
                    ▼
Screen 6: Document Detail
  ┌─────────────────────────────────────────┐
  │  Education at a Glance 2026 — Draft     │
  │  Classification: Restricted             │
  │  Last modified: 2026-04-02              │
  │  Committee: Education Policy            │
  │                                         │
  │  [Download PDF]                         │
  └─────────────────────────────────────────┘
```

**Total: 6 screens, 5 clicks, zero proactive intelligence.**

The delegate must already know which committee has a meeting soon, navigate there,
find the meeting, open the agenda, and visually scan for changes. If they participate
in 3 committees, they repeat this flow 3 times.

### Screen Flow: Use Case 2 — Delegate Creation with DAR (8 screens)

The delegation editor wants to: *"Add Marie Laurent as an education policy advisor to our delegation, with proper document access."*

```
Screen 1: Dashboard
  └── click "Delegations"

Screen 2: Delegation List
  ┌─────────────────────────────────────────┐
  │  Delegations                            │
  │  ┌──────────┬──────────┬────────────┐   │
  │  │ Name     │ Type     │ Delegates  │   │
  │  ├──────────┼──────────┼────────────┤   │
  │  │ France   │ Member   │ 42         │   │
  │  │ Germany  │ Member   │ 38         │   │
  │  │ Brazil   │ Partner  │ 15         │   │
  │  │ India    │ Partner  │ 12         │   │
  │  └──────────┴──────────┴────────────┘   │
  └─────────────────────────────────────────┘
  └── click "France"

Screen 3: Delegation Detail — Delegates
  ┌─────────────────────────────────────────┐
  │  France — Member Country                │
  │  Active delegates: 42                   │
  │  Framework Agreements: none             │
  │                                         │
  │  [Add New Delegate]                     │
  │                                         │
  │  ┌──────────────────┬────────────────┐  │
  │  │ Name             │ Function       │  │
  │  ├──────────────────┼────────────────┤  │
  │  │ Jean Dupont      │ Trade Advisor  │  │
  │  │ Claire Martin    │ Env. Attaché   │  │
  │  │ ...              │ ...            │  │
  │  └──────────────────┴────────────────┘  │
  └─────────────────────────────────────────┘
  └── click "Add New Delegate"

Screen 4: Add Delegate — Step 1 of 4: Personal Information
  ┌─────────────────────────────────────────┐
  │  Add New Delegate to France             │
  │  Step 1 of 4: Personal Information      │
  │                                         │
  │  Full Name:    [________________]       │
  │  Email:        [________________]       │
  │  Function:     [________________]       │
  │  Title (opt):  [________________]       │
  │                                         │
  │  [Cancel]                     [Next →]  │
  └─────────────────────────────────────────┘
  └── fill form, click "Next"

Screen 5: Add Delegate — Step 2 of 4: Committee Participations
  ┌─────────────────────────────────────────┐
  │  Step 2 of 4: Committee Participations  │
  │                                         │
  │  Select committees for Marie Laurent:   │
  │                                         │
  │  ☐ Development Assistance Committee     │
  │  ☑ Education Policy Committee           │
  │  ☐ Environment Policy Committee         │
  │  ☑ Skills & Employment Committee        │
  │  ☐ Trade Committee                      │
  │  ☐ ... (15 more committees)             │
  │                                         │
  │  The user must know which committees    │
  │  are relevant for "education policy     │
  │  advisor" — no suggestions offered.     │
  │                                         │
  │  [← Back]                     [Next →]  │
  └─────────────────────────────────────────┘
  └── select committees, click "Next"

Screen 6: Add Delegate — Step 3 of 4: Document Access Rights
  ┌──────────────────────────────────────────────────────┐
  │  Step 3 of 4: Document Access Rights                 │
  │                                                      │
  │  For each committee, set the document access level.  │
  │                                                      │
  │  ┌─────────────────────┬───────────────┬───────────┐ │
  │  │ Committee           │ Access Level  │ Retro?    │ │
  │  ├─────────────────────┼───────────────┼───────────┤ │
  │  │ Education Policy    │ [Restricted▾] │ ☐         │ │
  │  │ Skills & Employment │ [Restricted▾] │ ☐         │ │
  │  └─────────────────────┴───────────────┴───────────┘ │
  │                                                      │
  │  ℹ Rules (shown as static help text):                │
  │  • Member delegates: up to Restricted                │
  │  • Partner delegates: General only (unless           │
  │    Framework Agreement applies)                      │
  │  • Confidential: requires secretariat approval       │
  │  • Retroactive: requires secretariat approval        │
  │                                                      │
  │  The user must READ these rules, understand them,    │
  │  and apply them correctly. The form enforces limits   │
  │  (dropdown restricts options based on membership      │
  │  type) but the user still needs to understand WHY.   │
  │                                                      │
  │  [← Back]                               [Next →]    │
  └──────────────────────────────────────────────────────┘
  └── configure access levels, click "Next"

Screen 7: Add Delegate — Step 4 of 4: Review & Submit
  ┌─────────────────────────────────────────────────────┐
  │  Step 4 of 4: Review & Submit                       │
  │                                                     │
  │  Delegate:    Marie Laurent                         │
  │  Email:       m.laurent@diplomatie.gouv.fr          │
  │  Function:    Education Policy Advisor              │
  │  Delegation:  France (Member)                       │
  │                                                     │
  │  Committee Participations:                          │
  │  • Education Policy Committee                       │
  │  • Skills & Employment Committee                    │
  │                                                     │
  │  Document Access Rights:                            │
  │  • Education Policy — Restricted (pending           │
  │    delegation head approval)                        │
  │  • Skills & Employment — Restricted (pending        │
  │    delegation head approval)                        │
  │                                                     │
  │  [← Back]                            [Submit]       │
  └─────────────────────────────────────────────────────┘
  └── click "Submit"

Screen 8: Confirmation
  ┌─────────────────────────────────────────────────────┐
  │  ✓ Delegate Created Successfully                    │
  │                                                     │
  │  Marie Laurent (DEL-2026-0891) has been added       │
  │  to the France delegation.                          │
  │                                                     │
  │  Pending approvals:                                 │
  │  • Education Policy — Restricted access:            │
  │    awaiting delegation head approval                │
  │  • Skills & Employment — Restricted access:         │
  │    awaiting delegation head approval                │
  │                                                     │
  │  [Back to Delegation]  [Add Another Delegate]       │
  └─────────────────────────────────────────────────────┘
```

**Total: 8 screens, 7 clicks, 4 form steps, user must understand business rules.**

The editor must know which committees match "education policy advisor" (no suggestion),
must understand the DAR rules to set the right access level (help text is passive),
and must repeat the DAR form for each committee. If they get it wrong, they discover
it on the review screen, go back, and re-enter.

### Implementation Sketch

```python
# classical_app/app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy.orm import Session as DBSession
from shared.database import get_engine, Delegation, Delegate, Committee, Meeting, init_db
from shared.business_rules import compute_default_access_level, determine_approval_route

app = Flask(__name__)
app.secret_key = "poc-secret-key"
engine = get_engine()


@app.route("/")
def dashboard():
    """Screen 1: Dashboard — no proactive information."""
    return render_template("dashboard.html", user=get_current_user())


@app.route("/delegations")
def delegation_list():
    """Screen 2: List of delegations."""
    with DBSession(engine) as db:
        delegations = db.query(Delegation).all()
    return render_template("delegation_list.html", delegations=delegations)


@app.route("/delegations/<delegation_id>")
def delegation_detail(delegation_id):
    """Screen 3: Delegation detail with delegate list."""
    with DBSession(engine) as db:
        delegation = db.get(Delegation, delegation_id)
        delegates = [d for d in delegation.delegates if d.is_active]
    return render_template("delegation_detail.html",
                           delegation=delegation, delegates=delegates)


@app.route("/delegations/<delegation_id>/delegates/new", methods=["GET", "POST"])
def delegate_create_step1(delegation_id):
    """Screen 4: Step 1 — Personal information form."""
    if request.method == "POST":
        session["new_delegate"] = {
            "full_name": request.form["full_name"],
            "email": request.form["email"],
            "function": request.form["function"],
            "title": request.form.get("title", ""),
            "delegation_id": delegation_id,
        }
        return redirect(url_for("delegate_create_step2", delegation_id=delegation_id))
    return render_template("delegate_create_step1.html", delegation_id=delegation_id)


@app.route("/delegations/<delegation_id>/delegates/new/committees", methods=["GET", "POST"])
def delegate_create_step2(delegation_id):
    """Screen 5: Step 2 — Committee selection (no intelligent suggestions)."""
    with DBSession(engine) as db:
        committees = db.query(Committee).order_by(Committee.name).all()
    if request.method == "POST":
        session["new_delegate"]["committee_ids"] = request.form.getlist("committee_ids")
        return redirect(url_for("delegate_create_step3", delegation_id=delegation_id))
    return render_template("delegate_create_step2.html",
                           delegation_id=delegation_id, committees=committees)


@app.route("/delegations/<delegation_id>/delegates/new/access", methods=["GET", "POST"])
def delegate_create_step3(delegation_id):
    """Screen 6: Step 3 — Document Access Rights (user applies rules manually)."""
    with DBSession(engine) as db:
        delegation = db.get(Delegation, delegation_id)
        selected_ids = session["new_delegate"]["committee_ids"]
        committees = db.query(Committee).filter(Committee.id.in_(selected_ids)).all()

        # Pre-compute defaults — but user can override
        defaults = {}
        for c in committees:
            defaults[c.id] = compute_default_access_level(
                delegation.membership_type, c.id, delegation.framework_agreements
            )

    if request.method == "POST":
        access_rights = []
        for c in committees:
            access_rights.append({
                "committee_id": c.id,
                "classification_level": request.form[f"level_{c.id}"],
                "retroactive": request.form.get(f"retro_{c.id}") == "on",
            })
        session["new_delegate"]["access_rights"] = access_rights
        return redirect(url_for("delegate_create_review", delegation_id=delegation_id))

    return render_template("delegate_create_step3.html",
                           delegation_id=delegation_id,
                           delegation=delegation,
                           committees=committees,
                           defaults=defaults)


@app.route("/delegations/<delegation_id>/delegates/new/review", methods=["GET", "POST"])
def delegate_create_review(delegation_id):
    """Screen 7: Review & Submit."""
    if request.method == "POST":
        # Create delegate and DARs using shared business logic
        # ... (calls shared/database.py and shared/business_rules.py)
        return redirect(url_for("delegate_create_confirm",
                                delegation_id=delegation_id, delegate_id="DEL-NEW"))
    return render_template("delegate_create_review.html",
                           data=session["new_delegate"],
                           delegation_id=delegation_id)


# --- Meeting brief flow (Use Case 1) ---

@app.route("/committees")
def committee_list():
    """Screen 2 (UC1): My committee participations."""
    # ... query committees for current user's delegate record ...
    return render_template("committee_list.html", committees=committees)


@app.route("/committees/<committee_id>/meetings")
def meeting_list(committee_id):
    """Screen 4 (UC1): Upcoming meetings for a committee."""
    # ... query meetings, NO "new since last visit" indicator ...
    return render_template("meeting_list.html", meetings=meetings)


@app.route("/meetings/<meeting_id>")
def meeting_detail(meeting_id):
    """Screen 5 (UC1): Meeting detail with agenda documents."""
    # ... query agenda items, NO "new since last visit" highlighting ...
    return render_template("meeting_detail.html", meeting=meeting, agenda=agenda)
```

### What the Classical App Deliberately Does NOT Do

These gaps are the point — they demonstrate the agent's value:

| Feature | Classical App | Agent App |
|---|---|---|
| Proactive meeting briefing on login | Not possible in a form paradigm | Agent greets with personalized brief |
| Suggest committees from function | User must know and select | Agent infers from "education policy advisor" |
| Explain why an access level applies | Static help text, user must read | Agent explains reasoning in conversation |
| Highlight new documents since last visit | Not shown (or requires a report screen) | Agent proactively lists changes |
| Batch DAR creation with reasoning | One form per committee, manual rule application | Agent reasons through all committees at once |
| Handle edge cases conversationally | Error messages, back button | "France has no Framework Agreements, so..." |

---

## 4. Agent Application — Same Data, Different Paradigm

The agent app uses the **same** `shared/database.py` and `shared/business_rules.py`.
Its tools are thin wrappers that call the shared layer:

```python
# agent_app/tools.py
from typing import Annotated
from pydantic import Field
from agent_framework import tool, FunctionInvocationContext
from shared.database import get_engine, Delegation, Delegate, Committee, Meeting
from shared.business_rules import compute_default_access_level, determine_approval_route
from sqlalchemy.orm import Session

engine = get_engine()

@tool(approval_mode="never_require")
def get_delegation_info(
    delegation_id: Annotated[str, Field(description="Delegation ID or country name")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Retrieve delegation details: country/organization, membership type, delegate count,
    and any Framework Agreements in effect."""
    with Session(engine) as db:
        delegation = db.query(Delegation).filter(
            (Delegation.id == delegation_id) | (Delegation.name == delegation_id)
        ).first()
        # ... format and return ...

@tool(approval_mode="always_require")
def create_delegate(
    full_name: Annotated[str, Field(description="Full name of the delegate")],
    delegation_id: Annotated[str, Field(description="Delegation ID")],
    function: Annotated[str, Field(description="Professional function")],
    email: Annotated[str, Field(description="Professional email address")],
    committee_ids: Annotated[list[str], Field(description="Committee IDs")],
    ctx: FunctionInvocationContext = None,
) -> str:
    """Create a new delegate. Also computes and creates Document Access Rights
    using shared business rules. Requires user confirmation."""
    with Session(engine) as db:
        # Create delegate
        # For each committee: compute_default_access_level → determine_approval_route
        # Create DARs
        # Return summary
        pass
```

### MCP Layer

The MCP server sits on top of the same shared layer. It exposes:
- **Data tools**: query delegations, delegates, meetings, documents (backed by `shared/database.py`)
- **Knowledge tools**: search business rules, get workflow definitions (backed by the KB markdown files + vector store)

```python
# agent_app/mcp_server.py
from mcp.server import Server
from shared.database import get_engine, Delegation, Delegate
from shared.business_rules import compute_default_access_level
from sqlalchemy.orm import Session

server = Server("one-mp-data-and-kb")
engine = get_engine()

@server.tool()
async def query_delegation(delegation_id: str) -> dict:
    """Query delegation details from the shared database."""
    with Session(engine) as db:
        delegation = db.query(Delegation).filter(
            (Delegation.id == delegation_id) | (Delegation.name == delegation_id)
        ).first()
        # ... return structured data ...

@server.tool()
async def search_business_rules(query: str, entity_type: str | None = None) -> dict:
    """Semantic search over business rules KB. Uses the same rules that
    the classical app enforces via form validation."""
    # ... ChromaDB vector search over KB markdown files ...
```

This ensures the MCP server is a protocol layer, not a separate data silo.
Any change to the database or business rules is immediately visible to both apps.

---

## 5. Side-by-Side Demo Script

### Demo 1: "What's new for my next meeting?"

**Classical app** (audience watches 6 clicks):
1. Login → Dashboard (no information)
2. Click "My Committees" → see 3 committees
3. Click "Education Policy" → committee page
4. Click "Upcoming Meetings" → see 2 meetings
5. Click "Spring Session" → see 12 agenda documents
6. Visually scan for changes... no "new" indicator. User has no way to know what changed.

**Agent app** (audience watches 0 clicks):
```
Agent: Good morning, Jean. Your next committee meeting is the Education
Policy Committee Spring Session on April 18th — 12 agenda documents.

Since your last visit on March 28th, 3 documents have been added or updated:
• "Education at a Glance 2026 — Draft" (Restricted, modified April 2)
• "PISA Results Analysis — 2025 Update" (General, added April 1)
• "Skills Forecast Methodology Note" (General, added March 30)

Would you like me to summarize any of these, or is there anything else
you'd like to prepare for the meeting?
```

**Takeaway**: the agent delivers in the greeting what the form app cannot deliver at all.

### Demo 2: "Add Marie Laurent as a delegate"

**Classical app** (audience watches 8 screens, 4 form steps):
1. Dashboard → Delegations → France → "Add New Delegate"
2. Fill personal info (name, email, function) → Next
3. Browse 20 committees, select the right ones (no suggestions) → Next
4. For each committee, pick classification level from dropdown, read help text about rules → Next
5. Review everything → Submit
6. Confirmation with pending approvals

**Agent app** (audience watches 3 conversational turns):
```
Editor: "Add Marie Laurent as a delegate — she's an education policy advisor.
         Email is m.laurent@diplomatie.gouv.fr"

Agent: "Marie Laurent's function suggests the Education Policy Committee.
        Should I assign her there? Any other committees?"

Editor: "Yes, and also Skills & Employment."

Agent: "Here's what I'll do:
        • Create Marie Laurent in the France delegation
        • Education Policy Committee — Restricted access (member default)
        • Skills & Employment Committee — Restricted access (member default)
        Both Restricted DARs require delegation head approval.
        No retroactive access. Shall I proceed?"

Editor: "Yes."

Agent: "Done. Marie Laurent (DEL-2026-0891) is created. Two DARs are
        pending delegation head approval."
```

**Takeaway**: 8 screens → 3 turns. The agent inferred committees from the function,
applied DAR rules automatically, batched the confirmation, and explained the
approval routing — all without the editor needing to know the rules.

---

## 6. Test Data Requirements

> **Deferred** — test data generation will be addressed separately.

The following test data categories are required for both apps:

| Entity | Minimum Count | Key Variations |
|---|---|---|
| Delegations | 6-8 | Mix of member (e.g., France, Japan, Germany) and partner (e.g., Brazil, India) countries |
| Delegates | 30-50 | Distributed across delegations, various functions |
| Committees | 8-10 | Covering different policy areas (education, trade, environment, development, etc.) |
| Framework Agreements | 2-3 | Partner delegations with elevated access on specific committees |
| Documents | 40-60 | Various classification levels, across committees |
| Meetings | 10-15 | Upcoming and past, with agenda documents linked |
| Document Access Rights | 50-80 | Pre-existing DARs for seeded delegates, covering all approval statuses |
| Delegate login history | Per delegate | Last login dates to drive "new since last visit" logic |

Test data must cover the key demo scenarios:
- A member delegation editor adding a delegate (UC2)
- A partner delegation editor adding a delegate with and without a Framework Agreement (UC2 variation)
- A delegate with upcoming meetings and recently modified agenda documents (UC1)
- Edge cases: Confidential access request, retroactive access request, delegation with no meetings

---

## 7. Project Structure

```
one_agent_poc/
├── shared/                          # Shared data layer — used by all consumers
│   ├── __init__.py
│   ├── database.py                  # SQLAlchemy models, engine setup
│   ├── business_rules.py           # DAR computation, approval routing
│   └── seed_data.py                # Test data population (deferred)
│
├── classical_app/                   # Flask form-based application
│   ├── app.py                       # Flask app, routes
│   ├── forms.py                     # WTForms form classes
│   ├── templates/
│   │   ├── base.html               # Bootstrap layout, navigation
│   │   ├── dashboard.html
│   │   ├── delegation_list.html
│   │   ├── delegation_detail.html
│   │   ├── delegate_create_step1.html
│   │   ├── delegate_create_step2.html
│   │   ├── delegate_create_step3.html
│   │   ├── delegate_create_review.html
│   │   ├── delegate_create_confirm.html
│   │   ├── committee_list.html
│   │   ├── committee_detail.html
│   │   ├── meeting_list.html
│   │   ├── meeting_detail.html
│   │   └── document_detail.html
│   └── static/
│       └── style.css               # Minimal custom styles (Bootstrap does the heavy lifting)
│
├── agent_app/                       # Microsoft Agent Framework application
│   ├── agent.py                     # Agent setup, system prompt, execution loop
│   ├── tools.py                     # @tool functions (thin wrappers over shared/)
│   ├── middleware.py                # AuditMiddleware, SecurityMiddleware
│   └── kb_server/                  # MCP Knowledge Base server
│       ├── server.py               # MCP server (mcp SDK)
│       ├── rules/                  # Business rule KB entries (markdown)
│       │   ├── dar_member_delegate_001.md
│       │   ├── dar_partner_delegate_001.md
│       │   ├── dar_framework_agreement_001.md
│       │   ├── dar_confidential_001.md
│       │   ├── dar_retroactive_001.md
│       │   ├── workflow_delegate_create.md
│       │   └── workflow_meeting_brief.md
│       └── vector_store/           # ChromaDB embeddings (auto-generated from rules/)
│
├── one_agent.db                     # SQLite database (shared, single file)
├── requirements.txt
└── README.md
```

---

## 8. Implementation Sequence

The build order is designed so each step produces a working, demonstrable artifact:

| Step | Deliverable | Depends On |
|---|---|---|
| 1. Shared data layer | `shared/database.py`, `shared/business_rules.py`, `shared/seed_data.py` | Nothing |
| 2. Database init + seed | Populated `one_agent.db` with test data | Step 1 |
| 3. Classical app — read flows | Dashboard, committee list, meeting list, meeting detail (UC1) | Step 2 |
| 4. Classical app — write flows | Delegate creation wizard, 4-step form with DAR (UC2) | Step 2 |
| 5. Agent tools | `@tool` functions backed by shared layer | Step 2 |
| 6. Agent — read agent (UC1) | Proactive meeting brief on session start | Step 5 |
| 7. Agent — write agent (UC2) | Delegate creation with DAR reasoning and confirmation | Step 5 |
| 8. MCP KB server | Business rules as MCP tools, connected via `MCPStdioTool` | Step 5 |
| 9. Demo script | Side-by-side walkthrough with both apps running | Steps 4 + 7 |

Steps 3-4 (classical app) and steps 5-7 (agent app) can be developed in parallel
once the shared layer (steps 1-2) is complete.

---

## 9. What This Architecture Proves

The dual-demo is not just a comparison — it validates the PoC thesis from
`ONE-Agent-concept.md` with tangible evidence:

| Thesis | Classical App Shows | Agent App Shows |
|---|---|---|
| Proactive intelligence is impossible in forms | User navigates 6 screens to find what's new — or doesn't find it at all | Agent greets with a personalized brief |
| Agentic compresses multi-step workflows | 8 screens, 4 form steps, manual rule application | 3 conversational turns, automatic reasoning |
| Business rules belong in a queryable KB, not in help text | Static help text next to form fields — users must read and apply | Agent queries KB, reasons, explains |
| Human-in-the-loop is better than form submission | Submit button with no explanation of consequences | Agent proposes action with reasoning, user approves |
| Audit trail captures reasoning, not just events | "Delegate created at 14:32 by user X" | "User asked for education policy advisor → agent inferred EDU committee → checked membership type → applied Restricted access → user confirmed" |

The shared database makes the comparison airtight: same data, same rules,
same business outcomes — different paradigm, different experience.
