"""Full tool registration - all operations as individual MCP tools.

Only loaded when TEPILORA_MCP_FULL_TOOLS=true.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from Tepilora._schema import SCHEMA

from .errors import handle_tool_errors
from .generic import _call_operation
from ..server import mcp

# Method name renames (match SDK conventions)
_RENAMES = {
    "global": "global_search",
    "import": "import_data",
    "exec": "execute",
    "eval": "evaluate",
}

# Skip these - they're already covered by curated/generic tools
_SKIP_ACTIONS = {
    "securities.search",       # search_securities
    "securities.details",      # get_security_details
    "securities.history",      # get_price_history
    "portfolio.create",        # create_portfolio
    "portfolio.returns",       # get_portfolio_returns
    "news.search",             # search_news
    "bonds.screen",            # screen_bonds
    "bonds.curve",             # get_yield_curve
    "realtime.quotes",         # get_realtime_quotes
    "realtime.quote",          # get_realtime_quote
    "realtime.chart",          # get_realtime_chart
    "realtime.calendar",       # get_realtime_calendar
    "realtime.health",         # get_realtime_health
}


def _make_tool_func(action: str, op: Dict[str, Any]):
    """Create a tool function for a single operation."""

    @handle_tool_errors
    async def tool_func(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await _call_operation(action, params=params or {})

    # Set metadata for FastMCP
    summary = op.get("summary", "")
    param_info = op.get("params", [])
    param_lines = []
    for p in param_info:
        req = " (required)" if p.get("required") else ""
        desc = p.get("description", "")
        param_lines.append(f"  - {p['name']}: {p.get('type', 'any')}{req} {desc}")

    params_doc = "\n".join(param_lines) if param_lines else "  No parameters."

    # Deprecation notice
    deprecation_doc = ""
    if op.get("deprecated"):
        dep_msg = op.get("deprecation_message", "")
        dep_replacement = op.get("replacement", "")
        deprecation_doc = "\n** DEPRECATED **"
        if dep_msg:
            deprecation_doc += f" {dep_msg}"
        elif dep_replacement:
            deprecation_doc += f" Use {dep_replacement} instead."
        if op.get("sunset_date"):
            deprecation_doc += f" Sunset: {op['sunset_date']}."
        deprecation_doc += "\n"

    # Rename reserved words
    op_name = action.split(".")[-1]
    safe_name = _RENAMES.get(op_name, op_name)
    category = action.split(".")[0]
    tool_func.__name__ = f"tepilora_{category}_{safe_name}"
    tool_func.__doc__ = f"""{summary or action}
{deprecation_doc}
Action: {action}
Category: {op['category']}
Credits: {op.get('credits', 1)}

Parameters (pass as dict):
{params_doc}

Args:
    params: Operation parameters as key-value dict
"""
    return tool_func


def register_all():
    """Register all operations as individual tools."""
    for action, op in sorted(SCHEMA["operations"].items()):
        if op.get("internal"):
            continue
        if action in _SKIP_ACTIONS:
            continue

        func = _make_tool_func(action, op)
        mcp.tool(func)


register_all()
