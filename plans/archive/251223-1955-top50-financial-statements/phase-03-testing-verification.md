# Phase 3: Testing & Verification

## Context Links

- [Main Plan](./plan.md)
- [Phase 1 - Backend](./phase-01-backend-exchange-normalization.md)
- [Phase 2 - Frontend](./phase-02-frontend-exchange-filter.md)

## Overview

- **Priority**: P1
- **Status**: Complete
- **Description**: Verify all changes work correctly end-to-end

## Key Insights

- Backend changes can be tested with curl
- Frontend changes need browser testing
- Cache invalidation happens automatically on data refresh

## Requirements

### Functional
- All test cases pass
- No regressions in existing functionality

### Non-Functional
- Response times < 500ms (cached)
- No console errors

## Test Cases

### Backend API Tests

```bash
# Test 1: HOSE filter returns HSX data
curl -s "http://localhost:8000/api/v1/stocks/analytics/financial-statements?exchange=HOSE&limit=5" | jq '.data[].exchange'
# Expected: ["HSX", "HSX", "HSX", "HSX", "HSX"]

# Test 2: HSX still works (backward compatibility)
curl -s "http://localhost:8000/api/v1/stocks/analytics/financial-statements?exchange=HSX&limit=5" | jq '.data | length'
# Expected: 5

# Test 3: HNX filter
curl -s "http://localhost:8000/api/v1/stocks/analytics/financial-statements?exchange=HNX&limit=5" | jq '.data[].exchange'
# Expected: ["HNX", "HNX", "HNX", "HNX", "HNX"]

# Test 4: Invalid exchange rejected
curl -s "http://localhost:8000/api/v1/stocks/analytics/financial-statements?exchange=INVALID"
# Expected: 422 Validation Error

# Test 5: Default returns all
curl -s "http://localhost:8000/api/v1/stocks/analytics/financial-statements?limit=50" | jq '.total'
# Expected: Total count including HSX, HNX, UPCOM
```

### Frontend UI Tests

| Test | Steps | Expected |
|------|-------|----------|
| Load page | Navigate to `/analytics/financial-statements` | Table loads with 50 records |
| Filter HOSE | Click dropdown, select HOSE | Table shows only HOSE stocks, badge shows "HOSE" |
| Filter HNX | Select HNX | Table shows only HNX stocks |
| Filter All | Select "Tất cả sàn" | Table shows combined |
| Pagination reset | On page 3, change filter | Resets to page 1 |
| Loading state | Change filter | Shows loading indicator |
| Error state | Disconnect API | Shows error message |

### Database Verification

```sql
-- Verify data distribution
SELECT exchange, COUNT(*) as count
FROM financial_statements
WHERE year = 2025 AND quarter = 3
GROUP BY exchange;

-- Verify top 50 ranking
SELECT rank, symbol, exchange, net_profit
FROM financial_statements
WHERE year = 2025 AND quarter = 3
  AND exchange IN ('HSX', 'HNX')
ORDER BY rank
LIMIT 50;
```

## Todo List

- [x] Run backend curl tests
- [x] Verify 422 on invalid exchange
- [x] Test frontend filter dropdown
- [x] Verify HSX → HOSE display mapping
- [x] Test pagination reset on filter change
- [x] Check browser console for errors
- [x] Verify cache works (second request faster)

## Success Criteria

- [x] All 5 backend tests pass
- [x] All 7 frontend tests pass
- [x] No console errors in browser
- [x] Response time < 500ms on cached requests

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Cache shows stale data | Manual refresh or wait for TTL |
| Test data missing | Verify Q3-2025 data exists first |

## Security Considerations

- Verify 422 error doesn't leak internal info
- Check no XSS in exchange display

## Next Steps

After all tests pass:
1. Commit changes with conventional commit message
2. Update documentation if needed
3. Consider adding year/quarter selector (future enhancement)
