"""
Tests for wizard step 3 — DAR rows GET/POST handler.

Covers:
- GET step3 without step1/step2 state redirects to step1
- GET step3 with valid state returns 200 and renders form rows
"""

from tests.classical_app.conftest import (  # noqa: F401 (fixtures)
    client,
    seeded_engine,
    temp_db,
    editor_member_id,
)


_STEP3_URL = "/delegations/FRA/delegates/new/step3"
_STEP1_URL = "/delegations/FRA/delegates/new/step1"
_STEP4_URL = "/delegations/FRA/delegates/new/step4"


def _seed_step1_and_step2_state(
    client, editor_member_id: str
) -> None:
    """Seed session with valid step1 and step2 state for FRA."""
    with client.session_transaction() as sess:
        sess["delegate_id"] = editor_member_id
        sess["delegate_wizard"] = {
            "FRA": {
                "step1": {
                    "full_name": "Test User",
                    "email": "test@example.com",
                    "function": "Advisor",
                    "title": "Dr",
                },
                "step2": {
                    "committee_ids": ["EDU"],
                },
                "updated_at": "2099-01-01T00:00:00+00:00",
            }
        }


class TestWizardStep3Get:
    """GET /delegations/<id>/delegates/new/step3 behaviour."""

    def test_get_step3_without_state_redirects_to_step1(
        self, client, editor_member_id
    ) -> None:
        """GET step3 with no session state redirects to step1."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id

        response = client.get(_STEP3_URL, follow_redirects=False)

        assert response.status_code == 302
        assert "step1" in response.location

    def test_get_step3_with_valid_state_returns_200(
        self, client, editor_member_id
    ) -> None:
        """GET step3 returns 200 with form rows when steps 1+2 present."""
        _seed_step1_and_step2_state(client, editor_member_id)

        response = client.get(_STEP3_URL)

        assert response.status_code == 200
        html = response.data.decode()
        # The EDU committee row label should be rendered
        assert "Education Committee" in html
