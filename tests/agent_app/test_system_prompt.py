"""Regression tests for agent_app/agent.py::SYSTEM_PROMPT."""

import pytest

from agent_app.agent import SYSTEM_PROMPT


class TestSystemPromptStructure:
    """Tests for required sections in the system prompt."""

    def test_contains_persona_mode_selection_section(self) -> None:
        """SYSTEM_PROMPT contains Persona Mode Selection section."""
        assert "Persona Mode Selection" in SYSTEM_PROMPT

    def test_contains_create_side_section(self) -> None:
        """SYSTEM_PROMPT contains Create Side section."""
        assert "Create Side" in SYSTEM_PROMPT

    def test_contains_hitl_write_guard_section(self) -> None:
        """SYSTEM_PROMPT contains HITL Write Guard section."""
        assert "HITL Write Guard" in SYSTEM_PROMPT

    def test_contains_pending_delegation_head_routing(self) -> None:
        """SYSTEM_PROMPT references PENDING_DELEGATION_HEAD approval tier."""
        assert "PENDING_DELEGATION_HEAD" in SYSTEM_PROMPT

    def test_contains_pending_secretariat_routing(self) -> None:
        """SYSTEM_PROMPT references PENDING_SECRETARIAT approval tier."""
        assert "PENDING_SECRETARIAT" in SYSTEM_PROMPT

    def test_branches_each_seeded_role(self) -> None:
        """Selection algorithm must name DELEGATE and DELEGATION_EDITOR explicitly."""
        assert "role is DELEGATE" in SYSTEM_PROMPT
        assert "role is DELEGATION_EDITOR" in SYSTEM_PROMPT

    def test_prompt_length_under_300_lines(self) -> None:
        """SYSTEM_PROMPT is under 300 lines (GUD-001)."""
        line_count = len(SYSTEM_PROMPT.splitlines())
        assert line_count < 300, (
            f"SYSTEM_PROMPT has {line_count} lines; max 300 allowed (GUD-001)"
        )
