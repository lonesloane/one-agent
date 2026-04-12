"""ONE-MP Agent PoC shared data layer - Business rules and domain logic.

This module contains the single source of truth for domain business rules
and logic. All application code should use these functions to make
decisions about access control, visibility, and approval workflows.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from shared.database import (
    ClassificationLevel,
    MembershipType,
    ApprovalStatus,
    Document,
    DocumentAccessRight,
    FrameworkAgreement,
    MeetingAgendaItem,
)


def compute_default_access_level(
    membership_type: MembershipType,
    committee_id: str,
    framework_agreements: list[FrameworkAgreement],
) -> ClassificationLevel:
    """
    Compute the default access classification level for a delegation.

    Members always get RESTRICTED access. Partners get GENERAL access
    unless they have an active framework agreement for the committee,
    which grants RESTRICTED access.

    Args:
        membership_type: The membership type of the delegation
        committee_id: The committee identifier to check
        framework_agreements: List of framework agreements for the
            delegation

    Returns:
        The default classification level for the delegation
    """
    if membership_type == MembershipType.MEMBER:
        return ClassificationLevel.RESTRICTED

    # For partners, check for active framework agreement
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for fa in framework_agreements:
        if fa.committee_id == committee_id:
            # Agreement is active if end_date is None or in the future
            if fa.end_date is None or fa.end_date > now:
                return ClassificationLevel.RESTRICTED

    # Partner without active FA on this committee
    return ClassificationLevel.GENERAL


def determine_approval_route(
    classification_level: ClassificationLevel,
    retroactive: bool,
) -> ApprovalStatus:
    """
    Determine the approval route for a document access request.

    Retroactive requests always go to secretariat. CONFIDENTIAL documents
    require secretariat approval. RESTRICTED requires delegation head
    approval. GENERAL and PUBLIC are auto-approved.

    Args:
        classification_level: The classification level of the document
        retroactive: Whether the access applies retroactively

    Returns:
        The appropriate approval status for the request
    """
    if retroactive:
        return ApprovalStatus.PENDING_SECRETARIAT

    if classification_level == ClassificationLevel.CONFIDENTIAL:
        return ApprovalStatus.PENDING_SECRETARIAT

    if classification_level == ClassificationLevel.RESTRICTED:
        return ApprovalStatus.PENDING_DELEGATION_HEAD

    return ApprovalStatus.AUTO_APPROVED


def is_document_visible(
    delegate_id: str,
    document: Document,
    session: Session,
) -> bool:
    """
    Determine if a delegate can see a specific document.

    A document is visible if the delegate has an approved or
    auto-approved access right for the document's committee with a
    classification level that permits access to the document's
    classification level.

    Args:
        delegate_id: The delegate identifier
        document: The document to check visibility for
        session: SQLAlchemy session for database queries

    Returns:
        True if the delegate can see the document, False otherwise
    """
    # Query document access rights that grant visibility
    stmt = select(DocumentAccessRight).where(
        DocumentAccessRight.delegate_id == delegate_id,
        DocumentAccessRight.committee_id == document.committee_id,
        DocumentAccessRight.approval_status.in_(
            (ApprovalStatus.AUTO_APPROVED, ApprovalStatus.APPROVED)
        ),
    )
    access_rights = session.scalars(stmt).all()

    # Check if any access right permits this classification level
    for dar in access_rights:
        if dar.classification_level >= document.classification:
            return True

    return False


def get_visible_agenda_documents(
    delegate_id: str,
    meeting_id: str,
    session: Session,
) -> list[Document]:
    """
    Get all agenda documents for a meeting that a delegate can see.

    Returns documents in agenda order, filtered by visibility based
    on the delegate's document access rights.

    Args:
        delegate_id: The delegate identifier
        meeting_id: The meeting identifier
        session: SQLAlchemy session for database queries

    Returns:
        List of visible documents in agenda item order
    """
    # Query agenda items for this meeting, ordered by item_order
    stmt = select(MeetingAgendaItem).where(
        MeetingAgendaItem.meeting_id == meeting_id
    ).order_by(MeetingAgendaItem.item_order)
    agenda_items = session.scalars(stmt).all()

    # Filter documents by visibility
    visible_documents = []
    for item in agenda_items:
        # Agenda items have document relationship loaded
        if is_document_visible(delegate_id, item.document, session):
            visible_documents.append(item.document)

    return visible_documents


def get_new_documents_since(
    delegate_last_login: datetime | None,
    meeting_id: str,
    session: Session,
) -> list[Document]:
    """
    Get all agenda documents modified since a delegate's last login.

    Returns documents that were modified after the delegate's last login
    timestamp. If the delegate has never logged in, returns an empty list.

    Args:
        delegate_last_login: The delegate's last login timestamp, or None
        meeting_id: The meeting identifier
        session: SQLAlchemy session for database queries

    Returns:
        List of documents modified since last login, in agenda order
    """
    if delegate_last_login is None:
        return []

    # Get all agenda items for this meeting
    stmt = select(MeetingAgendaItem).where(
        MeetingAgendaItem.meeting_id == meeting_id
    ).order_by(MeetingAgendaItem.item_order)
    agenda_items = session.scalars(stmt).all()

    # Filter by modification date
    new_documents = [
        item.document
        for item in agenda_items
        if item.document.last_modified > delegate_last_login
    ]

    return new_documents
