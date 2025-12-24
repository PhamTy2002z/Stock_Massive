# Phase 3: Migrate Data

## Context
- **Parent:** [plan.md](./plan.md)
- **Depends on:** [Phase 2](./phase-02-configure-backend-connection.md)
- **Research:** [researcher-02-data-migration-strategy.md](./research/researcher-02-data-migration-strategy.md)

## Overview

| Property | Value |
|----------|-------|
| Priority | P1 |
| Status | Pending |
| Effort | 45 min |

Export data from Docker PostgreSQL and import to Supabase.

## Key Insights

- Run Alembic migrations first to create schema
- Export data-only with pg_dump (schema created by Alembic)
- Use `--quote-all-identifiers` to prevent case issues
- Verify row counts after import

## Requirements

### Functional
- Run Alembic migrations on Supabase
- Export all data from Docker PostgreSQL
- Import data to Supabase
- Verify data integrity

### Non-Functional
- Zero data loss
- Maintain foreign key relationships
- Preserve sequence values

## Related Code Files

**Files to reference:**
- `apps/api/alembic/versions/` - migration files
- `apps/api/src/stocks/models.py` - table definitions

## Implementation Steps

### Step 1: Backup Local Database

```bash
# Create timestamped backup FIRST
cd /Users/typham/Documents/GitHub/Stock_Massive

docker-compose exec db pg_dump -U postgres -d stockmassive \
  --format=custom \
  --compress=9 \
  > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Step 2: Run Alembic Migrations on Supabase

```bash
# Set direct connection for migrations
export DATABASE_URL_DIRECT="postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres"

cd apps/api

# Run migrations
alembic upgrade head

# Verify tables created
psql "$DATABASE_URL_DIRECT" -c "\dt"
```

Expected tables:
- `alembic_version`
- `stock_daily_ohlcv`
- `stock_intraday_bars`
- `financial_statements`

### Step 3: Export Data from Docker PostgreSQL

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive

# Export data only (schema already created by Alembic)
docker-compose exec db pg_dump -U postgres -d stockmassive \
  --data-only \
  --no-owner \
  --no-privileges \
  --quote-all-identifiers \
  --table=stock_daily_ohlcv \
  --table=stock_intraday_bars \
  --table=financial_statements \
  > data_export.sql
```

### Step 4: Import Data to Supabase

```bash
# Set connection
export SUPABASE_DB_URL="postgresql://postgres.[project-ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

# Import data
psql "$SUPABASE_DB_URL" -f data_export.sql

# If errors occur, check the output and fix
```

### Step 5: Verify Data Integrity

```bash
# Run on BOTH databases and compare

# Docker (source)
docker-compose exec db psql -U postgres -d stockmassive -c "
SELECT 'stock_daily_ohlcv' as tbl, COUNT(*) as rows FROM stock_daily_ohlcv
UNION ALL
SELECT 'stock_intraday_bars', COUNT(*) FROM stock_intraday_bars
UNION ALL
SELECT 'financial_statements', COUNT(*) FROM financial_statements;
"

# Supabase (target)
psql "$SUPABASE_DB_URL" -c "
SELECT 'stock_daily_ohlcv' as tbl, COUNT(*) as rows FROM stock_daily_ohlcv
UNION ALL
SELECT 'stock_intraday_bars', COUNT(*) FROM stock_intraday_bars
UNION ALL
SELECT 'financial_statements', COUNT(*) FROM financial_statements;
"
```

### Step 6: Fix Sequences (if needed)

```bash
# Reset sequences to max(id) + 1
psql "$SUPABASE_DB_URL" -c "
SELECT setval(pg_get_serial_sequence('stock_daily_ohlcv', 'id'),
       COALESCE((SELECT MAX(id) FROM stock_daily_ohlcv), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('stock_intraday_bars', 'id'),
       COALESCE((SELECT MAX(id) FROM stock_intraday_bars), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('financial_statements', 'id'),
       COALESCE((SELECT MAX(id) FROM financial_statements), 0) + 1, false);
"
```

## Todo List

- [ ] Create backup of Docker database
- [ ] Run Alembic migrations on Supabase
- [ ] Verify tables created correctly
- [ ] Export data from Docker PostgreSQL
- [ ] Import data to Supabase
- [ ] Verify row counts match
- [ ] Fix sequences if needed
- [ ] Keep backup file for 7 days

## Success Criteria

- [ ] All 3 tables have matching row counts
- [ ] No import errors
- [ ] Sequences reset correctly
- [ ] Indexes created by Alembic

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Data export fails | Create backup first, retry |
| Import errors | Check error messages, may need to DROP and re-CREATE |
| Missing data | Compare row counts, re-export if needed |
| Sequence mismatch | Run setval() to fix |

## Security Considerations

- Delete data_export.sql after successful import (contains data)
- Keep backup_*.dump encrypted or secured
- Don't commit export files to git

## Next Steps

→ [Phase 4: Update Docker & Cleanup](./phase-04-update-docker-cleanup.md)
