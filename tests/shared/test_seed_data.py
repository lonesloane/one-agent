"""
Tests for ONE-MP Agent PoC shared data layer seed data.

Verifies seed data completeness, idempotency, and demo scenario behaviors
as defined in REQ-005 and REQ-007.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.database import (
    Base,
    init_db,
    Delegation,
    Committee,
    Delegate,
    Document,
    DocumentAccessRight,
    FrameworkAgreement,
    Meeting,
    MeetingAgendaItem,
    DelegateRole,
)
from shared.seed_data import seed_all
from shared.business_rules import get_visible_agenda_documents


@pytest.fixture
def seeded_session():
    """
    Create an in-memory database with complete seed data.

    Initializes schema, seeds all data, and yields a session for test use.
    This fixture provides the canonical demo dataset for all tests.

    Yields:
        SQLAlchemy session with fully seeded test database
    """
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
        yield session


class TestSeedDataCompleteness:
    """Verify seed data meets minimum entity count requirements."""

    def test_entity_counts_meet_minimums(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify seeded database contains required minimum entities.

        REQ-007 defines minimum entity counts for demo purposes:
        - delegations >= 4
        - committees >= 5
        - delegates >= 8
        - documents >= 15
        - document_access_rights >= 20
        - meetings >= 4
        - agenda_items >= 15

        All counts use >= to allow for future additions while enforcing
        demo dataset sufficiency.
        """
        delegation_count = seeded_session.query(Delegation).count()
        committee_count = seeded_session.query(Committee).count()
        delegate_count = seeded_session.query(Delegate).count()
        document_count = seeded_session.query(Document).count()
        dar_count = seeded_session.query(DocumentAccessRight).count()
        meeting_count = seeded_session.query(Meeting).count()
        agenda_item_count = (
            seeded_session.query(MeetingAgendaItem).count()
        )

        # Verify counts meet or exceed minimums
        assert delegation_count >= 4, (
            f"Expected >= 4 delegations, got {delegation_count}"
        )
        assert committee_count >= 5, (
            f"Expected >= 5 committees, got {committee_count}"
        )
        assert delegate_count >= 8, (
            f"Expected >= 8 delegates, got {delegate_count}"
        )
        assert document_count >= 15, (
            f"Expected >= 15 documents, got {document_count}"
        )
        assert dar_count >= 20, (
            f"Expected >= 20 DARs, got {dar_count}"
        )
        assert meeting_count >= 4, (
            f"Expected >= 4 meetings, got {meeting_count}"
        )
        assert agenda_item_count >= 15, (
            f"Expected >= 15 agenda items, got {agenda_item_count}"
        )

    def test_delegations_have_expected_structure(
        self,
        seeded_session: Session,
    ) -> None:
        """Verify delegations match expected IDs and membership types."""
        delegations = seeded_session.query(Delegation).all()
        delegation_map = {d.id: d for d in delegations}

        # Verify expected delegations exist
        assert "FRA" in delegation_map
        assert "DEU" in delegation_map
        assert "BRA" in delegation_map
        assert "IND" in delegation_map

        # Verify membership types
        from shared.database import MembershipType
        assert (
            delegation_map["FRA"].membership_type == MembershipType.MEMBER
        )
        assert (
            delegation_map["DEU"].membership_type == MembershipType.MEMBER
        )
        assert (
            delegation_map["BRA"].membership_type == MembershipType.PARTNER
        )
        assert (
            delegation_map["IND"].membership_type == MembershipType.PARTNER
        )

    def test_committees_have_expected_ids(
        self,
        seeded_session: Session,
    ) -> None:
        """Verify expected committees exist with correct IDs."""
        committees = seeded_session.query(Committee).all()
        committee_ids = {c.id for c in committees}

        expected_ids = {"EDU", "TRADE", "DAC", "ENV", "SKILLS"}
        assert committee_ids == expected_ids


class TestSeedDataIdempotency:
    """Verify seed_all can be called multiple times without duplication."""

    def test_seed_all_idempotent(self, seeded_session: Session) -> None:
        """
        Verify seed_all() can be called again without creating duplicates.

        This test ensures that running seed_all() on an already-seeded
        session maintains entity counts, relying on merge() upserting on
        primary key.

        Procedure:
        1. Record initial entity counts (already seeded by fixture)
        2. Call seed_all() again
        3. Verify counts remain identical
        """
        # Record initial counts
        initial_delegation_count = (
            seeded_session.query(Delegation).count()
        )
        initial_committee_count = seeded_session.query(Committee).count()
        initial_delegate_count = seeded_session.query(Delegate).count()
        initial_document_count = seeded_session.query(Document).count()
        initial_dar_count = (
            seeded_session.query(DocumentAccessRight).count()
        )
        initial_meeting_count = seeded_session.query(Meeting).count()
        initial_agenda_item_count = (
            seeded_session.query(MeetingAgendaItem).count()
        )

        # Run seed_all again
        seed_all(seeded_session)
        seeded_session.commit()

        # Verify counts remain the same (no duplicates)
        assert (
            seeded_session.query(Delegation).count()
            == initial_delegation_count
        )
        assert (
            seeded_session.query(Committee).count()
            == initial_committee_count
        )
        assert (
            seeded_session.query(Delegate).count()
            == initial_delegate_count
        )
        assert (
            seeded_session.query(Document).count()
            == initial_document_count
        )
        assert (
            seeded_session.query(DocumentAccessRight).count()
            == initial_dar_count
        )
        assert seeded_session.query(Meeting).count() == initial_meeting_count
        assert (
            seeded_session.query(MeetingAgendaItem).count()
            == initial_agenda_item_count
        )


class TestDemoScenarios:
    """
    Verify demo scenarios from REQ-005.

    Tests validate visibility rules for members vs. partners with
    different access levels and framework agreements.
    """

    def test_member_visibility_on_own_committee(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify MEMBER delegate sees appropriate docs on own committee.

        Scenario: DEL-2026-0001 (FRA, MEMBER) on EDU committee,
        MTG-EDU-2026-05 meeting agenda

        Expected: DEL-2026-0001 has RESTRICTED + APPROVED DAR on EDU,
        so sees PUBLIC, GENERAL, and RESTRICTED docs on agenda.
        Does NOT see CONFIDENTIAL docs.

        Agenda docs (MTG-EDU-2026-05):
        - DOC-2026-0001: PUBLIC → visible
        - DOC-2026-0002: GENERAL → visible
        - DOC-2026-0003: RESTRICTED → visible
        - DOC-2026-0004: CONFIDENTIAL → NOT visible
        - DOC-2026-0017: GENERAL → visible

        Assertion: exactly 4 visible documents (all except CONFIDENTIAL)
        """
        visible = get_visible_agenda_documents(
            "DEL-2026-0001",
            "MTG-EDU-2026-05",
            seeded_session,
        )

        assert len(visible) == 4, (
            f"DEL-2026-0001 should see 4 docs, saw {len(visible)}"
        )

        doc_ids = {d.id for d in visible}
        assert "DOC-2026-0001" in doc_ids  # PUBLIC
        assert "DOC-2026-0002" in doc_ids  # GENERAL
        assert "DOC-2026-0003" in doc_ids  # RESTRICTED
        assert "DOC-2026-0004" not in doc_ids  # CONFIDENTIAL blocked
        assert "DOC-2026-0017" in doc_ids  # GENERAL

    def test_partner_with_framework_agreement_restricted_access(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify PARTNER with active FA sees RESTRICTED docs.

        Scenario: DEL-2026-0005 (BRA, PARTNER) on EDU via active
        framework agreement (FA id=1, active)

        Expected: BRA-EDU FA grants RESTRICTED access, so
        DEL-2026-0005 with RESTRICTED + APPROVED DAR sees all
        non-CONFIDENTIAL docs.

        Agenda docs (MTG-EDU-2026-05): same as above
        Assertion: 4 visible documents (all except CONFIDENTIAL)
        """
        visible = get_visible_agenda_documents(
            "DEL-2026-0005",
            "MTG-EDU-2026-05",
            seeded_session,
        )

        assert len(visible) == 4, (
            f"DEL-2026-0005 (BRA with active FA) should see 4 docs, "
            f"saw {len(visible)}"
        )

        doc_ids = {d.id for d in visible}
        assert "DOC-2026-0001" in doc_ids  # PUBLIC
        assert "DOC-2026-0002" in doc_ids  # GENERAL
        assert "DOC-2026-0003" in doc_ids  # RESTRICTED (via FA)
        assert "DOC-2026-0004" not in doc_ids  # CONFIDENTIAL blocked

    def test_partner_without_restricted_access_blocks_restricted_docs(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify PARTNER without restricted access cannot see RESTRICTED.

        Scenario: DEL-2026-0008 (IND, PARTNER) on TRADE committee

        IND has:
        - DAR on TRADE: GENERAL + AUTO_APPROVED (id=16)
        - No active FA on TRADE (IND-DAC FA id=2 is expired)

        Expected: Sees PUBLIC + GENERAL only. RESTRICTED and
        CONFIDENTIAL blocked.

        Agenda docs (MTG-TRADE-2026-05):
        - DOC-2026-0005: PUBLIC → visible
        - DOC-2026-0006: GENERAL → visible
        - DOC-2026-0007: RESTRICTED → NOT visible
        - DOC-2026-0018: CONFIDENTIAL → NOT visible

        Assertion: exactly 2 visible documents
        """
        visible = get_visible_agenda_documents(
            "DEL-2026-0008",
            "MTG-TRADE-2026-05",
            seeded_session,
        )

        assert len(visible) == 2, (
            f"DEL-2026-0008 (IND partner, GENERAL access) should see "
            f"2 docs, saw {len(visible)}"
        )

        doc_ids = {d.id for d in visible}
        assert "DOC-2026-0005" in doc_ids  # PUBLIC visible
        assert "DOC-2026-0006" in doc_ids  # GENERAL visible
        assert "DOC-2026-0007" not in doc_ids  # RESTRICTED blocked
        assert "DOC-2026-0018" not in doc_ids  # CONFIDENTIAL blocked

    def test_delegate_without_access_right_sees_nothing(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify delegates without DAR see no documents.

        Scenario: DEL-2026-0009 (DEU, MEMBER, Adviser) only has
        access to EDU committee, not TRADE.

        Expected: On TRADE meeting agenda, sees no documents despite
        MEMBER status, because no DAR exists for TRADE.

        Assertion: 0 visible documents for TRADE meeting
        """
        visible = get_visible_agenda_documents(
            "DEL-2026-0009",
            "MTG-TRADE-2026-05",
            seeded_session,
        )

        assert len(visible) == 0, (
            f"DEL-2026-0009 without TRADE DAR should see 0 docs, "
            f"saw {len(visible)}"
        )

    def test_meeting_agenda_ordering_preserved(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify visible documents are returned in agenda order.

        Scenario: MTG-EDU-2026-05 agenda with 5 items in order.
        DEL-2026-0001 can see 4 of them (all except CONFIDENTIAL).

        Expected: Visible documents returned in the same order as
        the agenda items (by item_order).

        Assertion: Document IDs appear in correct order
        """
        visible = get_visible_agenda_documents(
            "DEL-2026-0001",
            "MTG-EDU-2026-05",
            seeded_session,
        )

        # Expected order from seed_data.py:
        # item 1: DOC-2026-0001 (PUBLIC)
        # item 2: DOC-2026-0002 (GENERAL)
        # item 3: DOC-2026-0003 (RESTRICTED)
        # item 4: DOC-2026-0004 (CONFIDENTIAL) - filtered out
        # item 5: DOC-2026-0017 (GENERAL)
        # Visible order: [DOC-0001, DOC-0002, DOC-0003, DOC-0017]

        assert len(visible) == 4
        assert visible[0].id == "DOC-2026-0001"
        assert visible[1].id == "DOC-2026-0002"
        assert visible[2].id == "DOC-2026-0003"
        assert visible[3].id == "DOC-2026-0017"


class TestSeedDataRoleSeeding:
    """Verify delegates with DELEGATION_EDITOR role are seeded correctly."""

    def test_three_delegation_editors_seeded(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify exactly 3 delegates are seeded as DELEGATION_EDITOR.

        Run seed_all(session). Query delegates where
        role == DelegateRole.DELEGATION_EDITOR. Assert count == 3 and
        IDs are exactly {"DEL-2026-0001", "DEL-2026-0005",
        "DEL-2026-0007"}.
        """
        editors = seeded_session.query(Delegate).filter_by(
            role=DelegateRole.DELEGATION_EDITOR
        ).all()

        assert len(editors) == 3, (
            f"Expected exactly 3 DELEGATION_EDITORs, got {len(editors)}"
        )

        editor_ids = {e.id for e in editors}
        expected_ids = {
            "DEL-2026-0001",
            "DEL-2026-0005",
            "DEL-2026-0007",
        }
        assert editor_ids == expected_ids, (
            f"Expected editor IDs {expected_ids}, got {editor_ids}"
        )

    def test_target_delegations_present(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify target delegations exist with 0 delegates each.

        Run seed_all(session). For each of TGT-ALPHA, TGT-BETA,
        TGT-GAMMA: assert the delegation exists, and assert it has
        0 delegates.
        """
        target_ids = {"TGT-ALPHA", "TGT-BETA", "TGT-GAMMA"}

        for target_id in target_ids:
            delegation = seeded_session.query(Delegation).filter_by(
                id=target_id
            ).first()

            assert delegation is not None, (
                f"Target delegation {target_id} not found"
            )

            delegate_count = seeded_session.query(Delegate).filter_by(
                delegation_id=target_id
            ).count()

            assert delegate_count == 0, (
                f"Expected {target_id} to have 0 delegates, "
                f"got {delegate_count}"
            )

    def test_seed_all_idempotent_with_role(
        self,
        seeded_session: Session,
    ) -> None:
        """
        Verify seed_all() is idempotent and preserves delegate roles.

        Run seed_all(session) twice. Assert total delegate count
        unchanged after second run. Assert the 3 editors are still
        editors (not reverted to DELEGATE).
        """
        # Record initial counts
        initial_delegate_count = seeded_session.query(Delegate).count()
        initial_editor_count = seeded_session.query(Delegate).filter_by(
            role=DelegateRole.DELEGATION_EDITOR
        ).count()

        # Run seed_all again
        seed_all(seeded_session)
        seeded_session.commit()

        # Verify counts unchanged
        final_delegate_count = seeded_session.query(Delegate).count()
        final_editor_count = seeded_session.query(Delegate).filter_by(
            role=DelegateRole.DELEGATION_EDITOR
        ).count()

        assert final_delegate_count == initial_delegate_count, (
            f"Delegate count changed from {initial_delegate_count} "
            f"to {final_delegate_count}"
        )

        assert final_editor_count == initial_editor_count == 3, (
            f"Expected 3 editors to remain after second seed, "
            f"got {final_editor_count}"
        )

        # Verify editor IDs are preserved
        editors = seeded_session.query(Delegate).filter_by(
            role=DelegateRole.DELEGATION_EDITOR
        ).all()
        editor_ids = {e.id for e in editors}
        expected_ids = {
            "DEL-2026-0001",
            "DEL-2026-0005",
            "DEL-2026-0007",
        }
        assert editor_ids == expected_ids
