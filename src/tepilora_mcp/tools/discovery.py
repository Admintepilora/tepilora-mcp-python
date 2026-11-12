"""Discovery tools - explore Tepilora API capabilities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from Tepilora import get_operation_info
from Tepilora._schema import SCHEMA

from ..server import mcp
from .policy import blocked_payload, is_operation_allowed


def _list_namespaces() -> List[Dict[str, Any]]:
    """List all Tepilora API namespaces with operation counts."""
    operations = SCHEMA["operations"]
    counts: Dict[str, int] = {}
    for action, op in operations.items():
        if op.get("internal") or not is_operation_allowed(action):
            continue
        cat = op["category"]
        counts[cat] = counts.get(cat, 0) + 1

    return [
        {"namespace": ns, "operations": counts.get(ns, 0)}
        for ns in sorted(counts.keys())
    ]


def _list_operations(namespace: str) -> List[Dict[str, str]]:
    """List all operations in a namespace with their summaries."""
    operations = SCHEMA["operations"]
    result = []
    for action, op in sorted(operations.items()):
        if op.get("internal") or op["category"] != namespace or not is_operation_allowed(action):
            continue
        entry = {
            "action": action,
            "summary": op.get("summary", ""),
        }
        if op.get("deprecated"):
            entry["deprecated"] = True
            if op.get("replacement"):
                entry["replacement"] = op["replacement"]
        result.append(entry)
    return result


def _describe_operation(action: str) -> Optional[Dict[str, Any]]:
    """Get full details for a specific operation including parameters."""
    info = get_operation_info(action)
    if not info:
        return {"error": f"Operation '{action}' not found"}
    if not is_operation_allowed(action):
        return blocked_payload(action)

    params = []
    for p in info.get("params", []):
        param = {
            "name": p["name"],
            "type": p.get("type", "any"),
            "required": p.get("required", False),
            "default": p.get("default"),
            "description": p.get("description", ""),
        }
        if p.get("type") == "file":
            param["mcp_transport"] = {
                "accepted_inputs": ["file_path", "content_base64"],
                "file_path": "Local readable file path. For multiple file fields use '<param>_path'.",
                "content_base64": "Base64-encoded file bytes. For multiple file fields use '<param>_base64'.",
                "max_bytes": p.get("max_bytes"),
            }
        params.append(param)

    result = {
        "action": info["action"],
        "category": info["category"],
        "summary": info.get("summary", ""),
        "description": info.get("description", ""),
        "credits": info.get("credits", 1),
        "params": params,
    }
    if info.get("response_transport") == "binary":
        result["response_transport"] = "binary"
        result["mcp_output"] = {
            "default": "content_base64",
            "save_to_file": "Pass output_file_path to write bytes to a local file instead of returning content_base64.",
        }
    if info.get("deprecated"):
        result["deprecated"] = True
        result["deprecated_since"] = info.get("deprecated_since", "")
        result["sunset_date"] = info.get("sunset_date", "")
        result["replacement"] = info.get("replacement", "")
        result["deprecation_message"] = info.get("deprecation_message", "")

    # Curated examples from ExampleCase for_docs=True (Phase D cascade)
    if info.get("examples"):
        result["examples"] = [
            {"name": ex["name"], "params": ex["params"]}
            for ex in info["examples"]
        ]

    return result


# --- MCP tool registration ---

@mcp.tool
def list_namespaces() -> List[Dict[str, Any]]:
    """List all Tepilora API namespaces with operation counts.

    Returns a list of namespaces (securities, portfolio, analytics, etc.)
    with how many operations each one has. Use this to discover what's available.
    """
    return _list_namespaces()


@mcp.tool
def list_operations(namespace: str) -> List[Dict[str, str]]:
    """List all operations in a namespace with their summaries.

    Args:
        namespace: Namespace name (e.g. "securities", "portfolio", "analytics")
    """
    return _list_operations(namespace)


@mcp.tool
def describe_operation(action: str) -> Optional[Dict[str, Any]]:
    """Get full details for a specific operation including parameters.

    Args:
        action: Full action string (e.g. "securities.search", "analytics.rolling_volatility")
    """
    return _describe_operation(action)
