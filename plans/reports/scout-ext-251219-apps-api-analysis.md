# Scout Report: apps/api Analysis

**Date:** 2025-12-19  
**Scope:** D:\Stock_Massive\apps\api  
**Type:** Python FastAPI Backend

---

## 1. Project Structure

```
apps/api/
├── alembic/                    # Database migrations
│   ├── env.py
│   └── versions/
│       └── 60811b8fd9e3_create_stock_intraday_bars_table.py
├── src/
│   ├── main.py                 # FastAPI app entry point
│   ├── core/
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── database.py         # Async SQLAlchemy setup
│   │   ├── dependencies.py     # FastAPI dependencies
│   │   └── scheduler.py        # APScheduler setup
│   └── stocks/
│       ├── models.py           # SQLAlchemy models
│       ├── schemas.py          # Pydantic schemas
│       ├── router.py           # API endpoints
│       ├── service.py          # Business logic (vnstock wrapper)
│       ├── intraday_collector.py  # Tick-to-bar aggregation
│       └── jobs.py             # Scheduled jobs
├── tests/                      # Pytest test suite
│   ├── conftest.py
│   ├── test_stocks_router.py
│   ├── test_stocks_service.py
│   ├── test_intraday_collector.py
│   ├── test_scheduler.py
│   ├── test_sector_performance.py
│   ├── test_volume_analysis.py
│   └── test_database_phase01.py
└── requirements.txt
```

---

## 2. Main Entry Points

### App Entry: `src/main.py`
- FastAPI app with lifespan management
- CORS enabled for `http://localhost:3000`
- Router mounted at `/api/v1`
- Health endpoints: `/` and `/health`
- Scheduler starts on app startup (if enabled)

### Router: `src/stocks/router.py`
- Prefix: `/api/v1/stocks`
- Tags: `["stocks"]`

---

## 3. API Endpoints (27 total)

### Symbol Listing
| Method | Path | Description |
|--------|------|-------------|
| GET | `/symbols` | List all symbols (filter by exchange) |
| GET | `/symbols/group/{group}` | List by group (VN30, HNX30, etc.) |
| GET | `/symbols/search` | Search by ticker/company name |

### Price Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{symbol}/history` | Historical OHLCV (1D/1W/1M intervals) |
| GET | `/{symbol}/intraday` | Intraday tick data |
| GET | `/market-indices` | VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX |
| GET | `/sector-performance` | ICB Level 2 sector performance |
| GET | `/fund-certificates` | ETFs and open-end funds |
| GET | `/price-board` | Real-time multi-symbol prices |

### Company Info
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{symbol}/company` | Company overview |
| GET | `/{symbol}/detail` | Comprehensive stock detail |
| GET | `/{symbol}/shareholders` | Major shareholders |
| GET | `/{symbol}/officers` | Company officers/management |
| GET | `/{symbol}/insider-deals` | Insider trading deals |

### Financial Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{symbol}/financials/ratios` | Financial ratios (ROE, ROA, P/E, etc.) |
| GET | `/{symbol}/financials/income` | Income statement (simplified) |
| GET | `/{symbol}/financials/income-statement` | Detailed income statement |
| GET | `/{symbol}/financials/balance-sheet` | Balance sheet (simplified) |
| GET | `/{symbol}/financials/balance-sheet-detailed` | Detailed balance sheet |
| GET | `/{symbol}/financials/cash-flow` | Detailed cash flow |

### Intraday Collection & Analysis
| Method | Path | Description |
|--------|------|-------------|
| POST | `/intraday/collect` | Manual trigger intraday collection |
| GET | `/{symbol}/volume-analysis` | Volume pattern analysis |

---

## 4. Database Models

### `StockIntradayBar` (stock_intraday_bars)
5-minute OHLCV bars for intraday data:
- `id` (BigInteger, PK)
- `symbol` (String(10), indexed)
- `bar_time` (DateTime)
- `open_price`, `high_price`, `low_price`, `close_price` (Numeric 12,2)
- `volume` (BigInteger)
- `trade_value` (Numeric 18,2)
- `trade_count` (Integer)
- `created_at` (DateTime, auto)

**Constraints:**
- Unique: `(symbol, bar_time)`
- Index: `idx_intraday_symbol_date`

---

## 5. External Integrations

### vnstock Library (Primary Data Source)
- **Classes used:** `Vnstock`, `Listing`, `Quote`, `Finance`, `Trading`
- **Data source:** VCI (default, most reliable)
- **Capabilities:**
  - Historical OHLCV data
  - Intraday tick data
  - Company overview & financials
  - Price board (real-time)
  - Market indices
  - Shareholders, officers, insider deals
  - Sector performance
  - Fund certificates

### PostgreSQL (via asyncpg)
- Async SQLAlchemy 2.0
- Connection pooling (5 base, 10 overflow)
- Auto-commit on success, rollback on error

### APScheduler 4.x
- Async scheduler with cron triggers
- Timezone: Asia/Ho_Chi_Minh
- Jobs:
  - `intraday-collection-daily` (15:30 ICT default)
  - `data-cleanup-daily` (16:00 ICT)

---

## 6. Dependencies (requirements.txt)

| Category | Packages |
|----------|----------|
| Core | fastapi>=0.100.0, uvicorn, pydantic>=2.0.0, pydantic-settings |
| Database | sqlalchemy>=2.0.0, alembic, asyncpg, psycopg2-binary |
| Auth | python-jose, passlib, python-multipart |
| HTTP | httpx>=0.25.0 |
| Stock Data | vnstock>=3.0.0 |
| Scheduler | apscheduler>=4.0.0a6 |
| Dev | pytest, pytest-asyncio |

---

## 7. Configuration (src/core/config.py)

| Setting | Default | Description |
|---------|---------|-------------|
| `api_host` | 0.0.0.0 | API bind host |
| `api_port` | 8000 | API port |
| `debug` | False | Debug mode |
| `database_url` | postgresql://... | DB connection |
| `jwt_secret` | change-me | JWT signing key |
| `scheduler_enabled` | True | Enable scheduler |
| `intraday_collect_hour` | 15 | Collection hour |
| `intraday_collect_minute` | 30 | Collection minute |
| `intraday_symbols` | VCB,FPT,VNM,VIC,VHM | Symbols to collect |
| `intraday_retention_days` | 30 | Data retention |

---

## 8. Recent Features (Based on Code Patterns)

1. **Sector Performance** - ICB Level 2 market-cap weighted performance
2. **Fund Certificates** - ETF/open-end fund listing
3. **Volume Analysis** - Peak trading period identification
4. **Detailed Financial Statements** - Vietnamese labels, hierarchical rows
5. **Stock Detail Endpoint** - Consolidated data from multiple sources
6. **Shareholders/Officers/Insider Deals** - Corporate governance data

---

## 9. Key File Paths

| Component | Path |
|-----------|------|
| App Entry | `D:\Stock_Massive\apps\api\src\main.py` |
| Config | `D:\Stock_Massive\apps\api\src\core\config.py` |
| Database | `D:\Stock_Massive\apps\api\src\core\database.py` |
| Router | `D:\Stock_Massive\apps\api\src\stocks\router.py` |
| Service | `D:\Stock_Massive\apps\api\src\stocks\service.py` |
| Models | `D:\Stock_Massive\apps\api\src\stocks\models.py` |
| Schemas | `D:\Stock_Massive\apps\api\src\stocks\schemas.py` |
| Collector | `D:\Stock_Massive\apps\api\src\stocks\intraday_collector.py` |
| Jobs | `D:\Stock_Massive\apps\api\src\stocks\jobs.py` |
| Scheduler | `D:\Stock_Massive\apps\api\src\core\scheduler.py` |
| Requirements | `D:\Stock_Massive\apps\api\requirements.txt` |
| Migration | `D:\Stock_Massive\apps\api\alembic\versions\60811b8fd9e3_create_stock_intraday_bars_table.py` |

---

## Unresolved Questions

1. Auth endpoints not implemented yet (JWT config exists but no auth routes)
2. `dependencies.py` content not examined - may have additional DI setup
3. Only one DB migration exists - schema may be minimal or using external data primarily
