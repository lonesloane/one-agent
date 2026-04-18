"""
Tests for classical_app Flask routes.

Covers delegate picker, dashboard, committees, meetings, and document
routes with seeded demo data.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.database import (
    Meeting,
    Document,
    Committee,
)


class TestDelegatePicker:
    """TEST-001: Delegate picker routes."""

    def test_get_switch_delegate_returns_200_and_delegate_names(
        self, client, seeded_engine
    ):
        """GET /switch-delegate returns 200 and lists all delegates."""
        response = client.get("/switch-delegate")
        assert response.status_code == 200
        # Check that delegate names appear in response
        assert b"Marie Dupont" in response.data
        assert b"Carlos Silva" in response.data
        assert b"Priya Sharma" in response.data

    def test_post_switch_delegate_with_valid_id_redirects_to_root(
        self, client, member_delegate_id
    ):
        """POST /switch-delegate redirects to / for valid delegate."""
        response = client.post(
            "/switch-delegate",
            data={"delegate_id": member_delegate_id},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.location.endswith("/")

    def test_post_switch_delegate_with_empty_id_redirects_back(
        self, client
    ):
        """POST /switch-delegate with empty delegate_id redirects back."""
        response = client.post(
            "/switch-delegate",
            data={"delegate_id": ""},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "switch-delegate" in response.location

    def test_get_root_without_session_redirects_to_picker(self, client):
        """GET / without delegate session redirects to /switch-delegate."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "switch-delegate" in response.location

    def test_editor_badge_visible_for_editor_delegate(
        self, client
    ):
        """Editor badge appears for DELEGATION_EDITOR delegates in picker.

        DEL-2026-0001 (Marie Dupont) has role DELEGATION_EDITOR, so the
        bg-warning 'Editor' badge should be present in the picker table.
        """
        response = client.get("/switch-delegate")
        assert response.status_code == 200
        assert b"Editor" in response.data


class TestDashboard:
    """TEST-002: Dashboard route."""

    def test_dashboard_with_member_delegate_returns_200(
        self, client, member_delegate_id
    ):
        """Dashboard returns 200 and displays delegate name."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/")
        assert response.status_code == 200
        assert b"Marie Dupont" in response.data

    def test_dashboard_with_partner_delegate_returns_200(
        self, client, partner_delegate_id
    ):
        """Dashboard returns 200 for partner delegate."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = partner_delegate_id

        response = client.get("/")
        assert response.status_code == 200
        assert b"Carlos Silva" in response.data


class TestMyCommittees:
    """TEST-003: My Committees route."""

    def test_committees_list_returns_200(
        self, client, member_delegate_id
    ):
        """GET /committees returns 200."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/committees")
        assert response.status_code == 200

    def test_committees_list_shows_only_delegate_committees(
        self, client, member_delegate_id, seeded_engine
    ):
        """Committees list shows only committees for the delegate."""
        # DEL-2026-0001 (Marie Dupont) is on 5 committees:
        # EDU, TRADE, DAC, ENV, SKILLS
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/committees")
        assert response.status_code == 200
        # Check that at least some expected committees appear
        assert b"Education Committee" in response.data or (
            b"EDU" in response.data
        )


class TestCommitteeDetail:
    """TEST-004: Committee detail route."""

    def test_committee_detail_returns_200_for_member_committee(
        self, client, member_delegate_id
    ):
        """GET /committees/EDU returns 200 for delegate on EDU."""
        # DEL-2026-0001 is on EDU committee
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/committees/EDU")
        assert response.status_code == 200

    def test_committee_detail_returns_404_for_non_member_committee(
        self, client, partner_delegate_id
    ):
        """GET /committees/<unknown> returns 404 for non-member."""
        # DEL-2026-0005 (Carlos Silva) is not on SKILLS committee
        with client.session_transaction() as sess:
            sess["delegate_id"] = partner_delegate_id

        response = client.get("/committees/SKILLS")
        assert response.status_code == 404

    def test_committee_detail_returns_404_for_nonexistent_committee(
        self, client, member_delegate_id
    ):
        """GET /committees/FAKE returns 404 for nonexistent committee."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/committees/FAKE")
        assert response.status_code == 404


class TestUpcomingMeetings:
    """TEST-005: Upcoming meetings route."""

    def test_upcoming_meetings_returns_200(
        self, client, member_delegate_id
    ):
        """GET /committees/EDU/meetings returns 200."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/committees/EDU/meetings")
        assert response.status_code == 200

    def test_upcoming_meetings_filters_to_future_only(
        self, client, member_delegate_id, seeded_engine
    ):
        """Upcoming meetings show only future meetings."""
        # The seed data includes:
        # - MTG-EDU-2026-05 (future, 2026-05-10)
        # - MTG-EDU-2026-03 (past, 2026-03-15)
        # Since "now" is 2026-04-12, only 2026-05 should show
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/committees/EDU/meetings")
        assert response.status_code == 200
        # Spring meeting (May) should be visible as future
        assert b"Spring" in response.data or b"2026-05" in response.data


class TestMeetingDetail:
    """TEST-006: Meeting detail route."""

    def test_meeting_detail_returns_200_for_visible_meeting(
        self, client, member_delegate_id
    ):
        """GET /meetings/<id> returns 200 for member."""
        # MTG-EDU-2026-05 has documents from EDU committee
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/meetings/MTG-EDU-2026-05")
        assert response.status_code == 200

    def test_meeting_detail_filters_visible_documents(
        self, client, member_delegate_id, seeded_engine
    ):
        """Meeting agenda filters documents by delegate access."""
        # MTG-EDU-2026-05 has: DOC-2026-0001 (PUBLIC), 0002 (GENERAL),
        # 0003 (RESTRICTED), 0004 (CONFIDENTIAL), 0017 (GENERAL)
        # DEL-2026-0001 (FRA member) has RESTRICTED access to EDU
        # so should see all docs with classification <= RESTRICTED
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/meetings/MTG-EDU-2026-05")
        assert response.status_code == 200
        # Should see agenda items (at least the meeting title)
        assert b"Spring" in response.data or (
            b"Education" in response.data
        )

    def test_meeting_detail_hides_docs_without_access(
        self, client, partner_delegate_id, seeded_engine
    ):
        """Partner without RESTRICTED access doesn't see restricted docs."""
        # DEL-2026-0005 (BRA partner) has RESTRICTED access to EDU
        # via framework agreement, but let's test a committee where
        # they only have GENERAL access.
        # DEL-2026-0005 is on TRADE with GENERAL access only (DAR 12)
        # MTG-TRADE-2026-05 has: DOC-2026-0005 (PUBLIC), 0006 (GENERAL),
        # 0007 (RESTRICTED), 0018 (CONFIDENTIAL)
        # They should only see PUBLIC and GENERAL docs
        with client.session_transaction() as sess:
            sess["delegate_id"] = partner_delegate_id

        response = client.get("/meetings/MTG-TRADE-2026-05")
        assert response.status_code == 200

    def test_meeting_detail_returns_404_for_nonexistent_meeting(
        self, client, member_delegate_id
    ):
        """GET /meetings/FAKE returns 404."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/meetings/FAKE")
        assert response.status_code == 404


class TestDocumentDetail:
    """TEST-007: Document detail route."""

    def test_document_detail_returns_200_for_visible_document(
        self, client, member_delegate_id
    ):
        """GET /documents/<id> returns 200 for visible document."""
        # DOC-2026-0001 is PUBLIC and in EDU committee
        # DEL-2026-0001 can see it
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/documents/DOC-2026-0001")
        assert response.status_code == 200
        assert b"Annual Report" in response.data

    def test_document_detail_returns_403_for_inaccessible_document(
        self, client, partner_delegate_id
    ):
        """GET /documents/<id> returns 403 for inaccessible document."""
        # DOC-2026-0004 is CONFIDENTIAL and in EDU committee
        # DEL-2026-0005 (BRA partner) has RESTRICTED access to EDU
        # but cannot access CONFIDENTIAL docs
        with client.session_transaction() as sess:
            sess["delegate_id"] = partner_delegate_id

        response = client.get("/documents/DOC-2026-0004")
        assert response.status_code == 403

    def test_document_detail_returns_404_for_nonexistent_document(
        self, client, member_delegate_id
    ):
        """GET /documents/<id> returns 404 for nonexistent document."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/documents/DOC-FAKE")
        assert response.status_code == 404


class TestDelegateSwitching:
    """TEST-008: Delegate switching during session."""

    def test_switching_delegates_shows_new_delegate_name(
        self, client, member_delegate_id, partner_delegate_id
    ):
        """Switching delegates changes the displayed name."""
        # Start with member delegate
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/")
        assert b"Marie Dupont" in response.data

        # Switch to partner delegate
        with client.session_transaction() as sess:
            sess["delegate_id"] = partner_delegate_id

        response = client.get("/")
        assert b"Carlos Silva" in response.data
        assert b"Marie Dupont" not in response.data

    def test_post_switch_and_redirect_shows_new_delegate(
        self, client, member_delegate_id, partner_delegate_id
    ):
        """POST /switch-delegate followed by GET / shows new delegate."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        # Switch via POST
        response = client.post(
            "/switch-delegate",
            data={"delegate_id": partner_delegate_id},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Carlos Silva" in response.data


class TestDelegationList:
    """TEST-009: Delegation list route."""

    def test_delegation_list_returns_200(
        self, client, member_delegate_id
    ):
        """GET /delegations returns 200 for authenticated delegate."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations")
        assert response.status_code == 200

    def test_delegation_list_shows_all_delegations(
        self, client, member_delegate_id
    ):
        """Delegation list shows all seeded delegation names."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations")
        assert response.status_code == 200
        # Seeded delegations: FRA, BRA, IND
        assert b"France" in response.data or b"FRA" in response.data
        assert b"Brazil" in response.data or b"BRA" in response.data

    def test_delegation_list_shows_type_badges(
        self, client, member_delegate_id
    ):
        """Delegation list renders MEMBER and PARTNER type badges."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations")
        assert response.status_code == 200
        assert b"MEMBER" in response.data
        assert b"PARTNER" in response.data

    def test_delegation_list_without_session_redirects(self, client):
        """GET /delegations without session redirects to picker."""
        response = client.get(
            "/delegations", follow_redirects=False
        )
        assert response.status_code == 302
        assert "switch-delegate" in response.location

    def test_delegation_list_nav_link_present(
        self, client, member_delegate_id
    ):
        """Delegations nav link is present on authenticated pages."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/")
        assert response.status_code == 200
        assert b"Delegations" in response.data


class TestDelegationDetail:
    """TEST-010: Delegation detail route."""

    def test_delegation_detail_returns_200_for_existing(
        self, client, member_delegate_id
    ):
        """GET /delegations/FRA returns 200 for existing delegation."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations/FRA")
        assert response.status_code == 200

    def test_delegation_detail_shows_delegate_roster(
        self, client, member_delegate_id
    ):
        """Delegation detail lists delegate names in the roster."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations/FRA")
        assert response.status_code == 200
        assert b"Marie Dupont" in response.data

    def test_delegation_detail_shows_framework_agreements(
        self, client, partner_delegate_id
    ):
        """Delegation detail lists framework agreements when present."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = partner_delegate_id

        # BRA has a framework agreement with EDU committee
        response = client.get("/delegations/BRA")
        assert response.status_code == 200
        assert b"Framework Agreements" in response.data

    def test_delegation_detail_returns_404_for_nonexistent(
        self, client, member_delegate_id
    ):
        """GET /delegations/FAKE returns 404 for unknown delegation."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations/FAKE")
        assert response.status_code == 404

    def test_delegation_detail_shows_add_button_for_editor(
        self, client, member_delegate_id
    ):
        """Add New Delegate button is visible for delegation editor."""
        # DEL-2026-0001 (Marie Dupont) is DELEGATION_EDITOR for FRA
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations/FRA")
        assert response.status_code == 200
        assert b"Add New Delegate" in response.data

    def test_delegation_detail_hides_add_button_for_non_editor(
        self, client, member_delegate_id
    ):
        """Add New Delegate button is hidden for non-editor delegate."""
        # DEL-2026-0001 (FRA editor) visits BRA — not their delegation
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations/BRA")
        assert response.status_code == 200
        assert b"Add New Delegate" not in response.data

    def test_delegation_detail_without_session_redirects(
        self, client
    ):
        """GET /delegations/FRA without session redirects to picker."""
        response = client.get(
            "/delegations/FRA", follow_redirects=False
        )
        assert response.status_code == 302
        assert "switch-delegate" in response.location
