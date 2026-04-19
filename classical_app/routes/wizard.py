"""
Wizard blueprint — add-delegate multi-step wizard routes for Phase 2C.

Provides stub route handlers for the six steps of the add-delegate
wizard: step1 through step4, confirmation, and cancel.
"""

from typing import Any

from flask import Blueprint

from classical_app.permissions import editor_of_delegation_required
from shared.database import ApprovalStatus


APPROVAL_LABELS: dict[str, str] = {
    ApprovalStatus.AUTO_APPROVED.value: "auto-approved",
    ApprovalStatus.PENDING_DELEGATION_HEAD.value: (
        "pending delegation head approval"
    ),
    ApprovalStatus.PENDING_SECRETARIAT.value: (
        "pending OECD secretariat approval"
    ),
}

wizard_bp = Blueprint("wizard", __name__)


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step1",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step1(delegation_id: str) -> Any:
    """Handle step 1 of the add-delegate wizard."""
    return "Not implemented", 501


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step2",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step2(delegation_id: str) -> Any:
    """Handle step 2 of the add-delegate wizard."""
    return "Not implemented", 501


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step3",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step3(delegation_id: str) -> Any:
    """Handle step 3 of the add-delegate wizard."""
    return "Not implemented", 501


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step4",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step4(delegation_id: str) -> Any:
    """Handle step 4 of the add-delegate wizard."""
    return "Not implemented", 501


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/confirmation",
    methods=["GET"],
)
@editor_of_delegation_required()
def wizard_confirmation(delegation_id: str) -> Any:
    """Render the confirmation page after completing the wizard."""
    return "Not implemented", 501


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/cancel",
    methods=["POST"],
)
@editor_of_delegation_required()
def wizard_cancel(delegation_id: str) -> Any:
    """Cancel the add-delegate wizard and discard draft state."""
    return "Not implemented", 501
