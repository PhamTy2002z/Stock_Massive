# Brainstorm: Sector Performance Tab Feature

**Date:** 2025-12-19
**Topic:** Triển khai tab hiển thị ngành tăng/giảm mạnh trong phiên

---

## 1. Problem Statement

Cần triển khai một tab mới hiển thị:
- Các ngành đang tăng mạnh trong phiên
- Các ngành đang giảm mạnh trong phiên

---

## 2. Vnstock API Analysis

### 2.1 Available APIs (Direct Support)

| API | Function | Description |
|-----|----------|-------------|
| `top.gainer()` | Top cổ phiếu tăng | index: VNINDEX/HNX/VN30, limit |
| `top.loser()` | Top cổ phiếu giảm | index: VNINDEX/HNX/VN30, limit |
| `top.volume()` | Top khối lượng | index: VNINDEX/HNX/VN30, limit |
| `top.value()` | Top giá trị | index: VNINDEX/HNX/VN30, limit |
| `top.deal()` | Top giao dịch thỏa thuận | index: VNINDEX/HNX/VN30, limit |
| `listing.symbols_by_industries()` | Danh sách mã theo ngành ICB | 14 columns: symbol, icb_name2/3/4, icb_code1/2/3/4 |
| `listing.industries_icb()` | Danh sách ngành ICB | Mapping ICB code → name |
| `company.overview()` | Thông tin công ty | Có field `industry`, `industry_id` |
| `Trading().price_board()` | Bảng giá realtime | Multiple symbols |

### 2.2 Key Finding: NO Direct Sector/Industry Performance API

**Vnstock KHÔNG có API trực tiếp cho sector performance.** Không có endpoint như:
- `sector.performance()`
- `industry.top_gainers()`
- `sector.realtime()`

---

## 3. Feasibility Assessment

### 3.1 Approach: Tự tính toán Sector Performance

**KHẢ THI** - Cần tự aggregate từ stock-level data.

#### Data Flow:
```
1. listing.symbols_by_industries() → Get all symbols + ICB codes
2. Trading().price_board(symbols) → Get realtime prices (price_change_pct)
3. Aggregate by ICB sector → Calculate sector avg performance
4. Sort & display top gainers/losers
```

### 3.2 Implementation Options

| Option | Pros | Cons |
|--------|------|------|
| **A. Full calculation** | Accurate, all stocks | Slow (1500+ symbols), API rate limit |
| **B. Sample-based** | Fast, representative | Less accurate |
| **C. VN30/VN100 only** | Fast, liquid stocks | Miss small caps |
| **D. Pre-computed (backend)** | Fast frontend | Need scheduler, storage |

**Recommended: Option D** - Backend pre-compute với scheduler

---

## 4. Proposed Solution

### 4.1 Architecture

```
[Scheduler: 5-min interval]
       ↓
[Backend Service]
  1. Fetch price_board for all symbols (batched)
  2. Join with industry mapping
  3. Calculate sector avg: SUM(price_change_pct * market_cap) / SUM(market_cap)
  4. Store in cache/DB
       ↓
[API Endpoint: /api/v1/stocks/sector-performance]
       ↓
[Frontend Tab: Sector Heatmap/Table]
```

### 4.2 Backend Implementation

```python
# New endpoint: GET /api/v1/stocks/sector-performance
# Response:
{
  "timestamp": "2025-12-19T14:30:00",
  "top_gainers": [
    {"sector": "Ngân hàng", "icb_code": "8355", "change_pct": 2.5, "stock_count": 27},
    {"sector": "Bất động sản", "icb_code": "8633", "change_pct": 1.8, "stock_count": 45}
  ],
  "top_losers": [
    {"sector": "Dầu khí", "icb_code": "0533", "change_pct": -1.2, "stock_count": 12}
  ]
}
```

### 4.3 Frontend Component

- Tab trong Dashboard hoặc Market Overview
- Display options: Table, Heatmap, Bar chart
- Auto-refresh: 5 minutes
- Click sector → drill down to stocks in sector

---

## 5. Implementation Steps

1. **Backend: Industry mapping service**
   - Cache `symbols_by_industries()` data
   - Build symbol → sector lookup

2. **Backend: Sector performance calculator**
   - Batch fetch price_board (chunks of 50-100 symbols)
   - Calculate weighted avg by market cap
   - Handle missing data gracefully

3. **Backend: New API endpoint**
   - `/api/v1/stocks/sector-performance`
   - Query params: `limit`, `sort_by`

4. **Backend: Scheduler job**
   - Run every 5 minutes during trading hours
   - Store results in Redis/memory cache

5. **Frontend: Sector Performance Tab**
   - New component in dashboard
   - Table with sorting
   - Optional: Treemap/Heatmap visualization

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limiting | Data gaps | Batch requests, caching |
| Slow calculation | Poor UX | Pre-compute, cache |
| Market hours only | Stale data | Show "last updated" timestamp |
| ICB mapping changes | Wrong grouping | Refresh mapping daily |

---

## 7. Conclusion

**FEASIBLE** với approach tự tính toán từ stock-level data.

### Summary:
- Vnstock không có direct sector performance API
- Cần build custom aggregation logic
- Recommend: Backend pre-compute + cache + scheduler
- Complexity: Medium
- Effort: ~2-3 days implementation

### Next Steps:
1. Confirm approach với user
2. Implement backend service
3. Add API endpoint
4. Build frontend tab

---

## Unresolved Questions

1. ICB level nào? (Level 2: 10 sectors, Level 3: ~40 subsectors, Level 4: ~100+ industries)
2. Weighting method? (Equal weight vs Market cap weighted)
3. Refresh interval? (1 min, 5 min, realtime websocket?)
4. Visualization preference? (Table, Heatmap, Both?)
