"""Quick diagnostic: run the brief and capture console + SSE traffic.

Why: prior run showed the backend executed 3 tools and the Next.js
proxy returned 200 after 18.4s, but the CopilotChat UI stayed in its
empty state. We need to know whether messages were appended to the
useAgent hook (console output) and what AG-UI events the proxy
forwarded (SSE body).
"""
from pathlib import Path

from playwright.sync_api import Page, Response


def test_debug_dump(page: Page, base_url: str) -> None:
    console_lines: list[str] = []
    page.on(
        "console",
        lambda msg: console_lines.append(f"{msg.type}: {msg.text}"),
    )
    page.on(
        "pageerror",
        lambda err: console_lines.append(f"pageerror: {err}"),
    )

    sse_bodies: list[tuple[str, str]] = []

    def on_response(resp: Response) -> None:
        url = resp.url
        if "/api/copilotkit/" not in url:
            return
        try:
            body = resp.text()
        except Exception as exc:  # noqa: BLE001
            body = f"<failed to read body: {exc}>"
        sse_bodies.append((url, body))

    page.on("response", on_response)

    page.goto(base_url)
    # Reason: backend tools ran in ~7s and stream returned after 18.4s;
    # 45s gives margin for slow LLM replies without doubling test time.
    page.wait_for_timeout(45_000)

    html = page.content()
    body_text = page.locator("body").inner_text()

    Path("/tmp/page_dump.html").write_text(html)
    Path("/tmp/page_text.txt").write_text(body_text)
    Path("/tmp/page_console.txt").write_text("\n".join(console_lines))

    sse_out = []
    for url, body in sse_bodies:
        sse_out.append(f"=== {url} ===\n{body}\n")
    Path("/tmp/page_sse.txt").write_text("\n".join(sse_out))

    print(f"\n=== VISIBLE TEXT ({len(body_text)} chars) ===")
    print(body_text[:2000])
    print(f"\n=== CONSOLE ({len(console_lines)} lines) ===")
    for line in console_lines[-60:]:
        print(line)
    print(f"\n=== SSE responses captured: {len(sse_bodies)} ===")
    for url, body in sse_bodies:
        print(f"  {url}  ({len(body)} chars)")
