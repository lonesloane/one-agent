"""
Wizard blueprint — add-delegate multi-step wizard routes for Phase 2C.

Provides stub route handlers for the six steps of the add-delegate
wizard: step1 through step4, confirmation, and cancel.
"""

from datetime import datetime, timezone
from typing import Any

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from loguru import logger
from sqlalchemy import func, select

from classical_app import wizard_state
from classical_app.forms.delegate_wizard import (
    Step1PersonalInfoForm,
    Step2CommitteesForm,
    Step3DARsForm,
)
from classical_app.permissions import editor_of_delegation_required
from shared.business_rules import compute_default_access_level
from shared.database import (
    ApprovalStatus,
    ClassificationLevel,
    Committee,
    Delegate,
    Delegation,
    MembershipType,
)


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


def _handle_step1_post(
    form: Step1PersonalInfoForm,
    db_session: Any,
    delegation_id: str,
) -> Any:
    """Process a valid Step 1 POST submission.

    Args:
        form: Validated Step1PersonalInfoForm instance.
        db_session: SQLAlchemy scoped session.
        delegation_id: Delegation identifier from the URL.

    Returns:
        Redirect to step 2, or re-rendered step1 on duplicate email.
    """
    if _email_exists_in_delegation(
        db_session, delegation_id, form.email.data
    ):
        logger.info(
            "Duplicate email rejected in step1: delegation={} email={}",
            delegation_id,
            form.email.data,
        )
        form.email.errors.append(
            "This email is already in use within this delegation."
        )
        return render_template(
            "wizard/step1.html", form=form, delegation_id=delegation_id
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
        "Wizard step1 complete; advancing to step2: delegation={}",
        delegation_id,
    )
    return redirect(
        url_for("wizard.wizard_step2", delegation_id=delegation_id)
    )


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step1",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step1(delegation_id: str) -> Any:
    """Handle step 1 of the add-delegate wizard.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        Rendered step1 template or a redirect to step 2.
    """
    db_session = current_app.extensions["db_session"]
    form = Step1PersonalInfoForm()

    if form.validate_on_submit():
        return _handle_step1_post(form, db_session, delegation_id)

    if not form.is_submitted():
        state = wizard_state.load(delegation_id)
        if state and "step1" in state:
            _prefill_step1_form(form, state)

    return render_template(
        "wizard/step1.html", form=form, delegation_id=delegation_id
    )


def _build_committee_choices(
    db_session: Any,
) -> list[tuple[str, str]]:
    """Query all committees ordered by name and return choice tuples.

    Args:
        db_session: SQLAlchemy scoped session.

    Returns:
        List of (id, name) tuples suitable for SelectMultipleField.
    """
    stmt = select(Committee).order_by(Committee.name)
    committees = db_session.scalars(stmt).all()
    return [(c.id, c.name) for c in committees]


def _prefill_step2_form(
    form: Step2CommitteesForm, state: dict
) -> None:
    """Pre-fill Step2CommitteesForm from saved wizard state.

    Args:
        form: The WTForms form instance to populate.
        state: Wizard session state dict for the delegation.
    """
    step2_data = state.get("step2", {})
    saved_ids = step2_data.get("committee_ids")
    if saved_ids:
        form.committee_ids.data = saved_ids


def _handle_step2_post(
    form: Step2CommitteesForm,
    delegation_id: str,
) -> Any:
    """Process Step 2 POST — save state and redirect or re-render.

    Args:
        form: Validated Step2CommitteesForm instance.
        delegation_id: Delegation identifier from the URL.

    Returns:
        Redirect to step 3 on valid submission, or re-rendered
        step2 template when validation fails.
    """
    if form.validate_on_submit():
        wizard_state.save(
            delegation_id,
            "step2",
            {"committee_ids": form.committee_ids.data},
        )
        logger.info(
            "Wizard step2 complete; advancing to step3:"
            " delegation={}",
            delegation_id,
        )
        return redirect(
            url_for(
                "wizard.wizard_step3",
                delegation_id=delegation_id,
            )
        )

    return render_template(
        "wizard/step2.html",
        form=form,
        delegation_id=delegation_id,
    )


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step2",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step2(delegation_id: str) -> Any:
    """Handle step 2 of the add-delegate wizard.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        Rendered step2 template or a redirect to step 3.
    """
    redirect_response = wizard_state.require_steps(
        delegation_id, ("step1",)
    )
    if redirect_response is not None:
        return redirect_response

    db_session = current_app.extensions["db_session"]
    choices = _build_committee_choices(db_session)

    form = Step2CommitteesForm()
    # Reason: choices must be set before validation for
    # SelectMultipleField to accept submitted values.
    form.committee_ids.choices = choices

    if form.is_submitted():
        return _handle_step2_post(form, delegation_id)

    state = wizard_state.load(delegation_id)
    if state:
        _prefill_step2_form(form, state)

    return render_template(
        "wizard/step2.html",
        form=form,
        delegation_id=delegation_id,
    )


def _allowed_levels(
    delegation: Delegation, committee_id: str
) -> list[ClassificationLevel]:
    """Return permitted classification levels for one DAR row.

    MEMBER or PARTNER with active FA → [GENERAL, RESTRICTED,
    CONFIDENTIAL].  PARTNER without active FA → [GENERAL, CONFIDENTIAL].

    Args:
        delegation: Delegation ORM object (framework_agreements loaded).
        committee_id: Committee ID to check active FA coverage for.

    Returns:
        List of ClassificationLevel values the user may select.
    """
    full_range = [
        ClassificationLevel.GENERAL,
        ClassificationLevel.RESTRICTED,
        ClassificationLevel.CONFIDENTIAL,
    ]
    restricted_range = [
        ClassificationLevel.GENERAL,
        ClassificationLevel.CONFIDENTIAL,
    ]

    if delegation.membership_type == MembershipType.MEMBER:
        return full_range

    # Reason: reuse the same active-FA logic as business_rules.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for fa in delegation.framework_agreements:
        if fa.committee_id == committee_id:
            if fa.end_date is None or fa.end_date > now:
                return full_range

    return restricted_range


def _apply_dar_row_override(
    row_entry: Any,
    saved: dict,
    default_level: ClassificationLevel,
) -> None:
    """Apply saved session override to a DAR row entry.

    Args:
        row_entry: The WTForms FormField entry to update.
        saved: Dict with optional 'access_level' and 'retroactive'.
        default_level: Default ClassificationLevel used as fallback.
    """
    row_entry.access_level.data = saved.get(
        "access_level", default_level.value
    )
    row_entry.retroactive.data = saved.get("retroactive", False)


def _build_step3_form(
    delegation: Delegation,
    committee_ids: list[str],
    committee_map: dict[str, str],
    state: dict,
) -> tuple[Step3DARsForm, list[str]]:
    """Build Step3DARsForm with choices and session overrides.

    Args:
        delegation: Delegation ORM object for membership/FA checks.
        committee_ids: Ordered list of committee IDs from step 2.
        committee_map: Mapping of committee_id → committee name.
        state: Full wizard session state dict for the delegation.

    Returns:
        Tuple of (populated Step3DARsForm, parallel list of labels).
    """
    form = Step3DARsForm()
    saved_rows = state.get("step3", {}).get("rows", [])
    row_labels: list[str] = []

    for i, committee_id in enumerate(committee_ids):
        allowed = _allowed_levels(delegation, committee_id)
        default = compute_default_access_level(
            delegation.membership_type,
            committee_id,
            delegation.framework_agreements,
        )
        form.rows.append_entry(
            {
                "committee_id": committee_id,
                "access_level": default.value,
                "retroactive": False,
            }
        )
        row_entry = form.rows[-1]
        row_entry.access_level.choices = [
            (lvl.value, lvl.value.capitalize()) for lvl in allowed
        ]
        if i < len(saved_rows):
            _apply_dar_row_override(row_entry, saved_rows[i], default)
        row_labels.append(committee_map[committee_id])

    return form, row_labels


def _handle_step3_post(delegation_id: str) -> Any:
    """Read raw POST data, save step3 state, and redirect to step4.

    WTForms FieldList with FormField does not validate reliably for
    this use case, so raw request.form values are read directly.
    The access_level values are valid because choices are fixed enum
    values enforced at the HTML level.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        Redirect response to wizard step 4.
    """
    state = wizard_state.load(delegation_id) or {}
    committee_ids = state.get("step2", {}).get("committee_ids", [])

    rows_data = []
    for i, committee_id in enumerate(committee_ids):
        rows_data.append(
            {
                "committee_id": request.form.get(
                    f"rows-{i}-committee_id", committee_id
                ),
                "access_level": request.form.get(
                    f"rows-{i}-access_level"
                ),
                "retroactive": (
                    f"rows-{i}-retroactive" in request.form
                ),
            }
        )

    wizard_state.save(delegation_id, "step3", {"rows": rows_data})
    logger.info(
        "Wizard step3 complete; advancing to step4: delegation={}",
        delegation_id,
    )
    return redirect(
        url_for("wizard.wizard_step4", delegation_id=delegation_id)
    )


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step3",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step3(delegation_id: str) -> Any:
    """Handle step 3 of the add-delegate wizard.

    Builds a dynamic table of document access right rows, one per
    committee selected in step 2.  GET renders the form with default
    access levels and any session-saved overrides.  POST reads raw
    form data, saves it to the session, and redirects to step 4.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        Rendered step3 template on GET, or redirect to step 4 on POST.
    """
    redirect_response = wizard_state.require_steps(
        delegation_id, ("step1", "step2")
    )
    if redirect_response is not None:
        return redirect_response

    if request.method == "POST":
        return _handle_step3_post(delegation_id)

    db_session = current_app.extensions["db_session"]
    state = wizard_state.load(delegation_id) or {}
    committee_ids = state.get("step2", {}).get("committee_ids", [])

    delegation = db_session.scalars(
        select(Delegation).where(Delegation.id == delegation_id)
    ).first()

    committees = db_session.scalars(
        select(Committee).where(
            Committee.id.in_(committee_ids)
        )
    ).all()
    committee_map = {c.id: c.name for c in committees}

    form, row_labels = _build_step3_form(
        delegation, committee_ids, committee_map, state
    )

    return render_template(
        "wizard/step3.html",
        form=form,
        delegation_id=delegation_id,
        row_labels=row_labels,
    )


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
