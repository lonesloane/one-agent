"""
Session state helpers for the 4-step delegate-creation wizard.

State lives in ``flask.session`` under a nested dict keyed by
``SESSION_KEY`` and then by ``delegation_id``.  Multiple delegations
can have simultaneous in-progress wizard sessions without interfering
with each other.

Example session layout::

    session['delegate_wizard']['FRA'] = {
        'step1': {...},
        'step2': {...},
        'updated_at': '2026-04-19T10:30:00+00:00',
    }
"""

from datetime import datetime, timezone, timedelta
from typing import Any

from flask import session, redirect, url_for
from loguru import logger

SESSION_KEY = "delegate_wizard"
TTL_MINUTES = 30


def load(delegation_id: str) -> dict | None:
    """Return the wizard state dict for a delegation, or None.

    Args:
        delegation_id: Delegation identifier used as the dict key.

    Returns:
        The wizard state dict, or None if no state is stored.
    """
    outer = session.get(SESSION_KEY)
    if not outer:
        return None
    return outer.get(delegation_id)


def save(delegation_id: str, step_key: str, data: dict) -> None:
    """Persist step data for a delegation's wizard session.

    Creates the outer session dict if it does not yet exist.  Updates
    ``updated_at`` to the current UTC time and marks the session
    modified so Flask serialises the change.

    Args:
        delegation_id: Delegation identifier used as the dict key.
        step_key: Wizard step key, e.g. ``'step1'``.
        data: Form data to store under the step key.
    """
    if SESSION_KEY not in session:
        session[SESSION_KEY] = {}

    wizard = session[SESSION_KEY].setdefault(delegation_id, {})
    wizard[step_key] = data
    wizard["updated_at"] = datetime.now(timezone.utc).isoformat()

    session.modified = True
    logger.debug(
        "Wizard state saved: delegation={} step={}",
        delegation_id,
        step_key,
    )


def clear(delegation_id: str) -> None:
    """Remove wizard state for a delegation.

    If the outer dict becomes empty after removal it is deleted too.
    Does NOT touch ``created_delegate_id`` entries stored separately.

    Args:
        delegation_id: Delegation identifier to remove.
    """
    outer = session.get(SESSION_KEY)
    if not outer:
        return

    outer.pop(delegation_id, None)

    if not outer:
        del session[SESSION_KEY]

    session.modified = True
    logger.debug("Wizard state cleared: delegation={}", delegation_id)


def is_stale(delegation_id: str) -> bool:
    """Return True if the wizard state is missing or has expired.

    A state is considered stale when it is absent OR when its
    ``updated_at`` timestamp is more than ``TTL_MINUTES`` minutes in
    the past.  Naive datetimes stored without timezone info are
    treated as UTC.

    Args:
        delegation_id: Delegation identifier to inspect.

    Returns:
        True if the state is missing or expired, False otherwise.
    """
    state = load(delegation_id)
    if state is None:
        return True

    raw = state.get("updated_at")
    if not raw:
        # Reason: a state dict without updated_at is treated as stale.
        logger.warning(
            "Wizard state missing updated_at: delegation={}",
            delegation_id,
        )
        return True

    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        logger.warning(
            "Unparseable updated_at '{}': delegation={}",
            raw,
            delegation_id,
        )
        return True

    # Reason: naive datetimes are assumed to be UTC for safe comparison.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    age = datetime.now(timezone.utc) - dt
    return age > timedelta(minutes=TTL_MINUTES)


def require_steps(
    delegation_id: str, step_keys: tuple[str, ...]
) -> Any | None:
    """Guard wizard routes by verifying required steps are present.

    Checks that the wizard state exists, is not stale, and contains
    all requested step keys.  On failure the state is cleared and a
    redirect to step 1 is returned.

    Usage in a route handler::

        redirect_response = require_steps(delegation_id, ('step1',))
        if redirect_response:
            return redirect_response

    Args:
        delegation_id: Delegation identifier to check.
        step_keys: Tuple of step keys that must be present.

    Returns:
        A Flask redirect response if the check fails, else None.
    """
    if is_stale(delegation_id):
        logger.info(
            "Wizard state stale or missing; redirecting to step1:"
            " delegation={}",
            delegation_id,
        )
        clear(delegation_id)
        return redirect(
            url_for("wizard.wizard_step1", delegation_id=delegation_id)
        )

    state = load(delegation_id)
    if state is None:
        clear(delegation_id)
        return redirect(
            url_for(
                "wizard.wizard_step1", delegation_id=delegation_id
            )
        )

    missing = [k for k in step_keys if k not in state]
    if missing:
        logger.info(
            "Wizard state missing steps {}; redirecting to step1:"
            " delegation={}",
            missing,
            delegation_id,
        )
        clear(delegation_id)
        return redirect(
            url_for("wizard.wizard_step1", delegation_id=delegation_id)
        )

    return None


def get_created_delegate_id(delegation_id: str) -> str | None:
    """Read the newly created delegate ID for a delegation.

    Args:
        delegation_id: Delegation identifier used as the dict key.

    Returns:
        The stored delegate ID string, or None if not set.
    """
    return session.get("created_delegate_id", {}).get(delegation_id)


def set_created_delegate_id(
    delegation_id: str, delegate_id: str
) -> None:
    """Store the newly created delegate ID for a delegation.

    Creates the outer ``created_delegate_id`` dict if it does not
    yet exist and marks the session modified.

    Args:
        delegation_id: Delegation identifier used as the dict key.
        delegate_id: The ID of the just-created delegate record.
    """
    if "created_delegate_id" not in session:
        session["created_delegate_id"] = {}

    session["created_delegate_id"][delegation_id] = delegate_id
    session.modified = True
    logger.debug(
        "created_delegate_id set: delegation={} delegate={}",
        delegation_id,
        delegate_id,
    )
