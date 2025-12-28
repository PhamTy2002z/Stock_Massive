# Brainstorm Report: Overview Page UX Enhancement

**Date:** 2025-12-28
**Status:** Approved
**Author:** Solution Brainstormer Agent

---

## 1. Problem Statement

Traders lần đầu vào website cần cái nhìn **bao quát về thị trường** ngay lập tức. Current Overview page thiếu:
- Market breadth (số mã tăng/giảm)
- Top gainers/losers của ngày
- Foreign flow (NDNN mua/bán ròng)
- Top volume/value stocks

**Constraints:**
- Chỉ sử dụng nguồn VCI (TCBS đã ngưng)
- Phải xử lý rate limit VCI khi kéo data
- Target: Cả day trader + swing/position trader

---

## 2. Current State Analysis

### Existing Dashboard Components
| Component | Status | Data Source |
|-----------|--------|-------------|
| Market Indices | ✅ Done | VCI |
| VN30 Overview Table | ✅ Done | VCI |
| Sector Performance | ✅ Done | VCI |
| Fund Certificates | ✅ Done | Fmarket |

### Current Architecture
- **Cache:** Trading-hours-aware TTL (Upstash Redis)
- **Rate Limit:** 100 req/60s standard, 20 req/60s heavy
- **Refresh:** 10s auto-refresh

### Vnstock API Capabilities (VCI Source)
```python
# Available from vnstock library
top.gainer(index='VNINDEX', limit=10)   # Top tăng giá
top.loser(index='VNINDEX', limit=10)    # Top giảm giá
top.volume(index='VNINDEX', limit=10)   # Top khối lượng
top.value(index='VNINDEX', limit=10)    # Top giá trị
top.foreign_buy(date='YYYY-MM-DD')      # NDNN mua ròng
top.foreign_sell(date='YYYY-MM-DD')     # NDNN bán ròng
trading.foreign_trade(start, end)       # Thống kê NDNN
```

---

## 3. Evaluated Approaches

### Approach 1: Single Aggregate Endpoint ✅ SELECTED

**Description:** Tạo 1 API endpoint `/api/v1/stocks/market-overview` aggregate tất cả data

**Implementation:**
```python
# Backend aggregates all data in single cached response
{
  "market_breadth": { "advances": 150, "declines": 200, "unchanged": 50 },
  "top_gainers": [...5 items],
  "top_losers": [...5 items],
  "foreign_flow": {
    "net_buy": [...5 items],
    "net_sell": [...5 items],
    "total_net_value": 123_000_000_000
  },
  "top_volume": [...5 items]
}
```

| Pros | Cons |
|------|------|
| 1 API call → safe rate limit | Response size lớn hơn |
| Backend cache hiệu quả | Fetch all even if need partial |
| Frontend đơn giản | Single point of failure |
| Graceful fallback per section | |

### Approach 2: Separate Endpoints ❌ NOT RECOMMENDED

**Description:** 4 separate endpoints, frontend fetch parallel

| Pros | Cons |
|------|------|
| Granular caching | ⚠️ 4x API calls → rate limit risk |
| Lazy load possible | Complex error handling |
| | Multiple loading states |

### Approach 3: Hybrid Core + Lazy ❌ NOT SELECTED

**Description:** Core endpoint (breadth + top 3) + detail endpoint (full data on expand)

| Pros | Cons |
|------|------|
| Balanced approach | Over-engineering cho use case này |
| Fast initial load | 2 endpoints to maintain |

---

## 4. Final Recommended Solution

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js)                  │
│  ┌─────────────────────────────────────────────────┐    │
│  │ useMarketOverview() hook                        │    │
│  │   - Single API call                             │    │
│  │   - 10s refetch interval                        │    │
│  │   - Suspense boundary per section               │    │
│  └─────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────┘
                            │ GET /api/v1/stocks/market-overview
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                   │
│  ┌─────────────────────────────────────────────────┐    │
│  │ MarketOverviewService                           │    │
│  │   - Calls vnstock functions sequentially        │    │
│  │   - 100ms delay between VCI calls               │    │
│  │   - Aggregates into single response             │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │ TradingHoursCache                               │    │
│  │   - TTL: 10s trading hours, 5min off-hours      │    │
│  │   - Key: "market_overview:aggregate"            │    │
│  └─────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────┘
                            │ Sequential calls with delay
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     VNSTOCK (VCI)                       │
│  top.gainer() → top.loser() → top.foreign_buy() → ...  │
│  (100ms delay between each call)                        │
└─────────────────────────────────────────────────────────┘
```

### UI Layout (Collapsible Grid)

```
┌─────────────────────────────────────────────────────────┐
│ [Market Indices - 4 cards] (existing, unchanged)        │
├─────────────────────────────────────────────────────────┤
│ [▼ Market Breadth] ─────────────────────────────────────│
│   🟢 Tăng: 150 (37.5%)  │  🔴 Giảm: 200 (50%)  │  ⚪ 50  │
│   ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
├─────────────────────────────────────────────────────────┤
│ [▼ Top Movers]                    [▼ Foreign Flow]      │
│ ┌────────────────────────┐  ┌────────────────────────┐  │
│ │ 🟢 Top Tăng │ 🔴 Top Giảm│  │ Net: +123.5 tỷ        │  │
│ │ VNM  +6.9% │ VHM -6.5%  │  │ ───────────────────── │  │
│ │ FPT  +4.2% │ MSN -5.1%  │  │ 🟢 Mua ròng │ 🔴 Bán  │  │
│ │ HPG  +3.8% │ VIC -4.8%  │  │ MWG 101.5B│VHM -50B   │  │
│ │ TCB  +3.5% │ VPB -4.2%  │  │ CTG  67.0B│MSN -35B   │  │
│ │ VCB  +2.9% │ STB -3.9%  │  │ DIG  67.0B│VND -30B   │  │
│ └────────────────────────┘  └────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│ [▼ Top Volume/Value] (optional, có thể dùng VN30 table) │
├─────────────────────────────────────────────────────────┤
│ [VN30 Overview Table] (existing, unchanged)             │
├─────────────────────────────────────────────────────────┤
│ [Sector Performance] + [Fund Certificates] (existing)   │
└─────────────────────────────────────────────────────────┘
```

### Collapsible Behavior
- Each section có toggle button (▼/▶)
- Collapsed state persist vào localStorage
- Keyboard shortcuts: `1-5` toggle từng section
- Default: All expanded

---

## 5. Implementation Considerations

### Backend Tasks
1. Create `/stocks/overview/` feature module
2. Create `MarketOverviewService` with VCI integration
3. Add `market-overview` cache instance
4. Add endpoint với standard rate limit

### Frontend Tasks
1. Create `useMarketOverview` hook
2. Create components:
   - `MarketBreadth` - stacked bar chart
   - `TopMovers` - dual column table
   - `ForeignFlowWidget` - net value + top lists
3. Create `CollapsibleSection` wrapper
4. Update `page.tsx` layout

### Rate Limit Strategy
```python
# Backend delays between VCI calls
async def fetch_market_overview():
    gainers = await vnstock.top.gainer(limit=5)
    await asyncio.sleep(0.1)  # 100ms delay

    losers = await vnstock.top.loser(limit=5)
    await asyncio.sleep(0.1)

    foreign_buy = await vnstock.top.foreign_buy(date=today)
    await asyncio.sleep(0.1)

    foreign_sell = await vnstock.top.foreign_sell(date=today)
    # ... aggregate and return
```

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| VCI rate limit exceeded | API fails | Backend delay + aggressive caching |
| VCI service down | No data | Graceful degradation per section |
| Large response size | Slow load | Gzip compression (already enabled) |
| Stale data during trading | Bad UX | 10s cache TTL during trading hours |

---

## 7. Success Metrics

| Metric | Target |
|--------|--------|
| Initial load time | < 2s |
| API response time | < 500ms (cached) |
| Rate limit errors | 0% |
| User session duration | +20% (measure via analytics) |

---

## 8. Next Steps

1. [ ] Create implementation plan với `/plan` command
2. [ ] Backend: Feature module + service + endpoint
3. [ ] Frontend: Components + hook + layout update
4. [ ] Testing: Unit + integration + E2E
5. [ ] Deploy và monitor

---

## Unresolved Questions

None at this time. All requirements clarified through brainstorming session.
