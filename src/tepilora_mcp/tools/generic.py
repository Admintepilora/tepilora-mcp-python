"""Generic tool - call any Tepilora API operation."""

from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from Tepilora import AsyncTepiloraClient
from Tepilora._schema import SCHEMA

from ..config import (
    TEPILORA_MCP_API_KEY, TEPILORA_BASE_URL, TEPILORA_FALLBACK_URL, TEPILORA_MCP_TIMEOUT,
)
from .cache import CACHE, is_cacheable_action, make_cache_key
from .credits import CREDITS
from .errors import handle_tool_errors
from ..server import mcp

_client: Optional[AsyncTepiloraClient] = None
_resolved_url: Optional[str] = None
_TOTAL_OPERATIONS = len(SCHEMA.get("operations", {}))
_CALL_OPERATION_DOC = f"""Call any Tepilora API operation by action string.

    This is the universal tool: it can execute any of the {_TOTAL_OPERATIONS} operations.
    Use `list_namespaces`, `list_operations`, and `describe_operation` to discover
    what's available and what parameters are needed.

    Args:
        action: Operation to call (e.g. "securities.search", "portfolio.create")
        params: Operation parameters as key-value pairs
    """


async def _probe_url(url: str) -> bool:
    """Check if a base URL returns JSON (not HTML) on a lightweight call."""
    try:
        probe = AsyncTepiloraClient(api_key=TEPILORA_MCP_API_KEY, base_url=url, timeout=5.0)
        resp = await probe.call("search.global", params={"query": "test", "limit": 1})
        return hasattr(resp, "data")
    except Exception:
        return False


async def _resolve_base_url() -> str:
    """Return the first working API URL, with fallback."""
    global _resolved_url
    if _resolved_url is not None:
        return _resolved_url
    if await _probe_url(TEPILORA_BASE_URL):
        _resolved_url = TEPILORA_BASE_URL
    elif TEPILORA_FALLBACK_URL and await _probe_url(TEPILORA_FALLBACK_URL):
        _resolved_url = TEPILORA_FALLBACK_URL
    else:
        _resolved_url = TEPILORA_BASE_URL  # default, let errors propagate
    return _resolved_url


async def _get_or_create_client() -> AsyncTepiloraClient:
    """Get client, resolving fallback URL on first call if needed."""
    global _client
    if _client is None:
        url = await _resolve_base_url()
        _client = AsyncTepiloraClient(
            api_key=TEPILORA_MCP_API_KEY,
            base_url=url,
            timeout=TEPILORA_MCP_TIMEOUT,
        )
    return _client


@handle_tool_errors
async def _call_operation(
    action: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call any Tepilora API operation by action string."""
    call_params = params or {}
    cache_key = None
    if is_cacheable_action(action):
        cache_key = make_cache_key(action, call_params)
        cached = await CACHE.get(cache_key)
        if cached is not None:
            return cached

    credit_check = await CREDITS.consume_for_action(action)
    if not credit_check.get("allowed", False):
        return {
            "error": str(credit_check["error"]),
            "details": str(credit_check["details"]),
        }

    client = await _get_or_create_client()
    response = await client.call(action, params=call_params)
    data = response.data
    if cache_key is not None and isinstance(data, dict) and "error" not in data:
        await CACHE.set(cache_key, data)
    return data


@handle_tool_errors
async def _call_operation_arrow_stream(
    action: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call an operation using Arrow IPC format and return base64 payload."""
    call_params = params or {}
    credit_check = await CREDITS.consume_for_action(action)
    if not credit_check.get("allowed", False):
        return {
            "error": str(credit_check["error"]),
            "details": str(credit_check["details"]),
        }

    client = await _get_or_create_client()
    response = await client.call_arrow_ipc_stream(action, params=call_params)
    return {
        "action": action,
        "format": response.format,
        "content_type": response.content_type,
        "size_bytes": len(response.content),
        "meta": {
            "request_id": response.meta.request_id,
            "execution_time_ms": response.meta.execution_time_ms,
            "total_count": response.meta.total_count,
            "row_count": response.meta.row_count,
        },
        "headers": response.headers,
        "content_base64": base64.b64encode(response.content).decode("ascii"),
    }


# --- MCP tool registration ---

async def call_operation(
    action: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Public async operation caller for SDK/test integrations."""
    return await _call_operation(action, params)


call_operation.__doc__ = _CALL_OPERATION_DOC
_call_operation_tool = mcp.tool(call_operation)


@mcp.tool
async def call_operation_arrow_stream(
    action: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call any operation in Arrow IPC format.

    Returns metadata plus `content_base64`, which contains Arrow IPC bytes.
    """
    return await _call_operation_arrow_stream(action, params)


@mcp.tool
async def clear_cache() -> Dict[str, Any]:
    """Clear the in-memory tool result cache."""
    return await _clear_cache()


async def _clear_cache() -> Dict[str, Any]:
    """Clear the in-memory tool result cache."""
    cleared = await CACHE.clear()
    stats = await CACHE.stats()
    return {
        "cleared_entries": cleared,
        "cache": stats,
    }


@mcp.tool
async def get_credit_usage() -> Dict[str, Any]:
    """Get current session credit usage and configured limit."""
    return await _get_credit_usage()


async def _get_credit_usage() -> Dict[str, Any]:
    """Get current session credit usage and configured limit."""
    return await CREDITS.usage()


@mcp.tool
async def reset_credits() -> Dict[str, Any]:
    """Reset the session credit usage counter."""
    return await _reset_credits()


async def _reset_credits() -> Dict[str, Any]:
    """Reset the session credit usage counter."""
    previous = await CREDITS.reset()
    usage = await CREDITS.usage()
    return {
        "reset": previous,
        "current": usage,
    }


__all__ = [
    "call_operation",
    "call_operation_arrow_stream",
    "clear_cache",
    "get_credit_usage",
    "reset_credits",
]
