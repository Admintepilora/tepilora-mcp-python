"""Tests for tool error normalization."""

import httpx
import pytest

from Tepilora.errors import TepiloraAPIError
from tepilora_mcp.tools.errors import error_from_exception, handle_tool_errors


class TestErrorFromException:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Not found"),
            (429, "Rate limit reached"),
            (500, "Tepilora server error"),
        ],
    )
    def test_http_status_mappings(self, status, expected):
        request = httpx.Request("POST", "https://example.test")
        response = httpx.Response(status_code=status, request=request)
        exc = httpx.HTTPStatusError("status error", request=request, response=response)
        result = error_from_exception(exc)
        assert expected in result["error"]
        assert "HTTPStatusError" in result["details"]

    def test_connect_error_mapping(self):
        request = httpx.Request("POST", "https://example.test")
        exc = httpx.ConnectError("cannot connect", request=request)
        result = error_from_exception(exc)
        assert "Connection failed" in result["error"]
        assert "ConnectError" in result["details"]

    def test_timeout_mapping(self):
        request = httpx.Request("POST", "https://example.test")
        exc = httpx.ReadTimeout("timeout", request=request)
        result = error_from_exception(exc)
        assert "timed out" in result["error"]
        assert "ReadTimeout" in result["details"]

    def test_sdk_error_mapping(self):
        exc = TepiloraAPIError(message="bad request", status_code=404)
        result = error_from_exception(exc)
        assert "Not found" in result["error"]
        assert "TepiloraAPIError" in result["details"]

    def test_value_error_mapping(self):
        result = error_from_exception(ValueError("bad input"))
        assert "Invalid parameters" in result["error"]
        assert "ValueError: bad input" in result["details"]


class TestDecorator:
    async def test_decorator_returns_error_dict(self):
        @handle_tool_errors
        async def boom():
            raise RuntimeError("boom")

        result = await boom()
        assert result["error"] == "Unexpected error while calling Tepilora API."
        assert "RuntimeError: boom" in result["details"]
