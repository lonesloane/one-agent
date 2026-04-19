"""
Tests for wizard step 4 POST (single-transaction submit) and cancel.

Covers:
- Happy path: POST step4 creates Delegate + DARs, redirects to confirmation
- Commit failure: rollback, re-renders step4, no Delegate in DB
- Cancel: clears session state, redirects to delegation detail
"""

from sqlalchemy.orm import Session
from sqlalchemy import select

from tests.classical_app.conftest import (  # noqa: F401 (fixtures)
    client,
    seeded_engine,
    temp_db,
    editor_member_id,
)
from shared.database import (
    ApprovalStatus,
    ClassificationLevel,
    Delegate,
    DocumentAccessRight,
)


_STEP4_URL = "/delegations/FRA/delegates/new/step4"
_CANCEL_URL = "/delegations/FRA/delegates/new/cancel"


def _seed_full_wizard_state(client, editor_member_id: str) -> None:
    """Seed session with complete step1–step3 state for FRA."""
    with client.session_transaction() as sess:
        sess["delegate_id"] = editor_member_id
        sess["delegate_wizard"] = {
            "FRA": {
                "step1": {
                    "full_name": "Alice Newperson",
                    "email": "alice.newperson@example.com",
                    "function": "Attaché",
                    "title": "Ms",
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


class TestWizardStep4Post:
    """POST /delegations/<id>/delegates/new/step4 behaviour."""

    def test_happy_path_creates_delegate_and_redirects(
        self, client, editor_member_id, seeded_engine
    ) -> None:
        """POST step4 persists Delegate + DAR and redirects to confirmation."""
        _seed_full_wizard_state(client, editor_member_id)

        response = client.post(
            _STEP4_URL,
            data={"submit": "true"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "confirmation" in response.location

        # Verify Delegate was persisted in the database
        with Session(seeded_engine) as db:
            delegate = db.scalars(
                select(Delegate).where(
                    Delegate.email == "alice.newperson@example.com"
                )
            ).first()
            assert delegate is not None
            assert delegate.full_name == "Alice Newperson"
            assert delegate.function == "Attaché"
            assert delegate.delegation_id == "FRA"

            # Verify DocumentAccessRight was created with correct routing
            dars = db.scalars(
                select(DocumentAccessRight).where(
                    DocumentAccessRight.delegate_id == delegate.id
                )
            ).all()
            assert len(dars) == 1
            assert dars[0].committee_id == "EDU"
            assert dars[0].retroactive is False
            assert (
                dars[0].classification_level
                == ClassificationLevel.RESTRICTED
            )
            # RESTRICTED + non-retroactive → PENDING_DELEGATION_HEAD
            assert (
                dars[0].approval_status
                == ApprovalStatus.PENDING_DELEGATION_HEAD
            )
            assert dars[0].created_by == editor_member_id

        # Verify session: created_delegate_id set, wizard state cleared
        with client.session_transaction() as sess:
            assert "created_delegate_id" in sess
            assert "FRA" in sess["created_delegate_id"]
            wizard = sess.get("delegate_wizard", {})
            assert "FRA" not in wizard

    def test_commit_failure_rollback_rerenders_step4(
        self, client, editor_member_id, seeded_engine
    ) -> None:
        """Commit failure rolls back and re-renders step4 with flash."""
        from sqlalchemy.exc import IntegrityError
        from unittest.mock import patch

        _seed_full_wizard_state(client, editor_member_id)

        app = client.application
        db_session = app.extensions["db_session"]

        def _raise_integrity(*_args, **_kwargs):
            raise IntegrityError(
                statement=None,
                params=None,
                orig=Exception("pk conflict"),
            )

        with patch.object(db_session, "commit", _raise_integrity):
            response = client.post(
                _STEP4_URL,
                data={"submit": "true"},
                follow_redirects=False,
            )

        # Should re-render step4 (200) with flash message
        assert response.status_code == 200
        html = response.data.decode().lower()
        assert "error occurred" in html

        # No Delegate should have been committed
        with Session(seeded_engine) as db:
            delegate = db.scalars(
                select(Delegate).where(
                    Delegate.email == "alice.newperson@example.com"
                )
            ).first()
            assert delegate is None


class TestWizardCancel:
    """POST /delegations/<id>/delegates/new/cancel behaviour."""

    def test_cancel_clears_state_and_redirects_to_detail(
        self, client, editor_member_id
    ) -> None:
        """Cancel clears wizard state and redirects to delegation detail."""
        _seed_full_wizard_state(client, editor_member_id)

        response = client.post(_CANCEL_URL, follow_redirects=False)

        assert response.status_code == 302
        # Must redirect to delegation detail, not back into the wizard
        assert response.location.endswith("/delegations/FRA")

        with client.session_transaction() as sess:
            wizard = sess.get("delegate_wizard", {})
            assert "FRA" not in wizard
