"""Scenario A: full wizard flow producing AUTO_APPROVED DARs."""
import pytest
from sqlalchemy.orm import Session

from shared.database import ApprovalStatus, Delegate, DocumentAccessRight


def test_scenario_a_auto_approved(page, base_url, login_as, e2e_engine):
    """
    Complete wizard for a GENERAL/non-retroactive delegate on FRA.

    Asserts that the confirmation page renders correctly and that the
    database contains exactly one new Delegate row (Alice Leblanc) with
    two DocumentAccessRight rows both carrying AUTO_APPROVED status.
    """
    login_as(page, "DEL-2026-0001")

    # ── Step 1: personal information ────────────────────────────────────
    page.goto(f"{base_url}/delegations/FRA/delegates/new/step1")
    page.fill("input[name='full_name']", "Alice Leblanc")
    page.fill("input[name='email']", "alice.leblanc@example.com")
    page.fill("input[name='function']", "Policy Analyst")
    page.fill("input[name='title']", "Ms")
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step2")

    # ── Step 2: select EDU and TRADE committees ──────────────────────────
    page.check("input[name='committee_ids'][value='EDU']")
    page.check("input[name='committee_ids'][value='TRADE']")
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step3")

    # ── Step 3: set both rows to GENERAL, leave retroactive unchecked ───
    page.select_option(
        "select[name='rows-0-access_level']", "GENERAL"
    )
    page.select_option(
        "select[name='rows-1-access_level']", "GENERAL"
    )
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step4")

    # ── Step 4: verify review table and submit ───────────────────────────
    general_cells = page.locator("td", has_text="GENERAL")
    assert general_cells.count() == 2
    no_retroactive = page.locator(".text-muted", has_text="No")
    assert no_retroactive.count() >= 2

    page.click("button.btn-success")
    page.wait_for_load_state("networkidle")
    assert "confirmation" in page.url
    assert "Alice Leblanc" in page.content()

    # ── DB assertions ────────────────────────────────────────────────────
    with Session(e2e_engine) as session:
        delegates = (
            session.query(Delegate)
            .filter(Delegate.full_name == "Alice Leblanc")
            .all()
        )
        assert len(delegates) == 1, (
            f"Expected 1 Delegate 'Alice Leblanc', got {len(delegates)}"
        )
        delegate = delegates[0]

        dars = (
            session.query(DocumentAccessRight)
            .filter(
                DocumentAccessRight.delegate_id == delegate.id
            )
            .all()
        )
        assert len(dars) == 2, (
            f"Expected 2 DARs for Alice Leblanc, got {len(dars)}"
        )
        for dar in dars:
            assert dar.approval_status == ApprovalStatus.AUTO_APPROVED, (
                f"Expected AUTO_APPROVED, got {dar.approval_status}"
            )
