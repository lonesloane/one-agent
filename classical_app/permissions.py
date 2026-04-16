"""
Permission helpers for the classical Flask application.

Provides is_editor_of() for direct checks and the
editor_of_delegation_required decorator factory for route protection.
"""

import functools
from typing import Callable, Any

from flask import session, abort, current_app
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import scoped_session

from shared.database import Delegate, DelegateRole


def is_editor_of(
    db_session: scoped_session,
    delegate_id: str,
    delegation_id: str,
) -> bool:
    """
    Check if a delegate has editor rights over a delegation.

    Args:
        db_session: Active SQLAlchemy scoped session
        delegate_id: Identifier of the delegate to check
        delegation_id: Identifier of the delegation to check against

    Returns:
        True if the delegate has the DELEGATION_EDITOR role and belongs
        to the specified delegation; False otherwise.
    """
    stmt = select(Delegate).where(Delegate.id == delegate_id)
    delegate = db_session.scalars(stmt).first()

    if delegate is None:
        logger.debug(
            "is_editor_of: delegate {} not found", delegate_id
        )
        return False

    if delegate.role != DelegateRole.DELEGATION_EDITOR:
        logger.debug(
            "is_editor_of: delegate {} role is {}, not DELEGATION_EDITOR",
            delegate_id,
            delegate.role,
        )
        return False

    if delegate.delegation_id != delegation_id:
        logger.debug(
            "is_editor_of: delegate {} belongs to {}, not {}",
            delegate_id,
            delegate.delegation_id,
            delegation_id,
        )
        return False

    return True


def editor_of_delegation_required(
    delegation_id_arg: str = "delegation_id",
) -> Callable:
    """
    Decorator factory that enforces delegation editor access on a route.

    Reads ``session['delegate_id']`` and the delegation identifier from
    the route keyword arguments under the key named by
    ``delegation_id_arg``.  Aborts with HTTP 403 if the current delegate
    is not an editor of the target delegation.

    Args:
        delegation_id_arg: Name of the URL keyword argument that holds
            the delegation identifier. Defaults to ``"delegation_id"``.

    Returns:
        A decorator that wraps a Flask route function with the permission
        check.

    Example:
        @delegations_bp.route(
            "/delegations/<delegation_id>/edit", methods=["GET"]
        )
        @editor_of_delegation_required()
        def edit_delegation(delegation_id: str) -> str:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delegate_id = session.get("delegate_id")
            delegation_id = kwargs.get(delegation_id_arg)

            if not delegate_id or not delegation_id:
                logger.warning(
                    "editor_of_delegation_required: missing "
                    "delegate_id={} or delegation_id={}",
                    delegate_id,
                    delegation_id,
                )
                abort(403)

            db = current_app.extensions["db_session"]
            if not is_editor_of(db, delegate_id, delegation_id):
                logger.warning(
                    "editor_of_delegation_required: delegate {} "
                    "denied access to delegation {}",
                    delegate_id,
                    delegation_id,
                )
                abort(403)

            return fn(*args, **kwargs)

        return wrapper

    return decorator
