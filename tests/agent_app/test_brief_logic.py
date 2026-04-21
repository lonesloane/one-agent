"""Tests for the proactive brief trigger and suppression conditions.

These tests verify the data conditions that drive the agent's
brief-or-suppress decision (BRIEF_LOOKBACK_DAYS) by calling the
tool sequence directly with a mock DB engine. No live agent loop
is started — see plan/phase3d.md RISK-001 for the rationale.

Logic under test:
  - Brief FIRES   when get_agenda_documents returns a doc whose
    last_modified is within the past BRIEF_LOOKBACK_DAYS days.
  - Brief SUPPRESSED when no docs are recent (older than lookback).
  - Brief SUPPRESSED when get_upcoming_meetings returns empty list.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from agent_app.agent import BRIEF_LOOKBACK_DAYS
from agent_app.tools import get_agenda_documents, get_upcoming_meetings
from shared.database import (
    ApprovalStatus,
    ClassificationLevel,
    Committee,
    Delegate,
    DelegateRole,
    Delegation,
    Document,
    DocumentAccessRight,
    Meeting,
    MeetingAgendaItem,
    MembershipType,
)

# -- Helpers ---------------------------------------------------------

_NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _make_delegate(
    delegate_id: str,
    full_name: str,
    email: str,
    function: str,
    delegation_id: str,
) -> Delegate:
    """Return a Delegate ORM instance with test defaults.

    Args:
        delegate_id: Unique delegate identifier.
        full_name: Display name.
        email: Contact email address.
        function: Role description within the delegation.
        delegation_id: Parent delegation identifier.

    Returns:
        Unsaved Delegate ORM object.
    """
    return Delegate(
        id=delegate_id,
        full_name=full_name,
        email=email,
        function=function,
        delegation_id=delegation_id,
        accreditation_date=datetime(2026, 1, 1),
        role=DelegateRole.DELEGATE,
    )


def _make_dar(
    dar_id: int,
    delegate_id: str,
    committee_id: str,
    classification_level: ClassificationLevel,
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED,
) -> DocumentAccessRight:
    """Return a DocumentAccessRight ORM instance with test defaults.

    Args:
        dar_id: Integer primary key.
        delegate_id: Owning delegate identifier.
        committee_id: Target committee identifier.
        classification_level: Maximum classification accessible.
        approval_status: Approval state (defaults to APPROVED).

    Returns:
        Unsaved DocumentAccessRight ORM object.
    """
    return DocumentAccessRight(
        id=dar_id,
        delegate_id=delegate_id,
        committee_id=committee_id,
        classification_level=classification_level,
        retroactive=False,
        approval_status=approval_status,
        created_at=datetime(2026, 1, 1),
        created_by="system",
    )


def _seed_delegate_in_committee(
    session: Session,
    delegation_id: str,
    committee_id: str,
    delegate_id: str,
) -> None:
    """Insert delegation, committee, and delegate (with committee link).

    Args:
        session: Active SQLAlchemy session (flush occurs internally).
        delegation_id: ID for the Delegation row.
        committee_id: ID for the Committee row.
        delegate_id: ID for the Delegate row.
    """
    session.add(
        Delegation(
            id=delegation_id,
            name="Test Nation",
            membership_type=MembershipType.MEMBER,
        )
    )
    session.add(Committee(id=committee_id, name="Test Committee"))
    delegate = _make_delegate(
        delegate_id, "Test Delegate",
        "test@example.com", "Member", delegation_id,
    )
    session.add(delegate)
    session.flush()
    delegate.committees = [session.get(Committee, committee_id)]


def _seed_doc_with_meeting(
    session: Session,
    committee_id: str,
    meeting_id: str,
    doc_id: str,
    delegate_id: str,
    last_modified: datetime,
) -> None:
    """Insert meeting, document, agenda item, and GENERAL DAR.

    Args:
        session: Active SQLAlchemy session.
        committee_id: Committee owning the meeting and document.
        meeting_id: ID for the upcoming Meeting row.
        doc_id: ID for the Document row.
        delegate_id: ID of the delegate receiving GENERAL DAR.
        last_modified: last_modified timestamp for the document.
    """
    session.add(
        Meeting(
            id=meeting_id,
            committee_id=committee_id,
            title="Test Meeting",
            date=_NOW + timedelta(days=10),
        )
    )
    session.add(
        Document(
            id=doc_id,
            title="Test Document",
            classification=ClassificationLevel.GENERAL,
            committee_id=committee_id,
            publication_date=_NOW,
            last_modified=last_modified,
        )
    )
    session.add(
        MeetingAgendaItem(
            id=1,
            meeting_id=meeting_id,
            document_id=doc_id,
            item_order=1,
        )
    )
    session.add(
        _make_dar(1, delegate_id, committee_id,
                  ClassificationLevel.GENERAL)
    )


def _make_ctx(delegate_id: str) -> MagicMock:
    """Return a MagicMock FunctionInvocationContext.

    Args:
        delegate_id: Value injected as ctx.kwargs['delegate_id'].

    Returns:
        Configured MagicMock context object.
    """
    ctx = MagicMock()
    ctx.kwargs = {"delegate_id": delegate_id}
    return ctx


# -- Class 1: TestBriefFiresWithNewDocuments -------------------------


class TestBriefFiresWithNewDocuments:
    """Verify tool sequence produces data that would trigger a brief.

    The brief fires when at least one agenda document has
    last_modified within the past BRIEF_LOOKBACK_DAYS days.
    """

    def _seed(self, session: Session, last_modified: datetime) -> None:
        """Insert delegate, committee, recent document and meeting."""
        _seed_delegate_in_committee(
            session, "BRI-DEL", "BRI-COM", "BRI-D1"
        )
        _seed_doc_with_meeting(
            session, "BRI-COM", "BRI-MTG-1",
            "BRI-DOC-1", "BRI-D1", last_modified,
        )

    def test_upcoming_meeting_is_returned(
        self, engine: object
    ) -> None:
        """Delegate in a committee sees a future meeting in results."""
        with Session(engine) as sess:
            _seed_delegate_in_committee(
                sess, "BRI-DEL", "BRI-COM", "BRI-D1"
            )
            sess.add(
                Meeting(
                    id="BRI-MTG-1",
                    committee_id="BRI-COM",
                    title="Upcoming Brief Meeting",
                    date=_NOW + timedelta(days=10),
                )
            )
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            result = get_upcoming_meetings(_make_ctx("BRI-D1"))

        ids = [m["id"] for m in json.loads(result)]
        assert "BRI-MTG-1" in ids

    def test_recent_document_appears_in_agenda(
        self, engine: object
    ) -> None:
        """Document modified within lookback window is visible."""
        recent = _NOW - timedelta(days=1)
        with Session(engine) as sess:
            self._seed(sess, recent)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            docs = json.loads(
                get_agenda_documents("BRI-MTG-1", _make_ctx("BRI-D1"))
            )

        assert any(d["id"] == "BRI-DOC-1" for d in docs)

    def test_recent_document_last_modified_within_lookback(
        self, engine: object
    ) -> None:
        """last_modified on returned doc is within
        BRIEF_LOOKBACK_DAYS."""
        recent = _NOW - timedelta(days=1)
        with Session(engine) as sess:
            self._seed(sess, recent)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            docs = json.loads(
                get_agenda_documents("BRI-MTG-1", _make_ctx("BRI-D1"))
            )

        target = next(d for d in docs if d["id"] == "BRI-DOC-1")
        age = _NOW - datetime.fromisoformat(target["last_modified"])
        assert age <= timedelta(days=BRIEF_LOOKBACK_DAYS), (
            f"Expected age <= {BRIEF_LOOKBACK_DAYS}d, got {age}"
        )

    def test_recent_document_title_in_result(
        self, engine: object
    ) -> None:
        """Document title from seed data is present in
        result payload."""
        recent = _NOW - timedelta(days=2)
        with Session(engine) as sess:
            self._seed(sess, recent)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            docs = json.loads(
                get_agenda_documents("BRI-MTG-1", _make_ctx("BRI-D1"))
            )

        titles = [d["title"] for d in docs]
        assert "Test Document" in titles


# -- Class 2: TestBriefSuppressedNoNewDocuments ----------------------


class TestBriefSuppressedNoNewDocuments:
    """Verify tool sequence produces data that would suppress the brief.

    The brief is suppressed when all agenda documents have
    last_modified older than BRIEF_LOOKBACK_DAYS days. The tools
    do not filter by date; the agent applies that filter. These
    tests assert the DATA CONDITION only.
    """

    def _seed(self, session: Session) -> None:
        """Insert delegate, committee, stale document and meeting."""
        old = _NOW - timedelta(days=30)
        _seed_delegate_in_committee(
            session, "SUP-DEL", "SUP-COM", "SUP-D1"
        )
        _seed_doc_with_meeting(
            session, "SUP-COM", "SUP-MTG-1",
            "SUP-DOC-1", "SUP-D1", old,
        )

    def test_upcoming_meeting_is_still_returned(
        self, engine: object
    ) -> None:
        """Meeting is returned even when all documents are stale."""
        with Session(engine) as sess:
            self._seed(sess)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            result = get_upcoming_meetings(_make_ctx("SUP-D1"))

        ids = [m["id"] for m in json.loads(result)]
        assert "SUP-MTG-1" in ids

    def test_stale_document_is_returned_by_tool(
        self, engine: object
    ) -> None:
        """Tool returns stale doc — agent, not tool,
        applies lookback."""
        with Session(engine) as sess:
            self._seed(sess)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            docs = json.loads(
                get_agenda_documents("SUP-MTG-1", _make_ctx("SUP-D1"))
            )

        assert any(d["id"] == "SUP-DOC-1" for d in docs)

    def test_stale_document_last_modified_outside_lookback(
        self, engine: object
    ) -> None:
        """last_modified on returned doc is beyond
        BRIEF_LOOKBACK_DAYS."""
        with Session(engine) as sess:
            self._seed(sess)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            docs = json.loads(
                get_agenda_documents("SUP-MTG-1", _make_ctx("SUP-D1"))
            )

        target = next(d for d in docs if d["id"] == "SUP-DOC-1")
        age = _NOW - datetime.fromisoformat(target["last_modified"])
        assert age > timedelta(days=BRIEF_LOOKBACK_DAYS), (
            f"Expected age > {BRIEF_LOOKBACK_DAYS}d, got {age}"
        )


# -- Class 3: TestBriefSuppressedNoMeetings --------------------------


class TestBriefSuppressedNoMeetings:
    """Verify tool returns [] when there are no upcoming meetings.

    If get_upcoming_meetings returns [], the agent never calls
    get_agenda_documents and the brief is suppressed.
    """

    def test_delegate_with_no_committees_returns_empty(
        self, engine: object
    ) -> None:
        """Delegate not assigned to any committee sees no meetings."""
        with Session(engine) as sess:
            sess.add(
                Delegation(
                    id="NOM-DEL",
                    name="No-Meeting Nation",
                    membership_type=MembershipType.MEMBER,
                )
            )
            sess.add(
                Committee(id="NOM-COM", name="Unassigned Committee")
            )
            # Delegate created but NOT linked to any committee
            sess.add(
                _make_delegate(
                    "NOM-D1", "Unassigned Delegate",
                    "none@example.com", "Observer", "NOM-DEL",
                )
            )
            sess.add(
                Meeting(
                    id="NOM-MTG-1",
                    committee_id="NOM-COM",
                    title="Meeting Delegate Cannot See",
                    date=_NOW + timedelta(days=5),
                )
            )
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            result = get_upcoming_meetings(_make_ctx("NOM-D1"))

        assert json.loads(result) == []

    def test_delegate_with_only_past_meetings_returns_empty(
        self, engine: object
    ) -> None:
        """Delegate in committee but all meetings are in the past."""
        with Session(engine) as sess:
            _seed_delegate_in_committee(
                sess, "PST-DEL", "PST-COM", "PST-D1"
            )
            sess.add(
                Meeting(
                    id="PST-MTG-1",
                    committee_id="PST-COM",
                    title="Past Meeting",
                    date=_NOW - timedelta(days=3),
                )
            )
            sess.add(
                Meeting(
                    id="PST-MTG-2",
                    committee_id="PST-COM",
                    title="Another Past Meeting",
                    date=_NOW - timedelta(days=15),
                )
            )
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            result = get_upcoming_meetings(_make_ctx("PST-D1"))

        assert json.loads(result) == []


# -- Class 4: TestGrounding ------------------------------------------


class TestGrounding:
    """Verify tool output contains only what was seeded in the DB.

    The grounding rule: the agent must never invent documents. These
    tests confirm that only seeded documents appear in results and
    that the count is exact.
    """

    def _seed(self, session: Session) -> None:
        """Insert delegation, committee, delegate, two docs, meeting.

        Args:
            session: Active SQLAlchemy session.
        """
        session.add(
            Delegation(
                id="GRD-DEL",
                name="Grounding Nation",
                membership_type=MembershipType.MEMBER,
            )
        )
        session.add(
            Committee(id="GRD-COM", name="Grounding Committee")
        )
        delegate = _make_delegate(
            "GRD-D1", "Grounding Delegate",
            "grd@example.com", "Member", "GRD-DEL",
        )
        session.add(delegate)
        session.flush()
        delegate.committees = [session.get(Committee, "GRD-COM")]

        session.add(
            Meeting(
                id="GRD-MTG-1",
                committee_id="GRD-COM",
                title="Grounding Meeting",
                date=_NOW + timedelta(days=5),
            )
        )
        session.add(
            Document(
                id="GRD-DOC-1",
                title="Alpha Report",
                classification=ClassificationLevel.GENERAL,
                committee_id="GRD-COM",
                publication_date=_NOW,
                last_modified=_NOW,
            )
        )
        session.add(
            Document(
                id="GRD-DOC-2",
                title="Beta Minutes",
                classification=ClassificationLevel.GENERAL,
                committee_id="GRD-COM",
                publication_date=_NOW,
                last_modified=_NOW,
            )
        )
        session.add(
            MeetingAgendaItem(
                id=10,
                meeting_id="GRD-MTG-1",
                document_id="GRD-DOC-1",
                item_order=1,
            )
        )
        session.add(
            MeetingAgendaItem(
                id=11,
                meeting_id="GRD-MTG-1",
                document_id="GRD-DOC-2",
                item_order=2,
            )
        )
        session.add(
            _make_dar(
                100, "GRD-D1", "GRD-COM",
                ClassificationLevel.GENERAL,
            )
        )

    def test_only_seeded_titles_in_result(
        self, engine: object
    ) -> None:
        """Result contains exactly the two seeded docs, no more.

        Verifies that the tool returns only database content and
        cannot invent documents such as 'Gamma Policy'.
        """
        with Session(engine) as sess:
            self._seed(sess)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            docs = json.loads(
                get_agenda_documents(
                    "GRD-MTG-1", _make_ctx("GRD-D1")
                )
            )

        titles = [d["title"] for d in docs]
        assert "Alpha Report" in titles
        assert "Beta Minutes" in titles
        assert "Gamma Policy" not in titles
        assert "Delta Brief" not in titles
        assert len(docs) == 2, (
            f"Expected exactly 2 docs, got {len(docs)}"
        )


# -- Class 5: TestDARVisibilityEnforcement ---------------------------


class TestDARVisibilityEnforcement:
    """Verify DAR enforcement is applied at the tool layer.

    Delegate A holds a RESTRICTED DAR and sees both documents.
    Delegate B holds no DAR at all and sees nothing.
    """

    def _seed(self, session: Session) -> None:
        """Insert delegation, committee, two delegates, two docs.

        Delegate A gets a RESTRICTED DAR; Delegate B gets none.

        Args:
            session: Active SQLAlchemy session.
        """
        session.add(
            Delegation(
                id="VIS-DEL",
                name="Visibility Nation",
                membership_type=MembershipType.MEMBER,
            )
        )
        session.add(
            Committee(id="VIS-COM", name="Visibility Committee")
        )
        del_a = _make_delegate(
            "VIS-DEL-A", "Delegate Alpha",
            "alpha@example.com", "Head", "VIS-DEL",
        )
        del_b = _make_delegate(
            "VIS-DEL-B", "Delegate Beta",
            "beta@example.com", "Member", "VIS-DEL",
        )
        session.add(del_a)
        session.add(del_b)
        session.flush()
        com = session.get(Committee, "VIS-COM")
        del_a.committees = [com]
        del_b.committees = [com]

        session.add(
            Meeting(
                id="VIS-MTG-1",
                committee_id="VIS-COM",
                title="Visibility Meeting",
                date=_NOW + timedelta(days=7),
            )
        )
        session.add(
            Document(
                id="VIS-DOC-R",
                title="Restricted Document",
                classification=ClassificationLevel.RESTRICTED,
                committee_id="VIS-COM",
                publication_date=_NOW,
                last_modified=_NOW,
            )
        )
        session.add(
            Document(
                id="VIS-DOC-G",
                title="General Document",
                classification=ClassificationLevel.GENERAL,
                committee_id="VIS-COM",
                publication_date=_NOW,
                last_modified=_NOW,
            )
        )
        session.add(
            MeetingAgendaItem(
                id=20,
                meeting_id="VIS-MTG-1",
                document_id="VIS-DOC-R",
                item_order=1,
            )
        )
        session.add(
            MeetingAgendaItem(
                id=21,
                meeting_id="VIS-MTG-1",
                document_id="VIS-DOC-G",
                item_order=2,
            )
        )
        # Only Delegate A receives a DAR; Delegate B gets none
        session.add(
            _make_dar(
                200, "VIS-DEL-A", "VIS-COM",
                ClassificationLevel.RESTRICTED,
            )
        )

    def test_delegate_with_restricted_dar_sees_both(
        self, engine: object
    ) -> None:
        """RESTRICTED DAR grants visibility of GENERAL and RESTRICTED
        docs."""
        with Session(engine) as sess:
            self._seed(sess)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            docs = json.loads(
                get_agenda_documents(
                    "VIS-MTG-1", _make_ctx("VIS-DEL-A")
                )
            )

        ids = [d["id"] for d in docs]
        assert "VIS-DOC-R" in ids
        assert "VIS-DOC-G" in ids

    def test_delegate_without_dar_sees_nothing(
        self, engine: object
    ) -> None:
        """Delegate with no DAR record returns empty list."""
        with Session(engine) as sess:
            self._seed(sess)
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            docs = json.loads(
                get_agenda_documents(
                    "VIS-MTG-1", _make_ctx("VIS-DEL-B")
                )
            )

        assert docs == []
