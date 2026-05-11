"""Pytest fixtures for agent_app tests."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from shared.database import get_engine, init_db
from shared.seed_data import seed_all


@pytest.fixture
def seeded_agent_db(tmp_path, monkeypatch):
    """Create a temp seeded SQLite DB and point ONE_AGENT_DB_PATH at it.

    Resets the agent_app.session singleton so db_session() picks up the
    temp path instead of the cached production engine.

    Args:
        tmp_path: pytest-provided temporary directory.
        monkeypatch: pytest monkeypatch fixture.

    Yields:
        Path string to the seeded temp DB file.
    """
    db_path = str(tmp_path / "test_agent.db")
    engine = get_engine(db_path)
    init_db(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
    engine.dispose()

    # Override env var so db_session() reads this path on first call.
    monkeypatch.setenv("ONE_AGENT_DB_PATH", db_path)

    # Reset the module-level singleton so a fresh engine is created
    # against the temp DB rather than whatever was cached previously.
    import agent_app.session as agent_session

    original_engine = agent_session._engine
    original_session_factory = agent_session._Session
    agent_session._engine = None
    agent_session._Session = None

    yield db_path

    # Restore singleton state after the test.
    agent_session._engine = original_engine
    agent_session._Session = original_session_factory
