"""Score aggregation across scenarios and criteria for model
evaluation."""

from dataclasses import dataclass

from eval.types import ScenarioScore


_AGGREGATE_THRESHOLD = 0.85
_CRITERION_THRESHOLD = 0.75
_CRITERIA_KEYS = ("C1", "C2", "C3", "C4")


@dataclass
class ModelScore:
    """Aggregated evaluation score for a single model.

    Attributes:
        model: Identifier of the model being evaluated.
        aggregate_score: Mean per-prompt score across all scenarios
            (range 0.0–1.0).
        criterion_pass_rates: Maps each criterion (C1–C4) to the
            fraction of applicable scenarios where it passed.
        per_prompt_scores: Maps scenario_id to its individual prompt
            score (range 0.0–1.0).
        passes_aggregate: True when aggregate_score >= 0.85.
        passes_all_criteria: True when every criterion pass rate
            is >= 0.75.
        overall_pass: True when both passes_aggregate and
            passes_all_criteria are True.
    """

    model: str
    aggregate_score: float
    criterion_pass_rates: dict[str, float]
    per_prompt_scores: dict[str, float]
    passes_aggregate: bool
    passes_all_criteria: bool
    overall_pass: bool


def compute_prompt_score(scenario_score: ScenarioScore) -> float:
    """Compute the pass rate for a single scenario across its criteria.

    Counts only criteria that are applicable (not None). If no criteria
    are applicable, returns 0.0.

    Args:
        scenario_score: The scored result for one scenario run.

    Returns:
        Fraction of applicable criteria that passed (0.0–1.0).
    """
    applicable = [
        v for v in scenario_score.criteria.values() if v is not None
    ]
    if not applicable:
        return 0.0
    return sum(1 for v in applicable if v is True) / len(applicable)


def compute_criterion_pass_rate(
    scenario_scores: list[ScenarioScore],
    criterion: str,
) -> float:
    """Compute the pass rate for one criterion across all scenarios.

    Only scenarios where the criterion is applicable (not None) are
    counted. If no scenarios have the criterion applicable, returns 1.0
    (vacuously true — the criterion does not apply here).

    Args:
        scenario_scores: Scored results for all evaluated scenarios.
        criterion: Criterion identifier to aggregate (e.g. "C1").

    Returns:
        Fraction of applicable scenarios where the criterion passed
        (0.0–1.0), or 1.0 if none are applicable.
    """
    applicable = [
        s.criteria[criterion]
        for s in scenario_scores
        if criterion in s.criteria and s.criteria[criterion] is not None
    ]
    if not applicable:
        return 1.0
    return sum(1 for v in applicable if v is True) / len(applicable)


def aggregate_model_scores(
    model: str,
    scenario_scores: list[ScenarioScore],
) -> ModelScore:
    """Aggregate per-scenario scores into a single ModelScore.

    Args:
        model: Identifier of the model being evaluated.
        scenario_scores: Scored results for all evaluated scenarios.

    Returns:
        A ModelScore summarising aggregate and per-criterion results.
    """
    per_prompt = {
        s.scenario_id: compute_prompt_score(s) for s in scenario_scores
    }
    aggregate = (
        sum(per_prompt.values()) / len(scenario_scores)
        if scenario_scores
        else 0.0
    )
    criterion_pass_rates = {
        c: compute_criterion_pass_rate(scenario_scores, c)
        for c in _CRITERIA_KEYS
    }
    passes_aggregate = aggregate >= _AGGREGATE_THRESHOLD
    passes_all_criteria = all(
        rate >= _CRITERION_THRESHOLD
        for rate in criterion_pass_rates.values()
    )
    return ModelScore(
        model=model,
        aggregate_score=aggregate,
        criterion_pass_rates=criterion_pass_rates,
        per_prompt_scores=per_prompt,
        passes_aggregate=passes_aggregate,
        passes_all_criteria=passes_all_criteria,
        overall_pass=passes_aggregate and passes_all_criteria,
    )
