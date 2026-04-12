"""Shared pytest fixtures for shared data layer tests."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.database import Base, init_db


@pytest.fixture
def engine():
    """In-memory SQLite engine with schema created."""
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    """SQLAlchemy session bound to in-memory engine."""
    with Session(engine) as sess:
        yield sess
