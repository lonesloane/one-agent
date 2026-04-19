"""
Wizard blueprint — add-delegate multi-step wizard routes for Phase 2C.

Provides route handlers for the six steps of the add-delegate wizard:
step1 through step4, confirmation, and cancel.
"""

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
    Step4ReviewForm,
)
from classical_app.permissions import editor_of_delegation_required
from classical_app.routes.wizard_helpers import (
    APPROVAL_LABELS,  # noqa: F401 (re-exported for templates/callers)
    _build_review_rows,
    _build_step3_form,
    _handle_step4_post,
)
from shared.database import (
    ClassificationLevel,
    Committee,
    Delegate,
    Delegation,
    DocumentAccessRight,
)


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


def _handle_step3_post(delegation_id: str) -> Any:
    """Read raw POST data, save step3 state, and redirect to step4.

    WTForms FieldList with FormField does not validate reliably for
    this use case, so raw request.form values are read directly.
    Access level values are server-side validated against the enum.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        Redirect response to wizard step 4.
    """
    state = wizard_state.load(delegation_id) or {}
    committee_ids = state.get("step2", {}).get("committee_ids", [])
    valid_levels = {lvl.value for lvl in ClassificationLevel}

    rows_data = []
    for i, committee_id in enumerate(committee_ids):
        submitted_level = request.form.get(
            f"rows-{i}-access_level", ClassificationLevel.GENERAL.value
        )
        if submitted_level not in valid_levels:
            submitted_level = ClassificationLevel.GENERAL.value
        rows_data.append(
            {
                "committee_id": request.form.get(
                    f"rows-{i}-committee_id", committee_id
                ),
                "access_level": submitted_level,
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
        select(Committee).where(Committee.id.in_(committee_ids))
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


def _build_step4_context(
    delegation_id: str, db_session: Any
) -> tuple[Any, list[dict]]:
    """Load committee map and review rows for the step 4 GET render.

    Args:
        delegation_id: Delegation identifier from the URL.
        db_session: SQLAlchemy scoped session.

    Returns:
        Tuple of (Step4ReviewForm instance, list of review_row dicts).
    """
    state = wizard_state.load(delegation_id) or {}
    committee_ids = [
        r["committee_id"]
        for r in state.get("step3", {}).get("rows", [])
    ]
    committees = db_session.scalars(
        select(Committee).where(Committee.id.in_(committee_ids))
    ).all()
    committee_map = {c.id: c.name for c in committees}
    return Step4ReviewForm(), _build_review_rows(state, committee_map)


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/step4",
    methods=["GET", "POST"],
)
@editor_of_delegation_required()
def wizard_step4(delegation_id: str) -> Any:
    """Handle step 4 of the add-delegate wizard.

    GET renders the review table showing approval routing per DAR row.
    POST creates the Delegate and DocumentAccessRight records in a
    single transaction via ``_handle_step4_post``.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        On GET: rendered step4 template with review rows.
        On POST: redirect to confirmation on success, or re-rendered
        step4 with flash error on commit failure.
    """
    redirect_response = wizard_state.require_steps(
        delegation_id, ("step1", "step2", "step3")
    )
    if redirect_response is not None:
        return redirect_response

    db_session = current_app.extensions["db_session"]

    if request.method == "POST":
        state = wizard_state.load(delegation_id) or {}
        return _handle_step4_post(delegation_id, db_session, state)

    form, review_rows = _build_step4_context(delegation_id, db_session)
    logger.info(
        "Rendering wizard step4 review: delegation={} rows={}",
        delegation_id,
        len(review_rows),
    )
    return render_template(
        "wizard/step4.html",
        form=form,
        delegation_id=delegation_id,
        review_rows=review_rows,
    )


def _build_dar_rows(
    dars: list[DocumentAccessRight],
    db_session: Any,
) -> list[dict]:
    """Build display rows for document-access-right entries.

    Args:
        dars: DocumentAccessRight ORM objects for a delegate.
        db_session: Active SQLAlchemy session.

    Returns:
        List of dicts with keys committee_name, level,
        retroactive, and status_label.
    """
    committee_ids = [d.committee_id for d in dars]
    committees = db_session.scalars(
        select(Committee).where(Committee.id.in_(committee_ids))
    ).all()
    committee_map = {c.id: c.name for c in committees}
    return [
        {
            "committee_name": committee_map.get(
                dar.committee_id, dar.committee_id
            ),
            "level": dar.classification_level.value,
            "retroactive": dar.retroactive,
            "status_label": APPROVAL_LABELS.get(
                dar.approval_status.value,
                dar.approval_status.value,
            ),
        }
        for dar in dars
    ]


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/confirmation",
    methods=["GET"],
)
@editor_of_delegation_required()
def wizard_confirmation(delegation_id: str) -> Any:
    """Render the confirmation page after completing the wizard.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        Rendered confirmation template, or redirect to delegation
        detail when the created-delegate ID is missing or stale.
    """
    detail_url = url_for(
        "delegations.delegation_detail",
        delegation_id=delegation_id,
    )
    delegate_id = wizard_state.get_created_delegate_id(delegation_id)
    if delegate_id is None:
        logger.warning(
            "No created delegate in wizard state: delegation={}",
            delegation_id,
        )
        return redirect(detail_url)

    db_session = current_app.extensions["db_session"]
    delegate = db_session.scalars(
        select(Delegate).where(Delegate.id == delegate_id)
    ).first()
    if delegate is None:
        logger.warning(
            "Delegate not found: delegate={} delegation={}",
            delegate_id,
            delegation_id,
        )
        return redirect(detail_url)

    dars = db_session.scalars(
        select(DocumentAccessRight).where(
            DocumentAccessRight.delegate_id == delegate_id
        )
    ).all()
    dar_rows = _build_dar_rows(dars, db_session)
    logger.info(
        "Rendering wizard confirmation: delegation={} delegate={}",
        delegation_id,
        delegate_id,
    )
    return render_template(
        "wizard/confirmation.html",
        delegate=delegate,
        dar_rows=dar_rows,
        delegation_id=delegation_id,
    )


@wizard_bp.route(
    "/delegations/<delegation_id>/delegates/new/cancel",
    methods=["POST"],
)
@editor_of_delegation_required()
def wizard_cancel(delegation_id: str) -> Any:
    """Cancel the add-delegate wizard and discard draft state.

    Args:
        delegation_id: Delegation identifier from the URL.

    Returns:
        Redirect to the delegation detail page.
    """
    wizard_state.clear(delegation_id)
    logger.info("Wizard cancelled: delegation={}", delegation_id)
    return redirect(
        url_for(
            "delegations.delegation_detail",
            delegation_id=delegation_id,
        )
    )
