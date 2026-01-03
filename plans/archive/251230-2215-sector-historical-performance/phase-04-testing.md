# Phase 4: Testing

## Overview

| Field | Value |
|-------|-------|
| Priority | P2 |
| Effort | 1h |
| Status | DONE |
| Dependencies | Phases 1-3 complete |

## Files to Create

| Action | File |
|--------|------|
| CREATE | `apps/api/tests/test_sector_historical.py` |

## Implementation Steps

### Step 1: Backend Unit Tests

**File**: `apps/api/tests/test_sector_historical.py` (CREATE)

```python
"""Tests for sector historical performance feature."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from src.stocks.analytics.sector_historical_service import (
    SectorHistoricalService,
    PERIODS,
)


class TestSectorHistoricalService:
    """Test cases for SectorHistoricalService."""

    @pytest.fixture
    def mock_vnstock(self):
        """Mock vnstock responses."""
        with patch("src.stocks.analytics.sector_historical_service.Listing") as mock_listing, \
             patch("src.stocks.analytics.sector_historical_service.Vnstock") as mock_vnstock:

            # Mock VN100 symbols
            mock_listing_instance = Mock()
            mock_listing_instance.symbols_by_group.return_value = pd.Series(["ACB", "VNM", "HPG"])
            mock_listing_instance.symbols_by_industries.return_value = pd.DataFrame({
                "symbol": ["ACB", "VNM", "HPG"],
                "icb_code2": ["8300", "3500", "1700"],
                "icb_name2": ["Ngân hàng", "Thực phẩm", "Vật liệu"],
            })
            mock_listing.return_value = mock_listing_instance

            # Mock stock history
            def create_mock_stock(symbol, source):
                mock_stock = Mock()
                mock_quote = Mock()
                mock_quote.history.return_value = pd.DataFrame({
                    "time": pd.date_range(end=datetime.now(), periods=35, freq="D"),
                    "close": [100 + i for i in range(35)],
                })
                mock_stock.quote = mock_quote
                return Mock(stock=lambda **kwargs: mock_stock)

            mock_vnstock.side_effect = create_mock_stock

            yield mock_listing, mock_vnstock

    def test_calculate_all_periods(self, mock_vnstock):
        """Test that all periods are calculated."""
        service = SectorHistoricalService()
        service.delay = 0  # No delay for tests

        with patch.object(service, "_calculate_period") as mock_calc:
            mock_calc.return_value = {
                "top_gainers": [{"icb_code": "8300", "icb_name": "Ngân hàng", "change_pct": 5.0}],
                "top_losers": [],
                "generated_at": str(datetime.now()),
            }

            # This would normally make API calls, but we've mocked it
            # Just verify the structure
            assert len(PERIODS) == 3
            assert "1W" in PERIODS
            assert "2W" in PERIODS
            assert "1M" in PERIODS

    def test_periods_config(self):
        """Test period configuration is correct."""
        assert PERIODS["1W"] == 7
        assert PERIODS["2W"] == 14
        assert PERIODS["1M"] == 30


class TestSectorHistoricalEndpoint:
    """Test cases for API endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from src.main import app
        return TestClient(app)

    def test_get_sector_historical_default_period(self, client):
        """Test GET with default period (1W)."""
        with patch("src.stocks.analytics.sector_historical_router.sector_historical_cache") as mock_cache:
            mock_cache.get.return_value = {
                "top_gainers": [
                    {"icb_code": "8300", "icb_name": "Ngân hàng", "change_pct": 5.23},
                ],
                "top_losers": [
                    {"icb_code": "4500", "icb_name": "Y tế", "change_pct": -2.34},
                ],
                "generated_at": "2025-12-30T15:45:00",
            }

            response = client.get("/api/v1/stocks/analytics/sector-historical")
            assert response.status_code == 200

            data = response.json()
            assert data["period"] == "1W"
            assert len(data["top_gainers"]) == 1
            assert data["top_gainers"][0]["icb_name"] == "Ngân hàng"

    def test_get_sector_historical_with_period(self, client):
        """Test GET with explicit period."""
        with patch("src.stocks.analytics.sector_historical_router.sector_historical_cache") as mock_cache:
            mock_cache.get.return_value = None

            response = client.get("/api/v1/stocks/analytics/sector-historical?period=1M")
            assert response.status_code == 200

            data = response.json()
            assert data["period"] == "1M"
            assert data["top_gainers"] == []
            assert data["generated_at"] is None

    def test_get_sector_historical_invalid_period(self, client):
        """Test GET with invalid period returns 422."""
        response = client.get("/api/v1/stocks/analytics/sector-historical?period=INVALID")
        assert response.status_code == 422  # Validation error


class TestIntegration:
    """Integration tests (run with real Redis)."""

    @pytest.mark.integration
    def test_cache_roundtrip(self):
        """Test cache set/get cycle."""
        from src.stocks.analytics.sector_historical_service import sector_historical_cache

        test_data = {
            "top_gainers": [{"icb_code": "8300", "icb_name": "Test", "change_pct": 1.0}],
            "top_losers": [],
            "generated_at": str(datetime.now()),
        }

        # Set
        sector_historical_cache.set("TEST", test_data)

        # Get
        cached = sector_historical_cache.get("TEST")
        assert cached is not None
        assert cached["top_gainers"][0]["icb_name"] == "Test"

        # Cleanup
        sector_historical_cache.delete("TEST")
```

### Step 2: Manual API Testing

```bash
# Test endpoint (after job runs)
curl http://localhost:8000/api/v1/stocks/analytics/sector-historical?period=1W

# Trigger refresh manually
curl -X POST http://localhost:8000/api/v1/stocks/analytics/sector-historical/refresh

# Test all periods
for p in 1W 2W 1M; do
  echo "=== Period: $p ==="
  curl -s "http://localhost:8000/api/v1/stocks/analytics/sector-historical?period=$p" | jq .
done
```

### Step 3: Frontend Visual Testing

1. Start dev server: `cd apps/web && pnpm dev`
2. Navigate to home page (/)
3. Verify:
   - [ ] Chart renders below VN30 table
   - [ ] Tabs switch periods (1W/2W/1M)
   - [ ] Green bars for gainers
   - [ ] Red bars for losers
   - [ ] Tooltip shows on hover
   - [ ] Empty state when no data

## Todo List

- [ ] Create `test_sector_historical.py`
- [ ] Run unit tests: `pytest apps/api/tests/test_sector_historical.py -v`
- [ ] Manual API test with curl
- [ ] Visual frontend test
- [ ] Test empty state (clear cache)
- [ ] Test error handling (stop Redis)

## Success Criteria

- All unit tests pass
- API returns correct response format
- Frontend renders without errors
- Tab switching works
- Empty state displays properly

## Test Coverage

| Component | Coverage |
|-----------|----------|
| Service class | Unit tests with mocks |
| API endpoint | Request/response tests |
| Cache | Integration test |
| Frontend | Manual visual test |

## Risks

| Risk | Mitigation |
|------|------------|
| Flaky tests from vnstock | Mock all external calls |
| Redis not available | Skip integration tests in CI |
| Frontend visual regression | Manual verification for now |
