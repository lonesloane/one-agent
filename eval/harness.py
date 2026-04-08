"""Evaluation harness for scenarios against Azure AI Foundry models."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv
from loguru import logger

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

from eval.aggregators import aggregate_model_scores
from eval.evaluators import score_scenario
from eval.middleware import RecorderMiddleware
from eval.results_writer import write_json_results, write_markdown_summary
from eval.tools import ALL_TOOLS, SCENARIO_DATA
from eval.types import ScenarioScore

load_dotenv()

SYSTEM_PROMPT = (
    "You are the ONE-MP Assistant, helping delegates and staff of an"
    " international organisation. You have access to tools for looking"
    " up delegations, delegates, meetings, and documents, as well as"
    " creating new delegate records and managing document access"
    " rights. Always use the tools available to you rather than"
    " guessing. If you lack required information to complete a task,"
    " ask the user for the missing details rather than inventing them."
    " When creating a delegate, always follow this sequence: first"
    " check whether the delegate already exists using lookup_delegate,"
    " then retrieve the delegation's details using get_delegation_info"
    " to determine membership type, then create the delegate record,"
    " then create the appropriate document access rights based on the"
    " delegation's membership type."
)

DEFAULT_MODEL = "gpt-4.1-mini"

MODELS: list[str] = [
    "gpt-5.4-nano",
    "gpt-4.1-nano",
    "gpt-5.4-mini",
    "gpt-4.1-mini",
    "o4-mini",
    "grok-3-mini",
]

SCENARIOS_PATH = Path(__file__).parent / "scenarios" / "scenarios.json"


def filter_scenarios(
    scenarios: list[dict],
    category: str | None,
) -> list[dict]:
    """Filter scenarios by category.

    Args:
        scenarios: Full list of scenario dicts from scenarios.json.
        category: Category to filter on, or None to return all.

    Returns:
        Filtered list of scenario dicts matching the given category,
        or the full list when category is None.
    """
    if category is None:
        return scenarios
    return [s for s in scenarios if s.get("category") == category]


async def _run_agent(
    model: str,
    scenario: dict,
    verbose: bool = False,
) -> tuple[list[dict], str]:
    """Set up and run the agent for one scenario.

    Args:
        model: Model identifier deployed in Azure AI Foundry.
        scenario: Scenario dict loaded from scenarios.json.
        verbose: When True, log tool call trace at DEBUG level.

    Returns:
        Tuple of (tool_calls, agent_response_text).
    """
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

    # Reason: SCENARIO_DATA is a module-level singleton;
    # do not call concurrently.
    SCENARIO_DATA.clear()
    SCENARIO_DATA.update(scenario.get("synthetic_results", {}))

    instructions = SYSTEM_PROMPT
    if scenario.get("system_context"):
        instructions += f"\n\n{scenario['system_context']}"

    recorder = RecorderMiddleware()

    async with (
        AzureCliCredential() as credential,
        Agent(
            client=FoundryChatClient(
                project_endpoint=endpoint,
                model=model,
                credential=credential,
            ),
            name="ONEAgent-Eval",
            instructions=instructions,
            tools=ALL_TOOLS,
            middleware=[recorder],
        ) as agent,
    ):
        result = await asyncio.wait_for(
            agent.run(scenario["user_message"]),
            timeout=90,
        )

    if verbose:
        logger.debug("Tool calls: {}", recorder.calls)
    return recorder.calls, result.text


async def evaluate_scenario(
    model: str,
    scenario: dict,
    verbose: bool = False,
) -> dict:
    """Run a single scenario and return scored results.

    Args:
        model: Model identifier deployed in Azure AI Foundry.
        scenario: Scenario dict loaded from scenarios.json.
        verbose: When True, log full tool call trace at DEBUG level.

    Returns:
        Dict with model, scenario_id, tool_calls, agent_response,
        and scores.
    """
    tool_calls, agent_response = await _run_agent(
        model, scenario, verbose
    )
    scores = score_scenario(
        scenario_id=scenario["id"],
        tool_calls=tool_calls,
        agent_response=agent_response,
        expected=scenario["expected"],
    )
    return {
        "model": model,
        "scenario_id": scenario["id"],
        "tool_calls": tool_calls,
        "agent_response": agent_response,
        "scores": {
            "criteria": scores.criteria,
            "details": scores.details,
        },
    }


async def run_model(
    model: str,
    scenarios: list[dict],
    verbose: bool = False,
) -> list[dict]:
    """Run all given scenarios against a single model.

    Args:
        model: Model identifier deployed in Azure AI Foundry.
        scenarios: List of scenario dicts to evaluate.
        verbose: When True, pass verbose flag to each scenario run.

    Returns:
        List of result dicts from evaluate_scenario.
    """
    logger.info(
        "Running {} scenarios on model '{}'",
        len(scenarios),
        model,
    )

    results = []
    for scenario in scenarios:
        logger.info(
            "Evaluating scenario {} - {}",
            scenario["id"],
            scenario["description"],
        )
        try:
            result = await evaluate_scenario(
                model, scenario, verbose=verbose
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Scenario {} [{}]: TIMEOUT (>90s), skipping",
                scenario["id"],
                model,
            )
            continue
        except Exception as exc:
            logger.warning(
                "Scenario {} [{}]: ERROR — {}, skipping",
                scenario["id"],
                model,
                exc,
            )
            continue

        results.append(result)

        criteria = result["scores"]["criteria"]
        all_pass = all(
            v is True
            for v in criteria.values()
            if v is not None
        )
        logger.info(
            "Scenario {} [{}]: {}",
            result["scenario_id"],
            model,
            "PASS" if all_pass else "FAIL",
        )

    return results


async def run_all(model: str = DEFAULT_MODEL) -> list[dict]:
    """Load all scenarios and evaluate each against the given model.

    Backward-compatible wrapper around run_model that loads scenarios
    from SCENARIOS_PATH.

    Args:
        model: Model identifier to evaluate. Defaults to gpt-4.1-mini.

    Returns:
        List of result dicts from run_model.
    """
    with open(SCENARIOS_PATH) as f:
        scenarios = json.load(f)
    return await run_model(model, scenarios)


def _print_results(results: list[dict]) -> None:
    """Log a summary of evaluation results.

    Args:
        results: List of result dicts from run_model or run_all.
    """
    logger.info("=" * 60)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 60)

    for result in results:
        logger.info(
            "Scenario: {} (model: {})",
            result["scenario_id"],
            result["model"],
        )
        logger.info(
            "  Tool calls: {}",
            [tc["tool"] for tc in result["tool_calls"]],
        )
        logger.info(
            "  Agent response: {}",
            result["agent_response"][:200],
        )
        criteria = result["scores"]["criteria"]
        details = result["scores"]["details"]
        for crit, passed in criteria.items():
            status = (
                "PASS" if passed is True
                else "FAIL" if passed is False
                else "SKIP"
            )
            logger.info(
                "  {}: {} - {}",
                crit,
                status,
                details.get(crit, ""),
            )


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="ONE-MP evaluation harness",
    )
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument(
        "--all",
        action="store_true",
        dest="run_all_models",
        help="Run evaluation against all models in MODELS.",
    )
    model_group.add_argument(
        "--model",
        metavar="NAME",
        help=(
            f"Model to evaluate (one of: {', '.join(MODELS)})."
        ),
    )
    parser.add_argument(
        "--category",
        metavar="CAT",
        help=(
            "Filter scenarios by category: single_tool_read, "
            "multi_step_sequencing, missing_information, business_rule."
        ),
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Output path for results (JSON/Markdown report).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log full tool call traces at DEBUG level.",
    )
    return parser


async def main() -> None:
    """Entry point for the evaluation harness CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    if "FOUNDRY_PROJECT_ENDPOINT" not in os.environ:
        parser.error(
            "FOUNDRY_PROJECT_ENDPOINT is not set."
            " Check your .env file."
        )

    if args.model and args.model not in MODELS:
        parser.error(
            f"Unknown model '{args.model}'. "
            f"Valid choices: {', '.join(MODELS)}"
        )

    if args.run_all_models:
        models_to_run = MODELS
    elif args.model:
        models_to_run = [args.model]
    else:
        models_to_run = [DEFAULT_MODEL]

    with open(SCENARIOS_PATH) as f:
        all_scenarios = json.load(f)

    scenarios = filter_scenarios(all_scenarios, args.category)
    logger.info(
        "Loaded {} scenarios (category filter: {})",
        len(scenarios),
        args.category or "none",
    )

    all_results: list[dict] = []
    evaluated_models: list[str] = []
    skipped_models: list[tuple[str, str]] = []

    for model in models_to_run:
        try:
            results = await run_model(
                model, scenarios, verbose=args.verbose
            )
            all_results.extend(results)
            evaluated_models.append(model)
        except Exception as exc:
            reason = str(exc)
            logger.warning(
                "Skipping model '{}': {}", model, reason
            )
            skipped_models.append((model, reason))

    if skipped_models:
        logger.warning(
            "Skipped {} model(s): {}",
            len(skipped_models),
            [m for m, _ in skipped_models],
        )

    _print_results(all_results)

    if args.output:
        model_scores = []
        for model in evaluated_models:
            model_results = [
                r for r in all_results if r["model"] == model
            ]
            scenario_scores = [
                ScenarioScore(
                    scenario_id=r["scenario_id"],
                    criteria=r["scores"]["criteria"],
                    details=r["scores"]["details"],
                )
                for r in model_results
            ]
            model_scores.append(
                aggregate_model_scores(model, scenario_scores)
            )
        json_path = write_json_results(
            all_results, args.output,
            models=evaluated_models,
            skipped_models=skipped_models,
        )
        md_path = write_markdown_summary(
            model_scores, args.output,
            results=all_results,
            skipped_models=skipped_models,
        )
        logger.info("Results written to: {}", json_path)
        logger.info("Summary written to: {}", md_path)


if __name__ == "__main__":
    asyncio.run(main())
