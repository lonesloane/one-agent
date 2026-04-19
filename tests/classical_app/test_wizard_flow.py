"""
Integration and flow tests for the 4-step delegate-creation wizard.

Covers cross-step scenarios not addressed by the individual step test
files: TTL expiry, cancel-then-step1, non-editor access, concurrent
delegation isolation, E2E happy path with all 3 approval routes, and
the confirmation page content.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select

from tests.classical_app.conftest import (  # noqa: F401
    client,
    seeded_engine,
    editor_member_id,
    non_editor_member_id,
)
from shared.database import (
    ApprovalStatus,
    Delegate,
    DocumentAccessRight,
)


_BASE = "/delegations/FRA/delegates/new"
_STEP1_URL = f"{_BASE}/step1"
_STEP2_URL = f"{_BASE}/step2"
_STEP3_URL = f"{_BASE}/step3"
_STEP4_URL = f"{_BASE}/step4"
_CANCEL_URL = f"{_BASE}/cancel"
_CONFIRM_URL = f"{_BASE}/confirmation"

_BRA_BASE = "/delegations/BRA/delegates/new"
_BRA_STEP1_URL = f"{_BRA_BASE}/step1"

_FUTURE_TS = "2099-01-01T00:00:00+00:00"


def _stale_ts() -> str:
    """Return an ISO timestamp 31 minutes in the past."""
    stale = datetime.now(timezone.utc) - timedelta(minutes=31)
    return stale.isoformat()


def _seed_full_fra_state(
    client, editor_id: str, *, name: str = "Flow Test"
) -> None:
    """Seed full step1–step3 wizard state for FRA."""
    with client.session_transaction() as sess:
        sess["delegate_id"] = editor_id
        sess["delegate_wizard"] = {
            "FRA": {
                "step1": {
                    "full_name": name,
                    "email": "flow.test@example.com",
                    "function": "Advisor",
                    "title": "Dr",
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
                "updated_at": _FUTURE_TS,
            }
        }


def _post_full_wizard(
    client,
    delegation_id: str,
    editor_id: str,
    step3_rows: list[dict],
):
    """
    Drive the wizard HTTP POSTs for steps 1–4.

    Seeds delegate_id in the session, then POSTs step1, step2, step3,
    and step4 in sequence.  Returns the final step4 response.

    Args:
        client: Flask test client.
        delegation_id: Two-letter delegation code (e.g. "FRA").
        editor_id: Delegate ID to set as the session user.
        step3_rows: List of dicts with keys committee_id, access_level,
            and retroactive (bool).

    Returns:
        The step4 POST response (follow_redirects=False).
    """
    base = f"/delegations/{delegation_id}/delegates/new"
    with client.session_transaction() as sess:
        sess["delegate_id"] = editor_id

    client.post(
        f"{base}/step1",
        data={
            "full_name": "E2E Test Person",
            "email": "e2e.test@example.com",
            "function": "Attaché",
            "title": "Ms",
        },
        follow_redirects=False,
    )

    committee_ids = [row["committee_id"] for row in step3_rows]
    client.post(
        f"{base}/step2",
        data={"committee_ids": committee_ids},
        follow_redirects=False,
    )

    step3_data: dict = {}
    for i, row in enumerate(step3_rows):
        step3_data[f"rows-{i}-committee_id"] = row["committee_id"]
        step3_data[f"rows-{i}-access_level"] = row["access_level"]
        if row.get("retroactive"):
            step3_data[f"rows-{i}-retroactive"] = "on"
    client.post(
        f"{base}/step3",
        data=step3_data,
        follow_redirects=False,
    )

    return client.post(
        f"{base}/step4",
        data={"submit": "true"},
        follow_redirects=False,
    )


class TestTTLExpiry:
    """Wizard state TTL: stale state redirects to step1."""

    def test_stale_state_on_step2_get_redirects_to_step1(
        self, client, editor_member_id
    ) -> None:
        """GET step2 with >30-min-old state redirects to step1."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id
            sess["delegate_wizard"] = {
                "FRA": {
                    "step1": {
                        "full_name": "Old User",
                        "email": "old@example.com",
                        "function": "Advisor",
                        "title": "",
                    },
                    "updated_at": _stale_ts(),
                }
            }

        response = client.get(_STEP2_URL, follow_redirects=False)

        assert response.status_code == 302
        assert "step1" in response.location

    def test_stale_state_on_step3_get_redirects_to_step1(
        self, client, editor_member_id
    ) -> None:
        """GET step3 with stale updated_at redirects to step1."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id
            sess["delegate_wizard"] = {
                "FRA": {
                    "step1": {
                        "full_name": "Old User",
                        "email": "old@example.com",
                        "function": "Advisor",
                        "title": "",
                    },
                    "step2": {"committee_ids": ["EDU"]},
                    "updated_at": _stale_ts(),
                }
            }

        response = client.get(_STEP3_URL, follow_redirects=False)

        assert response.status_code == 302
        assert "step1" in response.location


class TestCancel:
    """Cancel clears session; subsequent step1 GET renders empty form."""

    def test_cancel_then_step1_shows_empty_form(
        self, client, editor_member_id
    ) -> None:
        """POST cancel then GET step1 returns blank form, not prefilled."""
        _seed_full_fra_state(client, editor_member_id)

        cancel_resp = client.post(_CANCEL_URL, follow_redirects=False)
        assert cancel_resp.status_code == 302

        step1_resp = client.get(_STEP1_URL, follow_redirects=True)

        assert step1_resp.status_code == 200
        html = step1_resp.data.decode()
        # The previously seeded name must not appear pre-filled
        assert "Flow Test" not in html

    def test_cancel_clears_fra_state_from_session(
        self, client, editor_member_id
    ) -> None:
        """POST cancel removes FRA wizard state from the session."""
        _seed_full_fra_state(client, editor_member_id)

        client.post(_CANCEL_URL, follow_redirects=False)

        with client.session_transaction() as sess:
            wizard = sess.get("delegate_wizard", {})
            assert "FRA" not in wizard


class TestNonEditorAccess:
    """Non-editor delegate receives 403 on wizard POST."""

    def test_non_editor_post_step1_returns_403(
        self, client, non_editor_member_id
    ) -> None:
        """POST step1 as a non-editor delegate on FRA returns 403."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = non_editor_member_id

        response = client.post(
            _STEP1_URL,
            data={
                "full_name": "Test Person",
                "email": "test@example.com",
                "function": "Advisor",
                "title": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 403

    def test_non_editor_get_step1_returns_403(
        self, client, non_editor_member_id
    ) -> None:
        """GET step1 as a non-editor delegate on FRA returns 403."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = non_editor_member_id

        response = client.get(_STEP1_URL, follow_redirects=False)

        assert response.status_code == 403


class TestConcurrentDelegations:
    """Wizard state is isolated per delegation key."""

    def test_posting_to_fra_does_not_alter_bra_state(
        self, client, editor_member_id
    ) -> None:
        """Advancing FRA wizard leaves BRA state unchanged in session."""
        bra_step1 = {
            "full_name": "BRA Person",
            "email": "bra@example.com",
            "function": "Analyst",
            "title": "",
        }
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id
            sess["delegate_wizard"] = {
                "FRA": {
                    "step1": {
                        "full_name": "FRA Person",
                        "email": "fra@example.com",
                        "function": "Advisor",
                        "title": "",
                    },
                    "updated_at": _FUTURE_TS,
                },
                "BRA": {
                    "step1": bra_step1,
                    "updated_at": _FUTURE_TS,
                },
            }

        # Advance FRA to step2 by POSTing step1
        client.post(
            _STEP1_URL,
            data={
                "full_name": "FRA Person Updated",
                "email": "fra2@example.com",
                "function": "Advisor",
                "title": "",
            },
            follow_redirects=False,
        )

        with client.session_transaction() as sess:
            wizard = sess.get("delegate_wizard", {})
            bra_state = wizard.get("BRA", {}).get("step1", {})

        # BRA step1 state must be exactly as seeded
        assert bra_state["full_name"] == bra_step1["full_name"]
        assert bra_state["email"] == bra_step1["email"]


class TestE2EHappyPath:
    """Full wizard flow produces Delegate and all 3 approval routes."""

    def test_e2e_member_delegation_all_three_statuses(
        self, client, editor_member_id, seeded_engine
    ) -> None:
        """Step1→2→3→4 creates 3 DARs with distinct approval statuses."""
        step3_rows = [
            # retroactive absent → AUTO_APPROVED
            {"committee_id": "EDU", "access_level": "GENERAL",
             "retroactive": False},
            # restricted, no retroactive → PENDING_DELEGATION_HEAD
            {"committee_id": "TRADE", "access_level": "RESTRICTED",
             "retroactive": False},
            # retroactive → PENDING_SECRETARIAT
            {"committee_id": "DAC", "access_level": "CONFIDENTIAL",
             "retroactive": True},
        ]
        r4 = _post_full_wizard(
            client, "FRA", editor_member_id, step3_rows
        )

        assert r4.status_code == 302
        assert "confirmation" in r4.location

        with Session(seeded_engine) as db:
            delegate = db.scalars(
                select(Delegate).where(
                    Delegate.email == "e2e.test@example.com"
                )
            ).first()
            assert delegate is not None
            assert delegate.delegation_id == "FRA"

            dars = db.scalars(
                select(DocumentAccessRight).where(
                    DocumentAccessRight.delegate_id == delegate.id
                )
            ).all()
            assert len(dars) == 3

            statuses = {d.committee_id: d.approval_status for d in dars}
            assert statuses["EDU"] == ApprovalStatus.AUTO_APPROVED
            assert (
                statuses["TRADE"]
                == ApprovalStatus.PENDING_DELEGATION_HEAD
            )
            assert (
                statuses["DAC"] == ApprovalStatus.PENDING_SECRETARIAT
            )


class TestRetroactivePendingSecretariat:
    """Retroactive=True always routes to PENDING_SECRETARIAT."""

    def test_retroactive_dar_has_pending_secretariat_status(
        self, client, editor_member_id, seeded_engine
    ) -> None:
        """Seeded step4 state with retroactive row → PENDING_SECRETARIAT."""
        retro_row = {
            "committee_id": "EDU",
            "access_level": "GENERAL",
            "retroactive": True,
        }
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id
            sess["delegate_wizard"] = {"FRA": {
                "step1": {
                    "full_name": "Retro Person",
                    "email": "retro.person@example.com",
                    "function": "Advisor",
                    "title": "",
                },
                "step2": {"committee_ids": ["EDU"]},
                "step3": {"rows": [retro_row]},
                "updated_at": _FUTURE_TS,
            }}

        client.post(
            _STEP4_URL,
            data={"submit": "true"},
            follow_redirects=False,
        )

        with Session(seeded_engine) as db:
            delegate = db.scalars(
                select(Delegate).where(
                    Delegate.email == "retro.person@example.com"
                )
            ).first()
            assert delegate is not None

            dar = db.scalars(
                select(DocumentAccessRight).where(
                    DocumentAccessRight.delegate_id == delegate.id
                )
            ).first()
            assert dar is not None
            assert dar.retroactive is True
            assert (
                dar.approval_status == ApprovalStatus.PENDING_SECRETARIAT
            )


class TestConfirmationPage:
    """Confirmation page renders delegate id, name, and status labels."""

    def test_confirmation_shows_delegate_info_and_status_labels(
        self, client, editor_member_id
    ) -> None:
        """POST step4 → redirect → confirmation page has correct content."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id
            sess["delegate_wizard"] = {
                "FRA": {
                    "step1": {
                        "full_name": "Confirm Test",
                        "email": "confirm.test@example.com",
                        "function": "Attaché",
                        "title": "Mr",
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
                    "updated_at": _FUTURE_TS,
                }
            }

        response = client.post(
            _STEP4_URL,
            data={"submit": "true"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.data.decode()
        assert "Confirm Test" in html
        assert "auto-approved" in html.lower()

    def test_confirmation_without_created_id_redirects(
        self, client, editor_member_id
    ) -> None:
        """GET /confirmation with no created_delegate_id redirects away."""
        with client.session_transaction() as sess:
            sess["delegate_id"] = editor_member_id

        response = client.get(_CONFIRM_URL, follow_redirects=False)

        assert response.status_code == 302
        assert "/delegations/FRA" in response.location
