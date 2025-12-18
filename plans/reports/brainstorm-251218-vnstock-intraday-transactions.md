# Vnstock Intraday Transaction Data Research

**Date:** 2024-12-18
**Topic:** Can Vnstock provide individual transaction data within a trading session?

## Answer: YES

Vnstock **fully supports** retrieving individual transaction (tick-by-tick) data for any stock ticker within a single trading session.

## Function: `quote.intraday()`

### Usage

```python
from vnstock import Vnstock

# Initialize
stock = Vnstock().stock(symbol='ACB', source='VCI')

# Get intraday transactions
stock.quote.intraday(symbol='ACB', page_size=10_000, show_log=False)

# Or using Quote directly
from vnstock import Quote
quote = Quote(symbol='ACB', source='VCI')
quote.intraday()
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `symbol` | Stock ticker (e.g., 'ACB', 'VNM', 'FPT') |
| `page_size` | Number of records to fetch (default varies, can set up to 10,000) |
| `show_log` | Enable/disable logging output |

### Data Returned

Each transaction record contains:

| Column | Type | Description |
|--------|------|-------------|
| `time` | datetime64 | Exact timestamp of transaction (second-accurate) |
| `price` | float64 | Transaction price |
| `volume` | int64 | Number of shares in transaction |
| `match_type` | object | Type: 'Buy', 'Sell', 'ATO', 'ATC', 'ATO/ATC' |
| `id` | object | Unique transaction ID |
| `accumulated_val` | int64 | Cumulative traded value (some sources) |
| `accumulated_vol` | int64 | Cumulative traded volume (some sources) |

### Sample Output

```
                  time    price  volume match_type         id
99 2024-05-24 14:29:02  48000.0   40000        Buy  206446786
98 2024-05-24 14:29:04  48000.0    2000        Buy  206447031
96 2024-05-24 14:29:05  48000.0    3000        Buy  206447056
95 2024-05-24 14:29:06  48000.0   10000        Buy  206447096
...
0  2024-05-24 14:45:06  47950.0  639200    ATO/ATC  206453858
```

## Key Characteristics

1. **Real-time capable** - Can fetch during trading hours (9:00 - 15:00)
2. **Second-accurate timestamps** - Each transaction has precise timing
3. **Match type identification** - Distinguishes Buy/Sell/ATO/ATC orders
4. **Unique transaction IDs** - Each trade has a unique identifier
5. **Pagination support** - Can fetch large datasets with `page_size`
6. **Current session only** - Returns data for current/most recent trading day

## Limitations

- Data is for **current trading session only** (not historical intraday)
- Rate limiting may apply for frequent API calls
- Recommend adding delays between calls when processing multiple tickers

## Use Cases

- Real-time trade flow analysis
- Buy/sell pressure monitoring
- Large transaction detection
- Intraday volume analysis
- Order flow imbalance calculation

## Conclusion

Vnstock is **well-suited** for your needs if you want to analyze individual transactions within a trading session. The `quote.intraday()` function provides comprehensive tick-by-tick data with timestamps, prices, volumes, and trade direction.
