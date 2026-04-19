"""
Tests for wizard step 4 — review GET handler.

Covers:
- GET step4 without step1/step2/step3 state redirects to step1
- GET step4 with valid state returns 200 and renders review_rows
  with correct approval status labels
"""

from tests.classical_app.conftest import (  # noqa: F401 (fixtures)
    client,
    seeded_engine,
    temp_db,
    editor_member_id,
)


_STEP4_URL = "/delegations/FRA/delegates/new/step4"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_steps_1_to_3(client, editor_member_id: str) -> None:
    """Seed session with valid step1, step2, and step3 state for FRA."""
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
                "step3": {
                    "rows": [
                        {
                            "committee_id": "EDU",
                            "access_level": "RESTRICTED",
                            "retroactive": False,
                        }
                    ]
                },
                "updated_at": "2099-01-01T00:00:00+00:00",
            }
        }


# ---------------------------------------------------------------------------
# GET handler tests
# ---------------------------------------------------------------------------


class TestWizardStep4Get:
    """GET /delegations/<id>/delegates/new/step4 behaviour."""

    def test_get_step4_without_state_redirects_to_step1(
        self, client, editor_member_id
    ) -> None:
        """GET step4 with no session state redirects to step1."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id

        response = client.get(_STEP4_URL, follow_redirects=False)

        assert response.status_code == 302
        assert "step1" in response.location

    def test_get_step4_with_valid_state_returns_200(
        self, client, editor_member_id
    ) -> None:
        """GET step4 with valid state renders review table with labels."""
        _seed_steps_1_to_3(client, editor_member_id)

        response = client.get(_STEP4_URL)

        assert response.status_code == 200
        html = response.data.decode()
        # Committee name should appear in the table
        assert "Education Committee" in html
        # RESTRICTED + non-retroactive → pending delegation head approval
        assert "pending delegation head approval" in html

    def test_get_step4_retroactive_shows_secretariat_label(
        self, client, editor_member_id
    ) -> None:
        """Retroactive row shows 'pending OECD secretariat approval'."""
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
                    "step2": {"committee_ids": ["EDU"]},
                    "step3": {
                        "rows": [
                            {
                                "committee_id": "EDU",
                                "access_level": "GENERAL",
                                "retroactive": True,
                            }
                        ]
                    },
                    "updated_at": "2099-01-01T00:00:00+00:00",
                }
            }

        response = client.get(_STEP4_URL)

        assert response.status_code == 200
        html = response.data.decode()
        assert "pending OECD secretariat approval" in html

    def test_get_step4_general_nonretro_shows_auto_approved(
        self, client, editor_member_id
    ) -> None:
        """GENERAL non-retroactive row shows 'auto-approved' label."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id
            sess["delegate_wizard"] = {
                "FRA": {
                    "step1": {
                        "full_name": "Test User",
                        "email": "test@example.com",
                        "function": "Advisor",
                        "title": "",
                    },
                    "step2": {"committee_ids": ["EDU"]},
                    "step3": {
                        "rows": [
                            {
                                "committee_id": "EDU",
                                "access_level": "GENERAL",
                                "retroactive": False,
                            }
                        ]
                    },
                    "updated_at": "2099-01-01T00:00:00+00:00",
                }
            }

        response = client.get(_STEP4_URL)

        assert response.status_code == 200
        assert b"auto-approved" in response.data
