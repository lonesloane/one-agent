"""
Delegations blueprint — list and detail routes for Phase 2B.

Provides read-only views for delegations, their delegates, and
framework agreements. The wizard_step1 stub is a placeholder for the
add-delegate wizard implemented in Phase 2C.
"""

from typing import Any

from flask import Blueprint, current_app, render_template
from loguru import logger
from sqlalchemy import select

from shared.database import Delegation

delegations_bp = Blueprint("delegations", __name__)


@delegations_bp.route("/delegations", methods=["GET"])
def delegation_list() -> str:
    """
    Render the list of all delegations with summary counts.

    Returns:
        Rendered delegation_list.html template with delegation rows
        containing delegate and framework agreement counts.
    """
    db_session = current_app.extensions["db_session"]
    stmt = select(Delegation)
    delegations = db_session.scalars(stmt).all()
    delegations_data = [
        {
            "delegation": d,
            "delegate_count": len(d.delegates),
            "fa_count": len(d.framework_agreements),
        }
        for d in delegations
    ]
    logger.info("Listing {} delegations", len(delegations_data))
    return render_template(
        "delegation_list.html", delegations=delegations_data
    )


@delegations_bp.route(
    "/delegations/<delegation_id>", methods=["GET"]
)
def delegation_detail(delegation_id: str) -> Any:
    """
    Render the detail page for a single delegation.

    Args:
        delegation_id: The delegation identifier.

    Returns:
        Rendered delegation_detail.html template, or 404 if not found.
    """
    db_session = current_app.extensions["db_session"]
    stmt = select(Delegation).where(Delegation.id == delegation_id)
    delegation = db_session.scalars(stmt).first()

    if delegation is None:
        logger.warning("Delegation not found: {}", delegation_id)
        return render_template("404.html"), 404

    delegates_data = [
        {
            "delegate": delegate,
            "committee_count": len(delegate.committees),
        }
        for delegate in delegation.delegates
    ]
    logger.info(
        "Delegation detail: {} ({} delegates)",
        delegation_id,
        len(delegates_data),
    )
    return render_template(
        "delegation_detail.html",
        delegation=delegation,
        delegates_data=delegates_data,
    )


@delegations_bp.route(
    "/delegations/<delegation_id>/delegates/new/step1",
    methods=["GET", "POST"],
)
def wizard_step1(delegation_id: str) -> Any:
    """Placeholder for wizard step 1 (implemented in Phase 2C)."""
    return "Not implemented", 501
