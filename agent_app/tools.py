"""ONE-MP Agent — DB-backed tool wrappers (read + write)."""

import json
import os
from datetime import UTC, datetime
from typing import Annotated

from agent_framework import FunctionInvocationContext, tool
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session as _Session

from classical_app.routes.wizard_helpers import (
    _generate_delegate_id as _next_delegate_id,
)
from shared.business_rules import get_visible_agenda_documents
from shared.database import (
    Delegate,
    DelegateRole,
    Delegation,
    Meeting,
    delegate_committees,
    get_engine,
)

_engine = get_engine(os.environ.get("DATABASE_PATH", "one_agent.db"))


@tool(approval_mode="never_require")
def get_delegation_info(
    delegation_id: Annotated[
        str,
        Field(description="Delegation ID (e.g. 'FRA', 'DEU')"),
    ],
) -> str:
    """Look up delegation info including delegates and framework agreements.

    Args:
        delegation_id: The unique delegation identifier to query.

    Returns:
        JSON string with keys: id, name, membership_type, delegates,
        framework_agreements. Returns null-filled structure when not found.
    """
    with _Session(_engine) as session:
        delegation = session.get(Delegation, delegation_id)
        if delegation is None:
            return json.dumps(
                {
                    "id": delegation_id,
                    "name": None,
                    "membership_type": None,
                    "delegates": [],
                    "framework_agreements": [],
                }
            )
        delegates = [
            {"id": d.id, "full_name": d.full_name}
            for d in delegation.delegates
        ]
        framework_agreements = [
            {
                "id": fa.id,
                "committee_id": fa.committee_id,
                "start_date": (
                    fa.start_date.isoformat() if fa.start_date else None
                ),
                "end_date": (fa.end_date.isoformat() if fa.end_date else None),
            }
            for fa in delegation.framework_agreements
        ]
        return json.dumps(
            {
                "id": delegation.id,
                "name": delegation.name,
                "membership_type": delegation.membership_type.value,
                "delegates": delegates,
                "framework_agreements": framework_agreements,
            }
        )


def _serialize_delegate_profile(session: _Session, delegate_id: str) -> str:
    """Serialize a delegate's profile, committees, and DARs to JSON.

    Args:
        session: Active SQLAlchemy session.
        delegate_id: The delegate ID to look up.

    Returns:
        JSON string with keys: id, full_name, delegation_id, committees,
        access_rights. Returns null-filled structure when delegate_id is
        missing from the DB.
    """
    delegate = session.get(Delegate, delegate_id)
    if delegate is None:
        return json.dumps(
            {
                "id": delegate_id or None,
                "full_name": None,
                "delegation_id": None,
                "committees": [],
                "access_rights": [],
            }
        )
    committees = [{"id": c.id, "name": c.name} for c in delegate.committees]
    access_rights = [
        {
            "id": dar.id,
            "committee_id": dar.committee_id,
            "classification_level": dar.classification_level.value,
            "approval_status": dar.approval_status.value,
        }
        for dar in delegate.document_access_rights
    ]
    return json.dumps(
        {
            "id": delegate.id,
            "full_name": delegate.full_name,
            "delegation_id": delegate.delegation_id,
            "committees": committees,
            "access_rights": access_rights,
        }
    )


@tool(approval_mode="never_require")
def lookup_delegate(
    delegate_id: Annotated[
        str,
        Field(description="Delegate ID (e.g. 'DEL-2026-0001')"),
    ],
) -> str:
    """Look up a delegate's profile, committees, and document access rights.

    Use this tool only for explicit by-id lookups of *other* delegates.
    To get the current session's delegate, use ``whoami`` instead.

    Args:
        delegate_id: The unique delegate identifier to query.

    Returns:
        JSON string with keys: id, full_name, delegation_id, committees,
        access_rights. Returns null-filled structure when not found.
    """
    with _Session(_engine) as session:
        return _serialize_delegate_profile(session, delegate_id)


# Reason: FunctionInvocationContext params are excluded from the
# model-visible tool schema; delegate_id stays invisible to the model.
@tool(approval_mode="never_require")
def whoami(ctx: FunctionInvocationContext) -> str:
    """Return the current session delegate's profile.

    The delegate identity is injected via FunctionInvocationContext using
    the ``delegate_id`` key from function_invocation_kwargs (mirrors the
    ``get_upcoming_meetings`` pattern). This tool exists so the model can
    confirm the current delegate's name without having to know — or
    hallucinate — the delegate_id.

    Args:
        ctx: Runtime context providing delegate_id via kwargs injection.

    Returns:
        JSON string with keys: id, full_name, delegation_id, committees,
        access_rights. Returns null-filled structure when no delegate_id
        is present in context.
    """
    delegate_id = ctx.kwargs.get("delegate_id", "")
    if not delegate_id:
        return json.dumps(
            {
                "id": None,
                "full_name": None,
                "delegation_id": None,
                "committees": [],
                "access_rights": [],
            }
        )
    with _Session(_engine) as session:
        return _serialize_delegate_profile(session, delegate_id)


# Reason: FunctionInvocationContext params are excluded from the
# model-visible tool schema; delegate_id stays invisible to the model.
@tool(approval_mode="never_require")
def get_upcoming_meetings(
    ctx: FunctionInvocationContext,
) -> str:
    """Get upcoming meetings for committees the delegate participates in.

    The delegate identity is injected via FunctionInvocationContext using
    the ``delegate_id`` key from function_invocation_kwargs.

    Args:
        ctx: Runtime context providing delegate_id via kwargs injection.

    Returns:
        JSON array of meetings with keys: id, title, committee_id,
        meeting_date. Returns empty array when no delegate or no meetings.
    """
    delegate_id = ctx.kwargs.get("delegate_id", "")
    if not delegate_id:
        return json.dumps([])

    now = datetime.now(UTC).replace(tzinfo=None)
    # Reason: strip tzinfo for SQLite naive-datetime comparison
    with _Session(_engine) as session:
        subq = select(delegate_committees.c.committee_id).where(
            delegate_committees.c.delegate_id == delegate_id
        )
        stmt = (
            select(Meeting)
            .where(Meeting.committee_id.in_(subq))
            .where(Meeting.date >= now)
            .order_by(Meeting.date)
        )
        meetings = session.scalars(stmt).all()
        return json.dumps(
            [
                {
                    "id": m.id,
                    "title": m.title,
                    "committee_id": m.committee_id,
                    "meeting_date": m.date.isoformat(),
                }
                for m in meetings
            ]
        )


@tool(approval_mode="never_require")
def get_agenda_documents(
    meeting_id: Annotated[
        str,
        Field(description="Meeting ID (e.g. 'MTG-EDU-2026-04')"),
    ],
    ctx: FunctionInvocationContext,
) -> str:
    """Get agenda documents for a meeting visible to the delegate.

    Visibility is enforced by the business layer via DAR classification
    checks. The delegate identity is injected via FunctionInvocationContext.

    Args:
        meeting_id: The meeting identifier whose agenda to query.
        ctx: Runtime context providing delegate_id via kwargs injection.

    Returns:
        JSON array of visible documents with keys: id, title,
        classification, last_modified. Returns empty array when no
        delegate_id is present in context.
    """
    delegate_id = ctx.kwargs.get("delegate_id", "")
    if not delegate_id:
        return json.dumps([])
    with _Session(_engine) as session:
        documents = get_visible_agenda_documents(
            delegate_id, meeting_id, session
        )
        return json.dumps(
            [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "classification": doc.classification.value,
                    "last_modified": doc.last_modified.isoformat(),
                }
                for doc in documents
            ]
        )


def _assert_editor(
    ctx: FunctionInvocationContext, session: _Session
) -> Delegate:
    """Verify the current delegate holds the DELEGATION_EDITOR role.

    Args:
        ctx: Runtime context providing delegate_id via kwargs injection.
        session: Active SQLAlchemy session.

    Returns:
        The loaded Delegate ORM object for the current session.

    Raises:
        PermissionError: If no delegate_id is present in context or if the
            delegate's role is not DELEGATION_EDITOR.
    """
    delegate_id = ctx.kwargs.get("delegate_id", "")
    if not delegate_id:
        raise PermissionError(
            "Only delegation editors can create delegates/DARs"
        )
    delegate = session.get(Delegate, delegate_id)
    if delegate is None or delegate.role != DelegateRole.DELEGATION_EDITOR:
        raise PermissionError(
            "Only delegation editors can create delegates/DARs"
        )
    return delegate


# Reason: approval_mode="always_require" enforces HITL confirmation for all
# write operations that mutate the database.
@tool(approval_mode="always_require")
def create_delegate(
    full_name: Annotated[
        str, Field(description="Full name of the new delegate")
    ],
    email: Annotated[
        str, Field(description="Email address of the new delegate")
    ],
    function: Annotated[
        str,
        Field(description="Function or job title of the new delegate"),
    ],
    delegation_id: Annotated[
        str,
        Field(
            description="Delegation ID the delegate belongs to (e.g. 'FRA')"
        ),
    ],
    role: Annotated[
        str,
        Field(
            description=(
                "Role for the new delegate: 'DELEGATE' or 'DELEGATION_EDITOR'. "
                "Defaults to 'DELEGATE'."
            ),
            default="DELEGATE",
        ),
    ] = "DELEGATE",
    ctx: FunctionInvocationContext = None,
) -> str:
    """Create a new delegate within a delegation.

    Requires the calling session delegate to hold the DELEGATION_EDITOR role.
    Generates the next sequential DEL-YYYY-NNNN ID automatically and sets
    accreditation_date to the current UTC timestamp.

    Args:
        full_name: Full name of the delegate to create.
        email: Email address for the new delegate.
        function: Function or job title (required by schema).
        delegation_id: Parent delegation identifier.
        role: DelegateRole value string; defaults to ``"DELEGATE"``.
        ctx: Runtime context providing delegate_id via kwargs injection.

    Returns:
        JSON string with keys: id, full_name, delegation_id, role on success.
        JSON error structure ``{"error": ..., "delegation_id": ...}`` when the
        target delegation does not exist or the role value is invalid.

    Raises:
        PermissionError: If the calling delegate is not a DELEGATION_EDITOR.
    """
    with _Session(_engine) as session:
        _assert_editor(ctx, session)

        delegation = session.get(Delegation, delegation_id)
        if delegation is None:
            return json.dumps(
                {
                    "error": f"Delegation '{delegation_id}' not found",
                    "delegation_id": delegation_id,
                }
            )

        try:
            delegate_role = DelegateRole(role)
        except ValueError:
            return json.dumps(
                {
                    "error": (
                        f"Invalid role '{role}'. "
                        f"Must be one of: {[r.value for r in DelegateRole]}"
                    ),
                    "delegation_id": delegation_id,
                }
            )

        new_id = _next_delegate_id(session)
        # Reason: strip tzinfo to match SQLite naive-datetime convention used
        # throughout the codebase (mirrors get_upcoming_meetings pattern).
        now = datetime.now(UTC).replace(tzinfo=None)
        new_delegate = Delegate(
            id=new_id,
            full_name=full_name,
            email=email,
            function=function,
            delegation_id=delegation_id,
            accreditation_date=now,
            role=delegate_role,
        )
        session.add(new_delegate)
        session.commit()

        return json.dumps(
            {
                "id": new_id,
                "full_name": full_name,
                "delegation_id": delegation_id,
                "role": delegate_role.value,
            }
        )


ALL_TOOLS: list[object] = [
    get_delegation_info,
    lookup_delegate,
    whoami,
    get_upcoming_meetings,
    get_agenda_documents,
]
