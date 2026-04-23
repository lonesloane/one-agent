"""Pytest fixtures for the CopilotKit E2E browser test suite.

Session-scoped fixtures start a test SQLite database with a fresh document,
a FastAPI subprocess on a free port, and a Next.js subprocess on port 3000.
"""

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, UTC
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Reason: pytest does not auto-load .env; without this, FOUNDRY_PROJECT_ENDPOINT
# is absent from os.environ and missing from the uvicorn subprocess env.
load_dotenv(Path(__file__).parent.parent.parent / "agent_app" / ".env")

from shared.database import (
    ClassificationLevel,
    Document,
    MeetingAgendaItem,
    get_engine,
    init_db,
)
from shared.seed_data import seed_all


def _evict_nextjs_server(frontend_dir: Path) -> None:
    """Kill any stale Next.js dev server registered for frontend_dir.

    Next.js 16 Turbopack writes a JSON lockfile at
    ``<distDir>/lock`` containing the PID of the running dev server.
    A stale entry from a prior aborted test run prevents new instances
    from starting (even on a different port).  This helper kills the
    registered PID and removes the lockfile so the next ``next dev``
    invocation can acquire the lock cleanly.

    Args:
        frontend_dir: Absolute path to the Next.js project root.
    """
    lock_path = frontend_dir / ".next" / "dev" / "lock"
    if lock_path.exists():
        try:
            info = json.loads(lock_path.read_text())
            stale_pid = info.get("pid")
            if stale_pid:
                os.kill(stale_pid, signal.SIGKILL)
                time.sleep(0.3)
        except (
            json.JSONDecodeError,
            KeyError,
            ProcessLookupError,
            PermissionError,
            OSError,
        ):
            pass
        try:
            lock_path.unlink()
        except OSError:
            pass


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
def fastapi_port() -> int:
    """Return a free TCP port for the test FastAPI server.

    Binds to port 0 to let the OS pick an available port, then releases
    the socket so uvicorn can bind to it.

    Returns:
        Free port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def fastapi_server(
    agent_db_path: str,
    agent_engine,
    fastapi_port: int,
    nextjs_port: int,
    tmp_path_factory,
):
    """
    Session-scoped fixture that starts the FastAPI server on a free port.

    Starts uvicorn with DATABASE_PATH pointing at the E2E database, polls
    GET /api/delegates until HTTP 200 is returned (up to 20 seconds),
    then yields.  The process is terminated on teardown.

    Args:
        agent_db_path: Absolute path to the temp SQLite file passed as
            DATABASE_PATH env var to the subprocess.
        agent_engine: Ensures the database is seeded before the server
            starts.
        fastapi_port: Free port allocated for this session.
        nextjs_port: Next.js port added to CORS_ORIGINS so the browser
            can fetch /api/delegates across origins.
        tmp_path_factory: Used to create a log file for server output.

    Yields:
        None

    Raises:
        RuntimeError: If the server does not become ready within 20 seconds.
    """
    log_path = tmp_path_factory.mktemp("logs") / "fastapi.log"
    log_file = open(log_path, "w")
    print(f"\n[e2e] FastAPI log: {log_path}", file=sys.stdout)

    process = subprocess.Popen(
        [
            "uvicorn",
            "agent_app.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(fastapi_port),
        ],
        env={
            **os.environ,
            "DATABASE_PATH": agent_db_path,
            "CORS_ORIGINS": f"http://localhost:{nextjs_port}",
        },
        stdout=log_file,
        stderr=log_file,
    )

    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{fastapi_port}/api/delegates"
                ) as resp:
                    if resp.status == 200:
                        break
            except urllib.error.URLError:
                time.sleep(0.5)

        else:
            process.terminate()
            raise RuntimeError(
                "FastAPI server did not start within 20 seconds"
            )

        yield

    finally:
        process.terminate()
        process.wait()
        log_file.close()


@pytest.fixture(scope="session")
def nextjs_port() -> int:
    """Return a free TCP port for the test Next.js server.

    Returns:
        Free port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def nextjs_server(
    fastapi_server, fastapi_port: int, nextjs_port: int, tmp_path_factory
):
    """
    Session-scoped fixture that installs deps and starts the Next.js server.

    Runs `npm install` if node_modules is absent, then starts the dev server
    on nextjs_port.  Depends on fastapi_server to ensure the FastAPI backend
    is running first.  Launches npm in a new process group so all child Node
    processes are terminated on teardown.  Polls until an HTTP response is
    received (up to 120 seconds — Next.js cold starts after npm install
    are slow).

    Args:
        fastapi_server: Ensures the FastAPI server is running first.
        fastapi_port: Port the FastAPI server is listening on, passed as
            AGENT_URL so route.ts proxies to the right backend.
        nextjs_port: Free port allocated for the Next.js server.
        tmp_path_factory: Used to create a log file for server output.

    Yields:
        None

    Raises:
        RuntimeError: If npm install fails or the server does not become
            ready within 120 seconds.
    """
    frontend_dir = (
        Path(__file__).parent.parent.parent / "agent_app" / "frontend"
    )

    if not (frontend_dir / "node_modules").exists():
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"npm install failed:\n{result.stderr}")

    # Reason: Next.js 16 Turbopack locks per-project; stale registrations
    # block new instances even on a different port.
    _evict_nextjs_server(frontend_dir)

    log_path = tmp_path_factory.mktemp("logs") / "nextjs.log"
    log_file = open(log_path, "w")
    print(f"\n[e2e] Next.js log: {log_path}", file=sys.stdout)

    process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_dir),
        env={
            **os.environ,
            "PORT": str(nextjs_port),
            "AGENT_URL": f"http://127.0.0.1:{fastapi_port}/",
            "NEXT_PUBLIC_AGENT_URL": f"http://127.0.0.1:{fastapi_port}",
        },
        start_new_session=True,
        stdout=log_file,
        stderr=log_file,
    )

    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://localhost:{nextjs_port}")
                break
            except urllib.error.HTTPError:
                # Reason: HTTPError means server responded — it is up.
                break
            except (
                urllib.error.URLError,
                http.client.RemoteDisconnected,
                ConnectionResetError,
            ):
                # Reason: Next.js accepts TCP connections but closes them
                # without a response during initial compilation. Keep polling.
                time.sleep(0.5)

        else:
            raise RuntimeError(
                "Next.js server did not start within 120 seconds"
            )

        yield

    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        log_file.close()
        _evict_nextjs_server(frontend_dir)


@pytest.fixture(autouse=True)
def _dump_on_failure(request, page):
    """Dump page HTML + visible text + console + SSE on test failure.

    Installs console and response listeners at test start so we can
    distinguish LLM response variance (brief rendered but didn't name
    the doc) from rendering failures (chat empty, stream truncated) or
    session carryover (re-used state).
    """
    console_lines: list[str] = []
    sse_bodies: list[str] = []

    def on_console(msg) -> None:
        console_lines.append(f"{msg.type}: {msg.text}")

    def on_response(resp) -> None:
        if "/api/copilotkit/" in resp.url and "/run" in resp.url:
            try:
                sse_bodies.append(
                    f"=== {resp.url} ({resp.status}) ===\n{resp.text()}"
                )
            except Exception as read_err:  # noqa: BLE001
                sse_bodies.append(
                    f"=== {resp.url} READ FAILED: {read_err} ==="
                )

    page.on("console", on_console)
    page.on("response", on_response)

    yield

    rep = getattr(request.node, "rep_call", None)
    if rep is None or not rep.failed:
        return
    safe = request.node.nodeid.replace("/", "_").replace("::", "__")
    try:
        Path(f"/tmp/failure_{safe}.html").write_text(page.content())
        Path(f"/tmp/failure_{safe}.txt").write_text(
            page.locator("body").inner_text()
        )
        Path(f"/tmp/failure_{safe}_console.txt").write_text(
            "\n".join(console_lines)
        )
        Path(f"/tmp/failure_{safe}_sse.txt").write_text(
            "\n\n".join(sse_bodies)
        )
        print(f"\n[e2e] dumped failure artifacts to /tmp/failure_{safe}.*")
    except Exception as dump_err:  # noqa: BLE001
        print(f"\n[e2e] dump failed: {dump_err}")


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Attach test call outcome to item so _dump_on_failure can inspect it."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture(scope="session")
def base_url(nextjs_server, nextjs_port: int) -> str:
    """Return the Next.js dev server base URL.

    Args:
        nextjs_server: Ensures the Next.js server is running.
        nextjs_port: Port the Next.js server is listening on.

    Returns:
        Base URL string for the Next.js dev server.
    """
    return f"http://localhost:{nextjs_port}"
