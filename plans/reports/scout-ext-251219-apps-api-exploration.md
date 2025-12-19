# Scout Report: apps/api Directory Exploration

**Date:** 2025-12-19
**Scope:** D:/Stock_Massive/apps/api

---

## 1. Project Structure

```
apps/api/
├── alembic/                    # Database migrations
│   ├── env.py                  # Alembic environment config
│   ├── script.py.mako          # Migration template
│   └── versions/               # Migration files
├── src/
│   ├── main.py                 # FastAPI app entry point
│   ├── core/                   # Core infrastructure
│   │   ├── config.py           # Settings via pydantic-settings
│   │   ├── database.py         # Async SQLAlchemy setup
│   │   ├── dependencies.py     # FastAPI dependencies
│   │   └── scheduler.py        # APScheduler setup
│   ├── stocks/                 # Main feature module
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── router.py           # FastAPI routes
│   │   ├── service.py          # Business logic (vnstock wrapper)
│   │   ├── intraday_collector.py  # Tick-to-bar aggregation
│   │   └── jobs.py             # Scheduled tasks
│   └── workers/tasks/          # (placeholder)
├── tests/                      # Test suite
├── alembic.ini                 # Alembic config
├── Dockerfile                  # Container build
└── requirements.txt            # Python dependencies
```

---

## 2. Entry Points and Routing

### Main Entry Point
- **File:** src/main.py
- **App:** FastAPI with lifespan management
- **Title:** Stock Massive API
- **Version:** 0.1.0

### Routing Structure
| Prefix | Router | Description |
|--------|--------|-------------|
| / | root | Health check |
| /health | health | Health endpoint |
| /api/v1/stocks | stocks_router | All stock endpoints |

### CORS
- Allowed origin: http://localhost:3000

---

## 3. API Endpoints

### Symbol Listing
| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/stocks/symbols | List all symbols |
| GET | /api/v1/stocks/symbols/group/{group} | Symbols by group (VN30, HNX30) |
| GET | /api/v1/stocks/symbols/search | Search by ticker/name |

### Price Data
| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/stocks/{symbol}/history | Historical OHLCV |
| GET | /api/v1/stocks/{symbol}/intraday | Tick-by-tick data |
| GET | /api/v1/stocks/market-indices | VN-INDEX, VN30, HNX, UPCOM |
| GET | /api/v1/stocks/price-board | Real-time multi-symbol prices |

### Company Info
| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/stocks/{symbol}/company | Company overview |
| GET | /api/v1/stocks/{symbol}/detail | Comprehensive stock detail |
| GET | /api/v1/stocks/{symbol}/shareholders | Major shareholders |
| GET | /api/v1/stocks/{symbol}/officers | Company officers |
| GET | /api/v1/stocks/{symbol}/insider-deals | Insider transactions |

### Financial Data
| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/stocks/{symbol}/financials/ratios | ROE, ROA, P/E, P/B |
| GET | /api/v1/stocks/{symbol}/financials/income | Income statement |
| GET | /api/v1/stocks/{symbol}/financials/income-statement | Detailed income |
| GET | /api/v1/stocks/{symbol}/financials/balance-sheet | Balance sheet |
| GET | /api/v1/stocks/{symbol}/financials/balance-sheet-detailed | Detailed balance |
| GET | /api/v1/stocks/{symbol}/financials/cash-flow | Cash flow |

### Intraday Collection
| Method | Path | Purpose |
|--------|------|---------|
| POST | /api/v1/stocks/intraday/collect | Manual tick collection |
| GET | /api/v1/stocks/{symbol}/volume-analysis | Peak volume periods |

---

## 4. Database Models

### StockIntradayBar (stock_intraday_bars)
| Column | Type | Description |
|--------|------|-------------|
| id | BigInteger | PK |
| symbol | String(10) | Stock ticker |
| bar_time | DateTime | 5-min bar timestamp |
| open_price | Numeric(12,2) | Open |
| high_price | Numeric(12,2) | High |
| low_price | Numeric(12,2) | Low |
| close_price | Numeric(12,2) | Close |
| volume | BigInteger | Volume |
| trade_value | Numeric(18,2) | Value |
| trade_count | Integer | Trades |
| created_at | DateTime | Created |

---

## 5. Key Services

### StockService (service.py)
- Wraps vnstock library for VN market data
- Data source: VCI (default)
- Singleton pattern

### IntradayCollector (intraday_collector.py)
- Aggregates ticks to 5-min OHLCV bars
- Upsert to PostgreSQL
- Volume analysis (09:00-15:00)

### Scheduled Jobs (jobs.py)
- collect_intraday_data_job: Daily 15:30 ICT
- cleanup_old_data_job: Daily 16:00 ICT

---

## 6. Tech Stack

- **FastAPI** >= 0.100.0
- **SQLAlchemy** >= 2.0.0 (async)
- **Alembic** >= 1.12.0
- **asyncpg** >= 0.28.0
- **vnstock** >= 3.0.0
- **APScheduler** >= 4.0.0a6
- **Pydantic** >= 2.0.0
- **pytest** >= 7.4.0

---

## 7. Configuration (config.py)

| Setting | Default |
|---------|---------|
| api_host | 0.0.0.0 |
| api_port | 8000 |
| database_url | postgresql://... |
| vnstock_source | VCI |
| scheduler_enabled | True |
| intraday_collect_hour | 15 |
| intraday_collect_minute | 30 |
| intraday_symbols | VCB,FPT,VNM,VIC,VHM |
| intraday_retention_days | 30 |

---

## 8. Key Files

| File | Purpose |
|------|---------|
| src/main.py | FastAPI app setup |
| src/core/config.py | Settings |
| src/core/database.py | Async DB |
| src/core/scheduler.py | Job scheduling |
| src/stocks/router.py | API routes (447 lines) |
| src/stocks/service.py | Business logic (1310 lines) |
| src/stocks/schemas.py | Pydantic models (382 lines) |
| src/stocks/models.py | SQLAlchemy models |
| src/stocks/intraday_collector.py | Data collection |
| src/stocks/jobs.py | Scheduled jobs |

---

## Unresolved Questions
- None
