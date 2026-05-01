"""Shared MAF agent definition for spike candidates C1, C2, C4.

Defines two tools (one read, one approval-gated write) operating on an
in-memory record list. The agent is identical across all three spikes
so that any HITL-contract differences observed in T1-T4 are
attributable to the frontend stack, not the agent definition.

Uses FoundryChatClient + gpt-4.1-mini per the project's selected-model
decision (see docs/DECISIONS.md, 2026-04-10).
"""

from __future__ import annotations

import os
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv
from pydantic import Field

# Load .env once on import so spikes pick up FOUNDRY_PROJECT_ENDPOINT
# without requiring shell exports.
load_dotenv()

# In-memory store. Reset on process restart. Not thread-safe.
_RECORDS: list[str] = ["alpha", "beta"]


@tool
def list_records() -> str:
    """Return a comma-separated list of records currently stored."""
    return ", ".join(_RECORDS) if _RECORDS else "(no records)"


@tool(approval_mode="always_require")
def create_record(
    name: Annotated[
        str,
        Field(description="Name of the record to create"),
    ],
) -> str:
    """Create a new record with the given name."""
    _RECORDS.append(name)
    return f"Record '{name}' created. Total: {len(_RECORDS)}."


def get_endpoint() -> str:
    """Return the Foundry project endpoint or raise."""
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
    model: str = "gpt-4.1-mini",
) -> Agent:
    """Build the spike agent with the shared tools.

    Args:
        credential: Azure credential (caller manages its lifetime).
        model: Foundry deployment name. Defaults to gpt-4.1-mini.

    Returns:
        An Agent ready to run. Caller is responsible for entering the
        agent's async context if required by the framework.
    """
    return Agent(
        client=FoundryChatClient(
            project_endpoint=get_endpoint(),
            model=model,
            credential=credential,
        ),
        name="SpikeAgent",
        instructions=(
            "You assist a user managing a list of records. "
            "Use list_records to read. "
            "When the user asks to create a record and provides a "
            "name, immediately call create_record with that name. "
            "Do not ask for additional confirmation in chat — the "
            "system handles approval through a separate mechanism."
        ),
        tools=[list_records, create_record],
    )
