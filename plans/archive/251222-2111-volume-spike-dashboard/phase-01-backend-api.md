# Phase 1: Backend API - Volume Spike Detection

## Context
- **Plan:** [Main Plan](./plan.md)
- **Research:** [vnstock API Report](./research/researcher-vnstock-api-report.md)
- **Existing Patterns:** `/apps/api/src/stocks/analytics/router.py` (top performers)
- **Cache:** `/apps/api/src/core/cache.py` (TradingHoursCache)

## Overview
Build backend API to detect volume spikes across all HOSE/HNX symbols, calculate spike ratios against 20-day average, and group by ICB Level 2 industry. No built-in vnstock API exists - must implement custom calculation.

## Requirements

### Functional
- **Endpoint:** `GET /api/v1/stocks/analytics/volume-spikes`
- **Query Params:**
  - `date` (optional): Target date (default: latest session)
  - `min_ratio` (optional): Minimum spike threshold (default: 1.5)
  - `exchange` (optional): Filter HOSE/HNX (default: both)
  - `include_upcom` (optional): Include UPCOM (default: false)
  - `limit` (optional): Max results per industry (default: 50)
- **Response:** Grouped by ICB Level 2, sorted by spike ratio desc
- **Cache:** 5min trading hours, 1hr off-hours

### Non-Functional
- Response time: <3s for 1,700 symbols
- Rate limit: Heavy tier (20/60s)
- Error handling: Graceful degradation if ICB data missing
- Logging: Track calculation time, cache hits

## Architecture

### Data Flow
```
Request → Cache Check → [MISS] → Fetch Symbols (ICB) →
Batch Price Board → Calculate 20d Avg → Compute Spike Ratio →
Filter & Rank → Group by Industry → Cache → Response
```

### Components

#### 1. New Endpoint (`/apps/api/src/stocks/analytics/router.py`)
```python
@router.get("/volume-spikes", response_model=VolumeSpikeResponse)
async def get_volume_spikes(
    date: Optional[str] = None,
    min_ratio: float = Query(1.5, ge=1.0, le=5.0),
    exchange: Optional[str] = Query(None, regex="^(HOSE|HNX)$"),
    include_upcom: bool = False,
    limit: int = Query(50, ge=10, le=200),
    db: AsyncSession = Depends(get_db),
) -> VolumeSpikeResponse:
    """Detect volume spikes grouped by ICB industry."""
```

#### 2. Service Layer (`/apps/api/src/stocks/analytics/service.py`)
```python
class AnalyticsService:
    async def get_volume_spikes(
        self,
        date: Optional[str],
        min_ratio: float,
        exchange: Optional[str],
        include_upcom: bool,
        limit: int,
    ) -> VolumeSpikeResponse:
        # 1. Fetch symbols with ICB mapping
        # 2. Batch fetch current volume (price_board)
        # 3. Fetch 20-day historical volume per symbol
        # 4. Calculate spike ratios
        # 5. Filter by min_ratio
        # 6. Group by ICB Level 2
        # 7. Sort and limit per group
```

#### 3. Schemas (`/apps/api/src/stocks/schemas/analytics.py`)
```python
class VolumeSpikeItem(BaseModel):
    symbol: str
    company_name: Optional[str]
    exchange: str
    current_volume: int
    avg_volume_20d: int
    spike_ratio: float
    price_change_pct: Optional[float]
    icb_code: str
    icb_name: str

class IndustryVolumeSpikeGroup(BaseModel):
    icb_code: str
    icb_name: str
    spike_count: int
    avg_spike_ratio: float
    stocks: List[VolumeSpikeItem]

class VolumeSpikeResponse(BaseModel):
    date: str
    total_spikes: int
    industries: List[IndustryVolumeSpikeGroup]
    metadata: dict  # calculation_time, cache_hit, etc.
```

#### 4. Cache Integration
```python
volume_spike_cache = TradingHoursCache(
    key_prefix="stock:volume_spikes:",
    ttl_trading=300,      # 5 min
    ttl_off_hours=3600,   # 1 hour
)
```

## Related Code Files
- `/apps/api/src/stocks/analytics/router.py` - Add new endpoint
- `/apps/api/src/stocks/analytics/service.py` - Add volume spike logic
- `/apps/api/src/stocks/schemas/analytics.py` - Add new schemas
- `/apps/api/src/stocks/service.py` - Reuse `get_price_board()`, `get_history()`
- `/apps/api/src/core/cache.py` - TradingHoursCache (existing)

## Implementation Steps

### Step 1: Define Schemas (30 min)
- [ ] Add `VolumeSpikeItem` to `schemas/analytics.py`
- [ ] Add `IndustryVolumeSpikeGroup` schema
- [ ] Add `VolumeSpikeResponse` schema
- [ ] Add validation rules (min_ratio 1.0-5.0)

### Step 2: Implement Service Logic (3-4 hours)
- [ ] Add `get_volume_spikes()` to `AnalyticsService`
- [ ] Fetch symbols with ICB via `listing.symbols_by_industries()`
- [ ] Batch fetch current volume (max 50 symbols per call)
- [ ] Fetch 20-day history per symbol (use existing `get_history()`)
- [ ] Calculate average volume and spike ratio
- [ ] Filter by `min_ratio` threshold
- [ ] Group by ICB Level 2 (extract first 4 digits of ICB code)
- [ ] Sort by spike ratio desc, limit per group
- [ ] Handle missing ICB data (fallback to "Uncategorized")

### Step 3: Add Router Endpoint (1 hour)
- [ ] Add `GET /volume-spikes` to `analytics/router.py`
- [ ] Add query parameter validation
- [ ] Integrate cache (check → miss → compute → set)
- [ ] Add rate limiting (heavy tier)
- [ ] Add error handling (StockServiceError)
- [ ] Add logging (calculation time, symbols processed)

### Step 4: Optimize Performance (2 hours)
- [ ] Implement async batch processing for price_board
- [ ] Add exponential backoff for rate limits
- [ ] Cache ICB mapping separately (24hr TTL)
- [ ] Optimize 20-day avg calculation (use DB if available)
- [ ] Add timeout protection (max 5s per batch)

### Step 5: Testing (2 hours)
- [ ] Unit tests for spike calculation logic
- [ ] Integration test for full endpoint
- [ ] Test cache hit/miss scenarios
- [ ] Test edge cases (no spikes, missing ICB, rate limit)
- [ ] Load test with 1,700 symbols

## Todo List
- [ ] Create Pydantic schemas for volume spike data
- [ ] Implement volume spike calculation in AnalyticsService
- [ ] Add ICB grouping logic (Level 2 extraction)
- [ ] Create new endpoint in analytics router
- [ ] Integrate TradingHoursCache with 5min/1hr TTL
- [ ] Add batch processing for price_board API
- [ ] Implement rate limit handling with backoff
- [ ] Add comprehensive error handling
- [ ] Write unit tests for calculation logic
- [ ] Write integration tests for endpoint
- [ ] Test with production-like data (1,700 symbols)
- [ ] Document API in OpenAPI/Swagger

## Success Criteria
- [ ] Endpoint returns <3s for 1,700 symbols
- [ ] Cache reduces API calls by 80%+ during trading
- [ ] Correctly groups by ICB Level 2 (10-15 industries)
- [ ] Handles rate limits gracefully (no 429 errors)
- [ ] Returns accurate spike ratios (validated against manual calc)
- [ ] Swagger docs auto-generated and accurate

## Risk Assessment

### High Risk
- **VCI Rate Limits:** Batch processing may hit 100/60s limit
  - *Mitigation:* Exponential backoff, cache aggressively, consider pre-computation job
- **Slow Historical Data Fetch:** 1,700 symbols × 20 days = 34,000 data points
  - *Mitigation:* Use DB cache for historical data, parallel async requests

### Medium Risk
- **ICB Data Inconsistency:** Some symbols may lack ICB codes
  - *Mitigation:* Fallback to "Uncategorized" group, log missing mappings
- **Large Response Payload:** 200+ spikes × 10 industries = 2,000+ items
  - *Mitigation:* Limit per industry, add pagination support

### Low Risk
- **Date Parsing Errors:** Invalid date formats
  - *Mitigation:* Pydantic validation, default to latest session

## Unresolved Questions
1. Should we pre-compute volume spikes via scheduled job (like top performers)?
2. What's the actual VCI rate limit for `price_board()` batch calls?
3. Should we store historical volume averages in DB to reduce API calls?
4. How to handle symbols with <20 days of trading history?
5. Should we include volume spike trend (increasing/decreasing over time)?
