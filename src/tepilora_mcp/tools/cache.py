"""Async TTL cache for MCP tool responses."""

from __future__ import annotations

import asyncio
import copy
import time
from collections import OrderedDict
from typing import Any, Dict, FrozenSet, Hashable, Optional, Tuple

from ..config import TEPILORA_MCP_CACHE_MAX_SIZE, TEPILORA_MCP_CACHE_TTL

_NON_CACHEABLE = {"create", "update", "delete", "remove", "add", "set", "import", "exec", "run", "evaluate"}

CacheKey = Tuple[str, FrozenSet[Tuple[str, Hashable]]]


def _freeze(value: Any) -> Hashable:
    if isinstance(value, dict):
        return frozenset((str(k), _freeze(v)) for k, v in value.items())
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return frozenset(_freeze(v) for v in value)
    return cast_hashable(value)


def cast_hashable(value: Any) -> Hashable:
    if isinstance(value, (str, int, float, bool, bytes, type(None))):
        return value
    return repr(value)


def make_cache_key(action: str, params: Optional[Dict[str, Any]]) -> CacheKey:
    frozen_params = frozenset((str(k), _freeze(v)) for k, v in (params or {}).items())
    return (action, frozen_params)


def is_cacheable_action(action: str) -> bool:
    tail = action.split(".")[-1].lower()
    for prefix in _NON_CACHEABLE:
        if tail == prefix:
            return False
        if tail.startswith(f"{prefix}_"):
            return False
        if tail.startswith(f"{prefix}-"):
            return False
    return True


class AsyncTTLCache:
    def __init__(self, ttl_seconds: int, max_size: int) -> None:
        self._ttl_seconds = max(0, ttl_seconds)
        self._max_size = max(1, max_size)
        self._store: "OrderedDict[CacheKey, Tuple[float, Dict[str, Any]]]" = OrderedDict()
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self._ttl_seconds > 0

    async def get(self, key: CacheKey) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        now = time.monotonic()
        async with self._lock:
            cached = self._store.get(key)
            if cached is None:
                return None
            expires_at, value = cached
            if expires_at <= now:
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return copy.deepcopy(value)

    async def set(self, key: CacheKey, value: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        expires_at = time.monotonic() + self._ttl_seconds
        async with self._lock:
            self._store[key] = (expires_at, copy.deepcopy(value))
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    async def stats(self) -> Dict[str, Any]:
        async with self._lock:
            return {
                "enabled": self.enabled,
                "ttl_seconds": self._ttl_seconds,
                "max_size": self._max_size,
                "size": len(self._store),
            }


CACHE = AsyncTTLCache(
    ttl_seconds=TEPILORA_MCP_CACHE_TTL,
    max_size=TEPILORA_MCP_CACHE_MAX_SIZE,
)
