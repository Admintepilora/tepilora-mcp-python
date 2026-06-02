"""Tepilora MCP Server - Financial data tools for AI assistants."""

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("tepilora-mcp")
except Exception:
    __version__ = "0.0.0"

from .server import mcp, main

__all__ = ["mcp", "main", "__version__"]
