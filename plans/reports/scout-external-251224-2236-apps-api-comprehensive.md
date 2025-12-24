# Scout Report: apps/api Backend Analysis

**Date:** 2024-12-24
**Scout ID:** a07dd4a
**Target:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api`

---

## 1. Directory Structure

```
apps/api/
├── alembic/                    # Database migrations
│   ├── env.py                  # Alembic config (Supabase-aware)
│   └── versions/               # Migration files
│       ├── 60811b8fd9e3_create_stock_intraday_bars_table.py
│       ├── 6948fc67_add_top_performers_table.py
│       ├── a1b2c3d4_rename_top_performers_to_financial_statements.py
│       └── d945d0cac5ec_add_stock_daily_ohlcv_table.py
├── src/
│   ├── core/                   # Core infrastructure
│   │   ├── cache.py            # TradingHoursCache (trading-aware TTL)
│   │   ├── config.py           # Pydantic settings (env vars)
│   │   ├── database.py         # SQLAlchemy async engine (Supabase)
│   │   ├── dependencies.py     # FastAPI dependencies
│   │   ├── job_status_store.py # In-memory job progress tracking
│   │   ├── ratelimit.py        # Upstash rate limiting
│   │   ├── redis.py            # Upstash Redis client
│   │   ├── scheduler.py        # APScheduler setup
│   │   └── vnstock_wrapper.py  # vnstock library wrapper
│   ├── stocks/                 # Main feature module
│   │   ├── analytics/          # Analytics domain
│   │   │   ├── router.py       # /analytics/* endpoints
│   │   │   └── service.py
│   │   ├── company/            # Company domain
│   │   │   ├── router.py       # /{symbol}/company, /detail, etc.
│   │   │   └── service.py
│   │   ├── financial/          # Financial domain
│   │   │   ├── router.py       # /{symbol}/financials/*
│   │   │   └── service.py
│   │   ├── market/             # Market domain
│   │   │   ├── router.py       # /symbols, /sector-performance
│   │   │   └── service.py
│   │   ├── price/              # Price domain
│   │   │   ├── cache.py        # Volume anomaly cache
│   │   │   ├── router.py       # /price-board, /market-indices
│   │   │   └── service.py
│   │   ├── schemas/            # Pydantic schemas
│   │   │   ├── analytics.py
│   │   │   ├── common.py
│   │   │   ├── company.py
│   │   │   ├── financial.py
│   │   │   ├── market.py
│   │   │   └── price.py
│   │   ├── shared/             # Shared utilities
│   │   │   ├── converters.py
│   │   │   ├── exceptions.py
│   │   │   └── validators.py
│   │   ├── financial_statements_collector.py  # Weekly batch job
│   │   ├── intraday_collector.py              # Intraday data collector
│   │   ├── jobs_router.py      # /jobs/status endpoint
│   │   ├── jobs.py             # Background job definitions
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── router.py           # Main router aggregator
│   │   └── service.py          # Stock service (vnstock wrapper)
│   └── main.py                 # FastAPI app entry point
├── tests/                      # Test files
├── requirements.txt            # Python dependencies
└── alembic.ini                 # Alembic configuration
```

---

## 2. Main Entry Points

### `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/main.py`
- FastAPI app with lifespan management
- CORS middleware (origins from config)
- APScheduler integration (background jobs)
- Two main routers:
  - `stocks_router` -> `/api/v1/stocks/*`
  - `jobs_router` -> `/api/v1/jobs/*`
- Health endpoints: `/` and `/health`

---

## 3. Database Configuration (Supabase)

### `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/database.py`

**Key Supabase Integration:**
```python
# SSL config for Supabase connections
connect_args = {}
if "supabase" in DATABASE_URL.lower():
    connect_args["ssl"quire"
```

**Features:**
- Async engine: `postgresql+asyncpg://` driver
- Sync engine: For Alembic migrations and background jobs
- Connection pooling: `pool_size=5`, `max_overflow=10`
- SSL auto-detection for Supabase URLs
- `sslmode` URL param stripped (asyncpg uses connect_args)

### `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`

**Database Settings:**
```python
database_url: str = "postgresql://..."
database_url_direct: str = ""  # Direct connection for Alembic (bypasses pooler)
```

### `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/alembic/env.py`

**Supabase Migration Support:**
- Prefers `database_url_direct` for migrations (bypasses connection pooler)
- Auto-detects Supabase and adds SSL config
- Async migration support with `async_engine_from_config`

---

## 4. Database Models

### `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/models.py`

| Model | Table | Purpose |
|-------|-------|---------|
| `StockDailyOHLCV` | `stock_daily_ohlcv` | Daily OHLCV data |
| `StockIntradayBar` | `stock_intraday_bars` | 5-minute intraday bars |
| `FinancialStatement` | `financial_statements` | Quarterly financials |

**Indexes:**
- `idx_daily_symbol_date` on (symbol, trade_date)
- `idx_intraday_symbol_date` on (symbol, date(bar_time))
- `ix_financial_statements_period` on (year, quarter)
- `ix_financial_statements_exchange` on (exchange)

---

## 5. API Endpoints Summary

### Jobs Router (`/api/v1/jobs`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Get all job statuses from today |

### Stocks Router (`/api/v1/stocks`)

#### Market Domain
| Method | Path | Description |
|--------|------|-------------|
| GET | `/symbols` | List all stock symbols |
| GET | `/symbols/group/{group}` | List symbols by group (VN30, etc.) |
| GET | `/symbols/search` | Search symbols by ticker/name |
| GET | `/sector-performance` | ICB Level 2 sector performance |
| GET | `/fund-certificates` | ETFs and open-end funds |
| GET | `/vn30-overview` | VN30 stocks with real-time prices |

#### Price Domain
| Method | Path | Description |
|--------|------|-------------|
| GET | `/market-indices` | VN-INDEX, VN30, HNX, UPCOM |
| GET | `/price-board` | Real-time price board (multi-symbol) |
| GET | `/{symbol}/history` | Historical OHLCV data |
| GET | `/{symbol}/intraday` | Intraday tick data |
| GET | `/{symbol}/volume-analysis` | Volume pattern analysis |
| GET | `/{symbol}/volume-anomalies` | Volume anomaly detection |
| POST | `/intraday/collect` | Manual intraday collection |

#### Company Domain
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{symbol}/company` | Company overview |
| GET | `/{symbol}/detail` | Comprehensive stock detail |
| GET | `/{symbol}/shareholders` | Major shareholders |
| GET | `/{symbol}/officers` | Company officers |
| GET | `/{symbol}/insider-deals` | Insider trading deals |

#### Financial Domain
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{symbol}/financials/ratios` | Financial ratios |
| GET | `/{symbol}/financials/income` | Income statement (simple) |
| GET | `/{symbol}/financials/income-statement` | Income statement (detailed) |
| GET | `/{symbol}/financials/balance-sheet` | Balance sheet (simple) |
| GET | `/{symbol}/financials/balance-sheet-detailed` | Balance sheet (detailed) |
| GET | `/{symbol}/financials/cash-flow` | Cash flow statement |

#### Analytics Domain
| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics/financial-statements` | Top companies by net profit |
| POST | `/analytics/financial-statements/collect` | Manual collection trigger |
| GET | `/analytics/volume-spikes` | Volume spikes by industry |
| DELETE | `/analytics/volume-spikes/cache` | Clear volume spikes cache |

---

## 6. Scheduled Jobs

### `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/scheduler.py`

| Job ID | Schedule | Description |
|--------|----------|-------------|
| `intraday-collection-daily` | 15:30 ICT (Mon-Fri) | Collect intraday bars |
| `data-cleanup-daily` | 16:00 ICT | Cleanup old data |
| `daily-ohlcv-collection` | 17:00 ICT | Collect daily OHLCV |
| `collect-financial-statements` | Sunday 02:00 ICT | Weekly financials |

**Startup Recovery:** Checks for missed jobs on startup and runs them if conditions met.

---

## 7. Key Dependencies

### `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/requirements.txt`

| Category | Packages |
|----------|----------|
| Core | fastapi, uvicorn, pydantic, pydantic-settings |
| Database | sqlalchemy, alembic, asyncpg, psycopg2-binary |
| Cache | upstash-redis, upstash-ratelimit |
| Stock Data | vnstock, pandas, numpy |
| Scheduler | apscheduler>=4.0.0a6 |
| HTTP | httpx, tenacity |

---

## 8. Architecture Patterns

1. **Feature-based Modular Architecture**
   - Domain routers: market, price, company, financial, analytics
   - Each domain has router.py + service.py

2. **Trading-Hours-Aware Caching**
   - `TradingHoursCache` with different TTLs for trading vs off-hours
   - Shorter TTL during market hours for fresher data

3. **Rate Limiting**
   - `standard_rate_limit`: 100 req/60s
   - `heavy_rate_limit`: 20 req/60s (for expensive operations)

4. **Job Progress Tracking**
   - In-memory `JobStatusStore` (thread-safe singleton)
   - Frontend polls `/api/v1/jobs/status` for progress updates

5. **Async/Sync Hybrid**
   - Async for API endpoints (asyncpg)
   - Sync for background jobs (psycopg2)

---

## 9. Supabase Migration Summary

**Changes Made:**
- `database.py`: SSL auto-detection for Supabase URLs
- `config.py`: Added `database_url_direct` for migrations
- `alembic/env.py`: Supabase-aware migration config
- Connection pooling optimized for Supabase

**Environment Variables:**
```
DATABASE_URL=postgresql://postgres.[project]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
DATABASE_URL_DIRECT=postgresql://postgres.[project]:[password]@db.[project].supabase.co:5432/postgres
```

---

## 10. Unresolved Questions

None identified during this scout.
