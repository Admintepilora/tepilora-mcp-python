"""Configuration for Tepilora MCP server."""

import os


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


TEPILORA_API_KEY = os.environ.get("TEPILORA_API_KEY", "")
TEPILORA_BASE_URL = os.environ.get("TEPILORA_BASE_URL", "https://tepiloradata.com")
TEPILORA_FALLBACK_URL = os.environ.get("TEPILORA_FALLBACK_URL", "")
def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default

TEPILORA_MCP_TIMEOUT = _env_float("TEPILORA_MCP_TIMEOUT", 30.0)
TEPILORA_MCP_FULL_TOOLS = os.environ.get("TEPILORA_MCP_FULL_TOOLS", "false").lower() in ("true", "1", "yes")
TEPILORA_MCP_CACHE_TTL = max(0, _env_int("TEPILORA_MCP_CACHE_TTL", 300))
TEPILORA_MCP_CACHE_MAX_SIZE = max(1, _env_int("TEPILORA_MCP_CACHE_MAX_SIZE", 1000))
TEPILORA_MCP_CREDIT_LIMIT = max(0, _env_int("TEPILORA_MCP_CREDIT_LIMIT", 0))
