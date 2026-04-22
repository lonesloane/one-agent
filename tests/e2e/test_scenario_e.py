"""Scenario E: permission gates for the Add New Delegate wizard."""


def test_e1_add_delegate_button_hidden_for_non_editor(
    page, base_url, login_as
):
    """
    Non-editor (Jean Martin) sees no 'Add New Delegate' button on FRA page.

    The button is wrapped in an is_editor_of_delegation() guard in the
    template; a DELEGATE-role user must not see it.
    """
    login_as(page, "DEL-2026-0002")
    page.goto(f"{base_url}/delegations/FRA")
    page.wait_for_load_state("networkidle")
    add_btn = page.locator("a.btn-success", has_text="Add New Delegate")
    assert add_btn.count() == 0


def test_e2_direct_post_forbidden_for_non_editor(
    page, base_url, login_as
):
    """
    Non-editor (Jean Martin) receives 403 on a direct POST to step1.

    page.request shares session cookies with the browser context so the
    delegate_id session variable set by login_as is forwarded automatically.
    """
    login_as(page, "DEL-2026-0002")
    response = page.request.post(
        f"{base_url}/delegations/FRA/delegates/new/step1",
        form={"full_name": "X"},
    )
    assert response.status == 403, (
        f"Expected 403, got {response.status}"
    )


def test_e3_direct_post_forbidden_for_editor_of_other_delegation(
    page, base_url, login_as
):
    """
    Editor of BRA (Carlos Silva) receives 403 on a direct POST to FRA step1.

    Being an editor of one delegation does not grant access to another.
    """
    login_as(page, "DEL-2026-0005")
    response = page.request.post(
        f"{base_url}/delegations/FRA/delegates/new/step1",
        form={"full_name": "X"},
    )
    assert response.status == 403, (
        f"Expected 403, got {response.status}"
    )
