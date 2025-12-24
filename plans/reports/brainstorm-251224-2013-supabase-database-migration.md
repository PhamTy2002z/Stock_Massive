# Brainstorm Report: Supabase Database Migration

**Date:** 2025-12-24
**Status:** Ready for Implementation
**Approach:** Migrate PostgreSQL from Docker to Supabase (Free Tier)

---

## Problem Statement

Current setup runs PostgreSQL inside Docker container. User wants to:
- Separate database from Docker for easier management
- Keep FastAPI backend (only change connection string)
- Migrate all existing data
- Use Supabase Free Tier

---

## Current Architecture

```
Docker Compose
├── db (PostgreSQL 16-alpine) ← TO BE REMOVED
├── api (FastAPI)
└── web (Next.js)
```

### Database Schema (3 tables)

| Table | Purpose | Estimated Size/Year |
|-------|---------|---------------------|
| `stock_daily_ohlcv` | Daily OHLCV data | ~10MB |
| `stock_intraday_bars` | 5-min bars (5 symbols) | ~5MB |
| `financial_statements` | Quarterly financials | ~320KB |

**Total:** ~15-20MB/year (well within 500MB limit)

---

## Supabase Free Tier Constraints

| Limit | Value | Impact |
|-------|-------|--------|
| Database Storage | 500MB | OK for current + 20+ years |
| Egress | 10GB/month | OK for API traffic |
| Direct Connections | 60 | OK (FastAPI uses 5+10 pool) |
| Pooler Connections | 200 | OK |
| Projects | 2 per org | OK |
| **Pause after inactive** | 7 days | **Mitigated: daily usage** |

---

## Migration Approach

### Phase 1: Setup Supabase Project
1. Create Supabase project (region: Singapore recommended for VN)
2. Get connection strings (direct + pooler)
3. Configure Transaction mode for SQLAlchemy

### Phase 2: Schema Migration
1. Run Alembic migrations against Supabase
2. Verify all tables, indexes, constraints created

### Phase 3: Data Migration
1. Export data from Docker PostgreSQL using `pg_dump`
2. Import to Supabase using `psql` or Supabase dashboard

### Phase 4: Backend Configuration
1. Update `DATABASE_URL` environment variable
2. Use pooler connection string (port 6543) for session mode
3. Update docker-compose to remove `db` service

### Phase 5: Testing & Validation
1. Run API tests
2. Verify scheduler jobs work
3. Check data integrity

---

## Code Changes Required

### 1. Environment Variables

```bash
# Before (Docker)
DATABASE_URL=postgresql://postgres:postgres@db:5432/stockmassive

# After (Supabase - Transaction Mode)
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

### 2. docker-compose.yml Changes

```yaml
# Remove db service entirely
# Update api service:
services:
  api:
    # Remove depends_on: db
    environment:
      DATABASE_URL: ${DATABASE_URL}  # From .env (Supabase)
```

### 3. SQLAlchemy Configuration (Optional Optimization)

For better compatibility with Supabase pooler:

```python
# database.py - add statement_cache_size=0 for Transaction mode
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"statement_cache_size": 0}  # Required for PgBouncer
)
```

---

## Data Migration Commands

```bash
# 1. Export from Docker PostgreSQL
docker-compose exec db pg_dump -U postgres -d stockmassive \
  --data-only --no-owner --no-privileges > backup.sql

# 2. Import to Supabase
psql "postgresql://postgres.[ref]:[pass]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres" \
  < backup.sql
```

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Latency increase (~50-100ms) | Low | Acceptable for personal project |
| Connection pool exhaustion | Low | Use Transaction mode pooler |
| Storage limit exceeded | Low | Current growth = 20MB/year, limit = 500MB |
| Project pause (7 days inactive) | Medium | Daily scheduler jobs will prevent this |
| Supabase outage | Low | Acceptable for non-critical app |

---

## Success Criteria

- [ ] All 3 tables migrated with data integrity
- [ ] Alembic migrations run successfully
- [ ] API endpoints respond correctly
- [ ] Scheduled jobs (intraday, daily OHLCV, financial statements) work
- [ ] Frontend displays data correctly
- [ ] No connection errors under normal load

---

## Estimated Effort

| Task | Time |
|------|------|
| Setup Supabase project | 15 min |
| Run migrations | 15 min |
| Export/Import data | 30 min |
| Update config & docker-compose | 30 min |
| Testing & validation | 1 hour |
| **Total** | **~2-3 hours** |

---

## Decision

**Approved:** Migrate to Supabase PostgreSQL (Free Tier)

**Rationale:**
1. Minimal code changes (just connection string)
2. Free tier sufficient for personal project
3. Daily usage prevents pause
4. Dashboard provides visual data management
5. Supabase Auth already scaffolded in frontend

---

## Next Steps

1. User creates Supabase project
2. Run `/plan` to generate detailed implementation steps
3. Execute migration

---

## Unresolved Questions

1. **Backup strategy**: Do you want to keep periodic local backups even with Supabase?
2. **Multiple environments**: Do you need separate Supabase projects for dev/prod?
