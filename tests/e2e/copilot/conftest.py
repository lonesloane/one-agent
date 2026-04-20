"""Pytest fixtures for the CopilotKit E2E browser test suite.

Session-scoped fixtures start a test SQLite database with a fresh document,
a FastAPI subprocess on port 8000, and a Next.js subprocess on port 3000.
"""

import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, UTC
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from shared.database import (
    ClassificationLevel,
    Document,
    MeetingAgendaItem,
    get_engine,
    init_db,
)
from shared.seed_data import seed_all


@pytest.fixture(scope="session")
def agent_db_path(tmp_path_factory) -> str:
    """
    Session-scoped temp SQLite file path for the copilot E2E database.

    Creates a temp directory named "copilot_e2e" and returns the
    absolute path to the "agent_e2e.db" file inside it.

    Args:
        tmp_path_factory: pytest built-in factory for session-scoped
            temp directories.

    Returns:
        Absolute path string to the temp .db file.
    """
    tmp = tmp_path_factory.mktemp("copilot_e2e")
    return str(tmp / "agent_e2e.db")


@pytest.fixture(scope="session")
def agent_engine(agent_db_path: str):
    """
    Session-scoped SQLAlchemy engine seeded with demo data and a test doc.

    Initialises the schema, seeds all standard demo data, then adds a
    fresh test document (DOC-TEST-001) as agenda item 6 on meeting
    MTG-EDU-2026-05.  The engine is disposed at session teardown.

    Args:
        agent_db_path: Absolute path to the temp SQLite file.

    Yields:
        Configured Engine instance.
    """
    engine = get_engine(agent_db_path)
    init_db(engine)

    with Session(engine) as session:
        seed_all(session)
        session.commit()

    with Session(engine) as session:
        doc = Document(
            id="DOC-TEST-001",
            title="E2E Test Policy Draft",
            classification=ClassificationLevel.GENERAL,
            committee_id="EDU",
            publication_date=datetime.now(UTC),
            last_modified=datetime.now(UTC),
        )
        item = MeetingAgendaItem(
            meeting_id="MTG-EDU-2026-05",
            document_id="DOC-TEST-001",
            item_order=6,
        )
        session.add(doc)
        session.add(item)
        session.commit()

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def fastapi_server(agent_db_path: str, agent_engine):
    """
    Session-scoped fixture that starts the FastAPI server on port 8000.

    Checks that port 8000 is free before launching, starts uvicorn as a
    subprocess with DATABASE_PATH pointing at the E2E database, polls
    GET /api/delegates until HTTP 200 is returned (up to 20 seconds),
    then yields.  The process is terminated on teardown.

    Args:
        agent_db_path: Absolute path to the temp SQLite file passed as
            DATABASE_PATH env var to the subprocess.
        agent_engine: Ensures the database is seeded before the server
            starts.

    Yields:
        None

    Raises:
        RuntimeError: If port 8000 is already in use, or if the server
            does not become ready within 20 seconds.
    """
    s = socket.socket()
    s.settimeout(1)
    result = s.connect_ex(("127.0.0.1", 8000))
    s.close()
    if result == 0:
        raise RuntimeError(
            "Port 8000 is already in use. "
            "Stop the dev FastAPI server before running e2e tests."
        )

    process = subprocess.Popen(
        [
            "uvicorn",
            "agent_app.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        env={**os.environ, "DATABASE_PATH": agent_db_path},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/api/delegates"
            ) as resp:
                if resp.status == 200:
                    break
        except urllib.error.URLError:
            time.sleep(0.5)

    else:
        process.terminate()
        process.wait()
        raise RuntimeError(
            "FastAPI server did not start within 20 seconds"
        )

    yield

    process.terminate()
    process.wait()


@pytest.fixture(scope="session")
def nextjs_server(fastapi_server):
    """
    Session-scoped fixture that starts the Next.js dev server on port 3000.

    Depends on fastapi_server to ensure the FastAPI backend is running
    before the frontend starts.  Polls GET http://localhost:3000 every
    0.5 seconds for up to 30 seconds.  Any HTTP response (including
    non-200) is treated as "server ready"; only connection-refused
    errors indicate the server is not yet up.

    Args:
        fastapi_server: Ensures the FastAPI server is running first.

    Yields:
        None

    Raises:
        RuntimeError: If the Next.js server does not become ready within
            30 seconds.
    """
    frontend_dir = (
        Path(__file__).parent.parent.parent / "agent_app" / "frontend"
    )
    process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            urllib.request.urlopen("http://localhost:3000")
            break
        except urllib.error.HTTPError:
            # Reason: HTTPError means server responded — it is up.
            break
        except urllib.error.URLError:
            time.sleep(0.5)

    else:
        process.terminate()
        process.wait()
        raise RuntimeError(
            "Next.js server did not start within 30 seconds"
        )

    yield

    process.terminate()
    process.wait()


@pytest.fixture(autouse=True)
def reset_db():
    """No-op override of Flask e2e reset_db to prevent it running here.

    The Flask e2e conftest defines an autouse reset_db that requires
    e2e_app and e2e_engine.  This fixture shadows it for all tests
    under tests/e2e/copilot/ so the Flask fixtures are never invoked.
    """
    yield


@pytest.fixture
def base_url(nextjs_server) -> str:
    """Return the Next.js dev server base URL.

    Args:
        nextjs_server: Ensures the Next.js server is running.

    Returns:
        Base URL string for the Next.js dev server.
    """
    return "http://localhost:3000"
