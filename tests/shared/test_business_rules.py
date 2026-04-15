"""Tests for shared.business_rules domain logic."""
from datetime import datetime
from typing import NamedTuple

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
    ApprovalStatus,
    FrameworkAgreement,
)
from shared.business_rules import (
    compute_default_access_level,
    determine_approval_route,
    is_document_visible,
    get_visible_agenda_documents,
    get_new_documents_since,
)


class MockFrameworkAgreement(NamedTuple):
    """Mock framework agreement for testing."""

    committee_id: str
    end_date: datetime | None


# ============================================================================
# TASK-037: compute_default_access_level Tests
# ============================================================================


def test_member_gets_restricted():
    """Test MEMBER membership type gets RESTRICTED access."""
    result = compute_default_access_level(
        MembershipType.MEMBER,
        "EDU",
        [],
    )
    assert result == ClassificationLevel.RESTRICTED


def test_partner_gets_general():
    """Test PARTNER with no FAs gets GENERAL access."""
    result = compute_default_access_level(
        MembershipType.PARTNER,
        "EDU",
        [],
    )
    assert result == ClassificationLevel.GENERAL


def test_partner_with_active_fa_gets_restricted():
    """Test PARTNER with active FA gets RESTRICTED access."""
    fa = MockFrameworkAgreement(
        committee_id="EDU",
        end_date=None,
    )
    result = compute_default_access_level(
        MembershipType.PARTNER,
        "EDU",
        [fa],
    )
    assert result == ClassificationLevel.RESTRICTED


def test_partner_with_expired_fa_gets_general():
    """Test PARTNER with expired FA gets GENERAL access."""
    fa = MockFrameworkAgreement(
        committee_id="EDU",
        end_date=datetime(2025, 12, 31),
    )
    result = compute_default_access_level(
        MembershipType.PARTNER,
        "EDU",
        [fa],
    )
    assert result == ClassificationLevel.GENERAL


# ============================================================================
# TASK-038: determine_approval_route Tests
# ============================================================================


def test_general_auto_approved():
    """Test GENERAL classification auto-approves."""
    result = determine_approval_route(ClassificationLevel.GENERAL, False)
    assert result == ApprovalStatus.AUTO_APPROVED


def test_public_auto_approved():
    """Test PUBLIC classification auto-approves."""
    result = determine_approval_route(ClassificationLevel.PUBLIC, False)
    assert result == ApprovalStatus.AUTO_APPROVED


def test_restricted_pending_delegation_head():
    """Test RESTRICTED requires delegation head approval."""
    result = determine_approval_route(
        ClassificationLevel.RESTRICTED,
        False,
    )
    assert result == ApprovalStatus.PENDING_DELEGATION_HEAD


def test_confidential_pending_secretariat():
    """Test CONFIDENTIAL requires secretariat approval."""
    result = determine_approval_route(
        ClassificationLevel.CONFIDENTIAL,
        False,
    )
    assert result == ApprovalStatus.PENDING_SECRETARIAT


def test_retroactive_general_pending_secretariat():
    """Test retroactive GENERAL requires secretariat approval."""
    result = determine_approval_route(ClassificationLevel.GENERAL, True)
    assert result == ApprovalStatus.PENDING_SECRETARIAT


def test_retroactive_restricted_pending_secretariat():
    """Test retroactive RESTRICTED requires secretariat approval."""
    result = determine_approval_route(
        ClassificationLevel.RESTRICTED,
        True,
    )
    assert result == ApprovalStatus.PENDING_SECRETARIAT


def test_retroactive_confidential_pending_secretariat():
    """
    Test retroactive CONFIDENTIAL requires secretariat approval.

    Assert determine_approval_route(ClassificationLevel.CONFIDENTIAL,
    True) == ApprovalStatus.PENDING_SECRETARIAT. Closes the
    retroactive coverage matrix — GENERAL and RESTRICTED already
    tested.
    """
    result = determine_approval_route(
        ClassificationLevel.CONFIDENTIAL,
        True,
    )
    assert result == ApprovalStatus.PENDING_SECRETARIAT


# ============================================================================
# TASK-039: is_document_visible Tests
# ============================================================================


def test_restricted_dar_sees_public(session: Session):
    """Test RESTRICTED DAR can see PUBLIC document."""
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-001",
        full_name="Alice",
        email="alice@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    document = Document(
        id="DOC-001",
        title="Public Doc",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    dar = DocumentAccessRight(
        delegate_id="DEL-001",
        committee_id="EDU",
        classification_level=ClassificationLevel.RESTRICTED,
        approval_status=ApprovalStatus.APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.add(dar)
    session.flush()

    assert is_document_visible("DEL-001", document, session) is True


def test_restricted_dar_sees_general(session: Session):
    """Test RESTRICTED DAR can see GENERAL document."""
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-002",
        full_name="Bob",
        email="bob@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    document = Document(
        id="DOC-002",
        title="General Doc",
        classification=ClassificationLevel.GENERAL,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    dar = DocumentAccessRight(
        delegate_id="DEL-002",
        committee_id="EDU",
        classification_level=ClassificationLevel.RESTRICTED,
        approval_status=ApprovalStatus.APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.add(dar)
    session.flush()

    assert is_document_visible("DEL-002", document, session) is True


def test_restricted_dar_sees_restricted(session: Session):
    """Test RESTRICTED DAR can see RESTRICTED document."""
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-003",
        full_name="Charlie",
        email="charlie@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    document = Document(
        id="DOC-003",
        title="Restricted Doc",
        classification=ClassificationLevel.RESTRICTED,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    dar = DocumentAccessRight(
        delegate_id="DEL-003",
        committee_id="EDU",
        classification_level=ClassificationLevel.RESTRICTED,
        approval_status=ApprovalStatus.APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.add(dar)
    session.flush()

    assert is_document_visible("DEL-003", document, session) is True


def test_restricted_dar_cannot_see_confidential(session: Session):
    """Test RESTRICTED DAR cannot see CONFIDENTIAL document."""
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-004",
        full_name="Diana",
        email="diana@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    document = Document(
        id="DOC-004",
        title="Confidential Doc",
        classification=ClassificationLevel.CONFIDENTIAL,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    dar = DocumentAccessRight(
        delegate_id="DEL-004",
        committee_id="EDU",
        classification_level=ClassificationLevel.RESTRICTED,
        approval_status=ApprovalStatus.APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.add(dar)
    session.flush()

    assert is_document_visible("DEL-004", document, session) is False


def test_general_dar_sees_public(session: Session):
    """Test GENERAL DAR can see PUBLIC document."""
    delegation = Delegation(
        id="DEU",
        name="Germany",
        membership_type=MembershipType.PARTNER,
    )
    delegate = Delegate(
        id="DEL-005",
        full_name="Eve",
        email="eve@example.com",
        function="Representative",
        delegation_id="DEU",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="ENV", name="Environment")
    document = Document(
        id="DOC-005",
        title="Public Doc",
        classification=ClassificationLevel.PUBLIC,
        committee_id="ENV",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    dar = DocumentAccessRight(
        delegate_id="DEL-005",
        committee_id="ENV",
        classification_level=ClassificationLevel.GENERAL,
        approval_status=ApprovalStatus.AUTO_APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.add(dar)
    session.flush()

    assert is_document_visible("DEL-005", document, session) is True


def test_general_dar_cannot_see_restricted(session: Session):
    """Test GENERAL DAR cannot see RESTRICTED document."""
    delegation = Delegation(
        id="DEU",
        name="Germany",
        membership_type=MembershipType.PARTNER,
    )
    delegate = Delegate(
        id="DEL-006",
        full_name="Frank",
        email="frank@example.com",
        function="Representative",
        delegation_id="DEU",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="ENV", name="Environment")
    document = Document(
        id="DOC-006",
        title="Restricted Doc",
        classification=ClassificationLevel.RESTRICTED,
        committee_id="ENV",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    dar = DocumentAccessRight(
        delegate_id="DEL-006",
        committee_id="ENV",
        classification_level=ClassificationLevel.GENERAL,
        approval_status=ApprovalStatus.AUTO_APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.add(dar)
    session.flush()

    assert is_document_visible("DEL-006", document, session) is False


def test_pending_dar_grants_no_access(session: Session):
    """Test PENDING DAR grants no access (REQ-004)."""
    delegation = Delegation(
        id="ITA",
        name="Italy",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-007",
        full_name="Grace",
        email="grace@example.com",
        function="Representative",
        delegation_id="ITA",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    document = Document(
        id="DOC-007",
        title="Restricted Doc",
        classification=ClassificationLevel.RESTRICTED,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    dar = DocumentAccessRight(
        delegate_id="DEL-007",
        committee_id="EDU",
        classification_level=ClassificationLevel.RESTRICTED,
        approval_status=ApprovalStatus.PENDING_DELEGATION_HEAD,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.add(dar)
    session.flush()

    assert is_document_visible("DEL-007", document, session) is False


def test_no_dar_grants_no_access(session: Session):
    """Test delegate with no DAR cannot see any document."""
    delegation = Delegation(
        id="ESP",
        name="Spain",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-008",
        full_name="Henry",
        email="henry@example.com",
        function="Representative",
        delegation_id="ESP",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    document = Document(
        id="DOC-008",
        title="Public Doc",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.flush()

    assert is_document_visible("DEL-008", document, session) is False


def test_approved_dar_same_as_auto_approved(session: Session):
    """Test APPROVED DAR works same as AUTO_APPROVED."""
    delegation = Delegation(
        id="GRC",
        name="Greece",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-009",
        full_name="Iris",
        email="iris@example.com",
        function="Representative",
        delegation_id="GRC",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="ENV", name="Environment")
    document = Document(
        id="DOC-009",
        title="Restricted Doc",
        classification=ClassificationLevel.RESTRICTED,
        committee_id="ENV",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    dar = DocumentAccessRight(
        delegate_id="DEL-009",
        committee_id="ENV",
        classification_level=ClassificationLevel.RESTRICTED,
        approval_status=ApprovalStatus.APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(document)
    session.add(dar)
    session.flush()

    assert is_document_visible("DEL-009", document, session) is True


# ============================================================================
# TASK-040: get_visible_agenda_documents Tests
# ============================================================================


def test_restricted_dar_sees_three_docs(session: Session):
    """Test RESTRICTED DAR sees 3 docs (PUBLIC, GENERAL, RESTRICTED)."""
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-101",
        full_name="Jack",
        email="jack@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    meeting = Meeting(
        id="MTG-EDU-2026-04",
        committee_id="EDU",
        title="April Meeting",
        date=datetime(2026, 4, 15),
    )

    doc_public = Document(
        id="DOC-PUB",
        title="Public Doc",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    doc_general = Document(
        id="DOC-GEN",
        title="General Doc",
        classification=ClassificationLevel.GENERAL,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    doc_restricted = Document(
        id="DOC-RES",
        title="Restricted Doc",
        classification=ClassificationLevel.RESTRICTED,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    doc_confidential = Document(
        id="DOC-CONF",
        title="Confidential Doc",
        classification=ClassificationLevel.CONFIDENTIAL,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )

    dar = DocumentAccessRight(
        delegate_id="DEL-101",
        committee_id="EDU",
        classification_level=ClassificationLevel.RESTRICTED,
        approval_status=ApprovalStatus.APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(meeting)
    session.add_all([doc_public, doc_general, doc_restricted,
                     doc_confidential])
    session.add(dar)
    session.flush()

    item1 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-04",
        document_id="DOC-PUB",
        item_order=1,
    )
    item2 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-04",
        document_id="DOC-GEN",
        item_order=2,
    )
    item3 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-04",
        document_id="DOC-RES",
        item_order=3,
    )
    item4 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-04",
        document_id="DOC-CONF",
        item_order=4,
    )
    session.add_all([item1, item2, item3, item4])
    session.flush()

    visible = get_visible_agenda_documents(
        "DEL-101",
        "MTG-EDU-2026-04",
        session,
    )
    assert len(visible) == 3
    doc_ids = {d.id for d in visible}
    assert doc_ids == {"DOC-PUB", "DOC-GEN", "DOC-RES"}


def test_general_dar_sees_two_docs(session: Session):
    """Test GENERAL DAR sees 2 docs (PUBLIC, GENERAL)."""
    delegation = Delegation(
        id="DEU",
        name="Germany",
        membership_type=MembershipType.PARTNER,
    )
    delegate = Delegate(
        id="DEL-102",
        full_name="Kate",
        email="kate@example.com",
        function="Representative",
        delegation_id="DEU",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="ENV", name="Environment")
    meeting = Meeting(
        id="MTG-ENV-2026-04",
        committee_id="ENV",
        title="April Meeting",
        date=datetime(2026, 4, 15),
    )

    doc_public = Document(
        id="DOC-PUB2",
        title="Public Doc",
        classification=ClassificationLevel.PUBLIC,
        committee_id="ENV",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    doc_general = Document(
        id="DOC-GEN2",
        title="General Doc",
        classification=ClassificationLevel.GENERAL,
        committee_id="ENV",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    doc_restricted = Document(
        id="DOC-RES2",
        title="Restricted Doc",
        classification=ClassificationLevel.RESTRICTED,
        committee_id="ENV",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )

    dar = DocumentAccessRight(
        delegate_id="DEL-102",
        committee_id="ENV",
        classification_level=ClassificationLevel.GENERAL,
        approval_status=ApprovalStatus.AUTO_APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(meeting)
    session.add_all([doc_public, doc_general, doc_restricted])
    session.add(dar)
    session.flush()

    item1 = MeetingAgendaItem(
        meeting_id="MTG-ENV-2026-04",
        document_id="DOC-PUB2",
        item_order=1,
    )
    item2 = MeetingAgendaItem(
        meeting_id="MTG-ENV-2026-04",
        document_id="DOC-GEN2",
        item_order=2,
    )
    item3 = MeetingAgendaItem(
        meeting_id="MTG-ENV-2026-04",
        document_id="DOC-RES2",
        item_order=3,
    )
    session.add_all([item1, item2, item3])
    session.flush()

    visible = get_visible_agenda_documents(
        "DEL-102",
        "MTG-ENV-2026-04",
        session,
    )
    assert len(visible) == 2
    doc_ids = {d.id for d in visible}
    assert doc_ids == {"DOC-PUB2", "DOC-GEN2"}


def test_results_in_item_order(session: Session):
    """Test results are in ascending item_order."""
    delegation = Delegation(
        id="ITA",
        name="Italy",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-103",
        full_name="Leo",
        email="leo@example.com",
        function="Representative",
        delegation_id="ITA",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    meeting = Meeting(
        id="MTG-EDU-2026-05",
        committee_id="EDU",
        title="May Meeting",
        date=datetime(2026, 5, 15),
    )

    doc4 = Document(
        id="DOC-04",
        title="Doc 4",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    doc1 = Document(
        id="DOC-01",
        title="Doc 1",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    doc3 = Document(
        id="DOC-03",
        title="Doc 3",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )
    doc2 = Document(
        id="DOC-02",
        title="Doc 2",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 1, 15),
        last_modified=datetime(2026, 1, 15),
    )

    dar = DocumentAccessRight(
        delegate_id="DEL-103",
        committee_id="EDU",
        classification_level=ClassificationLevel.RESTRICTED,
        approval_status=ApprovalStatus.APPROVED,
        created_at=datetime(2026, 1, 15),
        created_by="ADMIN",
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(meeting)
    session.add_all([doc4, doc1, doc3, doc2])
    session.add(dar)
    session.flush()

    item4 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-05",
        document_id="DOC-04",
        item_order=4,
    )
    item1 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-05",
        document_id="DOC-01",
        item_order=1,
    )
    item3 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-05",
        document_id="DOC-03",
        item_order=3,
    )
    item2 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-05",
        document_id="DOC-02",
        item_order=2,
    )
    session.add_all([item4, item1, item3, item2])
    session.flush()

    visible = get_visible_agenda_documents(
        "DEL-103",
        "MTG-EDU-2026-05",
        session,
    )
    doc_ids = [d.id for d in visible]
    assert doc_ids == ["DOC-01", "DOC-02", "DOC-03", "DOC-04"]


# ============================================================================
# TASK-041: get_new_documents_since Tests
# ============================================================================


def test_returns_docs_modified_after_login(session: Session):
    """Test returns docs modified after last_login."""
    delegation = Delegation(
        id="FRA",
        name="France",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-201",
        full_name="Mike",
        email="mike@example.com",
        function="Representative",
        delegation_id="FRA",
        accreditation_date=datetime(2026, 1, 15),
        last_login=datetime(2026, 4, 5),
    )
    committee = Committee(id="EDU", name="Education")
    meeting = Meeting(
        id="MTG-EDU-2026-06",
        committee_id="EDU",
        title="June Meeting",
        date=datetime(2026, 6, 15),
    )

    doc1 = Document(
        id="DOC-201-1",
        title="Doc 1",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 4, 1),
        last_modified=datetime(2026, 4, 1),
    )
    doc2 = Document(
        id="DOC-201-2",
        title="Doc 2",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 4, 9),
        last_modified=datetime(2026, 4, 9),
    )
    doc3 = Document(
        id="DOC-201-3",
        title="Doc 3",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 4, 11),
        last_modified=datetime(2026, 4, 11),
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(meeting)
    session.add_all([doc1, doc2, doc3])
    session.flush()

    item1 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-06",
        document_id="DOC-201-1",
        item_order=1,
    )
    item2 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-06",
        document_id="DOC-201-2",
        item_order=2,
    )
    item3 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-06",
        document_id="DOC-201-3",
        item_order=3,
    )
    session.add_all([item1, item2, item3])
    session.flush()

    result = get_new_documents_since(
        datetime(2026, 4, 5),
        "MTG-EDU-2026-06",
        session,
    )
    assert len(result) == 2
    doc_ids = {d.id for d in result}
    assert doc_ids == {"DOC-201-2", "DOC-201-3"}


def test_returns_empty_for_none_login(session: Session):
    """Test returns empty list when last_login is None."""
    delegation = Delegation(
        id="DEU",
        name="Germany",
        membership_type=MembershipType.PARTNER,
    )
    delegate = Delegate(
        id="DEL-202",
        full_name="Nancy",
        email="nancy@example.com",
        function="Representative",
        delegation_id="DEU",
        accreditation_date=datetime(2026, 1, 15),
        last_login=None,
    )
    committee = Committee(id="ENV", name="Environment")
    meeting = Meeting(
        id="MTG-ENV-2026-06",
        committee_id="ENV",
        title="June Meeting",
        date=datetime(2026, 6, 15),
    )

    doc1 = Document(
        id="DOC-202-1",
        title="Doc 1",
        classification=ClassificationLevel.PUBLIC,
        committee_id="ENV",
        publication_date=datetime(2026, 4, 1),
        last_modified=datetime(2026, 4, 1),
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(meeting)
    session.add(doc1)
    session.flush()

    item1 = MeetingAgendaItem(
        meeting_id="MTG-ENV-2026-06",
        document_id="DOC-202-1",
        item_order=1,
    )
    session.add(item1)
    session.flush()

    result = get_new_documents_since(None, "MTG-ENV-2026-06", session)
    assert result == []


def test_returns_empty_when_all_before_login(session: Session):
    """Test returns empty when all docs are before last_login."""
    delegation = Delegation(
        id="ESP",
        name="Spain",
        membership_type=MembershipType.MEMBER,
    )
    delegate = Delegate(
        id="DEL-203",
        full_name="Oscar",
        email="oscar@example.com",
        function="Representative",
        delegation_id="ESP",
        accreditation_date=datetime(2026, 1, 15),
    )
    committee = Committee(id="EDU", name="Education")
    meeting = Meeting(
        id="MTG-EDU-2026-07",
        committee_id="EDU",
        title="July Meeting",
        date=datetime(2026, 7, 15),
    )

    doc1 = Document(
        id="DOC-203-1",
        title="Doc 1",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 4, 1),
        last_modified=datetime(2026, 4, 1),
    )
    doc2 = Document(
        id="DOC-203-2",
        title="Doc 2",
        classification=ClassificationLevel.PUBLIC,
        committee_id="EDU",
        publication_date=datetime(2026, 4, 9),
        last_modified=datetime(2026, 4, 9),
    )

    session.add(delegation)
    session.add(delegate)
    session.add(committee)
    session.add(meeting)
    session.add_all([doc1, doc2])
    session.flush()

    item1 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-07",
        document_id="DOC-203-1",
        item_order=1,
    )
    item2 = MeetingAgendaItem(
        meeting_id="MTG-EDU-2026-07",
        document_id="DOC-203-2",
        item_order=2,
    )
    session.add_all([item1, item2])
    session.flush()

    result = get_new_documents_since(
        datetime(2026, 4, 12),
        "MTG-EDU-2026-07",
        session,
    )
    assert result == []
