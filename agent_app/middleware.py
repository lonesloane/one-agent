"""ONE-MP Read Agent — audit middleware for tool call logging."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from agent_framework import FunctionInvocationContext, FunctionMiddleware
from loguru import logger


class AuditMiddleware(FunctionMiddleware):
    """Logs each tool call with name, args, result, and UTC timestamp."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Log tool call details at INFO level after execution.

        Args:
            context: Invocation context with function name, arguments,
                and result (populated after call_next).
            call_next: Callable to invoke the next middleware or tool.
        """
        await call_next()
        ts = datetime.now(timezone.utc).isoformat()
        logger.info(
            "tool={} args={} result={} ts={}",
            context.function.name,
            dict(context.arguments),
            context.result,
            ts,
        )
