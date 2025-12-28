# Phase 1: Backend Enhancement

## Context

- **Parent Plan:** [plan.md](../plan.md)
- **Research:** [Rate Limit Strategy](../research/researcher-02-rate-limit-caching.md)
- **Docs:** [Code Standards](../../../../docs/code-standards.md)

## Overview

| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Status | Done (2025-12-28) |
| Effort | 2h |
| Description | Enhance sector_peers endpoint với sector median, premium/discount metrics |

## Key Insights

From research:
- VCI rate limit: 60 req/min, 3000 req/hr
- Existing `TradingHoursCache` supports dynamic TTL
- `safe_vnstock_call` has retry + adaptive delay
- Current endpoint returns 5 peers, need 10

## Requirements

### Functional
1. Return sector median values (P/E, P/B, ROE, ROA, Market Cap)
2. Calculate premium/discount % for target stock vs median
3. Return 10 peers instead of 5
4. Add market_cap to PeerMetrics

### Non-Functional
1. Response time < 2s (with cache)
2. Cache TTL: 4h trading, 24h off-hours
3. Handle VCI rate limit gracefully

## Architecture

```
Request → Cache Check → [Hit: Return] / [Miss: Fetch VCI]
                                           ↓
                                    Calculate Median
                                           ↓
                                    Add Premium/Discount
                                           ↓
                                    Cache Response
                                           ↓
                                    Return
```

## Related Code Files

**Modify:**
- `apps/api/src/stocks/financial/service.py` - get_sector_peers()
- `apps/api/src/stocks/schemas/financial.py` - SectorPeersResponse, PeerMetrics

**Create:**
- `apps/api/src/stocks/financial/cache.py` - sector-specific cache instances

## Implementation Steps

### 1. Update Schemas (10 min)

```python
# apps/api/src/stocks/schemas/financial.py

class SectorMedian(BaseModel):
    """Sector median values."""
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    market_cap: Optional[float] = None

class PeerMetrics(BaseModel):
    """Financial metrics for a peer company."""
    symbol: str
    company_name: Optional[str] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    market_cap: Optional[float] = None
    # NEW: Premium/discount vs sector median
    premium_pe: Optional[float] = None      # % deviation
    premium_pb: Optional[float] = None
    premium_roe: Optional[float] = None
    premium_roa: Optional[float] = None

class SectorPeersResponse(BaseModel):
    """Sector peers comparison response."""
    symbol: str
    icb_code: str
    icb_name: str
    peers: list[PeerMetrics]
    # NEW
    sector_median: SectorMedian
    target_premium: dict[str, Optional[float]]  # Target stock premium/discount
```

### 2. Create Sector Cache (15 min)

```python
# apps/api/src/stocks/financial/cache.py

from src.core.cache import TradingHoursCache

sector_peers_cache = TradingHoursCache(
    key_prefix="sector:peers:",
    ttl_trading=4 * 3600,    # 4 hours
    ttl_off_hours=24 * 3600  # 24 hours
)
```

### 3. Enhance get_sector_peers() (45 min)

```python
# apps/api/src/stocks/financial/service.py

import statistics
from .cache import sector_peers_cache

def calculate_sector_median(peers: list[dict]) -> dict:
    """Calculate median values for sector metrics."""
    metrics = ['pe', 'pb', 'roe', 'roa', 'market_cap']
    medians = {}
    for metric in metrics:
        values = [p.get(metric) for p in peers if p.get(metric) is not None]
        medians[metric] = statistics.median(values) if values else None
    return medians

def calculate_premium(value: float, median: float) -> Optional[float]:
    """Calculate premium/discount as percentage."""
    if value is None or median is None or median == 0:
        return None
    return ((value - median) / median) * 100

async def get_sector_peers(symbol: str, limit: int = 10) -> SectorPeersResponse:
    """Get sector peers with median and premium/discount."""
    cache_key = f"{symbol}:{limit}"

    # Check cache
    cached = sector_peers_cache.get(cache_key)
    if cached:
        return SectorPeersResponse(**cached)

    # Fetch from VCI...
    # (existing logic, increase limit to 10)

    # Calculate median
    median = calculate_sector_median(peers_data)

    # Add premium/discount to each peer
    for peer in peers_data:
        peer['premium_pe'] = calculate_premium(peer.get('pe'), median['pe'])
        peer['premium_pb'] = calculate_premium(peer.get('pb'), median['pb'])
        peer['premium_roe'] = calculate_premium(peer.get('roe'), median['roe'])
        peer['premium_roa'] = calculate_premium(peer.get('roa'), median['roa'])

    # Find target stock and its premium
    target = next((p for p in peers_data if p['symbol'] == symbol), None)
    target_premium = {
        'pe': target.get('premium_pe') if target else None,
        'pb': target.get('premium_pb') if target else None,
        'roe': target.get('premium_roe') if target else None,
        'roa': target.get('premium_roa') if target else None,
    }

    response = SectorPeersResponse(
        symbol=symbol,
        icb_code=icb_code,
        icb_name=icb_name,
        peers=[PeerMetrics(**p) for p in peers_data],
        sector_median=SectorMedian(**median),
        target_premium=target_premium
    )

    # Cache response
    sector_peers_cache.set(cache_key, response.model_dump())

    return response
```

### 4. Update Router (10 min)

```python
# apps/api/src/stocks/financial/router.py

@router.get("/{symbol}/sector-peers", response_model=SectorPeersResponse)
async def get_stock_sector_peers(
    symbol: str,
    limit: int = Query(10, ge=5, le=20, description="Number of peers")
):
    """Get sector peers comparison with median and premium/discount."""
    service = get_financial_service()
    return await service.get_sector_peers(symbol.upper(), limit)
```

### 5. Add Unit Tests (20 min)

```python
# apps/api/tests/test_sector_peers.py

def test_sector_peers_returns_median():
    response = client.get("/api/v1/stocks/VCB/sector-peers")
    assert response.status_code == 200
    data = response.json()
    assert "sector_median" in data
    assert "target_premium" in data

def test_premium_calculation():
    from src.stocks.financial.service import calculate_premium
    assert calculate_premium(15, 10) == 50.0  # 50% premium
    assert calculate_premium(8, 10) == -20.0  # 20% discount

def test_cache_hit():
    # First call
    client.get("/api/v1/stocks/VCB/sector-peers")
    # Second call should hit cache
    # (mock cache to verify)
```

## Todo List

- [ ] Update `SectorPeersResponse` schema with median + premium
- [ ] Add `SectorMedian` schema
- [ ] Create `apps/api/src/stocks/financial/cache.py`
- [ ] Implement `calculate_sector_median()` helper
- [ ] Implement `calculate_premium()` helper
- [ ] Enhance `get_sector_peers()` with caching
- [ ] Update router with limit parameter
- [ ] Write unit tests for premium calculation
- [ ] Write integration tests for endpoint

## Success Criteria

- [ ] `/stocks/{symbol}/sector-peers` returns `sector_median` object
- [ ] Each peer has `premium_*` fields
- [ ] Response cached for 4h during trading
- [ ] Tests pass with >80% coverage on new code

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| VCI rate limit | Medium | 4h cache TTL, adaptive delay |
| No peers in sector | Low | Return empty list with message |
| Median calculation edge cases | Low | Handle None values, min 3 peers for median |

## Security Considerations

- Input validation: Symbol uppercase, limit 5-20
- No user data exposed
- Rate limiting already in place

## Next Steps

After completion → [Phase 2: Frontend Components](./phase-2-frontend-components.md)
