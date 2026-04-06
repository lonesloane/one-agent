"""Middleware for recording tool calls during evaluation runs."""

from collections.abc import Awaitable, Callable

from agent_framework import FunctionInvocationContext, FunctionMiddleware


class RecorderMiddleware(FunctionMiddleware):
    """Captures tool call details (name, arguments, result) during agent runs."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict] = []

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Record tool call details before and after execution.

        Args:
            context: The function invocation context containing the tool
                name, arguments, and result.
            call_next: Callable that invokes the next middleware or the
                tool itself.
        """
        record = {
            "tool": context.function.name,
            "arguments": dict(context.arguments),
        }
        await call_next()
        record["result"] = context.result
        self.calls.append(record)

    def reset(self) -> None:
        """Clear all recorded tool calls."""
        self.calls = []
