"""Discovery tools - explore Tepilora API capabilities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from Tepilora import get_operation_info
from Tepilora._schema import SCHEMA

from ..server import mcp


def _list_namespaces() -> List[Dict[str, Any]]:
    """List all Tepilora API namespaces with operation counts."""
    operations = SCHEMA["operations"]
    counts: Dict[str, int] = {}
    for op in operations.values():
        if op.get("internal"):
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
        if op.get("internal") or op["category"] != namespace:
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
    result = {
        "action": info["action"],
        "category": info["category"],
        "summary": info.get("summary", ""),
        "description": info.get("description", ""),
        "credits": info.get("credits", 1),
        "params": [
            {
                "name": p["name"],
                "type": p.get("type", "any"),
                "required": p.get("required", False),
                "default": p.get("default"),
                "description": p.get("description", ""),
            }
            for p in info.get("params", [])
        ],
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
