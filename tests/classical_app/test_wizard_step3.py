"""
Tests for wizard step 3 — DAR rows GET/POST handler.

Covers:
- GET step3 without step1/step2 state redirects to step1
- GET step3 with valid state returns 200 and renders form rows
- _allowed_levels logic for MEMBER and PARTNER delegations
- POST saves rows to session and redirects to step4
- POST without state redirects to step1
"""

from datetime import datetime, timezone

from tests.classical_app.conftest import (  # noqa: F401 (fixtures)
    client,
    seeded_engine,
    temp_db,
    editor_member_id,
)
from classical_app.routes.wizard import _allowed_levels
from shared.database import ClassificationLevel, MembershipType


_STEP3_URL = "/delegations/FRA/delegates/new/step3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockFA:
    """Minimal stand-in for a FrameworkAgreement ORM row."""

    def __init__(
        self, committee_id: str, end_date: datetime | None = None
    ) -> None:
        self.committee_id = committee_id
        self.end_date = end_date


class _MockDelegation:
    """Minimal stand-in for a Delegation ORM row."""

    def __init__(
        self,
        membership_type: MembershipType,
        framework_agreements: list | None = None,
    ) -> None:
        self.membership_type = membership_type
        self.framework_agreements = framework_agreements or []


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


# ---------------------------------------------------------------------------
# _allowed_levels unit tests
# ---------------------------------------------------------------------------


class TestAllowedLevels:
    """Unit tests for _allowed_levels helper."""

    def test_allowed_levels_member_returns_all_three(self) -> None:
        """MEMBER delegation always gets all three classification levels."""
        delegation = _MockDelegation(MembershipType.MEMBER)

        result = _allowed_levels(delegation, "EDU")

        assert result == [
            ClassificationLevel.GENERAL,
            ClassificationLevel.RESTRICTED,
            ClassificationLevel.CONFIDENTIAL,
        ]

    def test_allowed_levels_partner_with_active_fa_returns_all_three(
        self,
    ) -> None:
        """PARTNER with an active FA on the committee gets all three levels."""
        active_fa = _MockFA(committee_id="EDU", end_date=None)
        delegation = _MockDelegation(
            MembershipType.PARTNER,
            framework_agreements=[active_fa],
        )

        result = _allowed_levels(delegation, "EDU")

        assert result == [
            ClassificationLevel.GENERAL,
            ClassificationLevel.RESTRICTED,
            ClassificationLevel.CONFIDENTIAL,
        ]

    def test_partner_no_fa_returns_general_and_confidential(
        self,
    ) -> None:
        """PARTNER with no FA gets GENERAL and CONFIDENTIAL only."""
        delegation = _MockDelegation(
            MembershipType.PARTNER,
            framework_agreements=[],
        )

        result = _allowed_levels(delegation, "EDU")

        assert result == [
            ClassificationLevel.GENERAL,
            ClassificationLevel.CONFIDENTIAL,
        ]

    def test_partner_expired_fa_returns_general_and_confidential(
        self,
    ) -> None:
        """PARTNER with an expired FA gets GENERAL and CONFIDENTIAL only."""
        past_date = datetime(2000, 1, 1, tzinfo=timezone.utc).replace(
            tzinfo=None
        )
        expired_fa = _MockFA(committee_id="EDU", end_date=past_date)
        delegation = _MockDelegation(
            MembershipType.PARTNER,
            framework_agreements=[expired_fa],
        )

        result = _allowed_levels(delegation, "EDU")

        assert result == [
            ClassificationLevel.GENERAL,
            ClassificationLevel.CONFIDENTIAL,
        ]


# ---------------------------------------------------------------------------
# GET handler tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# POST handler tests
# ---------------------------------------------------------------------------


class TestWizardStep3Post:
    """POST /delegations/<id>/delegates/new/step3 behaviour."""

    def test_post_step3_saves_rows_and_redirects_to_step4(
        self, client, editor_member_id
    ) -> None:
        """POST with valid data saves step3 rows and redirects to step4."""
        _seed_step1_and_step2_state(client, editor_member_id)

        response = client.post(
            _STEP3_URL,
            data={
                "rows-0-committee_id": "EDU",
                "rows-0-access_level": "RESTRICTED",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "step4" in response.location

        with client.session_transaction() as sess:
            wizard = sess["delegate_wizard"]
            rows = wizard["FRA"]["step3"]["rows"]

        assert len(rows) == 1
        assert rows[0]["committee_id"] == "EDU"
        assert rows[0]["access_level"] == "RESTRICTED"

    def test_post_step3_retroactive_checkbox_parsed(
        self, client, editor_member_id
    ) -> None:
        """Retroactive checkbox is True when present, False when absent."""
        _seed_step1_and_step2_state(client, editor_member_id)

        # POST with retroactive=on
        client.post(
            _STEP3_URL,
            data={
                "rows-0-committee_id": "EDU",
                "rows-0-access_level": "GENERAL",
                "rows-0-retroactive": "on",
            },
        )
        with client.session_transaction() as sess:
            rows_with = sess["delegate_wizard"]["FRA"]["step3"]["rows"]
        assert rows_with[0]["retroactive"] is True

        # POST without retroactive field
        _seed_step1_and_step2_state(client, editor_member_id)
        client.post(
            _STEP3_URL,
            data={
                "rows-0-committee_id": "EDU",
                "rows-0-access_level": "GENERAL",
            },
        )
        with client.session_transaction() as sess:
            rows_without = (
                sess["delegate_wizard"]["FRA"]["step3"]["rows"]
            )
        assert rows_without[0]["retroactive"] is False

    def test_post_step3_without_state_redirects_to_step1(
        self, client, editor_member_id
    ) -> None:
        """POST with empty wizard session redirects to step1."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id

        response = client.post(
            _STEP3_URL,
            data={
                "rows-0-committee_id": "EDU",
                "rows-0-access_level": "GENERAL",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "step1" in response.location
