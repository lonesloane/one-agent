"""Write evaluation results to JSON and Markdown formats."""

import datetime
import json
from pathlib import Path

from eval.aggregators import ModelScore

_COST_TIER: dict[str, str] = {
    "gpt-5.4-nano": "nano",
    "gpt-4.1-nano": "nano",
    "gpt-5.4-mini": "mini",
    "gpt-4.1-mini": "mini",
    "o4-mini": "reasoning",
    "grok-3-mini": "mini",
}

_TIER_ORDER = ["nano", "mini", "reasoning"]


def write_json_results(
    results: list[dict],
    path: str,
    models: list[str] | None = None,
) -> str:
    """Write evaluation results to a JSON file.

    Args:
        results: List of result dicts from evaluate_scenario.
        path: Output path (directory or file). If directory or ends
            with '/', outputs to {path}/results_{today}.json.
        models: Optional list of model names. If None, extracted from
            results in order of first appearance.

    Returns:
        Absolute path to the written JSON file as a string.
    """
    path_obj = Path(path)
    today = datetime.date.today().isoformat()

    # Determine output file path
    if path_obj.is_dir() or str(path).endswith("/"):
        output_file = path_obj / f"results_{today}.json"
    else:
        output_file = path_obj

    # Extract models from results if not provided
    if models is None:
        seen = set()
        models = []
        for result in results:
            model = result["model"]
            if model not in seen:
                models.append(model)
                seen.add(model)

    # Extract scenarios (order of first appearance)
    seen = set()
    scenarios = []
    for result in results:
        scenario_id = result["scenario_id"]
        if scenario_id not in seen:
            scenarios.append(scenario_id)
            seen.add(scenario_id)

    # Build output structure
    output = {
        "run_date": today,
        "models": models,
        "scenarios": scenarios,
        "results": results,
    }

    # Ensure parent directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    return str(output_file.resolve())


def write_markdown_summary(
    model_scores: list[ModelScore],
    path: str,
    results: list[dict] | None = None,
) -> str:
    """Write a Markdown summary of model evaluation results.

    Args:
        model_scores: List of aggregated ModelScore objects.
        path: Output path (directory or file). If directory or ends
            with '/', outputs to {path}/summary_{today}.md.
        results: Optional list of result dicts for per-model
            failure details. If None, details section is omitted.

    Returns:
        Absolute path to the written Markdown file as a string.
    """
    path_obj = Path(path)
    today = datetime.date.today().isoformat()

    # Determine output file path
    if path_obj.is_dir() or str(path).endswith("/"):
        output_file = path_obj / f"summary_{today}.md"
    else:
        output_file = path_obj

    # Build markdown content
    lines = []

    # Section 1: Header
    lines.append(f"# Evaluation Summary — {today}")
    lines.append("")

    # Section 2: Decision matrix table
    lines.append("| Model | C1% | C2% | C3% | C4% | Aggregate% | "
                 "Cost Tier | Pass/Fail |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for score in model_scores:
        c1_pct = round(score.criterion_pass_rates.get("C1", 0) * 100)
        c2_pct = round(score.criterion_pass_rates.get("C2", 0) * 100)
        c3_pct = round(score.criterion_pass_rates.get("C3", 0) * 100)
        c4_pct = round(score.criterion_pass_rates.get("C4", 0) * 100)
        agg_pct = round(score.aggregate_score * 100)
        tier = _COST_TIER.get(score.model, "unknown")
        status = "✅ PASS" if score.overall_pass else "❌ FAIL"

        lines.append(
            f"| {score.model} | {c1_pct}% | {c2_pct}% | {c3_pct}% | "
            f"{c4_pct}% | {agg_pct}% | {tier} | {status} |"
        )

    lines.append("")

    # Section 3: Per-model details (only if results provided)
    if results is not None:
        for score in model_scores:
            lines.append(f"## {score.model}")
            lines.append("")

            # Find failing scenarios for this model
            model_results = [
                r for r in results if r["model"] == score.model
            ]
            failing = []
            for result in model_results:
                criteria = result["scores"]["criteria"]
                details = result["scores"]["details"]
                for crit, passed in criteria.items():
                    if passed is False:
                        failing.append({
                            "scenario_id": result["scenario_id"],
                            "criterion": crit,
                            "detail": details.get(crit, ""),
                        })

            if not failing:
                lines.append("Failing scenarios: none")
            else:
                lines.append("Failing scenarios:")
                for fail in failing:
                    lines.append(
                        f"- {fail['scenario_id']}: "
                        f"{fail['criterion']} FAIL — {fail['detail']}"
                    )

            lines.append("")

    # Section 4: Recommendation
    lines.append("## Recommendation")
    lines.append("")

    passing_models = [s for s in model_scores if s.overall_pass]
    if passing_models:
        # Sort by tier order, then alphabetically
        passing_models.sort(
            key=lambda s: (
                _TIER_ORDER.index(
                    _COST_TIER.get(s.model, "unknown")
                ),
                s.model,
            )
        )
        recommended = passing_models[0]
        tier = _COST_TIER.get(recommended.model, "unknown")
        lines.append(
            f"Cheapest passing model: **{recommended.model}** "
            f"({tier} tier)."
        )
    else:
        lines.append("No models passed all criteria.")

    lines.append("")

    # Ensure parent directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write Markdown
    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    return str(output_file.resolve())
