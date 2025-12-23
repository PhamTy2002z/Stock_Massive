# Intraday Volume Analysis Feature

**Created:** 2024-12-18
**Status:** ✅ Completed
**Branch:** main

## Overview

Enable retrieval and analysis of 10-day historical intraday trading data to identify peak volume periods within trading sessions (9:00-15:00 Vietnam time).

## Goals

1. Store 5-minute OHLCV bars in PostgreSQL
2. Collect intraday tick data from vnstock, aggregate to 5-min bars
3. Provide API endpoint for volume analysis by time period
4. Schedule daily data collection after market close (15:30)

## Implementation Phases

| Phase | Name | Status | Progress |
|-------|------|--------|----------|
| 01 | [Database Setup](phase-01-database-setup.md) | ✅ Completed | 100% |
| 02 | [Data Collection Service](phase-02-data-collection-service.md) | ✅ Completed | 100% |
| 03 | [Volume Analysis API](phase-03-volume-analysis-api.md) | ✅ Completed | 100% |
| 04 | [Scheduled Jobs](phase-04-scheduled-jobs.md) | ✅ Completed | 100% |

## Dependencies

- PostgreSQL 16 (configured)
- SQLAlchemy 2.0 + asyncpg (in requirements.txt)
- Alembic (configured, no migrations yet)
- vnstock >= 3.0.0 (integrated)
- APScheduler 4.x (to add)

## Research

- [SQLAlchemy Async Patterns](research/researcher-01-sqlalchemy-async.md)
- [APScheduler + FastAPI](research/researcher-02-apscheduler-fastapi.md)
- [Brainstorm Report](../reports/brainstorm-251218-intraday-volume-database-design.md)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
├─────────────────────────────────────────────────────────────┤
│  Scheduler (APScheduler)                                     │
│  └── Daily 15:30: collect_intraday_data()                   │
├─────────────────────────────────────────────────────────────┤
│  API Endpoints                                               │
│  └── GET /stocks/{symbol}/volume-analysis                   │
├─────────────────────────────────────────────────────────────┤
│  Services                                                    │
│  ├── StockService (existing) - vnstock integration          │
│  └── IntradayService (new) - data collection + analysis     │
├─────────────────────────────────────────────────────────────┤
│  Database (PostgreSQL)                                       │
│  └── stock_intraday_bars table                              │
└─────────────────────────────────────────────────────────────┘
```

## Success Criteria

- [x] Database migrations run successfully
- [x] Intraday data collected and stored for test symbol
- [x] Volume analysis endpoint returns correct peak periods
- [x] Scheduled job executes at 15:30 daily
- [x] Data retention cleanup works

## Risks

| Risk | Mitigation |
|------|------------|
| vnstock 5-min data unavailable | Fall back to tick aggregation |
| API rate limits | Batch requests, add delays |
| Large data volume | Start with VN30 symbols only |

## Completion Notes
- Database migration: `apps/api/alembic/versions/60811b8fd9e3_create_stock_intraday_bars_table.py`
- Model: `StockIntradayBar` in `apps/api/src/stocks/models.py`
- Collector service: `apps/api/src/stocks/intraday_collector.py`
- Scheduler jobs: `apps/api/src/stocks/jobs.py`
- Tests: `apps/api/tests/test_intraday_collector.py`
