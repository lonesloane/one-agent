"""ONE-MP Read Agent — audit middleware for tool call logging."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from agent_framework import FunctionInvocationContext, FunctionMiddleware
from loguru import logger


class AuditMiddleware(FunctionMiddleware):
    """Logs each tool call with name, args, result, and UTC timestamp.

    Also resolves the acting delegate_id from the session's ``ag_ui_thread_id``
    metadata when the agent_framework_ag_ui approval-execution path bypasses
    ``function_invocation_kwargs`` (the kwargs injected by ``_BoundAgent.run``
    only flow through the LLM tool-call path; ``_resolve_approval_responses``
    builds its own ``tool_kwargs`` from session+tools alone).
    """

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Inject delegate_id fallback then log tool call details.

        Args:
            context: Invocation context with function name, arguments,
                and result (populated after call_next).
            call_next: Callable to invoke the next middleware or tool.
        """
        if not context.kwargs.get("delegate_id"):
            session = context.kwargs.get("session")
            metadata = getattr(session, "metadata", None) or {}
            thread_id = (
                metadata.get("ag_ui_thread_id", "")
                if isinstance(metadata, dict)
                else ""
            )
            if thread_id:
                # Reason: avoid circular import — server module wires the map.
                from agent_app.server import _thread_delegate_map

                resolved = _thread_delegate_map.get(thread_id, "")
                if resolved:
                    context.kwargs["delegate_id"] = resolved

        await call_next()
        ts = datetime.now(UTC).isoformat()
        logger.info(
            "tool={} args={} result={} ts={}",
            context.function.name,
            dict(context.arguments),
            context.result,
            ts,
        )
