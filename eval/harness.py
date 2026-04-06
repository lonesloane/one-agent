"""Evaluation harness for running scenarios against Azure AI Foundry models."""

import asyncio
import json
import os
from pathlib import Path

from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv
from loguru import logger

from agent_framework import Agent

from agent_framework.foundry import FoundryChatClient

from eval.evaluators import score_scenario
from eval.middleware import RecorderMiddleware
from eval.tools import ALL_TOOLS, SCENARIO_DATA

load_dotenv()

SYSTEM_PROMPT = (
    "You are the ONE-MP Assistant, helping delegates and staff of an"
    " international organisation. You have access to tools for looking"
    " up delegations, delegates, meetings, and documents, as well as"
    " creating new delegate records and managing document access"
    " rights. Always use the tools available to you rather than"
    " guessing. If you lack required information to complete a task,"
    " ask the user for the missing details rather than inventing them."
)

DEFAULT_MODEL = "gpt-4.1-mini"

SCENARIOS_PATH = Path(__file__).parent / "scenarios" / "scenarios.json"


async def evaluate_scenario(
    model: str,
    scenario: dict,
) -> dict:
    """Run a single scenario and return scored results.

    Args:
        model: Model identifier deployed in Azure AI Foundry.
        scenario: Scenario dict loaded from scenarios.json.

    Returns:
        Dict with model, scenario_id, tool_calls, agent_response,
        and scores.
    """
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

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
        result = await agent.run(scenario["user_message"])

    scores = score_scenario(
        scenario_id=scenario["id"],
        tool_calls=recorder.calls,
        agent_response=result.text,
        expected=scenario["expected"],
    )

    return {
        "model": model,
        "scenario_id": scenario["id"],
        "tool_calls": recorder.calls,
        "agent_response": result.text,
        "scores": {
            "criteria": scores.criteria,
            "details": scores.details,
        },
    }


async def run_all(model: str = DEFAULT_MODEL) -> list[dict]:
    """Load scenarios and evaluate each against the given model.

    Args:
        model: Model identifier to evaluate. Defaults to gpt-4.1-mini.

    Returns:
        List of result dicts from evaluate_scenario.
    """
    with open(SCENARIOS_PATH) as f:
        scenarios = json.load(f)

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
        result = await evaluate_scenario(model, scenario)
        results.append(result)
        logger.info(
            "Scenario {} complete: {} tool calls",
            result["scenario_id"],
            len(result["tool_calls"]),
        )

    return results


def _print_results(results: list[dict]) -> None:
    """Log a summary of evaluation results.

    Args:
        results: List of result dicts from run_all.
    """
    logger.info("=" * 60)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 60)

    for result in results:
        logger.info(
            "\nScenario: {} (model: {})",
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


async def main() -> None:
    """Entry point for the evaluation harness."""
    results = await run_all()
    _print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
