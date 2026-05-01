"""Spike C2 raw client — direct httpx + SSE against AG-UI server.

Bypasses AGUIChatClient and the Agent abstraction. Talks the AG-UI
wire protocol directly so the spike can exercise the HITL round-trip
that the high-level Python API does not surface cleanly. Goal: confirm
or refute F2 (backend message-history cleanup gap on multi-turn after
denied approval).

Wire reference (verified against agent-framework tests, 2026-04-29):
- POST body: `{thread_id, run_id, messages, ...}`
- Response: SSE `data: {json}` lines
- Approval request arrives as either
  `RUN_FINISHED` event with `interrupt: [...]` payload OR a
  `CUSTOM` event with `name: "function_approval_request"` carrying the
  approval call_id.
- Approval response is a regular tool-result message in the *next*
  POST's messages array:
  `{"role": "tool", "content": '{"accepted": true}', "toolCallId": id}`.

Run (server in another terminal first):
    .venv/bin/python -m spikes.c2_custom_agui.raw_client
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

SERVER_URL = os.environ.get("AGUI_SERVER_URL", "http://127.0.0.1:8888/")


async def _prompt(message: str) -> bool:
    """Block on terminal input for an approve/deny decision."""
    while True:
        choice = await asyncio.to_thread(input, f"\n{message} (y/n): ")
        c = choice.strip().lower()
        if c in {"y", "yes"}:
            return True
        if c in {"n", "no"}:
            return False
        print("Please enter y or n.")


async def _post_and_stream(
    client: httpx.AsyncClient,
    body: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """POST to the AG-UI server and consume the SSE stream.

    Returns:
        (text_chunks, approval_requests, all_events)
    """
    text_chunks: list[str] = []
    approval_requests: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []

    async with client.stream(
        "POST",
        SERVER_URL,
        json=body,
        headers={"Accept": "text/event-stream"},
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: ") :]
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            all_events.append(event)
            etype = event.get("type")
            if etype == "TEXT_MESSAGE_CONTENT":
                delta = event.get("delta", "")
                if delta:
                    text_chunks.append(delta)
                    print(delta, end="", flush=True)
            elif etype == "CUSTOM":
                name = event.get("name") or event.get("rawEvent", {}).get(
                    "name"
                )
                value = event.get("value") or event.get("rawEvent", {}).get(
                    "value"
                )
                if name == "function_approval_request":
                    val = value or {}
                    aid = val.get("id") or (
                        val.get("function_call") or {}
                    ).get("call_id")
                    if aid and not any(
                        (
                            r.get("id")
                            or (r.get("function_call") or {}).get("call_id")
                        )
                        == aid
                        for r in approval_requests
                    ):
                        approval_requests.append(val)
            elif etype == "RUN_FINISHED":
                interrupts = event.get("interrupt") or []
                for entry in interrupts:
                    val = entry.get("value", {})
                    if val.get("type") == "function_approval_request":
                        aid = entry.get("id") or (
                            val.get("function_call") or {}
                        ).get("call_id")
                        if aid and not any(
                            (
                                r.get("id")
                                or (r.get("function_call") or {}).get(
                                    "call_id"
                                )
                            )
                            == aid
                            for r in approval_requests
                        ):
                            approval_requests.append(
                                {
                                    "id": aid,
                                    "function_call": val.get("function_call"),
                                }
                            )
            elif etype == "RUN_ERROR":
                msg = event.get("message", "<no message>")
                print(f"\n[RUN_ERROR] {msg}", file=sys.stderr)

    return text_chunks, approval_requests, all_events


async def main() -> None:
    """Run the four-turn spike scenario."""
    print(f"Connecting to AG-UI server at {SERVER_URL}")
    thread_id = f"thread_{uuid.uuid4().hex}"
    history: list[dict[str, Any]] = []

    print(
        "\nSpike C2 (raw httpx) ready. Suggested scenario:\n"
        "  1. List the records\n"
        "  2. Create a record named gamma  (approve)\n"
        "  3. Create another one named delta  (deny)\n"
        "  4. List the records again\n"
        "Type ':q' or Ctrl-D to exit.\n",
    )

    async with httpx.AsyncClient() as client:
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

            history.append({"role": "user", "content": user_text})

            print("\nA: ", end="", flush=True)
            run_id = f"run_{uuid.uuid4().hex}"
            body = {
                "thread_id": thread_id,
                "run_id": run_id,
                "messages": history,
            }
            try:
                _, approvals, _ = await _post_and_stream(client, body)
            except httpx.HTTPStatusError as exc:
                print(
                    f"\n[HTTP {exc.response.status_code}] "
                    f"{exc.response.text[:300]}",
                )
                continue
            except Exception as exc:
                print(f"\n[ERROR] {type(exc).__name__}: {exc}")
                continue
            print()

            # Loop on pending approvals
            while approvals:
                next_resume_msgs: list[dict[str, Any]] = []
                for req in approvals:
                    fc = req.get("function_call") or {}
                    name = fc.get("name", "<unknown>")
                    args = fc.get("arguments", {})
                    call_id = req.get("id") or fc.get("call_id")
                    print()
                    print("=" * 60)
                    print("APPROVAL REQUIRED")
                    print("=" * 60)
                    print(f"Tool: {name}")
                    print(f"Arguments: {args}")
                    print("=" * 60)
                    approved = await _prompt(
                        f"Approve execution of '{name}'?",
                    )
                    print(
                        f"[Sending {'APPROVE' if approved else 'DENY'}]",
                    )
                    # Per agent-framework tests, history must include the
                    # assistant message bearing the tool_call BEFORE the
                    # tool-result that carries the approval response.
                    args_json = (
                        args if isinstance(args, str) else json.dumps(args)
                    )
                    # The server's message adapter scans for a synthetic
                    # `request_approval` tool call and its matching tool
                    # result. The assistant message must therefore use
                    # name=request_approval, with the original function
                    # call wrapped inside the `request` argument as JSON.
                    approval_request_payload = {
                        "approvalId": call_id,
                        "functionName": name,
                        "functionArguments": args
                        if isinstance(args, dict)
                        else (json.loads(args_json) if args_json else {}),
                        "message": (f"Approve execution of '{name}'?"),
                    }
                    # Python AG-UI uses `confirm_changes` (not the C#
                    # `request_approval`) for the synthetic approval
                    # tool name. The matcher in _message_adapters.py
                    # specifically tracks `confirm_changes` call_ids.
                    next_resume_msgs.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "toolCalls": [
                                {
                                    "id": call_id,
                                    "type": "function",
                                    "function": {
                                        "name": "confirm_changes",
                                        "arguments": json.dumps(
                                            approval_request_payload,
                                        ),
                                    },
                                },
                            ],
                        },
                    )
                    next_resume_msgs.append(
                        {
                            "role": "tool",
                            "content": json.dumps(
                                {"accepted": approved},
                            ),
                            "toolCallId": call_id,
                        },
                    )

                history.extend(next_resume_msgs)
                run_id = f"run_{uuid.uuid4().hex}"
                resume_body = {
                    "thread_id": thread_id,
                    "run_id": run_id,
                    "messages": history,
                }
                print("\nA: ", end="", flush=True)
                try:
                    _, approvals, _ = await _post_and_stream(
                        client,
                        resume_body,
                    )
                except httpx.HTTPStatusError as exc:
                    print(
                        f"\n[HTTP {exc.response.status_code}] "
                        f"{exc.response.text[:500]}",
                    )
                    break
                except Exception as exc:
                    print(f"\n[ERROR] {type(exc).__name__}: {exc}")
                    break
                print()


if __name__ == "__main__":
    asyncio.run(main())
