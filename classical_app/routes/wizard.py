"""
Wizard blueprint — add-delegate multi-step wizard routes for Phase 2C.

Provides stub route handlers for the six steps of the add-delegate
wizard: step1 through step4, confirmation, and cancel.
"""

from typing import Any

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    url_for,
)
from loguru import logger
from sqlalchemy import func, select

from classical_app import wizard_state
from classical_app.forms.delegate_wizard import Step1PersonalInfoForm
from classical_app.permissions import editor_of_delegation_required
from shared.database import ApprovalStatus, Delegate


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


def _prefill_step1_form(
    form: Step1PersonalInfoForm, state: dict
) -> None:
    """Pre-fill Step1PersonalInfoForm from saved wizard state.

    Args:
        form: The WTForms form instance to populate.
        state: Wizard session state dict for the delegation.
    """
    step1_data = state.get("step1", {})
    form.full_name.data = step1_data.get("full_name", "")
    form.email.data = step1_data.get("email", "")
    form.function.data = step1_data.get("function", "")
    form.title.data = step1_data.get("title", "")


def _email_exists_in_delegation(
    db_session: Any, delegation_id: str, email: str
) -> bool:
    """Check whether an email is already used in a delegation.

    Args:
        db_session: SQLAlchemy scoped session.
        delegation_id: Delegation to search within.
        email: Email address to check (case-insensitive).

    Returns:
        True if a delegate with that email exists, False otherwise.
    """
    stmt = select(Delegate).where(
        Delegate.delegation_id == delegation_id,
        func.lower(Delegate.email) == email.lower(),
    )
    return db_session.scalars(stmt).first() is not None


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step1",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step1(delegation_id: str) -> Any:
    """Handle step 1 of the add-delegate wizard.

    GET: Render the personal info form, pre-filling from session if
    a draft already exists for this delegation.

    POST: Validate the form, check email uniqueness within the
    delegation, save step data to the wizard session, and redirect
    to step 2.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        Rendered step1 template or a redirect to step 2.
    """
    db_session = current_app.extensions["db_session"]
    form = Step1PersonalInfoForm()

    if form.validate_on_submit():
        if _email_exists_in_delegation(
            db_session, delegation_id, form.email.data
        ):
            logger.info(
                "Duplicate email rejected in step1:"
                " delegation={} email={}",
                delegation_id,
                form.email.data,
            )
            form.email.errors.append(
                "This email is already in use within this delegation."
            )
            return render_template(
                "wizard/step1.html",
                form=form,
                delegation_id=delegation_id,
            )

        wizard_state.save(
            delegation_id,
            "step1",
            {
                "full_name": form.full_name.data,
                "email": form.email.data,
                "function": form.function.data,
                "title": form.title.data,
            },
        )
        logger.info(
            "Wizard step1 complete; advancing to step2:"
            " delegation={}",
            delegation_id,
        )
        return redirect(
            url_for("wizard.wizard_step2", delegation_id=delegation_id)
        )

    # GET or failed validation — pre-fill from session on GET only.
    if not form.is_submitted():
        state = wizard_state.load(delegation_id)
        if state and "step1" in state:
            _prefill_step1_form(form, state)

    return render_template(
        "wizard/step1.html",
        form=form,
        delegation_id=delegation_id,
    )


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
