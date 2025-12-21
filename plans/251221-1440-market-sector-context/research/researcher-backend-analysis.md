# Backend Analysis: Deep Dive Feature Implementation

**Date:** 2024-12-21
**Focus:** Stock-related API endpoints, data models, vnstock usage, price history & sector data

---

## 1. API Architecture Overview

### Main Router Structure
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/router.py`

- **Pattern:** Feature-based modular architecture with domain separation
- **Router hierarchy:** Market → Price → Company → Financial (order matters for path matching)
- **Base prefix:** `/stocks`

### Domain Routers
1. **Market Router** (`/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py`)
   - `/symbols` - List all stock symbols
   - `/symbols/group/{group}` - Get symbols by group (VN30, HNX30, VN100)
   - `/symbols/search` - Search symbols by ticker/name
   - `/sector-performance` - Market-cap weighted sector performance (ICB Level 2)
   - `/fund-certificates` - ETFs and open-end funds
   - `/vn30-overview` - VN30 stocks with real-time price data

2. **Price Router** (`/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py`)
   - `/{symbol}/history` - Historical OHLCV data
   - `/{symbol}/intraday` - Intraday tick data
   - `/market-indices` - VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX
   - `/price-board` - Real-time price board for multiple stocks
   - `/{symbol}/volume-analysis` - Intraday volume pattern analysis
   - `/{symbol}/volume-anomalies` - Volume anomaly detection (72 time slots)

3. **Company Router** - Company overview, shareholders, officers, insider deals
4. **Financial Router** - Financial statements, ratios, cash flow

---

## 2. Data Models

### Database Models
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/models.py`

```python
class StockIntradayBar(Base):
    """5-minute OHLCV bar for intraday trading data."""
    - symbol: String(10), indexed
    - bar_time: DateTime, indexed
    - open_price, high_price, low_price, close_price: Numeric(12,2)
    - volume: BigInteger
    - trade_value: Numeric(18,2)
    - trade_count: Integer
    - Unique constraint: (symbol, bar_time)
    - Index: (symbol, date(bar_time))
```

### Price Schemas
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas/price.py`

Key models:
- `StockPrice` - Historical OHLCV (time, open, high, low, close, volume)
- `IntradayTick` - Tick data (time, price, volume, accumulated_vol/val, match_type)
- `PriceBoardItem` - Real-time price board (symbol, match_price, highest, lowest, ceiling, floor, ref_price, change, change_pct)
- `MarketIndexItem` - Market indices (symbol, name, value, change, change_pct)
- `VolumeTimeSlot` - Volume anomaly detection with 4 levels (normal, elevated, high, very_high)

### Market Schemas
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas/market.py`

```python
class SectorPerformanceItem:
    - icb_code: str (ICB Level 2 code)
    - icb_name: str (Sector name in Vietnamese)
    - change_pct: float (Market-cap weighted change %)
    - total_market_cap: float (Billion VND)
    - stock_count: int
    - top_gainers: list[str] (Top 3 symbols)
    - top_losers: list[str] (Top 3 symbols)

class VN30OverviewItem:
    - symbol, company_name, price, change_pct, volume, market_cap
```

---

## 3. vnstock Integration

### Usage Pattern
**Primary files:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/service.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/service.py`

### vnstock Classes Used

1. **Quote** (from vnstock)
   - `history(start, end, interval)` - Historical OHLCV data
   - `intraday(page_size)` - Intraday tick data
   - Used for: Price history, market indices

2. **Trading** (from vnstock)
   - `price_board(symbols_list)` - Real-time price board (batch up to 50 symbols)
   - Used for: Real-time prices, sector performance calculation

3. **Listing** (from vnstock)
   - `all_symbols()` - All stock symbols with metadata
   - `symbols_by_exchange(exchange)` - Filter by HOSE/HNX/UPCOM
   - `symbols_by_group(group)` - VN30, HNX30, VN100 groups
   - `symbols_by_industries()` - Symbols with ICB classification

4. **Vnstock** (facade)
   - `stock(symbol).company.overview()` - Company overview
   - `stock(symbol).company.ratio_summary()` - Financial ratios
   - `stock(symbol).company.trading_stats()` - 52-week high/low

5. **Fund** (from vnstock.explorer.fmarket.fund)
   - `listing()` - Fund certificates (ETFs, open-end funds)

---

## 4. Price History Implementation

### Endpoint: `GET /stocks/{symbol}/history`
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py:42-60`

**Parameters:**
- `symbol`: Stock ticker
- `start`: Start date (YYYY-MM-DD)
- `end`: End date (default: today)
- `interval`: 1D, 1W, 1M

**Service Implementation:**
```python
# PriceService.get_history()
quote = Quote(symbol=symbol, source="VCI")
df = quote.history(start, end, interval)
# Returns list[StockPrice] with OHLCV data
```

**Features:**
- Validates symbol format
- Converts DataFrame to StockPrice schema
- Error handling with StockServiceError
- No caching (real-time data)

---

## 5. Sector Performance Implementation

### Endpoint: `GET /stocks/sector-performance`
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py:86-106`

**Service Implementation:**
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/service.py:91-243`

**Algorithm:**
1. Fetch all symbols with ICB classification (`symbols_by_industries()`)
2. Get price board for all symbols in batches of 100
3. Merge price data with ICB classification
4. Group by ICB Level 2 (sector)
5. Calculate market-cap weighted change percentage:
   ```python
   market_cap = match_price * listed_share
   weighted_change = sum(change_pct * market_cap) / sum(market_cap)
   ```
6. Extract top 3 gainers/losers per sector
7. Sort sectors by change_pct descending

**Caching:**
- TradingHoursCache: 5 min during trading, 1 hour off-hours
- Key: "performance"

**Data Fields:**
- ICB Level 2 code & name (Vietnamese)
- Market-cap weighted change %
- Total market cap (billion VND)
- Stock count
- Top gainers/losers

---

## 6. Existing Deep Dive Related Features

### VN30 Overview
**Endpoint:** `GET /stocks/vn30-overview`
- Fetches VN30 symbols via `listing.symbols_by_group("VN30")`
- Gets real-time price board for all VN30 stocks
- Calculates market cap: `(match_price * listed_share) / 1e9`
- Sorts by market cap descending
- Returns: symbol, company_name, price, change_pct, volume, market_cap

### Stock Detail (Composite)
**Service method:** `StockService.get_stock_detail(symbol)`
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/service.py:124-266`

Aggregates data from multiple sources:
1. Price board (Trading API)
2. Company overview (Vnstock)
3. Financial ratios (ratio_summary)
4. Trading stats (52-week high/low)
5. VN30 rank calculation

**Returns:** Comprehensive StockDetail with 20+ fields

---

## 7. Key Findings for Deep Dive Feature

### Available Data Sources
✅ **Historical price data** - `Quote.history()` with 1D/1W/1M intervals
✅ **Sector classification** - ICB Level 2 via `symbols_by_industries()`
✅ **Market-cap weighted sector performance** - Already implemented
✅ **Real-time price board** - Batch API for multiple symbols
✅ **Intraday data** - 5-minute bars stored in database
✅ **Volume analysis** - Peak periods and anomaly detection

### Missing for Deep Dive
❌ **Sector-specific stock listings** - Need to filter by ICB code
❌ **Sector historical performance** - Need time-series sector aggregation
❌ **Sector comparison charts** - Need multi-sector historical data
❌ **Individual stock deep-dive within sector** - Need sector context

### Recommended Approach
1. **Extend MarketService** with sector-specific methods:
   - `get_sector_stocks(icb_code)` - List stocks in sector
   - `get_sector_history(icb_code, start, end)` - Historical sector performance

2. **Create new endpoint** `/stocks/sectors/{icb_code}/deep-dive`:
   - Sector metadata (name, stock count, market cap)
   - Historical performance (30/90/365 days)
   - Top performers (gainers/losers)
   - Stock listings with key metrics

3. **Leverage existing infrastructure**:
   - Use `symbols_by_industries()` for ICB mapping
   - Reuse `price_board()` for real-time data
   - Apply TradingHoursCache pattern for performance

---

## 8. Technical Considerations

### Caching Strategy
- **TradingHoursCache** - Different TTLs for trading vs off-hours
- Market indices: 30s trading, 1h off-hours
- Price board: 15s trading, 1h off-hours
- Sector performance: 5min trading, 1h off-hours

### Rate Limiting
- `standard_rate_limit` - Most endpoints
- `heavy_rate_limit` - Volume anomalies, intraday collection

### Error Handling
- Custom `StockServiceError` exception
- Graceful degradation (log warnings, continue)
- Batch processing with error isolation

### Data Validation
- `validate_symbol()` - Symbol format validation
- `safe_float()` - Null-safe float conversion
- Schema validation via Pydantic

---

## Unresolved Questions

1. Should sector deep-dive use ICB Level 2 or Level 3 classification?
2. What time ranges for historical sector performance (30/90/365 days)?
3. Should we cache sector historical data separately or compute on-demand?
4. Do we need sector-to-sector comparison endpoints?
5. Should deep-dive include sector news/events integration?
