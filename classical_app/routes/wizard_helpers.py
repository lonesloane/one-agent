"""
Pure helper functions for the add-delegate wizard.

Contains business-rule helpers and form-building utilities used by
``classical_app.routes.wizard``.  No Flask context required.
"""

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from classical_app.forms.delegate_wizard import Step3DARsForm
from shared.business_rules import (
    compute_default_access_level,
    determine_approval_route,
)
from shared.database import (
    ApprovalStatus,
    ClassificationLevel,
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
