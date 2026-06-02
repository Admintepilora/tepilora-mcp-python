"""Error normalization helpers for MCP tool responses."""

from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable, Dict, TypeVar, cast

import httpx

try:
    from Tepilora.errors import TepiloraAPIError, TepiloraError
except ImportError:  # pragma: no cover - fallback for unexpected SDK layouts
    TepiloraAPIError = None  # type: ignore[assignment]
    TepiloraError = Exception  # type: ignore[assignment]


_AsyncDictFn = TypeVar("_AsyncDictFn", bound=Callable[..., Awaitable[Dict[str, Any]]])


def _http_status_message(status_code: int) -> str:
    if status_code == 401:
        return "Unauthorized: check `TEPILORA_MCP_API_KEY` and verify the key is active."
    if status_code == 403:
        return "Forbidden: this API key is not allowed to use the requested operation."
    if status_code == 404:
        return "Not found: the requested Tepilora operation or resource does not exist."
    if status_code == 429:
        return "Rate limit reached: wait and retry, or reduce request frequency."
    if status_code >= 500:
        return "Tepilora server error: the API is temporarily unavailable. Retry shortly."
    return f"Tepilora request failed with HTTP {status_code}."


def _format_details(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def error_from_exception(exc: Exception) -> Dict[str, str]:
    """Convert low-level exceptions into AI-friendly error payloads."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else None
        if status is None:
            return {
                "error": "HTTP request failed while calling Tepilora.",
                "details": _format_details(exc),
            }
        return {
            "error": _http_status_message(status),
            "details": _format_details(exc),
        }

    if isinstance(exc, httpx.ConnectError):
        return {
            "error": "Connection failed: could not reach Tepilora API. Check network and base URL.",
            "details": _format_details(exc),
        }

    if isinstance(exc, httpx.TimeoutException):
        return {
            "error": "Request timed out contacting Tepilora API. Retry or increase `TEPILORA_MCP_TIMEOUT`.",
            "details": _format_details(exc),
        }

    if TepiloraAPIError is not None and isinstance(exc, TepiloraAPIError):
        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            return {
                "error": _http_status_message(status),
                "details": _format_details(exc),
            }
        return {
            "error": "Tepilora API returned an error response.",
            "details": _format_details(exc),
        }

    if isinstance(exc, (KeyError, ValueError)):
        return {
            "error": "Invalid parameters: verify required fields and value formats.",
            "details": _format_details(exc),
        }

    if isinstance(exc, TepiloraError):
        return {
            "error": "Tepilora SDK error while processing this request.",
            "details": _format_details(exc),
        }

    return {
        "error": "Unexpected error while calling Tepilora API.",
        "details": _format_details(exc),
    }


def handle_tool_errors(func: _AsyncDictFn) -> _AsyncDictFn:
    """Decorator that returns structured errors instead of raising."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            return await func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised through tests
            return error_from_exception(exc)

    return cast(_AsyncDictFn, wrapper)
