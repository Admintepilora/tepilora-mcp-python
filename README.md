# Tepilora MCP Server

[![PyPI](https://img.shields.io/pypi/v/tepilora-mcp)](https://pypi.org/project/tepilora-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/tepilora-mcp)](https://pypi.org/project/tepilora-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

MCP (Model Context Protocol) server for the [Tepilora](https://tepiloradata.com) financial analytics ecosystem.

Give any AI assistant (Claude, Codex, Cursor, Copilot) direct access to **279 financial analytics operations** across **28 categories** — securities search, portfolio optimization, risk analytics, realtime quotes, bonds, macro indicators, ESG, reporting, and more.

> **Why Tepilora MCP?** One API key, one MCP server, and your AI assistant can search 600K+ securities, build portfolios, run 75+ analytics functions, generate fund sheets, and stream realtime market data — no custom code needed.

## Features

- **22 default tools** (discovery + generic + admin + curated), full mode for all operations
- **Async client** — non-blocking, optimized for MCP
- **Smart caching** — TTL + LRU, skips mutating operations
- **Credit tracking** — per-session usage limits
- **Analytics summary-first** — large time series truncated to preview + MCP resource for full data
- **Arrow IPC streaming** — binary format for large result sets

## Install

```bash
pip install tepilora-mcp
```

## Quick Start

### Claude Desktop

```json
{
  "mcpServers": {
    "tepilora": {
      "command": "tepilora-mcp",
      "env": { "TEPILORA_MCP_API_KEY": "your-api-key" }
    }
  }
}
```

### Claude Code

```bash
claude mcp add tepilora tepilora-mcp -e TEPILORA_MCP_API_KEY=your-api-key
```

### Run Directly

```bash
export TEPILORA_MCP_API_KEY=your-api-key
tepilora-mcp
```

## Available Tools

### Discovery & Generic

| Tool | Description |
|------|-------------|
| `list_namespaces` | List all API namespaces with operation counts |
| `list_operations` | List operations for a namespace |
| `describe_operation` | Get parameter details for any operation |
| `call_operation` | Execute any operation by action string |
| `call_operation_arrow_stream` | Execute any operation in Arrow IPC format |

### Curated

| Tool | Description |
|------|-------------|
| `search_securities` | Search stocks, ETFs, bonds, funds |
| `get_security_details` | Get security information |
| `get_price_history` | Historical price data |
| `create_portfolio` | Create a portfolio |
| `save_query` | Save a reusable query |
| `get_portfolio_returns` | Portfolio return analysis |
| `run_analytics` | 75+ analytics functions (summary-first with MCP resource for full data) |
| `search_news` | Search financial news |
| `screen_bonds` | Screen bonds by criteria |
| `get_yield_curve` | Yield curve data |
| `get_realtime_quotes` | Realtime quotes for a market category |
| `get_realtime_quote` | Single realtime quote by symbol |
| `get_realtime_chart` | Intraday chart data (1D, 5D, 1M, 1Y) |
| `get_realtime_calendar` | Economic calendar with actual vs forecast |
| `get_realtime_health` | Data source health status |

### Utility

| Tool | Description |
|------|-------------|
| `clear_cache` | Clear the in-memory result cache |
| `get_credit_usage` | View session credit usage and limits |
| `reset_credits` | Reset the session credit counter |

### Full Mode

Set `TEPILORA_MCP_FULL_TOOLS=true` to expose all operations as individual tools.

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TEPILORA_MCP_API_KEY` | Yes | - | Your Tepilora API key for MCP (`TEPILORA_API_KEY` is a deprecated alias until 0.6.0) |
| `TEPILORA_BASE_URL` | No | `https://tepiloradata.com` | API base URL |
| `TEPILORA_FALLBACK_URL` | No | `-` | Fallback URL |
| `TEPILORA_MCP_FULL_TOOLS` | No | `false` | Register all operations as tools |
| `TEPILORA_MCP_TIMEOUT` | No | `30` | Request timeout (seconds) |
| `TEPILORA_MCP_CACHE_TTL` | No | `300` | Cache TTL in seconds (`0` disables) |
| `TEPILORA_MCP_CACHE_MAX_SIZE` | No | `1000` | Max cached entries (LRU) |
| `TEPILORA_MCP_CREDIT_LIMIT` | No | `0` | Session credit cap (`0` = unlimited) |

## Requirements

- Python 3.10+
- [`Tepilora`](https://pypi.org/project/Tepilora/) >= 0.5.0
- [`fastmcp`](https://pypi.org/project/fastmcp/) >= 2.14, < 3

## License

MIT
