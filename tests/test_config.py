"""Tests for MCP environment configuration."""

import importlib


def reload_config(monkeypatch, *, canonical=None, legacy=None):
    if canonical is None:
        monkeypatch.delenv("TEPILORA_MCP_API_KEY", raising=False)
    else:
        monkeypatch.setenv("TEPILORA_MCP_API_KEY", canonical)

    if legacy is None:
        monkeypatch.delenv("TEPILORA_API_KEY", raising=False)
    else:
        monkeypatch.setenv("TEPILORA_API_KEY", legacy)

    import tepilora_mcp.config as config

    return importlib.reload(config)


def test_mcp_api_key_prefers_canonical_env(monkeypatch):
    config = reload_config(monkeypatch, canonical="canonical-key", legacy="legacy-key")
    assert config.TEPILORA_MCP_API_KEY == "canonical-key"
    assert config.TEPILORA_API_KEY == "canonical-key"


def test_legacy_api_key_alias_warns(monkeypatch):
    with monkeypatch.context() as m:
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            config = reload_config(m, legacy="legacy-key")

    assert config.TEPILORA_MCP_API_KEY == "legacy-key"
    assert config.TEPILORA_API_KEY == "legacy-key"
    assert any("TEPILORA_API_KEY is deprecated" in str(item.message) for item in caught)
