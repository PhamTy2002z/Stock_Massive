# Scout Report: apps/api Backend (Python FastAPI)

**Generated:** 2024-12-23 20:56
**Scout ID:** a495ac3
**Directory:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api`

---

## 1. Directory Structure Overview

```
apps/api/
├── alembic/                    # Database migrations
│   ├── versions/               # Migration files
│   └── env.py                  # Alembic config
├── src/
│   ├── core/                   # Core infrastructure
│   │   ├── cache.py            # Trading-hours-aware Redis cache
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # SQLAlchemy async/sync setup
│   │   ├── dependencies.py     # FastAPI dependencies
│   │   ├── ratelimit.py        # Upstash Redis rate limiting
│   │   ├── redis.py            # Redis client
│   │   ├── scheduler.py        # APScheduler setup
│   │   └── vnstock_wrapper.py  # Safe vnstock API wrapper
│   ├── stocks/                 # Main feature module
│   │   ├── analytics/          # Analytics domain
│   │   ├── company/            # Company info domain
│   │   ├── financial/          # Financial statements domain
│   │   ├── market/             # Market-wide data domain
│   │   ├── price/              # Price/OHLCV domain
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── shared/             # Shared utilities
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── router.py           # Main router aggregator
│   │   ├── service.py          # Facade service
│   │   ├── jobs.py             # Scheduled job functions
│   │   ├── intraday_collector.py
│   │   └── financial_statements_collector.py
│   └── main.py                 # FastAPI app entry
├── tests/                      # Test suite (15 files)
├── requirements.txt            # Dependencies
├── Dockerfile                  # Dev container
├── Dockerfile.prod             # Production container
└── alembic.ini                 # Alembic config
```

---

## 2. Key Files and Purposes

| File | Purpose |
|------|---------|
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/main.py` | FastAPI app entry, lifespan management, CORS, router mounting |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py` | Pydantic settings from env vars (DB, Redis, scheduler, rate limits) |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/database.py` | Async/sync SQLAlchemy engines, session factories |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/scheduler.py` | APScheduler 4.x async setup with cron triggers |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/models.py` | SQLAlchemy ORM models |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/router.py` | Main router aggregating 5 domain routers |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/service.py` | Facade service delegating to domain services |

---

## 3. Main Modules/Features

### Core Infrastructure (`src/core/`)
- **Config**: Pydantic-settings with env file support
- **Database**: Async (asyncpg) + sync (psycopg2) SQLAlchemy 2.0
- **Cache**: Trading-hours-aware TTL (shorter during market hours)
- **Rate Limiting**: Upstash Redis sliding window algorithm
- **Scheduler**: APScheduler 4.x async with Vietnam timezone

### Stocks Module (`src/stocks/`)
Feature-based modular architecture with 5 domains:

| Domain | Purpose |
|--------|---------|
| `analytics/` | Volume spikes, financial statements rankings |
| `company/` | Company overview, shareholders, officers, insider deals |
| `financial/` | Income statement, balance sheet, cash flow, ratios |
| `market/` | Symbols listing, sector performance, VN30 overview |
| `price/` | Historical OHLCV, intraday ticks, price board, volume analysis |

---

## 4. Database Models

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/models.py`

| Model | Table | Purpose |
|-------|-------|---------|
| `StockDailyOHLCV` | `stock_daily_ohlcv` | Daily OHLCV data (symbol, date, OHLCV) |
| `StockIntradayBar` | `stock_intraday_bars` | 5-minute intraday bars |
| `FinancialStatement` | `financial_statements` | Quarterly financials with ranking |

### Alembic Migrations
- `60811b8fd9e3_create_stock_intraday_bars_table.py`
- `d945d0cac5ec_add_stock_daily_ohlcv_table.py`
- `6948fc67_add_top_performers_table.py`
- `a1b2c3d4_rename_top_performers_to_financial_statements.py`

---

## 5. API Routes/Endpoints

**Base prefix:** `/api/v1/stocks`

### Market Router (`/api/v1/stocks/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/symbols` | List all symbols (filterable by exchange) |
| GET | `/symbols/group/{group}` | Symbols by group (VN30, HNX30) |
| GET | `/symbols/search` | Search symbols by ticker/name |
| GET | `/sector-performance` | ICB Level 2 sector performance |
| GET | `/fund-certificates` | ETFs and open-end funds |
| GET | `/vn30-overview` | VN30 stocks with real-time prices |

### Price Router (`/api/v1/stocks/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{symbol}/history` | Historical OHLCV (1D/1W/1M) |
| GET | `/{symbol}/intraday` | Intraday tick data |
| GET | `/market-indices` | VN-INDEX, VN30, HNX-INDEX |
| GET | `/price-board` | Real-time prices for multiple symbols |
| POST | `/intraday/collect` | Manual intraday collection trigger |
| GET | `/{symbol}/volume-analysis` | Volume pattern analysis |
| GET | `/{symbol}/volume-anomalies` | Volume anomaly detection |

### Company Router (`/api/v1/stocks/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{symbol}/company` | Company overview |
| GET | `/{symbol}/detail` | Comprehensive stock detail |
| GET | `/{symbol}/shareholders` | Major shareholders |
| GET | `/{symbol}/officers` | Company officers |
| GET | `/{symbol}/insider-deals` | Insider trading deals |

### Financial Router (`/api/v1/stocks/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{symbol}/financials/ratios` | Financial ratios |
| GET | `/{symbol}/financials/income` | Income statement (simple) |
| GET | `/{symbol}/financials/income-statement` | Income statement (detailed) |
| GET | `/{symbol}/financials/balance-sheet` | Balance sheet (simple) |
| GET | `/{symbol}/financials/balance-sheet-detailed` | Balance sheet (detailed) |
| GET | `/{symbol}/financials/cash-flow` | Cash flow statement |

### Analytics Router (`/api/v1/stocks/analytics/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/financial-statements` | Top companies by net profit |
| POST | `/financial-statements/collect` | Manual collection trigger |
| GET | `/volume-spikes` | Volume spikes by ICB industry |

---

## 6. Services and Business Logic

### Facade Pattern
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/service.py`

`StockService` aggregates 4 domain services:
- `PriceService` - Historical/intraday price data
- `CompanyService` - Company information
- `FinancialService` - Financial statements
- `MarketService` - Market-wide data

### Key Collectors
| Collector | File | Purpose |
|-----------|------|---------|
| `IntradayCollector` | `intraday_collector.py` | Aggregates ticks to 5-min bars, volume analysis |
| `FinancialStatementsCollector` | `financial_statements_collector.py` | Fetches quarterly financials, ranks by profit |

### Analytics Service
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/analytics/service.py`
- Volume spike detection with 20-day baseline
- ICB industry grouping
- Financial statements ranking

---

## 7. Configuration

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`

| Category | Settings |
|----------|----------|
| API | `api_host`, `api_port`, `debug` |
| Database | `database_url` (PostgreSQL) |
| CORS | `cors_origins` (comma-separated) |
| Vnstock | `vnstock_source` (default: VCI) |
| Redis | `upstash_redis_url`, `upstash_redis_token` |
| Scheduler | `scheduler_enabled`, intraday/daily/financial times |
| Rate Limits | `rate_limit_standard_max` (100/60s), `rate_limit_heavy_max` (20/60s) |

---

## 8. Tests Structure

**Directory:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/tests/`

| Test File | Coverage |
|-----------|----------|
| `test_analytics_api.py` | Analytics endpoints |
| `test_database_phase01.py` | Database models |
| `test_financial_statements_collector.py` | Financial data collection |
| `test_intraday_collector.py` | Intraday aggregation |
| `test_ratelimit.py` | Rate limiting |
| `test_scheduler.py` | Scheduled jobs |
| `test_sector_performance.py` | Sector performance |
| `test_stocks_router.py` | Stock router endpoints |
| `test_stocks_service.py` | Stock service |
| `test_trading_hours_cache.py` | Cache TTL logic |
| `test_volume_analysis.py` | Volume analysis |
| `test_volume_anomaly_api.py` | Volume anomaly API |
| `test_volume_anomaly_detection.py` | Anomaly detection |

**Test Config:** `conftest.py` with pytest-asyncio fixtures

---

## 9. Scheduled Jobs/Background Tasks

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/scheduler.py`

| Job ID | Schedule | Function | Description |
|--------|----------|----------|-------------|
| `intraday-collection-daily` | 15:30 ICT daily | `collect_intraday_data_job` | Collect 5-min bars for configured symbols |
| `data-cleanup-daily` | 16:00 ICT daily | `cleanup_old_data_job` | Remove data older than retention period |
| `daily-ohlcv-collection` | 20:00 ICT daily | `collect_daily_ohlcv_job` | Fetch daily OHLCV for all symbols |
| `collect-financial-statements` | 02:00 ICT Sunday | `collect_financial_statements_job` | Weekly financial data collection |

### Job Implementation
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/jobs.py`
- Async jobs for intraday/cleanup
- Sync job for daily OHLCV (vnstock blocking)
- Batch processing with adaptive delays
- Rate limit handling with exponential backoff

---

## 10. Dependencies

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/requirements.txt`

| Category | Packages |
|----------|----------|
| **Core** | `fastapi>=0.100.0`, `uvicorn[standard]>=0.23.0`, `pydantic>=2.0.0`, `pydantic-settings>=2.0.0` |
| **Database** | `sqlalchemy>=2.0.0`, `alembic>=1.12.0`, `asyncpg>=0.28.0`, `psycopg2-binary>=2.9.0`, `greenlet>=3.0.0` |
| **Utils** | `httpx>=0.25.0`, `python-multipart>=0.0.6`, `tenacity>=8.2.0` |
| **Cache** | `upstash-redis>=1.0.0`, `upstash-ratelimit>=1.0.0` |
| **Stock Data** | `vnstock>=3.0.0`, `pandas>=2.0.0`, `numpy>=1.24.0` |
| **Scheduler** | `apscheduler>=4.0.0a6` |
| **Dev** | `pytest>=7.4.0`, `pytest-asyncio>=0.21.0` |

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI App                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   /api/v1/stocks                     │   │
│  │  ┌─────────┬─────────┬─────────┬─────────┬────────┐ │   │
│  │  │ Market  │  Price  │ Company │Financial│Analytics│ │   │
│  │  │ Router  │ Router  │ Router  │ Router  │ Router  │ │   │
│  │  └────┬────┴────┬────┴────┬────┴────┬────┴────┬───┘ │   │
│  │       │         │         │         │         │      │   │
│  │       └─────────┴────┬────┴─────────┴─────────┘      │   │
│  │                      │                               │   │
│  │              ┌───────▼───────┐                       │   │
│  │              │ StockService  │ (Facade)              │   │
│  │              │   Facade      │                       │   │
│  │              └───────┬───────┘                       │   │
│  │    ┌─────────┬───────┼───────┬─────────┐            │   │
│  │    ▼         ▼       ▼       ▼         ▼            │   │
│  │ Market   Price   Company  Financial  Analytics      │   │
│  │ Service  Service Service  Service    Service        │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────┼────────────────────────────┐   │
│  │                   Core Layer                         │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐  │   │
│  │  │Database│ │ Cache  │ │RateLimit│ │  Scheduler   │  │   │
│  │  │(Async) │ │(Redis) │ │(Upstash)│ │(APScheduler) │  │   │
│  │  └────────┘ └────────┘ └────────┘ └──────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────┼────────────────────────────┐   │
│  │              External Services                       │   │
│  │  ┌──────────────┐  ┌──────────────┐                 │   │
│  │  │   vnstock    │  │   Upstash    │                 │   │
│  │  │  (VCI API)   │  │    Redis     │                 │   │
│  │  └──────────────┘  └──────────────┘                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Unresolved Questions

1. No explicit API versioning strategy beyond `/api/v1` prefix
2. No authentication/authorization layer visible
3. `vnstock_wrapper.py` handles SystemExit from vnstock rate limits - potential fragility
4. Some test files are large (30K+ lines) - may need refactoring

