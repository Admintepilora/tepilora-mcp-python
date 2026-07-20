"""Tests for generic call_operation tool."""

import base64
import importlib
import inspect
from unittest.mock import AsyncMock, patch

from Tepilora._schema import SCHEMA
from tepilora_mcp.tools import generic as generic_module
from tepilora_mcp.tools.generic import (
    _call_operation,
    _call_operation_arrow_stream,
    call_operation,
)


def _schema_with_file_operation():
    return {
        "operations": {
            "attachments.upload": {
                "action": "attachments.upload",
                "category": "attachments",
                "operation": "upload",
                "params": [
                    {
                        "name": "file",
                        "type": "file",
                        "required": True,
                        "max_bytes": 16,
                    },
                    {"name": "filename", "type": "string", "required": True},
                    {"name": "source", "type": "string", "required": False},
                ],
            },
            "attachments.list": {
                "action": "attachments.list",
                "category": "attachments",
                "operation": "list",
                "params": [
                    {"name": "limit", "type": "int", "required": False},
                ],
            },
            "attachments.download": {
                "action": "attachments.download",
                "category": "attachments",
                "operation": "download",
                "response_transport": "binary",
                "params": [
                    {"name": "file_id", "type": "string", "required": True},
                ],
            },
        }
    }


class _Response:
    def __init__(self, data):
        self.data = data


class _BinaryMeta:
    request_id = "req-binary"
    execution_time_ms = 5
    total_count = None
    row_count = None


class _BinaryResponse:
    action = "attachments.download"
    format = "binary"
    content_type = "application/pdf"
    content = b"%PDF-1.4\n"
    meta = _BinaryMeta()
    headers = {
        "content-type": "application/pdf",
        "content-disposition": 'attachment; filename="statement.pdf"',
        "x-tepilora-request-id": "req-binary",
    }


def _multipart_mock_was_called(mock_client) -> bool:
    return bool(getattr(getattr(mock_client, "call_multipart", None), "called", False))


class TestCallOperation:
    def test_tool_docstring_uses_schema_count(self):
        expected = len(SCHEMA.get("operations", {}))
        description = getattr(call_operation, "description", None) or call_operation.__doc__ or ""
        assert f"{expected} operations" in description

    def test_public_call_operation_is_async_export(self):
        assert inspect.iscoroutinefunction(call_operation)
        assert "call_operation" in generic_module.__all__

    async def test_public_call_operation_delegates_to_private(self):
        with patch.object(
            generic_module,
            "_call_operation",
            AsyncMock(return_value={"ok": True}),
        ) as mock_call:
            result = await generic_module.call_operation("securities.search", {"limit": 1})

        assert result == {"ok": True}
        mock_call.assert_awaited_once_with("securities.search", {"limit": 1})

    async def test_get_client_singleton_uses_config_values(self):
        import tepilora_mcp.tools.generic as generic_module

        importlib.reload(generic_module)

        fake_client = object()
        generic_module._client = None
        generic_module._resolved_url = None
        try:
            async def fake_resolve():
                return "https://example.test"

            with patch.object(generic_module, "TEPILORA_MCP_API_KEY", "api-key-test"), \
                 patch.object(generic_module, "TEPILORA_MCP_TIMEOUT", 12.5), \
                 patch.object(generic_module, "_resolve_base_url", fake_resolve), \
                 patch.object(generic_module, "AsyncTepiloraClient", return_value=fake_client) as mock_ctor:
                first = await generic_module._get_or_create_client()
                second = await generic_module._get_or_create_client()

            assert first is fake_client
            assert second is first
            mock_ctor.assert_called_once_with(
                api_key="api-key-test",
                base_url="https://example.test",
                timeout=12.5,
            )
        finally:
            generic_module._client = None
            generic_module._resolved_url = None

    async def test_calls_correct_action(self, mock_client, mock_transport):
        result = await _call_operation("securities.search", params={"query": "MSCI", "limit": 10})
        assert result is not None

        calls = mock_transport.calls
        assert len(calls) == 1
        assert calls[0]["payload"]["action"] == "securities.search"
        assert calls[0]["payload"]["params"]["query"] == "MSCI"

    async def test_calls_without_params(self, mock_client, mock_transport):
        result = await _call_operation("analytics.list")
        assert result is not None

        calls = mock_transport.calls
        assert len(calls) == 1
        assert calls[0]["payload"]["action"] == "analytics.list"

    async def test_params_none_sends_empty_dict(self, mock_transport):
        await _call_operation("some.action", params=None)

        calls = mock_transport.calls
        assert len(calls) == 1
        assert calls[0]["payload"]["action"] == "some.action"
        assert calls[0]["payload"]["params"] == {}

    async def test_returns_structured_error_on_client_exception(self, mock_client):
        mock_client.call = AsyncMock(side_effect=RuntimeError("boom"))
        result = await _call_operation("some.action", params={"x": 1})
        assert result["error"] == "Unexpected error while calling Tepilora API."
        assert "RuntimeError: boom" in result["details"]

    async def test_arrow_stream_operation_returns_base64_payload(self, mock_client):
        class _Meta:
            request_id = "req-1"
            execution_time_ms = 9
            total_count = 2
            row_count = 2

        class _Resp:
            format = "arrow"
            content_type = "application/vnd.apache.arrow.stream"
            content = b"abc"
            meta = _Meta()
            headers = {"x-test": "1"}

        mock_client.call_arrow_ipc_stream = AsyncMock(return_value=_Resp())
        result = await _call_operation_arrow_stream("securities.search", {"query": "MSCI"})
        assert result["format"] == "arrow"
        assert result["size_bytes"] == 3
        assert result["content_base64"] == "YWJj"

    async def test_file_operation_accepts_file_path(self, tmp_path, monkeypatch, mock_client):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        payload_path = tmp_path / "notes.txt"
        payload_path.write_bytes(b"hello path")
        mock_client.call_multipart = AsyncMock(return_value=_Response({"ok": True}))

        result = await _call_operation(
            "attachments.upload",
            params={"file_path": str(payload_path), "source": "pytest"},
        )

        assert result == {"ok": True}
        mock_client.call_multipart.assert_awaited_once()
        _, kwargs = mock_client.call_multipart.await_args
        assert kwargs["file_fields"] == ("file",)
        assert kwargs["params"]["file"] == b"hello path"
        assert kwargs["params"]["filename"] == "notes.txt"
        assert kwargs["params"]["source"] == "pytest"
        assert "file_path" not in kwargs["params"]

    async def test_file_operation_accepts_content_base64(self, monkeypatch, mock_client):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        mock_client.call_multipart = AsyncMock(return_value=_Response({"ok": True}))
        encoded = base64.b64encode(b"hello b64").decode("ascii")

        result = await _call_operation(
            "attachments.upload",
            params={"content_base64": encoded, "filename": "payload.txt"},
        )

        assert result == {"ok": True}
        _, kwargs = mock_client.call_multipart.await_args
        assert kwargs["file_fields"] == ("file",)
        assert kwargs["params"]["file"] == b"hello b64"
        assert kwargs["params"]["filename"] == "payload.txt"
        assert "content_base64" not in kwargs["params"]

    async def test_file_operation_rejects_multiple_sources(self, tmp_path, monkeypatch, mock_client):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        payload_path = tmp_path / "notes.txt"
        payload_path.write_bytes(b"hello")

        result = await _call_operation(
            "attachments.upload",
            params={
                "file_path": str(payload_path),
                "content_base64": base64.b64encode(b"hello").decode("ascii"),
            },
        )

        assert result["error"] == "Invalid parameters: verify required fields and value formats."
        assert "accepts exactly one source" in result["details"]
        assert not _multipart_mock_was_called(mock_client)

    async def test_file_operation_rejects_traversal_path(self, tmp_path, monkeypatch, mock_client):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        result = await _call_operation(
            "attachments.upload",
            params={"file_path": str(tmp_path / ".." / "notes.txt")},
        )

        assert result["error"] == "Invalid parameters: verify required fields and value formats."
        assert "must not contain '..'" in result["details"]
        assert not _multipart_mock_was_called(mock_client)

    async def test_file_operation_rejects_oversize_base64(self, monkeypatch, mock_client):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        encoded = base64.b64encode(b"x" * 17).decode("ascii")

        result = await _call_operation(
            "attachments.upload",
            params={"content_base64": encoded, "filename": "large.txt"},
        )

        assert result["error"] == "Invalid parameters: verify required fields and value formats."
        assert "exceeds max size" in result["details"]
        assert not _multipart_mock_was_called(mock_client)

    async def test_file_companion_operation_remains_json(self, monkeypatch, mock_transport):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())

        result = await _call_operation("attachments.list", params={"limit": 5})

        assert result is not None
        assert len(mock_transport.calls) == 1
        assert mock_transport.calls[0]["payload"]["action"] == "attachments.list"
        assert mock_transport.calls[0]["payload"]["params"] == {"limit": 5}

    async def test_binary_operation_returns_base64_by_default(self, monkeypatch, mock_client):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        mock_client.call_binary = AsyncMock(return_value=_BinaryResponse())

        result = await _call_operation("attachments.download", params={"file_id": "att_1"})

        assert result["action"] == "attachments.download"
        assert result["content_type"] == "application/pdf"
        assert result["filename"] == "statement.pdf"
        assert result["size_bytes"] == len(b"%PDF-1.4\n")
        assert result["content_base64"] == base64.b64encode(b"%PDF-1.4\n").decode("ascii")
        mock_client.call_binary.assert_awaited_once_with("attachments.download", params={"file_id": "att_1"})

    async def test_binary_operation_writes_output_file(self, tmp_path, monkeypatch, mock_client):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        mock_client.call_binary = AsyncMock(return_value=_BinaryResponse())
        output_path = tmp_path / "statement.pdf"

        result = await _call_operation(
            "attachments.download",
            params={"file_id": "att_1", "output_file_path": str(output_path)},
        )

        assert output_path.read_bytes() == b"%PDF-1.4\n"
        assert result["output_file_path"] == str(output_path)
        assert "content_base64" not in result
        _, kwargs = mock_client.call_binary.await_args
        assert kwargs["params"] == {"file_id": "att_1"}

    async def test_binary_operation_rejects_traversal_output_path(self, tmp_path, monkeypatch, mock_client):
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        mock_client.call_binary = AsyncMock(return_value=_BinaryResponse())

        result = await _call_operation(
            "attachments.download",
            params={"file_id": "att_1", "output_file_path": str(tmp_path / ".." / "statement.pdf")},
        )

        assert result["error"] == "Invalid parameters: verify required fields and value formats."
        assert "must not contain '..'" in result["details"]
        mock_client.call_binary.assert_not_awaited()

    async def test_dashboard_ai_policy_blocks_documents_parse_before_sdk(self, monkeypatch, mock_transport):
        import tepilora_mcp.tools.policy as policy

        monkeypatch.setattr(policy, "TEPILORA_MCP_POLICY", "dashboard_ai")

        result = await _call_operation("documents.parse", params={"file_path": "/tmp/secret.pdf"})

        assert result["error"] == "MCP policy blocked this tool or operation."
        assert "documents.parse" in result["details"]
        assert mock_transport.calls == []

    async def test_dashboard_ai_policy_blocks_attachment_upload_before_file_read(
        self, tmp_path, monkeypatch, mock_client
    ):
        import tepilora_mcp.tools.policy as policy

        monkeypatch.setattr(policy, "TEPILORA_MCP_POLICY", "dashboard_ai")
        monkeypatch.setattr(generic_module, "SCHEMA", _schema_with_file_operation())
        payload_path = tmp_path / "notes.txt"
        payload_path.write_bytes(b"hello")

        result = await _call_operation(
            "attachments.upload",
            params={"file_path": str(payload_path), "filename": "notes.txt"},
        )

        assert result["error"] == "MCP policy blocked this tool or operation."
        assert "attachments.upload" in result["details"]
        assert not _multipart_mock_was_called(mock_client)

    async def test_dashboard_ai_policy_allows_attachment_parse(self, monkeypatch, mock_transport):
        import tepilora_mcp.tools.policy as policy

        monkeypatch.setattr(policy, "TEPILORA_MCP_POLICY", "dashboard_ai")

        result = await _call_operation("attachments.parse", params={"file_id": "att_1"})

        assert result["action"] == "attachments.parse"
        assert mock_transport.calls[-1]["payload"]["action"] == "attachments.parse"

    async def test_dashboard_ai_policy_blocks_arrow_for_disallowed_action(self, monkeypatch, mock_client):
        import tepilora_mcp.tools.policy as policy

        monkeypatch.setattr(policy, "TEPILORA_MCP_POLICY", "dashboard_ai")
        mock_client.call_arrow_ipc_stream = AsyncMock()

        result = await _call_operation_arrow_stream("documents.parse", {"file_path": "/tmp/secret.pdf"})

        assert result["error"] == "MCP policy blocked this tool or operation."
        assert "documents.parse" in result["details"]
        mock_client.call_arrow_ipc_stream.assert_not_awaited()

    async def test_dashboard_ai_policy_blocks_mutating_local_tools(self, monkeypatch):
        import tepilora_mcp.tools.policy as policy

        monkeypatch.setattr(policy, "TEPILORA_MCP_POLICY", "dashboard_ai")

        clear_result = await generic_module._clear_cache()
        reset_result = await generic_module._reset_credits()
        usage_result = await generic_module._get_credit_usage()

        assert clear_result["error"] == "MCP policy blocked this tool or operation."
        assert reset_result["error"] == "MCP policy blocked this tool or operation."
        assert "used_credits" in usage_result
