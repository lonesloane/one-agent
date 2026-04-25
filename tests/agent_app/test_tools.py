"""Unit tests for agent_app/tools.py — DB-backed tool wrappers."""

import json
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from agent_app.tools import (
    get_agenda_documents,
    get_delegation_info,
    get_upcoming_meetings,
    lookup_delegate,
    whoami,
)
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

# -- Helpers ------------------------------------------------------------------

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _make_delegate(
    delegate_id: str,
    full_name: str,
    email: str,
    function: str,
    delegation_id: str,
) -> Delegate:
    """Return a Delegate ORM instance with test defaults."""
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
    """Return a DocumentAccessRight ORM instance with test defaults."""
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


# -- Class 1: TestGetDelegationInfo -------------------------------------------


class TestGetDelegationInfo:
    """Tests for the get_delegation_info tool."""

    def test_found_returns_delegation_data(self, engine: object) -> None:
        """Known delegation returns full JSON with delegates list."""
        with Session(engine) as sess:
            sess.add(
                Delegation(
                    id="FRA",
                    name="France",
                    membership_type=MembershipType.MEMBER,
                )
            )
            sess.add(
                _make_delegate(
                    "DEL-T1", "Alice Test", "a@test.com", "Head", "FRA"
                )
            )
            sess.add(
                _make_delegate(
                    "DEL-T2", "Bob Test", "b@test.com", "Delegate", "FRA"
                )
            )
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            result = get_delegation_info("FRA")

        data = json.loads(result)
        assert data["id"] == "FRA"
        assert data["name"] == "France"
        assert data["membership_type"] == "MEMBER"
        assert len(data["delegates"]) == 2
        assert isinstance(data["framework_agreements"], list)

    def test_unknown_id_returns_null_filled(self, engine: object) -> None:
        """Unknown delegation returns null-filled structure."""
        with patch("agent_app.tools._engine", engine):
            result = get_delegation_info("UNKNOWN")

        data = json.loads(result)
        assert data["name"] is None
        assert data["delegates"] == []
        assert data["framework_agreements"] == []


# -- Class 2: TestLookupDelegate ----------------------------------------------


class TestLookupDelegate:
    """Tests for the lookup_delegate tool."""

    def test_found_with_committees_and_dars(self, engine: object) -> None:
        """Known delegate returns full profile with committees and DARs."""
        with Session(engine) as sess:
            sess.add(
                Delegation(
                    id="FRA",
                    name="France",
                    membership_type=MembershipType.MEMBER,
                )
            )
            sess.add(Committee(id="EDU", name="Education Committee"))
            sess.add(Committee(id="TRADE", name="Trade Committee"))
            delegate = _make_delegate(
                "DEL-T1", "Alice Test", "a@test.com", "Head", "FRA"
            )
            sess.add(delegate)
            sess.flush()
            delegate.committees = [
                sess.get(Committee, "EDU"),
                sess.get(Committee, "TRADE"),
            ]
            sess.add(
                _make_dar(
                    1,
                    "DEL-T1",
                    "EDU",
                    ClassificationLevel.RESTRICTED,
                )
            )
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            result = lookup_delegate("DEL-T1")

        data = json.loads(result)
        assert data["full_name"] == "Alice Test"
        assert data["delegation_id"] == "FRA"
        committee_ids = [c["id"] for c in data["committees"]]
        assert "EDU" in committee_ids
        assert len(data["access_rights"]) == 1
        assert data["access_rights"][0]["classification_level"] == "RESTRICTED"

    def test_unknown_delegate_id_returns_null_filled(
        self, engine: object
    ) -> None:
        """Unknown delegate ID returns null-filled structure."""
        with patch("agent_app.tools._engine", engine):
            result = lookup_delegate("NOT-EXIST")

        data = json.loads(result)
        assert data["full_name"] is None
        assert data["committees"] == []
        assert data["access_rights"] == []

    def test_does_not_consult_ctx(self, engine: object) -> None:
        """lookup_delegate accepts no ctx parameter and ignores session state."""
        with Session(engine) as sess:
            sess.add(
                Delegation(
                    id="FRA",
                    name="France",
                    membership_type=MembershipType.MEMBER,
                )
            )
            sess.add(
                _make_delegate(
                    "DEL-T1", "Alice Test", "a@test.com", "Head", "FRA"
                )
            )
            sess.commit()

        with patch("agent_app.tools._engine", engine):
            result = lookup_delegate("DEL-T1")

        data = json.loads(result)
        assert data["id"] == "DEL-T1"
        assert data["full_name"] == "Alice Test"


# -- Class 3: TestWhoami ------------------------------------------------------


class TestWhoami:
    """Tests for the whoami tool (ctx-injected delegate identity)."""

    def test_returns_current_delegate_profile_via_ctx(
        self, engine: object
    ) -> None:
        """Ctx-injected delegate_id returns full profile with committees and DARs."""
        with Session(engine) as sess:
            sess.add(
                Delegation(
                    id="FRA",
                    name="France",
                    membership_type=MembershipType.MEMBER,
                )
            )
            sess.add(Committee(id="EDU", name="Education Committee"))
            sess.add(Committee(id="TRADE", name="Trade Committee"))
            delegate = _make_delegate(
                "DEL-T1", "Alice Test", "a@test.com", "Head", "FRA"
            )
            sess.add(delegate)
            sess.flush()
            delegate.committees = [
                sess.get(Committee, "EDU"),
                sess.get(Committee, "TRADE"),
            ]
            sess.add(
                _make_dar(
                    1,
                    "DEL-T1",
                    "EDU",
                    ClassificationLevel.RESTRICTED,
                )
            )
            sess.commit()

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T1"}
        with patch("agent_app.tools._engine", engine):
            result = whoami(ctx)

        data = json.loads(result)
        assert data["full_name"] == "Alice Test"
        assert data["delegation_id"] == "FRA"
        committee_ids = [c["id"] for c in data["committees"]]
        assert "EDU" in committee_ids
        assert len(data["access_rights"]) == 1
        assert data["access_rights"][0]["classification_level"] == "RESTRICTED"

    def test_missing_delegate_id_in_ctx_returns_null_filled(
        self, engine: object
    ) -> None:
        """Empty delegate_id in ctx returns null-filled structure."""
        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": ""}
        with patch("agent_app.tools._engine", engine):
            result = whoami(ctx)

        data = json.loads(result)
        assert data["id"] is None
        assert data["full_name"] is None
        assert data["delegation_id"] is None
        assert data["committees"] == []
        assert data["access_rights"] == []
        assert data["role"] is None

    def test_returns_role_field_as_enum_string(self, engine: object) -> None:
        """whoami() result includes a 'role' key with the DelegateRole enum string."""
        with Session(engine) as sess:
            sess.add(
                Delegation(
                    id="DEU",
                    name="Germany",
                    membership_type=MembershipType.MEMBER,
                )
            )
            delegate = Delegate(
                id="DEL-T99",
                full_name="Editor User",
                email="editor@test.com",
                function="Editor",
                delegation_id="DEU",
                accreditation_date=datetime(2026, 1, 1),
                role=DelegateRole.DELEGATION_EDITOR,
            )
            sess.add(delegate)
            sess.commit()

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T99"}
        with patch("agent_app.tools._engine", engine):
            result = whoami(ctx)

        data = json.loads(result)
        assert data["role"] == "DELEGATION_EDITOR"


# -- Class 4: TestGetUpcomingMeetings -----------------------------------------


class TestGetUpcomingMeetings:
    """Tests for the get_upcoming_meetings tool."""

    def _setup_meetings(self, session: Session) -> None:
        """Insert committees, delegates, and meetings into session."""
        session.add(
            Delegation(
                id="FRA",
                name="France",
                membership_type=MembershipType.MEMBER,
            )
        )
        session.add(Committee(id="EDU", name="Education Committee"))
        session.add(Committee(id="TRADE", name="Trade Committee"))

        delegate1 = _make_delegate(
            "DEL-T1", "Alice Test", "a@test.com", "Head", "FRA"
        )
        session.add(delegate1)
        delegate2 = _make_delegate(
            "DEL-T2", "Bob Test", "b@test.com", "Delegate", "FRA"
        )
        session.add(delegate2)
        session.flush()
        delegate1.committees = [
            session.get(Committee, "EDU"),
            session.get(Committee, "TRADE"),
        ]

        session.add(
            Meeting(
                id="MTG-FUTURE-1",
                committee_id="EDU",
                title="Future Meeting 1",
                date=_NOW + timedelta(days=10),
            )
        )
        session.add(
            Meeting(
                id="MTG-FUTURE-2",
                committee_id="TRADE",
                title="Future Meeting 2",
                date=_NOW + timedelta(days=20),
            )
        )
        session.add(
            Meeting(
                id="MTG-PAST-1",
                committee_id="EDU",
                title="Past Meeting",
                date=_NOW - timedelta(days=10),
            )
        )
        session.commit()

    def test_returns_upcoming_meetings_sorted_by_date(
        self, engine: object
    ) -> None:
        """Delegate with committees gets future meetings in date order."""
        with Session(engine) as sess:
            self._setup_meetings(sess)

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T1"}
        with patch("agent_app.tools._engine", engine):
            result = get_upcoming_meetings(ctx)

        data = json.loads(result)
        meeting_ids = [m["id"] for m in data]
        assert "MTG-FUTURE-1" in meeting_ids
        assert "MTG-FUTURE-2" in meeting_ids
        assert "MTG-PAST-1" not in meeting_ids

        future_1_pos = meeting_ids.index("MTG-FUTURE-1")
        future_2_pos = meeting_ids.index("MTG-FUTURE-2")
        assert future_1_pos < future_2_pos

        for item in data:
            assert "id" in item
            assert "title" in item
            assert "committee_id" in item
            assert "meeting_date" in item

    def test_delegate_with_no_committees_returns_empty(
        self, engine: object
    ) -> None:
        """Delegate without committee assignments returns empty list."""
        with Session(engine) as sess:
            self._setup_meetings(sess)

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T2"}
        with patch("agent_app.tools._engine", engine):
            result = get_upcoming_meetings(ctx)

        assert json.loads(result) == []

    def test_delegate_with_only_past_meetings_returns_empty(
        self, engine: object
    ) -> None:
        """Delegate in a committee but all meetings are past."""
        with Session(engine) as sess:
            sess.add(
                Delegation(
                    id="FRA",
                    name="France",
                    membership_type=MembershipType.MEMBER,
                )
            )
            sess.add(Committee(id="EDU", name="Education Committee"))
            delegate = _make_delegate(
                "DEL-T3", "Carol Test", "c@test.com", "Adviser", "FRA"
            )
            sess.add(delegate)
            sess.flush()
            delegate.committees = [sess.get(Committee, "EDU")]
            sess.add(
                Meeting(
                    id="MTG-PAST-ONLY",
                    committee_id="EDU",
                    title="Old Meeting",
                    date=_NOW - timedelta(days=5),
                )
            )
            sess.commit()

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T3"}
        with patch("agent_app.tools._engine", engine):
            result = get_upcoming_meetings(ctx)

        assert json.loads(result) == []

    def test_empty_delegate_id_returns_empty(self, engine: object) -> None:
        """Empty delegate_id in context returns empty list."""
        with Session(engine) as sess:
            self._setup_meetings(sess)

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": ""}
        with patch("agent_app.tools._engine", engine):
            result = get_upcoming_meetings(ctx)

        assert json.loads(result) == []


# -- Class 5: TestGetAgendaDocuments ------------------------------------------


class TestGetAgendaDocuments:
    """Tests for the get_agenda_documents tool."""

    def _setup_base(self, session: Session) -> None:
        """Insert core delegation, committee, delegate, documents."""
        session.add(
            Delegation(
                id="FRA",
                name="France",
                membership_type=MembershipType.MEMBER,
            )
        )
        session.add(Committee(id="EDU", name="Education Committee"))
        session.add(
            _make_delegate("DEL-T1", "Alice Test", "a@test.com", "Head", "FRA")
        )
        session.add(
            _make_delegate(
                "DEL-T2", "Bob Test", "b@test.com", "Delegate", "FRA"
            )
        )
        session.add(
            Document(
                id="DOC-T1",
                title="General Doc",
                classification=ClassificationLevel.GENERAL,
                committee_id="EDU",
                publication_date=datetime(2026, 1, 1),
                last_modified=datetime(2026, 1, 1),
            )
        )
        session.add(
            Document(
                id="DOC-T2",
                title="Restricted Doc",
                classification=ClassificationLevel.RESTRICTED,
                committee_id="EDU",
                publication_date=datetime(2026, 1, 1),
                last_modified=datetime(2026, 1, 1),
            )
        )
        session.add(
            Meeting(
                id="MTG-T1",
                committee_id="EDU",
                title="Test Meeting",
                date=datetime(2026, 5, 1),
            )
        )
        session.add(
            MeetingAgendaItem(
                id=1,
                meeting_id="MTG-T1",
                document_id="DOC-T1",
                item_order=1,
            )
        )
        session.add(
            MeetingAgendaItem(
                id=2,
                meeting_id="MTG-T1",
                document_id="DOC-T2",
                item_order=2,
            )
        )

    def test_delegate_with_general_dar_sees_general_not_restricted(
        self, engine: object
    ) -> None:
        """GENERAL DAR grants access to GENERAL docs, not RESTRICTED."""
        with Session(engine) as sess:
            self._setup_base(sess)
            sess.add(
                _make_dar(
                    1,
                    "DEL-T1",
                    "EDU",
                    ClassificationLevel.GENERAL,
                )
            )
            sess.commit()

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T1"}
        with patch("agent_app.tools._engine", engine):
            result = get_agenda_documents("MTG-T1", ctx)

        data = json.loads(result)
        doc_ids = [d["id"] for d in data]
        assert "DOC-T1" in doc_ids
        assert "DOC-T2" not in doc_ids

    def test_delegate_with_restricted_dar_sees_both(
        self, engine: object
    ) -> None:
        """RESTRICTED DAR grants access to GENERAL and RESTRICTED docs."""
        with Session(engine) as sess:
            self._setup_base(sess)
            sess.add(
                _make_dar(
                    2,
                    "DEL-T2",
                    "EDU",
                    ClassificationLevel.RESTRICTED,
                )
            )
            sess.commit()

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T2"}
        with patch("agent_app.tools._engine", engine):
            result = get_agenda_documents("MTG-T1", ctx)

        data = json.loads(result)
        doc_ids = [d["id"] for d in data]
        assert "DOC-T1" in doc_ids
        assert "DOC-T2" in doc_ids

    def test_delegate_without_any_dar_sees_nothing(
        self, engine: object
    ) -> None:
        """Delegate with no DAR records cannot see any documents."""
        with Session(engine) as sess:
            self._setup_base(sess)
            sess.commit()

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T1"}
        with patch("agent_app.tools._engine", engine):
            result = get_agenda_documents("MTG-T1", ctx)

        assert json.loads(result) == []

    def test_empty_meeting_returns_empty(self, engine: object) -> None:
        """Non-existent meeting ID returns empty list."""
        with Session(engine) as sess:
            self._setup_base(sess)
            sess.add(
                _make_dar(
                    1,
                    "DEL-T1",
                    "EDU",
                    ClassificationLevel.GENERAL,
                )
            )
            sess.commit()

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": "DEL-T1"}
        with patch("agent_app.tools._engine", engine):
            result = get_agenda_documents("MTG-NONEXISTENT", ctx)

        assert json.loads(result) == []

    def test_empty_delegate_id_returns_empty(self, engine: object) -> None:
        """Empty delegate_id in context returns empty list."""
        with Session(engine) as sess:
            self._setup_base(sess)
            sess.commit()

        ctx = MagicMock()
        ctx.kwargs = {"delegate_id": ""}
        with patch("agent_app.tools._engine", engine):
            result = get_agenda_documents("MTG-T1", ctx)

        assert json.loads(result) == []
