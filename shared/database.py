"""ONE-MP Agent PoC shared data layer - SQLAlchemy ORM models and enums."""

from enum import Enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Table,
    PrimaryKeyConstraint,
    create_engine,
    Engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


# ============================================================================
# Enums
# ============================================================================


class MembershipType(Enum):
    """Enumeration of delegation membership types."""

    MEMBER = "MEMBER"
    PARTNER = "PARTNER"


# Mapping of classification level values to order for comparison
_CLASSIFICATION_ORDER = {
    "PUBLIC": 0,
    "GENERAL": 1,
    "RESTRICTED": 2,
    "CONFIDENTIAL": 3,
}


class ClassificationLevel(Enum):
    """
    Enumeration of document classification levels.

    Supports ordered comparison. Order is PUBLIC < GENERAL < RESTRICTED
    < CONFIDENTIAL.
    """

    PUBLIC = "PUBLIC"
    GENERAL = "GENERAL"
    RESTRICTED = "RESTRICTED"
    CONFIDENTIAL = "CONFIDENTIAL"

    def __ge__(self, other: "ClassificationLevel") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, ClassificationLevel):
            return NotImplemented
        return (
            _CLASSIFICATION_ORDER[self.value]
            >= _CLASSIFICATION_ORDER[other.value]
        )

    def __le__(self, other: "ClassificationLevel") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, ClassificationLevel):
            return NotImplemented
        return (
            _CLASSIFICATION_ORDER[self.value]
            <= _CLASSIFICATION_ORDER[other.value]
        )

    def __gt__(self, other: "ClassificationLevel") -> bool:
        """Greater than comparison."""
        if not isinstance(other, ClassificationLevel):
            return NotImplemented
        return (
            _CLASSIFICATION_ORDER[self.value]
            > _CLASSIFICATION_ORDER[other.value]
        )

    def __lt__(self, other: "ClassificationLevel") -> bool:
        """Less than comparison."""
        if not isinstance(other, ClassificationLevel):
            return NotImplemented
        return (
            _CLASSIFICATION_ORDER[self.value]
            < _CLASSIFICATION_ORDER[other.value]
        )


class ApprovalStatus(Enum):
    """
    Enumeration of document access right approval statuses.

    Maps PRD approval routes to enum values:
        AUTO_APPROVED: PRD "auto-approved route" — GENERAL and PUBLIC
            classification levels with retroactive=False
        PENDING_DELEGATION_HEAD: PRD "pending_delegation_head" —
            RESTRICTED classification level with retroactive=False
        PENDING_SECRETARIAT: PRD "pending_secretariat" — CONFIDENTIAL
            classification or retroactive=True for any classification
        APPROVED: Access right has been approved by delegation head
        REJECTED: Access right has been rejected
    """

    AUTO_APPROVED = "AUTO_APPROVED"
    PENDING_DELEGATION_HEAD = "PENDING_DELEGATION_HEAD"
    PENDING_SECRETARIAT = "PENDING_SECRETARIAT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DelegateRole(Enum):
    """
    Enumeration of delegate role types.

    Defines the roles a delegate can have within a delegation:
        DELEGATE: Standard delegate with basic privileges
        DELEGATION_EDITOR: Delegate with delegation management privileges
    """

    DELEGATE = "DELEGATE"
    DELEGATION_EDITOR = "DELEGATION_EDITOR"


# ============================================================================
# SQLAlchemy Base and Association Tables
# ============================================================================


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


# Association table for many-to-many relationship between Delegate and
# Committee
delegate_committees = Table(
    "delegate_committees",
    Base.metadata,
    Column("delegate_id", String, ForeignKey("delegates.id")),
    Column("committee_id", String, ForeignKey("committees.id")),
    PrimaryKeyConstraint("delegate_id", "committee_id"),
)


# ============================================================================
# ORM Models
# ============================================================================


class Delegation(Base):
    """
    Represents a delegation entity in the system.

    Attributes:
        id: Unique identifier for the delegation (e.g., "FRA")
        name: Full name of the delegation
        membership_type: Type of membership (MEMBER or PARTNER)
        delegates: List of delegates belonging to this delegation
        framework_agreements: List of framework agreements for this
            delegation
    """

    __tablename__ = "delegations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    membership_type = Column(
        SQLEnum(MembershipType, native_enum=False),
        nullable=False,
    )

    delegates = relationship(
        "Delegate",
        back_populates="delegation",
        cascade="all, delete-orphan",
    )
    framework_agreements = relationship(
        "FrameworkAgreement",
        cascade="all, delete-orphan",
    )


class Committee(Base):
    """
    Represents a committee in the system.

    Attributes:
        id: Unique identifier for the committee (e.g., "EDU")
        name: Full name of the committee
        description: Optional description of the committee
    """

    __tablename__ = "committees"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)


class Delegate(Base):
    """
    Represents a delegate (representative) in the system.

    Attributes:
        id: Unique identifier for the delegate (e.g., "DEL-2026-0001")
        full_name: Full name of the delegate
        email: Email address of the delegate
        function: Function or role of the delegate
        title: Optional title of the delegate
        delegation_id: Foreign key reference to the delegation
        accreditation_date: Date when the delegate was accredited
        is_active: Whether the delegate is currently active
        last_login: Optional timestamp of last login
        role: Role of the delegate within the delegation
        delegation: Reference to the parent delegation
        committees: List of committees the delegate is member of
        document_access_rights: List of document access rights granted
            to this delegate
    """

    __tablename__ = "delegates"

    id = Column(String, primary_key=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    function = Column(String, nullable=False)
    title = Column(String, nullable=True)
    delegation_id = Column(
        String,
        ForeignKey("delegations.id"),
        nullable=False,
    )
    accreditation_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime, nullable=True)
    role = Column(
        SQLEnum(DelegateRole, native_enum=False),
        nullable=False,
        server_default=DelegateRole.DELEGATE.value,
        default=DelegateRole.DELEGATE,
    )

    delegation = relationship("Delegation", back_populates="delegates")
    committees = relationship(
        "Committee",
        secondary=delegate_committees,
        overlaps="delegate_committees",
    )
    document_access_rights = relationship(
        "DocumentAccessRight",
        back_populates="delegate",
        cascade="all, delete-orphan",
    )


class FrameworkAgreement(Base):
    """
    Represents a framework agreement between a delegation and committee.

    Attributes:
        id: Unique auto-incrementing identifier
        delegation_id: Foreign key reference to the delegation
        committee_id: Foreign key reference to the committee
        start_date: Date when the agreement becomes effective
        end_date: Optional date when the agreement expires (None = ongoing)
        delegation: Reference to the delegation
        committee: Reference to the committee
    """

    __tablename__ = "framework_agreements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delegation_id = Column(
        String,
        ForeignKey("delegations.id"),
        nullable=False,
    )
    committee_id = Column(
        String,
        ForeignKey("committees.id"),
        nullable=False,
    )
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)

    delegation = relationship(
        "Delegation",
        overlaps="framework_agreements",
    )
    committee = relationship("Committee")


class Document(Base):
    """
    Represents a document in the system.

    Attributes:
        id: Unique identifier for the document (e.g., "DOC-2026-0042")
        title: Title of the document
        classification: Classification level of the document
        committee_id: Foreign key reference to the responsible committee
        publication_date: Date when the document was published
        last_modified: Date when the document was last modified
        summary: Optional summary of the document content
        committee: Reference to the responsible committee
    """

    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    classification = Column(
        SQLEnum(ClassificationLevel, native_enum=False),
        nullable=False,
    )
    committee_id = Column(
        String,
        ForeignKey("committees.id"),
        nullable=False,
    )
    publication_date = Column(DateTime, nullable=False)
    last_modified = Column(DateTime, nullable=False)
    summary = Column(String, nullable=True)

    committee = relationship("Committee")


class DocumentAccessRight(Base):
    """
    Represents access rights of a delegate to documents in a committee.

    Attributes:
        id: Unique auto-incrementing identifier
        delegate_id: Foreign key reference to the delegate
        committee_id: Foreign key reference to the committee
        classification_level: Maximum classification level the delegate
            can access
        retroactive: Whether this right applies to past documents
        approval_status: Current approval status of the access right
        created_at: Timestamp when the access right was created
        created_by: Identifier of the user who created this access right
        delegate: Reference to the delegate
        committee: Reference to the committee
    """

    __tablename__ = "document_access_rights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delegate_id = Column(
        String,
        ForeignKey("delegates.id"),
        nullable=False,
    )
    committee_id = Column(
        String,
        ForeignKey("committees.id"),
        nullable=False,
    )
    classification_level = Column(
        SQLEnum(ClassificationLevel, native_enum=False),
        nullable=False,
    )
    retroactive = Column(Boolean, nullable=False, default=False)
    approval_status = Column(
        SQLEnum(ApprovalStatus, native_enum=False),
        nullable=False,
    )
    created_at = Column(DateTime, nullable=False)
    created_by = Column(String, nullable=False)

    delegate = relationship(
        "Delegate",
        back_populates="document_access_rights",
    )
    committee = relationship("Committee")


class Meeting(Base):
    """
    Represents a committee meeting in the system.

    Attributes:
        id: Unique identifier for the meeting (e.g., "MTG-EDU-2026-04")
        committee_id: Foreign key reference to the committee
        title: Title of the meeting
        date: Date and time of the meeting
        location: Optional location of the meeting
        committee: Reference to the committee
        agenda_items: Ordered list of agenda items for this meeting
    """

    __tablename__ = "meetings"

    id = Column(String, primary_key=True)
    committee_id = Column(
        String,
        ForeignKey("committees.id"),
        nullable=False,
    )
    title = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    location = Column(String, nullable=True)

    committee = relationship("Committee")
    agenda_items = relationship(
        "MeetingAgendaItem",
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="MeetingAgendaItem.item_order",
    )


class MeetingAgendaItem(Base):
    """
    Represents an item on a meeting agenda.

    Attributes:
        id: Unique auto-incrementing identifier
        meeting_id: Foreign key reference to the meeting
        document_id: Foreign key reference to the document
        item_order: Ordering position of this item in the agenda
        meeting: Reference to the meeting
        document: Reference to the document
    """

    __tablename__ = "meeting_agenda_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(
        String,
        ForeignKey("meetings.id"),
        nullable=False,
    )
    document_id = Column(
        String,
        ForeignKey("documents.id"),
        nullable=False,
    )
    item_order = Column(Integer, nullable=False)

    meeting = relationship(
        "Meeting",
        back_populates="agenda_items",
    )
    document = relationship("Document")


# ============================================================================
# Utility Functions
# ============================================================================


def get_engine(db_path: str) -> Engine:
    """
    Create a SQLAlchemy engine for the given SQLite database path.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Configured SQLAlchemy engine instance
    """
    return create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )


def init_db(engine: Engine) -> None:
    """
    Create all tables defined in Base.metadata.

    Args:
        engine: SQLAlchemy engine to use for table creation
    """
    Base.metadata.create_all(engine)
