"""Pytest fixtures for classical_app Flask tests."""
import os
import tempfile

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.database import (
    Delegate,
    get_engine,
    init_db,
)
from shared.seed_data import seed_all
from classical_app.app import create_app


@pytest.fixture
def temp_db():
    """
    Create a temporary SQLite database file.

    Yields the path to the temp database file. The file is cleaned up
    after the test.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def seeded_engine(temp_db):
    """
    Create engine on temp DB, initialize schema, and seed with demo data.

    Yields the engine. It is disposed after the test.
    """
    engine = get_engine(temp_db)
    init_db(engine)

    with Session(engine) as session:
        seed_all(session)
        session.commit()

    yield engine

    engine.dispose()


@pytest.fixture
def client(seeded_engine):
    """
    Create Flask test client with TESTING config.

    The app is created with the same temp DB as the seeded_engine,
    so all seed data is available. Session is removed after each request.
    """
    # Get the DB path from the engine URL (sqlite:///path -> path)
    db_url = str(seeded_engine.url)
    db_path = db_url.removeprefix("sqlite:///")

    app = create_app(f"sqlite:///{db_path}")
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def member_delegate_id(seeded_engine) -> str:
    """
    Get a member delegation's delegate ID.

    Returns the ID of a delegate from FRA delegation (MEMBER type).
    This is DEL-2026-0001 (Marie Dupont, Head of Delegation).
    """
    with Session(seeded_engine) as session:
        stmt = select(Delegate).where(Delegate.id == "DEL-2026-0001")
        delegate = session.scalars(stmt).first()
        assert delegate is not None
        return delegate.id


@pytest.fixture
def partner_delegate_id(seeded_engine) -> str:
    """
    Get a partner delegation's delegate ID.

    Returns the ID of a delegate from BRA delegation (PARTNER type).
    This is DEL-2026-0005 (Carlos Silva, Head of Delegation).
    """
    with Session(seeded_engine) as session:
        stmt = select(Delegate).where(Delegate.id == "DEL-2026-0005")
        delegate = session.scalars(stmt).first()
        assert delegate is not None
        return delegate.id
