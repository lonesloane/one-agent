"""Unit tests for _fix_tool_call_ordering in agent_app.server.

Tests cover BUG-4C-001: CopilotKit v2 sends tool-result messages before the
assistant message that requested them. The helper reorders them so every
assistant message precedes its tool-result messages.
"""

from agent_app.server import _fix_tool_call_ordering


def _make_tool_call(call_id: str, name: str = "f") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": "{}"},
    }


def _make_assistant(call_ids: list[str]) -> dict:
    return {
        "role": "assistant",
        "tool_calls": [_make_tool_call(cid) for cid in call_ids],
    }


def _make_tool_result(call_id: str, content: str = "result") -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _make_user(content: str = "hi") -> dict:
    return {"role": "user", "content": content}


# ---------------------------------------------------------------------------
# Case A — correct order is left unchanged (idempotency)
# ---------------------------------------------------------------------------


def test_correct_order_is_unchanged() -> None:
    """Already-ordered messages are returned verbatim."""
    user = _make_user()
    asst = _make_assistant(["c1"])
    tool = _make_tool_result("c1")

    result = _fix_tool_call_ordering([user, asst, tool])

    assert result == [user, asst, tool]


# ---------------------------------------------------------------------------
# Case B — single misordered pair is fixed
# ---------------------------------------------------------------------------


def test_single_misordered_pair_fixed() -> None:
    """A (tool, assistant) pair is reordered to (assistant, tool)."""
    user = _make_user()
    asst = _make_assistant(["c1"])
    tool = _make_tool_result("c1")

    result = _fix_tool_call_ordering([user, tool, asst])

    assert result == [user, asst, tool]


# ---------------------------------------------------------------------------
# Case C — multiple tools per assistant, already correct
# ---------------------------------------------------------------------------


def test_multiple_tools_per_assistant_correct_order() -> None:
    """Multiple tool results after a single assistant message are left in place."""
    user = _make_user()
    asst = _make_assistant(["c1", "c2"])
    tool1 = _make_tool_result("c1")
    tool2 = _make_tool_result("c2")

    result = _fix_tool_call_ordering([user, asst, tool1, tool2])

    assert result == [user, asst, tool1, tool2]


# ---------------------------------------------------------------------------
# Case D — multiple misordered pairs are both fixed
# ---------------------------------------------------------------------------


def test_multiple_misordered_pairs_fixed() -> None:
    """Two independent misordered pairs are fixed by call-id, not position.

    Input intentionally crosses call-ids: tool(c2) appears before asst(c1),
    so a positional adjacent-swap algorithm produces the wrong result.
    Expected: asst(c2) precedes tool(c2); asst(c1) precedes tool(c1).
    """
    user = _make_user()
    asst1 = _make_assistant(["c1"])
    asst2 = _make_assistant(["c2"])
    tool1 = _make_tool_result("c1")
    tool2 = _make_tool_result("c2")

    # tool(c2) sits before asst(c1); tool(c1) sits before asst(c2)
    result = _fix_tool_call_ordering([user, tool2, asst1, tool1, asst2])

    # asst(c2) must be spliced before tool(c2); asst(c1) is already correct
    assert result == [user, asst2, tool2, asst1, tool1]


# ---------------------------------------------------------------------------
# Case E — orphan tool message (no matching call_id) is preserved, no crash
# ---------------------------------------------------------------------------


def test_orphan_tool_message_preserved() -> None:
    """A tool message whose call_id has no matching assistant is kept as-is."""
    orphan = _make_tool_result("unknown", content="orphan")

    result = _fix_tool_call_ordering([orphan])

    assert result == [orphan]


# ---------------------------------------------------------------------------
# Case F — empty list returns empty list
# ---------------------------------------------------------------------------


def test_empty_list_returns_empty() -> None:
    """Empty input produces empty output."""
    assert _fix_tool_call_ordering([]) == []


# ---------------------------------------------------------------------------
# Case G — camelCase toolCallId fallback (AG-UI variant)
# ---------------------------------------------------------------------------


def test_camel_case_tool_call_id_fallback() -> None:
    """tool_call_id may arrive as camelCase toolCallId in some AG-UI payloads."""
    asst = _make_assistant(["c1"])
    # Use camelCase key instead of snake_case
    tool_camel = {"role": "tool", "toolCallId": "c1", "content": "result"}
    user = _make_user()

    result = _fix_tool_call_ordering([user, tool_camel, asst])

    assert result == [user, asst, tool_camel]


# ---------------------------------------------------------------------------
# Case H — multiple tool results before a shared assistant, no duplicate
# ---------------------------------------------------------------------------


def test_multi_tool_results_before_shared_assistant_no_duplicate() -> None:
    """When N tool results all precede their single shared assistant,
    the assistant appears exactly once and precedes all its results."""
    user = _make_user()
    asst = _make_assistant(["c1", "c2"])
    tool1 = _make_tool_result("c1")
    tool2 = _make_tool_result("c2")

    result = _fix_tool_call_ordering([user, tool1, tool2, asst])

    assert result == [user, asst, tool1, tool2]
    assert result.count(asst) == 1
