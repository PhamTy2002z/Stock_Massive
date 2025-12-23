# Phase 03: Testing & Edge Cases

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Dependencies:** [Phase 01](./phase-01-backend-filter.md), [Phase 02](./phase-02-frontend-tabs.md)
- **Docs:** `docs/code-standards.md`

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-23 |
| Priority | P2 |
| Effort | 0.5h |
| Implementation Status | pending |
| Review Status | pending |

## Description

Test backend filter logic and frontend tab behavior. Verify edge cases and caching.

## Test Cases

### Backend Tests (pytest)

```python
# apps/api/tests/test_analytics_api.py

@pytest.mark.asyncio
async def test_volume_spikes_top_profitable_only(client, db_session):
    """Test volume spikes filtered by top 50 profitable companies."""
    # Setup: Create test financial statements with ranks
    # ...

    response = await client.get(
        "/api/v1/stocks/analytics/volume-spikes",
        params={"top_profitable_only": True}
    )

    assert response.status_code == 200
    data = response.json()

    # All returned symbols should be in top 50
    for industry in data["industries"]:
        for stock in industry["stocks"]:
            assert stock["symbol"] in TOP_50_SYMBOLS

@pytest.mark.asyncio
async def test_volume_spikes_top_profitable_empty(client, db_session):
    """Test when no top 50 companies have volume spikes."""
    # Setup: Create financial statements but no matching volume data
    # ...

    response = await client.get(
        "/api/v1/stocks/analytics/volume-spikes",
        params={"top_profitable_only": True}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_spikes"] == 0
    assert data["industries"] == []

@pytest.mark.asyncio
async def test_volume_spikes_cache_key_separation(client):
    """Test that top_profitable_only creates separate cache entry."""
    # Call with top_profitable_only=False
    response1 = await client.get(
        "/api/v1/stocks/analytics/volume-spikes",
        params={"top_profitable_only": False}
    )

    # Call with top_profitable_only=True
    response2 = await client.get(
        "/api/v1/stocks/analytics/volume-spikes",
        params={"top_profitable_only": True}
    )

    # Results should be different (assuming some stocks are not in top 50)
    data1 = response1.json()
    data2 = response2.json()

    # top_profitable should have fewer or equal spikes
    assert data2["total_spikes"] <= data1["total_spikes"]
```

### Frontend Manual Testing

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Default tab | Open `/analytics/volume-spikes` | "Top 50 LN" tab is active |
| Tab switch | Click "Tất cả" tab | Shows all stocks, exchange filter appears |
| Exchange hidden | In "Top 50 LN" tab | Exchange filter not visible |
| Empty state | When no Top 50 spikes | Shows message with link to "Tất cả" |
| Header change | Switch tabs | Header text updates dynamically |
| Data refresh | Switch tabs | New data loads (loading state) |
| Cache hit | Switch back to previous tab | Fast load (cached) |

## Edge Cases

| Case | Handling |
|------|----------|
| Empty FinancialStatement table | Return empty response, no error |
| Top 50 symbols with no OHLCV data | Skip silently (existing behavior) |
| All Top 50 stocks have no spikes | Show empty state with link |
| Backend unavailable | Show error state (existing behavior) |

## Todo List

- [ ] Add pytest test for `top_profitable_only=true`
- [ ] Add pytest test for empty case
- [ ] Add pytest test for cache separation
- [ ] Manual test all frontend scenarios
- [ ] Verify no regression in "Tất cả" mode

## Success Criteria

1. All pytest tests pass
2. Manual testing confirms all scenarios work
3. No console errors in browser
4. Cache works correctly (verify via metadata.cache_hit)

## Next Steps

After all phases complete:
- Consider adding [Top 50] badge in "Tất cả" mode (future enhancement)
- Consider URL state for tab (shareability)
