# Vnstock Intraday Data Research for Volume Analysis

**Date:** 2024-12-20
**Focus:** `Quote.intraday()` capabilities for volume anomaly detection

## 1. Quote.intraday() Method

### Initialization & Usage
```python
from vnstock import Vnstock
stock = Vnstock().stock(symbol='ACB', source='VCI')
df = stock.quote.intraday(symbol='ACB', page_size=10_000, show_log=False)

# Or direct Quote usage
from vnstock import Quote
quote = Quote(symbol='ACB', source='VCI')
df = quote.intraday()
```

### Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `symbol` | str | Stock ticker (e.g., 'ACB', 'VNM') |
| `page_size` | int | Records to fetch (up to 10,000) |
| `show_log` | bool | Enable/disable logging |

## 2. Return Data Structure

Returns `pandas.DataFrame` with columns:

| Column | Dtype | Description |
|--------|-------|-------------|
| `time` | datetime64[ns] | Transaction timestamp (second-accurate) |
| `price` | float64 | Transaction price |
| `volume` | int64 | Shares traded in transaction |
| `match_type` | object | Trade type: 'Buy', 'Sell', 'ATO', 'ATC' |
| `id` | object | Unique transaction ID |
| `accumulated_val` | int64 | Cumulative traded value (VCI source) |
| `accumulated_vol` | int64 | Cumulative traded volume (VCI source) |

### Sample Output
```
                   time  price  accumulated_vol  volume match_type
0   2024-11-08 09:15:01   64.9            20300   20300        ATO
1   2024-11-08 09:15:43   64.9            20600     300       Sell
...
659 2024-11-08 14:45:02   64.6           700700   35400        ATC
```

## 3. Limitations

| Limitation | Detail |
|------------|--------|
| **Data retention** | Current trading session only (no historical intraday) |
| **Trading hours** | 9:00 - 15:00 Vietnam time |
| **Rate limits** | Recommend 1s delay between API calls |
| **Max records** | ~10,000 per call (pagination available) |

## 4. Best Practices for Time Bar Aggregation

### Tick-to-Bar Aggregation Pattern
```python
import pandas as pd

def aggregate_to_bars(df: pd.DataFrame, interval: str = '5min') -> pd.DataFrame:
    """Aggregate tick data to OHLCV bars."""
    df = df.set_index('time').sort_index()

    bars = df.resample(interval).agg({
        'price': ['first', 'max', 'min', 'last'],
        'volume': 'sum'
    })
    bars.columns = ['open', 'high', 'low', 'close', 'volume']

    # Add buy/sell volume breakdown
    buy_vol = df[df['match_type'] == 'Buy'].resample(interval)['volume'].sum()
    sell_vol = df[df['match_type'] == 'Sell'].resample(interval)['volume'].sum()
    bars['buy_volume'] = buy_vol
    bars['sell_volume'] = sell_vol

    return bars.dropna()
```

### Collection Strategy for Historical Data
1. Run daily collection at 15:05 (after ATC)
2. Store raw ticks or pre-aggregated 5-min bars
3. Use Parquet format for efficient storage
4. Add 1s delay between ticker API calls

### Volume Analysis Fields
- `volume`: Per-transaction volume for spike detection
- `accumulated_vol`: Running total for session progress
- `match_type`: Buy/Sell pressure analysis
- Derived: VWAP, buy/sell ratio, volume profile

## 5. Key Findings

1. **Suitable for volume analysis** - Provides tick-level granularity with buy/sell classification
2. **Current day only** - Must collect daily and store for historical analysis
3. **Rich metadata** - Transaction IDs enable deduplication, match_type enables order flow analysis
4. **Aggregation required** - Raw ticks need resampling to time bars for pattern detection

## Unresolved Questions
- Exact rate limit thresholds (undocumented)
- Data availability during market holidays
- Handling of order amendments/cancellations in tick data
