"""Generic tool - call any Tepilora API operation."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Tepilora import AsyncTepiloraClient
from Tepilora._schema import SCHEMA

from ..config import (
    TEPILORA_MCP_API_KEY, TEPILORA_BASE_URL, TEPILORA_FALLBACK_URL, TEPILORA_MCP_TIMEOUT,
)
from .cache import CACHE, is_cacheable_action, make_cache_key
from .credits import CREDITS
from .errors import handle_tool_errors
from .policy import blocked_payload, is_local_tool_allowed, is_operation_allowed
from ..server import mcp

_client: Optional[AsyncTepiloraClient] = None
_resolved_url: Optional[str] = None
_TOTAL_OPERATIONS = len(SCHEMA.get("operations", {}))
_DEFAULT_FILE_MAX_BYTES = 10 * 1024 * 1024
_CALL_OPERATION_DOC = f"""Call any Tepilora API operation by action string.

    This is the universal tool: it can execute any of the {_TOTAL_OPERATIONS} operations.
    Use `list_namespaces`, `list_operations`, and `describe_operation` to discover
    what's available and what parameters are needed.

    File upload operations are still JSON at the MCP layer. For each parameter
    whose type is `file`, pass exactly one of:
    - `file_path`: local readable file path, for single-file operations;
    - `content_base64`: base64-encoded file bytes, for single-file operations;
    - `<param>_path` or `<param>_base64` for operations with multiple file fields.
    The MCP server reads/decodes the content, checks the operation max size, then
    sends bytes through the SDK multipart transport.

    Binary download operations are also JSON at the MCP layer. By default they
    return `content_base64`; pass `output_file_path` to save bytes to a local
    file instead.

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


def _operation_for_action(action: str) -> Optional[Dict[str, Any]]:
    operation = SCHEMA.get("operations", {}).get(action)
    return operation if isinstance(operation, dict) else None


def _file_params_for_action(action: str) -> List[Dict[str, Any]]:
    operation = _operation_for_action(action)
    if not operation:
        return []
    return [
        param
        for param in operation.get("params", []) or []
        if isinstance(param, dict) and param.get("type") == "file"
    ]


def _response_transport_for_action(action: str) -> Optional[str]:
    operation = _operation_for_action(action)
    transport = operation.get("response_transport") if operation else None
    return str(transport) if transport else None


def _file_max_bytes(param: Dict[str, Any]) -> int:
    raw = param.get("max_bytes") or param.get("maxBytes") or _DEFAULT_FILE_MAX_BYTES
    try:
        max_bytes = int(raw)
    except (TypeError, ValueError):
        max_bytes = _DEFAULT_FILE_MAX_BYTES
    return max(1, max_bytes)


def _path_keys(param_name: str, *, single_file_operation: bool) -> Tuple[str, ...]:
    keys = [f"{param_name}_path"]
    if single_file_operation:
        keys.append("file_path")
    return tuple(dict.fromkeys(keys))


def _base64_keys(param_name: str, *, single_file_operation: bool) -> Tuple[str, ...]:
    keys = [f"{param_name}_base64", f"{param_name}_content_base64"]
    if single_file_operation:
        keys.append("content_base64")
    return tuple(dict.fromkeys(keys))


def _provided_values(params: Dict[str, Any], keys: Tuple[str, ...]) -> List[Tuple[str, Any]]:
    return [(key, params[key]) for key in keys if params.get(key) is not None]


def _read_file_path(path_value: Any, *, max_bytes: int) -> Tuple[bytes, Optional[str]]:
    if not isinstance(path_value, (str, Path)):
        raise ValueError("file_path must be a string path")
    raw_path = Path(path_value).expanduser()
    if ".." in Path(path_value).parts:
        raise ValueError("file_path must not contain '..' traversal segments")
    resolved = raw_path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"file_path is not a regular file: {resolved}")
    size = resolved.stat().st_size
    if size > max_bytes:
        raise ValueError(f"file_path exceeds max size of {max_bytes} bytes")
    return resolved.read_bytes(), resolved.name


def _decode_base64(value: Any, *, max_bytes: int) -> bytes:
    if not isinstance(value, str):
        raise ValueError("content_base64 must be a base64 string")
    try:
        data = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError("content_base64 is not valid base64") from exc
    if len(data) > max_bytes:
        raise ValueError(f"content_base64 exceeds max size of {max_bytes} bytes")
    return data


def _prepare_file_operation_params(
    action: str,
    params: Dict[str, Any],
) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    """Convert MCP JSON file inputs into SDK multipart bytes."""
    file_params = _file_params_for_action(action)
    if not file_params:
        return params, ()

    prepared = dict(params)
    single_file_operation = len(file_params) == 1

    for file_param in file_params:
        name = str(file_param["name"])
        max_bytes = _file_max_bytes(file_param)
        path_values = _provided_values(
            prepared,
            _path_keys(name, single_file_operation=single_file_operation),
        )
        base64_values = _provided_values(
            prepared,
            _base64_keys(name, single_file_operation=single_file_operation),
        )

        total_sources = len(path_values) + len(base64_values)
        direct_value = prepared.get(name)
        if direct_value is not None and isinstance(direct_value, (bytes, bytearray, memoryview)):
            total_sources += 1

        if total_sources == 0:
            raise ValueError(
                f"{action} requires file parameter '{name}'. "
                "Provide file_path or content_base64."
            )
        if total_sources > 1:
            raise ValueError(
                f"{action} file parameter '{name}' accepts exactly one source: "
                "file_path or content_base64."
            )

        inferred_filename: Optional[str] = None
        if path_values:
            _, value = path_values[0]
            data, inferred_filename = _read_file_path(value, max_bytes=max_bytes)
        elif base64_values:
            _, value = base64_values[0]
            data = _decode_base64(value, max_bytes=max_bytes)
        elif isinstance(direct_value, (bytes, bytearray, memoryview)):
            data = bytes(direct_value)
            if len(data) > max_bytes:
                raise ValueError(f"{name} exceeds max size of {max_bytes} bytes")
        else:
            raise ValueError(
                f"{action} file parameter '{name}' must use file_path or content_base64."
            )

        for key in (
            *_path_keys(name, single_file_operation=single_file_operation),
            *_base64_keys(name, single_file_operation=single_file_operation),
        ):
            prepared.pop(key, None)
        prepared[name] = data
        operation = _operation_for_action(action) or {}
        operation_param_names = {
            p.get("name")
            for p in operation.get("params", []) or []
            if isinstance(p, dict)
        }
        if inferred_filename and "filename" in operation_param_names:
            prepared.setdefault("filename", inferred_filename)

    return prepared, tuple(str(param["name"]) for param in file_params)


def _output_path_keys(*, allow_file_path_alias: bool) -> Tuple[str, ...]:
    keys = ["output_file_path"]
    if allow_file_path_alias:
        keys.append("file_path")
    return tuple(keys)


def _prepare_binary_output_params(
    params: Dict[str, Any],
    *,
    allow_file_path_alias: bool,
) -> Tuple[Dict[str, Any], Optional[Path]]:
    prepared = dict(params)
    output_values = _provided_values(
        prepared,
        _output_path_keys(allow_file_path_alias=allow_file_path_alias),
    )
    if len(output_values) > 1:
        raise ValueError("Binary output accepts only one output path")
    if not output_values:
        return prepared, None

    key, value = output_values[0]
    if not isinstance(value, (str, Path)):
        raise ValueError(f"{key} must be a string path")
    raw_path = Path(value).expanduser()
    if ".." in Path(value).parts:
        raise ValueError(f"{key} must not contain '..' traversal segments")

    parent = raw_path.parent.resolve(strict=True)
    target = (parent / raw_path.name).resolve()
    if not target.is_relative_to(parent):
        raise ValueError(f"{key} resolves outside its parent directory")
    if target.exists():
        raise ValueError(f"{key} already exists: {target}")
    if target.name in ("", ".", ".."):
        raise ValueError(f"{key} must include a file name")

    for output_key in _output_path_keys(allow_file_path_alias=allow_file_path_alias):
        prepared.pop(output_key, None)
    return prepared, target


def _header_value(headers: Dict[str, str], name: str) -> Optional[str]:
    lower_name = name.lower()
    for key, value in headers.items():
        if key.lower() == lower_name:
            return value
    return None


def _filename_from_headers(headers: Dict[str, str]) -> Optional[str]:
    disposition = _header_value(headers, "content-disposition")
    if not disposition:
        return None
    for part in disposition.split(";"):
        clean = part.strip()
        if clean.lower().startswith("filename="):
            return clean.split("=", 1)[1].strip().strip('"') or None
    return None


def _binary_response_payload(response: Any, output_path: Optional[Path]) -> Dict[str, Any]:
    content = getattr(response, "content", None)
    if not isinstance(content, (bytes, bytearray, memoryview)):
        raise ValueError("Binary operation did not return bytes")
    content_bytes = bytes(content)
    headers = dict(getattr(response, "headers", {}) or {})
    payload = {
        "action": getattr(response, "action", ""),
        "format": getattr(response, "format", "binary"),
        "content_type": getattr(response, "content_type", "application/octet-stream"),
        "size_bytes": len(content_bytes),
        "filename": _filename_from_headers(headers),
        "headers": headers,
    }
    meta = getattr(response, "meta", None)
    if meta is not None:
        payload["meta"] = {
            "request_id": getattr(meta, "request_id", None),
            "execution_time_ms": getattr(meta, "execution_time_ms", None),
            "total_count": getattr(meta, "total_count", None),
            "row_count": getattr(meta, "row_count", None),
        }
    if output_path is not None:
        output_path.write_bytes(content_bytes)
        payload["output_file_path"] = str(output_path)
        return payload

    payload["content_base64"] = base64.b64encode(content_bytes).decode("ascii")
    return payload


async def _call_sdk_operation(
    client: AsyncTepiloraClient,
    action: str,
    *,
    params: Dict[str, Any],
    file_fields: Tuple[str, ...] = (),
    binary_response: bool = False,
) -> Any:
    if binary_response and not file_fields:
        call_binary = getattr(client, "call_binary", None)
        if not callable(call_binary):
            raise ValueError(
                "Installed Tepilora SDK does not support binary transport. "
                "Upgrade TepiloraSDK before calling binary operations through MCP."
            )
        return await call_binary(action, params=params)
    if not file_fields:
        return await client.call(action, params=params)
    call_multipart = getattr(client, "call_multipart", None)
    if not callable(call_multipart):
        raise ValueError(
            "Installed Tepilora SDK does not support file transport. "
            "Upgrade TepiloraSDK before calling file operations through MCP."
        )
    return await call_multipart(action, params=params, file_fields=file_fields)


@handle_tool_errors
async def _call_operation(
    action: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call any Tepilora API operation by action string."""
    if not is_operation_allowed(action):
        return blocked_payload(action)

    call_params = params or {}
    file_params = _file_params_for_action(action)
    file_fields: Tuple[str, ...] = ()
    if file_params:
        call_params, file_fields = _prepare_file_operation_params(action, call_params)
    binary_response = _response_transport_for_action(action) == "binary"
    output_path: Optional[Path] = None
    if binary_response:
        call_params, output_path = _prepare_binary_output_params(
            call_params,
            allow_file_path_alias=not file_fields,
        )

    cache_key = None
    if not file_fields and not binary_response and is_cacheable_action(action):
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
    response = await _call_sdk_operation(
        client,
        action,
        params=call_params,
        file_fields=file_fields,
        binary_response=binary_response,
    )
    if binary_response:
        return _binary_response_payload(response, output_path)
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
    if not is_operation_allowed(action):
        return blocked_payload(action)

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
    if not is_local_tool_allowed("clear_cache"):
        return blocked_payload("clear_cache")

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
    if not is_local_tool_allowed("reset_credits"):
        return blocked_payload("reset_credits")

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
