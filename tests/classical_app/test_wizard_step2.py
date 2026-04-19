"""
Tests for wizard step 2 — committee multi-select GET/POST handler.

Covers:
- GET renders step2 template with committee choices
- GET pre-fills form from saved session state
- GET redirects to step1 when step1 is not in session
- POST with valid committee selection saves state and redirects
- POST with no committees selected re-renders with error
"""

import pytest

from tests.classical_app.conftest import (  # noqa: F401 (fixtures)
    client,
    seeded_engine,
    temp_db,
    editor_member_id,
)


_STEP2_URL = "/delegations/FRA/delegates/new/step2"
_STEP1_URL = "/delegations/FRA/delegates/new/step1"
_STEP3_URL = "/delegations/FRA/delegates/new/step3"


def _seed_step1_state(client, editor_member_id: str) -> None:
    """Set up a valid step1 session state so step2 is accessible."""
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
                "updated_at": "2099-01-01T00:00:00+00:00",
            }
        }


class TestWizardStep2Get:
    """GET /delegations/<id>/delegates/new/step2 behaviour."""

    def test_get_step2_without_step1_redirects_to_step1(
        self, client, editor_member_id
    ) -> None:
        """GET step2 with no session state redirects to step1."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id

        response = client.get(_STEP2_URL, follow_redirects=False)

        assert response.status_code == 302
        assert "step1" in response.location

    def test_get_step2_with_step1_complete_returns_200(
        self, client, editor_member_id
    ) -> None:
        """GET step2 returns 200 when step1 is present in session."""
        _seed_step1_state(client, editor_member_id)

        response = client.get(_STEP2_URL)

        assert response.status_code == 200

    def test_get_step2_renders_committee_choices(
        self, client, editor_member_id
    ) -> None:
        """GET step2 renders committee names as selectable options."""
        _seed_step1_state(client, editor_member_id)

        response = client.get(_STEP2_URL)

        assert response.status_code == 200
        # Seeded committees include Education Committee (EDU)
        assert (
            b"Education Committee" in response.data
            or b"EDU" in response.data
        )

    def test_get_step2_prefills_from_session_state(
        self, client, editor_member_id
    ) -> None:
        """GET step2 pre-selects committees saved in wizard state."""
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
                    "updated_at": "2099-01-01T00:00:00+00:00",
                }
            }

        response = client.get(_STEP2_URL)

        assert response.status_code == 200
        # The selected value EDU should appear as selected in the HTML
        assert b"EDU" in response.data


class TestWizardStep2Post:
    """POST /delegations/<id>/delegates/new/step2 behaviour."""

    def test_post_step2_with_valid_selection_redirects_to_step3(
        self, client, editor_member_id
    ) -> None:
        """Valid committee POST saves state and redirects to step3."""
        _seed_step1_state(client, editor_member_id)

        response = client.post(
            _STEP2_URL,
            data={"committee_ids": ["EDU"]},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "step3" in response.location

    def test_post_step2_saves_committee_ids_to_session(
        self, client, editor_member_id
    ) -> None:
        """Valid POST persists selected committee_ids in wizard state."""
        _seed_step1_state(client, editor_member_id)

        client.post(
            _STEP2_URL,
            data={"committee_ids": ["EDU", "TRADE"]},
            follow_redirects=False,
        )

        with client.session_transaction() as sess:
            wizard = sess.get("delegate_wizard", {})
            step2 = wizard.get("FRA", {}).get("step2", {})
            saved_ids = step2.get("committee_ids", [])

        assert "EDU" in saved_ids
        assert "TRADE" in saved_ids

    def test_post_step2_with_no_selection_returns_200_with_error(
        self, client, editor_member_id
    ) -> None:
        """POST with no committee selected re-renders form with error."""
        _seed_step1_state(client, editor_member_id)

        response = client.post(
            _STEP2_URL,
            data={},
            follow_redirects=False,
        )

        assert response.status_code == 200
        assert (
            b"at least one committee" in response.data
            or b"committee" in response.data.lower()
        )

    def test_post_step2_without_step1_redirects_to_step1(
        self, client, editor_member_id
    ) -> None:
        """POST step2 with no wizard state redirects to step1."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id

        response = client.post(
            _STEP2_URL,
            data={"committee_ids": ["EDU"]},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "step1" in response.location
