# Brainstorming: Overview Page Feature Implementation

**Date:** 2025-12-22
**Context:** Evaluate feasible features for Overview page using Vnstock API

---

## Current State Analysis

### Existing Overview Page Components
| Component | Status | Data Source |
|-----------|--------|-------------|
| Market Indices (VN-INDEX, VN30, HNX, UPCOM) | Done | `/market-indices` |
| VN30 Overview Table | Done | `/vn30-overview` |
| Sector Performance (ICB Level 2) | Done | `/sector-performance` |
| Fund Certificates | Done | `/fund-certificates` |

### Rate Limiting Constraints
| Tier | Limit | Window | Use Case |
|------|-------|--------|----------|
| Standard | 100 req | 60s | Most endpoints |
| Heavy | 20 req | 60s | Expensive operations (intraday, volume-analysis) |

### Auto-refresh: 10s interval for Market Indices

---

## Vnstock API Capabilities (Feasible for Overview)

### 1. Top Stocks Statistics (`top.*` functions)
- `top.gainer(index, limit)` - Top gaining stocks
- `top.loser(index, limit)` - Top losing stocks
- `top.volume(index, limit)` - Top by volume
- `top.value(index, limit)` - Top by trading value
- `top.deal(index, limit)` - Top deals
- `top.foreign_buy(date)` - Foreign net buyers
- `top.foreign_sell(date)` - Foreign net sellers

### 2. Price Board Data (`trading.price_board`)
- Real-time price for multiple symbols
- 61 columns including bid/ask, foreign activity
- Suitable for watchlist/heatmap

### 3. Foreign Trading (`trading.foreign_trade`)
- Daily foreign net volume/value
- Ownership percentages
- Historical foreign flow

---

## Recommended Features (Prioritized)

### Tier 1: High Value, Low API Cost

#### 1. Top Movers Section (Gainers/Losers)
**API:** `top.gainer()`, `top.loser()`
**Cost:** 2 requests per refresh
**Value:** High - shows market momentum at a glance

```
Layout: 2-column grid
- Left: Top 5 Gainers (green cards)
- Right: Top 5 Losers (red cards)
Each card: Symbol, Price, Change%, Volume
```

**Refresh:** On page load + manual refresh button (no auto-refresh to save quota)

#### 2. Foreign Flow Summary
**API:** `top.foreign_buy()`, `top.foreign_sell()`
**Cost:** 2 requests per refresh
**Value:** High - institutional sentiment indicator

```
Layout: Compact horizontal bar
- Net Foreign Buy/Sell value
- Top 3 foreign bought symbols
- Top 3 foreign sold symbols
```

**Refresh:** Daily data, cache for 5-10 minutes

#### 3. Top Volume Leaders
**API:** `top.volume()` or `top.value()`
**Cost:** 1 request per refresh
**Value:** Medium-High - shows where action is

```
Layout: Horizontal scrollable cards or compact table
- Top 10 by trading value
- Symbol, Price, Change%, Volume
```

---

### Tier 2: Medium Value, Moderate Cost

#### 4. Market Heatmap (VN30)
**API:** Already have `/vn30-overview` data
**Cost:** 0 additional requests (reuse existing)
**Value:** High - visual market snapshot

```
Layout: Treemap/grid visualization
- Size by market cap
- Color by price change %
- Clickable to stock detail
```

**Implementation:** Transform existing VN30 data into heatmap visualization

#### 5. Market Breadth Indicator
**API:** Derive from existing sector/VN30 data
**Cost:** 0 additional requests
**Value:** Medium - market health indicator

```
Layout: Horizontal bar
- Advances vs Declines ratio
- Unchanged count
- Simple visual indicator
```

---

### Tier 3: Lower Priority (Future)

#### 6. Intraday Market Summary
**API:** Intraday endpoints (heavy rate limit)
**Cost:** High - uses heavy quota
**Value:** Medium - real-time tick data
**Recommendation:** Defer, not suitable for Overview page auto-refresh

#### 7. Volume Anomaly Alerts
**API:** `/volume-anomalies`
**Cost:** Heavy endpoint
**Value:** Medium-High but better on dedicated page
**Recommendation:** Keep on Stock Detail page only

---

## Feasibility Matrix

| Feature | API Cost | Dev Effort | User Value | Recommend |
|---------|----------|------------|------------|-----------|
| Top Movers (Gainers/Losers) | Low (2 req) | Low | High | **Yes** |
| Foreign Flow Summary | Low (2 req) | Low | High | **Yes** |
| Top Volume Leaders | Low (1 req) | Low | Medium | **Yes** |
| Market Heatmap | Zero | Medium | High | **Yes** |
| Market Breadth | Zero | Low | Medium | **Yes** |
| Intraday Summary | High | High | Medium | No |
| Volume Anomaly | High | Low | Medium | No |

---

## Recommended Implementation Order

### Phase 1 (Immediate - Low Risk)
1. **Market Heatmap** - Zero additional API cost, high visual impact
2. **Market Breadth** - Zero additional API cost, quick win

### Phase 2 (Short-term - New Endpoints)
3. **Top Movers** - Requires new backend endpoint
4. **Foreign Flow** - Requires new backend endpoint

### Phase 3 (Optional Enhancement)
5. **Top Volume Leaders** - Nice to have

---

## Backend Endpoints Needed

```python
# New endpoints to add
GET /api/v1/stocks/top-movers?index=VNINDEX&limit=5
  # Returns: { gainers: [...], losers: [...] }

GET /api/v1/stocks/foreign-flow?date={today}
  # Returns: { net_value, top_buys: [...], top_sells: [...] }

GET /api/v1/stocks/top-volume?index=VNINDEX&limit=10
  # Returns: [{ symbol, price, change, volume, value }]
```

---

## Rate Limit Budget Analysis

**Current Usage (per minute per user):**
- Market Indices: 6 req (10s auto-refresh)
- Sector Performance: 1 req (on load)
- VN30 Overview: 1 req (on load)
- Fund Certificates: 1 req (on load)
- **Total:** ~9 req/min

**With New Features (conservative):**
- Top Movers: 2 req (on load only)
- Foreign Flow: 2 req (5-min cache)
- Top Volume: 1 req (on load only)
- **Additional:** ~5 req/min

**Total:** ~14 req/min - Well within 100/60s limit

---

## Final Recommendations

### Must Implement
1. **Market Heatmap** - Transform VN30 data into visual treemap
2. **Top Movers Section** - Gainers/Losers side by side
3. **Foreign Flow Summary** - Net foreign sentiment

### Nice to Have
4. Market Breadth indicator
5. Top Volume Leaders

### Avoid for Overview
- Intraday data (heavy quota)
- Volume anomalies (better on stock detail)
- Real-time price board for many symbols

---

## Open Questions

1. Should Top Movers show VN30 only or full VNINDEX? (VN30 reduces noise)
2. Preferred heatmap library? (Recharts treemap vs custom SVG)
3. Should Foreign Flow include historical trend line?

---

## Next Steps

1. Confirm feature priority with stakeholder
2. Create implementation plan for Phase 1 (Heatmap)
3. Design API endpoints for Phase 2
