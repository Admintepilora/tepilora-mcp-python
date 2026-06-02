"""Shared fixtures for TepiloraMCP tests."""

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from Tepilora import AsyncTepiloraClient
from tepilora_mcp.tools.cache import CACHE
from tepilora_mcp.tools.credits import CREDITS


@pytest.fixture
def mock_transport():
    """Mock transport that records calls and returns success responses."""
    calls: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        try:
            payload = json.loads(request.content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        calls.append({
            "method": request.method,
            "url": str(request.url),
            "payload": payload,
        })

        action = payload.get("action", "unknown")
        return httpx.Response(
            200,
            json={
                "success": True,
                "action": action,
                "data": {"result": "mock", "action": action},
                "meta": {"request_id": "test-123", "execution_time_ms": 1, "timestamp": "t"},
            },
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    transport.calls = calls  # type: ignore
    return transport


@pytest.fixture
def mock_client(mock_transport) -> AsyncTepiloraClient:
    """AsyncTepiloraClient with mock transport."""
    return AsyncTepiloraClient(
        api_key="test-key",
        base_url="http://testserver",
        transport=mock_transport,
    )


@pytest.fixture(autouse=True)
def patch_get_client(mock_client):
    """Patch generic client singleton constructor (sync and async paths)."""
    async_mock = AsyncMock(return_value=mock_client)
    with patch("tepilora_mcp.tools.generic._get_or_create_client", async_mock):
        yield mock_client


@pytest.fixture(autouse=True)
async def reset_shared_state():
    """Reset mutable cache/credit singletons between tests."""
    await CACHE.clear()
    await CREDITS.reset()
    yield
    await CACHE.clear()
    await CREDITS.reset()
