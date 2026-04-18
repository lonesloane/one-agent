"""
Tests for delegation permission enforcement and data accuracy.

Covers delegate counts on the list page and 403 enforcement on the
wizard POST endpoint. Tests that duplicate coverage already in
test_routes.py are intentionally omitted.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.database import Delegation


class TestDelegationCounts:
    """TASK-017: Delegate counts in the delegation list match the DB."""

    def test_counts_match_seed_data(
        self, client, member_delegate_id, seeded_engine
    ) -> None:
        """Delegate counts shown on /delegations match actual DB counts.

        Queries the seeded DB for each delegation's delegate count and
        verifies that the rendered HTML contains that count for each
        delegation.
        """
        with client.session_transaction() as sess:
            sess["delegate_id"] = member_delegate_id

        response = client.get("/delegations")
        assert response.status_code == 200

        with Session(seeded_engine) as session:
            delegations = session.scalars(select(Delegation)).all()
            for delegation in delegations:
                expected_count = len(delegation.delegates)
                # Check name appears in response
                assert delegation.name.encode() in response.data
                # Check count appears in a table data cell
                assert (
                    f"<td>{expected_count}</td>".encode()
                    in response.data
                )


class TestWizardPermissions:
    """TASK-022/023/024: POST /delegations/<id>/delegates/new/step1."""

    _WIZARD_URL = "/delegations/FRA/delegates/new/step1"

    def test_direct_post_from_non_editor_returns_403(
        self, client
    ) -> None:
        """Non-editor delegate POSTing wizard URL receives HTTP 403.

        DEL-2026-0002 (Jean Martin) has role DELEGATE on FRA, so the
        editor_of_delegation_required decorator must deny access.
        """
        # Reason: DEL-2026-0002 is a DELEGATE (not DELEGATION_EDITOR)
        non_editor_id = "DEL-2026-0002"
        with client.session_transaction() as sess:
            sess["delegate_id"] = non_editor_id

        response = client.post(self._WIZARD_URL, data={})
        assert response.status_code == 403

    def test_direct_post_from_editor_of_other_delegation_returns_403(
        self, client, editor_other_delegation_id
    ) -> None:
        """Editor of a different delegation POSTing FRA wizard gets 403.

        The editor has DELEGATION_EDITOR role but belongs to a delegation
        other than FRA, so permission must be denied.
        """
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_other_delegation_id

        response = client.post(self._WIZARD_URL, data={})
        assert response.status_code == 403

    def test_direct_post_from_correct_editor_does_not_403(
        self, client, editor_member_id
    ) -> None:
        """FRA's own DELEGATION_EDITOR POSTing the FRA wizard is not 403.

        The wizard returns 501 (stub), but permission must be granted.
        """
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id

        response = client.post(self._WIZARD_URL, data={})
        assert response.status_code == 501

    def test_403_template_rendered_on_permission_denied(
        self, client
    ) -> None:
        """403 error response renders the Access Denied template.

        When a non-editor POSTs the wizard URL, the 403.html template
        must be returned with the "Access Denied" heading.
        """
        # Reason: DEL-2026-0002 is a DELEGATE (not DELEGATION_EDITOR)
        non_editor_id = "DEL-2026-0002"
        with client.session_transaction() as sess:
            sess["delegate_id"] = non_editor_id

        response = client.post(self._WIZARD_URL, data={})
        assert response.status_code == 403
        assert b"Access Denied" in response.data
