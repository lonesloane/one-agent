"""ONE-MP AG-UI FastAPI server — SSE endpoint and /api/delegates route."""

import os
from collections.abc import AsyncGenerator
from typing import Any

from ag_ui.core import RunErrorEvent
from ag_ui.encoder import EventEncoder
from agent_framework import Agent
from agent_framework_ag_ui import AgentFrameworkAgent, AGUIRequest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as _Session
from sqlalchemy.orm import joinedload

from agent_app.agent import create_agent
from shared.database import Delegate, get_engine

_DB_PATH: str = os.environ.get("DATABASE_PATH", "one_agent.db")
_db_engine = get_engine(_DB_PATH)
_agent: Agent | None = None

_CORS_ORIGINS: list[str] = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000"
).split(",")

app = FastAPI(title="ONE-MP Read Agent Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DelegateOut(BaseModel):
    """Output schema for a delegate in the picker list."""

    id: str
    full_name: str
    delegation_name: str
    role: str


class _BoundAgent:
    """Wraps Agent to inject delegate_id into every run call.

    Delegates all protocol surface to the underlying agent so that
    AgentFrameworkAgent can introspect client, name, and function
    middleware without modification.
    """

    def __init__(self, agent: Agent, delegate_id: str) -> None:
        self._agent = agent
        self._delegate_id = delegate_id
        self.name: str = agent.name
        self.client: Any = agent.client

    def run(self, messages: Any, **kwargs: Any) -> Any:
        """Forward to underlying agent with delegate_id injected.

        Args:
            messages: Agent run inputs forwarded unchanged.
            **kwargs: Run-time kwargs; function_invocation_kwargs is
                merged so any upstream value is preserved.

        Returns:
            Agent run result or stream, same as Agent.run.
        """
        existing = kwargs.get("function_invocation_kwargs") or {}
        kwargs["function_invocation_kwargs"] = {
            **existing,
            "delegate_id": self._delegate_id,
        }
        return self._agent.run(messages, **kwargs)


def _fix_tool_call_ordering(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reorder messages so every assistant tool-call message precedes its tool-result messages.

    CopilotKit v2 may reconstruct conversation history with tool results before
    the assistant message that requested them. AgentFrameworkAgent._sanitize_tool_history
    drops out-of-order results rather than fixing the order, leaving dangling tool_call
    IDs that Foundry rejects with 400 (BUG-4C-001).

    Note:
        Assumes the misorder is a contiguous group: the tool-result message
        appears immediately before its owning assistant message with no unrelated
        messages interspersed. Dry-run observation confirms this is the consistent
        CopilotKit v2 pattern (ASSUMPTION-001).

    Args:
        messages: Raw AG-UI message list from request body.

    Returns:
        Reordered list where each assistant message precedes its tool-result messages.
    """
    call_to_asst: dict[str, int] = {}
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls") or []:
                if isinstance(tc, dict) and tc.get("id"):
                    call_to_asst[str(tc["id"])] = i

    result: list[dict[str, Any]] = []
    skip: set[int] = set()
    for i, msg in enumerate(messages):
        if i in skip:
            continue
        if msg.get("role") == "tool":
            cid = str(msg.get("tool_call_id") or msg.get("toolCallId") or "")
            asst_idx = call_to_asst.get(cid, -1)
            if asst_idx > i:
                result.append(messages[asst_idx])
                skip.add(asst_idx)
        result.append(msg)
    return result


def _get_agent() -> Agent:
    """Return the module-level agent singleton, creating it on first call.

    Returns:
        Configured ONEMPReadAgent instance.
    """
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent


@app.get("/api/delegates", response_model=list[DelegateOut])
async def get_delegates() -> list[DelegateOut]:
    """Return all delegates sorted alphabetically by full_name.

    Returns:
        List of DelegateOut with id, full_name, delegation_name, role.
    """
    with _Session(_db_engine) as session:
        stmt = (
            select(Delegate)
            .options(joinedload(Delegate.delegation))
            .order_by(Delegate.full_name)
        )
        delegates = session.scalars(stmt).unique().all()
        return [
            DelegateOut(
                id=d.id,
                full_name=d.full_name,
                delegation_name=d.delegation.name,
                role=d.role.value,
            )
            for d in delegates
        ]


@app.post("/", tags=["AG-UI"])
async def agent_endpoint(request_body: AGUIRequest) -> StreamingResponse:
    """AG-UI SSE endpoint with delegate_id identity threading.

    Extracts delegate_id from request_body.state and binds it into
    function_invocation_kwargs so tools receive it via
    FunctionInvocationContext without model exposure.

    Args:
        request_body: Standard AG-UI request with optional state dict
            containing ``delegate_id``.

    Returns:
        StreamingResponse in text/event-stream format.
    """
    delegate_id: str = (request_body.state or {}).get("delegate_id", "")
    if not delegate_id:
        # Reason: without delegate_id, ctx-injected tools return empty
        # results and the brief silently degrades to "nothing new".
        # Fail loudly so frontend state wiring bugs surface immediately.
        logger.error("AG-UI request missing delegate_id in state")
        raise HTTPException(
            status_code=400,
            detail="delegate_id is required in AG-UI request state",
        )

    input_data: dict[str, Any] = request_body.model_dump(exclude_none=True)
    if "messages" in input_data:
        input_data["messages"] = _fix_tool_call_ordering(
            input_data["messages"]
        )
    bound = _BoundAgent(_get_agent(), delegate_id)
    protocol_runner = AgentFrameworkAgent(agent=bound)

    async def event_generator() -> AsyncGenerator[str, None]:
        encoder = EventEncoder()
        try:
            async for event in protocol_runner.run(input_data):
                try:
                    yield encoder.encode(event)
                except Exception as enc_err:
                    logger.exception(
                        "Failed to encode AG-UI event: %s", enc_err
                    )
                    run_error = RunErrorEvent(
                        message="Event encoding error.",
                        code=type(enc_err).__name__,
                    )
                    try:
                        yield encoder.encode(run_error)
                    except Exception:
                        logger.exception("Failed to encode RunErrorEvent")
                    return
        except Exception as stream_err:
            logger.exception("AG-UI stream failed: %s", stream_err)
            run_error = RunErrorEvent(
                message="Internal streaming error.",
                code=type(stream_err).__name__,
            )
            try:
                yield encoder.encode(run_error)
            except Exception:
                logger.exception("Failed to encode RunErrorEvent")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
