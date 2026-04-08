"""Shared data types for the evaluation harness."""

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
