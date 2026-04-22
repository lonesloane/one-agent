"""
Permission gating tests for the delegate wizard and delegation detail page.

Covers:
- 'Add New Delegate' button visibility by role and delegation membership
- 403 response when an editor from another delegation POSTs to the wizard
"""

from tests.classical_app.conftest import (  # noqa: F401
    client,
    seeded_engine,
    editor_member_id,
    non_editor_member_id,
    editor_other_delegation_id,
)


_FRA_DETAIL_URL = "/delegations/FRA"
_FRA_STEP1_URL = "/delegations/FRA/delegates/new/step1"
_ADD_DELEGATE_TEXT = "Add New Delegate"


class TestAddDelegateButtonVisibility:
    """'Add New Delegate' button visibility follows editor permissions."""

    def test_add_delegate_button_hidden_for_non_editor(
        self, client, non_editor_member_id
    ) -> None:
        """FRA detail page hides add-delegate link for a non-editor."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = non_editor_member_id

        response = client.get(_FRA_DETAIL_URL, follow_redirects=False)

        assert response.status_code == 200
        assert _ADD_DELEGATE_TEXT not in response.data.decode()

    def test_add_delegate_button_visible_for_editor_of_this_delegation(
        self, client, editor_member_id
    ) -> None:
        """FRA detail page shows add-delegate link for the FRA editor."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id

        response = client.get(_FRA_DETAIL_URL, follow_redirects=False)

        assert response.status_code == 200
        assert _ADD_DELEGATE_TEXT in response.data.decode()

    def test_add_delegate_button_hidden_for_editor_of_other_delegation(
        self, client, editor_other_delegation_id
    ) -> None:
        """FRA detail page hides add-delegate link for a non-FRA editor."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_other_delegation_id

        response = client.get(_FRA_DETAIL_URL, follow_redirects=False)

        assert response.status_code == 200
        assert _ADD_DELEGATE_TEXT not in response.data.decode()


class TestWizardEditorOfOtherDelegation:
    """Wizard rejects an editor whose delegation differs from the URL."""

    def test_direct_post_to_wizard_by_editor_of_other_delegation_returns_403(
        self, client, editor_other_delegation_id
    ) -> None:
        """POST to FRA wizard step1 by a BRA editor returns 403."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_other_delegation_id

        response = client.post(
            _FRA_STEP1_URL,
            data={
                "full_name": "Intruder",
                "email": "intruder@example.com",
                "function": "Analyst",
                "title": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 403
