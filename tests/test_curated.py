"""Tests for curated high-value tools."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from Tepilora import AsyncTepiloraClient

from tepilora_mcp.tools.curated import (
    _search_securities,
    _get_security_details,
    _get_price_history,
    _create_portfolio,
    _get_portfolio_returns,
    _run_analytics,
    _search_news,
    _screen_bonds,
    _get_yield_curve,
    _get_realtime_quotes,
    _get_realtime_quote,
    _get_realtime_chart,
    _get_realtime_calendar,
    _get_realtime_health,
)


class TestSearchSecurities:
    async def test_basic_search(self, mock_transport):
        result = await _search_securities("MSCI World")
        assert result is not None
        assert mock_transport.calls[-1]["payload"]["action"] == "securities.search"
        assert mock_transport.calls[-1]["payload"]["params"]["query"] == "MSCI World"
        assert mock_transport.calls[-1]["payload"]["params"]["limit"] == 20

    async def test_with_filters(self, mock_transport):
        await _search_securities("ETF", filters={"Currency": "EUR"})
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["filters"] == {"Currency": "EUR"}

    async def test_propagates_client_errors(self, mock_client):
        mock_client.call = AsyncMock(side_effect=RuntimeError("search failed"))
        result = await _search_securities("MSCI World")
        assert result["error"] == "Unexpected error while calling Tepilora API."
        assert "RuntimeError: search failed" in result["details"]


class TestGetSecurityDetails:
    async def test_basic(self, mock_transport):
        await _get_security_details("IE00B4L5Y983EURXMIL")
        assert mock_transport.calls[-1]["payload"]["action"] == "securities.details"


class TestGetPriceHistory:
    async def test_basic(self, mock_transport):
        await _get_price_history("IE00B4L5Y983EURXMIL", start_date="2024-01-01")
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "securities.history"
        assert payload["params"]["start_date"] == "2024-01-01"

    async def test_omits_optional_dates_when_not_provided(self, mock_transport):
        await _get_price_history("ID")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert "start_date" not in params
        assert "end_date" not in params

    async def test_includes_end_date_when_provided(self, mock_transport):
        await _get_price_history("ID", end_date="2024-12-31")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["end_date"] == "2024-12-31"


class TestCreatePortfolio:
    async def test_basic(self, mock_transport):
        await _create_portfolio("Test", weights={"ISIN1": 0.6, "ISIN2": 0.4}, start_date="2024-01-01")
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "portfolio.create"
        assert payload["params"]["name"] == "Test"
        assert payload["params"]["weights"] == {"ISIN1": 0.6, "ISIN2": 0.4}
        assert payload["params"]["start_date"] == "2024-01-01"

    async def test_omits_optional_when_not_provided(self, mock_transport):
        await _create_portfolio("name")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert "weights" not in params
        assert "start_date" not in params
        assert "input_data" not in params

    async def test_includes_weights_when_provided(self, mock_transport):
        await _create_portfolio("name", weights={"ISIN1": 1.0})
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["weights"] == {"ISIN1": 1.0}

    async def test_includes_input_data_when_provided(self, mock_transport):
        await _create_portfolio("name", input_data={"ISIN1": 1.0})
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["input_data"] == {"ISIN1": 1.0}


class TestGetPortfolioReturns:
    async def test_basic(self, mock_transport):
        await _get_portfolio_returns("abc-123")
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "portfolio.returns"
        assert payload["params"]["id"] == "abc-123"

    async def test_omits_optional_dates_when_not_provided(self, mock_transport):
        await _get_portfolio_returns("id")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert "start_date" not in params
        assert "end_date" not in params

    async def test_includes_optional_dates_when_provided(self, mock_transport):
        await _get_portfolio_returns("id", start_date="2024-01-01", end_date="2024-12-31")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["start_date"] == "2024-01-01"
        assert params["end_date"] == "2024-12-31"


class TestRunAnalytics:
    async def test_basic(self, mock_transport):
        await _run_analytics("rolling_volatility", identifiers="IE00B4L5Y983EURXMIL", params={"period": 252})
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "analytics.rolling_volatility"
        assert payload["params"]["identifiers"] == "IE00B4L5Y983EURXMIL"
        assert payload["params"]["period"] == 252

    async def test_identifiers_injected_when_provided(self, mock_transport):
        await _run_analytics("rolling_sharpe", identifiers="ID")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["identifiers"] == "ID"

    async def test_does_not_mutate_original_params(self, mock_transport):
        original_params = {"period": 252}
        await _run_analytics("rolling_volatility", identifiers="ID", params=original_params)
        assert original_params == {"period": 252}

        call_params = mock_transport.calls[-1]["payload"]["params"]
        assert call_params["period"] == 252
        assert call_params["identifiers"] == "ID"

    async def test_without_identifiers_uses_params_only(self, mock_transport):
        await _run_analytics("rolling_volatility", params={"period": 63})
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["period"] == 63
        assert "identifiers" not in params


class TestRunAnalyticsTruncation:
    """Tests for analytics summary-first truncation."""

    @pytest.fixture
    def analytics_mock_transport(self):
        """Mock transport that returns large analytics results."""
        calls = []

        def handler(request):
            payload = json.loads(request.content.decode("utf-8"))
            calls.append({"method": request.method, "url": str(request.url), "payload": payload})
            n = 100
            result = [{"D": f"2024-01-{i + 1:02d}", "V": float(i)} for i in range(n)]
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "action": payload.get("action", "unknown"),
                    "data": {"result": result, "action": payload.get("action", "unknown")},
                    "meta": {"request_id": "test", "execution_time_ms": 1, "timestamp": "t"},
                },
                headers={"content-type": "application/json"},
            )

        transport = httpx.MockTransport(handler)
        transport.calls = calls  # type: ignore[attr-defined]
        return transport

    @pytest.fixture
    def analytics_mock_client(self, analytics_mock_transport):
        return AsyncTepiloraClient(
            api_key="test-key",
            base_url="http://testserver",
            transport=analytics_mock_transport,
        )

    @pytest.fixture(autouse=True)
    def patch_analytics_client(self, analytics_mock_client):
        with patch(
            "tepilora_mcp.tools.generic._get_or_create_client", AsyncMock(return_value=analytics_mock_client)
        ):
            yield

    async def test_large_result_returns_summary_and_preview(self):
        result = await _run_analytics("rolling_volatility", identifiers="ID")
        assert "summary" in result
        assert result["summary"]["total_points"] == 100
        assert len(result["result"]) == 20
        assert "full_series_uri" in result
        assert result["full_series_uri"].startswith("analytics://rolling_volatility/")

    async def test_small_result_returns_full_data(self):
        result = await _run_analytics("rolling_volatility", identifiers="ID", max_points=200)
        assert "summary" not in result
        assert len(result["result"]) == 100

    async def test_custom_max_points(self):
        result = await _run_analytics("rolling_volatility", identifiers="ID", max_points=10)
        assert len(result["result"]) == 10
        assert result["summary"]["total_points"] == 100

    async def test_summary_stats_correct(self):
        result = await _run_analytics("rolling_volatility", identifiers="ID", max_points=5)
        summary = result["summary"]
        assert summary["V"]["min"] == 0.0
        assert summary["V"]["max"] == 99.0
        assert summary["V"]["last"] == 99.0
        assert summary["date_range"]["start"] == "2024-01-01"
        assert summary["date_range"]["end"] == "2024-01-100"

    async def test_resource_uri_retrievable(self):
        from tepilora_mcp.tools.analytics_store import get_result

        result = await _run_analytics("rolling_volatility", identifiers="ID")
        uri = result["full_series_uri"]
        rid = uri.split("/")[-1]
        full_data = get_result(rid)
        assert full_data is not None
        assert len(full_data) == 100


class TestSearchNews:
    async def test_basic(self, mock_transport):
        await _search_news("bitcoin")
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "news.search"
        assert payload["params"]["query"] == "bitcoin"


class TestScreenBonds:
    async def test_basic(self, mock_transport):
        await _screen_bonds(criteria={"min_yield": 4.0})
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "bonds.screen"

    async def test_omits_criteria_when_not_provided(self, mock_transport):
        await _screen_bonds()
        params = mock_transport.calls[-1]["payload"]["params"]
        assert "criteria" not in params

    async def test_includes_criteria_when_provided(self, mock_transport):
        await _screen_bonds(criteria={"min_yield": 4.0})
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["criteria"] == {"min_yield": 4.0}


class TestGetYieldCurve:
    async def test_basic(self, mock_transport):
        await _get_yield_curve("USD")
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "bonds.curve"
        assert payload["params"]["currency"] == "USD"

    async def test_omits_date_when_not_provided(self, mock_transport):
        await _get_yield_curve("EUR")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert "date" not in params

    async def test_includes_date_when_provided(self, mock_transport):
        await _get_yield_curve("EUR", date="2024-01-15")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["date"] == "2024-01-15"


class TestGetRealtimeQuotes:
    async def test_all_categories(self, mock_transport):
        await _get_realtime_quotes()
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "realtime.quotes"
        assert payload["params"] == {}

    async def test_filtered_by_category(self, mock_transport):
        await _get_realtime_quotes(category="idx")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["category"] == "idx"


class TestGetRealtimeQuote:
    async def test_by_symbol(self, mock_transport):
        await _get_realtime_quote(category="idx", symbol="DAX")
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "realtime.quote"
        assert payload["params"]["category"] == "idx"
        assert payload["params"]["symbol"] == "DAX"

    async def test_by_identifier(self, mock_transport):
        await _get_realtime_quote(identifier="DAXEURXETR")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["identifier"] == "DAXEURXETR"
        assert "category" not in params
        assert "symbol" not in params


class TestGetRealtimeChart:
    async def test_basic(self, mock_transport):
        await _get_realtime_chart(symbol="DAX")
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "realtime.chart"
        assert payload["params"]["symbol"] == "DAX"
        assert payload["params"]["timeframe"] == "1D"

    async def test_custom_timeframe(self, mock_transport):
        await _get_realtime_chart(symbol="SP500", timeframe="5D")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["timeframe"] == "5D"

    async def test_by_identifier(self, mock_transport):
        await _get_realtime_chart(identifier="DAXEURXETR", timeframe="1M")
        params = mock_transport.calls[-1]["payload"]["params"]
        assert params["identifier"] == "DAXEURXETR"
        assert "symbol" not in params


class TestGetRealtimeCalendar:
    async def test_basic(self, mock_transport):
        await _get_realtime_calendar()
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "realtime.calendar"

    async def test_returns_data(self, mock_transport):
        result = await _get_realtime_calendar()
        assert result is not None


class TestGetRealtimeHealth:
    async def test_basic(self, mock_transport):
        await _get_realtime_health()
        payload = mock_transport.calls[-1]["payload"]
        assert payload["action"] == "realtime.health"

    async def test_returns_data(self, mock_transport):
        result = await _get_realtime_health()
        assert result is not None
