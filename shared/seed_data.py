"""
ONE-MP Agent PoC shared data layer - Seed data for database initialization.

This module provides seed data and seeding functions for the ONE-MP Agent
PoC database. It creates a comprehensive demo dataset covering:

- 4 delegations (2 MEMBER: FRA, DEU; 2 PARTNER: BRA, IND)
- 5 committees (EDU, TRADE, DAC, ENV, SKILLS)
- 9 delegates with various roles and committee assignments
- 2 framework agreements (BRA-EDU active, IND-DAC expired)
- 18 documents across all committees with varied classifications
- 24 document access rights (DARs) based on business rules
- 5 meetings across committees with future/past dates
- 19 meeting agenda items linking documents to meetings

REQ-005 Demo Scenarios:
- Member delegates (FRA, DEU) see RESTRICTED documents via APPROVED DARs
- Partner delegates (BRA, IND) see GENERAL documents via AUTO_APPROVED DARs
- BRA-EDU RESTRICTED access via active framework agreement (FA id=1)
- IND-DAC GENERAL access (FA id=2 expired, no enhanced access)
- Visibility filtering by classification level and approval status
- Meeting agendas with mixed document classifications

Idempotency via:
- session.merge() for string-PK entities (Delegation, Committee, Delegate,
  Document, Meeting) — upserts on PK
- session.merge() with explicit id for integer-PK entities
- Clear and re-add for M2M delegate-committee associations
"""

from datetime import datetime
from sqlalchemy.orm import Session

from shared.database import (
    Delegation,
    Committee,
    Delegate,
    FrameworkAgreement,
    Document,
    DocumentAccessRight,
    Meeting,
    MeetingAgendaItem,
    MembershipType,
    ClassificationLevel,
    ApprovalStatus,
    get_engine,
    init_db,
)
from shared.business_rules import (
    compute_default_access_level,
    determine_approval_route,
)


def seed_delegations(session: Session) -> None:
    """
    Seed delegations table.

    Creates 4 delegations: FRA (MEMBER), DEU (MEMBER), BRA (PARTNER),
    IND (PARTNER).
    """
    delegations = [
        Delegation(id="FRA", name="France", membership_type=MembershipType.MEMBER),
        Delegation(
            id="DEU",
            name="Germany",
            membership_type=MembershipType.MEMBER,
        ),
        Delegation(
            id="BRA",
            name="Brazil",
            membership_type=MembershipType.PARTNER,
        ),
        Delegation(
            id="IND",
            name="India",
            membership_type=MembershipType.PARTNER,
        ),
    ]
    for delegation in delegations:
        session.merge(delegation)


def seed_committees(session: Session) -> None:
    """
    Seed committees table.

    Creates 5 committees: EDU, TRADE, DAC, ENV, SKILLS.
    """
    committees = [
        Committee(
            id="EDU",
            name="Education Committee",
            description="Oversees education policy",
        ),
        Committee(
            id="TRADE",
            name="Trade Committee",
            description="Handles trade agreements",
        ),
        Committee(
            id="DAC",
            name="Development Aid Committee",
            description="Development aid coordination",
        ),
        Committee(
            id="ENV",
            name="Environment Committee",
            description="Environmental policy",
        ),
        Committee(
            id="SKILLS",
            name="Skills & Training Committee",
            description="Workforce development",
        ),
    ]
    for committee in committees:
        session.merge(committee)


def seed_delegates(session: Session) -> None:
    """
    Seed delegates table with committee associations.

    Creates 9 delegates across 4 delegations with various committee
    assignments via the delegate_committees M2M table.
    """
    # Define delegates with their committee assignments
    delegates_data = [
        {
            "id": "DEL-2026-0001",
            "full_name": "Marie Dupont",
            "email": "m.dupont@fra.example",
            "function": "Head of Delegation",
            "title": "Ambassador",
            "delegation_id": "FRA",
            "accreditation_date": datetime(2026, 1, 10),
            "last_login": datetime(2026, 4, 10),
            "committees": ["EDU", "TRADE", "DAC", "ENV", "SKILLS"],
        },
        {
            "id": "DEL-2026-0002",
            "full_name": "Jean Martin",
            "email": "j.martin@fra.example",
            "function": "Delegate",
            "title": None,
            "delegation_id": "FRA",
            "accreditation_date": datetime(2026, 1, 15),
            "last_login": datetime(2026, 4, 8),
            "committees": ["EDU", "ENV", "TRADE"],
        },
        {
            "id": "DEL-2026-0003",
            "full_name": "Hans Mueller",
            "email": "h.mueller@deu.example",
            "function": "Head of Delegation",
            "title": "Dr.",
            "delegation_id": "DEU",
            "accreditation_date": datetime(2026, 1, 12),
            "last_login": datetime(2026, 4, 9),
            "committees": ["TRADE", "DAC", "SKILLS", "ENV"],
        },
        {
            "id": "DEL-2026-0004",
            "full_name": "Anna Schmidt",
            "email": "a.schmidt@deu.example",
            "function": "Delegate",
            "title": None,
            "delegation_id": "DEU",
            "accreditation_date": datetime(2026, 2, 1),
            "last_login": datetime(2026, 4, 7),
            "committees": ["EDU", "SKILLS"],
        },
        {
            "id": "DEL-2026-0005",
            "full_name": "Carlos Silva",
            "email": "c.silva@bra.example",
            "function": "Head of Delegation",
            "title": None,
            "delegation_id": "BRA",
            "accreditation_date": datetime(2026, 1, 20),
            "last_login": datetime(2026, 4, 11),
            "committees": ["EDU", "TRADE", "DAC"],
        },
        {
            "id": "DEL-2026-0006",
            "full_name": "Ana Souza",
            "email": "a.souza@bra.example",
            "function": "Delegate",
            "title": None,
            "delegation_id": "BRA",
            "accreditation_date": datetime(2026, 2, 5),
            "last_login": None,
            "committees": ["EDU"],
        },
        {
            "id": "DEL-2026-0007",
            "full_name": "Priya Sharma",
            "email": "p.sharma@ind.example",
            "function": "Head of Delegation",
            "title": None,
            "delegation_id": "IND",
            "accreditation_date": datetime(2026, 1, 25),
            "last_login": datetime(2026, 4, 10),
            "committees": ["DAC", "ENV", "TRADE"],
        },
        {
            "id": "DEL-2026-0008",
            "full_name": "Raj Patel",
            "email": "r.patel@ind.example",
            "function": "Delegate",
            "title": None,
            "delegation_id": "IND",
            "accreditation_date": datetime(2026, 2, 10),
            "last_login": datetime(2026, 4, 5),
            "committees": ["TRADE", "DAC"],
        },
        {
            "id": "DEL-2026-0009",
            "full_name": "Sophie Weber",
            "email": "s.weber@deu.example",
            "function": "Adviser",
            "title": None,
            "delegation_id": "DEU",
            "accreditation_date": datetime(2026, 3, 1),
            "last_login": None,
            "committees": ["EDU"],
        },
    ]

    # Create delegates with committee associations before merge
    for delegate_data in delegates_data:
        committee_ids = delegate_data.pop("committees")
        delegate = Delegate(**delegate_data)

        # Pre-load committees from the session
        committees = [
            session.get(Committee, cid) for cid in committee_ids
        ]
        delegate.committees = committees

        session.merge(delegate)


def seed_framework_agreements(session: Session) -> None:
    """
    Seed framework agreements table.

    Creates 2 framework agreements:
    - FA id=1: BRA-EDU, active (start 2026-01-01, no end date)
    - FA id=2: IND-DAC, expired (start 2026-01-01, end 2025-12-31)
    """
    fa1 = FrameworkAgreement(
        id=1,
        delegation_id="BRA",
        committee_id="EDU",
        start_date=datetime(2026, 1, 1),
        end_date=None,
    )
    fa2 = FrameworkAgreement(
        id=2,
        delegation_id="IND",
        committee_id="DAC",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2025, 12, 31),
    )
    session.merge(fa1)
    session.merge(fa2)


def seed_documents(session: Session) -> None:
    """
    Seed documents table.

    Creates 18 documents across all committees with varied classifications:
    PUBLIC, GENERAL, RESTRICTED, CONFIDENTIAL.
    """
    documents = [
        Document(
            id="DOC-2026-0001",
            title="EDU Annual Report 2025",
            classification=ClassificationLevel.PUBLIC,
            committee_id="EDU",
            publication_date=datetime(2026, 1, 15),
            last_modified=datetime(2026, 1, 20),
        ),
        Document(
            id="DOC-2026-0002",
            title="EDU Budget Proposal 2026",
            classification=ClassificationLevel.GENERAL,
            committee_id="EDU",
            publication_date=datetime(2026, 2, 1),
            last_modified=datetime(2026, 2, 5),
        ),
        Document(
            id="DOC-2026-0003",
            title="EDU Strategic Roadmap",
            classification=ClassificationLevel.RESTRICTED,
            committee_id="EDU",
            publication_date=datetime(2026, 2, 10),
            last_modified=datetime(2026, 3, 1),
        ),
        Document(
            id="DOC-2026-0004",
            title="EDU Confidential Assessment",
            classification=ClassificationLevel.CONFIDENTIAL,
            committee_id="EDU",
            publication_date=datetime(2026, 3, 1),
            last_modified=datetime(2026, 3, 5),
        ),
        Document(
            id="DOC-2026-0005",
            title="TRADE Framework Overview",
            classification=ClassificationLevel.PUBLIC,
            committee_id="TRADE",
            publication_date=datetime(2026, 1, 20),
            last_modified=datetime(2026, 1, 25),
        ),
        Document(
            id="DOC-2026-0006",
            title="TRADE Negotiation Briefing",
            classification=ClassificationLevel.GENERAL,
            committee_id="TRADE",
            publication_date=datetime(2026, 2, 15),
            last_modified=datetime(2026, 2, 20),
        ),
        Document(
            id="DOC-2026-0007",
            title="TRADE Restricted Position Paper",
            classification=ClassificationLevel.RESTRICTED,
            committee_id="TRADE",
            publication_date=datetime(2026, 3, 1),
            last_modified=datetime(2026, 3, 10),
        ),
        Document(
            id="DOC-2026-0008",
            title="DAC Aid Allocation Report",
            classification=ClassificationLevel.PUBLIC,
            committee_id="DAC",
            publication_date=datetime(2026, 1, 25),
            last_modified=datetime(2026, 2, 1),
        ),
        Document(
            id="DOC-2026-0009",
            title="DAC Program Review",
            classification=ClassificationLevel.GENERAL,
            committee_id="DAC",
            publication_date=datetime(2026, 2, 20),
            last_modified=datetime(2026, 2, 25),
        ),
        Document(
            id="DOC-2026-0010",
            title="DAC Restricted Strategy",
            classification=ClassificationLevel.RESTRICTED,
            committee_id="DAC",
            publication_date=datetime(2026, 3, 5),
            last_modified=datetime(2026, 3, 15),
        ),
        Document(
            id="DOC-2026-0011",
            title="DAC Confidential Report",
            classification=ClassificationLevel.CONFIDENTIAL,
            committee_id="DAC",
            publication_date=datetime(2026, 3, 10),
            last_modified=datetime(2026, 4, 1),
        ),
        Document(
            id="DOC-2026-0012",
            title="ENV Climate Action Plan",
            classification=ClassificationLevel.PUBLIC,
            committee_id="ENV",
            publication_date=datetime(2026, 2, 1),
            last_modified=datetime(2026, 2, 10),
        ),
        Document(
            id="DOC-2026-0013",
            title="ENV Policy Draft",
            classification=ClassificationLevel.GENERAL,
            committee_id="ENV",
            publication_date=datetime(2026, 3, 1),
            last_modified=datetime(2026, 3, 5),
        ),
        Document(
            id="DOC-2026-0014",
            title="ENV Restricted Data",
            classification=ClassificationLevel.RESTRICTED,
            committee_id="ENV",
            publication_date=datetime(2026, 3, 15),
            last_modified=datetime(2026, 4, 5),
        ),
        Document(
            id="DOC-2026-0015",
            title="SKILLS Training Framework",
            classification=ClassificationLevel.PUBLIC,
            committee_id="SKILLS",
            publication_date=datetime(2026, 2, 5),
            last_modified=datetime(2026, 2, 10),
        ),
        Document(
            id="DOC-2026-0016",
            title="SKILLS Development Plan",
            classification=ClassificationLevel.GENERAL,
            committee_id="SKILLS",
            publication_date=datetime(2026, 3, 1),
            last_modified=datetime(2026, 3, 5),
        ),
        Document(
            id="DOC-2026-0017",
            title="EDU Partnership Guidelines",
            classification=ClassificationLevel.GENERAL,
            committee_id="EDU",
            publication_date=datetime(2026, 3, 15),
            last_modified=datetime(2026, 4, 8),
        ),
        Document(
            id="DOC-2026-0018",
            title="TRADE Confidential Analysis",
            classification=ClassificationLevel.CONFIDENTIAL,
            committee_id="TRADE",
            publication_date=datetime(2026, 3, 20),
            last_modified=datetime(2026, 4, 9),
        ),
    ]

    for document in documents:
        session.merge(document)


def seed_document_access_rights(session: Session) -> None:
    """
    Seed document access rights table.

    Creates 24 DARs based on business rules:
    - MEMBER delegates: RESTRICTED classification + APPROVED status
    - PARTNER delegates (no active FA): GENERAL classification +
      AUTO_APPROVED status
    - PARTNER delegates (active FA): RESTRICTED classification +
      APPROVED status
    """
    # Ensure all delegations and delegates are loaded
    session.flush()

    # Explicit DAR data: (id, delegate_id, committee_id, classification,
    # status)
    dar_data = [
        (1, "DEL-2026-0001", "EDU", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (2, "DEL-2026-0001", "TRADE", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (3, "DEL-2026-0001", "DAC", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (4, "DEL-2026-0002", "EDU", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (5, "DEL-2026-0002", "ENV", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (6, "DEL-2026-0003", "TRADE", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (7, "DEL-2026-0003", "DAC", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (8, "DEL-2026-0003", "SKILLS", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (9, "DEL-2026-0004", "EDU", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (10, "DEL-2026-0004", "SKILLS", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (11, "DEL-2026-0005", "EDU", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (12, "DEL-2026-0005", "TRADE", ClassificationLevel.GENERAL,
         ApprovalStatus.AUTO_APPROVED),
        (13, "DEL-2026-0006", "EDU", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (14, "DEL-2026-0007", "DAC", ClassificationLevel.GENERAL,
         ApprovalStatus.AUTO_APPROVED),
        (15, "DEL-2026-0007", "ENV", ClassificationLevel.GENERAL,
         ApprovalStatus.AUTO_APPROVED),
        (16, "DEL-2026-0008", "TRADE", ClassificationLevel.GENERAL,
         ApprovalStatus.AUTO_APPROVED),
        (17, "DEL-2026-0008", "DAC", ClassificationLevel.GENERAL,
         ApprovalStatus.AUTO_APPROVED),
        (18, "DEL-2026-0009", "EDU", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (19, "DEL-2026-0001", "ENV", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (20, "DEL-2026-0001", "SKILLS", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (21, "DEL-2026-0002", "TRADE", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (22, "DEL-2026-0003", "ENV", ClassificationLevel.RESTRICTED,
         ApprovalStatus.APPROVED),
        (23, "DEL-2026-0005", "DAC", ClassificationLevel.GENERAL,
         ApprovalStatus.AUTO_APPROVED),
        (24, "DEL-2026-0007", "TRADE", ClassificationLevel.GENERAL,
         ApprovalStatus.AUTO_APPROVED),
    ]

    created_at = datetime(2026, 1, 15)
    for dar_id, delegate_id, committee_id, level, status in dar_data:
        dar = DocumentAccessRight(
            id=dar_id,
            delegate_id=delegate_id,
            committee_id=committee_id,
            classification_level=level,
            retroactive=False,
            approval_status=status,
            created_at=created_at,
            created_by="system",
        )
        session.merge(dar)


def seed_meetings(session: Session) -> None:
    """
    Seed meetings table.

    Creates 5 meetings across committees with various dates (past and
    future relative to 2026-04-12).
    """
    meetings = [
        Meeting(
            id="MTG-EDU-2026-05",
            committee_id="EDU",
            title="Education Committee Spring Meeting",
            date=datetime(2026, 5, 10, 9, 0),
            location="Geneva",
        ),
        Meeting(
            id="MTG-EDU-2026-03",
            committee_id="EDU",
            title="Education Committee March Session",
            date=datetime(2026, 3, 15, 10, 0),
            location="Paris",
        ),
        Meeting(
            id="MTG-TRADE-2026-05",
            committee_id="TRADE",
            title="Trade Committee Q2 Meeting",
            date=datetime(2026, 5, 20, 14, 0),
            location="Brussels",
        ),
        Meeting(
            id="MTG-DAC-2026-04",
            committee_id="DAC",
            title="Development Aid Review April",
            date=datetime(2026, 4, 25, 9, 0),
            location="Geneva",
        ),
        Meeting(
            id="MTG-ENV-2026-06",
            committee_id="ENV",
            title="Environment Committee Summer Session",
            date=datetime(2026, 6, 5, 10, 0),
            location="Vienna",
        ),
    ]

    for meeting in meetings:
        session.merge(meeting)


def seed_agenda_items(session: Session) -> None:
    """
    Seed meeting agenda items table.

    Creates 19 agenda items across 5 meetings, linking documents to
    meetings in a specific order.
    """
    agenda_items_data = [
        # MTG-EDU-2026-05 (5 items)
        (1, "MTG-EDU-2026-05", "DOC-2026-0001", 1),
        (2, "MTG-EDU-2026-05", "DOC-2026-0002", 2),
        (3, "MTG-EDU-2026-05", "DOC-2026-0003", 3),
        (4, "MTG-EDU-2026-05", "DOC-2026-0004", 4),
        (5, "MTG-EDU-2026-05", "DOC-2026-0017", 5),
        # MTG-EDU-2026-03 (3 items)
        (6, "MTG-EDU-2026-03", "DOC-2026-0001", 1),
        (7, "MTG-EDU-2026-03", "DOC-2026-0002", 2),
        (8, "MTG-EDU-2026-03", "DOC-2026-0003", 3),
        # MTG-TRADE-2026-05 (4 items)
        (9, "MTG-TRADE-2026-05", "DOC-2026-0005", 1),
        (10, "MTG-TRADE-2026-05", "DOC-2026-0006", 2),
        (11, "MTG-TRADE-2026-05", "DOC-2026-0007", 3),
        (12, "MTG-TRADE-2026-05", "DOC-2026-0018", 4),
        # MTG-DAC-2026-04 (4 items)
        (13, "MTG-DAC-2026-04", "DOC-2026-0008", 1),
        (14, "MTG-DAC-2026-04", "DOC-2026-0009", 2),
        (15, "MTG-DAC-2026-04", "DOC-2026-0010", 3),
        (16, "MTG-DAC-2026-04", "DOC-2026-0011", 4),
        # MTG-ENV-2026-06 (3 items)
        (17, "MTG-ENV-2026-06", "DOC-2026-0012", 1),
        (18, "MTG-ENV-2026-06", "DOC-2026-0013", 2),
        (19, "MTG-ENV-2026-06", "DOC-2026-0014", 3),
    ]

    for item_id, meeting_id, document_id, order in agenda_items_data:
        agenda_item = MeetingAgendaItem(
            id=item_id,
            meeting_id=meeting_id,
            document_id=document_id,
            item_order=order,
        )
        session.merge(agenda_item)


def seed_all(session: Session) -> None:
    """
    Seed all tables in correct dependency order.

    Order: delegations → committees → delegates → framework_agreements →
    documents → document_access_rights → meetings → agenda_items
    """
    seed_delegations(session)
    seed_committees(session)
    seed_delegates(session)
    seed_framework_agreements(session)
    seed_documents(session)
    seed_document_access_rights(session)
    seed_meetings(session)
    seed_agenda_items(session)


if __name__ == "__main__":
    db_path = "one_agent.db"
    engine = get_engine(db_path)
    init_db(engine)

    with Session(engine) as session:
        seed_all(session)
        session.commit()

        print(f"Database initialized at {db_path}")
        print(f"  Delegations: {session.query(Delegation).count()}")
        print(f"  Committees: {session.query(Committee).count()}")
        print(f"  Delegates: {session.query(Delegate).count()}")
        print(
            f"  Framework Agreements: "
            f"{session.query(FrameworkAgreement).count()}"
        )
        print(f"  Documents: {session.query(Document).count()}")
        print(
            f"  Document Access Rights: "
            f"{session.query(DocumentAccessRight).count()}"
        )
        print(f"  Meetings: {session.query(Meeting).count()}")
        print(
            f"  Meeting Agenda Items: "
            f"{session.query(MeetingAgendaItem).count()}"
        )
