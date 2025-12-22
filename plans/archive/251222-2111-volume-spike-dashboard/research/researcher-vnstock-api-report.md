# vnstock API Research Report - Volume Spike Detection
**Date:** 2025-12-22
**Researcher:** Claude Code
**Scope:** VCI data source, volume/value APIs, ICB classification, volume spike metrics

---

## Executive Summary
vnstock library does NOT provide built-in `top.volume()` or `top.value()` APIs. No pre-calculated volume spike metrics found. Must implement custom volume spike detection using available trading data APIs.

---

## 1. Top Performers APIs - NOT FOUND

### Expected APIs (NOT AVAILABLE)
- `top.volume()` - Does not exist
- `top.value()` - Does not exist
- `volume_spike_20d_pct` - No pre-calculated metric

### Alternative Approach Required
Must fetch raw trading data and calculate volume spikes manually:
- Use `Trading().price_board()` for real-time data
- Use `stock.quote.intraday()` for intraday tick data
- Use `company.trading_stats()` for trading statistics
- Calculate volume comparisons against historical averages

---

## 2. Available Trading Data APIs

### 2.1 Price Board (Real-time)
```python
from vnstock import Trading
Trading(source='VCI').price_board(['VCB','ACB','TCB','BID'])
```
- **Purpose:** Real-time trading prices for multiple symbols
- **Source:** VCI
- **Returns:** Current price, volume data for specified symbols
- **Rate Limits:** Not documented

### 2.2 Intraday Trading Data
```python
stock.quote.intraday(symbol='ACB', page_size=10_000, show_log=False)
```
- **Purpose:** Granular tick-level order book data
- **Parameters:**
  - `symbol`: Stock ticker (e.g., 'ACB')
  - `page_size`: Max 10,000 records
  - `show_log`: Boolean for logging
- **Returns:** Order book with timestamps, prices, volumes
- **Rate Limits:** Not documented

### 2.3 Company Trading Statistics
```python
company.trading_stats()
```
- **Purpose:** Statistical trading data (volume, turnover)
- **Returns:** Aggregated trading metrics
- **Use Case:** Market participation insights

### 2.4 Price Depth
```python
stock.quote.price_depth('ACB')
```
- **Purpose:** Real-time bid/ask with volumes
- **Re* Market liquidity snapshot

---

## 3. Listing & ICB Classification

### 3.1 Symbols by Industries
```python
from vnstock import Listing
listing = Listing()
listing.symbols_by_industries()
```
- **Purpose:** Stock symbols grouped by ICB codes
- **Returns:** DataFrame with symbol-to-industry mapping
- **Use Case:** Sector-specific analysis

### 3.2 Industries ICB Mapping
```python
listing.industries_icb()
```
- **Purpose:** ICB code to industry name mapping
- **Returns:** ICB classification structure
- **Use Case:** Industry categorization

### 3.3 Other Listing Methods
```python
listing.all_symbols()                    # All available symbols
listing.symbols_by_exchange()            # By exchange (HOSE, HNX, UPCOM)
listing.symbols_by_group('VN30')         # By index (VN30, VNMidCap, ETF, CW)
```

---

## 4. VCI Data Source Specifics

### 4.1 Source Configuration
- **Primary Source:** VCI (Viet Capital Securities)
- **Alternative:** TCBS (available but not primary focus)
- **Initialization:** `Trading(source='VCI')`

### 4.2 Data Characteristics
- Real-time price board available
- Intraday tick data up to 10,000 records per request
- No historical volume spike pre-calculations
- No documented rate limits (use cautiously)

### 4.3 Limitations
- No built-in top performers ranking
- No volume spike percentage metrics
- Must calculate volume comparisons manually
- Historical data requires separate API calls
- Rate limits not explicitly documented

---

## 5. Volume Spike Implementation Strategy

### Required Custom Implementation
1. **Fetch Historical Data:** Get 20-day volume history per symbol
2. **Calculate Average:** Compute 20-day average volume
3. **Compare Current:** Calculate percentage change vs average
4. **Rank & Filter:** Sort by spike percentage, filter threshold
5. **Industry Context:** Join with ICB classification

### Data Flow
```
all_symbols() → historical_volume_data → calculate_avg_20d →
current_volume → spike_pct → rank → filter → add_icb_info
```

### Performance Considerations
- Batch processing required for all symbols (~1,700+ stocks)
- Cache historical averages to reduce API calls
- Implement rate limiting/throttling
- Consider async requests for scalability

---

## 6. Unresolved Questions

1. **Rate Limits:** VCI API rate limits not documented - need empirical testing
2. **Historical Volume API:** Which API provides 20-day historical volume efficiently?
3. **Data Freshness:** Real-time vs delayed data latency?
4. **Batch Limits:** Max symbols per `price_board()` call?
5. **Error Handling:** API failure modes and retry strategies?

---

## Recommendations

1. **Use `Trading().price_board()`** for current volume data
2. **Implement custom volume spike calculator** (no built-in API)
3. **Cache ICB mappings** from `listing.symbols_by_industries()`
4. **Test rate limits** empirically before production deployment
5. **Consider alternative data sources** if VCI proves insufficient
6. **Build incremental updates** rather than full scans per request

---

**End of Report**
