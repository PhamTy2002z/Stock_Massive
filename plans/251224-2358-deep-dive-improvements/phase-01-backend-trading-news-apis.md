# Phase 01: Backend Trading & News APIs

## Context

- **Plan**: [plan.md](./plan.md)
- **Research**: [researcher-01-vnstock-money-flow-apis.md](./research/researcher-01-vnstock-money-flow-apis.md), [researcher-02-vnstock-news-events-apis.md](./research/researcher-02-vnstock-news-events-apis.md)
- **Docs**: [system-architecture.md](../../docs/system-architecture.md), [code-standards.md](../../docs/code-standards.md)

## Overview

| Field | Value |
|-------|-------|
| Priority | P1 |
| Status | Pending |
| Effort | 3h |
| Description | Add 5 new backend endpoints for trading data and news |

## Key Insights

- VCI source required (TCBS deprecated)
- `trading.foreign_trade()`: 8 columns, date range required
- `trading.prop_trade()`: 26 columns, has `resolution` param
- `trading.order_stats()`: 7 columns
- `company.news()`: ~15 items, no pagination
- `company.dividends()`: Full history
- `company.insider_deals()`: Already exists - reuse

## Requirements

**Functional:**
- 5 new endpoints with proper error handling
- Standard rate limiting (100/60s)
- Redis caching with trading-hours-aware TTL

**Non-functional:**
- Response time < 500ms (cached)
- Follow existing service pattern

## Architecture

```
apps/api/src/stocks/
├── trading/                     # NEW module
│   ├── __init__.py
│   ├── router.py               # 3 endpoints
│   ├── service.py              # vnstock integration
│   └── schemas.py              # Pydantic models
├── company/
│   ├── router.py               # +2 endpoints (news, dividends)
│   ├── service.py              # +2 methods
│   └── schemas.py              # +schemas
└── router.py                   # Include trading router
```

## Related Code Files

**Create:**
- `apps/api/src/stocks/trading/__init__.py`
- `apps/api/src/stocks/trading/router.py`
- `apps/api/src/stocks/trading/service.py`
- `apps/api/src/stocks/trading/schemas.py`

**Modify:**
- `apps/api/src/stocks/router.py` - include trading router
- `apps/api/src/stocks/company/router.py` - add news, dividends endpoints
- `apps/api/src/stocks/company/service.py` - add get_news, get_dividends methods
- `apps/api/src/stocks/schemas/company.py` - add NewsResponse, DividendsResponse

## Implementation Steps

### Step 1: Create Trading Module Structure (15min)

```bash
mkdir -p apps/api/src/stocks/trading
touch apps/api/src/stocks/trading/{__init__.py,router.py,service.py,schemas.py}
```

### Step 2: Define Trading Schemas (20min)

```python
# apps/api/src/stocks/trading/schemas.py
from pydantic import BaseModel
from datetime import date
from typing import List

class ForeignTradingItem(BaseModel):
    date: date
    net_volume: int
    net_value: int
    buy_volume: int
    buy_value: int
    sell_volume: int
    sell_value: int
    remaining_room: int
    ownership_pct: float

class ForeignTradingResponse(BaseModel):
    symbol: str
    items: List[ForeignTradingItem]
    total_net_volume: int
    total_net_value: int

class PropTradingItem(BaseModel):
    date: date
    buy_volume: float
    sell_volume: float
    net_volume: float
    net_value: float

class PropTradingResponse(BaseModel):
    symbol: str
    items: List[PropTradingItem]
    total_net_volume: float

class OrderStatsItem(BaseModel):
    date: date
    buy_orders: int
    sell_orders: int
    buy_volume: int
    sell_volume: int
    avg_buy_order: float
    avg_sell_order: float

class OrderStatsResponse(BaseModel):
    symbol: str
    items: List[OrderStatsItem]
```

### Step 3: Implement Trading Service (45min)

```python
# apps/api/src/stocks/trading/service.py
from datetime import date, timedelta
from vnstock import Vnstock
from .schemas import ForeignTradingResponse, PropTradingResponse, OrderStatsResponse

class TradingService:
    def __init__(self, source: str = "VCI"):
        self.source = source

    def get_foreign_trading(self, symbol: str, days: int = 30) -> ForeignTradingResponse:
        end = date.today()
        start = end - timedelta(days=days)
        stock = Vnstock().stock(symbol=symbol, source=self.source)
        df = stock.trading.foreign_trade(
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d')
        )
        # Transform DataFrame to response
        items = [...]
        return ForeignTradingResponse(symbol=symbol, items=items, ...)

    def get_prop_trading(self, symbol: str, days: int = 30) -> PropTradingResponse:
        # Similar pattern
        pass

    def get_order_stats(self, symbol: str, days: int = 30) -> OrderStatsResponse:
        # Similar pattern
        pass

def get_trading_service() -> TradingService:
    return TradingService()
```

### Step 4: Create Trading Router (30min)

```python
# apps/api/src/stocks/trading/router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from src.core.ratelimit import standard_rate_limit
from src.core.cache import TradingHoursCache
from .service import get_trading_service
from .schemas import ForeignTradingResponse, PropTradingResponse, OrderStatsResponse

router = APIRouter()
cache = TradingHoursCache()

@router.get("/{symbol}/foreign-trading", response_model=ForeignTradingResponse,
            dependencies=[Depends(standard_rate_limit)])
async def get_foreign_trading(symbol: str, days: int = Query(30, ge=1, le=365)):
    """Get foreign investor trading data for last N days"""
    cache_key = f"foreign_trading:{symbol}:{days}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    service = get_trading_service()
    result = service.get_foreign_trading(symbol, days)
    await cache.set(cache_key, result, ttl_trading=900, ttl_off=3600)  # 15min/1h
    return result

@router.get("/{symbol}/prop-trading", response_model=PropTradingResponse,
            dependencies=[Depends(standard_rate_limit)])
async def get_prop_trading(symbol: str, days: int = Query(30, ge=1, le=365)):
    """Get proprietary trading data"""
    # Similar pattern
    pass

@router.get("/{symbol}/order-stats", response_model=OrderStatsResponse,
            dependencies=[Depends(standard_rate_limit)])
async def get_order_stats(symbol: str, days: int = Query(30, ge=1, le=365)):
    """Get order flow statistics"""
    # Similar pattern
    pass
```

### Step 5: Add News & Dividends to Company Module (45min)

```python
# apps/api/src/stocks/schemas/company.py - ADD:
class NewsItem(BaseModel):
    id: int
    title: str
    source: Optional[str] = None
    published_at: str
    price: Optional[float] = None
    price_change_pct: Optional[float] = None

class NewsResponse(BaseModel):
    symbol: str
    items: List[NewsItem]

class DividendItem(BaseModel):
    exercise_date: str
    year: int
    dividend_pct: float
    method: str  # 'cash' or 'share'

class DividendsResponse(BaseModel):
    symbol: str
    items: List[DividendItem]
```

```python
# apps/api/src/stocks/company/service.py - ADD methods:
def get_company_news(self, symbol: str) -> NewsResponse:
    stock = Vnstock().stock(symbol=symbol, source=self.source)
    df = stock.company.news()
    items = [NewsItem(...) for _, row in df.iterrows()]
    return NewsResponse(symbol=symbol, items=items)

def get_company_dividends(self, symbol: str) -> DividendsResponse:
    stock = Vnstock().stock(symbol=symbol, source=self.source)
    df = stock.company.dividends()
    items = [DividendItem(...) for _, row in df.iterrows()]
    return DividendsResponse(symbol=symbol, items=items)
```

```python
# apps/api/src/stocks/company/router.py - ADD:
@router.get("/{symbol}/news", response_model=NewsResponse,
            dependencies=[Depends(standard_rate_limit)])
async def get_company_news(symbol: str):
    """Get company news and announcements"""
    # With 5min cache
    pass

@router.get("/{symbol}/dividends", response_model=DividendsResponse,
            dependencies=[Depends(standard_rate_limit)])
async def get_company_dividends(symbol: str):
    """Get dividend history"""
    # With 24h cache
    pass
```

### Step 6: Include Trading Router (5min)

```python
# apps/api/src/stocks/router.py - ADD:
from .trading.router import router as trading_router

stocks_router.include_router(trading_router, tags=["trading"])
```

### Step 7: Test Endpoints (20min)

```bash
# Test foreign trading
curl http://localhost:8000/api/v1/stocks/VCB/foreign-trading?days=30

# Test prop trading
curl http://localhost:8000/api/v1/stocks/VCB/prop-trading?days=30

# Test order stats
curl http://localhost:8000/api/v1/stocks/VCB/order-stats?days=30

# Test news
curl http://localhost:8000/api/v1/stocks/VCB/news

# Test dividends
curl http://localhost:8000/api/v1/stocks/VCB/dividends
```

## Todo List

- [ ] Create trading module directory structure
- [ ] Define Pydantic schemas for trading data
- [ ] Implement TradingService with vnstock integration
- [ ] Create trading router with 3 endpoints
- [ ] Add NewsItem, DividendItem schemas to company
- [ ] Add get_news, get_dividends to CompanyService
- [ ] Add news, dividends endpoints to company router
- [ ] Include trading router in main router
- [ ] Test all 5 endpoints
- [ ] Verify caching works correctly

## Success Criteria

- [ ] `GET /{symbol}/foreign-trading` returns 30-day data
- [ ] `GET /{symbol}/prop-trading` returns 30-day data
- [ ] `GET /{symbol}/order-stats` returns 30-day data
- [ ] `GET /{symbol}/news` returns latest news
- [ ] `GET /{symbol}/dividends` returns dividend history
- [ ] All endpoints have Redis caching
- [ ] Rate limiting applied (100/60s)
- [ ] Proper error handling (404, 502)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| VCI API changes | High | Pin vnstock version, error handling |
| Rate limits hit | Medium | Aggressive caching, retry logic |
| Data format variance | Medium | Defensive parsing, null checks |

## Security Considerations

- Input validation via Pydantic
- Symbol sanitization
- No sensitive data exposure
- Rate limiting prevents abuse

## Next Steps

→ Phase 02: Frontend Money Flow Tab
