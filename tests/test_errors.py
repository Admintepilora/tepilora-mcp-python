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

    def test_sdk_error_keeps_real_attachment_code_without_changing_legacy_fields(self):
        # Captured from call_operation against DEV :8004 on 2026-10-20.
        exc = TepiloraAPIError(
            message="{'code': 'NOT_FOUND', 'message': 'Attachment not found'}",
            status_code=404,
            error_data={"detail": {"code": "NOT_FOUND", "message": "Attachment not found"}},
        )
        result = error_from_exception(exc)
        assert result == {
            "error": "Not found: the requested Tepilora operation or resource does not exist.",
            "details": "TepiloraAPIError: HTTP 404: {'code': 'NOT_FOUND', 'message': 'Attachment not found'}",
            "code": "NOT_FOUND",
            "message": "Attachment not found",
        }

    @pytest.mark.parametrize("status", [200, 422, None])
    @pytest.mark.parametrize("wrapper", [None, "detail", "error"])
    def test_sdk_error_preserves_structured_fields_across_envelopes(self, status, wrapper):
        payload = {"code": "VALIDATION_ERROR", "message": "Invalid template"}
        data = {wrapper: payload} if wrapper else payload
        result = error_from_exception(TepiloraAPIError("bad request", status_code=status, error_data=data))
        assert result["code"] == "VALIDATION_ERROR"
        assert result["message"] == "Invalid template"

    @pytest.mark.parametrize("data", [
        None, {}, {"detail": "not found"}, {"detail": [{"msg": "bad"}]},
        {"code": None, "message": None}, {"code": 404, "message": {"text": "bad"}},
    ])
    def test_sdk_error_does_not_infer_codes_from_status_or_exception_text(self, data):
        result = error_from_exception(TepiloraAPIError("NOT_FOUND", status_code=404, error_data=data))
        assert set(result) == {"error", "details"}

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
