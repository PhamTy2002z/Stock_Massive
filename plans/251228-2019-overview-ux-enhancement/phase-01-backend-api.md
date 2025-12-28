# Phase 1: Backend API - Market Overview Endpoint

## Context Links

- [Main Plan](./plan.md)
- [Brainstorm Report](../reports/brainstorm-251228-2011-overview-ux-enhancement.md)
- [MarketService Pattern](../../../apps/api/src/stocks/market/service.py)
- [Vnstock Docs](https://vnstocks.com/docs/vnstock-data/thong-ke-thi-truong)

## Overview

- **Priority:** P2
- **Status:** Done (2025-12-28)
- **Effort:** 3h
- **Description:** Create aggregate endpoint `/api/v1/stocks/market-overview` returning top gainers/losers, foreign flow, market breadth, and top volume data.

## Key Insights

1. **VCI Source Only** - TCBS deprecated, use `source='VCI'` for all vnstock calls
2. **Sequential Calls with Delay** - 100ms between VCI calls to avoid rate limit
3. **Market Breadth** - Calculate from `Trading.price_board()` by counting advances/declines
4. **Foreign Flow** - Use `Top.foreign_buy()` and `Top.foreign_sell()` with today's date

## Requirements

### Functional
- Return top 5 gainers/losers (VNINDEX)
- Return top 5 foreign net buy/sell
- Return market breadth (advances, declines, unchanged counts)
- Return top 5 by volume and value

### Non-Functional
- Response time < 500ms (cached)
- Cache TTL: 10s trading hours, 5min off-hours
- Rate limit: standard (100/60s)

## Architecture

```python
# Response Schema
class MarketOverviewResponse(BaseModel):
    market_breadth: MarketBreadth  # advances, declines, unchanged
    top_gainers: list[TopMoverItem]  # 5 items
    top_losers: list[TopMoverItem]  # 5 items
    foreign_flow: ForeignFlowData  # net_buy, net_sell, total_net
    top_volume: list[TopVolumeItem]  # 5 items
    generated_at: datetime
```

## Related Code Files

### Files to Create
| Path | Description |
|------|-------------|
| `apps/api/src/stocks/overview/` | New feature module directory |
| `apps/api/src/stocks/overview/__init__.py` | Module init |
| `apps/api/src/stocks/overview/router.py` | API endpoint |
| `apps/api/src/stocks/overview/service.py` | Business logic |
| `apps/api/src/stocks/overview/schemas.py` | Pydantic schemas |

### Files to Modify
| Path | Description |
|------|-------------|
| `apps/api/src/stocks/router.py` | Include overview router |

## Implementation Steps

### Step 1: Create Schema Definitions
```python
# apps/api/src/stocks/overview/schemas.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MarketBreadth(BaseModel):
    advances: int
    declines: int
    unchanged: int
    total: int

class TopMoverItem(BaseModel):
    symbol: str
    price: float
    change_pct: float
    volume: Optional[int] = None

class ForeignFlowItem(BaseModel):
    symbol: str
    net_value: float  # in VND

class ForeignFlowData(BaseModel):
    net_buy: list[ForeignFlowItem]  # top 5
    net_sell: list[ForeignFlowItem]  # top 5
    total_net_value: float  # net across all

class TopVolumeItem(BaseModel):
    symbol: str
    price: float
    volume: int
    value: float

class MarketOverviewResponse(BaseModel):
    market_breadth: MarketBreadth
    top_gainers: list[TopMoverItem]
    top_losers: list[TopMoverItem]
    foreign_flow: ForeignFlowData
    top_volume: list[TopVolumeItem]
    generated_at: datetime
```

### Step 2: Create Service with Sequential VCI Calls
```python
# apps/api/src/stocks/overview/service.py

import asyncio
import logging
from datetime import date, datetime
from typing import Optional
from vnstock import Trading
from vnstock_data import Top

from .schemas import (
    MarketOverviewResponse, MarketBreadth, TopMoverItem,
    ForeignFlowData, ForeignFlowItem, TopVolumeItem
)
from ..shared import StockServiceError

logger = logging.getLogger(__name__)
VCI_DELAY = 0.1  # 100ms delay between calls

class MarketOverviewService:
    def __init__(self, source: str = "VCI"):
        self.source = source

    async def get_market_overview(self) -> MarketOverviewResponse:
        """Aggregate all market overview data with rate limit protection."""
        try:
            # Sequential calls with delay
            top = Top(source=self.source)
            trading = Trading()
            today = date.today().strftime("%Y-%m-%d")

            # 1. Top gainers
            gainers_df = top.gainer(index='VNINDEX', limit=5)
            await asyncio.sleep(VCI_DELAY)

            # 2. Top losers
            losers_df = top.loser(index='VNINDEX', limit=5)
            await asyncio.sleep(VCI_DELAY)

            # 3. Foreign buy
            foreign_buy_df = top.foreign_buy(date=today)
            await asyncio.sleep(VCI_DELAY)

            # 4. Foreign sell
            foreign_sell_df = top.foreign_sell(date=today)
            await asyncio.sleep(VCI_DELAY)

            # 5. Top volume
            volume_df = top.volume(index='VNINDEX', limit=5)
            await asyncio.sleep(VCI_DELAY)

            # 6. Market breadth from price board (batch)
            breadth = await self._calculate_breadth(trading)

            return MarketOverviewResponse(
                market_breadth=breadth,
                top_gainers=self._parse_movers(gainers_df),
                top_losers=self._parse_movers(losers_df),
                foreign_flow=self._parse_foreign(foreign_buy_df, foreign_sell_df),
                top_volume=self._parse_volume(volume_df),
                generated_at=datetime.now()
            )
        except Exception as e:
            logger.error(f"Market overview error: {e}")
            raise StockServiceError(f"Failed to fetch market overview: {e}")

    async def _calculate_breadth(self, trading: Trading) -> MarketBreadth:
        """Calculate market breadth from VN30 price board."""
        try:
            from vnstock import Listing
            listing = Listing()
            # Use VN30 for breadth calculation (smaller dataset, faster)
            symbols = listing.symbols_by_group("VN30").tolist()
            df = trading.price_board(symbols_list=symbols, flatten_columns=True, drop_levels=[0])

            if df is None or df.empty:
                return MarketBreadth(advances=0, declines=0, unchanged=0, total=0)

            advances = len(df[df["match_price"] > df["ref_price"]])
            declines = len(df[df["match_price"] < df["ref_price"]])
            unchanged = len(df[df["match_price"] == df["ref_price"]])

            return MarketBreadth(
                advances=advances,
                declines=declines,
                unchanged=unchanged,
                total=advances + declines + unchanged
            )
        except Exception as e:
            logger.warning(f"Breadth calculation error: {e}")
            return MarketBreadth(advances=0, declines=0, unchanged=0, total=0)

    def _parse_movers(self, df) -> list[TopMoverItem]:
        """Parse top gainers/losers DataFrame."""
        if df is None or df.empty:
            return []
        items = []
        for _, row in df.head(5).iterrows():
            items.append(TopMoverItem(
                symbol=str(row.get("symbol", "")),
                price=float(row.get("last_price", 0)),
                change_pct=float(row.get("price_change_pct_1d", 0)),
                volume=int(row.get("accumulated_value", 0)) if row.get("accumulated_value") else None
            ))
        return items

    def _parse_foreign(self, buy_df, sell_df) -> ForeignFlowData:
        """Parse foreign flow DataFrames."""
        net_buy = []
        net_sell = []
        total_buy = 0
        total_sell = 0

        if buy_df is not None and not buy_df.empty:
            for _, row in buy_df.head(5).iterrows():
                val = float(row.get("net_value", 0))
                net_buy.append(ForeignFlowItem(symbol=str(row.get("symbol", "")), net_value=val))
                total_buy += val

        if sell_df is not None and not sell_df.empty:
            for _, row in sell_df.head(5).iterrows():
                val = float(row.get("net_value", 0))
                net_sell.append(ForeignFlowItem(symbol=str(row.get("symbol", "")), net_value=val))
                total_sell += val

        return ForeignFlowData(
            net_buy=net_buy,
            net_sell=net_sell,
            total_net_value=total_buy + total_sell  # net_sell already negative
        )

    def _parse_volume(self, df) -> list[TopVolumeItem]:
        """Parse top volume DataFrame."""
        if df is None or df.empty:
            return []
        items = []
        for _, row in df.head(5).iterrows():
            items.append(TopVolumeItem(
                symbol=str(row.get("symbol", "")),
                price=float(row.get("last_price", 0)),
                volume=int(row.get("accumulated_value", 0)) if row.get("accumulated_value") else 0,
                value=float(row.get("accumulated_value", 0))
            ))
        return items
```

### Step 3: Create Router with Caching
```python
# apps/api/src/stocks/overview/router.py

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from src.core.cache import TradingHoursCache
from src.core.ratelimit import standard_rate_limit
from .service import MarketOverviewService
from .schemas import MarketOverviewResponse

router = APIRouter(prefix="/market-overview", tags=["overview"])

# Cache: 10s trading, 5min off-hours
overview_cache = TradingHoursCache(
    key_prefix="market_overview:",
    ttl_trading=10,
    ttl_off_hours=300
)

@router.get("", response_model=MarketOverviewResponse)
async def get_market_overview(response: Response, _: None = Depends(standard_rate_limit)):
    """Get aggregated market overview data."""
    cache_key = "aggregate"

    # Try cache first
    cached = overview_cache.get(cache_key)
    if cached:
        return MarketOverviewResponse(**cached)

    # Fetch fresh data
    service = MarketOverviewService()
    data = await service.get_market_overview()

    # Cache result
    overview_cache.set(cache_key, data.model_dump())

    return data
```

### Step 4: Register Router
```python
# In apps/api/src/stocks/router.py
# Add import and include:

from .overview.router import router as overview_router

# In router includes section:
router.include_router(overview_router)
```

### Step 5: Create Module Init
```python
# apps/api/src/stocks/overview/__init__.py
from .router import router
from .service import MarketOverviewService
from .schemas import MarketOverviewResponse

__all__ = ["router", "MarketOverviewService", "MarketOverviewResponse"]
```

## Todo List

- [ ] Create `apps/api/src/stocks/overview/` directory
- [ ] Create `schemas.py` with all response models
- [ ] Create `service.py` with MarketOverviewService
- [ ] Create `router.py` with cached endpoint
- [ ] Create `__init__.py`
- [ ] Register router in main stocks router
- [ ] Test endpoint manually
- [ ] Write unit tests

## Success Criteria

- [ ] Endpoint returns all 4 data sections
- [ ] Response time < 500ms (cached)
- [ ] No VCI rate limit errors
- [ ] Cache works correctly (10s trading, 5min off)
- [ ] Graceful degradation if one data source fails

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| VCI rate limit | API fails | Sequential calls with 100ms delay |
| VCI service down | No data | Return partial data, log error |
| Slow first request | Bad UX | Acceptable (cache primes quickly) |

## Security Considerations

- No auth required (public market data)
- Rate limiting applied via standard_rate_limit
- Input validation via Pydantic

## Next Steps

After this phase:
1. Phase 2: Create frontend components
2. Integrate with useMarketOverview hook
