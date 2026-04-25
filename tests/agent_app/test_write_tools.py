"""Unit tests for write tools in agent_app/tools.py.

Covers: create_delegate, create_document_access_rights, HITL enforcement,
and rollback-on-error behaviour.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from agent_app.tools import create_delegate, create_document_access_rights
from shared.database import (
    ApprovalStatus,
    ClassificationLevel,
    Committee,
    Delegate,
    DelegateRole,
    Delegation,
    DocumentAccessRight,
    FrameworkAgreement,
    MembershipType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _make_delegation(
    delegation_id: str,
    membership_type: MembershipType = MembershipType.MEMBER,
) -> Delegation:
    """Return a Delegation ORM instance with test defaults."""
    return Delegation(
        id=delegation_id,
        name=f"Delegation {delegation_id}",
        membership_type=membership_type,
    )


def _make_delegate(
    delegate_id: str,
    delegation_id: str,
    role: DelegateRole = DelegateRole.DELEGATE,
) -> Delegate:
    """Return a Delegate ORM instance with test defaults."""
    return Delegate(
        id=delegate_id,
        full_name=f"Test Delegate {delegate_id}",
        email=f"{delegate_id.lower()}@test.com",
        function="Tester",
        delegation_id=delegation_id,
        accreditation_date=datetime(2026, 1, 1),
        role=role,
    )


def _make_editor_ctx(editor_id: str) -> MagicMock:
    """Return a mock FunctionInvocationContext with the given editor id."""
    ctx = MagicMock()
    ctx.kwargs = {"delegate_id": editor_id}
    return ctx


# ---------------------------------------------------------------------------
# Class 1: TestCreateDelegate
# ---------------------------------------------------------------------------


class TestCreateDelegate:
    """Tests for create_delegate write tool."""

    def test_editor_creates_delegate_persists_row(
        self, engine: object
    ) -> None:
        """Editor creates a delegate; new row appears in the database."""
        with Session(engine) as sess:
            sess.add(Committee(id="EDU", name="Education"))
            sess.add(_make_delegation("FRA"))
            sess.add(
                _make_delegate(
                    "DEL-2026-0001", "FRA", DelegateRole.DELEGATION_EDITOR
                )
            )
            sess.commit()

        ctx = _make_editor_ctx("DEL-2026-0001")
        with patch("agent_app.tools._engine", engine):
            result = create_delegate(
                full_name="New Person",
                email="new@example.com",
                function="Policy Analyst",
                delegation_id="FRA",
                ctx=ctx,
            )

        data = json.loads(result)
        # ID generator uses max(seq)+1 over DEL-YYYY-NNNN, so next is 0002
        assert data["id"] == "DEL-2026-0002"
        assert data["full_name"] == "New Person"
        assert data["delegation_id"] == "FRA"
        assert data["role"] == "DELEGATE"

        # Verify row persisted
        with Session(engine) as sess:
            row = sess.get(Delegate, "DEL-2026-0002")
        assert row is not None
        assert row.full_name == "New Person"
        assert row.email == "new@example.com"
        assert row.function == "Policy Analyst"
        assert row.role == DelegateRole.DELEGATE

    def test_non_editor_raises_permission_error(self, engine: object) -> None:
        """Caller with DELEGATE role (not DELEGATION_EDITOR) raises PermissionError."""
        with Session(engine) as sess:
            sess.add(_make_delegation("FRA"))
            # Editor seeded so FK is satisfied; caller is a plain DELEGATE
            sess.add(
                _make_delegate(
                    "DEL-2026-0001", "FRA", DelegateRole.DELEGATION_EDITOR
                )
            )
            sess.add(
                _make_delegate("DEL-2026-0002", "FRA", DelegateRole.DELEGATE)
            )
            sess.commit()

        ctx = _make_editor_ctx("DEL-2026-0002")
        with (
            patch("agent_app.tools._engine", engine),
            pytest.raises(PermissionError),
        ):
            create_delegate(
                full_name="Should Fail",
                email="fail@example.com",
                function="None",
                delegation_id="FRA",
                ctx=ctx,
            )

    def test_unknown_delegation_returns_error_json(
        self, engine: object
    ) -> None:
        """Unknown delegation_id returns a structured JSON error, not an exception."""
        with Session(engine) as sess:
            sess.add(_make_delegation("FRA"))
            sess.add(
                _make_delegate(
                    "DEL-2026-0001", "FRA", DelegateRole.DELEGATION_EDITOR
                )
            )
            sess.commit()

        ctx = _make_editor_ctx("DEL-2026-0001")
        with patch("agent_app.tools._engine", engine):
            result = create_delegate(
                full_name="Alice",
                email="alice@example.com",
                function="Analyst",
                delegation_id="BOGUS",
                ctx=ctx,
            )

        data = json.loads(result)
        assert "error" in data
        assert "BOGUS" in data["error"]
        assert data["delegation_id"] == "BOGUS"

        # No Delegate row must have been inserted despite the error path
        with Session(engine) as sess:
            count = sess.query(Delegate).count()
        assert count == 1  # only the seeded editor remains


# ---------------------------------------------------------------------------
# Class 2: TestCreateDocumentAccessRights
# ---------------------------------------------------------------------------

# Parametrize 4 distinct DAR routing scenarios (PRD had 5; scenarios 1 & 2
# were identical — collapsed to a single test; deviation documented below).
#
# Scenario deviation note
# -----------------------
# The PRD listed "Confidential retroactive → PENDING_SECRETARIAT" as scenario
# 5.  However, compute_default_access_level() only ever returns RESTRICTED or
# GENERAL (never CONFIDENTIAL) — there is no combination of inputs to this
# tool that produces a CONFIDENTIAL DAR.  Scenario 5 is therefore replaced by
# the closest reachable path: retroactive=True for a MEMBER delegation, which
# routes to PENDING_SECRETARIAT via determine_approval_route regardless of the
# classification level.  The approval behaviour (PENDING_SECRETARIAT) is
# identical to the PRD intent.

_DAR_SCENARIOS = [
    pytest.param(
        MembershipType.MEMBER,
        False,  # no FA
        False,  # retroactive
        ClassificationLevel.RESTRICTED,
        ApprovalStatus.PENDING_DELEGATION_HEAD,
        id="member-non-retroactive",
    ),
    pytest.param(
        MembershipType.PARTNER,
        False,  # no FA for this committee
        False,
        ClassificationLevel.GENERAL,
        ApprovalStatus.AUTO_APPROVED,
        id="partner-no-fa",
    ),
    pytest.param(
        MembershipType.PARTNER,
        True,  # active FA on the committee
        False,
        ClassificationLevel.RESTRICTED,
        ApprovalStatus.PENDING_DELEGATION_HEAD,
        id="partner-with-active-fa",
    ),
    pytest.param(
        MembershipType.MEMBER,
        False,
        True,  # retroactive
        ClassificationLevel.RESTRICTED,
        ApprovalStatus.PENDING_SECRETARIAT,
        id="member-retroactive-routes-to-secretariat",
    ),
]


class TestCreateDocumentAccessRights:
    """Tests for create_document_access_rights write tool.

    Each test parametrizes over the 4 achievable DAR routing scenarios and
    asserts both the JSON return value and the persisted database row.
    """

    @pytest.mark.parametrize(
        "membership_type,has_active_fa,retroactive,exp_level,exp_status",
        _DAR_SCENARIOS,
    )
    def test_dar_routing_scenario(
        self,
        engine: object,
        membership_type: MembershipType,
        has_active_fa: bool,
        retroactive: bool,
        exp_level: ClassificationLevel,
        exp_status: ApprovalStatus,
    ) -> None:
        """DAR is created with correct classification_level and approval_status."""
        committee_id = "EDU"

        with Session(engine) as sess:
            sess.add(Committee(id=committee_id, name="Education"))
            deleg = _make_delegation("FRA", membership_type)
            sess.add(deleg)

            editor = _make_delegate(
                "DEL-2026-0001", "FRA", DelegateRole.DELEGATION_EDITOR
            )
            sess.add(editor)

            target = _make_delegate(
                "DEL-2026-0002", "FRA", DelegateRole.DELEGATE
            )
            sess.add(target)

            if has_active_fa:
                sess.add(
                    FrameworkAgreement(
                        delegation_id="FRA",
                        committee_id=committee_id,
                        start_date=_NOW - timedelta(days=30),
                        end_date=None,  # ongoing — active
                    )
                )

            sess.commit()

        ctx = _make_editor_ctx("DEL-2026-0001")
        with patch("agent_app.tools._engine", engine):
            result = create_document_access_rights(
                delegate_id="DEL-2026-0002",
                committee_id=committee_id,
                retroactive=retroactive,
                ctx=ctx,
            )

        # Assert JSON return value
        data = json.loads(result)
        assert isinstance(data["id"], int)
        assert data["delegate_id"] == "DEL-2026-0002"
        assert data["committee_id"] == committee_id
        assert data["classification_level"] == exp_level.value
        assert data["approval_status"] == exp_status.value
        assert data["retroactive"] is retroactive

        # Assert persisted row
        with Session(engine) as sess:
            row = sess.get(DocumentAccessRight, data["id"])
        assert row is not None
        assert row.delegate_id == "DEL-2026-0002"
        assert row.committee_id == committee_id
        assert row.classification_level == exp_level
        assert row.approval_status == exp_status
        assert row.retroactive is retroactive


# ---------------------------------------------------------------------------
# Class 3: TestHITLEnforcement
# ---------------------------------------------------------------------------


class TestHITLEnforcement:
    """Verify that both write tools declare approval_mode='always_require'."""

    def test_create_delegate_requires_approval(self) -> None:
        """create_delegate must declare HITL approval mode."""
        assert (
            getattr(create_delegate, "approval_mode", None) == "always_require"
        )

    def test_create_document_access_rights_requires_approval(self) -> None:
        """create_document_access_rights must declare HITL approval mode."""
        assert (
            getattr(create_document_access_rights, "approval_mode", None)
            == "always_require"
        )


# ---------------------------------------------------------------------------
# Class 4: TestRollbackOnError
# ---------------------------------------------------------------------------


class TestRollbackOnError:
    """Verify that SQLAlchemyError during commit triggers rollback and re-raise."""

    def test_commit_error_leaves_no_dar_row(self, engine: object) -> None:
        """When session.commit raises SQLAlchemyError, no DAR row is persisted."""
        with Session(engine) as sess:
            sess.add(Committee(id="EDU", name="Education"))
            sess.add(_make_delegation("FRA", MembershipType.MEMBER))
            sess.add(
                _make_delegate(
                    "DEL-2026-0001", "FRA", DelegateRole.DELEGATION_EDITOR
                )
            )
            sess.add(
                _make_delegate("DEL-2026-0002", "FRA", DelegateRole.DELEGATE)
            )
            sess.commit()

        ctx = _make_editor_ctx("DEL-2026-0001")

        # Patch commit AFTER seeding so the seed itself is not disrupted.
        # Reason: Session.commit is patched on the class so every subsequent
        # session inside the tool's context manager will raise on commit/flush.
        with (
            patch.object(
                Session, "commit", side_effect=SQLAlchemyError("forced")
            ),
            patch("agent_app.tools._engine", engine),
            pytest.raises(SQLAlchemyError),
        ):
            create_document_access_rights(
                delegate_id="DEL-2026-0002",
                committee_id="EDU",
                retroactive=False,
                ctx=ctx,
            )

        # No DocumentAccessRight row must exist after the rollback
        with Session(engine) as sess:
            count = sess.query(DocumentAccessRight).count()
        assert count == 0

    def test_create_delegate_commit_error_leaves_no_delegate_row(
        self, engine: object
    ) -> None:
        """When session.commit raises SQLAlchemyError, no Delegate row is persisted."""
        with Session(engine) as sess:
            sess.add(_make_delegation("FRA", MembershipType.MEMBER))
            sess.add(
                _make_delegate(
                    "DEL-2026-0001", "FRA", DelegateRole.DELEGATION_EDITOR
                )
            )
            sess.commit()

        seeded_count: int
        with Session(engine) as sess:
            seeded_count = sess.query(Delegate).count()

        ctx = _make_editor_ctx("DEL-2026-0001")

        # Patch commit AFTER seeding so the seed itself is not disrupted.
        with (
            patch.object(
                Session, "commit", side_effect=SQLAlchemyError("forced")
            ),
            patch("agent_app.tools._engine", engine),
            pytest.raises(SQLAlchemyError),
        ):
            create_delegate(
                full_name="Should Not Persist",
                email="ghost@example.com",
                function="Ghost",
                delegation_id="FRA",
                ctx=ctx,
            )

        # Delegate count must be unchanged after the forced rollback
        with Session(engine) as sess:
            count = sess.query(Delegate).count()
        assert count == seeded_count
