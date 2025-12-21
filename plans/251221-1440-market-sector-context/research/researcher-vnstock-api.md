# vnstock API Research Report

**Library:** vnstock (thinh-vu/vnstock)
**Purpose:** Market & Sector Context Feature
**Date:** 2025-12-21

## Overview

vnstock is a Python library for accessing Vietnamese stock market data. Supports multiple data sources (VCI, TCBS, MSN) with unified interface.

## 1. Stock Price History (OHLCV)

### Basic Usage

```python
from vnstock import Vnstock, Quote

# Method 1: Unified interface
stock = Vnstock().stock(symbol='ACB', source='VCI')
df = stock.quote.history(start='2024-01-01', end='2025-03-19', interval='1D')

# Method 2: Direct Quote class
quote = Quote(symbol='ACB', source='VCI')
df = quote.history(start='2024-01-01', end='2025-03-19', interval='1D')
```

### Response Metadata

```python
print(f'Symbol: {df.name}')
print(f'Asset Category: {df.category}')
```

### Parameters
- `symbol`: Stock ticker (e.g., 'ACB', 'FPT')
- `start`: Start date (format: 'YYYY-MM-DD')
- `end`: End date (format: 'YYYY-MM-DD')
- `interval`: Data interval ('1D' for daily)
- `source`: Data provider ('VCI', 'TCBS', 'MSN')

### Limitations
- Date format must be 'YYYY-MM-DD'
- Interval options not fully documented (confirmed: '1D')
- DataFrame includes metadata attributes (name, category)

## 2. Index History (VNINDEX, VN30)

### Supported Indices

```python
# VNINDEX (Ho Chi Minh Stock Exchange)
df_vnindex = stock.quote.history(symbol='VNINDEX', start='2024-01-02', end='2025-03-19', interval='1D')

# HNXINDEX (Hanoi Stock Exchange)
df_hnx = stock.quote.history(symbol='HNXINDEX', start='2024-01-02', end='2025-03-19', interval='1D')

# UPCOMINDEX (Unlisted Public Company Market)
df_upcom = stock.quote.history(symbol='UPCOMINDEX', start='2024-01-02', end='2025-03-19', interval='1D')
```

### VN30 Index Constituents

```python
from vnstock import Listing

listing = Listing()
vn30_stocks = listing.symbols_by_group('VN30')
```

### Futures Data

```python
# VN30 Futures
df_futures = stock.quote.history(symbol='VN30F1M', start='2024-01-02', end='2025-03-19', interval='1D')
df_futures2 = stock.quote.history(symbol='VN30F2411', start='2024-01-02', end='2025-03-19', interval='1D')
```

### Limitations
- Same API as stock history (no separate index endpoint)
- Use special symbols: VNINDEX, HNXINDEX, UPCOMINDEX
- VN30 is a group, not directly queryable as index

## 3. Industry/Sector Classification (ICB Codes)

### Get ICB Industry List

```python
from vnstock import Listing

listing = Listing()

# Get all industries with ICB codes
industries_df = listing.industries_icb()
```

### Response Structure
Returns DataFrame mapping ICB codes to industry names following Industry Classification Benchmark standard.

### Limitations
- Documentation doesn't show exact DataFrame columns
- ICB (Industry Classification Benchmark) is international standard
- No examples of filtering by specific ICB code

## 4. Stocks by Sector

### Get All Stocks by Industry

```python
from vnstock import Listing

listing = Listing()

# Get all stocks organized by industry (ICB)
stocks_by_industry = listing.symbols_by_industries()
```

### Get Stocks by Market Group

```python
# VN30 index constituents
vn30_stocks = listing.symbols_by_group('VN30')

# VNMidCap stocks
midcap_stocks = listing.symbols_by_group('VNMidCap')

# ETFs
etfs = listing.symbols_by_group('ETF')

# Covered Warrants
cws = listing.symbols_by_group('CW')
```

### Get All Symbols

```python
# All listed symbols
all_stocks = listing.all_symbols()

# Symbols by exchange
by_exchange = listing.symbols_by_exchange()
```

### Stock Screener (Advanced Filtering)

```python
from vnstock import Screener

# Filter stocks by exchange (requires TCBS source)
screener_df = stock.screener.stock(
    params={"exchangeName": "HOSE,HNX,UPCOM"},
    limit=1700
)
```

### Limitations
- `symbols_by_industries()` returns all stocks with ICB classification
- No direct filtering by specific sector/industry code shown
- Screener requires TCBS source
- Group filtering limited to predefined groups (VN30, VNMidCap, ETF, CW)

## Additional Features

### Real-time Price Board

```python
from vnstock import Trading

# Get real-time quotes for multiple stocks
trading = Trading(source='VCI')
prices = trading.price_board(['VCB', 'ACB', 'TCB', 'BID'])

# Flattened format
prices_flat = trading.price_board(
    ['VCB', 'ACB', 'TCB', 'BID'],
    flatten_columns=True,
    drop_levels=[0]
).T
```

### Price Depth

```python
# Real-time bid/ask depth
depth = stock.quote.price_depth('ACB')
```

## Key Takeaways

1. **Unified Interface**: Use `Vnstock()` for consistent API across data sources
2. **Multiple Sources**: VCI, TCBS, MSN (choose based on data availability)
3. **Index Data**: Use same history() method with index symbols
4. **ICB Classification**: Built-in support for industry classification
5. **Sector Filtering**: Use `symbols_by_industries()` for ICB-based grouping

## Limitations Summary

- Interval options beyond '1D' not documented
- No direct sector filtering (must filter DataFrame post-fetch)
- Screener functionality requires TCBS source
- ICB code filtering mechanism not explicitly shown
- Real-time features may have rate limits (not documented)
- Date range limits not specified

## Recommended Implementation

For Market & Sector Context feature:
1. Use `Quote.history()` for OHLCV data
2. Use `Listing.industries_icb()` for sector mapping
3. Use `Listing.symbols_by_industries()` for sector constituents
4. Use `Quote.history(symbol='VNINDEX')` for market index
5. Filter DataFrames in application layer for specific sectors
