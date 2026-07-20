"""Runtime policy gates for MCP operations.

The public MCP package stays unrestricted by default. Dashboard AI launches the
server with TEPILORA_MCP_POLICY=dashboard_ai so the MCP layer becomes the
server-side allowlist, independent from the model/provider path.
"""

from __future__ import annotations

from typing import Dict

from ..config import TEPILORA_MCP_POLICY


_DASHBOARD_AI_POLICIES = {"dashboard_ai", "dashboard-ai"}

_DASHBOARD_AI_ALLOWED_ACTIONS = frozenset(
    {
        "attachments.read",
        "attachments.list",
        "attachments.info",
        "attachments.download",
        "attachments.parse",
        "news.latest",
        "news.search",
        "queries.list",
        "queries.get",
        "queries.execute",
        "queries.preview",
        "securities.search",
        "securities.details",
        "securities.history",
        "bonds.screen",
        "bonds.curve",
        "realtime.quotes",
        "realtime.quote",
        "realtime.chart",
        "realtime.calendar",
        "realtime.health",
    }
)

_DASHBOARD_AI_ALLOWED_PREFIXES = ("analytics.",)

_DASHBOARD_AI_ALLOWED_LOCAL_TOOLS = frozenset({"get_credit_usage"})


def is_dashboard_ai_policy() -> bool:
    """Return True when the server is running in dashboard AI allowlist mode."""
    return TEPILORA_MCP_POLICY in _DASHBOARD_AI_POLICIES


def is_operation_allowed(action: str) -> bool:
    """Apply runtime operation allowlist for restricted MCP contexts."""
    if not is_dashboard_ai_policy():
        return True
    if action in _DASHBOARD_AI_ALLOWED_ACTIONS:
        return True
    return any(action.startswith(prefix) for prefix in _DASHBOARD_AI_ALLOWED_PREFIXES)


def is_local_tool_allowed(tool_name: str) -> bool:
    """Apply runtime allowlist to MCP-local utility tools."""
    if not is_dashboard_ai_policy():
        return True
    return tool_name in _DASHBOARD_AI_ALLOWED_LOCAL_TOOLS


def blocked_payload(name: str) -> Dict[str, str]:
    """Consistent AI-readable policy denial payload."""
    return {
        "error": "MCP policy blocked this tool or operation.",
        "details": (
            f"{name} is not allowed when TEPILORA_MCP_POLICY=dashboard_ai. "
            "Use an allowlisted read operation or route the action through the dashboard backend."
        ),
    }
