"""Delegate-scoped read-only tools for the ONE-MP Agent app.

Each factory function uses closure-bound DI (PAT-001) so the model
never sees ``delegate_id`` as a tool argument. The model interacts only
with the zero-argument ``@tool``-decorated callable.
"""

from __future__ import annotations

from agent_framework import tool
from loguru import logger
from sqlalchemy import select

from agent_app.session import db_session
from shared.database import Delegate, Delegation


def make_get_current_delegate_summary(delegate_id: str):
    """Create a read-only tool that returns the delegate's identity line.

    The ``delegate_id`` is captured in the closure; the model never sees
    it as a parameter (SEC-001 / PAT-001).

    Args:
        delegate_id: String ID of the authenticated delegate (e.g.
            ``"DEL-2026-0001"``).

    Returns:
        A ``@tool``-decorated callable with signature ``() -> str``.
    """

    @tool
    def get_current_delegate_summary() -> str:
        """Return a one-line summary of the currently-logged-in delegate.

        Returns:
            A string in the format ``"<full_name> — <delegation_name>"``.
        """
        with db_session() as session:
            stmt = (
                select(Delegate)
                .join(Delegation, Delegate.delegation_id == Delegation.id)
                .where(Delegate.id == delegate_id)
            )
            delegate = session.scalars(stmt).first()
            if delegate is None:
                logger.warning("Delegate not found in DB: {}", delegate_id)
                return f"Unknown delegate ({delegate_id})"
            return f"{delegate.full_name} — {delegate.delegation.name}"

    return get_current_delegate_summary
