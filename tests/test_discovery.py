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

    def test_dashboard_ai_policy_counts_only_allowed_operations(self, monkeypatch):
        import tepilora_mcp.tools.policy as policy

        monkeypatch.setattr(policy, "TEPILORA_MCP_POLICY", "dashboard_ai")
        monkeypatch.setattr(
            discovery_module,
            "SCHEMA",
            {
                "operations": {
                    "attachments.parse": {
                        "category": "attachments",
                        "internal": False,
                        "summary": "Parse attachment",
                        "params": [],
                    },
                    "documents.parse": {
                        "category": "documents",
                        "internal": False,
                        "summary": "Parse document",
                        "params": [],
                    },
                }
            },
        )

        namespaces = _list_namespaces()

        assert namespaces == [{"namespace": "attachments", "operations": 1}]


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

    def test_dashboard_ai_policy_hides_disallowed_operations(self, monkeypatch):
        import tepilora_mcp.tools.policy as policy

        monkeypatch.setattr(policy, "TEPILORA_MCP_POLICY", "dashboard_ai")
        monkeypatch.setattr(
            discovery_module,
            "SCHEMA",
            {
                "operations": {
                    "attachments.parse": {
                        "category": "attachments",
                        "internal": False,
                        "summary": "Parse attachment",
                        "params": [],
                    },
                    "documents.parse": {
                        "category": "documents",
                        "internal": False,
                        "summary": "Parse document",
                        "params": [],
                    },
                }
            },
        )

        assert _list_operations("attachments") == [
            {"action": "attachments.parse", "summary": "Parse attachment"}
        ]
        assert _list_operations("documents") == []


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

    def test_file_params_include_mcp_transport_instructions(self, monkeypatch):
        def fake_get_operation_info(_action: str):
            return {
                "action": "attachments.upload",
                "category": "attachments",
                "params": [
                    {
                        "name": "file",
                        "type": "file",
                        "required": True,
                        "description": "Upload payload",
                        "max_bytes": 10485760,
                    }
                ],
            }

        monkeypatch.setattr(discovery_module, "get_operation_info", fake_get_operation_info)

        result = _describe_operation("attachments.upload")
        file_param = result["params"][0]
        assert file_param["type"] == "file"
        assert file_param["mcp_transport"]["accepted_inputs"] == ["file_path", "content_base64"]
        assert file_param["mcp_transport"]["max_bytes"] == 10485760

    def test_dashboard_ai_policy_blocks_disallowed_describe(self, monkeypatch):
        import tepilora_mcp.tools.policy as policy

        def fake_get_operation_info(_action: str):
            return {
                "action": "documents.parse",
                "category": "documents",
                "params": [{"name": "file_path", "type": "string"}],
            }

        monkeypatch.setattr(policy, "TEPILORA_MCP_POLICY", "dashboard_ai")
        monkeypatch.setattr(discovery_module, "get_operation_info", fake_get_operation_info)

        result = _describe_operation("documents.parse")

        assert result["error"] == "MCP policy blocked this tool or operation."
        assert "documents.parse" in result["details"]

    def test_binary_response_includes_mcp_output_instructions(self, monkeypatch):
        def fake_get_operation_info(_action: str):
            return {
                "action": "attachments.download",
                "category": "attachments",
                "params": [{"name": "file_id", "type": "string", "required": True}],
                "response_transport": "binary",
            }

        monkeypatch.setattr(discovery_module, "get_operation_info", fake_get_operation_info)

        result = _describe_operation("attachments.download")

        assert result["response_transport"] == "binary"
        assert result["mcp_output"]["default"] == "content_base64"
        assert "output_file_path" in result["mcp_output"]["save_to_file"]
