# Research: Vnstock Money Flow APIs

## Summary

Vnstock cung cấp 3 APIs chính cho Money Flow tab: `foreign_trade()`, `prop_trade()`, `order_stats()`. Tất cả APIs đều sử dụng VCI source (TCBS deprecated), trả về pandas DataFrame, yêu cầu date range format `YYYY-mm-dd`.

**Key findings:**
- `foreign_trade()`: 8 columns (net/buy/sell volume, value, ownership, remaining room)
- `prop_trade()`: 26 columns (buy/sell volume/value, match/deal trades, percentages) + resolution param
- `order_stats()`: 7 columns (orders count, volumes, avg volumes)
- No explicit rate limits documented - needs testing
- Caching recommended: data static sau trading hours (15:00)

## API Details

### 1. Foreign Trade API

**Function:** `trading.foreign_trade(start, end)`

**Parameters:**
- `start` (string, required): Start date `YYYY-mm-dd` (e.g., `2024-08-01`)
- `end` (string, required): End date `YYYY-mm-dd` (e.g., `2024-08-16`)

**Return Schema:**
```python
# 8 columns, datetime index
{
    'fr_net_volume': int64,      # Net foreign volume
    'fr_net_value': int64,        # Net foreign value (VND)
    'fr_buy_volume': int64,       # Foreign buy volume
    'fr_buy_value': int64,        # Foreign buy value (VND)
    'fr_sell_volume': int64,      # Foreign sell volume
    'fr_sell_value': int64,       # Foreign sell value (VND)
    'fr_remaining_room': int64,   # Remaining foreign room
    'fr_ownership': float64       # Foreign ownership %
}
```

**Sample Code:**
```python
from vnstock_data import Trading

trading = Trading(symbol='MSN', source='vci')
df = trading.foreign_trade(start='2024-08-01', end='2024-08-16')
# Returns DataFrame with time index
```

**Use Cases:**
- Track foreign investor net buy/sell activity
- Monitor foreign ownership limits
- Identify foreign buying/selling pressure

---

### 2. Proprietary Trade API

**Function:** `trading.prop_trade(start, end, resolution='1D')`

**Parameters:**
- `start` (string, required): Start date `YYYY-mm-dd`
- `end` (string, required): End date `YYYY-mm-dd`
- `resolution` (string, optional): `1D` (daily), `1W` (weekly), `1M` (monthly), `1Q` (quarterly), `1Y` (yearly). Default: `1D`

**Return Schema:**
```python
# 26 columns
{
    'trading_date': datetime64[ns],
    'total_buy_trade_volume': float64,
    'percent_buy_trade_volume': float64,
    'total_buy_trade_value': float64,
    'percent_buy_trade_value': float64,
    'total_sell_trade_volume': float64,
    'percent_sell_trade_volume': float64,
    'total_sell_trade_value': float64,
    'percent_sell_trade_value': float64,
    'total_trade_net_volume': float64,      # Key metric
    'total_trade_net_value': float64,       # Key metric
    'total_match_buy_trade_volume': float64,
    'total_match_buy_trade_value': float64,
    'total_match_sell_trade_volume': float64,
    'total_match_sell_trade_value': float64,
    'total_match_trade_net_volume': float64,
    'total_match_trade_net_value': float64,
    'total_deal_buy_trade_volume': float64,
    'total_deal_buy_trade_value': float64,
    'total_deal_sell_trade_volume': float64,
    'total_deal_sell_trade_value': float64,
    'total_deal_trade_net_volume': float64,
    'total_deal_trade_net_value': float64,
    'update_date': object,
    'total_volume': float64,
    'total_value': float64
}
```

**Sample Code:**
```python
trading = Trading(symbol='MSN', source='vci')
df = trading.prop_trade(start='2024-08-01', end='2024-08-16', resolution='1D')
# Returns detailed proprietary trading breakdown
```

**Use Cases:**
- Monitor proprietary trading (securities firms' own trading)
- Analyze matched vs deal transactions
- Calculate net proprietary positions

---

### 3. Order Stats API

**Function:** `trading.order_stats(start, end)`

**Parameters:**
- `start` (string, required): Start date `YYYY-mm-dd`
- `end` (string, required): End date `YYYY-mm-dd`

**Return Schema:**
```python
# 7 columns, datetime index
{
    'buy_orders': int64,              # Number of buy orders
    'sell_orders': int64,             # Number of sell orders
    'buy_volume': int64,              # Total buy volume
    'sell_volume': int64,             # Total sell volume
    'volume_diff': object,            # Volume difference (formatted string)
    'avg_buy_order_volume': float64,  # Avg buy order size
    'avg_sell_order_volume': int64    # Avg sell order size
}
```

**Sample Code:**
```python
trading = Trading(symbol='MSN', source='vci')
df = trading.order_stats(start='2024-08-01', end='2024-08-16')
# Returns order flow statistics
```

**Use Cases:**
- Analyze order flow imbalance
- Detect institutional vs retail activity (via avg order size)
- Monitor buying/selling pressure

---

## Implementation Notes

### Initialization
```python
from vnstock_data import Trading

# Initialize with VCI source (required)
trading = Trading(symbol='MSN', source='vci')
START_DATE = '2024-08-01'
END_DATE = '2024-08-16'
```

### Caching Strategy
**Recommended approach:**
- Cache data by date after market close (15:00 ICT)
- Use Redis/SQLite for daily data storage
- Cache key format: `{symbol}:{api}:{date}`
- TTL: Permanent for historical data, 5 min for current day

```python
import redis
from datetime import datetime

cache = redis.Redis()
cache_key = f"{symbol}:foreign_trade:{date}"
cached = cache.get(cache_key)

if cached:
    return pd.read_json(cached)
else:
    df = trading.foreign_trade(start=date, end=date)
    cache.setex(cache_key, 86400, df.to_json())  # 24h TTL
    return df
```

### Rate Limiting
**No official docs on rate limits - recommendations:**
- Conservative: 1 req/sec per API endpoint
- Batch requests: Use wider date ranges instead of multiple calls
- Retry logic: Exponential backoff (1s, 2s, 4s, 8s)
- Monitor: Track 429 errors, adjust limits accordingly

```python
import time
from functools import wraps

def rate_limit(calls=1, period=1):
    def decorator(func):
        last_called = [0.0]
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            wait = period - elapsed
            if wait > 0:
                time.sleep(wait)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator

@rate_limit(calls=1, period=1)
def fetch_foreign_trade(symbol, start, end):
    trading = Trading(symbol=symbol, source='vci')
    return trading.foreign_trade(start=start, end=end)
```

### Error Handling
```python
from requests.exceptions import HTTPError, Timeout

def safe_api_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited
                time.sleep(5)
                return func(*args, **kwargs)
            raise
        except Timeout:
            # Retry once
            return func(*args, **kwargs)
    return wrapper
```

### Data Validation
```python
def validate_date_range(start, end):
    """Validate date format and range"""
    from datetime import datetime

    try:
        start_dt = datetime.strptime(start, '%Y-%m-%d')
        end_dt = datetime.strptime(end, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Date format must be YYYY-mm-dd")

    if start_dt > end_dt:
        raise ValueError("Start date must be before end date")

    # Limit to 1 year max
    if (end_dt - start_dt).days > 365:
        raise ValueError("Date range must be <= 1 year")
```

## Unresolved Questions

1. **Rate Limits:** Vnstock docs không specify rate limits cho VCI source. Cần test để xác định:
   - Max requests/minute per API
   - Concurrent request limits
   - Rate limit error codes/messages

2. **Data Freshness:** Update frequency không rõ:
   - Real-time hay end-of-day?
   - Delay bao nhiêu sau market close?
   - Intraday updates cho current trading day?

3. **Resolution Parameter:** `prop_trade()` có `resolution` param nhưng `foreign_trade()` và `order_stats()` không:
   - Có thể aggregate foreign/order data weekly/monthly không?
   - Phải tự aggregate client-side?

4. **Historical Data Limits:**
   - Max historical range cho mỗi API?
   - Data availability cho stocks cũ?

5. **VCI Source Stability:**
   - VCI API uptime/SLA?
   - Fallback strategy nếu VCI down?
