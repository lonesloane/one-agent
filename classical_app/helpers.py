"""
Classical app helper functions.

Shared utilities for database access and datetime handling.
"""

from datetime import datetime, timezone

from flask import session
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import scoped_session

from shared.database import Delegate


def get_current_delegate(db_session: scoped_session) -> Delegate:
    """
    Retrieve the currently logged-in delegate from the database.

    Args:
        db_session: SQLAlchemy scoped session

    Returns:
        The Delegate object for the current session

    Raises:
        RuntimeError: If delegate_id is not in session or delegate
            not found in database
    """
    delegate_id = session.get("delegate_id")
    if not delegate_id:
        raise RuntimeError("No delegate_id in session")

    stmt = select(Delegate).where(Delegate.id == delegate_id)
    delegate = db_session.scalars(stmt).first()
    if not delegate:
        logger.error("Delegate not found: {}", delegate_id)
        raise RuntimeError(f"Delegate not found: {delegate_id}")

    return delegate


def get_now_utc() -> datetime:
    """
    Get current UTC time as naive datetime for database comparison.

    Returns:
        Naive datetime in UTC
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
