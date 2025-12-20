# Phase 03: Testing

## Context

- [Plan Overview](plan.md)
- [Phase 01: TradingHoursCache](phase-01-trading-hours-cache.md)
- [Phase 02: On-Demand Collector](phase-02-on-demand-collector.md)

## Overview

Test the TradingHoursCache utility and on-demand collection endpoint to ensure correct behavior across trading hours, cache states, and error conditions.

## Requirements

1. Unit tests for TradingHoursCache
2. Integration test for endpoint on-demand behavior
3. Test trading hours detection logic
4. Test cache expiration behavior

## Related Code Files

| File | Purpose | Action |
|------|---------|--------|
| `tests/stocks/price/test_cache.py` | **NEW** - Cache unit tests |
| `tests/stocks/price/test_router.py` | Endpoint tests | **MODIFY** or create |

## Implementation Steps

### Step 1: Create test_cache.py

Create `tests/stocks/price/test_cache.py`:

```python
"""Tests for TradingHoursCache."""
import pytest
from datetime import datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.stocks.price.cache import TradingHoursCache, VN_TZ


class TestTradingHoursCache:
    """Test TradingHoursCache functionality."""

    def test_set_and_get(self):
        """Test basic set/get operations."""
        cache = TradingHoursCache(maxsize=10)
        cache.set("VCB:20", {"symbol": "VCB"})
        result = cache.get("VCB:20")
        assert result == {"symbol": "VCB"}

    def test_get_missing_key(self):
        """Test get returns None for missing key."""
        cache = TradingHoursCache(maxsize=10)
        assert cache.get("MISSING") is None

    def test_is_stale_missing_key(self):
        """Test is_stale returns True for missing key."""
        cache = TradingHoursCache(maxsize=10)
        assert cache.is_stale("MISSING") is True

    def test_maxsize_eviction(self):
        """Test oldest entry evicted when at capacity."""
        cache = TradingHoursCache(maxsize=2)
        cache.set("A", 1)
        cache.set("B", 2)
        cache.set("C", 3)  # Should evict A
        assert cache.get("A") is None
        assert cache.get("B") == 2
        assert cache.get("C") == 3

    def test_clear(self):
        """Test clear removes all entries."""
        cache = TradingHoursCache(maxsize=10)
        cache.set("A", 1)
        cache.set("B", 2)
        cache.clear()
        assert cache.get("A") is None
        assert cache.get("B") is None

    @patch("src.stocks.price.cache.datetime")
    def test_trading_hours_weekday_morning(self, mock_datetime):
        """Test is_trading_hours during market open."""
        # Monday 10:00 VN time
        mock_datetime.now.return_value = datetime(
            2025, 12, 22, 10, 0, tzinfo=VN_TZ
        )
        cache = TradingHoursCache()
        assert cache._is_trading_hours() is True
        assert cache._get_ttl() == 60

    @patch("src.stocks.price.cache.datetime")
    def test_trading_hours_weekend(self, mock_datetime):
        """Test is_trading_hours returns False on weekend."""
        # Saturday 10:00 VN time
        mock_datetime.now.return_value = datetime(
            2025, 12, 20, 10, 0, tzinfo=VN_TZ
        )
        cache = TradingHoursCache()
        assert cache._is_trading_hours() is False
        assert cache._get_ttl() == 3600

    @patch("src.stocks.price.cache.datetime")
    def test_trading_hours_after_close(self, mock_datetime):
        """Test is_trading_hours returns False after market close."""
        # Monday 16:00 VN time
        mock_datetime.now.return_value = datetime(
            2025, 12, 22, 16, 0, tzinfo=VN_TZ
        )
        cache = TradingHoursCache()
        assert cache._is_trading_hours() is False
        assert cache._get_ttl() == 3600


class TestCacheExpiration:
    """Test cache expiration behavior."""

    @patch("src.stocks.price.cache.datetime")
    def test_expired_during_trading(self, mock_datetime):
        """Test entry expires after 60s during trading hours."""
        cache = TradingHoursCache(maxsize=10)

        # Set at 10:00
        mock_datetime.now.return_value = datetime(
            2025, 12, 22, 10, 0, 0, tzinfo=VN_TZ
        )
        cache.set("VCB:20", {"data": "test"})

        # Get at 10:01:30 (90s later) - should be expired
        mock_datetime.now.return_value = datetime(
            2025, 12, 22, 10, 1, 30, tzinfo=VN_TZ
        )
        assert cache.get("VCB:20") is None

    @patch("src.stocks.price.cache.datetime")
    def test_not_expired_during_trading(self, mock_datetime):
        """Test entry valid within 60s during trading hours."""
        cache = TradingHoursCache(maxsize=10)

        # Set at 10:00
        mock_datetime.now.return_value = datetime(
            2025, 12, 22, 10, 0, 0, tzinfo=VN_TZ
        )
        cache.set("VCB:20", {"data": "test"})

        # Get at 10:00:30 (30s later) - should be valid
        mock_datetime.now.return_value = datetime(
            2025, 12, 22, 10, 0, 30, tzinfo=VN_TZ
        )
        assert cache.get("VCB:20") == {"data": "test"}
```

### Step 2: Add endpoint integration test

Add to existing test file or create `tests/stocks/price/test_volume_anomalies.py`:

```python
"""Integration tests for volume anomalies endpoint."""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from src.main import app


@pytest.mark.asyncio
async def test_volume_anomalies_cache_hit():
    """Test endpoint returns cached response on second call."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First call - may collect data
        response1 = await client.get("/stocks/VCB/volume-anomalies?days=20")
        assert response1.status_code == 200

        # Second call - should hit cache (faster)
        response2 = await client.get("/stocks/VCB/volume-anomalies?days=20")
        assert response2.status_code == 200
        assert response2.json()["symbol"] == "VCB"


@pytest.mark.asyncio
async def test_volume_anomalies_invalid_symbol():
    """Test endpoint handles invalid symbol gracefully."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/stocks/INVALID123/volume-anomalies")
        # Should return 200 with empty time_slots or 4xx error
        assert response.status_code in [200, 400, 404]
```

## Todo List

- [ ] Create `tests/stocks/price/` directory if not exists
- [ ] Create `tests/stocks/price/test_cache.py`
- [ ] Create or update `tests/stocks/price/test_volume_anomalies.py`
- [ ] Run tests: `pytest tests/stocks/price/ -v`
- [ ] Verify all tests pass

## Success Criteria

1. All unit tests pass for TradingHoursCache
2. Trading hours detection works for weekdays/weekends
3. Cache expiration respects dynamic TTL
4. Endpoint integration tests pass
5. No regressions in existing tests

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Datetime mocking issues | Medium | Low | Use patch at module level |
| Flaky integration tests | Medium | Low | Mock external API calls |
| Missing test directory | Low | Low | Create with __init__.py |

## Manual Testing Checklist

```bash
# 1. Test with fresh symbol (no prior data)
curl "http://localhost:8000/stocks/FPT/volume-anomalies?days=20"

# 2. Test cache hit (run immediately after #1)
curl "http://localhost:8000/stocks/FPT/volume-anomalies?days=20"

# 3. Test different days param (different cache key)
curl "http://localhost:8000/stocks/FPT/volume-anomalies?days=10"

# 4. Test invalid symbol
curl "http://localhost:8000/stocks/INVALID/volume-anomalies"
```

## Notes

- Integration tests may need DB fixtures or mocked collector
- Consider adding pytest-asyncio to dev dependencies if not present
- Mock vnstock API calls in CI to avoid rate limiting
