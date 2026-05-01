"""Spike C2 server — MAF agent exposed via AG-UI protocol.

Wraps the shared spike agent with `AgentFrameworkAgent` and mounts an
AG-UI FastAPI endpoint at `/`. Run alongside `client.py` (or any
AG-UI-compatible client) to exercise the in-session HITL contract.

Run: `.venv/bin/python -m spikes.c2_custom_agui.server`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_framework_ag_ui import (  # noqa: E402
    AgentFrameworkAgent,
    add_agent_framework_fastapi_endpoint,
)
from azure.identity import AzureCliCredential  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from spikes._shared.agent import build_agent  # noqa: E402


def build_app() -> FastAPI:
    """Construct the FastAPI app with the AG-UI endpoint mounted."""
    credential = AzureCliCredential()
    agent = build_agent(credential=credential)
    wrapped = AgentFrameworkAgent(
        agent=agent,
        require_confirmation=True,
    )

    app = FastAPI(title="Spike C2 — AG-UI")
    add_agent_framework_fastapi_endpoint(app, wrapped, "/")
    return app


app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8888)
