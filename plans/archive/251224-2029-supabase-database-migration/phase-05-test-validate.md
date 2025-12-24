# Phase 5: Test & Validate

## Context
- **Parent:** [plan.md](./plan.md)
- **Depends on:** [Phase 4](./phase-04-update-docker-cleanup.md)

## Overview

| Property | Value |
|----------|-------|
| Priority | P1 |
| Status | Pending |
| Effort | 1 hour |

Comprehensive testing to ensure migration success.

## Key Insights

- Test all API endpoints
- Verify scheduler jobs work
- Check frontend displays data correctly
- Monitor latency increase (expected ~50-100ms)

## Requirements

### Functional
- All 30+ API endpoints work
- Scheduler jobs execute successfully
- Frontend pages render data
- Data writes work (new data collection)

### Non-Functional
- Latency < 500ms (acceptable for personal project)
- No connection errors
- Graceful degradation if Supabase unavailable

## Implementation Steps

### Step 1: API Health Check

```bash
# Test API is running
curl http://localhost:8000/docs

# Test basic endpoint
curl http://localhost:8000/api/v1/stocks/market-indices
```

### Step 2: Test Key Endpoints

```bash
# Market data
curl http://localhost:8000/api/v1/stocks/symbols | head
curl http://localhost:8000/api/v1/stocks/vn30-overview
curl http://localhost:8000/api/v1/stocks/sector-performance

# Stock detail
curl http://localhost:8000/api/v1/stocks/VCB/detail
curl http://localhost:8000/api/v1/stocks/VCB/history

# Analytics (database-dependent)
curl "http://localhost:8000/api/v1/stocks/analytics/financial-statements?limit=10"
curl http://localhost:8000/api/v1/stocks/analytics/volume-spikes

# Financials
curl http://localhost:8000/api/v1/stocks/VCB/financials/ratios
```

### Step 3: Verify Scheduler Jobs

```bash
# Check scheduler logs
docker-compose logs api | grep -i scheduler

# Manual trigger test (if endpoint exists)
# curl -X POST http://localhost:8000/api/v1/stocks/intraday/collect

# Check scheduled job execution in logs after 15:30 ICT
```

### Step 4: Test Frontend

1. Open http://localhost:3000
2. Verify:
   - [ ] Market indices cards load
   - [ ] VN30 overview table loads
   - [ ] Sector performance loads
   - [ ] Stock search works
   - [ ] Stock detail page works (try VCB, FPT, VNM)
   - [ ] Volume spikes page loads (analytics/volume-spikes)
   - [ ] Financial statements page loads (analytics/financial-statements)

### Step 5: Test Data Writing

```bash
# Trigger a test data write (if safe to do so)
# Wait for scheduled job or manually trigger

# Verify new data appears in Supabase dashboard
```

### Step 6: Latency Check

```bash
# Measure response time
time curl -o /dev/null -s -w '%{time_total}s\n' \
  http://localhost:8000/api/v1/stocks/analytics/financial-statements

# Expected: < 0.5s for cached, < 1s for uncached
```

### Step 7: Run Backend Tests

```bash
cd apps/api

# Run test suite
pytest tests/ -v

# If tests fail due to database, check DATABASE_URL_TEST env
```

## Todo List

- [ ] Verify API health endpoint
- [ ] Test market data endpoints
- [ ] Test stock detail endpoints
- [ ] Test analytics endpoints (financial-statements, volume-spikes)
- [ ] Check scheduler job logs
- [ ] Test all frontend pages
- [ ] Verify data appears in Supabase dashboard
- [ ] Measure and document latency
- [ ] Run backend test suite
- [ ] Document any issues found

## Success Criteria

- [ ] All API endpoints return 200 OK
- [ ] Financial statements endpoint returns data from Supabase
- [ ] Volume spikes endpoint works
- [ ] Frontend renders all pages without errors
- [ ] Scheduler logs show no database errors
- [ ] Latency acceptable (< 500ms for API calls)
- [ ] Test suite passes (or failures are unrelated to migration)

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Endpoints fail | Check error message, verify DATABASE_URL |
| Slow responses | Expected ~50-100ms increase, acceptable |
| Scheduler fails | Check network connectivity to Supabase |
| Frontend errors | Check browser console, verify API responses |

## Rollback Plan

If critical issues found:

1. Stop Docker containers: `docker-compose down`
2. Restore .env with Docker DATABASE_URL
3. Add db service back to docker-compose.yml
4. Restore backup: `docker-compose up -d db && pg_restore -d stockmassive backup_*.dump`
5. Restart: `docker-compose up -d`

## Post-Migration Tasks

- [ ] Update README.md with new setup instructions
- [ ] Update docs/deployment-guide.md
- [ ] Remove backup files after 7 days
- [ ] Monitor Supabase dashboard for usage

## Unresolved Questions

- Need to verify if existing tests mock database or require real connection
- Consider adding health check endpoint that verifies database connectivity
