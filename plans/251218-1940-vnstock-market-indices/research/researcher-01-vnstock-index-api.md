# Vnstock Index API Research

## Summary
Vnstock library supports fetching market index data (VNINDEX, VN30, HNXINDEX, UPCOMINDEX) using the same `Quote` class used for stocks.

## Key Findings

### 1. Index Data Retrieval
```python
from vnstock import Quote

# Initialize Quote for index (same as stock)
quote = Quote(symbol='VNINDEX', source='VCI')

# Get historical OHLCV data
df = quote.history(start='2024-01-01', end='2024-12-31', interval='1D')
```

**Supported Indices:**
- `VNINDEX` - VN-Index (HOSE main index)
- `VN30` - VN30 Index (top 30 HOSE stocks)
- `HNXINDEX` - HNX Index
- `UPCOMINDEX` - UPCOM Index
- `VN30F1M` - VN30 Futures (1 month)

### 2. Data Structure Returned
```
time      open      high      low       close     volume
2024-01-02  1234.56   1240.00   1230.00   1238.45   123456789
```

### 3. Current vs Historical Data
- `quote.history()` - Historical OHLCV data
- For real-time/current price: Use latest record from history or price_board

### 4. Calculating Change Values
From historical data, calculate:
- `change = close_today - close_yesterday`
- `changePercent = (change / close_yesterday) * 100`
- `chartData = [close prices for last N days]`

## API Design Recommendation

### New Endpoint: `/api/v1/indices`
```
GET /api/v1/indices
Response: [
  {
    symbol: "VNINDEX",
    name: "VN-INDEX",
    value: 1284.23,
    change: 12.45,
    changePercent: 0.98,
    chartData: [1270, 1275, 1268, ...]
  }
]
```

### Implementation Notes
1. Use `Quote(symbol='VNINDEX')` for each index
2. Fetch last 10-20 days of history for sparkline
3. Calculate change from last 2 trading days
4. Cache results (indices don't change frequently during session)

## References
- Context7: /thinh-vu/vnstock - Quote class for indices
- Context7: /websites/vnstocks - Market statistics API
