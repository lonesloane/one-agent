"""Stub tools for the evaluation harness."""

from typing import Annotated

from agent_framework import tool
from pydantic import Field


SCENARIO_DATA: dict = {}


@tool(approval_mode="never_require")
def get_delegation_info(
    delegation_id: Annotated[
        str,
        Field(description="Delegation ID or country/organization name"),
    ],
) -> str:
    """Look up delegation information by ID or country name."""
    return SCENARIO_DATA.get(
        "get_delegation_info",
        '{"name": "Unknown", "type": "unknown", "delegates": 0}',
    )


@tool(approval_mode="never_require")
def lookup_delegate(
    name: Annotated[
        str,
        Field(description="Delegate name to search for"),
    ],
    delegation_id: Annotated[
        str,
        Field(description="Delegation to search within"),
    ] = "",
) -> str:
    """Search for a delegate by name, optionally within a specific delegation."""
    return SCENARIO_DATA.get(
        "lookup_delegate",
        "No delegate found matching the search criteria.",
    )


@tool(approval_mode="never_require")
def get_upcoming_meetings(
    delegate_id: Annotated[
        str,
        Field(description="Delegate ID to look up meetings for"),
    ],
) -> str:
    """Retrieve upcoming meetings for a specific delegate."""
    return SCENARIO_DATA.get("get_upcoming_meetings", '{"meetings": []}')


@tool(approval_mode="never_require")
def get_agenda_documents(
    meeting_id: Annotated[
        str,
        Field(description="Meeting ID to retrieve agenda documents for"),
    ],
    since: Annotated[
        str,
        Field(
            description=(
                "ISO date - only return docs added/modified after this date"
            )
        ),
    ] = "",
) -> str:
    """Retrieve agenda documents for a meeting, optionally filtered by date."""
    return SCENARIO_DATA.get(
        "get_agenda_documents", '{"documents": []}'
    )


@tool(approval_mode="never_require")
def create_delegate(
    full_name: Annotated[
        str,
        Field(description="Full name of the delegate"),
    ],
    delegation_id: Annotated[
        str,
        Field(description="Delegation this delegate belongs to"),
    ],
    function: Annotated[
        str,
        Field(description="Professional function"),
    ],
    email: Annotated[
        str,
        Field(description="Professional email address"),
    ],
    committee_ids: Annotated[
        list[str],
        Field(description="Committees the delegate will participate in"),
    ],
) -> str:
    """Create a new delegate record in the system."""
    return SCENARIO_DATA.get(
        "create_delegate",
        f"Delegate '{full_name}' created (ID: DEL-2026-0891)",
    )


@tool(approval_mode="never_require")
def create_document_access_rights(
    delegate_id: Annotated[
        str,
        Field(description="Delegate to grant access to"),
    ],
    committee_id: Annotated[
        str,
        Field(description="Committee scoping the document access"),
    ],
    classification_level: Annotated[
        str,
        Field(
            description=(
                "Max classification: General, Restricted, or Confidential"
            )
        ),
    ],
    retroactive: Annotated[
        bool,
        Field(
            description=(
                "Include documents published before accreditation date"
            )
        ),
    ] = False,
) -> str:
    """Grant document access rights to a delegate for a specific committee."""
    return SCENARIO_DATA.get(
        "create_document_access_rights",
        (
            f"Access rights granted: delegate={delegate_id},"
            f" committee={committee_id}, level={classification_level}"
        ),
    )


ALL_TOOLS: list = [
    get_delegation_info,
    lookup_delegate,
    get_upcoming_meetings,
    get_agenda_documents,
    create_delegate,
    create_document_access_rights,
]
