"""Tests for shared.database models and relationships."""
from datetime import datetime

from sqlalchemy.orm import Session

from shared.database import (
    Delegation,
    Delegate,
    Committee,
    Document,
    DocumentAccessRight,
    Meeting,
    MeetingAgendaItem,
    MembershipType,
    ClassificationLevel,
    DelegateRole,
    ApprovalStatus,
)


def test_create_delegation_and_delegate(session: Session):
    """Test creating a Delegation and Delegate with FK relationship."""
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-2026-0001",
        full_name="Alice Dupont",
        email="alice@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
    )
    session.add(delegation)
    session.add(delegate)
    session.flush()

    assert delegate.delegation.name == "France"
    assert delegate.delegation.id == "FRA"


def test_create_committee_and_document(session: Session):
    """Test creating a Committee and Document with FK relationship."""
    committee = Committee(
        id="EDU",
        name="Education Committee",
        description="Oversees education policy",
    )
    document = Document(
        id="DOC-2026-0042",
        title="Education Report",
        classification=ClassificationLevel.GENERAL,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    session.add(committee)
    session.add(document)
    session.flush()

    assert document.committee.id == "EDU"
    assert document.committee.name == "Education Committee"


def test_delegate_committee_m2m(session: Session):
    """Test M2M relationship between Delegate and Committee."""
    delegation = Delegation(
        id="GER",
        name="Germany",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-2026-0002",
        full_name="Bob Mueller",
        email="bob@example.com",
        function="Ambassador",
        delegation_id="GER",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee1 = Committee(id="EDU", name="Education")
    committee2 = Committee(id="ENV", name="Environment")

    session.add(delegation)
    session.add(delegate)
    session.add(committee1)
    session.add(committee2)
    session.flush()

    delegate.committees = [committee1, committee2]
    session.flush()

    assert len(delegate.committees) == 2
    committee_ids = {c.id for c in delegate.committees}
    assert committee_ids == {"EDU", "ENV"}


def test_enum_column_storage_and_retrieval(session: Session):
    """Test enum column storage and retrieval."""
    delegation = Delegation(
        id="ITA",
        name="Italy",
        membership_type=MembershipType.MEMBER,
    )
    session.add(delegation)
    session.flush()

    retrieved = session.query(Delegation).filter_by(id="ITA").first()
    assert retrieved.membership_type == MembershipType.MEMBER


def test_classification_level_ordering(session: Session):
    """Test ClassificationLevel ordering comparisons."""
    assert ClassificationLevel.CONFIDENTIAL > ClassificationLevel.RESTRICTED
    assert ClassificationLevel.RESTRICTED > ClassificationLevel.GENERAL
    assert ClassificationLevel.GENERAL > ClassificationLevel.PUBLIC

    assert ClassificationLevel.RESTRICTED >= ClassificationLevel.RESTRICTED
    assert not (ClassificationLevel.PUBLIC >= ClassificationLevel.GENERAL)


def test_meeting_agenda_items_ordered(session: Session):
    """Test MeetingAgendaItem ordering by item_order."""
    committee = Committee(id="EDU", name="Education")
    meeting = Meeting(
        id="MTG-EDU-2026-04",
        committee_id="EDU",
        title="April Meeting",
        date=datetime(2026, 4, 15),
    )
    doc1 = Document(
        id="DOC-001",
        title="Doc 1",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 1),
        last_modified=datetime(2026, 1, 1),
    )
    doc2 = Document(
        id="DOC-002",
        title="Doc 2",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 1),
        last_modified=datetime(2026, 1, 1),
    )
    doc3 = Document(
        id="DOC-003",
        title="Doc 3",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 1),
        last_modified=datetime(2026, 1, 1),
    )

    session.add(committee)
    session.add(meeting)
    session.add_all([doc1, doc2, doc3])
    session.flush()

    item1 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-04",
        document_id="DOC-001",
        item_order=3,
    )
    item2 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-04",
        document_id="DOC-002",
        item_order=1,
    )
    item3 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-04",
        document_id="DOC-003",
        item_order=2,
    )

    session.add_all([item1, item2, item3])
    session.flush()

    retrieved_meeting = session.query(Meeting).filter_by(
        id="MTG-EDU-2026-04"
    ).first()
    orders = [item.item_order for item in retrieved_meeting.agenda_items]
    assert orders == [1, 2, 3]


def test_delegate_role_default(session: Session):
    """
    Test Delegate role defaults to DelegateRole.DELEGATE.

    Persist a Delegate without explicitly setting role. Reload from DB.
    Assert role == DelegateRole.DELEGATE.
    """
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-2026-0001",
        full_name="Alice Dupont",
        email="alice@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
    )
    session.add(delegation)
    session.add(delegate)
    session.flush()

    retrieved = session.query(Delegate).filter_by(
        id="DEL-2026-0001"
    ).first()
    assert retrieved.role == DelegateRole.DELEGATE


def test_delegate_role_editor_roundtrip(session: Session):
    """
    Test Delegate role=DELEGATION_EDITOR persists correctly.

    Persist a Delegate with role=DelegateRole.DELEGATION_EDITOR.
    Reload from DB. Assert role == DelegateRole.DELEGATION_EDITOR.
    """
    delegation = Delegation(
        id="DEU",
        name="Germany",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-2026-0005",
        full_name="Bob Mueller",
        email="bob@example.com",
        function="Representative",
        delegation_id="DEU",
        accreditation_date=datetime(2026, 1, 15),
        role=DelegateRole.DELEGATION_EDITOR,
    )
    session.add(delegation)
    session.add(delegate)
    session.flush()

    retrieved = session.query(Delegate).filter_by(
        id="DEL-2026-0005"
    ).first()
    assert retrieved.role == DelegateRole.DELEGATION_EDITOR


def test_approval_status_contains_required_values():
    """
    Test ApprovalStatus enum contains required approval values.

    Assert that {AUTO_APPROVED, PENDING_DELEGATION_HEAD,
    PENDING_SECRETARIAT} is a subset of set(ApprovalStatus).
    """
    approval_statuses = set(ApprovalStatus)

    required_statuses = {
        ApprovalStatus.AUTO_APPROVED,
        ApprovalStatus.PENDING_DELEGATION_HEAD,
        ApprovalStatus.PENDING_SECRETARIAT,
    }

    assert required_statuses.issubset(approval_statuses)


def test_document_access_right_retroactive_default(session: Session):
    """
    Test DocumentAccessRight.retroactive defaults to False.

    Persist a DAR without setting retroactive. Reload from DB.
    Assert retroactive == False.
    """
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    committee = Committee(
        id="EDU",
        name="Education Committee",
    )
    delegate = Delegate(
        id="DEL-2026-0001",
        full_name="Alice Dupont",
        email="alice@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
    )
    session.add_all([delegation, committee, delegate])
    session.flush()

    dar = DocumentAccessRight(
        delegate_id="DEL-2026-0001",
        committee_id="EDU",
        classification_level=ClassificationLevel.GENERAL,
        approval_status=ApprovalStatus.AUTO_APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="DEL-2026-0001",
    )
    session.add(dar)
    session.flush()

    retrieved = session.query(DocumentAccessRight).filter_by(
        delegate_id="DEL-2026-0001"
    ).first()
    assert retrieved.retroactive is False
