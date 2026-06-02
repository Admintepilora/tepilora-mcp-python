"""Curated high-value tools with typed parameters."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .errors import handle_tool_errors
from .generic import _call_operation
from ..server import mcp


# --- Raw functions (testable directly) ---

@handle_tool_errors
async def _search_securities(
    query: str,
    limit: int = 20,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"query": query, "limit": limit}
    if filters:
        params["filters"] = filters
    return await _call_operation("securities.search", params=params)


@handle_tool_errors
async def _get_security_details(identifier: str) -> Dict[str, Any]:
    return await _call_operation("securities.details", params={"identifier": identifier})


@handle_tool_errors
async def _get_price_history(
    identifiers: Union[str, List[str]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"identifiers": identifiers, "limit": limit}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return await _call_operation("securities.history", params=params)


@handle_tool_errors
async def _create_portfolio(
    name: str,
    input_type: str = "fixed_weights",
    weights: Optional[Dict[str, float]] = None,
    start_date: Optional[str] = None,
    input_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"name": name, "input_type": input_type}
    if weights:
        params["weights"] = weights
    if start_date:
        params["start_date"] = start_date
    if input_data:
        params["input_data"] = input_data
    return await _call_operation("portfolio.create", params=params)


@handle_tool_errors
async def _save_query(
    name: str,
    category: str = "securities",
    type: str = "dynamic",
    visibility: str = "private",
    definition: Optional[Dict[str, Any]] = None,
    items: Optional[List[str]] = None,
    expression: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "name": name,
        "category": category,
        "type": type,
        "visibility": visibility,
    }
    if definition is not None:
        params["definition"] = definition
    if items is not None:
        params["items"] = items
    if expression is not None:
        params["expression"] = expression
    if description is not None:
        params["description"] = description
    if tags is not None:
        params["tags"] = tags
    return await _call_operation("queries.save", params=params)


@handle_tool_errors
async def _get_portfolio_returns(
    id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    return_method: str = "twr",
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"id": id, "return_method": return_method}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return await _call_operation("portfolio.returns", params=params)


@handle_tool_errors
async def _run_analytics(
    function: str,
    identifiers: Optional[Union[str, List[str]]] = None,
    params: Optional[Dict[str, Any]] = None,
    max_points: int = 20,
) -> Dict[str, Any]:
    call_params: Dict[str, Any] = dict(params or {})
    if identifiers:
        call_params["identifiers"] = identifiers
    data = await _call_operation(f"analytics.{function}", params=call_params)

    # Post-process: summary-first for large responses
    result = data.get("result") if isinstance(data, dict) else None
    if isinstance(result, list) and len(result) > max_points and max_points > 0:
        total = len(result)
        value_keys = [k for k in result[0] if k != "D"] if result and isinstance(result[0], dict) else []
        summary: Dict[str, Any] = {
            "total_points": total,
            "date_range": {
                "start": result[0].get("D") if isinstance(result[0], dict) else None,
                "end": result[-1].get("D") if isinstance(result[-1], dict) else None,
            },
        }
        for vk in value_keys:
            vals = [row[vk] for row in result if isinstance(row, dict) and isinstance(row.get(vk), (int, float))]
            if vals:
                summary[vk] = {
                    "last": vals[-1],
                    "min": min(vals),
                    "max": max(vals),
                    "mean": round(sum(vals) / len(vals), 6),
                }

        from .analytics_store import store_result
        rid = store_result(result, function)

        data["summary"] = summary
        data["result"] = result[-max_points:]
        data["full_series_uri"] = f"analytics://{function}/{rid}"
        data["_note"] = (
            f"Showing last {max_points} of {total} points. "
            "Full series available via resource URI."
        )

    return data


@handle_tool_errors
async def _search_news(
    query: str,
    limit: int = 20,
) -> Dict[str, Any]:
    return await _call_operation("news.search", params={
        "query": query,
        "limit": limit,
    })


@handle_tool_errors
async def _screen_bonds(
    criteria: Optional[Dict[str, Any]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"limit": limit}
    if criteria:
        params["criteria"] = criteria
    return await _call_operation("bonds.screen", params=params)


@handle_tool_errors
async def _get_yield_curve(
    currency: str = "EUR",
    date: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"currency": currency}
    if date:
        params["date"] = date
    return await _call_operation("bonds.curve", params=params)


@handle_tool_errors
async def _get_realtime_quotes(
    category: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if category:
        params["category"] = category
    return await _call_operation("realtime.quotes", params=params)


@handle_tool_errors
async def _get_realtime_quote(
    category: Optional[str] = None,
    symbol: Optional[str] = None,
    identifier: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if category:
        params["category"] = category
    if symbol:
        params["symbol"] = symbol
    if identifier:
        params["identifier"] = identifier
    return await _call_operation("realtime.quote", params=params)


@handle_tool_errors
async def _get_realtime_chart(
    symbol: Optional[str] = None,
    identifier: Optional[str] = None,
    timeframe: str = "1D",
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"timeframe": timeframe}
    if symbol:
        params["symbol"] = symbol
    if identifier:
        params["identifier"] = identifier
    return await _call_operation("realtime.chart", params=params)


@handle_tool_errors
async def _get_realtime_calendar() -> Dict[str, Any]:
    return await _call_operation("realtime.calendar", params={})


@handle_tool_errors
async def _get_realtime_health() -> Dict[str, Any]:
    return await _call_operation("realtime.health", params={})


# --- MCP tool registration ---

@mcp.tool
async def search_securities(
    query: str,
    limit: int = 20,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Search for securities (stocks, ETFs, bonds, funds) by name, ISIN, or ticker.

    Args:
        query: Search text (e.g. "MSCI World", "Apple", "IE00B4L5Y983")
        limit: Maximum results to return (default 20)
        filters: Optional filters (e.g. {"Currency": "EUR", "TepiloraType": "ETF"})
    """
    return await _search_securities(query, limit, filters)


@mcp.tool
async def get_security_details(identifier: str) -> Dict[str, Any]:
    """Get detailed information about a specific security.

    Args:
        identifier: Security identifier (e.g. "IE00B4L5Y983EURXMIL")
    """
    return await _get_security_details(identifier)


@mcp.tool
async def get_price_history(
    identifiers: Union[str, List[str]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """Get historical price data for one or more securities.

    Args:
        identifiers: One or more security identifiers
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        limit: Maximum data points (default 1000)
    """
    return await _get_price_history(identifiers, start_date, end_date, limit)


@mcp.tool
async def create_portfolio(
    name: str,
    input_type: str = "fixed_weights",
    weights: Optional[Dict[str, float]] = None,
    start_date: Optional[str] = None,
    input_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a new portfolio.

    Args:
        name: Portfolio name
        input_type: Type of input (e.g. "fixed_weights", "drifting_weights", "holdings", "values", "trades")
        weights: Portfolio weights (e.g. {"ISIN1": 0.6, "ISIN2": 0.4}). Required for fixed_weights.
        start_date: Start date (YYYY-MM-DD). Required for fixed_weights.
        input_data: Alternative input data dict (format depends on input_type)
    """
    return await _create_portfolio(name, input_type, weights, start_date, input_data)


@mcp.tool
async def save_query(
    name: str,
    category: str = "securities",
    type: str = "dynamic",
    visibility: str = "private",
    definition: Optional[Dict[str, Any]] = None,
    items: Optional[List[str]] = None,
    expression: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Save a reusable query definition.

    Args:
        name: Query name, up to 100 chars; letters, numbers, underscore, and hyphen.
        category: Query category: "securities" (default), "news", or "publications".
        type: Query type: "dynamic" (filters+text), "static" (TepiloraCode list), or "composite" (set algebra).
        visibility: "private" (default, owner-only) or "workspace" (requires workspace context).
        definition: For type="dynamic": {"query": str, "filters": dict}.
        items: For type="static": list of TepiloraCode strings.
        expression: For type="composite": set-algebra expression like "[A] + [B] - [C]".
        description: Optional description, up to 500 chars.
        tags: Optional list of tags.
    """
    return await _save_query(
        name,
        category,
        type,
        visibility,
        definition,
        items,
        expression,
        description,
        tags,
    )


@mcp.tool
async def get_portfolio_returns(
    id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    return_method: str = "twr",
) -> Dict[str, Any]:
    """Get portfolio return data.

    Args:
        id: Portfolio ID
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        return_method: Return calculation method ("twr" or "mwr")
    """
    return await _get_portfolio_returns(id, start_date, end_date, return_method)


@mcp.tool
async def run_analytics(
    function: str,
    identifiers: Optional[Union[str, List[str]]] = None,
    params: Optional[Dict[str, Any]] = None,
    max_points: int = 20,
) -> Dict[str, Any]:
    """Run any analytics function. Returns summary + preview by default.

    There are 68 analytics functions. Use `list_operations("analytics")` to see them all.

    Args:
        function: Analytics function name (e.g. "rolling_volatility", "rolling_sharpe")
        identifiers: Security identifier(s) to analyze
        params: Function-specific parameters (e.g. {"period": 252, "rf": 0.02})
        max_points: Max data points in response (default 20, -1 for all). Full series available as MCP resource.
    """
    return await _run_analytics(function, identifiers, params, max_points)


@mcp.tool
async def search_news(
    query: str,
    limit: int = 20,
) -> Dict[str, Any]:
    """Search financial news articles.

    Args:
        query: Search text (e.g. "bitcoin", "interest rates", "AAPL earnings")
        limit: Maximum results (default 20)
    """
    return await _search_news(query, limit)


@mcp.tool
async def screen_bonds(
    criteria: Optional[Dict[str, Any]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Screen bonds by criteria (yield, duration, rating, etc.).

    Args:
        criteria: Screening criteria (e.g. {"min_yield": 4.0, "max_duration": 5.0})
        limit: Maximum results (default 50)
    """
    return await _screen_bonds(criteria, limit)


@mcp.tool
async def get_yield_curve(
    currency: str = "EUR",
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Get the yield curve for a currency.

    Args:
        currency: Currency code (e.g. "EUR", "USD", "GBP")
        date: Date for historical curve (YYYY-MM-DD), defaults to latest
    """
    return await _get_yield_curve(currency, date)


@mcp.tool
async def get_realtime_quotes(
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Get realtime quotes for a market category.

    Args:
        category: Asset category filter: idx, bond, fx, cmd, crypto, futures, stock. Omit for all.
    """
    return await _get_realtime_quotes(category)


@mcp.tool
async def get_realtime_quote(
    category: Optional[str] = None,
    symbol: Optional[str] = None,
    identifier: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a single realtime quote.

    Args:
        category: Asset category: idx, bond, fx, cmd, crypto, futures, stock (required if no identifier)
        symbol: Symbol identifier e.g. DAX, EURUSD, BTC (required if no identifier)
        identifier: TepiloraCode — resolves category+symbol automatically
    """
    return await _get_realtime_quote(category, symbol, identifier)


@mcp.tool
async def get_realtime_chart(
    symbol: Optional[str] = None,
    identifier: Optional[str] = None,
    timeframe: str = "1D",
) -> Dict[str, Any]:
    """Get realtime chart data (intraday OHLC).

    Args:
        symbol: Symbol identifier (required if no identifier)
        identifier: TepiloraCode — resolves symbol automatically
        timeframe: Timeframe: 1D, 5D, 1M, 1Y (default 1D)
    """
    return await _get_realtime_chart(symbol, identifier, timeframe)


@mcp.tool
async def get_realtime_calendar() -> Dict[str, Any]:
    """Get realtime economic calendar with upcoming and recent macro events."""
    return await _get_realtime_calendar()


@mcp.tool
async def get_realtime_health() -> Dict[str, Any]:
    """Get data source health status (gfinance, tradingview, yahoo, reuters)."""
    return await _get_realtime_health()


@mcp.resource("analytics://{function}/{rid}")
def analytics_full_series(function: str, rid: str) -> Any:
    """Full analytics time series data."""
    from .analytics_store import get_result

    data = get_result(rid)
    if data is None:
        return {"error": "Resource expired or not found", "ttl_minutes": 15}
    return data
