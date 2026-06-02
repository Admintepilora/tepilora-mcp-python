"""Tests for credit accounting and limits."""

from tepilora_mcp.tools.credits import CreditTracker, CREDITS
from tepilora_mcp.tools.generic import _call_operation, _get_credit_usage, _reset_credits


class TestCreditTracker:
    async def test_usage_updates_after_consume(self):
        tracker = CreditTracker(credit_limit=10)
        result = await tracker.consume_for_action("securities.search")
        assert result["allowed"] is True
        usage = await tracker.usage()
        assert usage["used_credits"] >= 1
        assert usage["remaining_credits"] == usage["credit_limit"] - usage["used_credits"]

    async def test_limit_blocks_when_exceeded(self):
        tracker = CreditTracker(credit_limit=1)
        first = await tracker.consume_for_action("securities.search")
        second = await tracker.consume_for_action("securities.search")
        assert first["allowed"] is True
        assert second["allowed"] is False
        assert "Credit limit reached" in second["error"]


class TestCreditIntegration:
    async def test_credit_limit_blocks_sdk_call(self, mock_transport, monkeypatch):
        monkeypatch.setattr(CREDITS, "_credit_limit", 1)
        await CREDITS.reset()

        first = await _call_operation("portfolio.create", {"name": "A"})
        second = await _call_operation("portfolio.create", {"name": "B"})

        assert "error" not in first
        assert "Credit limit reached" in second["error"]
        assert len(mock_transport.calls) == 1

    async def test_credit_usage_and_reset_tools(self):
        await CREDITS.reset()
        await _call_operation("portfolio.create", {"name": "A"})

        usage = await _get_credit_usage()
        assert usage["used_credits"] >= 1

        reset_result = await _reset_credits()
        assert reset_result["reset"]["used_credits"] >= 1
        assert reset_result["current"]["used_credits"] == 0
