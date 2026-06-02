"""Tests for full tool generation and registration."""

import inspect
from unittest.mock import Mock

import pytest

from Tepilora._schema import SCHEMA
from tepilora_mcp.server import mcp
from tepilora_mcp.tools import full as full_module
from tepilora_mcp.tools.full import _RENAMES, _SKIP_ACTIONS, _make_tool_func


def _action_to_tool_name(action: str) -> str:
    category = action.split(".")[0]
    op_name = action.split(".")[-1]
    safe_name = _RENAMES.get(op_name, op_name)
    return f"tepilora_{category}_{safe_name}"


def _full_tool_names():
    names = {name for name in mcp._tool_manager._tools if name.startswith("tepilora_")}
    if not names:
        pytest.skip("Full tool registration is not active.")
    return names


class TestRenames:
    async def test_reserved_keyword_renames(self):
        assert _RENAMES == {
            "global": "global_search",
            "import": "import_data",
            "exec": "execute",
            "eval": "evaluate",
        }


class TestSkipActions:
    async def test_contains_curated_skip_actions(self):
        assert _SKIP_ACTIONS == {
            "securities.search",
            "securities.details",
            "securities.history",
            "portfolio.create",
            "portfolio.returns",
            "queries.save",
            "news.search",
            "bonds.screen",
            "bonds.curve",
            "realtime.quotes",
            "realtime.quote",
            "realtime.chart",
            "realtime.calendar",
            "realtime.health",
        }


class TestMakeToolFunc:
    async def test_generated_function_is_async_and_awaitable(self):
        action = "alerts.ack"
        op = SCHEMA["operations"][action]
        func = _make_tool_func(action, op)
        assert inspect.iscoroutinefunction(func)
        result = await func({"event_id": "evt-1"})
        assert isinstance(result, dict)

    async def test_sets_name_for_normal_action(self):
        action = "alerts.ack"
        op = SCHEMA["operations"][action]
        func = _make_tool_func(action, op)
        assert func.__name__ == "tepilora_alerts_ack"

    async def test_sets_name_for_renamed_action(self):
        action = "search.global"
        op = SCHEMA["operations"][action]
        func = _make_tool_func(action, op)
        assert func.__name__ == "tepilora_search_global_search"

    async def test_doc_contains_action_category_and_credits(self):
        action = "alerts.ack"
        op = SCHEMA["operations"][action]
        func = _make_tool_func(action, op)
        doc = func.__doc__ or ""
        assert f"Action: {action}" in doc
        assert f"Category: {op['category']}" in doc
        assert f"Credits: {op.get('credits', 1)}" in doc

    async def test_doc_contains_parameter_info_when_params_exist(self):
        action = "alerts.ack"
        op = SCHEMA["operations"][action]
        func = _make_tool_func(action, op)
        doc = func.__doc__ or ""
        for p in op["params"]:
            required = " (required)" if p.get("required") else ""
            expected_line = f"  - {p['name']}: {p.get('type', 'any')}{required} {p.get('description', '')}"
            assert expected_line in doc

    async def test_doc_contains_no_parameters_for_paramless_ops(self):
        action = "bonds.metrics"
        op = SCHEMA["operations"][action]
        assert op.get("params") in (None, [])
        func = _make_tool_func(action, op)
        doc = func.__doc__ or ""
        assert "No parameters." in doc

    async def test_calls_correct_action_when_awaited(self, mock_transport):
        action = "alerts.ack"
        op = SCHEMA["operations"][action]
        func = _make_tool_func(action, op)
        await func({"event_id": "evt-1"})
        assert mock_transport.calls[-1]["payload"]["action"] == action
        assert mock_transport.calls[-1]["payload"]["params"]["event_id"] == "evt-1"

    async def test_default_params_none_sends_empty_dict(self, mock_transport):
        action = "alerts.ack"
        op = SCHEMA["operations"][action]
        func = _make_tool_func(action, op)

        await func()
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == action
        assert payload["params"] == {}


class TestRegistration:
    async def test_skipped_actions_are_not_registered_as_full_tools(self):
        names = _full_tool_names()
        for action in _SKIP_ACTIONS:
            assert _action_to_tool_name(action) not in names

    async def test_internal_operations_are_not_registered(self):
        names = _full_tool_names()
        for action, op in SCHEMA["operations"].items():
            if op.get("internal"):
                assert _action_to_tool_name(action) not in names

    async def test_reserved_word_rename_is_applied_in_registration(self):
        names = _full_tool_names()
        assert "tepilora_search_global_search" in names
        assert "tepilora_search_global" not in names

    async def test_total_registered_full_tools_matches_schema(self):
        names = _full_tool_names()
        expected = sum(
            1
            for action, op in SCHEMA["operations"].items()
            if not op.get("internal") and action not in _SKIP_ACTIONS
        )
        assert expected >= 218  # minimum: SDK 0.3.2 baseline
        assert len(names) == expected

    async def test_register_all_with_monkeypatched_schema_registers_only_normal_ops(self, monkeypatch):
        fake_schema = {
            "operations": {
                "test.normal": {
                    "category": "test",
                    "internal": False,
                    "summary": "Visible operation",
                    "params": [],
                },
                "securities.search": {
                    "category": "securities",
                    "internal": False,
                    "summary": "Curated and skipped",
                    "params": [],
                },
                "test.secret": {
                    "category": "test",
                    "internal": True,
                    "summary": "Internal operation",
                    "params": [],
                },
            }
        }
        mock_tool = Mock()
        monkeypatch.setattr(full_module, "SCHEMA", fake_schema)
        monkeypatch.setattr(full_module.mcp, "tool", mock_tool)

        full_module.register_all()

        assert mock_tool.call_count == 1
        registered = mock_tool.call_args[0][0]
        assert registered.__name__ == "tepilora_test_normal"
