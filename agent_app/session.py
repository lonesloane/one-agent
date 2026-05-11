"""DB session helper for agent_app tools.

Mirrors classical_app's get_engine + sessionmaker pattern so both apps
share one database file (one_agent.db) and one connection lifecycle
shape.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from shared.database import get_engine

# Two parent() steps up from agent_app/session.py lands at project root.
# Override via ONE_AGENT_DB_PATH env var when running from a worktree.
_DEFAULT_DB = str(Path(__file__).resolve().parent.parent / "one_agent.db")

# Reason: lazy, single engine reused across tool invocations.
_engine = None
_Session: sessionmaker | None = None


def _get_session_factory() -> sessionmaker:
    """Return the module-level sessionmaker, creating it on first call.

    Returns:
        A configured sessionmaker bound to the project SQLite database.
    """
    global _engine, _Session
    if _Session is None:
        db_path = os.environ.get("ONE_AGENT_DB_PATH", _DEFAULT_DB)
        _engine = get_engine(db_path)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _Session


@contextmanager
def db_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session; commits on success, rolls back on error.

    Yields:
        An active SQLAlchemy Session bound to the project database.

    Raises:
        Exception: Re-raises any exception after rolling back the session.
    """
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
