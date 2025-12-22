# Brainstorm Report: Volume Spike Dashboard by Industry

**Date:** 2024-12-22
**Type:** Feasibility Analysis
**Feature:** Dashboard hiển thị cổ phiếu có khối lượng giao dịch đột biến, phân nhóm theo ngành

---

## 1. Problem Statement

User muốn implement Dashboard trong tab "Deep Dive" (dưới "Stock Details") hiển thị:
- Các cổ phiếu có **khối lượng giao dịch đột biến** trong phiên gần nhất
- **Phân nhóm theo ngành** (ICB classification)
- Sử dụng **VCI source** (TCBS đã ngưng dịch vụ)
- Chú ý **rate limit** khi kéo dữ liệu

---

## 2. Vnstock API Analysis (VCI Source)

### 2.1 Available APIs for Volume Spike Detection

| API | Function | Data Returned |
|-----|----------|---------------|
| `top.volume(index, limit)` | Top stocks by volume | `volume_spike_20d_pct`, `deal_volume_spike_20d_pct` |
| `top.value(index, limit)` | Top stocks by value | Similar metrics |
| `listing.symbols_by_industries()` | All symbols with ICB codes | `icb_code1-4`, `icb_name2-4` |
| `trading.price_board(symbols)` | Real-time price/volume | `accumulated_volume`, `match_price` |
| `quote.history(symbol)` | Historical OHLCV | `volume`, `close` |

### 2.2 Key Metrics from `top.volume()`

```
- volume_spike_20d_pct: % spike vs 20-day avg
- deal_volume_spike_20d_pct: Deal volume spike %
- deal_volume_spike_5d_20d_pct: 5d vs 20d comparison
- avg_volume_20d: 20-day average volume
```

### 2.3 ICB Industry Classification

- **Level 2** (`icb_name2`): 10 sectors (Ngân hàng, Bất động sản, etc.)
- **Level 3** (`icb_name3`): 40+ sub-sectors
- **Level 4** (`icb_name4`): 150+ detailed industries

---

## 3. Existing Codebase Assets

### 3.1 Backend (Already Implemented)

| Component | Location | Reusable? |
|-----------|----------|-----------|
| `PriceService` | `apps/api/src/stocks/price/service.py` | ✅ VCI source configured |
| `MarketService.get_sector_performance()` | `apps/api/src/stocks/market/service.py` | ✅ ICB grouping logic |
| Volume anomaly detection | `apps/api/src/stocks/price/router.py:170` | ✅ Per-symbol anomaly |
| Rate limiting | `src/core/ratelimit.py` | ✅ 100/60s standard, 20/60s heavy |
| Redis caching | `src/core/cache.py` | ✅ Trading-hours-aware TTL |

### 3.2 Frontend (Already Implemented)

| Component | Location | Reusable? |
|-----------|----------|-----------|
| `VolumeAnomalyChart` | `apps/web/src/components/dashboard/volume-anomaly-chart.tsx` | ✅ Recharts-based |
| Deep Dive page | `apps/web/src/app/analytics/deep-dive/page.tsx` | ✅ Target location |
| `StockDetailClient` | `apps/web/src/components/dashboard/stock-detail-client.tsx` | ✅ Tab system |

---

## 4. Proposed Approaches

### Approach A: Extend `top.volume()` API (Recommended)

**Concept:** Use vnstock's built-in `top.volume()` which already calculates volume spikes, then group by ICB.

**Pros:**
- Vnstock pre-calculates `volume_spike_20d_pct` - no custom logic needed
- Single API call for all stocks in an index
- Built-in spike detection algorithm

**Cons:**
- Limited to index members (VNINDEX, HNX, VN30)
- May not cover all 1500+ stocks

**Implementation:**
1. Backend: New endpoint `/api/v1/stocks/analytics/volume-spikes-by-industry`
2. Call `top.volume(index='VNINDEX', limit=100)` + `top.volume(index='HNX', limit=50)`
3. Merge with `listing.symbols_by_industries()` for ICB data
4. Group by `icb_name2` (Level 2 sectors)
5. Cache result (TTL: 5min trading, 1hr off-hours)

---

### Approach B: Custom Volume Spike Calculation

**Concept:** Fetch historical data for all symbols, calculate spike ratio manually.

**Pros:**
- Full control over spike threshold
- Cover all 1500+ stocks

**Cons:**
- **Rate limit risk**: 1500 API calls × 2s delay = 50 minutes
- High latency, complex batch processing
- Redundant - vnstock already does this

**Not recommended** due to rate limit constraints.

---

### Approach C: Hybrid - Scheduled Job + Real-time Top

**Concept:** Background job collects daily volume data, real-time endpoint filters spikes.

**Pros:**
- Pre-computed data, fast queries
- Full market coverage

**Cons:**
- Requires database schema changes
- More complex infrastructure

**Viable for Phase 2** if Approach A insufficient.

---

## 5. Recommended Solution: Approach A

### 5.1 Backend Implementation

```python
# New endpoint: GET /api/v1/stocks/analytics/volume-spikes-by-industry
# Parameters: threshold (default 1.5), limit (default 50)

async def get_volume_spikes_by_industry(
    threshold: float = 1.5,  # 150% of 20d avg
    limit: int = 50,
):
    # 1. Fetch top volume stocks from VCI
    top_hose = top.volume(index='VNINDEX', limit=100)
    top_hnx = top.volume(index='HNX', limit=50)

    # 2. Filter by spike threshold
    spikes = df[df['volume_spike_20d_pct'] >= threshold]

    # 3. Merge with ICB classification
    industries = listing.symbols_by_industries()
    merged = spikes.merge(industries, on='symbol')

    # 4. Group by icb_name2 (Level 2)
    grouped = merged.groupby('icb_name2')

    return {
        "sectors": [
            {
                "icb_name": "Ngân hàng",
                "icb_code": "8300",
                "stocks": [
                    {"symbol": "VCB", "spike_pct": 2.5, "volume": 5000000},
                    ...
                ]
            },
            ...
        ],
        "generated_at": "2024-12-22T15:30:00",
        "threshold": 1.5
    }
```

### 5.2 Frontend Implementation

```
Deep Dive Page
└── VolumeSpikesDashboard (new component)
    ├── SectorAccordion (collapsible by industry)
    │   ├── SectorHeader (icb_name, stock count, avg spike)
    │   └── StockSpikeTable (symbol, spike%, volume, price change)
    └── VolumeSpikeChart (bar chart by sector)
```

### 5.3 Rate Limit Strategy

| Operation | Calls | Rate | Strategy |
|-----------|-------|------|----------|
| `top.volume()` | 2 (VNINDEX + HNX) | Standard | Parallel calls OK |
| `symbols_by_industries()` | 1 | Standard | Cache 24hr |
| Total per request | 3 | Within 100/60s | ✅ Safe |

### 5.4 Caching Strategy

| Data | TTL (Trading) | TTL (Off-hours) |
|------|---------------|-----------------|
| Volume spikes | 5 minutes | 1 hour |
| ICB classification | 24 hours | 24 hours |

---

## 6. UI/UX Recommendations

### 6.1 Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│ Volume Spikes by Industry          [Threshold: 1.5x ▼] │
│ Phiên 22/12/2024 • 45 cổ phiếu đột biến               │
├─────────────────────────────────────────────────────────┤
│ ▼ Ngân hàng (8 stocks)                    Avg: +2.3x   │
│   ┌─────┬──────────┬──────────┬──────────┐            │
│   │ VCB │ +2.5x    │ 5.2M     │ +1.2%    │            │
│   │ TCB │ +2.1x    │ 3.8M     │ +0.8%    │            │
│   └─────┴──────────┴──────────┴──────────┘            │
│                                                         │
│ ▶ Bất động sản (12 stocks)                Avg: +1.8x   │
│ ▶ Chứng khoán (5 stocks)                  Avg: +3.1x   │
└─────────────────────────────────────────────────────────┘
```

### 6.2 Chart Options

1. **Bar Chart by Sector**: Horizontal bars showing avg spike per sector
2. **Heatmap**: Sectors × Time showing spike intensity
3. **Treemap**: Sector size = stock count, color = avg spike

---

## 7. Implementation Steps

### Phase 1: Core Feature

1. **Backend**
   - [ ] Create `VolumeSpikeService` in `apps/api/src/stocks/analytics/`
   - [ ] Add endpoint `GET /analytics/volume-spikes-by-industry`
   - [ ] Implement caching with `TradingHoursCache`
   - [ ] Add Pydantic schemas for response

2. **Frontend**
   - [ ] Create `VolumeSpikesDashboard` component
   - [ ] Create `SectorAccordion` with collapsible sections
   - [ ] Create `StockSpikeTable` for stock list
   - [ ] Adve page as new section/tab
   - [ ] Implement TanStack Query for data fetching

### Phase 2: Enhancements (Optional)

- [ ] Add threshold selector (1.5x, 2x, 3x)
- [ ] Add sector filter dropdown
- [ ] Add historical comparison (vs yesterday)
- [ ] Add click-to-detail navigation

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VCI rate limit hit | Low | High | Cache aggressively, batch requests |
| VCI API changes | Low | Medium | Abstract vnstock calls in service layer |
| Slow response time | Medium | Medium | Pre-compute during off-hours |
| Missing ICB data | Low | Low | Fallback to "Khác" category |

---

## 9. Success Metrics

- Response time < 2s (cached), < 5s (fresh)
- Cover 80%+ of actively traded stocks
- UI renders within 500ms
- Zero rate limit errors in production

---

## 10. Conclusion

**Feasibility: HIGH** ✅

The feature is highly feasible because:
1. Vnstock's `top.volume()` already provides volume spike metrics
2. ICB classification data is readily available
3. Existing codebase has reusable components (caching, rate limiting, charts)
4. Rate limit risk is minimal with proper caching

**Recommended Approach:** Approach A (Extend `top.volume()` API)

**Estimated Complexity:** Medium
- Backend: ~200 LOC
- Frontend: ~400 LOC
- Testing: ~100 LOC

---

## Unresolved Questions

1. Should we include UPCOM stocks? (Lower liquidity, more noise)
2. Preferred ICB level for grouping? (Level 2 recommended, Level 3 optional)
3. Default spike threshold? (1.5x suggested, user-configurable)
4. Should clicking a stock navigate to its detail page or show inline modal?
