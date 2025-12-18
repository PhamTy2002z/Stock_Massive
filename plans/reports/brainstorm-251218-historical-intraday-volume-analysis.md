# Historical Intraday Volume Analysis - Vnstock Research

**Date:** 2024-12-18
**Topic:** Retrieve 10 days historical intraday data to analyze peak volume time periods

---

## Key Finding

Vnstock `quote.history()` **supports minute-level intervals** for historical data:

```
Supported intervals: 1m, 5m, 15m, 1H, 1D, 1W, 1M
```

This means you **CAN** retrieve historical intraday data for the past 10 days directly!

---

## Solution: Use `quote.history()` with Minute Intervals

### Code Example

```python
from vnstock import Vnstock
import pandas as pd

# Initialize
stock = Vnstock().stock(symbol='VNM', source='VCI')

# Get 10 days of 15-minute data
df = stock.quote.history(
    start='2025-12-08',
    end='2025-12-18',
    interval='15m'  # Options: 1m, 5m, 15m, 1H
)

# Filter trading hours only (9:00 - 15:00)
df['time'] = pd.to_datetime(df['time'])
df = df[(df['time'].dt.hour >= 9) & (df['time'].dt.hour < 15)]

# Extract time components
df['hour'] = df['time'].dt.hour
df['minute'] = df['time'].dt.minute
df['time_slot'] = df['time'].dt.strftime('%H:%M')

# Aggregate volume by time slot across all days
volume_by_slot = df.groupby('time_slot')['volume'].sum().sort_values(ascending=False)

print("Top 10 highest volume time slots:")
print(volume_by_slot.head(10))
```

### Expected Output

```
time_slot
09:15    12,500,000   # ATO period - typically highest
14:30     8,200,000   # Near close
14:45     7,800,000   # ATC period
09:30     5,100,000   # Morning active
11:30     4,200,000   # Before lunch break
...
```

---

## Interval Selection Guide

| Interval | Use Case | Data Points (10 days) |
|----------|----------|----------------------|
| `1m` | Precise analysis, scalping patterns | ~3,600 rows |
| `5m` | Balanced granularity | ~720 rows |
| `15m` | General trend analysis | ~240 rows |
| `1H` | Broad session patterns | ~60 rows |

**Recommendation:** Start with `15m` for initial analysis, then drill down to `5m` or `1m` if needed.

---

## Important Notes

1. **Data availability** - Minute-level data may have time range limitations (verify with VCI source)
2. **Trading hours** - Vietnam market: 9:00-11:30 (morning), 13:00-15:00 (afternoon)
3. **ATO/ATC periods** - 9:00-9:15 (opening) and 14:30-14:45 (closing) typically have highest volume

---

## Alternative: Tick-Level Data (If Needed)

If minute intervals aren't granular enough, use `quote.intraday()` but note:
- Only returns **current session** data
- Must build your own database by collecting daily

```python
# Daily collection job (run at 15:30)
quote.intraday(page_size=10_000)  # Save to parquet/DB
```

---

## Recommended Approach

| Priority | Action |
|----------|--------|
| 1 | Use `quote.history(interval='15m')` for immediate 10-day analysis |
| 2 | If more granularity needed, try `interval='5m'` or `interval='1m'` |
| 3 | Only build intraday collection pipeline if tick-level precision required |

---

## Conclusion

**You can achieve your goal immediately** using Vnstock's `quote.history()` with minute-level intervals. No need to build a data collection pipeline unless you specifically need tick-by-tick transaction data.
