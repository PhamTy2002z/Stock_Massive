# Intraday Volume Analysis Feature

**Created:** 2024-12-18
**Status:** Planning
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
| 01 | [Database Setup](phase-01-database-setup.md) | Pending | 0% |
| 02 | [Data Collection Service](phase-02-data-collection-service.md) | Pending | 0% |
| 03 | [Volume Analysis API](phase-03-volume-analysis-api.md) | Pending | 0% |
| 04 | [Scheduled Jobs](phase-04-scheduled-jobs.md) | Pending | 0% |

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

- [ ] Database migrations run successfully
- [ ] Intraday data collected and stored for test symbol
- [ ] Volume analysis endpoint returns correct peak periods
- [ ] Scheduled job executes at 15:30 daily
- [ ] Data retention cleanup works

## Risks

| Risk | Mitigation |
|------|------------|
| vnstock 5-min data unavailable | Fall back to tick aggregation |
| API rate limits | Batch requests, add delays |
| Large data volume | Start with VN30 symbols only |
