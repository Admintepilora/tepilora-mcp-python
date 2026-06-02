"""Tepilora MCP Server - main entry point."""

from fastmcp import FastMCP

from .config import TEPILORA_MCP_FULL_TOOLS

mcp = FastMCP("Tepilora")

# Register tools and prompts
from .tools import discovery, generic, curated, prompts  # noqa: E402, F401

if TEPILORA_MCP_FULL_TOOLS:
    from .tools import full  # noqa: E402, F401


def main():
    """Run the MCP server."""
    mcp.run()
