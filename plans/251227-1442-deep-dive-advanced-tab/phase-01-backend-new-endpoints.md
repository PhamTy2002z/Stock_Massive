# Phase 1: Backend New Endpoints

## Context
Backend cần 3 endpoints mới cho Advanced tab. Existing: order-stats, foreign-trading, prop-trading.

## Overview
Create price-depth, ratio-summary, trading-stats endpoints using VCI source.

## Requirements
- R1: price-depth endpoint với bid/ask 3 levels
- R2: ratio-summary endpoint với P/E, P/B, ROE, ROA
- R3: trading-stats endpoint với volume, turnover metrics
- R4: Pydantic schemas cho mỗi response
- R5: Redis caching với trading-hours-aware TTL

## Architecture
```
stocks/
├── price/
│   ├── router.py  # ADD: /{symbol}/price-depth
│   ├── service.py # ADD: get_price_depth()
│   └── cache.py   # ADD: cache config
├── company/
│   ├── router.py  # ADD: /{symbol}/ratio-summary, /{symbol}/trading-stats
│   └── service.py # ADD: get_ratio_summary(), get_trading_stats()
└── schemas/
    └── price.py   # ADD: PriceDepthResponse, RatioSummaryResponse, TradingStatsResponse
```

## Related Files
| File | Action | Description |
|------|--------|-------------|
| `apps/api/src/stocks/price/router.py` | EDIT | Add price-depth endpoint |
| `apps/api/src/stocks/price/service.py` | EDIT | Add get_price_depth method |
| `apps/api/src/stocks/company/router.py` | EDIT | Add ratio-summary, trading-stats endpoints |
| `apps/api/src/stocks/company/service.py` | EDIT | Add get_ratio_summary, get_trading_stats |
| `apps/api/src/stocks/schemas/price.py` | EDIT | Add PriceDepthResponse schema |
| `apps/api/src/stocks/schemas/company.py` | EDIT | Add RatioSummaryResponse, TradingStatsResponse |
| `apps/api/tests/test_advanced_endpoints.py` | CREATE | Test new endpoints |

## Implementation Steps

### Step 1.1: Add Pydantic Schemas
```python
# schemas/price.py - ADD
class PriceLevel(BaseModel):
    price: float
    volume: int

class PriceDepthResponse(BaseModel):
    symbol: str
    bid_1: PriceLevel
    bid_2: Optional[PriceLevel] = None
    bid_3: Optional[PriceLevel] = None
    ask_1: PriceLevel
    ask_2: Optional[PriceLevel] = None
    ask_3: Optional[PriceLevel] = None
    total_bid_volume: int
    total_ask_volume: int
    spread: float
    spread_percent: float
    timestamp: datetime
```

```python
# schemas/company.py - ADD
class RatioSummaryResponse(BaseModel):
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None

class TradingStatsResponse(BaseModel):
    total_volume: Optional[int] = None
    avg_volume: Optional[float] = None
    total_value: Optional[float] = None
    avg_value: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
```

### Step 1.2: Add Service Methods
```python
# price/service.py - ADD
def get_price_depth(self, symbol: str) -> PriceDepthResponse:
    quote = Quote(symbol=symbol, source='VCI')
    df = quote.price_depth()
    # Parse DataFrame, calculate spread
    return PriceDepthResponse(...)
```

```python
# company/service.py - ADD
def get_ratio_summary(self, symbol: str) -> RatioSummaryResponse:
    stock = Vnstock().stock(symbol=symbol, source='VCI')
    df = stock.company.ratio_summary()
    return RatioSummaryResponse(...)

def get_trading_stats(self, symbol: str) -> TradingStatsResponse:
    stock = Vnstock().stock(symbol=symbol, source='VCI')
    df = stock.company.trading_stats()
    return TradingStatsResponse(...)
```

### Step 1.3: Add Router Endpoints
```python
# price/router.py - ADD
@router.get("/{symbol}/price-depth", response_model=PriceDepthResponse)
async def get_price_depth(symbol: str):
    return service.get_price_depth(symbol)
```

```python
# company/router.py - ADD
@router.get("/{symbol}/ratio-summary", response_model=RatioSummaryResponse)
async def get_ratio_summary(symbol: str):
    return service.get_ratio_summary(symbol)

@router.get("/{symbol}/trading-stats", response_model=TradingStatsResponse)
async def get_trading_stats(symbol: str):
    return service.get_trading_stats(symbol)
```

### Step 1.4: Add Caching
```python
# Cache TTL config
CACHE_CONFIG = {
    "price-depth": {"trading": 30, "off_hours": 300},    # 30s / 5min
    "ratio-summary": {"trading": 3600, "off_hours": 21600},  # 1h / 6h
    "trading-stats": {"trading": 900, "off_hours": 3600},    # 15min / 1h
}
```

### Step 1.5: Add Tests
```python
# tests/test_advanced_endpoints.py
def test_price_depth():
    response = client.get("/api/v1/stocks/VCB/price-depth")
    assert response.status_code == 200
    assert "bid_1" in response.json()

def test_ratio_summary():
    response = client.get("/api/v1/stocks/VCB/ratio-summary")
    assert response.status_code == 200

def test_trading_stats():
    response = client.get("/api/v1/stocks/VCB/trading-stats")
    assert response.status_code == 200
```

## Todo List
- [x] Add PriceLevel, PriceDepthResponse schemas
- [x] Add RatioSummaryResponse, TradingStatsResponse schemas
- [x] Implement get_price_depth service method
- [x] Implement get_ratio_summary service method
- [x] Implement get_trading_stats service method
- [x] Add price-depth router endpoint
- [x] Add ratio-summary router endpoint
- [x] Add trading-stats router endpoint
- [x] Configure Redis caching
- [x] Write tests for new endpoints
- [x] Test with VCI data source
- [ ] **[CRITICAL]** Fix InsiderDealItem schema mismatch (id, name, position, deal_type, shares, relation fields)
- [ ] **[CRITICAL]** Fix CompanyOverview schema mismatch (short_name, issue_share, outstanding_share fields)

## Success Criteria
- [x] GET /stocks/{symbol}/price-depth returns bid/ask data
- [x] GET /stocks/{symbol}/ratio-summary returns financial ratios
- [x] GET /stocks/{symbol}/trading-stats returns volume metrics
- [x] All endpoints handle missing data gracefully
- [x] Caching works with trading-hours-aware TTL
- [x] Tests pass with real VCI data

## Notes
- price_depth() cần test thực tế để confirm column names
- ratio_summary và trading_stats đã có trong service.py, cần extract ra endpoints riêng

## Completed
**Date:** 2025-12-27

**Achievements:**
- 3 new backend endpoints implemented: price-depth, ratio-summary, trading-stats
- All endpoints return valid VCI data with proper error handling
- Redis caching configured with trading-hours-aware TTL
- Tests passing with real VCI data source

**Outstanding Issues:**
- Schema mismatches in InsiderDealItem and CompanyOverview (tracked in todo list)
