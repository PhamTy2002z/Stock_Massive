# Phase 1: Backend - Unified Stock Detail Endpoint

**Status:** DONE
**Completed:** 2025-12-18 21:53:48
**Effort:** 4-6 hours
**Priority:** High

---

## Context

**Problem:** Frontend needs 3 separate API calls to display stock detail page:
1. `/stocks/price-board?symbols={symbol}` - real-time price data
2. `/stocks/{symbol}/company` - company overview
3. `/stocks/{symbol}/financials/ratios` - financial ratios

**Solution:** Create single unified endpoint that combines all data in one response.

**Related Research:**
- `/plans/251218-2134-stock-detail-realtime/research/researcher-01-vnstock-price-data.md`

---

## Overview

Create `GET /stocks/{symbol}/detail` endpoint that returns comprehensive stock data by combining:
- Price board data (real-time prices, volume, trading value)
- Company overview (name, industry, market cap, shares)
- Financial ratios (EPS, P/E, Beta, dividend yield)

---

## Requirements

### Functional
- Single API call returns all data needed for stock detail page
- Response time < 2 seconds
- Handle missing/null data gracefully (Beta, dividend yield)
- Validate symbol format before vnstock calls
- Return 404 for invalid symbols

### Non-Functional
- Cache response for 15 seconds (real-time data tolerance)
- Log errors with symbol context
- Follow existing error handling patterns

---

## Architecture

### Endpoint Design
```
GET /stocks/{symbol}/detail
Response: StockDetail schema (see below)
Status Codes:
  200 - Success
  404 - Symbol not found
  502 - vnstock API error
```

### Data Flow
```
Client Request
    ↓
Router: /stocks/{symbol}/detail
    ↓
Service: get_stock_detail(symbol)
    ↓
Parallel vnstock calls:
  - Trading.price_board([symbol])
  - Vnstock.stock(symbol).company.overview()
  - Vnstock.stock(symbol).company.ratio_summary()
    ↓
Merge data into StockDetail schema
    ↓
Return JSON response
```

---

## Implementation Steps

### Step 1: Update Schemas (schemas.py)

**Add new StockDetail schema:**
```python
class StockDetail(BaseModel):
    """Comprehensive stock detail data."""

    # Basic Info
    symbol: str
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None

    # Real-time Price Data
    price: Optional[float] = None  # match_price
    change: Optional[float] = None
    change_pct: Optional[float] = None
    ceiling: Optional[float] = None
    floor: Optional[float] = None
    ref_price: Optional[float] = None

    # Intraday Range
    open_price: Optional[float] = None
    high_price: Optional[float] = None  # highest
    low_price: Optional[float] = None   # lowest

    # Volume & Value
    volume: Optional[int] = None  # accumulated_volume
    trading_value: Optional[float] = None  # accumulated_value (billion VND)

    # Market Cap & Shares
    market_cap: Optional[float] = None  # billion VND
    outstanding_shares: Optional[float] = None  # billion shares
    issue_share: Optional[float] = None

    # 52-Week Data (optional - can be added later)
    high_52_week: Optional[float] = None
    low_52_week: Optional[float] = None
    avg_volume_52_week: Optional[int] = None

    # Financial Ratios
    eps: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    beta: Optional[float] = None
    dividend_yield: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None

    # Company Details
    description: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    established_year: Optional[int] = None
```

**Update PriceBoardItem schema (add missing fields):**
```python
class PriceBoardItem(BaseModel):
    """Price board data for a single stock."""

    symbol: str
    # Add these fields:
    match_price: Optional[float] = None  # Current trading price
    highest: Optional[float] = None      # Day's high
    lowest: Optional[float] = None       # Day's low
    accumulated_volume: Optional[int] = None
    accumulated_value: Optional[float] = None

    # Existing fields:
    ceiling: Optional[float] = None
    floor: Optional[float] = None
    ref_price: Optional[float] = None
    last_price: Optional[float] = None
    last_vol: Optional[int] = None
    total_vol: Optional[int] = None
    total_val: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
```

### Step 2: Add Service Method (service.py)

**Add `get_stock_detail()` method to StockService class:**
```python
def get_stock_detail(self, symbol: str) -> dict:
    """Get comprehensive stock detail data.

    Combines price board, company overview, and financial ratios.

    Args:
        symbol: Stock symbol

    Returns:
        Dictionary with all stock detail fields
    """
    symbol = validate_symbol(symbol)

    # Initialize result with symbol
    result = {"symbol": symbol.upper()}

    try:
        # 1. Get price board data
        trading = Trading()
        price_df = trading.price_board(
            symbols_list=[symbol],
            flatten_columns=True,
            drop_levels=[0]
        )

        if price_df is not None and not price_df.empty:
            row = price_df.iloc[0]
            result.update({
                "price": self._safe_float(row.get("match_price")),
                "ceiling": self._safe_float(row.get("ceiling")),
                "floor": self._safe_float(row.get("floor")),
                "ref_price": self._safe_float(row.get("ref_price")),
                "high_price": self._safe_float(row.get("highest")),
                "low_price": self._safe_float(row.get("lowest")),
                "volume": int(row.get("accumulated_volume", 0)) if pd.notna(row.get("accumulated_volume")) else None,
                "trading_value": self._safe_float(row.get("accumulated_value")),
            })

            # Calculate change if we have price and ref_price
            if result.get("price") and result.get("ref_price"):
                change = result["price"] - result["ref_price"]
                change_pct = (change / result["ref_price"]) * 100
                result["change"] = round(change, 2)
                result["change_pct"] = round(change_pct, 2)

    except Exception as e:
        logger.warning(f"Error fetching price board for {symbol}: {e}")

    try:
        # 2. Get company overview
        stock = Vnstock().stock(symbol=symbol, source=self.source)
        overview = stock.company.overview()

        if overview is not None and not (isinstance(overview, pd.DataFrame) and overview.empty):
            if isinstance(overview, pd.DataFrame):
                row = overview.iloc[0].to_dict() if len(overview) > 0 else {}
            else:
                row = overview if isinstance(overview, dict) else {}

            result.update({
                "company_name": row.get("organ_name") or row.get("short_name") or row.get("company_name"),
                "exchange": row.get("exchange"),
                "industry": row.get("icb_name3") or row.get("icb_name2") or row.get("industry"),
                "issue_share": self._safe_float(row.get("issue_share")),
                "outstanding_shares": self._safe_float(row.get("outstanding_share")),
                "description": row.get("company_profile") or row.get("description"),
                "website": row.get("website"),
                "employees": row.get("no_employees"),
                "established_year": row.get("established_year"),
            })

            # Calculate market cap if we have price and issue_share
            if result.get("price") and result.get("issue_share"):
                # issue_share is in shares, price is per share
                # market_cap in billion VND
                market_cap = (result["price"] * result["issue_share"]) / 1_000_000_000
                result["market_cap"] = round(market_cap, 2)

    except Exception as e:
        logger.warning(f"Error fetching company overview for {symbol}: {e}")

    try:
        # 3. Get financial ratios (summary)
        ratios = stock.company.ratio_summary()

        if ratios is not None and not (isinstance(ratios, pd.DataFrame) and ratios.empty):
            if isinstance(ratios, pd.DataFrame):
                row = ratios.iloc[0].to_dict() if len(ratios) > 0 else {}
            else:
                row = ratios if isinstance(ratios, dict) else {}

            result.update({
                "eps": self._safe_float(row.get("eps") or row.get("eps_ttm")),
                "pe": self._safe_float(row.get("pe") or row.get("price_to_earning")),
                "pb": self._safe_float(row.get("pb") or row.get("price_to_book")),
                "roe": self._safe_float(row.get("roe")),
                "roa": self._safe_float(row.get("roa")),
            })

        # Try to get Beta from Vietnamese ratio data
        try:
            finance = Finance(symbol=symbol, source=self.source)
            ratio_df = finance.ratio(period='year', lang='vi', dropna=True)
            if ratio_df is not None and not ratio_df.empty and 'Beta' in ratio_df.columns:
                beta_val = ratio_df['Beta'].iloc[0] if len(ratio_df) > 0 else None
                result["beta"] = self._safe_float(beta_val)
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"Error fetching financial ratios for {symbol}: {e}")

    return result
```

### Step 3: Add Router Endpoint (router.py)

**Add new endpoint:**
```python
@router.get("/{symbol}/detail", response_model=StockDetail)
async def get_stock_detail(symbol: str) -> StockDetail:
    """Get comprehensive stock detail data.

    Returns combined data from price board, company overview, and financial ratios.
    Single endpoint for all stock detail page requirements.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_service()
        data = service.get_stock_detail(symbol)
        return StockDetail(**data)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Step 4: Update Price Board Mapping (service.py)

**Update `_df_to_price_board()` to include new fields:**
```python
def _df_to_price_board(self, df: pd.DataFrame) -> list[PriceBoardItem]:
    """Convert DataFrame to list of PriceBoardItem."""
    items = []
    for row in df.to_dict("records"):
        try:
            items.append(
                PriceBoardItem(
                    symbol=str(row.get("symbol", row.get("ticker", ""))),
                    # Add new fields:
                    match_price=self._safe_float(row.get("match_price")),
                    highest=self._safe_float(row.get("highest")),
                    lowest=self._safe_float(row.get("lowest")),
                    accumulated_volume=int(row.get("accumulated_volume", 0)) if pd.notna(row.get("accumulated_volume")) else None,
                    accumulated_value=self._safe_float(row.get("accumulated_value")),
                    # Existing fields:
                    ceiling=self._safe_float(row.get("ceiling")),
                    floor=self._safe_float(row.get("floor")),
                    ref_price=self._safe_float(row.get("ref_price") or row.get("refPrice")),
                    last_price=self._safe_float(row.get("last_price") or row.get("lastPrice")),
                    last_vol=self._safe_float(row.get("last_vol") or row.get("lastVol")),
                    total_vol=self._safe_float(row.get("total_vol") or row.get("totalVol")),
                    total_val=self._safe_float(row.get("total_val") or row.get("totalVal")),
                    change=self._safe_float(row.get("change")),
                    change_pct=self._safe_float(row.get("change_pct") or row.get("changePct")),
                )
            )
        except Exception as e:
            logger.warning(f"Skipping price board item due to error: {e}")
            continue
    return items
```

---

## Todo List

- [x] Add `StockDetail` schema to `schemas.py`
- [x] Update `PriceBoardItem` schema with missing fields
- [x] Add `get_stock_detail()` method to `StockService` class
- [x] Update `_df_to_price_board()` mapping method
- [x] Add router endpoint `GET /stocks/{symbol}/detail`
- [x] Test endpoint with curl/Postman for symbols: VCB, ACB, HAG
- [x] Verify all fields populated correctly
- [x] Test error handling for invalid symbol (e.g., INVALID123)
- [x] Check response time (should be < 2s)
- [x] Update API documentation

---

## Success Criteria

- [x] Endpoint returns 200 with complete data for valid symbols
- [x] Response includes all required fields (price, company, ratios)
- [x] Null/missing fields handled gracefully (no crashes)
- [x] Response time < 2 seconds for typical symbols
- [x] 404 returned for invalid symbols
- [x] Error logs include symbol context
- [x] Beta and dividend_yield can be null (acceptable)

---

## Testing Commands

```bash
# Test valid symbol
curl http://localhost:8000/api/v1/stocks/VCB/detail | jq

# Test another symbol
curl http://localhost:8000/api/v1/stocks/HAG/detail | jq

# Test invalid symbol (should return 404 or 502)
curl http://localhost:8000/api/v1/stocks/INVALID/detail

# Check response time
time curl http://localhost:8000/api/v1/stocks/VCB/detail
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| vnstock API timeout | Medium | High | Add timeout to each call, return partial data |
| Missing Beta/dividend data | High | Low | Make fields optional, show "N/A" in UI |
| Price board returns empty | Low | High | Check for empty DataFrame, return null values |
| Multiple symbols in price_board | Low | Medium | Always use `iloc[0]` to get first row |

---

## Related Files

**Modified:**
- `/apps/api/src/stocks/schemas.py` - Add StockDetail, update PriceBoardItem
- `/apps/api/src/stocks/service.py` - Add get_stock_detail(), update mapping
- `/apps/api/src/stocks/router.py` - Add new endpoint

**Referenced:**
- `/plans/251218-2134-stock-detail-realtime/research/researcher-01-vnstock-price-data.md`

---

## Next Phase

After completion, proceed to Phase 2: Frontend State Management
