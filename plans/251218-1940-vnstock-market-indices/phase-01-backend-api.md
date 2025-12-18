# Phase 01: Backend API Endpoint

## Context
- **Parent Plan**: [plan.md](./plan.md)
- **Dependencies**: vnstock library (already installed)
- **Docs**: [code-standards.md](../../docs/code-standards.md)

## Overview
- **Date**: 2024-12-18
- **Priority**: High
- **Implementation Status**: Pending
- **Review Status**: Pending

## Key Insights
- vnstock `Quote` class works for indices same as stocks
- Supported symbols: VNINDEX, VN30, HNXINDEX, UPCOMINDEX
- Need to calculate change values from historical data

## Requirements
1. New endpoint `GET /api/v1/indices` returning market index data
2. Response includes: symbol, name, value, change, changePercent, chartData
3. Fetch 10-day history for sparkline data
4. Handle market closed scenarios gracefully

## Architecture
```
Router (indices endpoint)
    ↓
Service (get_market_indices)
    ↓
vnstock Quote class
```

## Related Code Files
- `apps/api/src/stocks/router.py` - Add new endpoint
- `apps/api/src/stocks/service.py` - Add service method
- `apps/api/src/stocks/schemas.py` - Add response schema

## Implementation Steps

### Step 1: Add Pydantic Schema
**File**: `apps/api/src/stocks/schemas.py`
```python
class MarketIndex(BaseModel):
    symbol: str
    name: str
    value: float
    change: float
    change_percent: float
    chart_data: list[float] = []
```

### Step 2: Add Service Method
**File**: `apps/api/src/stocks/service.py`
```python
MARKET_INDICES = [
    ("VNINDEX", "VN-INDEX"),
    ("VN30", "VN30"),
    ("HNXINDEX", "HNX-INDEX"),
    ("UPCOMINDEX", "UPCOM-INDEX"),
]

def get_market_indices(self) -> list[MarketIndex]:
    """Get current market index data with sparkline."""
    results = []
    end = date.today()
    start = end - timedelta(days=20)  # Extra days for weekends

    for symbol, name in MARKET_INDICES:
        try:
            quote = Quote(symbol=symbol, source=self.source)
            df = quote.history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval="1D"
            )

            if df is None or len(df) < 2:
                continue

            # Get last 10 trading days
            df = df.tail(10)
            closes = df['close'].tolist()

            # Calculate change
            current = closes[-1]
            previous = closes[-2] if len(closes) > 1 else current
            change = current - previous
            change_pct = (change / previous * 100) if previous else 0

            results.append(MarketIndex(
                symbol=symbol,
                name=name,
                value=current,
                change=change,
                change_percent=change_pct,
                chart_data=closes
            ))
        except Exception as e:
            logger.warning(f"Failed to fetch {symbol}: {e}")
            continue

    return results
```

### Step 3: Add Router Endpoint
**File**: `apps/api/src/stocks/router.py`
```python
@router.get("/indices", response_model=list[MarketIndex])
async def get_market_indices() -> list[MarketIndex]:
    """Get current market index data.

    Returns VNINDEX, VN30, HNXINDEX, UPCOMINDEX with:
    - Current value
    - Daily change and percentage
    - 10-day sparkline data
    """
    try:
        service = get_service()
        return service.get_market_indices()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Step 4: Update Schema Import
Add `MarketIndex` to imports in `router.py`

## Todo List
- [ ] Add `MarketIndex` schema to schemas.py
- [ ] Add `get_market_indices()` to StockService
- [ ] Add `/indices` endpoint to router.py
- [ ] Test endpoint manually
- [ ] Add unit tests (optional)

## Success Criteria
- [ ] `GET /api/v1/indices` returns 4 indices
- [ ] Each index has valid value, change, changePercent
- [ ] chartData contains ~10 float values
- [ ] Handles errors gracefully (returns partial data)

## Risk Assessment
- **Low**: vnstock API may be slow - mitigate with caching later
- **Low**: Weekend/holiday data gaps - handled by fetching 20 days

## Security Considerations
- No user input validation needed (no parameters)
- Rate limiting recommended for production

## Next Steps
After completion, proceed to [Phase 02: Frontend Integration](./phase-02-frontend-integration.md)
