"""Tests for agent_app.agent.build_agent factory."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def agent(monkeypatch):
    """Build a test Agent with a mock credential and fake endpoint.

    Sets FOUNDRY_PROJECT_ENDPOINT before importing build_agent so
    _get_endpoint() does not raise. Uses a MagicMock credential to
    avoid any live Azure HTTP calls.

    Yields:
        A fully-constructed Agent instance.
    """
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT", "https://test.example/foundry"
    )
    # Import after env-var is set so load_dotenv() in agent.py does not
    # override the monkeypatched value with an absent .env entry.
    from agent_app.agent import build_agent  # noqa: PLC0415

    return build_agent(
        credential=MagicMock(),
        delegate_id="DEL-2026-0001",
        model="test",
    )


def test_build_agent_assembles_one_tool(agent) -> None:
    """build_agent wires exactly one closure-bound tool visible to the model.

    Asserts:
    - Exactly one tool is registered in default_options["tools"].
    - That tool's name as seen by the model is "get_current_delegate_summary".
    """
    tools = agent.default_options["tools"]
    assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}: {tools}"
    assert tools[0].name == "get_current_delegate_summary", (
        f"Unexpected tool name: {tools[0].name!r}"
    )


def test_build_agent_sets_agent_name(agent) -> None:
    """build_agent sets agent.name to 'OneMPAgent'."""
    assert agent.name == "OneMPAgent"


def test_build_agent_sets_instructions(agent) -> None:
    """build_agent sets a non-empty instructions string for the agent.

    Instructions are exposed via agent.default_options["instructions"].
    Asserts the string contains the opening phrase that identifies the
    agent's purpose. Full placeholder:
    "You assist a delegate. Tools added in subsequent phases."
    """
    instructions = agent.default_options.get("instructions", "")
    assert instructions, "agent instructions must not be empty"
    assert "You assist a delegate" in instructions
