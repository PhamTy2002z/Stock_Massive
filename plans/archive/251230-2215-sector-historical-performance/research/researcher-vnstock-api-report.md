# vnstock API Research Report: Sector Historical Performance

**Date:** 2025-12-30
**Focus:** Historical data API, rate limiting, ICB sector mapping
**Constraint:** VCI source only, ~100 stocks (VN100)

---

## 1. Historical Data API

### Basic Usage
```python
from vnstock import Vnstock

# Initialize with VCI source
stock = Vnstock().stock(symbol='ACB', source='VCI')

# Fetch historical OHLCV
df = stock.quote.history(
    start='2024-01-01',
    end='2025-03-19',
    interval='1D'  # Daily bars
)
```

### Alternative Approach (Quote class)
```python
from vnstock import Quote

quote = Quote(symbol='ACB', source='VCI')
df = quote.history(start='2024-01-01', end='2025-03-19', interval='1D')
```

### Key Parameters
- `symbol`: Stock ticker (e.g., 'ACB', 'VNM')
- `source`: **Must be 'VCI'** (TCBS discontinued)
- `start`/`end`: Date strings (format: 'YYYY-MM-DD')
- `interval`: '1D' for daily, supports intraday if needed

---

## 2. Rate Limiting Strategy

### VCI Source Limits (2025)
- **Community version**: ~60 requests/minute
- **Error handling**: `RateLimitExceed` or HTTP 429
- **Proactive warnings**: vnstock 3.x includes rate limit alerts

### Recommended Approach for 100 Stocks

**Option A: Sequential with delays**
```python
import time
from vnstock import Vnstock

def fetch_batch_history(symbols, start, end, delay=1.2):
    """Fetch with 1.2s delay = ~50 req/min (safe margin)"""
    results = {}
    for symbol in symbols:
        try:
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            results[symbol] = stock.quote.history(start, end, interval='1D')
            time.sleep(delay)  # Stay under 60/min limit
        except Exception as e:
            results[symbol] = None
            # Log error
    return results
```

**Option B: Batch with exponential backoff**
```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def fetch_with_retry(symbol, start, end):
    stock = Vnstock().stock(symbol=symbol, source='VCI')
    return stock.quote.history(start, end, interval='1D')
```

**Option C: Leverage existing Redis cache**
- Project already has Redis caching (trading-hours-aware)
- Cache historical data per stock/date range
- Only refetch on cache miss or daily update

### Estimated Time for 100 Stocks
- With 1.2s delay: ~2 minutes total
- With Redis cache hit ratio 80%: ~24 seconds (20 stocks only)

---

## 3. ICB Classification & Sector Mapping

### Get ICB Industry List
```python
from vnstock import Listing

listing = Listing()
icb_df = listing.industries_icb()
# Returns: ICB codes → Industry names mapping
```

### Get Stock Listings with ICB
```python
# Likely available via:
listing = Listing()
all_stocks = listing.all_symbols()  # May include ICB Level 2/3/4
# OR
all_stocks = listing.symbols_by_group('VN100')
```

### Sector Grouping Strategy
1. **Fetch ICB mapping** once at startup/daily
2. **Map each VN100 stock** to ICB Level 2 (sector)
3. **Group stocks** by sector for aggregation
4. **Calculate sector performance**:
   - Average % change (1W/2W/1M)
   - Median % change (reduce outlier impact)
   - Weighted by market cap (if available)

### Example ICB Levels
- **Level 1**: Industry (e.g., Financials, Technology)
- **Level 2**: Supersector (e.g., Banks, Software)
- **Level 3**: Sector
- **Level 4**: Subsector

**Recommendation**: Use ICB Level 2 for sector grouping (as per existing `/sector-performance` endpoint)

---

## 4. Implementation Recommendations

### Data Flow
1. **Daily Job** (APScheduler):
   - Fetch VN100 symbol list
   - Get ICB mapping for all symbols
   - Batch fetch historical data (1W/2W/1M ago → today)
   - Cache in Redis (24h TTL)

2. **API Endpoint** (`/sector-historical-performance`):
   - Read from Redis cache
   - Group by ICB Level 2
   - Calculate sector % changes
   - Return sorted by performance

### Database Schema (Optional)
```python
# If caching isn't sufficient, persist to DB:
class SectorHistoricalPerformance(Base):
    __tablename__ = 'sector_historical_performance'

    id = Column(Integer, primary_key=True)
    sector_name = Column(String)  # ICB Level 2
    period = Column(String)  # '1W', '2W', '1M'
    pct_change = Column(Float)
    date = Column(Date)
```

### Redis Key Strategy
```
sector_hist:1W:{sector_name}  # 1-week performance
sector_hist:2W:{sector_name}  # 2-week performance
sector_hist:1M:{sector_name}  # 1-month performance
```

---

## 5. Unresolved Questions

1. **VN100 symbol list source**: Does vnstock provide `listing.symbols_by_group('VN100')`? Or need manual list?
2. **ICB data freshness**: How often do ICB classifications change? Daily vs weekly update?
3. **Sponsorship needed?**: Will 60 req/min suffice for production? Or need sponsored tier (X10 = 600 req/min)?
4. **Historical data granularity**: Do we need intraday data, or daily bars sufficient for 1W/2W/1M calculations?
5. **Market cap weighting**: Should sector performance be market-cap weighted or equal-weighted average?

---

**Sources:**
- vnstock GitHub: github.com/thinh-vu/vnstock
- Context7 docs: /thinh-vu/vnstock (128 snippets)
- Project README: Redis cache, APScheduler, existing rate limiting (100/60s)
