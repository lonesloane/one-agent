"""Pytest fixtures for the pytest-playwright E2E test suite."""
import threading

import pytest
from sqlalchemy.orm import Session
from werkzeug.serving import make_server

from shared.database import Base, get_engine, init_db
from shared.seed_data import seed_all
from classical_app.app import create_app


@pytest.fixture(scope="session")
def e2e_db_path(tmp_path_factory):
    """
    Session-scoped temp SQLite file path for the E2E database.

    Returns:
        Absolute path string to the temp .db file.
    """
    tmp = tmp_path_factory.mktemp("e2e_db")
    return str(tmp / "e2e.db")


@pytest.fixture(scope="session")
def e2e_engine(e2e_db_path):
    """
    Session-scoped SQLAlchemy engine on the E2E temp database.

    Initialises the schema and seeds demo data once. The engine is
    disposed at session teardown.

    Args:
        e2e_db_path: Path to the temp SQLite file.

    Yields:
        Configured Engine instance.
    """
    engine = get_engine(e2e_db_path)
    init_db(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def e2e_app(e2e_db_path):
    """
    Session-scoped Flask application pointing at the E2E temp database.

    Args:
        e2e_db_path: Path to the temp SQLite file.

    Returns:
        Configured Flask application instance.
    """
    app = create_app(db_url=f"sqlite:///{e2e_db_path}")
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="session")
def live_server(e2e_app):
    """
    Session-scoped Werkzeug live server running in a daemon thread.

    Uses threaded=True so that concurrent asset requests from Playwright
    do not serialise and stall behind each other.

    Args:
        e2e_app: The Flask application to serve.

    Yields:
        Base URL string, e.g. "http://127.0.0.1:5001".
    """
    server = make_server("127.0.0.1", 5001, e2e_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield "http://127.0.0.1:5001"
    server.shutdown()


@pytest.fixture(scope="session")
def base_url(live_server):
    """
    Return the live-server base URL.

    Args:
        live_server: Running server URL from the live_server fixture.

    Returns:
        Base URL string.
    """
    return live_server


@pytest.fixture(autouse=True)
def reset_db(e2e_app, e2e_engine):
    """
    Function-scoped autouse fixture that resets the database to a clean
    seeded state before every test.

    Releases the app's scoped session first to avoid SQLite write-lock
    conflicts when dropping tables.

    Args:
        e2e_app: Flask app whose scoped session must be released.
        e2e_engine: Engine used to drop/recreate schema.
    """
    e2e_app.extensions["db_session"].remove()
    Base.metadata.drop_all(e2e_engine)
    init_db(e2e_engine)
    with Session(e2e_engine) as session:
        seed_all(session)
        session.commit()


@pytest.fixture
def login_as(base_url):
    """
    Factory fixture that logs a delegate in via the real /switch-delegate.

    Usage::

        def test_something(page, login_as):
            login_as(page, "DEL-2026-0001")

    Args:
        base_url: Live-server base URL.

    Returns:
        Callable accepting (page, delegate_id: str).
    """
    def _login(page, delegate_id: str) -> None:
        page.goto(f"{base_url}/switch-delegate")
        page.click(f"button[value='{delegate_id}']")
        page.wait_for_load_state("networkidle")
        assert "/switch-delegate" not in page.url, (
            f"Login failed for {delegate_id}; still on {page.url}"
        )

    return _login
