"""Chainlit entrypoint for the ONE-MP Agent app (scaffold stub).

Boot stub: responds to every message with a placeholder.
Replaced by the full approval loop in TASK-005.
"""

from __future__ import annotations

import chainlit as cl


@cl.on_chat_start
async def on_chat_start() -> None:
    """Send a greeting when a new chat session starts."""
    await cl.Message(content="Agent scaffold ready.").send()


@cl.on_message
async def on_message(user_msg: cl.Message) -> None:
    """Echo a placeholder response for every user message."""
    await cl.Message(
        content=f"[scaffold stub] received: {user_msg.content}",
    ).send()
