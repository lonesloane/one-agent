"""Spike C2 client — Python terminal driver against AG-UI server.

Uses AGUIChatClient + Agent with a client-side `request_approval` tool.
The MS Agent Framework hybrid-execution model delegates approval
rendering to the client by emitting a tool call named `request_approval`;
the local tool returns `{"accepted": bool}` and the server unwraps it
back into the agent loop.

Run (server in another terminal first):
    .venv/bin/python -m spikes.c2_custom_agui.client
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_framework import Agent, tool  # noqa: E402
from agent_framework_ag_ui import AGUIChatClient  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from pydantic import Field  # noqa: E402

load_dotenv()

SERVER_URL = os.environ.get("AGUI_SERVER_URL", "http://127.0.0.1:8888/")


async def _prompt_user(message: str) -> bool:
    """Block on terminal input for an approve/deny decision."""
    while True:
        choice = await asyncio.to_thread(input, f"\n{message} (y/n): ")
        c = choice.strip().lower()
        if c in {"y", "yes"}:
            return True
        if c in {"n", "no"}:
            return False
        print("Please enter y or n.")


@tool
async def request_approval(
    request: Annotated[
        str,
        Field(description="JSON-encoded approval request payload"),
    ],
) -> str:
    """Render an approval prompt and return the user's decision.

    Called by the AG-UI server when its agent invokes a function
    decorated with `@tool(approval_mode="always_require")`. The
    `request` argument is a JSON blob containing approvalId,
    functionName, functionArguments, message. Return value: JSON with
    key `accepted` (bool); the server unwraps it into a
    function_approval_response back to its agent.
    """
    try:
        payload: dict[str, Any] = json.loads(request)
    except json.JSONDecodeError:
        payload = {"functionName": "<unknown>", "raw": request}

    func_name = payload.get("functionName", "<unknown>")
    func_args = payload.get("functionArguments", {})
    message = payload.get("message", f"Approve execution of '{func_name}'?")

    print()
    print("=" * 60)
    print("APPROVAL REQUIRED")
    print("=" * 60)
    print(f"Tool: {func_name}")
    print(f"Arguments: {func_args}")
    print("=" * 60)

    approved = await _prompt_user(message)
    response = {
        "accepted": approved,
        "approvalId": payload.get("approvalId"),
    }
    print(f"[Sending approval: {'APPROVED' if approved else 'DENIED'}]")
    return json.dumps(response)


async def main() -> None:
    """Run the four-turn spike scenario."""
    print(f"Connecting to AG-UI server at {SERVER_URL}")
    async with AGUIChatClient(endpoint=SERVER_URL) as chat_client:
        agent = Agent(
            chat_client,
            instructions=(
                "You forward user messages to the server. "
                "When the server requests approval via the "
                "request_approval tool, that tool will run "
                "locally — do not generate any text response."
            ),
            name="SpikeC2Client",
            tools=[request_approval],
        )
        session = agent.create_session()

        print(
            "\nSpike C2 ready. Suggested scenario:\n"
            "  1. List the records\n"
            "  2. Create a record named gamma  (approve)\n"
            "  3. Create another one named delta  (deny)\n"
            "  4. List the records again\n"
            "Type ':q' or Ctrl-D to exit.\n",
        )

        while True:
            try:
                user_text = await asyncio.to_thread(input, "User: ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            user_text = user_text.strip()
            if not user_text:
                continue
            if user_text in {":q", "quit", "exit"}:
                break

            print("\nA: ", end="", flush=True)
            try:
                chunk_count = 0
                async for chunk in agent.run(
                    user_text, session=session, stream=True
                ):
                    chunk_count += 1
                    if chunk.text:
                        print(chunk.text, end="", flush=True)
                    # DEBUG: dump every chunk's structure
                    contents_repr = (
                        [type(c).__name__ for c in chunk.contents]
                        if getattr(chunk, "contents", None)
                        else []
                    )
                    sys.stderr.write(
                        f"\n[debug chunk#{chunk_count}] "
                        f"contents={contents_repr} "
                        f"text={chunk.text!r} "
                        f"props={getattr(chunk, 'additional_properties', None)}\n"
                    )
                sys.stderr.write(
                    f"[debug] run finished, {chunk_count} chunks total\n"
                )
            except Exception as exc:
                print(f"\n[ERROR] {type(exc).__name__}: {exc}")
                continue
            print()


if __name__ == "__main__":
    asyncio.run(main())
