"""ONE-MP AG-UI FastAPI server — SSE endpoint and /api/delegates route."""

import os
from collections import OrderedDict
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


class _ApprovalRegistry(OrderedDict):
    """OrderedDict that normalises approval-registry keys to call_id only.

    Reason: AgentFrameworkAgent registers approval requests under
    ``{foundry_conv_id}:{call_id}`` (set *after* the first Foundry token
    arrives), but validates them under ``{ui_thread_id}:{call_id}`` (set
    *before* streaming starts from the UI's threadId).  The two prefixes
    never match, so every approval is rejected as "no matching pending
    approval request" (BUG-4C-003).

    By stripping the prefix on every access we make both operations hit
    the same underlying entry.  OpenAI call_ids (``call_<base64>``) never
    contain ``:``, so the split is unambiguous.  ``OrderedDict`` is
    preserved so the LRU eviction in ``_evict_oldest_approvals`` still
    works without modification.
    """

    @staticmethod
    def _key(k: str) -> str:
        return k.split(":", 1)[-1] if ":" in k else k

    def __setitem__(self, key: str, value: str) -> None:
        super().__setitem__(self._key(key), value)

    def __getitem__(self, key: str) -> str:
        return super().__getitem__(self._key(key))

    def __contains__(self, key: object) -> bool:
        return super().__contains__(self._key(str(key)))

    def __delitem__(self, key: str) -> None:
        super().__delitem__(self._key(key))


_DB_PATH: str = os.environ.get("DATABASE_PATH", "one_agent.db")
_db_engine = get_engine(_DB_PATH)

_agent: Agent | None = None
_protocol_runner: AgentFrameworkAgent | None = None
# Reason: CopilotKit HITL continuation POSTs drop the state dict, so
# delegate_id is unavailable on approval round-trips.  We persist the
# mapping from the initial request (which always carries state) and use
# it as a fallback for stateless follow-up requests.
_thread_delegate_map: dict[str, str] = {}


def _install_approval_delegate_id_injector() -> None:
    """Patch ``_auto_invoke_function`` to thread delegate_id into HITL execution.

    ``agent_framework_ag_ui._resolve_approval_responses`` builds its function-
    middleware pipeline from ``client.function_middleware`` only.  ONE-MP's
    ``AuditMiddleware`` is registered on ``agent.middleware`` (the LLM-tool
    path) and therefore never runs for HITL-approved tool execution, leaving
    ``delegate_id`` absent from ctx.kwargs and write tools failing with
    "Only delegation editors can create delegates/DARs".  We resolve the
    acting delegate from the session's ``ag_ui_thread_id`` metadata via
    ``_thread_delegate_map`` and inject it into ``custom_args`` before the
    framework dispatches the approved tool.
    """
    import agent_framework._tools as _af_tools

    _orig = _af_tools._auto_invoke_function

    async def _patched(function_call_content, custom_args=None, **kw):
        fcc_type = getattr(function_call_content, "type", "?")
        if fcc_type == "function_approval_response":
            args = dict(custom_args or {})
            if not args.get("delegate_id"):
                session = args.get("session")
                metadata = getattr(session, "metadata", None) or {}
                if isinstance(metadata, dict):
                    thread_id = metadata.get("ag_ui_thread_id", "")
                    if thread_id:
                        resolved = _thread_delegate_map.get(thread_id, "")
                        if resolved:
                            args["delegate_id"] = resolved
            custom_args = args
        return await _orig(function_call_content, custom_args, **kw)

    _af_tools._auto_invoke_function = _patched


_install_approval_delegate_id_injector()

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
        # Reason: AgentFrameworkAgent.collect_server_tools introspects
        # ``default_options['tools']`` (and ``mcp_tools``) to build the
        # tool_map used by the HITL approval-execution path.  Without
        # these passthroughs the tool_map is empty, ``_auto_invoke_function``
        # silently returns the approval response unchanged, and the
        # approved write tool is never executed.
        self.default_options: Any = getattr(agent, "default_options", None)
        self.mcp_tools: Any = getattr(agent, "mcp_tools", None)

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
        The algorithm is index-based, so it correctly handles both adjacent and
        non-contiguous misorderings. Dry-run observation confirms the consistent
        CopilotKit v2 pattern is `[tool, assistant]` pairs (ASSUMPTION-001),
        but the implementation is not limited to that shape.
        When multiple tool results share one assistant message, the assistant is
        spliced before the first preceding result only; the ``skip`` guard
        prevents duplication.

    Args:
        messages: Raw AG-UI message list from request body.

    Returns:
        Reordered list where each assistant message precedes its tool-result messages.
    """
    call_to_asst: dict[str, int] = {}
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls") or msg.get("toolCalls") or []:
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
            if asst_idx > i and asst_idx not in skip:
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


def _get_protocol_runner(delegate_id: str) -> AgentFrameworkAgent:
    """Return the module-level AgentFrameworkAgent singleton.

    The singleton is created on first call and reused across requests so
    that ``_pending_approvals`` (populated when a ``function_approval_request``
    event streams) survives the HITL round-trip to the approval POST.  A fresh
    instance per request would lose the registry, causing approval validation
    to fail and the approved tool call to be silently dropped (BUG-4C-002).

    The per-request ``delegate_id`` is threaded in by updating ``.agent``
    before each run; this is safe because FastAPI dispatches requests
    sequentially within a single Uvicorn worker and the runner is not shared
    across concurrent event-generator coroutines.

    Args:
        delegate_id: Identity of the acting delegate for this request.

    Returns:
        Singleton AgentFrameworkAgent with updated bound agent.
    """
    global _protocol_runner
    bound = _BoundAgent(_get_agent(), delegate_id)
    if _protocol_runner is None:
        _protocol_runner = AgentFrameworkAgent(agent=bound)
        _protocol_runner._pending_approvals = _ApprovalRegistry()
    else:
        _protocol_runner.agent = bound
    return _protocol_runner


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
    thread_id: str = request_body.thread_id or ""
    if delegate_id and thread_id:
        _thread_delegate_map[thread_id] = delegate_id
    elif not delegate_id and thread_id:
        delegate_id = _thread_delegate_map.get(thread_id, "")
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
    protocol_runner = _get_protocol_runner(delegate_id)

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
