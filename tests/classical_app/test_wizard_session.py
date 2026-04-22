"""
Session state tests for the 4-step delegate-creation wizard.

Covers back-navigation data persistence and step-guard redirects
when earlier session state is absent.
"""

from tests.classical_app.conftest import (  # noqa: F401
    client,
    seeded_engine,
    editor_member_id,
)


_BASE = "/delegations/FRA/delegates/new"
_STEP2_URL = f"{_BASE}/step2"
_STEP3_URL = f"{_BASE}/step3"
_FUTURE_TS = "2099-01-01T00:00:00+00:00"


def _seed_step1_state(client, editor_id: str) -> None:
    """Seed step1 wizard state for FRA in the session."""
    with client.session_transaction() as sess:
        sess["delegate_id"] = editor_id
        sess["delegate_wizard"] = {
            "FRA": {
                "step1": {
                    "full_name": "Session Test",
                    "email": "session.test@example.com",
                    "function": "Advisor",
                    "title": "",
                },
                "updated_at": _FUTURE_TS,
            }
        }


class TestWizardSessionBackNavigation:
    """Returning to a prior step shows previously entered data."""

    def test_back_preserves_prior_step_data(
        self, client, editor_member_id
    ) -> None:
        """GET step2 after step2 was submitted shows prior committee_ids.

        Scenario: user selects EDU on step2, advances, then navigates
        back.  The step2 form must render EDU as checked.
        """
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id
            sess["delegate_wizard"] = {
                "FRA": {
                    "step1": {
                        "full_name": "Back Test",
                        "email": "back.test@example.com",
                        "function": "Analyst",
                        "title": "",
                    },
                    "step2": {"committee_ids": ["EDU"]},
                    "updated_at": _FUTURE_TS,
                }
            }

        response = client.get(_STEP2_URL, follow_redirects=False)

        assert response.status_code == 200
        html = response.data.decode()
        # EDU checkbox must be rendered as checked
        assert 'value="EDU"' in html
        assert "checked" in html


class TestWizardSessionStepGuards:
    """Accessing a later step without earlier state redirects to step1."""

    def test_step3_post_without_step2_redirects_to_step1(
        self, client, editor_member_id
    ) -> None:
        """POST step3 when step2 state is absent redirects to step1.

        The step guard runs before the POST handler so the request
        is rejected even though it is a write operation.
        """
        _seed_step1_state(client, editor_member_id)

        response = client.post(
            _STEP3_URL,
            data={"rows-0-committee_id": "EDU",
                  "rows-0-access_level": "GENERAL"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "step1" in response.location
