"""Scenario C: RESTRICTED access level routes to PENDING_DELEGATION_HEAD."""
from sqlalchemy.orm import Session

from shared.database import ApprovalStatus, Delegate, DocumentAccessRight


def test_scenario_c_pending_delegation_head(
    page, base_url, login_as, e2e_engine
):
    """
    Wizard with RESTRICTED/non-retroactive produces PENDING_DELEGATION_HEAD DARs.

    Drives the full wizard (steps 1–4) for Claire Morel with RESTRICTED
    access on EDU and TRADE, then asserts both DAR rows carry
    PENDING_DELEGATION_HEAD status.
    """
    login_as(page, "DEL-2026-0001")

    # ── Step 1 ────────────────────────────────────────────────────────────
    page.goto(f"{base_url}/delegations/FRA/delegates/new/step1")
    page.fill("input[name='full_name']", "Claire Morel")
    page.fill("input[name='email']", "claire.morel@example.com")
    page.fill("input[name='function']", "Delegate")
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step2")

    # ── Step 2: select EDU and TRADE ─────────────────────────────────────
    page.check("input[name='committee_ids'][value='EDU']")
    page.check("input[name='committee_ids'][value='TRADE']")
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step3")

    # ── Step 3: RESTRICTED, non-retroactive ──────────────────────────────
    for i in range(2):
        page.select_option(
            f"select[name='rows-{i}-access_level']", "RESTRICTED"
        )
        page.uncheck(f"input[name='rows-{i}-retroactive']")
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step4")

    # ── Step 4: submit ────────────────────────────────────────────────────
    page.click("button.btn-success")
    page.wait_for_load_state("networkidle")
    assert "confirmation" in page.url
    assert "Claire Morel" in page.content()

    # ── DB assertions ─────────────────────────────────────────────────────
    with Session(e2e_engine) as session:
        delegates = (
            session.query(Delegate)
            .filter(Delegate.full_name == "Claire Morel")
            .all()
        )
        assert len(delegates) == 1, (
            f"Expected 1 Delegate 'Claire Morel', got {len(delegates)}"
        )
        dars = (
            session.query(DocumentAccessRight)
            .filter(
                DocumentAccessRight.delegate_id == delegates[0].id
            )
            .all()
        )
        assert len(dars) == 2, (
            f"Expected 2 DARs for Claire Morel, got {len(dars)}"
        )
        for dar in dars:
            assert (
                dar.approval_status
                == ApprovalStatus.PENDING_DELEGATION_HEAD
            ), (
                f"Expected PENDING_DELEGATION_HEAD, got {dar.approval_status}"
            )
