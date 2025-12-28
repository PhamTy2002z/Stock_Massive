# Research: vnstock Data Availability Analysis

**Date**: 2024-12-27
**Status**: Complete

## Problem

vnstock Trading class methods raise `NotImplementedError` for VCI/TCBS sources:
- `Trading.foreign_trade()` - NOT IMPLEMENTED
- `Trading.prop_trade()` - NOT IMPLEMENTED
- `Trading.order_stats()` - NOT IMPLEMENTED

## Working Methods (Tested)

| Method | Returns | Data Type |
|--------|---------|-----------|
| `quote.history()` | DataFrame | OHLCV daily/weekly |
| `quote.intraday()` | DataFrame | Real-time tick data (time, price, volume, match_type) |
| `quote.price_depth()` | DataFrame | Bid/Ask levels with accumulated volumes |
| `company.trading_stats()` | DataFrame | Snapshot: foreign_volume, foreign_room, current_holding_ratio |
| `finance.ratio()` | DataFrame | Historical financial ratios |

## quote.intraday() Analysis

```python
# Returns per-trade data for current day
df = stock.quote.intraday(page_size=10000)
# Columns: ['time', 'price', 'volume', 'match_type', 'id']
# match_type values: 'ATO', 'Sell', 'Buy', 'ATC'

# Aggregated example:
# match_type  | count | sum_volume
# ATC         |   1   | 185,700
# ATO         |   1   |  15,500
# Buy         | 1487  | 1,128,200
# Sell        | 1600  | 1,069,500
```

## company.trading_stats() Analysis

```python
# Single row snapshot
df = stock.company.trading_stats()
# Columns include:
# - foreign_volume: 820,196
# - foreign_room: 2,089,955,445
# - current_holding_ratio: 0.506
# - avg_match_volume_2w: 3,538,353
# - total_volume: 2,449,027
```

## Recommended Approach

### Option 1: Real-time Order Stats from intraday()
- Calculate buy/sell order counts from match_type
- Only available for CURRENT day
- No historical data

### Option 2: Foreign snapshot from trading_stats()
- Current foreign volume, ownership ratio
- No historical chart
- Combine with price_depth for market depth view

## Limitations

- NO historical foreign/prop trading data
- NO multi-day order statistics
- Real-time data only for current trading session
