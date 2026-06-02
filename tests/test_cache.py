"""Tests for operation result caching."""

import asyncio

from tepilora_mcp.tools.cache import AsyncTTLCache, is_cacheable_action, make_cache_key
from tepilora_mcp.tools.generic import _call_operation, _clear_cache


class TestCacheHelpers:
    def test_make_cache_key_is_order_independent(self):
        key1 = make_cache_key("securities.search", {"query": "MSCI", "limit": 10})
        key2 = make_cache_key("securities.search", {"limit": 10, "query": "MSCI"})
        assert key1 == key2

    def test_non_cacheable_prefix_detection(self):
        assert is_cacheable_action("securities.search") is True
        assert is_cacheable_action("portfolio.create") is False
        assert is_cacheable_action("workflows.run_report") is False
        assert is_cacheable_action("alerts.evaluate") is False


class TestAsyncTTLCache:
    async def test_set_get_and_expire(self):
        cache = AsyncTTLCache(ttl_seconds=1, max_size=10)
        key = make_cache_key("securities.search", {"query": "MSCI"})
        await cache.set(key, {"result": 1})
        assert await cache.get(key) == {"result": 1}
        await asyncio.sleep(1.1)
        assert await cache.get(key) is None

    async def test_lru_eviction(self):
        cache = AsyncTTLCache(ttl_seconds=100, max_size=2)
        key1 = make_cache_key("a.one", {})
        key2 = make_cache_key("a.two", {})
        key3 = make_cache_key("a.three", {})
        await cache.set(key1, {"v": 1})
        await cache.set(key2, {"v": 2})
        assert await cache.get(key1) == {"v": 1}  # touch key1 so key2 becomes LRU
        await cache.set(key3, {"v": 3})
        assert await cache.get(key1) == {"v": 1}
        assert await cache.get(key2) is None
        assert await cache.get(key3) == {"v": 3}


class TestIntegration:
    async def test_cache_hit_avoids_second_sdk_call(self, mock_transport):
        params = {"query": "MSCI", "limit": 10}
        first = await _call_operation("securities.search", params)
        second = await _call_operation("securities.search", params)
        assert first == second
        assert len(mock_transport.calls) == 1

    async def test_non_cacheable_actions_always_call_sdk(self, mock_transport):
        params = {"name": "My Portfolio"}
        await _call_operation("portfolio.create", params)
        await _call_operation("portfolio.create", params)
        assert len(mock_transport.calls) == 2

    async def test_clear_cache_tool(self, mock_transport):
        await _call_operation("securities.search", {"query": "MSCI"})
        result = await _clear_cache()
        assert result["cleared_entries"] >= 1
        assert result["cache"]["size"] == 0
        await _call_operation("securities.search", {"query": "MSCI"})
        assert len(mock_transport.calls) == 2
