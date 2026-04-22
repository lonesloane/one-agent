"""Phase 1 smoke test: unauthenticated GET / redirects to /switch-delegate."""


def test_unauthenticated_redirect_to_switch_delegate(page, base_url):
    """Verify that an unauthenticated GET / ends up at /switch-delegate."""
    page.goto(f"{base_url}/")
    assert page.url.endswith("/switch-delegate")
