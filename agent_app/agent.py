"""Agent factory for the ONE-MP Agent app.

Constructs the Microsoft Agent Framework Agent instance with a
FoundryChatClient backed by Azure Foundry and an AzureCliCredential.
"""

from __future__ import annotations

import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from loguru import logger

from agent_app.tools.delegate import make_get_current_delegate_summary


def _get_endpoint() -> str:
    """Return the Foundry project endpoint or raise.

    Returns:
        The FOUNDRY_PROJECT_ENDPOINT env-var value.

    Raises:
        RuntimeError: If FOUNDRY_PROJECT_ENDPOINT is not set.
    """
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "FOUNDRY_PROJECT_ENDPOINT is not set. "
            "Copy .env.example to .env and fill in the endpoint."
        )
    return endpoint


def build_agent(
    *,
    credential: AzureCliCredential,
    delegate_id: str,
    model: str = "gpt-4.1-mini",
) -> Agent:
    """Build the ONE-MP agent for the given delegate session.

    The delegate_id is bound into read-only tools via closure so the
    model never sees it as a tool argument (SEC-001 / PAT-001).

    Args:
        credential: Azure credential (caller manages its lifetime).
        delegate_id: String ID of the authenticated delegate (e.g.
            ``"DEL-2026-0001"``). Bound into tool closures; never
            exposed to the model as a parameter.
        model: Foundry deployment name. Defaults to ``gpt-4.1-mini``.

    Returns:
        An Agent ready to call ``create_session()`` on.
    """
    logger.debug("Building agent for delegate_id={}", delegate_id)
    get_current_delegate_summary = make_get_current_delegate_summary(
        delegate_id
    )
    return Agent(
        client=FoundryChatClient(
            project_endpoint=_get_endpoint(),
            model=model,
            credential=credential,
        ),
        name="OneMPAgent",
        instructions=(
            "You assist a delegate. Tools added in subsequent phases."
        ),
        tools=[get_current_delegate_summary],
    )
