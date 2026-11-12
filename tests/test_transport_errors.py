"""Keep typed transport codes when MCP serializes SDK exceptions."""

from unittest.mock import AsyncMock

import httpx
import pytest
from Tepilora import AsyncTepiloraClient

from tepilora_mcp.tools import generic
from tepilora_mcp.tools.errors import error_from_exception


TRANSPORT_ERRORS = [
    (httpx.TimeoutException, "timeout"),
    (httpx.ReadTimeout, "timeout"),
    (httpx.ConnectTimeout, "timeout"),
    (httpx.ConnectError, "connection_error"),
    (httpx.RemoteProtocolError, "connection_error"),
    (httpx.ReadError, "connection_error"),
    (httpx.NetworkError, "connection_error"),
]


@pytest.mark.parametrize("error_type,code", TRANSPORT_ERRORS)
def test_typed_transport_code_is_additive(error_type, code):
    result = error_from_exception(error_type("opaque"))
    if issubclass(error_type, httpx.TimeoutException):
        legacy_error = "Request timed out contacting Tepilora API. Retry or increase `TEPILORA_MCP_TIMEOUT`."
    elif issubclass(error_type, httpx.ConnectError):
        legacy_error = "Connection failed: could not reach Tepilora API. Check network and base URL."
    else:
        legacy_error = "Unexpected error while calling Tepilora API."
    assert result == {"error": legacy_error, "details": f"{error_type.__name__}: opaque", "code": code}


@pytest.mark.parametrize("error_type", [RuntimeError, httpx.LocalProtocolError])
def test_other_errors_do_not_gain_a_transport_code(error_type):
    assert error_from_exception(error_type("opaque")) == {
        "error": "Unexpected error while calling Tepilora API.",
        "details": f"{error_type.__name__}: opaque",
    }


@pytest.mark.parametrize("error_type,code", TRANSPORT_ERRORS)
async def test_public_mcp_call_preserves_code_from_mock_transport(error_type, code, monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            raise error_type("opaque", request=request)
        return httpx.Response(200, json={
            "success": True, "action": "securities.search",
            "data": {"result": "ok"}, "meta": {},
        })

    async with AsyncTepiloraClient(
        api_key="test-key", base_url="http://transport.test", transport=httpx.MockTransport(handle),
    ) as client:
        monkeypatch.setattr(generic, "_get_or_create_client", AsyncMock(return_value=client))
        first = await generic.call_operation("securities.search", {"query": "test"})
        assert first["code"] == code
        assert len(calls) == 1  # The tool does not add a retry.
        second = await generic.call_operation("securities.search", {"query": "test"})
    assert second == {"result": "ok"}
    assert len(calls) == 2
