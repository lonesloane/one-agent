"""
Business-rule wiring and approval route tests for the delegate wizard.

Covers:
- determine_approval_route called once per DAR on step4 POST (spy)
- Parametrized US-5 approval-route matrix (6 scenarios)
- Default access level pre-select in step3 matches compute_default_access_level
"""

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from tests.classical_app.conftest import (  # noqa: F401
    client,
    seeded_engine,
    editor_member_id,
)
from shared.business_rules import compute_default_access_level
from shared.database import (
    ApprovalStatus,
    ClassificationLevel,
    Delegate,
    DocumentAccessRight,
    MembershipType,
)


_FUTURE_TS = "2099-01-01T00:00:00+00:00"
_STEP3_FRA_URL = "/delegations/FRA/delegates/new/step3"


def _complete_wizard(
    client,
    delegation_id: str,
    editor_id: str,
    step3_rows: list[dict],
    *,
    email: str = "wizard.test@example.com",
) -> None:
    """Seed full wizard state directly and POST step4.

    Bypasses steps 1-3 HTTP round-trips by seeding session state, then
    performs the step4 POST that triggers DAR creation.

    Args:
        client: Flask test client.
        delegation_id: Target delegation identifier.
        editor_id: Delegate ID of the acting editor.
        step3_rows: Dicts with committee_id, access_level, retroactive.
        email: Step1 email — used to identify the created Delegate in DB.
    """
    committee_ids = [row["committee_id"] for row in step3_rows]
    with client.session_transaction() as sess:
        sess["delegate_id"] = editor_id
        sess["delegate_wizard"] = {
            delegation_id: {
                "step1": {
                    "full_name": "Route Test",
                    "email": email,
                    "function": "Advisor",
                    "title": "",
                },
                "step2": {"committee_ids": committee_ids},
                "step3": {"rows": step3_rows},
                "updated_at": _FUTURE_TS,
            }
        }
    base = f"/delegations/{delegation_id}/delegates/new"
    client.post(
        f"{base}/step4",
        data={"submit": "true"},
        follow_redirects=False,
    )


class TestDetermineApprovalRouteWiring:
    """Every DAR creation calls determine_approval_route via wizard_helpers."""

    def test_every_dar_routes_through_determine_approval_route(
        self, client, editor_member_id, monkeypatch
    ) -> None:
        """Step4 POST calls determine_approval_route once per DAR row.

        Uses a spy that calls through to the original so actual DB state
        is unaffected.
        """
        import classical_app.routes.wizard_helpers as _wh

        original_fn = _wh.determine_approval_route
        calls: list[tuple] = []

        def _spy(level: ClassificationLevel, retroactive: bool) -> ApprovalStatus:
            calls.append((level, retroactive))
            return original_fn(level, retroactive)

        monkeypatch.setattr(
            "classical_app.routes.wizard_helpers.determine_approval_route",
            _spy,
        )

        step3_rows = [
            {"committee_id": "EDU",
             "access_level": "GENERAL", "retroactive": False},
            {"committee_id": "TRADE",
             "access_level": "RESTRICTED", "retroactive": False},
            {"committee_id": "DAC",
             "access_level": "CONFIDENTIAL", "retroactive": False},
        ]
        _complete_wizard(
            client, "FRA", editor_member_id, step3_rows,
            email="spy.test@example.com",
        )

        assert len(calls) == 3
        assert (ClassificationLevel.GENERAL, False) in calls
        assert (ClassificationLevel.RESTRICTED, False) in calls
        assert (ClassificationLevel.CONFIDENTIAL, False) in calls


_US5_MATRIX = [
    pytest.param(
        "GENERAL", False, ApprovalStatus.AUTO_APPROVED,
        id="general-no-retro",
    ),
    pytest.param(
        "RESTRICTED", False, ApprovalStatus.PENDING_DELEGATION_HEAD,
        id="restricted-no-retro",
    ),
    pytest.param(
        "CONFIDENTIAL", False, ApprovalStatus.PENDING_SECRETARIAT,
        id="confidential-no-retro",
    ),
    pytest.param(
        "GENERAL", True, ApprovalStatus.PENDING_SECRETARIAT,
        id="general-retroactive",
    ),
    pytest.param(
        "CONFIDENTIAL", True, ApprovalStatus.PENDING_SECRETARIAT,
        id="confidential-retroactive",
    ),
    pytest.param(
        "RESTRICTED", True, ApprovalStatus.PENDING_SECRETARIAT,
        id="restricted-retroactive",
    ),
]


class TestApprovalRouteMatrix:
    """US-5 approval-route matrix: all 6 scenarios produce correct DAR status."""

    @pytest.mark.parametrize(
        "access_level,retroactive,expected_status", _US5_MATRIX
    )
    def test_approval_route_matrix(
        self,
        client,
        editor_member_id,
        seeded_engine,
        access_level: str,
        retroactive: bool,
        expected_status: ApprovalStatus,
    ) -> None:
        """Wizard step4 produces DAR with the expected approval_status."""
        email = (
            f"matrix.{access_level.lower()}"
            f".{str(retroactive).lower()}@example.com"
        )
        step3_rows = [
            {
                "committee_id": "EDU",
                "access_level": access_level,
                "retroactive": retroactive,
            }
        ]
        _complete_wizard(
            client, "FRA", editor_member_id, step3_rows, email=email
        )

        with Session(seeded_engine) as db:
            delegate = db.scalars(
                select(Delegate).where(Delegate.email == email)
            ).first()
            assert delegate is not None, f"Delegate not created for {email}"

            dar = db.scalars(
                select(DocumentAccessRight).where(
                    DocumentAccessRight.delegate_id == delegate.id
                )
            ).first()
            assert dar is not None
            assert dar.approval_status == expected_status


class TestDefaultAccessLevelPreselect:
    """Step3 default access level matches compute_default_access_level."""

    def test_compute_default_access_level_preselect_matches_ui(
        self, client, editor_member_id
    ) -> None:
        """Step3 GET for FRA (MEMBER) renders RESTRICTED as default.

        Verifies that _build_step3_form wires compute_default_access_level
        correctly: the helper returns RESTRICTED for MEMBER, and that value
        appears as the selected option in the rendered HTML.
        """
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id
            sess["delegate_wizard"] = {
                "FRA": {
                    "step1": {
                        "full_name": "Preselect Test",
                        "email": "preselect.test@example.com",
                        "function": "Analyst",
                        "title": "",
                    },
                    "step2": {"committee_ids": ["EDU"]},
                    "updated_at": _FUTURE_TS,
                }
            }

        response = client.get(_STEP3_FRA_URL, follow_redirects=False)

        assert response.status_code == 200
        html = response.data.decode()
        assert 'value="RESTRICTED"' in html
        # Exactly one option is selected; it must be the RESTRICTED one
        assert html.count("selected") == 1
        assert html.index('value="RESTRICTED"') < html.index("selected")

        # Helper independently confirms MEMBER defaults to RESTRICTED
        expected = compute_default_access_level(
            MembershipType.MEMBER, "EDU", []
        )
        assert expected == ClassificationLevel.RESTRICTED
