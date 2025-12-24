---
title: "Supabase Database Migration"
description: "Migrate PostgreSQL from Docker to Supabase Free Tier for easier management"
status: pending
priority: P2
effort: 3h
branch: main
tags: [database, infrastructure, supabase, migration]
created: 2025-12-24
---

# Supabase Database Migration Plan

## Overview

Migrate PostgreSQL database from Docker container to Supabase (Free Tier) for easier management and maintenance. Keep FastAPI backend unchanged except connection configuration.

## Context

- **Brainstorm Report:** [brainstorm-251224-2013-supabase-database-migration.md](../reports/brainstorm-251224-2013-supabase-database-migration.md)
- **Research - SQLAlchemy Config:** [researcher-01-supabase-sqlalchemy-config.md](./research/researcher-01-supabase-sqlalchemy-config.md)
- **Research - Data Migration:** [researcher-02-data-migration-strategy.md](./research/researcher-02-data-migration-strategy.md)

## Current State

```
Docker Compose
├── db (PostgreSQL 16) ← TO BE REMOVED
├── api (FastAPI)
└── web (Next.js)
```

### Tables to Migrate
| Table | Records | Estimated Size |
|-------|---------|----------------|
| `stock_daily_ohlcv` | ~TBD | ~10MB/year |
| `stock_intraday_bars` | ~TBD | ~5MB/year |
| `financial_statements` | ~800 | ~320KB |

## Target State

```
Docker Compose              Supabase (Cloud)
├── api (FastAPI)  ──────►  PostgreSQL
└── web (Next.js)           + Dashboard
```

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Setup Supabase Project | Pending | 15m | [phase-01](./phase-01-setup-supabase-project.md) |
| 2 | Configure Backend Connection | Pending | 30m | [phase-02](./phase-02-configure-backend-connection.md) |
| 3 | Migrate Data | Pending | 45m | [phase-03](./phase-03-migrate-data.md) |
| 4 | Update Docker & Cleanup | Pending | 30m | [phase-04](./phase-04-update-docker-cleanup.md) |
| 5 | Test & Validate | Pending | 1h | [phase-05](./phase-05-test-validate.md) |

## Dependencies

- Supabase account (free tier)
- Docker running with current database containing data
- psql CLI installed locally

## Success Criteria

- [ ] All 3 tables migrated with data integrity
- [ ] API endpoints respond correctly (<200ms latency acceptable)
- [ ] Scheduled jobs work (intraday, daily OHLCV, financial statements)
- [ ] Frontend displays data correctly
- [ ] No connection errors under normal load
- [ ] Docker `db` service removed

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Latency increase (~50-100ms) | Low | Acceptable for personal project |
| Free tier pause (7 days inactive) | Medium | Daily scheduler jobs prevent this |
| Data loss during migration | Medium | Backup before migration, verify row counts |

---

## Validation Summary

**Validated:** 2025-12-24
**Questions asked:** 5

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Docker DB after migration | **Xóa vĩnh viễn** - Remove completely |
| Backup strategy | **Supabase backup** - Trust managed backup |
| Environments | **Single project** - 1 Supabase project for all |
| Migration timing | **Ngay bây giờ** - Proceed immediately |
| Rollback strategy | **Chỉ giữ backup file** - Keep dump file only |

### Action Items

- [x] Plan validated, no changes needed
- [ ] Proceed to implementation
