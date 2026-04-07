"""Evaluation scoring for scenario tool call traces."""

from dataclasses import dataclass, field


@dataclass
class ScenarioScore:
    """Score results for a single scenario evaluation.

    Attributes:
        scenario_id: Unique identifier for the evaluated scenario.
        criteria: Maps criterion name (e.g. "C1") to True/False/None,
            where None means the criterion is not applicable.
        details: Maps criterion name to a human-readable explanation
            of the evaluation result.
    """

    scenario_id: str
    criteria: dict[str, bool | None] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)


_WRITE_TOOLS: frozenset[str] = frozenset(
    {"create_delegate", "create_document_access_rights"}
)

_QUESTION_PHRASES: tuple[str, ...] = (
    "could you",
    "please provide",
    "what is",
    "which ",
    "can you tell",
    "do you have",
    "what committee",
    "what email",
    "what delegation",
)


def evaluate_c1_correct_tool(
    tool_calls: list[dict],
    expected: dict,
) -> tuple[bool, str]:
    """Check that the agent called the correct tools.

    Args:
        tool_calls: List of tool call dicts, each containing a "tool"
            key with the tool name.
        expected: Expected outcomes dict, containing "tool_calls_ordered"
            (list of dicts with "name" keys) and optionally
            "should_ask_user" (bool).

    Returns:
        A tuple of (passed, detail) where passed is True if the
        criterion is met and detail is a human-readable explanation.
    """
    expected_names = {
        tc["name"] for tc in expected.get("tool_calls_ordered", [])
    }

    if (
        expected.get("should_ask_user") is True
        and len(expected.get("tool_calls_ordered", [])) == 0
    ):
        actual_names = {tc["tool"] for tc in tool_calls}
        called_write_tools = actual_names & _WRITE_TOOLS

        if not called_write_tools:
            return (
                True,
                "Correctly avoided write tools when info missing",
            )
        else:
            return (
                False,
                f"Called write tool(s) {called_write_tools} when"
                " should have asked user",
            )

    actual_names = {tc["tool"] for tc in tool_calls}

    if expected_names.issubset(actual_names):
        return (
            True,
            f"All expected tools called: {sorted(expected_names)}",
        )

    missing = expected_names - actual_names
    return (False, f"Missing tools: {sorted(missing)}")


def _args_value_matches(actual: object, expected_val: object) -> bool:
    """Compare an actual arg value to an expected value.

    Strings are compared case-insensitively; all other types use
    exact equality.

    Args:
        actual: The value from the actual tool call.
        expected_val: The value from the expected specification.

    Returns:
        True if the values match according to the comparison rules.
    """
    if isinstance(expected_val, str) and isinstance(actual, str):
        return actual.lower() == expected_val.lower()
    return actual == expected_val


def _check_entry_args(
    entry: dict,
    actual_by_tool: dict,
) -> tuple[bool, str]:
    """Check that a single expected tool entry's args match the actual call.

    Args:
        entry: A dict with ``"name"`` and ``"args_must_contain"`` keys
            from the expected spec.
        actual_by_tool: Maps tool name to the first actual call dict
            for that tool.

    Returns:
        A tuple of (passed, detail). ``passed`` is True when all
        required args are present and match; False with a description
        of the first failure.
    """
    name = entry["name"]
    if name not in actual_by_tool:
        return (False, f"Tool '{name}' was not called")

    args_must_contain = entry.get("args_must_contain", {})
    if not args_must_contain:
        return (True, "")

    actual_args = actual_by_tool[name].get("arguments", {})
    for key, expected_val in args_must_contain.items():
        if key not in actual_args:
            return (
                False,
                f"Tool '{name}': required arg '{key}' not present",
            )
        if not _args_value_matches(actual_args[key], expected_val):
            return (
                False,
                f"Tool '{name}': arg '{key}' value mismatch"
                f" (expected {expected_val!r},"
                f" got {actual_args[key]!r})",
            )
    return (True, "")


def evaluate_c2_schema_valid_args(
    tool_calls: list[dict],
    expected: dict,
) -> tuple[bool, str]:
    """Check that tool arguments match expected schema.

    For each entry in ``expected["tool_calls_ordered"]``, finds the
    matching actual call by tool name and verifies that all keys in
    ``args_must_contain`` are present with matching values. String
    values are compared case-insensitively; booleans and numbers use
    exact match.

    Args:
        tool_calls: List of tool call dicts recorded during the run,
            each with ``"tool"`` and ``"arguments"`` keys.
            When a tool appears multiple times, only the first
            occurrence is used for arg matching.
        expected: Expected outcomes dict containing
            ``"tool_calls_ordered"`` (list of dicts with ``"name"``
            and ``"args_must_contain"`` keys).

    Returns:
        A tuple of (passed, detail). ``passed`` is True if all checks
        pass; False with a description of the first failure.
    """
    ordered = expected.get("tool_calls_ordered", [])
    if not ordered:
        return (True, "No tool calls expected — C2 not applicable")

    # Reason: first-occurrence semantics — avoids false passes caused
    # by a retry call that happens to supply correct args after an
    # initial call with incorrect ones.
    actual_by_tool: dict[str, dict] = {}
    for tc in tool_calls:
        if tc["tool"] not in actual_by_tool:
            actual_by_tool[tc["tool"]] = tc

    for entry in ordered:
        passed, detail = _check_entry_args(entry, actual_by_tool)
        if not passed:
            return (False, detail)

    return (True, "All required args present and matching")


def _find_tool_in_sequence(
    name: str,
    actual_tool_names: list[str],
    search_from: int,
    prev_name: str | None,
) -> tuple[int | None, str]:
    """Locate a tool name at or after a given position in the sequence.

    Args:
        name: Tool name to search for.
        actual_tool_names: Ordered list of actual tool names.
        search_from: Index at which to start searching.
        prev_name: Name of the previous required tool, used in the
            error message when ``name`` is not found.

    Returns:
        A tuple of (position, error). ``position`` is the found index
        or None; ``error`` is an empty string on success or a
        human-readable failure message.
    """
    try:
        pos = actual_tool_names.index(name, search_from)
        return (pos, "")
    except ValueError:
        if prev_name is not None:
            return (
                None,
                f"Tool '{name}' not found after '{prev_name}'"
                " in actual sequence",
            )
        return (None, f"Tool '{name}' not found in actual sequence")


def evaluate_c3_multi_step_sequencing(
    tool_calls: list[dict],
    expected: dict,
) -> tuple[bool, str]:
    """Check that multi-step tool calls follow the expected relative order.

    Verifies that the required tools appear in the same relative order
    as ``expected["tool_calls_ordered"]``. Interleaved extra calls are
    allowed; only relative ordering of the required tools matters.

    Args:
        tool_calls: List of tool call dicts recorded during the run,
            each with a ``"tool"`` key.
        expected: Expected outcomes dict containing
            ``"tool_calls_ordered"`` (list of dicts with ``"name"``
            keys).

    Returns:
        A tuple of (passed, detail). ``passed`` is True if the required
        tools appear in order; False with a description of the first
        ordering violation.
    """
    ordered = expected.get("tool_calls_ordered", [])
    if len(ordered) < 2:
        return (
            True,
            "Single or zero tool calls — sequencing not applicable",
        )

    actual_tool_names = [tc["tool"] for tc in tool_calls]
    search_from = 0
    prev_name = None

    for entry in ordered:
        name = entry["name"]
        pos, error = _find_tool_in_sequence(
            name, actual_tool_names, search_from, prev_name
        )
        if pos is None:
            return (False, error)
        search_from = pos + 1
        prev_name = name

    expected_names = [e["name"] for e in ordered]
    return (True, f"Tools called in correct order: {expected_names}")


def _response_contains_question(response: str) -> bool:
    """Return True if the response appears to ask the user a question.

    Args:
        response: The agent's final text response.

    Returns:
        True if the response ends with '?' or contains a known
        question phrase (case-insensitive).
    """
    if response.strip().endswith("?"):
        return True
    lowered = response.lower()
    return any(phrase in lowered for phrase in _QUESTION_PHRASES)


def _evaluate_c4_should_ask(
    tool_calls: list[dict],
    agent_response: str,
) -> tuple[bool, str]:
    """Evaluate C4 for the should_ask_user=True branch.

    Args:
        tool_calls: List of tool call dicts, each with a ``"tool"`` key.
        agent_response: The agent's final text response.

    Returns:
        A tuple of (passed, detail).
    """
    actual_tools = {tc["tool"] for tc in tool_calls}
    called_write = actual_tools & _WRITE_TOOLS
    if called_write:
        tool_name = next(iter(called_write))
        return (
            False,
            f"Called write tool '{tool_name}' when should have asked",
        )
    if not _response_contains_question(agent_response):
        return (
            False,
            "Agent did not ask a question when info was missing",
        )
    return (True, "Correctly asked for missing information")


def evaluate_c4_asks_vs_invents(
    tool_calls: list[dict],
    agent_response: str,
    expected: dict,
) -> tuple[bool, str]:
    """Check that the agent asks for missing info instead of inventing it.

    Branch A (``should_ask_user`` is True): passes when no write tool
    was called and the agent response contains a question.

    Branch B (``should_ask_user`` is False): passes immediately when
    ``must_not_hallucinate`` is empty. When non-empty, defers to manual
    review — automated hallucination checking is a known limitation.

    Args:
        tool_calls: List of tool call dicts recorded during the run,
            each with a ``"tool"`` key.
        agent_response: The agent's final text response.
        expected: Expected outcomes dict containing
            ``"should_ask_user"`` (bool) and
            ``"must_not_hallucinate"`` (list of field names).

    Returns:
        A tuple of (passed, detail). ``passed`` is True if the
        criterion is met; False with a human-readable explanation.
    """
    if expected.get("should_ask_user", False):
        return _evaluate_c4_should_ask(tool_calls, agent_response)

    # Branch B — should_ask_user is False
    must_not_hallucinate = expected.get("must_not_hallucinate", [])
    if not must_not_hallucinate:
        return (True, "No hallucination fields to check")
    return (True, "Hallucination check deferred to manual review")


def score_scenario(
    scenario_id: str,
    tool_calls: list[dict],
    agent_response: str,
    expected: dict,
) -> ScenarioScore:
    """Score a scenario run against expected outcomes.

    Evaluates each applicable criterion defined in
    ``expected["applicable_criteria"]`` and records pass/fail results
    along with human-readable detail strings. Criteria absent from the
    applicable list are recorded as None (not applicable).

    Args:
        scenario_id: Unique identifier for the scenario being scored.
        tool_calls: List of tool call dicts recorded during the run,
            each containing at minimum a "tool" key.
        agent_response: The agent's final text response for the run.
        expected: Expected outcomes dict for the scenario, must contain
            an "applicable_criteria" key listing criterion identifiers
            (e.g. ["C1", "C3"]).

    Returns:
        A ScenarioScore populated with per-criterion results.
    """
    applicable = expected.get("applicable_criteria", [])
    score = ScenarioScore(scenario_id=scenario_id)

    evaluators = {
        "C1": lambda: evaluate_c1_correct_tool(tool_calls, expected),
        "C2": lambda: evaluate_c2_schema_valid_args(tool_calls, expected),
        "C3": lambda: evaluate_c3_multi_step_sequencing(
            tool_calls, expected
        ),
        "C4": lambda: evaluate_c4_asks_vs_invents(
            tool_calls, agent_response, expected
        ),
    }

    for criterion, evaluator in evaluators.items():
        if criterion in applicable:
            result, detail = evaluator()
            score.criteria[criterion] = result
            score.details[criterion] = detail
        else:
            score.criteria[criterion] = None
            score.details[criterion] = "Not applicable"

    return score
