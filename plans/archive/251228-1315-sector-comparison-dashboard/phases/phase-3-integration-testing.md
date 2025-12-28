# Phase 3: Integration & Testing

## Context

- **Parent Plan:** [plan.md](../plan.md)
- **Depends On:** [Phase 1](./phase-1-backend-enhancement.md), [Phase 2](./phase-2-frontend-components.md)
- **Docs:** [Code Standards](../../../../docs/code-standards.md)

## Overview

| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Status | Done (2025-12-28) |
| Effort | 1.5h |
| Description | End-to-end testing, integration verification, documentation |

## Key Insights

- Backend tests: pytest + TestClient
- Frontend tests: planned (Vitest + RTL) but not yet implemented
- Focus on integration tests and manual verification
- Document API changes in OpenAPI

## Requirements

### Functional
1. Backend integration tests for sector-peers endpoint
2. Manual E2E verification flow
3. API documentation update

### Non-Functional
1. Test coverage >80% on new backend code
2. Response time validation (<2s)
3. Cache behavior verification

## Related Code Files

**Create:**
- `apps/api/tests/test_sector_peers.py`

**Modify:**
- `apps/api/src/main.py` - Verify router included

## Implementation Steps

### 1. Backend Integration Tests (45 min)

```python
# apps/api/tests/test_sector_peers.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.main import app

client = TestClient(app)


class TestSectorPeersEndpoint:
    """Test /stocks/{symbol}/sector-peers endpoint."""

    def test_sector_peers_success(self):
        """Test successful sector peers retrieval."""
        response = client.get("/api/v1/stocks/VCB/sector-peers")
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "symbol" in data
        assert "icb_code" in data
        assert "icb_name" in data
        assert "peers" in data
        assert "sector_median" in data
        assert "target_premium" in data

        # Verify median structure
        median = data["sector_median"]
        assert "pe" in median
        assert "pb" in median
        assert "roe" in median
        assert "roa" in median

    def test_sector_peers_with_limit(self):
        """Test limit parameter."""
        response = client.get("/api/v1/stocks/VCB/sector-peers?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["peers"]) <= 5

    def test_sector_peers_invalid_symbol(self):
        """Test with invalid symbol."""
        response = client.get("/api/v1/stocks/INVALID123/sector-peers")
        # Should handle gracefully (empty peers or 404)
        assert response.status_code in [200, 404]

    def test_sector_peers_limit_validation(self):
        """Test limit parameter bounds."""
        # Too low
        response = client.get("/api/v1/stocks/VCB/sector-peers?limit=1")
        assert response.status_code == 422  # Validation error

        # Too high
        response = client.get("/api/v1/stocks/VCB/sector-peers?limit=100")
        assert response.status_code == 422


class TestSectorPeersService:
    """Test sector peers service layer."""

    def test_calculate_sector_median(self):
        """Test median calculation."""
        from src.stocks.financial.service import calculate_sector_median

        peers = [
            {"pe": 10, "pb": 1.5, "roe": 15, "roa": 5, "market_cap": 100},
            {"pe": 20, "pb": 2.5, "roe": 20, "roa": 8, "market_cap": 200},
            {"pe": 15, "pb": 2.0, "roe": 18, "roa": 6, "market_cap": 150},
        ]
        median = calculate_sector_median(peers)

        assert median["pe"] == 15  # Median of [10, 15, 20]
        assert median["pb"] == 2.0
        assert median["roe"] == 18
        assert median["roa"] == 6
        assert median["market_cap"] == 150

    def test_calculate_sector_median_with_nulls(self):
        """Test median with null values."""
        from src.stocks.financial.service import calculate_sector_median

        peers = [
            {"pe": 10, "pb": None, "roe": 15, "roa": 5, "market_cap": 100},
            {"pe": 20, "pb": 2.0, "roe": None, "roa": 8, "market_cap": None},
            {"pe": None, "pb": 3.0, "roe": 18, "roa": 6, "market_cap": 150},
        ]
        median = calculate_sector_median(peers)

        assert median["pe"] == 15  # Median of [10, 20]
        assert median["pb"] == 2.5  # Median of [2.0, 3.0]
        assert median["roe"] == 16.5  # Median of [15, 18]

    def test_calculate_premium(self):
        """Test premium/discount calculation."""
        from src.stocks.financial.service import calculate_premium

        # Premium (above median)
        assert calculate_premium(15, 10) == 50.0

        # Discount (below median)
        assert calculate_premium(8, 10) == -20.0

        # At median
        assert calculate_premium(10, 10) == 0.0

        # Null handling
        assert calculate_premium(None, 10) is None
        assert calculate_premium(10, None) is None
        assert calculate_premium(10, 0) is None


class TestSectorPeersCache:
    """Test caching behavior."""

    @patch("src.stocks.financial.cache.sector_peers_cache")
    def test_cache_hit(self, mock_cache):
        """Test cache hit returns cached data."""
        cached_data = {
            "symbol": "VCB",
            "icb_code": "8355",
            "icb_name": "Ngân hàng",
            "peers": [],
            "sector_median": {"pe": 10, "pb": 1.5, "roe": 15, "roa": 5, "market_cap": 100},
            "target_premium": {"pe": 10.0, "pb": 5.0, "roe": -5.0, "roa": 0.0},
        }
        mock_cache.get.return_value = cached_data

        response = client.get("/api/v1/stocks/VCB/sector-peers")
        assert response.status_code == 200

        # Verify cache was checked
        mock_cache.get.assert_called()

    def test_cache_key_format(self):
        """Test cache key format includes symbol and limit."""
        from src.stocks.financial.cache import sector_peers_cache

        key = "VCB:10"
        expected_full_key = f"sector:peers:{key}"
        # Verify key construction matches expected pattern


class TestSectorPeersPerformance:
    """Test performance requirements."""

    def test_response_time(self):
        """Test response time under 2 seconds."""
        import time

        start = time.time()
        response = client.get("/api/v1/stocks/VCB/sector-peers")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0, f"Response took {elapsed:.2f}s, expected <2s"
```

### 2. Manual E2E Verification Checklist (20 min)

```markdown
## E2E Verification Checklist

### Backend Verification
- [ ] Start API server: `cd apps/api && uvicorn src.main:app --reload`
- [ ] Test endpoint: `curl http://localhost:8000/api/v1/stocks/VCB/sector-peers`
- [ ] Verify response has: symbol, icb_code, icb_name, peers[], sector_median, target_premium
- [ ] Verify peers have: premium_pe, premium_pb, premium_roe, premium_roa
- [ ] Test with different symbols: ACB, TCB, VNM, FPT
- [ ] Test limit parameter: ?limit=5, ?limit=15
- [ ] Check OpenAPI docs: http://localhost:8000/docs

### Frontend Verification
- [ ] Start frontend: `cd apps/web && pnpm dev`
- [ ] Navigate to stock detail page (e.g., /stocks/VCB)
- [ ] Click on "Advanced" tab
- [ ] Click on "Sector" subtab
- [ ] Verify sector overview card shows ICB name and medians
- [ ] Verify peer table shows 10 companies
- [ ] Verify target stock (VCB) is highlighted
- [ ] Test sort by each column (P/E, P/B, ROE, ROA)
- [ ] Verify premium badges show correct colors:
  - Green: values > 5% above median
  - Gray: values within ±5% of median
  - Orange/Red: values > 5% below median
- [ ] Test responsive (resize browser to mobile width)
- [ ] Verify horizontal scroll on mobile
- [ ] Test refresh button works
- [ ] Test with stock that has no peers (rare sector)

### Performance Verification
- [ ] Open Network tab in DevTools
- [ ] Verify API response < 2s on first load
- [ ] Refresh page, verify cache hit (faster response)
- [ ] Check Redis cache has entry (if accessible)
```

### 3. Update OpenAPI Documentation (10 min)

Verify endpoint shows in auto-generated docs:
- Response schema includes `SectorPeersResponse`
- Query parameter `limit` documented with bounds
- Example responses available

### 4. Run Test Suite (15 min)

```bash
# Backend tests
cd apps/api
pytest tests/test_sector_peers.py -v

# Run all tests to ensure no regressions
pytest tests/ -v --tb=short
```

## Todo List

- [ ] Create `apps/api/tests/test_sector_peers.py`
- [ ] Write endpoint success/error tests
- [ ] Write service layer unit tests
- [ ] Write cache behavior tests
- [ ] Write performance tests
- [ ] Run full test suite
- [ ] Complete E2E verification checklist
- [ ] Verify OpenAPI documentation
- [ ] Fix any issues found

## Success Criteria

- [ ] All new tests pass
- [ ] No regressions in existing tests
- [ ] Response time < 2s verified
- [ ] E2E checklist 100% complete
- [ ] OpenAPI docs show new endpoint

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| VCI API unavailable during tests | High | Mock VCI calls in tests |
| Flaky tests due to real API | Medium | Use fixtures/mocks |
| Performance varies | Low | Set reasonable threshold (2s) |

## Security Considerations

- No security changes in this phase
- Tests should not expose sensitive data
- Use test fixtures, not production data

## Next Steps

After completion:
1. Deploy to staging environment
2. User acceptance testing
3. Merge to main branch
4. Monitor cache hit rates in production
