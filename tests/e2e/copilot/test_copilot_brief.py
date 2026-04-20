"""Browser tests verifying CopilotKit brief firing, suppression,
persona switch, and tool call rendering."""

import re

from playwright.sync_api import Page


def test_brief_fires_on_session_open(page: Page, base_url: str) -> None:
    """Assert that the agent brief fires when a session is opened.

    Navigates to the app, which auto-selects the first delegate (Ana
    Souza, EDU committee member), then waits for the fresh test
    document title to appear in the chat response.
    """
    page.goto(base_url)
    page.get_by_text("E2E Test Policy Draft").wait_for(timeout=90_000)
    assert page.get_by_text("E2E Test Policy Draft").first.is_visible()


def test_brief_suppressed_no_new_docs(page: Page, base_url: str) -> None:
    """Verify brief is suppressed for a delegate with no new documents.

    DEL-2026-0007 (Priya Sharma, IND) is not in EDU, so the fresh
    EDU test document should not appear in her brief.
    """
    page.goto(base_url)
    # Switch quickly before any brief starts streaming.
    page.wait_for_selector("select:not([disabled])", timeout=10_000)
    page.select_option("select", value="DEL-2026-0007")
    page.locator("[class*='message']").filter(
        has_text=re.compile(".+")
    ).first.wait_for(timeout=90_000)
    assert page.get_by_text("E2E Test Policy Draft").count() == 0


def test_persona_switch_resets_thread(page: Page, base_url: str) -> None:
    """Assert that switching personas clears the previous thread.

    Loads the first delegate's brief (EDU member), then switches to
    Priya Sharma and verifies the new thread does not carry over the
    previous delegate's brief content.
    """
    page.goto(base_url)
    page.get_by_text("E2E Test Policy Draft").wait_for(timeout=90_000)

    page.select_option("select", value="DEL-2026-0007")

    # Wait for previous thread to clear before checking new thread.
    page.get_by_text("E2E Test Policy Draft").wait_for(
        state="hidden", timeout=30_000
    )

    page.locator("[class*='message']").filter(
        has_text=re.compile(".+")
    ).first.wait_for(timeout=90_000)

    assert page.get_by_text("E2E Test Policy Draft").count() == 0


def test_tool_call_blocks_visible(page: Page, base_url: str) -> None:
    """Assert that at least one tool call block renders after the brief.

    Navigates to the app with the auto-selected EDU delegate and waits
    for the brief to complete, then confirms a details element (tool
    call block) is present in the DOM.
    """
    page.goto(base_url)
    page.get_by_text("E2E Test Policy Draft").wait_for(timeout=90_000)
    assert page.locator("details").count() >= 1
