"""Tests for server entrypoints and import gating."""

import importlib
import os
import runpy
import sys
from unittest.mock import patch

import pytest

from tepilora_mcp.server import main


class TestMain:
    async def test_main_calls_mcp_run(self):
        with patch("tepilora_mcp.server.mcp") as mock_mcp:
            main()
            mock_mcp.run.assert_called_once()


class TestServerImportGating:
    @pytest.mark.parametrize(
        "raw_value,expected",
        [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("", False),
        ],
    )
    async def test_config_parses_full_tools_env_values(self, raw_value, expected):
        with patch.dict(os.environ, {"TEPILORA_MCP_FULL_TOOLS": raw_value}):
            import tepilora_mcp.config as config_module

            importlib.reload(config_module)
            assert config_module.TEPILORA_MCP_FULL_TOOLS is expected

    async def test_server_does_not_import_full_when_env_false(self):
        import tepilora_mcp.tools as tools_pkg

        sys.modules.pop("tepilora_mcp.server", None)
        sys.modules.pop("tepilora_mcp.tools.full", None)
        if hasattr(tools_pkg, "full"):
            delattr(tools_pkg, "full")

        with patch.dict(os.environ, {"TEPILORA_MCP_FULL_TOOLS": "false"}):
            import tepilora_mcp.config as config_module

            importlib.reload(config_module)
            importlib.import_module("tepilora_mcp.server")

        assert "tepilora_mcp.tools.full" not in sys.modules

    async def test_config_parses_new_numeric_env_values(self):
        with patch.dict(
            os.environ,
            {
                "TEPILORA_MCP_CACHE_TTL": "123",
                "TEPILORA_MCP_CACHE_MAX_SIZE": "55",
                "TEPILORA_MCP_CREDIT_LIMIT": "999",
            },
        ):
            import tepilora_mcp.config as config_module

            importlib.reload(config_module)
            assert config_module.TEPILORA_MCP_CACHE_TTL == 123
            assert config_module.TEPILORA_MCP_CACHE_MAX_SIZE == 55
            assert config_module.TEPILORA_MCP_CREDIT_LIMIT == 999


class TestMainModule:
    async def test_module_execution_calls_server_main(self):
        with patch("tepilora_mcp.server.main") as mock_main:
            runpy.run_module("tepilora_mcp", run_name="__main__")
            mock_main.assert_called_once()
