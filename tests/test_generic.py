"""Tests for generic call_operation tool."""

import importlib
from unittest.mock import AsyncMock, patch

from Tepilora._schema import SCHEMA
from tepilora_mcp.tools.generic import (
    _call_operation,
    _call_operation_arrow_stream,
    call_operation,
)


class TestCallOperation:
    def test_tool_docstring_uses_schema_count(self):
        expected = len(SCHEMA.get("operations", {}))
        description = getattr(call_operation, "description", None) or call_operation.__doc__ or ""
        assert f"{expected} operations" in description

    async def test_get_client_singleton_uses_config_values(self):
        import tepilora_mcp.tools.generic as generic_module

        importlib.reload(generic_module)

        fake_client = object()
        generic_module._client = None
        generic_module._resolved_url = None
        try:
            async def fake_resolve():
                return "https://example.test"

            with patch.object(generic_module, "TEPILORA_API_KEY", "api-key-test"), \
                 patch.object(generic_module, "TEPILORA_MCP_TIMEOUT", 12.5), \
                 patch.object(generic_module, "_resolve_base_url", fake_resolve), \
                 patch.object(generic_module, "AsyncTepiloraClient", return_value=fake_client) as mock_ctor:
                first = await generic_module._get_or_create_client()
                second = await generic_module._get_or_create_client()

            assert first is fake_client
            assert second is first
            mock_ctor.assert_called_once_with(
                api_key="api-key-test",
                base_url="https://example.test",
                timeout=12.5,
            )
        finally:
            generic_module._client = None
            generic_module._resolved_url = None

    async def test_calls_correct_action(self, mock_client, mock_transport):
        result = await _call_operation("securities.search", params={"query": "MSCI", "limit": 10})
        assert result is not None

        calls = mock_transport.calls
        assert len(calls) == 1
        assert calls[0]["payload"]["action"] == "securities.search"
        assert calls[0]["payload"]["params"]["query"] == "MSCI"

    async def test_calls_without_params(self, mock_client, mock_transport):
        result = await _call_operation("analytics.list")
        assert result is not None

        calls = mock_transport.calls
        assert len(calls) == 1
        assert calls[0]["payload"]["action"] == "analytics.list"

    async def test_params_none_sends_empty_dict(self, mock_transport):
        await _call_operation("some.action", params=None)

        calls = mock_transport.calls
        assert len(calls) == 1
        assert calls[0]["payload"]["action"] == "some.action"
        assert calls[0]["payload"]["params"] == {}

    async def test_returns_structured_error_on_client_exception(self, mock_client):
        mock_client.call = AsyncMock(side_effect=RuntimeError("boom"))
        result = await _call_operation("some.action", params={"x": 1})
        assert result["error"] == "Unexpected error while calling Tepilora API."
        assert "RuntimeError: boom" in result["details"]

    async def test_arrow_stream_operation_returns_base64_payload(self, mock_client):
        class _Meta:
            request_id = "req-1"
            execution_time_ms = 9
            total_count = 2
            row_count = 2

        class _Resp:
            format = "arrow"
            content_type = "application/vnd.apache.arrow.stream"
            content = b"abc"
            meta = _Meta()
            headers = {"x-test": "1"}

        mock_client.call_arrow_ipc_stream = AsyncMock(return_value=_Resp())
        result = await _call_operation_arrow_stream("securities.search", {"query": "MSCI"})
        assert result["format"] == "arrow"
        assert result["size_bytes"] == 3
        assert result["content_base64"] == "YWJj"
