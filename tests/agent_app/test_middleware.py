"""Unit tests for agent_app/middleware.py — AuditMiddleware."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_app.middleware import AuditMiddleware


class TestAuditMiddleware:
    """Tests for the AuditMiddleware tool call logger."""

    @pytest.mark.asyncio
    async def test_process_calls_next_and_logs(self) -> None:
        """Middleware invokes call_next and logs at INFO level."""
        middleware = AuditMiddleware()
        context = MagicMock()
        context.function.name = "test_tool"
        context.arguments = {"key": "val"}
        context.result = "ok"

        call_next = AsyncMock()

        with patch("agent_app.middleware.logger.info") as mock_log:
            await middleware.process(context, call_next)

        call_next.assert_called_once()
        mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_logs_after_call_next(self) -> None:
        """Log message is emitted only after call_next completes."""
        middleware = AuditMiddleware()
        context = MagicMock()
        context.function.name = "test_tool"
        context.arguments = {"key": "val"}
        context.result = "ok"

        call_order: list[str] = []

        async def tracking_call_next() -> None:
            call_order.append("call_next")

        with patch("agent_app.middleware.logger.info") as mock_log:
            mock_log.side_effect = (
                lambda *a, **k: call_order.append("log")
            )
            await middleware.process(context, tracking_call_next)

        assert call_order == ["call_next", "log"]
