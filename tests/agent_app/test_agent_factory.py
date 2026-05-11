"""Tests for agent_app.agent.build_agent factory."""

from __future__ import annotations

import os
from unittest.mock import MagicMock


def test_build_agent_assembles_one_tool(monkeypatch) -> None:
    """build_agent wires exactly one closure-bound tool visible to the model.

    Asserts:
    - Agent name is "OneMPAgent".
    - Exactly one tool is registered in default_options["tools"].
    - That tool's name as seen by the model is "get_current_delegate_summary".
    """
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT", "https://test.example/foundry"
    )
    # Import after env-var is set so _get_endpoint() does not raise at
    # module import time.
    from agent_app.agent import build_agent  # noqa: PLC0415

    agent = build_agent(
        credential=MagicMock(),
        delegate_id="DEL-2026-0001",
        model="test",
    )

    assert agent.name == "OneMPAgent"

    tools = agent.default_options["tools"]
    assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}: {tools}"
    assert tools[0].name == "get_current_delegate_summary", (
        f"Unexpected tool name: {tools[0].name!r}"
    )
