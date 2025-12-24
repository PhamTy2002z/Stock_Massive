# Apps/API Directory Summary Report

**Scout ID**: aef004d | **Date**: 2024-12-24 21:17  
**Path**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/`

---

## 1. Directory Structure

```
apps/api/
├── alembic/                    # Database migrations
│   ├── versions/               # Migration scripts
│   └── env.py                  # Alembic config
├── src/                        # Main source code
│   ├── main.py                 # FastAPI entry point
│   ├── api/v1/endpoints/       # (placeholder, unused)
│   ├── core/                   # Core infrastructure
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── database.py         # SQLAlchemy async/sync engines
│   │   ├── scheduler.py        # APScheduler setup
│   │   ├── cache.py            # TradingHoursCache (Upstash Redis)
│   │   ├── ratelimit.py        # Rate limiting middleware
│   │   ├── redis.py            # Redis client
│   │   ├── vnstock_wrapper.py  # Vnstock API wrapper
│   │   ├── job_status_store.py # Job progress tracking (NEW)
│   │   └── dependencies.py     # FastAPI dependencies
│   ├── stocks/                 # Main feature module
│   │   ├── router.py           # Aggregates domain routers
│   │   ├── service.py          # Stock service (vnstock)
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── jobs.py             # Scheduled job functions
│   │   ├── jobs_router.py      # Job status API (NEW)
│   │   ├── intraday_collector.py
│   │   ├── financial_statements_collector.py
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── analytics/          # Analytics domain
│   │   ├── company/            # Company domain
│   │   ├── financial/          # Financial domain
│   │   ├── market/             # Market domain
│   │   ├── price/              # Price domain
│   │   └── shared/             # Shared utilities
│   └── workers/                # (placeholder)
├── tests/                      # Test suite (15 test files)
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Dev container
├── Dockerfile.prod             # Production container
└── Makefile                    # Dev commands
```

---

## 2. Key Configuration Files

| File | Purpose |
|------|---------|
| `/apps/api/src/core/config.py` | Pydantic Settings - API, DB, Redis, Scheduler configs |
| `/apps/api/alembic.ini` | Alembic migration config |
| `/apps/api/requirements.txt` | Python dependencies |

### Environment Variables (from config.py)
- `DATABASE_URL` - PostgreSQL connection (supports Supabase)
- `UPSTASH_REDIS_REST_URL/TOKEN` - Redis cache
- `SCHEDULER_ENABLED` - Toggle background jobs
- `DAILY_OHLCV_*` - Daily collection settings
- `FINANCIAL_STATEMENTS_*` - Weekly collection settings
- `RATE_LIMIT_*` - API rate limiting

---

## 3. Features/Modules (src/stocks/)

### Domain Architecture (Feature-based)

| Domain | Router | Service | Purpose |
|--------|--------|---------|---------|
| **market** | `/symbols`, `/sector-performance`, `/vn30-overview` | service.py | Market-wide data |
| **price** | `/{symbol}/history`, `/market-indices`, `/price-board` | service.py | Price & OHLCV data |
| **company** | `/{symbol}/company`, `/{symbol}/shareholders` | company/service.py | Company info |
| **financial** | `/{symbol}/financials/*` | financial/service.py | Financial statements |
| **analytics** | `/analytics/financial-statements`, `/analytics/volume-spikes` | analytics/service.py | Analytics & insights |

---

## 4. Database Models (src/stocks/models.py)

| Model | Table | Purpose |
|-------|-------|---------|
| `StockDailyOHLCV` | `stock_daily_ohlcv` | Daily OHLCV data (symbol, date, OHLCV) |
| `StockIntradayBar` | `stock_intraday_bars` | 5-min intraday bars |
| `FinancialStatement` | `financial_statements` | Quarterly financials (net profit, revenue, EPS) |

### Alembic Migrations
1. `60811b8fd9e3` - Create stock_intraday_bars table
2. `d945d0cac5ec` - Add stock_daily_ohlcv table
3. `6948fc67` - Add top_performers table
4. `a1b2c3d4` - Rename to financial_statements

---

## 5. API Endpoints

### Base: `/api/v1/stocks`

**Market Domain:**
- `GET /symbols` - List all symbols (filter by exchange)
- `GET /symbols/group/{group}` - Symbols by group (VN30, HNX30)
- `GET /symbols/search?q=` - Search symbols
- `GET /sector-performance` - ICB sector performance
- `GET /fund-certificates` - ETFs and funds
- `GET /vn30-overview` - VN30 stocks overview

**Price Domain:**
- `GET /{symbol}/history` - Historical OHLCV
- `GET /{symbol}/intraday` - Intraday ticks
- `GET /market-indices` - VN-INDEX, VN30, HNX
- `GET /price-board?symbols=` - Real-time prices
- `POST /intraday/collect` - Manual intraday collection
- `GET /{symbol}/volume-analysis` - Volume patterns
- `GET /{symbol}/volume-anomalies` - Volume anomaly detection

**Analytics Domain:**
- `GET /analytics/financial-statements` - Top companies by profit
- `POST /analytics/financial-statements/collect` - Manual collection
- `GET /analytics/volume-spikes` - Volume spike detection
- `DELETE /analytics/volume-spikes/cache` - Clear cache

**Jobs Domain (NEW):**
- `GET /api/v1/jobs/status` - Poll job progress

---

## 6. Background Jobs (src/core/scheduler.py)

| Job ID | Schedule | Function |
|--------|----------|----------|
| `intraday-collection-daily` | 15:30 ICT (Mon-Fri) | `collect_intraday_data_job()` |
| `data-cleanup-daily` | 16:00 ICT | `cleanup_old_data_job()` |
| `daily-ohlcv-collection` | 17:00 ICT | `collect_daily_ohlcv_job()` |
| `collect-financial-statements` | Sunday 02:00 ICT | `collect_financial_statements_job()` |

### Startup Recovery
- Checks for missed jobs on API startup
- Runs missed jobs in background (non-blocking)
- Uses `job_status_store.py` for progress tracking

---

## 7. Dependencies (requirements.txt)

**Core:**
- fastapi >= 0.100.0
- uvicorn[standard] >= 0.23.0
- pydantic >= 2.0.0
- pydantic-settings >= 2.0.0

**Database:**
- sqlalchemy >= 2.0.0
- alembic >= 1.12.0
- asyncpg >= 0.28.0 (async PostgreSQL)
- psycopg2-binary >= 2.9.0 (sync PostgreSQL)

**Cache & Rate Limiting:**
- upstash-redis >= 1.0.0
- upstash-ratelimit >= 1.0.0

**Stock Data:**
- vnstock >= 3.0.0
- pandas >= 2.0.0
- numpy >= 1.24.0

**Scheduler:**
- apscheduler >= 4.0.0a6

---

## 8. Recent Changes & Patterns

### New Additions (from git status)
- `src/core/job_status_store.py` - Job progress tracking store
- `src/stocks/jobs_router.py` - Job status polling API
- Supabase migration in progress (config.py, database.py changes)

### Architecture Patterns
- **Feature-based modular architecture** with domain separation
- **TradingHoursCache** - Smart caching with different TTLs for trading/off-hours
- **Rate limiting** - Standard (100/min) and Heavy (20/min) tiers
- **Async/Sync dual engines** - Async for API, Sync for background jobs
- **Startup job recovery** - Catches missed scheduled jobs

### Data Flow
```
vnstock API -> Collectors -> PostgreSQL -> API Endpoints -> Frontend
                  |
                  v
            Upstash Redis (cache)
```

---

## Test Coverage

15 test files covering:
- API endpoints (router tests)
- Services (stocks_service, analytics)
- Collectors (intraday, financial_statements)
- Infrastructure (scheduler, ratelimit, cache)
- Volume analysis & anomaly detection

---

## Unresolved Questions

1. `src/api/v1/endpoints/` - Empty placeholder, purpose unclear
2. `src/workers/` - Empty placeholder, future use?
3. Supabase migration status - In progress per git status
