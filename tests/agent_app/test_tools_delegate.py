"""Tests for agent_app.tools.delegate — closure-bound read-only tool.

All tests call the zero-argument tool function directly (no Chainlit or
agent-framework session required). The seeded_agent_db fixture provides
an isolated temp DB so tests do not depend on the state of one_agent.db.
"""

from __future__ import annotations

from agent_app.tools.delegate import make_get_current_delegate_summary


def test_get_current_delegate_summary_returns_correct_format(
    seeded_agent_db,
) -> None:
    """Tool returns '<full_name> — <delegation_name>' for a known delegate.

    DEL-2026-0001 is Marie Dupont, Head of Delegation for France.
    Expected: "Marie Dupont — France"
    """
    tool = make_get_current_delegate_summary("DEL-2026-0001")
    result = tool()
    assert result == "Marie Dupont — France"


def test_get_current_delegate_summary_isolates_closure(
    seeded_agent_db,
) -> None:
    """Two tools built with different delegate_ids return their own summaries.

    Proves closure-DI isolation: invoking tool_a and tool_b in any order
    never cross-contaminates — each reads only its own delegate from the DB.

    - DEL-2026-0001: Marie Dupont — France
    - DEL-2026-0003: Hans Mueller — Germany
    """
    tool_fra = make_get_current_delegate_summary("DEL-2026-0001")
    tool_deu = make_get_current_delegate_summary("DEL-2026-0003")

    # Invoke both; order is intentionally interleaved to check isolation.
    result_deu = tool_deu()
    result_fra = tool_fra()

    assert result_fra == "Marie Dupont — France"
    assert result_deu == "Hans Mueller — Germany"


def test_get_current_delegate_summary_handles_missing_delegate(
    seeded_agent_db,
) -> None:
    """Tool returns a safe fallback string when delegate_id is not in DB.

    The tool must not raise. The exact return value is
    "Unknown delegate (DEL-NONEXISTENT)" per the current implementation.
    """
    tool = make_get_current_delegate_summary("DEL-NONEXISTENT")
    result = tool()
    assert result == "Unknown delegate (DEL-NONEXISTENT)"
