# PostgreSQL to Supabase Data Migration Strategy

## 1. Data Export (pg_dump)

### Recommended Command
```bash
# Full export with clean import options
pg_dump "$LOCAL_DB_URL" \
  --clean \
  --if-exists \
  --quote-all-identifiers \
  --no-owner \
  --no-privileges \
  > stock_massive_dump.sql
```

### Key Flags Explained
| Flag | Purpose |
|------|---------|
| `--clean` | DROP objects before CREATE (clean slate) |
| `--if-exists` | Add IF EXISTS to DROP commands |
| `--quote-all-identifiers` | Prevent case-sensitivity issues |
| `--no-owner` | Skip ownership (Supabase manages this) |
| `--no-privileges` | Skip GRANT/REVOKE (RLS handles this) |

### Export Specific Tables Only
```bash
pg_dump "$LOCAL_DB_URL" \
  --table=stock_daily_ohlcv \
  --table=stock_intraday_bars \
  --table=financial_statements \
  --clean --if-exists --quote-all-identifiers \
  --no-owner --no-privileges \
  > stock_tables_dump.sql
```

### Handle Sequences Separately (for large datasets)
```bash
# Export sequences after data
pg_dump "$LOCAL_DB_URL" --data-only \
  --table='*_seq' --table='*_id_seq' > sequences.sql
```

## 2. Data Import to Supabase

### Get Supabase Connection String
- Dashboard > Project Settings > Database > Connection String
- Use "Session mode" pooler (port 5432) for migrations

### Import Command
```bash
# Set connection (replace with actual credentials)
export SUPABASE_DB_URL="postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres"

# Run import
psql -d "$SUPABASE_DB_URL" -f stock_tables_dump.sql

# Import sequences after data
psql -d "$SUPABASE_DB_URL" -f sequences.sql
```

### Large Dataset Handling
For `stock_intraday_bars` (likely largest):
```bash
# Split export by table for parallel import
pg_dump "$LOCAL_DB_URL" -t stock_intraday_bars --data-only > intraday.sql
pg_dump "$LOCAL_DB_URL" -t stock_daily_ohlcv --data-only > daily.sql
pg_dump "$LOCAL_DB_URL" -t financial_statements --data-only > financials.sql

# Import separately (can run in parallel if needed)
psql -d "$SUPABASE_DB_URL" -f daily.sql
psql -d "$SUPABASE_DB_URL" -f financials.sql
psql -d "$SUPABASE_DB_URL" -f intraday.sql
```

## 3. Migration Verification

### Row Count Validation
```sql
-- Run on BOTH databases, compare results
SELECT
  'stock_daily_ohlcv' as table_name, COUNT(*) as rows FROM stock_daily_ohlcv
UNION ALL
SELECT
  'stock_intraday_bars', COUNT(*) FROM stock_intraday_bars
UNION ALL
SELECT
  'financial_statements', COUNT(*) FROM financial_statements;
```

### Data Integrity Checksums
```sql
-- Sample checksum (run on both, compare)
SELECT md5(string_agg(t::text, ''))
FROM (SELECT * FROM stock_daily_ohlcv ORDER BY symbol, date LIMIT 1000) t;
```

### Index Verification
```sql
-- List all indexes on migrated tables
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('stock_daily_ohlcv','stock_intraday_bars','financial_statements');
```

## 4. Rollback Strategy

### Pre-Migration Backup
```bash
# Create timestamped backup BEFORE any changes
pg_dump "$LOCAL_DB_URL" \
  --format=custom \
  --compress=9 \
  > backup_$(date +%Y%m%d_%H%M%S).dump

# Restore if needed
pg_restore -d "$LOCAL_DB_URL" backup_*.dump
```

### Testing Checklist
- [ ] Export to local test Supabase project first
- [ ] Verify all 3 tables imported
- [ ] Run app against Supabase (read-only test)
- [ ] Confirm vnstock data fetching works
- [ ] Only then update production connection string

### Safe Cutover Process
1. Stop scheduler jobs
2. Set local DB to read-only: `ALTER DATABASE stockdb SET default_transaction_read_only = true;`
3. Final sync of sequences
4. Switch app to Supabase URL
5. Verify functionality
6. Keep local backup for 7 days minimum

---

## Quick Reference Commands

```bash
# Complete migration in 4 commands:
export LOCAL_DB_URL="postgresql://user:pass@localhost:5432/stockdb"
export SUPABASE_DB_URL="postgresql://postgres.[ref]:[pass]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

# 1. Export
pg_dump "$LOCAL_DB_URL" --clean --if-exists --quote-all-identifiers --no-owner --no-privileges > dump.sql

# 2. Import
psql -d "$SUPABASE_DB_URL" -f dump.sql

# 3. Verify
psql -d "$SUPABASE_DB_URL" -c "SELECT relname, n_live_tup FROM pg_stat_user_tables;"

# 4. Keep backup
mv dump.sql backup_$(date +%Y%m%d).sql
```
