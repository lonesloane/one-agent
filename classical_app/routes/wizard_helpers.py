"""
Helper functions for the add-delegate wizard.

Contains business-rule helpers, form-building utilities, and the
submit transaction helper used by ``classical_app.routes.wizard``.
"""

import flask
from datetime import datetime, timezone
from typing import Any

from flask import flash, redirect, render_template, url_for
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from classical_app.forms.delegate_wizard import Step3DARsForm, Step4ReviewForm
from shared.business_rules import (
    compute_default_access_level,
    determine_approval_route,
)
from shared.database import (
    ApprovalStatus,
    ClassificationLevel,
    Committee,
    Delegate,
    DelegateRole,
    Delegation,
    DocumentAccessRight,
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

    # Reason: end_date stored as naive UTC; compare against naive now.
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
        committee_map: Mapping of committee_id to committee name.
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


def _build_review_rows(
    state: dict, committee_map: dict[str, str]
) -> list[dict]:
    """Build review rows for the step 4 template.

    For each DAR row in step3 state, resolve the approval route and
    return a list of dicts suitable for the step4.html template.

    Args:
        state: Full wizard session state dict for the delegation.
        committee_map: Mapping of committee_id to committee name.

    Returns:
        List of dicts with keys: committee_name, level, retroactive,
        status_label.
    """
    rows = []
    for row in state.get("step3", {}).get("rows", []):
        try:
            level = ClassificationLevel(row["access_level"])
        except ValueError:
            logger.warning(
                "Invalid access_level '{}' in session; defaulting "
                "to GENERAL",
                row.get("access_level"),
            )
            level = ClassificationLevel.GENERAL
        route = determine_approval_route(level, row["retroactive"])
        rows.append(
            {
                "committee_name": committee_map.get(
                    row["committee_id"], row["committee_id"]
                ),
                "level": row["access_level"],
                "retroactive": row["retroactive"],
                "status_label": APPROVAL_LABELS.get(
                    route.value, route.value
                ),
            }
        )
    return rows


def _generate_delegate_id(db_session: Any) -> str:
    """Generate the next delegate ID in DEL-YYYY-NNNN format.

    Scans all existing delegate IDs, extracts the numeric sequence,
    and returns one more than the current maximum.

    Args:
        db_session: SQLAlchemy scoped session.

    Returns:
        New delegate ID string, e.g. ``"DEL-2026-0042"``.
    """
    all_ids = db_session.scalars(select(Delegate.id)).all()
    max_seq = 0
    for did in all_ids:
        parts = did.split("-")
        if len(parts) == 3 and parts[0] == "DEL":
            try:
                max_seq = max(max_seq, int(parts[2]))
            except ValueError:
                pass
    year = datetime.now(timezone.utc).year
    return f"DEL-{year}-{max_seq + 1:04d}"


def _build_delegate(
    step1: dict,
    delegation_id: str,
    new_id: str,
    now: datetime,
) -> Delegate:
    """Construct a Delegate ORM object from step1 wizard state.

    Args:
        step1: Step 1 wizard state dict (full_name, email, etc.)
        delegation_id: Delegation this delegate belongs to.
        new_id: Pre-generated unique delegate ID.
        now: Current UTC timestamp (naive) for accreditation_date.

    Returns:
        Unsaved Delegate instance ready for db_session.add().
    """
    return Delegate(
        id=new_id,
        full_name=step1["full_name"],
        email=step1["email"],
        function=step1["function"],
        title=step1.get("title") or None,
        delegation_id=delegation_id,
        accreditation_date=now,
        is_active=True,
        role=DelegateRole.DELEGATE,
    )


def _build_dars(
    delegate_id: str,
    step3_rows: list[dict],
    now: datetime,
    created_by: str,
) -> list[DocumentAccessRight]:
    """Build DocumentAccessRight objects from step3 wizard rows.

    Args:
        delegate_id: ID of the delegate being created.
        step3_rows: List of dicts with committee_id, access_level,
            retroactive.
        now: Current UTC timestamp (naive) for created_at.
        created_by: Session user ID for audit trail.

    Returns:
        List of unsaved DocumentAccessRight instances.
    """
    dars = []
    for row in step3_rows:
        level = ClassificationLevel(row["access_level"])
        status = determine_approval_route(level, row["retroactive"])
        dars.append(DocumentAccessRight(
            delegate_id=delegate_id,
            committee_id=row["committee_id"],
            classification_level=level,
            retroactive=row["retroactive"],
            approval_status=status,
            created_at=now,
            created_by=created_by,
        ))
    return dars


def _handle_step4_post(
    delegation_id: str,
    db_session: Any,
    state: dict,
) -> Any:
    """Execute single-transaction delegate creation on step 4 POST.

    Reads wizard state, creates a ``Delegate`` record with committees
    and ``DocumentAccessRight`` rows, commits in a single transaction,
    then stores the created delegate ID in session and clears wizard
    state.  On commit failure, rolls back and re-renders step 4 with
    a flash error message.

    Args:
        delegation_id: Delegation identifier from the URL.
        db_session: SQLAlchemy scoped session.
        state: Full wizard state dict for the delegation.

    Returns:
        Redirect to confirmation on success, or re-rendered step4
        template on commit failure.
    """
    from classical_app import wizard_state  # avoid circular import

    step1 = state.get("step1", {})
    step3_rows = state.get("step3", {}).get("rows", [])

    new_id = _generate_delegate_id(db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    current_user = flask.session.get("delegate_id", "system")

    delegate = _build_delegate(step1, delegation_id, new_id, now)

    committee_ids = [r["committee_id"] for r in step3_rows]
    committees = db_session.scalars(
        select(Committee).where(Committee.id.in_(committee_ids))
    ).all()
    delegate.committees = list(committees)

    dars = _build_dars(new_id, step3_rows, now, current_user)

    try:
        db_session.add(delegate)
        for dar in dars:
            db_session.add(dar)
        db_session.commit()
    except SQLAlchemyError as exc:
        db_session.rollback()
        logger.error(
            "Wizard step4 commit failed: delegation={} error={}",
            delegation_id,
            exc,
        )
        flash(
            "An error occurred while saving. Please try again.",
            "danger",
        )
        committee_map = {c.id: c.name for c in committees}
        review_rows = _build_review_rows(state, committee_map)
        return render_template(
            "wizard/step4.html",
            form=Step4ReviewForm(),
            delegation_id=delegation_id,
            review_rows=review_rows,
        )

    wizard_state.set_created_delegate_id(delegation_id, delegate.id)
    wizard_state.clear(delegation_id)
    logger.info(
        "Delegate created: id={} delegation={}",
        delegate.id,
        delegation_id,
    )
    return redirect(
        url_for(
            "wizard.wizard_confirmation",
            delegation_id=delegation_id,
        )
    )
