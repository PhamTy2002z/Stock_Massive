# Phase 5: Integration Testing & Verification

**Date:** 2024-12-19
**Priority:** P2
**Status:** pending
**Effort:** 1h

## Context

- [Plan Overview](plan.md)
- **Depends on:** Phase 1-4 (all refactoring complete)

## Overview

Comprehensive testing and verification of refactored architecture. Ensure all endpoints work, tests pass, and backward compatibility maintained. Clean up backup files after successful verification.

## Related Files

- All test files in `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/tests/`
- Backup files: `service_old.py`, `schemas_old.py`, `router_old.py`

## Requirements

1. All 8 existing test files must pass
2. All 27 API endpoints functional
3. Manual endpoint testing
4. Import verification
5. Performance baseline check
6. Clean up backup files

## Implementation Steps

### Step 1: Run Unit Tests

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api

# Test individual modules
pytest tests/test_stocks_service.py -v
pytest tests/test_stocks_router.py -v
pytest tests/test_volume_analysis.py -v
pytest tests/test_intraday_collector.py -v
pytest tests/test_sector_performance.py -v
pytest tests/test_database_phase01.py -v
pytest tests/test_scheduler.py -v

# Full test suite
pytest tests/ -v --tb=short
```

**Expected:** All tests pass without modification.

### Step 2: Test Coverage Check

```bash
pytest tests/ --cov=src.stocks --cov-report=term-missing
```

**Expected:** Coverage maintained or improved (target: 80%+).

### Step 3: Manual API Testing

Start the API server:

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api
uvicorn src.main:app --reload
```

Test all endpoint categories:

#### Symbol/Market Endpoints

```bash
# List all symbols
curl http://localhost:8000/api/v1/stocks/symbols | jq '.[0:3]'

# Symbols by group
curl http://localhost:8000/api/v1/stocks/symbols/group/VN30 | jq '.[0:5]'

# Search symbols
curl "http://localhost:8000/api/v1/stocks/symbols/search?q=VCB" | jq
```

#### Price Endpoints

```bash
# Historical data
curl "http://localhost:8000/api/v1/stocks/VCB/history?start=2024-01-01&end=2024-01-31&interval=1D" | jq '.[0:2]'

# Intraday data
curl http://localhost:8000/api/v1/stocks/VCB/intraday | jq '.[0:2]'

# Market indices
curl http://localhost:8000/api/v1/stocks/market-indices | jq

# Price board
curl "http://localhost:8000/api/v1/stocks/price-board?symbols_list=VN30" | jq '.[0:2]'

# Volume analysis
curl http://localhost:8000/api/v1/stocks/VCB/volume-analysis | jq
```

#### Company Endpoints

```bash
# Company overview
curl http://localhost:8000/api/v1/stocks/VCB/company | jq

# Stock detail (composite)
curl http://localhost:8000/api/v1/stocks/VCB/detail | jq

# Shareholders
curl http://localhost:8000/api/v1/stocks/VCB/shareholders | jq

# Officers
curl http://localhost:8000/api/v1/stocks/VCB/officers | jq

# Insider deals
curl http://localhost:8000/api/v1/stocks/VCB/insider-deals | jq
```

#### Financial Endpoints

```bash
# Financial ratios
curl http://localhost:8000/api/v1/stocks/VCB/financials/ratios | jq '.[0:2]'

# Income statement (simple)
curl http://localhost:8000/api/v1/stocks/VCB/financials/income | jq '.[0:2]'

# Income statement (detailed)
curl http://localhost:8000/api/v1/stocks/VCB/financials/income-statement | jq

# Balance sheet (simple)
curl http://localhost:8000/api/v1/stocks/VCB/financials/balance-sheet | jq '.[0:2]'

# Balance sheet (detailed)
curl http://localhost:8000/api/v1/stocks/VCB/financials/balance-sheet-detailed | jq

# Cash flow
curl http://localhost:8000/api/v1/stocks/VCB/financials/cash-flow | jq
```

#### Market Endpoints

```bash
# Sector performance
curl http://localhost:8000/api/v1/stocks/sector-performance | jq

# Fund certificates
curl http://localhost:8000/api/v1/stocks/fund-certificates | jq
```

### Step 4: OpenAPI Documentation Check

```bash
# Open Swagger UI
open http://localhost:8000/docs

# Verify OpenAPI JSON
curl http://localhost:8000/openapi.json | jq '.paths | keys' | grep stocks
```

**Verify:**
- All 27 endpoints listed under "stocks" tag
- Request/response schemas correct
- Descriptions preserved
- Query parameters documented

### Step 5: Import Verification

Test backward compatibility of imports:

```python
# Test in Python REPL
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api
python

>>> from src.stocks import StockService, get_stock_service
>>> from src.stocks.schemas import StockPrice, CompanyOverview, FinancialRatio
>>> from src.stocks.shared import StockServiceError, validate_symbol
>>>
>>> # Test service instantiation
>>> service = get_stock_service()
>>> print(type(service))
>>> print(hasattr(service, 'price'))
>>> print(hasattr(service, 'company'))
>>> print(hasattr(service, 'financial'))
>>> print(hasattr(service, 'market'))
```

**Expected:** All imports work, service has domain attributes.

### Step 6: Performance Baseline

Compare response times before/after refactor:

```bash
# Test response time for key endpoints
time curl -s http://localhost:8000/api/v1/stocks/VCB/detail > /dev/null
time curl -s http://localhost:8000/api/v1/stocks/market-indices > /dev/null
time curl -s http://localhost:8000/api/v1/stocks/sector-performance > /dev/null
```

**Expected:** No significant performance degradation (< 5% difference).

### Step 7: Frontend Integration Test

Start both frontend and backend:

```bash
# Terminal 1: Backend
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api
uvicorn src.main:app --reload

# Terminal 2: Frontend
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/web
pnpm dev
```

Test in browser:
1. Navigate to `http://localhost:3000`
2. Search for stock (e.g., VCB)
3. View stock detail page
4. Check market indices cards
5. View sector performance tab
6. Verify all data loads correctly

**Expected:** No frontend errors, all data displays correctly.

### Step 8: Error Handling Verification

Test error scenarios:

```bash
# Invalid symbol
curl http://localhost:8000/api/v1/stocks/INVALID/detail
# Expected: 502 with StockServiceError message

# Invalid date range
curl "http://localhost:8000/api/v1/stocks/VCB/history?start=2024-12-31&end=2024-01-01"
# Expected: 502 or validation error

# Missing query parameter
curl http://localhost:8000/api/v1/stocks/symbols/search
# Expected: 422 validation error
```

### Step 9: Database Operations Test

Test intraday data collection (if database configured):

```bash
# Trigger collection
curl -X POST http://localhost:8000/api/v1/stocks/intraday/collect | jq

# Check volume analysis
curl http://localhost:8000/api/v1/stocks/VCB/volume-analysis | jq
```

**Expected:** Database operations work correctly.

### Step 10: Clean Up Backup Files

After all tests pass:

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks

# Remove backup files
rm -f service_old.py
rm -f schemas_old.py
rm -f router_old.py

# Verify clean structure
tree -L 2
```

### Step 11: Update Documentation

Update relevant documentation files:

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/docs/system-architecture.md`

Add section on domain-based architecture:

```markdown
## Backend Architecture - Stocks Module

The stocks module follows domain-based modular architecture:

- **shared/**: Common utilities (exceptions, validators, converters)
- **price/**: Price data (history, intraday, market indices)
- **company/**: Company info (overview, shareholders, officers)
- **financial/**: Financial data (ratios, statements)
- **market/**: Market-wide data (symbols, sectors, funds)

Each domain has:
- `service.py`: Business logic
- `schemas.py`: Pydantic models
- `router.py`: API endpoints

Main `StockService` acts as facade, delegating to domain services.
```

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/docs/codebase-summary.md`

Update stocks module section with new structure.

### Step 12: Git Commit

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive

# Stage changes
git add apps/api/src/stocks/

# Commit with descriptive message
git commit -m "refactor(stocks): split monolithic module into domain-based architecture

- Extract shared utilities (exceptions, validators, converters)
- Split schemas into 5 domain modules (price, company, financial, market, common)
- Split services into 4 domain services + facade
- Split routers into 4 domain routers + aggregator
- Maintain backward compatibility via re-exports
- All 27 endpoints functional, all tests passing

Reduces service.py from 1507 to ~50 lines (facade)
Reduces schemas.py from 426 to re-export module
Reduces router.py from 485 to aggregator

Closes #[issue-number]"
```

## Success Criteria

- [ ] All 8 test files pass
- [ ] All 27 API endpoints functional
- [ ] Manual testing successful for all categories
- [ ] OpenAPI docs complete and correct
- [ ] Import backward compatibility verified
- [ ] No performance degradation
- [ ] Frontend integration working
- [ ] Error handling preserved
- [ ] Database operations functional
- [ ] Backup files removed
- [ ] Documentation updated
- [ ] Changes committed to git

## Testing Checklist

### Unit Tests
- [ ] `test_stocks_service.py` - All service methods
- [ ] `test_stocks_router.py` - All router endpoints
- [ ] `test_volume_analysis.py` - Volume analysis logic
- [ ] `test_intraday_collector.py` - Data collection
- [ ] `test_sector_performance.py` - Sector data
- [ ] `test_database_phase01.py` - Database models
- [ ] `test_scheduler.py` - Scheduled jobs

### API Endpoints (27 total)
- [ ] GET `/symbols` (3 endpoints)
- [ ] GET `/price-board`, `/market-indices` (2 endpoints)
- [ ] GET `/{symbol}/history`, `/{symbol}/intraday` (2 endpoints)
- [ ] POST `/intraday/collect` (1 endpoint)
- [ ] GET `/{symbol}/volume-analysis` (1 endpoint)
- [ ] GET `/{symbol}/company`, `/{symbol}/detail` (2 endpoints)
- [ ] GET `/{symbol}/shareholders`, `/officers`, `/insider-deals` (3 endpoints)
- [ ] GET `/{symbol}/financials/*` (6 endpoints)
- [ ] GET `/sector-performance`, `/fund-certificates` (2 endpoints)

### Integration
- [ ] Frontend loads data correctly
- [ ] Database operations work
- [ ] Error handling preserved
- [ ] Performance acceptable

## Risk Assessment

**Low Risk:**
- All refactoring complete in previous phases
- This phase is verification only
- Backup files available for rollback

**Mitigation:**
- Comprehensive test coverage
- Manual testing of all endpoints
- Frontend integration verification
- Keep backup files until all tests pass
- Document any issues found

## Rollback Plan

If critical issues found:

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks

# Restore from backups
mv service_old.py service.py
mv schemas_old.py schemas.py
mv router_old.py router.py

# Remove new structure
rm -rf shared/ price/ company/ financial/ market/ schemas/

# Restart server
uvicorn src.main:app --reload
```

## Performance Metrics

Track these metrics before/after:

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| service.py lines | 1507 | ~50 | -97% |
| schemas.py lines | 426 | ~20 | -95% |
| router.py lines | 485 | ~30 | -94% |
| Total files | 6 | 23 | +283% |
| Test coverage | X% | Y% | +Z% |
| Avg response time | Xms | Yms | ±Z% |

## Unresolved Questions

None - all architectural decisions made in previous phases.

## Next Steps

After successful verification:
1. Monitor production for any issues
2. Consider adding domain-specific tests
3. Evaluate further optimizations (caching, async)
4. Document lessons learned
