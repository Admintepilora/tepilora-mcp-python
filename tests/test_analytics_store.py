"""Tests for analytics in-memory result storage."""

from __future__ import annotations

from tepilora_mcp.tools import analytics_store


def _sample_data(points: int = 2):
    return [{"D": f"2024-01-{i + 1:02d}", "V": float(i)} for i in range(points)]


class TestAnalyticsStore:
    def setup_method(self):
        analytics_store._RESULTS.clear()

    def teardown_method(self):
        analytics_store._RESULTS.clear()

    def test_store_and_retrieve(self):
        data = _sample_data(3)
        rid = analytics_store.store_result(data, "rolling_volatility")

        assert len(rid) == 12
        assert analytics_store.get_result(rid) == data

    def test_expired_entry_returns_none(self, monkeypatch):
        current_time = [1000.0]
        monkeypatch.setattr(analytics_store.time, "time", lambda: current_time[0])

        rid = analytics_store.store_result(_sample_data(1), "rolling_volatility", ttl=1)
        current_time[0] = 1002.0

        assert analytics_store.get_result(rid) is None

    def test_evict_removes_expired(self, monkeypatch):
        current_time = [2000.0]
        monkeypatch.setattr(analytics_store.time, "time", lambda: current_time[0])

        expired_rid = analytics_store.store_result(_sample_data(1), "f1", ttl=1)
        active_rid = analytics_store.store_result(_sample_data(2), "f2", ttl=10)
        current_time[0] = 2002.0

        analytics_store._evict_expired()

        assert expired_rid not in analytics_store._RESULTS
        assert active_rid in analytics_store._RESULTS

    def test_list_results(self):
        rid_one = analytics_store.store_result(_sample_data(1), "rolling_volatility")
        rid_two = analytics_store.store_result(_sample_data(4), "rolling_sharpe")

        entries = analytics_store.list_results()
        by_id = {entry["id"]: entry for entry in entries}

        assert rid_one in by_id
        assert rid_two in by_id
        assert by_id[rid_one]["function"] == "rolling_volatility"
        assert by_id[rid_one]["total_points"] == 1
        assert by_id[rid_two]["function"] == "rolling_sharpe"
        assert by_id[rid_two]["total_points"] == 4
