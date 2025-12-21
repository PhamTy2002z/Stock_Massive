---
phase: 01
title: Backend API Implementation
status: done
priority: P2
estimated_hours: 3
actual_hours: 2
completed_at: 2025-12-21
dependencies: []
---

# Phase 01: Backend API Implementation

**Date**: 2025-12-21
**Description**: Create FastAPI endpoint for VN30 overview data
**Priority**: P2
**Status**: Done (Completed 2025-12-21)

## Context

- **Research**: [vnstock API Report](./research/researcher-vnstock-api-report.md)
- **Existing Pattern**: Market router with sector performance endpoint
- **API Method**: `listing.symbols_by_group('VN30')` + `trading.price_board()`
- **Caching**: TradingHoursCache (5min trading, 1hr off-hours)

## Requirements

### Functional
1. Endpoint returns VN30 stocks with real-time price data
2. Response includes: symbol, company_name, price, change_pct
3. Data sorted by market cap or symbol
4. Response time <3 seconds for all 30 stocks
5. Cache responses to reduce API load

### Non-Functional
1. Rate limiting via standard_rate_limit dependency
2. Error handling with proper HTTP status codes
3. Logging for debugging and monitoring
4. Type safety with Pydantic schemas

## Related Code Files

### Files to Modify
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/service.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas/market.py`

### Reference Files
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas/company.py` (StockSymbol schema)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/service.py` (price_board usage)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/shared/converters.py` (safe_float helper)

## Implementation Steps

### Step 1: Create Pydantic Schemas
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas/market.py`

Add new schemas after existing FundCertificatesResponse:

```python
class VN30OverviewItem(BaseModel):
    """VN30 stock overview item."""

    symbol: str = Field(..., description="Stock symbol")
    company_name: str = Field(..., description="Company name")
    price: Optional[float] = Field(None, description="Current price (VND)")
    change_pct: Optional[float] = Field(None, description="Daily change percentage")
    volume: Optional[float] = Field(None, description="Trading volume")
    market_cap: Optional[float] = Field(None, description="Market cap (billion VND)")


class VN30OverviewResponse(BaseModel):
    """Response for VN30 overview endpoint."""

    stocks: list[VN30OverviewItem]
    generated_at: datetime
    total_count: int
```

**Validation**:
- All fields properly typed with Optional where nullable
- Field descriptions clear and concise
- Follows existing schema patterns

### Step 2: Implement Service Method
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/service.py`

Add method to MarketService class after get_fund_certificates():

```python
def get_vn30_overview(self) -> VN30OverviewResponse:
    """Get VN30 index stocks with real-time price data."""
    try:
        listing = Listing()
        trading = Trading()

        # Step 1: Get VN30 symbols
        vn30_symbols = listing.symbols_by_group('VN30')
        if vn30_symbols is None or vn30_symbols.empty:
            return VN30OverviewResponse(
                stocks=[],
                generated_at=pd.Timestamp.now(),
                total_count=0
            )

        symbols_list = vn30_symbols.tolist()

        # Step 2: Get price board data for all VN30 stocks (batch call)
        price_df = trading.price_board(
            symbols_list=symbols_list,
            flatten_columns=True,
            drop_levels=[0],
        )

        if price_df is None or price_df.empty:
            return VN30OverviewResponse(
                stocks=[],
                generated_at=pd.Timestamp.now(),
                total_count=0
            )

        # Remove duplicate columns and symbols
        price_df = price_df.loc[:, ~price_df.columns.duplicated()]
        price_df = price_df.drop_duplicates(subset=["symbol"], keep="first")

        # Step 3: Get company names (use all_symbols for efficiency)
        all_symbols_df = listing.all_symbols()
        company_names = {}
        if all_symbols_df is not None and not all_symbols_df.empty:
            for _, row in all_symbols_df.iterrows():
                symbol = row.get("symbol")
                name = row.get("organ_name") or row.get("organName")
                if symbol and name:
                    company_names[symbol] = name

        # Step 4: Build response items
        stocks = []
        for _, row in price_df.iterrows():
            symbol = str(row.get("symbol", ""))
            if not symbol:
                continue

            # Extract price data
            match_price = safe_float(row.get("match_price"))
            ref_price = safe_float(row.get("ref_price"))

            # Calculate change percentage
            change_pct = None
            if match_price and ref_price and ref_price > 0:
                change_pct = ((match_price - ref_price) / ref_price) * 100

            # Calculate market cap (price * listed_share / 1e9 for billion VND)
            market_cap = None
            listed_share = safe_float(row.get("listed_share"))
            if match_price and listed_share:
                market_cap = (match_price * listed_share) / 1e9

            stocks.append(VN30OverviewItem(
                symbol=symbol,
                company_name=company_names.get(symbol, symbol),
                price=round(match_price, 2) if match_price else None,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                volume=safe_float(row.get("accumulated_volume")),
                market_cap=round(market_cap, 2) if market_cap else None,
            ))

        # Sort by market cap descending (largest first)
        stocks.sort(key=lambda x: x.market_cap or 0, reverse=True)

        return VN30OverviewResponse(
            stocks=stocks,
            generated_at=pd.Timestamp.now(),
            total_count=len(stocks),
        )

    except Exception as e:
        logger.error(f"Error fetching VN30 overview: {e}")
        raise StockServiceError(f"Failed to fetch VN30 overview: {e}")
```

**Key Points**:
- Batch API call for efficiency (single price_board call for all 30 stocks)
- Reuse all_symbols() for company names (already cached)
- Calculate change_pct from match_price and ref_price
- Sort by market cap for meaningful ordering
- Proper error handling and logging

### Step 3: Add Router Endpoint
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py`

Add imports at top:
```python
from ..schemas.market import (
    SectorPerformanceResponse,
    FundCertificatesResponse,
    VN30OverviewResponse,  # Add this
)
```

Add cache instance after existing caches:
```python
vn30_overview_cache = TradingHoursCache(
    key_prefix="stock:vn30:",
    ttl_trading=300,      # 5 minutes during trading
    ttl_off_hours=3600,   # 1 hour off-hours
)
```

Add endpoint after get_fund_certificates():
```python
@router.get("/vn30-overview", response_model=VN30OverviewResponse, dependencies=[Depends(standard_rate_limit)])
async def get_vn30_overview() -> VN30OverviewResponse:
    """Get VN30 index stocks with real-time price data."""
    cache_key = "overview"

    # Check cache first
    cached = vn30_overview_cache.get(cache_key)
    if cached is not None:
        return VN30OverviewResponse(**cached)

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.get_vn30_overview()

        # Cache the result
        vn30_overview_cache.set(cache_key, result.model_dump())

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Key Points**:
- Follows existing endpoint pattern (sector-performance, fund-certificates)
- Uses TradingHoursCache for smart caching
- Rate limiting via standard_rate_limit
- Proper error handling with 502 status

### Step 4: Update Service Imports
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/service.py`

Add to imports at top:
```python
from ..schemas.market import (
    SectorPerformanceItem,
    SectorPerformanceResponse,
    FundCertificateItem,
    FundCertificatesResponse,
    VN30OverviewItem,        # Add this
    VN30OverviewResponse,    # Add this
)
```

### Step 5: Test Endpoint
**Manual Testing**:
```bash
# Start API server
cd apps/api
uvicorn src.main:app --reload

# Test endpoint
curl http://localhost:8000/api/v1/stocks/vn30-overview

# Expected response structure:
{
  "stocks": [
    {
      "symbol": "VCB",
      "company_name": "Ngân hàng TMCP Ngoại thương Việt Nam",
      "price": 95500.0,
      "change_pct": 2.15,
      "volume": 1234567.0,
      "market_cap": 456789.12
    },
    ...
  ],
  "generated_at": "2025-12-21T12:00:00",
  "total_count": 30
}
```

**Validation Checks**:
- Response time <3 seconds
- All 30 VN30 stocks returned
- Prices and change_pct calculated correctly
- Company names populated
- Sorted by market cap descending
- Cache working (second request faster)

## Success Criteria

- [x] Pydantic schemas created and validated
- [x] Service method implemented with proper error handling
- [x] Router endpoint added with caching
- [x] Manual testing passes all validation checks
- [x] Response time consistently <3 seconds
- [x] Cache reduces subsequent request time to <100ms
- [x] Proper logging for debugging
- [x] No rate limit errors during testing

## Completion Summary

**Completed**: 2025-12-21
**Testing Results**: 30/30 VN30 stocks returned successfully, sorted by market cap

**Deliverables Implemented**:
- Pydantic schemas: `VN30OverviewItem`, `VN30OverviewResponse` in `market.py`
- Service method: `get_vn30_overview()` in `market/service.py`
- Router endpoint: `/vn30-overview` in `market/router.py` with TradingHoursCache
- Facade delegation: `get_vn30_overview()` in `service.py`

## Risk Assessment

**Low Risk**:
- Pattern well-established in codebase
- vnstock API proven reliable for batch calls
- Similar endpoints already working

**Potential Issues**:
1. **vnstock API rate limits**: Mitigated by caching and batch calls
2. **Company name lookup slow**: Mitigated by reusing cached all_symbols()
3. **Missing data for some stocks**: Handled with Optional fields and safe_float()

**Mitigation**:
- Comprehensive error handling at each step
- Fallback to symbol if company name unavailable
- Cache responses to minimize API calls
- Log errors for monitoring

## Testing Checklist

- [x] Endpoint returns 200 with valid data
- [x] All 30 VN30 stocks present
- [x] Price and change_pct calculated correctly
- [x] Company names populated
- [x] Sorted by market cap
- [x] Cache working (check logs)
- [x] Rate limiting applied
- [x] Error handling works (test with API down)
- [x] Response schema validates
- [x] Performance <3s consistently

## Next Steps

After completion, proceed to [Phase 02: Frontend Components](./phase-02-frontend-components.md)
