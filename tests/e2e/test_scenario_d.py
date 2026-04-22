"""Scenario D: retroactive access always routes to PENDING_SECRETARIAT."""
from sqlalchemy.orm import Session

from shared.database import ApprovalStatus, Delegate, DocumentAccessRight


def test_scenario_d_retroactive_override(page, base_url, login_as, e2e_engine):
    """
    Retroactive GENERAL access produces PENDING_SECRETARIAT DARs.

    Even though GENERAL is normally auto-approved, retroactive access
    always escalates to secretariat review. Drives the full wizard
    (steps 1–4) for Denis Fontaine with GENERAL+retroactive on both
    committees, then asserts both DARs carry PENDING_SECRETARIAT status.
    """
    login_as(page, "DEL-2026-0001")

    # ── Step 1 ────────────────────────────────────────────────────────────
    page.goto(f"{base_url}/delegations/FRA/delegates/new/step1")
    page.fill("input[name='full_name']", "Denis Fontaine")
    page.fill("input[name='email']", "denis.fontaine@example.com")
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

    # ── Step 3: GENERAL, retroactive on both rows ─────────────────────────
    for i in range(2):
        page.select_option(
            f"select[name='rows-{i}-access_level']", "GENERAL"
        )
        page.check(f"input[name='rows-{i}-retroactive']")
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step4")

    # ── Step 4: submit ────────────────────────────────────────────────────
    page.click("button.btn-success")
    page.wait_for_load_state("networkidle")
    assert "confirmation" in page.url
    assert "Denis Fontaine" in page.content()

    # ── DB assertions ─────────────────────────────────────────────────────
    with Session(e2e_engine) as session:
        delegates = (
            session.query(Delegate)
            .filter(Delegate.full_name == "Denis Fontaine")
            .all()
        )
        assert len(delegates) == 1, (
            f"Expected 1 Delegate 'Denis Fontaine', got {len(delegates)}"
        )
        dars = (
            session.query(DocumentAccessRight)
            .filter(
                DocumentAccessRight.delegate_id == delegates[0].id
            )
            .all()
        )
        assert len(dars) == 2, (
            f"Expected 2 DARs for Denis Fontaine, got {len(dars)}"
        )
        for dar in dars:
            assert dar.approval_status == ApprovalStatus.PENDING_SECRETARIAT, (
                f"Expected PENDING_SECRETARIAT, got {dar.approval_status}"
            )
