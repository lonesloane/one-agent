"""Scenario F: cancel and session-clear behaviour for the wizard."""


def test_f1_cancel_from_step3_redirects_to_delegation(
    page, base_url, login_as
):
    """
    Clicking Cancel on step 3 redirects to the FRA delegation page.

    After completing steps 1 and 2, the Cancel button on step 3 should
    POST to the cancel route which clears wizard state and redirects to
    the delegation detail page.
    """
    login_as(page, "DEL-2026-0001")

    # Step 1
    page.goto(f"{base_url}/delegations/FRA/delegates/new/step1")
    page.fill("input[name='full_name']", "Test Cancel")
    page.fill("input[name='email']", "test.cancel@example.com")
    page.fill("input[name='function']", "Analyst")
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step2")

    # Step 2
    page.check("input[name='committee_ids'][value='EDU']")
    page.click("button.btn-primary")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step3")

    # Cancel on step 3 via the Cancel button
    page.click("button.btn-outline-secondary:has-text('Cancel')")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("/delegations/FRA")


def test_f2_direct_navigation_to_step3_redirects_to_step1(
    page, base_url, login_as
):
    """
    Navigating directly to step3 without state redirects to step1.

    After a cancel (or a fresh session), wizard state for FRA is cleared.
    The require_steps guard on step3 must redirect back to step1 when
    steps 1 and 2 have not been completed.
    """
    login_as(page, "DEL-2026-0001")
    page.goto(
        f"{base_url}/delegations/FRA/delegates/new/step3"
    )
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("step1"), (
        f"Expected redirect to step1, got {page.url}"
    )
