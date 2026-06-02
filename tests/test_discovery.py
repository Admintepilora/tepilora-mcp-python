"""Tests for discovery tools."""

import tepilora_mcp.tools.discovery as discovery_module

from tepilora_mcp.tools.discovery import _list_namespaces, _list_operations, _describe_operation


class TestListNamespaces:
    def test_returns_all_namespaces(self):
        result = _list_namespaces()
        names = [ns["namespace"] for ns in result]
        assert "securities" in names
        assert "analytics" in names
        assert "portfolio" in names
        assert len(result) >= 20

    def test_has_operation_counts(self):
        result = _list_namespaces()
        analytics = next(ns for ns in result if ns["namespace"] == "analytics")
        expected = sum(
            1
            for op in discovery_module.SCHEMA["operations"].values()
            if not op.get("internal") and op["category"] == "analytics"
        )
        assert analytics["operations"] == expected

    def test_excludes_internal_operations_with_synthetic_schema(self, monkeypatch):
        fake_schema = {
            "operations": {
                "test.normal": {
                    "category": "test",
                    "internal": False,
                    "summary": "Test op",
                    "params": [{"name": "id"}],
                },
                "test.internal": {
                    "category": "test",
                    "internal": True,
                    "summary": "Internal op",
                    "params": [],
                },
            }
        }
        monkeypatch.setattr(discovery_module, "SCHEMA", fake_schema)

        namespaces = _list_namespaces()
        assert namespaces == [{"namespace": "test", "operations": 1}]


class TestListOperations:
    def test_list_securities(self):
        result = _list_operations("securities")
        actions = [op["action"] for op in result]
        assert "securities.search" in actions
        assert "securities.history" in actions

    def test_empty_for_unknown(self):
        result = _list_operations("nonexistent")
        assert result == []

    def test_excludes_internal_operations_with_synthetic_schema(self, monkeypatch):
        fake_schema = {
            "operations": {
                "test.normal": {
                    "category": "test",
                    "internal": False,
                    "summary": "Test op",
                    "params": [{"name": "id"}],
                },
                "test.internal": {
                    "category": "test",
                    "internal": True,
                    "summary": "Internal op",
                    "params": [],
                },
            }
        }
        monkeypatch.setattr(discovery_module, "SCHEMA", fake_schema)

        result = _list_operations("test")
        assert result == [{"action": "test.normal", "summary": "Test op"}]


class TestDescribeOperation:
    def test_describe_securities_search(self):
        result = _describe_operation("securities.search")
        assert result["action"] == "securities.search"
        assert result["category"] == "securities"
        assert isinstance(result["params"], list)
        assert len(result["params"]) > 0

    def test_describe_unknown(self):
        result = _describe_operation("not.real")
        assert "error" in result

    def test_default_normalization_for_missing_optional_fields(self, monkeypatch):
        def fake_get_operation_info(_action: str):
            return {
                "action": "test.normal",
                "category": "test",
                "params": [{"name": "identifier"}],
            }

        monkeypatch.setattr(discovery_module, "get_operation_info", fake_get_operation_info)

        result = _describe_operation("test.normal")
        assert result["summary"] == ""
        assert result["description"] == ""
        assert result["credits"] == 1
        assert result["params"] == [{
            "name": "identifier",
            "type": "any",
            "required": False,
            "default": None,
            "description": "",
        }]
