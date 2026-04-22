"""
Transactional rollback tests for the delegate wizard step 4 submit.

Verifies that a commit failure leaves zero new Delegate or
DocumentAccessRight rows in the database.
"""

from unittest.mock import patch

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from tests.classical_app.conftest import (  # noqa: F401
    client,
    seeded_engine,
    editor_member_id,
)
from shared.database import Delegate, DocumentAccessRight


_STEP4_URL = "/delegations/FRA/delegates/new/step4"
_FUTURE_TS = "2099-01-01T00:00:00+00:00"


def _seed_two_committee_state(client, editor_id: str) -> None:
    """Seed session with step1–3 state for FRA using two committees."""
    with client.session_transaction() as sess:
        sess["delegate_id"] = editor_id
        sess["delegate_wizard"] = {
            "FRA": {
                "step1": {
                    "full_name": "Rollback Person",
                    "email": "rollback.person@example.com",
                    "function": "Analyst",
                    "title": "",
                },
                "step2": {"committee_ids": ["EDU", "TRADE"]},
                "step3": {
                    "rows": [
                        {
                            "committee_id": "EDU",
                            "access_level": "GENERAL",
                            "retroactive": False,
                        },
                        {
                            "committee_id": "TRADE",
                            "access_level": "RESTRICTED",
                            "retroactive": False,
                        },
                    ]
                },
                "updated_at": _FUTURE_TS,
            }
        }


class TestWizardRollback:
    """Step4 commit failure leaves DB state entirely unchanged."""

    def test_submit_failure_rolls_back_all_inserts(
        self, client, editor_member_id, seeded_engine
    ) -> None:
        """Forced commit failure leaves Delegate and DAR row counts unchanged.

        Two committees are used so the expected successful write would create
        1 Delegate + 2 DocumentAccessRight rows.  After the forced failure,
        all three counts must match the pre-submit baseline.
        """
        _seed_two_committee_state(client, editor_member_id)

        with Session(seeded_engine) as db:
            delegate_count_before = db.scalar(
                select(func.count()).select_from(Delegate)
            )
            dar_count_before = db.scalar(
                select(func.count()).select_from(DocumentAccessRight)
            )

        app = client.application
        db_session = app.extensions["db_session"]

        def _raise(*_args, **_kwargs) -> None:
            raise IntegrityError(
                statement=None,
                params=None,
                orig=Exception("forced rollback"),
            )

        with patch.object(db_session, "commit", _raise):
            response = client.post(
                _STEP4_URL,
                data={"submit": "true"},
                follow_redirects=False,
            )

        assert response.status_code == 200  # re-renders step4

        with Session(seeded_engine) as db:
            assert db.scalar(
                select(func.count()).select_from(Delegate)
            ) == delegate_count_before
            assert db.scalar(
                select(func.count()).select_from(DocumentAccessRight)
            ) == dar_count_before
