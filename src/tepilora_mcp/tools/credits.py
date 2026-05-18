"""Session credit tracking for Tepilora MCP calls."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from Tepilora._schema import SCHEMA

from ..config import TEPILORA_MCP_CREDIT_LIMIT


def _build_credit_map() -> Dict[str, int]:
    credit_map: Dict[str, int] = {}
    for action, op in SCHEMA.get("operations", {}).items():
        raw = op.get("credits", 1)
        try:
            credit_map[action] = max(0, int(raw))
        except (TypeError, ValueError):
            credit_map[action] = 1
    return credit_map


_ACTION_CREDITS = _build_credit_map()


class CreditTracker:
    def __init__(self, credit_limit: int) -> None:
        self._credit_limit = max(0, credit_limit)
        self._used_credits = 0
        self._calls = 0
        self._lock = asyncio.Lock()

    def get_cost(self, action: str) -> int:
        return _ACTION_CREDITS.get(action, 1)

    async def consume_for_action(self, action: str) -> Dict[str, Any]:
        cost = self.get_cost(action)
        async with self._lock:
            if self._credit_limit > 0 and self._used_credits + cost > self._credit_limit:
                remaining = self._credit_limit - self._used_credits
                return {
                    "allowed": False,
                    "error": (
                        "Credit limit reached: this session cannot run more Tepilora operations. "
                        "Use `reset_credits` or raise `TEPILORA_MCP_CREDIT_LIMIT`."
                    ),
                    "details": (
                        f"action={action}, cost={cost}, used={self._used_credits}, "
                        f"limit={self._credit_limit}, remaining={max(0, remaining)}"
                    ),
                }
            self._used_credits += cost
            self._calls += 1
            return {"allowed": True, "cost": cost}

    async def reset(self) -> Dict[str, Any]:
        async with self._lock:
            previous = {
                "used_credits": self._used_credits,
                "calls": self._calls,
            }
            self._used_credits = 0
            self._calls = 0
            return previous

    async def usage(self) -> Dict[str, Any]:
        async with self._lock:
            remaining = None
            if self._credit_limit > 0:
                remaining = max(0, self._credit_limit - self._used_credits)
            return {
                "used_credits": self._used_credits,
                "total_calls": self._calls,
                "credit_limit": self._credit_limit,
                "remaining_credits": remaining,
                "unlimited": self._credit_limit == 0,
            }


CREDITS = CreditTracker(credit_limit=TEPILORA_MCP_CREDIT_LIMIT)
