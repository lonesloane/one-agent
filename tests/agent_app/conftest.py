"""Shared pytest fixtures for agent_app tests."""
import pytest
from sqlalchemy import create_engine

from shared.database import init_db


@pytest.fixture
def engine():
    """In-memory SQLite engine with schema created."""
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    yield eng
    eng.dispose()
