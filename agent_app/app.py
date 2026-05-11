"""Chainlit entrypoint for the ONE-MP Agent app.

Drives the Microsoft Agent Framework approval loop. The approval branch
is carried as dead code for UC2 (no HITL tools are registered in Phase 1).

Per-session identity threading (SEC-001 / PAT-001): delegate_id is read
from cl.user_session and bound into tool closures — the model never sees
it as a tool argument.
"""

from __future__ import annotations

import chainlit as cl
from agent_framework import Message
from azure.identity import AzureCliCredential
from loguru import logger

from agent_app.agent import build_agent

# Default delegate for dev login bypass (no auth layer yet).
# First seed delegate: full_name="Alice Martin", delegation="France".
_DEV_DEFAULT_DELEGATE_ID = "DEL-2026-0001"


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialise the agent and stash it on the user session."""
    delegate_id: str = cl.user_session.get(
        "delegate_id", _DEV_DEFAULT_DELEGATE_ID
    )
    credential = AzureCliCredential()
    agent = build_agent(credential=credential, delegate_id=delegate_id)
    session = agent.create_session()
    cl.user_session.set("credential", credential)
    cl.user_session.set("agent", agent)
    cl.user_session.set("session", session)
    await cl.Message(
        content="Agent ready. Try: who am I?",
    ).send()


async def _prompt_for_approval(req: object) -> bool:
    """Render an approval prompt and return whether the user approved.

    Args:
        req: A FunctionApprovalRequestContent-shaped object with
            ``function_call.name`` and ``function_call.arguments``.

    Returns:
        True if the user clicked Approve, False if Deny or timeout.
    """
    fc = req.function_call  # type: ignore[attr-defined]
    args = fc.arguments
    actions = [
        cl.Action(
            name="approve",
            payload={"value": "yes"},
            label="✅ Approve",
        ),
        cl.Action(
            name="deny",
            payload={"value": "no"},
            label="❌ Deny",
        ),
    ]
    res = await cl.AskActionMessage(
        content=(
            f"Tool `{fc.name}` requires approval.\n\nArguments: `{args}`"
        ),
        actions=actions,
        timeout=300,
    ).send()
    return bool(res) and res.get("payload", {}).get("value") == "yes"


@cl.on_message
async def on_message(user_msg: cl.Message) -> None:
    """Drive the MAF agent through the approval loop for one turn."""
    agent = cl.user_session.get("agent")
    session = cl.user_session.get("session")
    if agent is None or session is None:
        await cl.Message(
            content="Agent not initialised — refresh the page.",
        ).send()
        return

    current_input: object = user_msg.content

    while True:
        out = cl.Message(content="")
        await out.send()
        user_input_requests: list[object] = []

        try:
            async for chunk in agent.run(
                current_input, session=session, stream=True
            ):
                if chunk.text:
                    await out.stream_token(chunk.text)
                if getattr(chunk, "user_input_requests", None):
                    user_input_requests.extend(chunk.user_input_requests)
        except Exception as exc:
            logger.exception("agent.run failed: {}", exc)
            await out.stream_token(
                f"\n\n**[ERROR]** {type(exc).__name__}: {exc}",
            )
            await out.update()
            return

        await out.update()

        if not user_input_requests:
            return

        # With a session, the framework already tracks the assistant
        # message that emitted the approval requests. Only the
        # user-side approval response needs to be sent back.
        approval_responses: list[object] = []
        for req in user_input_requests:
            approved = await _prompt_for_approval(req)
            approval_responses.append(
                req.to_function_approval_response(  # type: ignore[attr-defined]
                    approved=approved,
                ),
            )
        current_input = Message("user", approval_responses)
