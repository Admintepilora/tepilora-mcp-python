"""In-memory storage for full analytics time series results."""

from __future__ import annotations

import secrets
import time
from typing import Any, Dict, List, Optional

_RESULTS: Dict[str, Dict[str, Any]] = {}


def store_result(data: List[Dict[str, Any]], function: str, ttl: int = 900) -> str:
    """Store full analytics data and return a short resource id."""
    _evict_expired()
    now = time.time()
    rid = secrets.token_hex(6)
    while rid in _RESULTS:
        rid = secrets.token_hex(6)
    _RESULTS[rid] = {
        "id": rid,
        "function": function,
        "data": data,
        "created_at": now,
        "expires_at": now + max(ttl, 0),
    }
    return rid


def get_result(rid: str) -> Optional[List[Dict[str, Any]]]:
    """Get stored analytics data by resource id."""
    _evict_expired()
    entry = _RESULTS.get(rid)
    if entry is None:
        return None
    return entry["data"]


def list_results() -> List[Dict[str, Any]]:
    """List active stored analytics result metadata."""
    _evict_expired()
    return [
        {
            "id": entry["id"],
            "function": entry["function"],
            "created_at": entry["created_at"],
            "expires_at": entry["expires_at"],
            "total_points": len(entry["data"]),
        }
        for entry in _RESULTS.values()
    ]


def _evict_expired() -> None:
    """Delete expired in-memory entries."""
    now = time.time()
    expired_ids = [rid for rid, entry in _RESULTS.items() if entry["expires_at"] <= now]
    for rid in expired_ids:
        _RESULTS.pop(rid, None)
