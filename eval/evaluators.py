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
        WRITE_TOOLS = {"create_delegate", "create_document_access_rights"}
        actual_names = {tc["tool"] for tc in tool_calls}
        called_write_tools = actual_names & WRITE_TOOLS

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


def evaluate_c2_schema_valid_args(
    tool_calls: list[dict],
    expected: dict,
) -> tuple[None, str]:
    """Check that tool arguments match expected schema.

    Args:
        tool_calls: List of tool call dicts recorded during the run.
        expected: Expected outcomes dict for the scenario.

    Returns:
        A tuple of (None, detail) — not yet implemented.
    """
    return (None, "Not implemented - Phase 0b")


def evaluate_c3_multi_step_sequencing(
    tool_calls: list[dict],
    expected: dict,
) -> tuple[None, str]:
    """Check that multi-step tool calls follow correct order.

    Args:
        tool_calls: List of tool call dicts recorded during the run.
        expected: Expected outcomes dict for the scenario.

    Returns:
        A tuple of (None, detail) — not yet implemented.
    """
    return (None, "Not implemented - Phase 0b")


def evaluate_c4_asks_vs_invents(
    tool_calls: list[dict],
    agent_response: str,
    expected: dict,
) -> tuple[None, str]:
    """Check that agent asks for missing info instead of inventing it.

    Args:
        tool_calls: List of tool call dicts recorded during the run.
        agent_response: The agent's final text response.
        expected: Expected outcomes dict for the scenario.

    Returns:
        A tuple of (None, detail) — not yet implemented.
    """
    return (None, "Not implemented - Phase 0b")


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
