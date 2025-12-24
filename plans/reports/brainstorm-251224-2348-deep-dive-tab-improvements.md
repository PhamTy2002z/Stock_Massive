# Brainstorm: Deep Dive Tab Improvements

**Date**: 2024-12-24
**Status**: ✅ DECISIONS FINALIZED
**Context**: Phân tích và đề xuất cải thiện tab "Deep Dive" dựa trên Vnstock docs (VCI source only)

---

## 🎯 CONFIRMED DECISIONS

| Category | Decision |
|----------|----------|
| **Tab "Dòng Tiền"** | Gộp Foreign + Prop Trading trong 1 tab |
| **Tab "Tin Tức"** | Full (News + Dividends + Insider Deals) |
| **Mobile Tabs** | Dropdown overflow (4 visible + More) |
| **Data Depth** | 30 days |
| **Sticky Elements** | Quick Stats Bar + Tabs Bar |
| **Fetch Pattern** | Lazy Load on tab switch |

### Final Layout
```
┌─────────────────────────────────────────────────────────────┐
│ [Quick Stats Bar] ← STICKY                                  │
│ VCB | 92,500 ▲+2.5% | Vol: 8.2M | Ngoại: +1.2M | P/E: 12.5 │
├─────────────────────────────────────────────────────────────┤
│ [Tabs Bar] ← STICKY                                         │
│ Desktop: Overview | Finance | Cổ Đông | Volume | Dòng Tiền | Tin Tức │
│ Mobile:  Overview | Finance | Cổ Đông | Volume | [More ▼]  │
├─────────────────────────────────────────────────────────────┤
│ [Tab Content - Lazy Load]       │ [Sidebar]                │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Problem Statement

Tab "Deep Dive" (`/analytics/deep-dive`) là trang phân tích chuyên sâu cho từng mã cổ phiếu. Cần đánh giá:
- Tính năng nào có thể thêm từ Vnstock API (VCI source)
- UI/UX có thể cải thiện
- Rate limit considerations khi thêm API calls

---

## 2. Current State Analysis

### 2.1 Existing Tabs (4 tabs)

| Tab | Content | API Used |
|-----|---------|----------|
| **Tổng Quan** | Ticker header, price stats, 52-week range, P/E, P/B, EPS | `/{symbol}/detail` |
| **Tài Chính** | Financial statements, ratios | `/{symbol}/financials/*` |
| **Cổ Đông** | Major shareholders, officers | `/{symbol}/shareholders`, `/{symbol}/officers` |
| **Khối Lượng** | Volume analysis, patterns | `/{symbol}/volume-analysis` |

### 2.2 Rate Limit Config (Current)
- Standard: 100 requests/60s
- Heavy endpoints: 20 requests/60s
- Redis-based sliding window

---

## 3. Vnstock APIs - Untapped Potential (VCI Source)

### 3.1 High-Value APIs Not Yet Implemented

| API | Method | Value | Rate Impact |
|-----|--------|-------|-------------|
| `trading.foreign_trade()` | Foreign buy/sell flow | **High** - Khối ngoại là indicator quan trọng | Medium |
| `trading.prop_trade()` | Proprietary trading | **High** - Tự doanh CTCK | Medium |
| `trading.order_stats()` | Buy/sell order counts | **Medium** - Order flow analysis | Low |
| `company.news()` | Company news | **High** - Event-driven trading | Low |
| `company.dividends()` | Dividend history | **Medium** - Income investors | Low |
| `quote.intraday()` | Intraday ticks | **High** - Day trading | High (heavy) |

### 3.2 Rate Limit Considerations

```
Current load per stock view:
- 1x detail API
- 1x shareholders (lazy)
- 1x financials (lazy)
- 1x volume analysis (lazy)
= ~4 requests/stock

Proposed additions (lazy-loaded):
- 1x foreign_trade (30-day range)
- 1x prop_trade (30-day range)
- 1x news (cached 5min)
- 1x dividends (cached 1h)
= +4 requests/stock (max)

Strategy: Lazy-load on tab switch + aggressive caching
```

---

## 4. Feature Proposals

### 4.1 New Tab: "Dòng Tiền" (Money Flow)

**Priority: HIGH**

Combines foreign + proprietary trading data:

```
┌─────────────────────────────────────────────────────┐
│ DÒNG TIỀN - VCB                                     │
├─────────────────────────────────────────────────────┤
│ Khối Ngoại (30D)                                    │
│ ┌───────────────────────────────────────┐           │
│ │ [Bar chart: Net buy/sell by day]      │           │
│ └───────────────────────────────────────┘           │
│ Net Buy: +1.2M shares | Value: +89.5B VND          │
│ Ownership: 28.56% | Room: 309M shares              │
├─────────────────────────────────────────────────────┤
│ Tự Doanh CTCK (30D)                                 │
│ ┌───────────────────────────────────────┐           │
│ │ [Bar chart: Prop trading volume]      │           │
│ └───────────────────────────────────────┘           │
│ Net: -2.3M shares | Sell pressure detected         │
└─────────────────────────────────────────────────────┘
```

**Data Sources:**
- `trading.foreign_trade(start, end)` → VCI
- `trading.prop_trade(start, end)` → VCI

**Implementation Notes:**
- Cache: 15min during trading hours, 1h after
- Charts: Recharts BarChart (already in stack)

---

### 4.2 New Tab: "Tin Tức & Sự Kiện" (News & Events)

**Priority: HIGH**

```
┌─────────────────────────────────────────────────────┐
│ TIN TỨC & SỰ KIỆN - VCB                             │
├─────────────────────────────────────────────────────┤
│ Tin Mới Nhất                                        │
│ ● [24/12] ĐHĐCĐ thông qua kế hoạch 2025...         │
│ ● [20/12] Phát hành 500 triệu cổ phiếu ESOP...     │
│ ● [15/12] Kết quả kinh doanh Q3/2024...            │
├─────────────────────────────────────────────────────┤
│ Lịch Sử Cổ Tức                                      │
│ ┌────────────┬──────────┬─────────┬────────┐       │
│ │ Ngày GDKQ  │   Năm    │  Tỷ lệ  │  Loại  │       │
│ ├────────────┼──────────┼─────────┼────────┤       │
│ │ 25/07/2023 │   2023   │  18.1%  │ CP     │       │
│ │ 22/12/2021 │   2022   │  27.6%  │ CP     │       │
│ │ 22/12/2021 │   2020   │  12.0%  │ TM     │       │
│ └────────────┴──────────┴─────────┴────────┘       │
├─────────────────────────────────────────────────────┤
│ Giao Dịch Nội Bộ (Insider Deals)                    │
│ [Already implemented - move here or duplicate]     │
└─────────────────────────────────────────────────────┘
```

**Data Sources:**
- `company.news()` → VCI
- `company.dividends()` → VCI
- `company.insider_deals()` → VCI (existing)

---

### 4.3 Enhancement: Order Flow Statistics (Volume Tab)

**Priority: MEDIUM**

Add to existing Volume tab:

```
┌─────────────────────────────────────────────────────┐
│ THỐNG KÊ ĐẶT LỆNH (30D)                             │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐         │
│ │ Date   │ Buy Orders │ Sell Orders │ Diff │        │
│ ├─────────────────────────────────────────┤         │
│ │ 24/12  │    6,520   │    6,883    │ -363 │        │
│ │ 23/12  │    4,771   │    3,794    │ +977 │        │
│ └─────────────────────────────────────────┘         │
│                                                     │
│ Avg Buy Order: 2,040 shares                         │
│ Avg Sell Order: 2,081 shares                        │
│ Order Imbalance: -1.9% (slight sell pressure)       │
└─────────────────────────────────────────────────────┘
```

**Data Source:** `trading.order_stats(start, end)` → VCI

---

### 4.4 UI/UX Improvements

#### A. Sticky Ticker Header
```tsx
// Current: Scrolls with content
// Proposed: Sticky header when scrolling down
<StockTickerHeader className="sticky top-0 z-10 bg-background/95 backdrop-blur" />
```

#### B. Tab Indicator Animation
```tsx
// Add Framer Motion for smooth tab transitions
<motion.div layoutId="tab-indicator" className="absolute bottom-0 h-0.5 bg-primary" />
```

#### C. Loading States per Tab
```tsx
// Instead of full skeleton, show tab-specific loading
{activeTab === "money-flow" && <MoneyFlowSkeleton />}
```

#### D. Quick Stats Bar (Always Visible)
```
┌──────────────────────────────────────────────────────────────┐
│ VCB │ 92,500 ▲+2.5% │ Vol: 8.2M │ Foreign: +1.2M │ P/E: 12.5 │
└──────────────────────────────────────────────────────────────┘
```

#### E. Responsive Improvements
- Mobile: Stack tabs vertically, collapsible sections
- Tablet: 2-column layout for sidebar
- Desktop: Current 3-column optimized

---

## 5. Technical Implementation Strategy

### 5.1 Backend Changes

```python
# New endpoints to add (apps/api/src/stocks/):

# 1. trading/router.py (new file)
@router.get("/{symbol}/foreign-trading")
async def get_foreign_trading(symbol: str, days: int = 30):
    """Foreign investor buy/sell data"""

@router.get("/{symbol}/prop-trading")
async def get_prop_trading(symbol: str, days: int = 30):
    """Securities company proprietary trading"""

@router.get("/{symbol}/order-stats")
async def get_order_stats(symbol: str, days: int = 30):
    """Order flow statistics"""

# 2. company/router.py (extend)
@router.get("/{symbol}/news")
async def get_company_news(symbol: str, limit: int = 20):
    """Company news and announcements"""

@router.get("/{symbol}/dividends")
async def get_dividend_history(symbol: str):
    """Historical dividend data"""
```

### 5.2 Frontend Changes

```typescript
// New tabs in stock-detail-tabs.tsx
export type StockDetailTabValue =
  | "overview"
  | "finance"
  | "shareholders"
  | "volume"
  | "money-flow"    // NEW
  | "news-events"   // NEW

// New hooks
useMoneyFlow(symbol)      // foreign + prop trading
useCompanyNews(symbol)    // news + dividends
useOrderStats(symbol)     // order flow
```

### 5.3 Caching Strategy

| Endpoint | TTL (Trading Hours) | TTL (After Hours) |
|----------|---------------------|-------------------|
| foreign-trading | 15min | 1h |
| prop-trading | 15min | 1h |
| order-stats | 5min | 30min |
| news | 5min | 15min |
| dividends | 1h | 24h |

---

## 6. Evaluated Approaches

### Option A: Add All Features (6 tabs total)
**Pros:** Comprehensive analysis, competitive with pro tools
**Cons:** UI cluttered, more API calls, higher complexity
**Verdict:** Too much for MVP

### Option B: Add 2 New Tabs + Enhance Volume ✅ RECOMMENDED
**Pros:** Balanced value/complexity, focused on unique data
**Cons:** Some features deferred
**Verdict:** Best ROI

### Option C: Single "Advanced" Tab with Sub-sections
**Pros:** Cleaner UI, progressive disclosure
**Cons:** Hidden features, extra clicks
**Verdict:** Consider for mobile

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VCI API rate limit | Medium | High | Aggressive caching, lazy-load |
| VCI API downtime | Low | High | Fallback UI, cache stale data |
| Performance degradation | Medium | Medium | Background prefetch, skeleton |
| UI overwhelm | Medium | Medium | Progressive disclosure, tooltips |

---

## 8. Success Metrics

- **Engagement:** Time on Deep Dive page ↑20%
- **Feature Usage:** Money Flow tab views ≥30% of users
- **Performance:** P95 load time <2s for all tabs
- **API Health:** Rate limit errors <0.1%

---

## 9. Final Recommendation

**Implement Option B - APPROVED**

### Phase 1 (Priority)
1. ✅ Backend: 5 new endpoints (foreign-trading, prop-trading, order-stats, news, dividends)
2. ✅ Tab "Dòng Tiền" (Foreign + Prop trading gộp 1 tab)
3. ✅ Quick Stats Bar (sticky)
4. ✅ Tabs Bar (sticky)

### Phase 2
1. Tab "Tin Tức & Sự Kiện" (News + Dividends + Insider Deals)
2. Dropdown overflow cho mobile (4 + More)
3. Order stats trong Volume tab

### Phase 3
1. Tab animations (Framer Motion)
2. UI polish
3. Export/share functionality

---

## 10. Resolved Questions

| Question | Answer |
|----------|--------|
| Intraday data? | Deferred to Phase 3+ (rate limit concern) |
| Historical depth? | **30 days** - đủ cho short-term trends |
| User preferences? | TBD - consider localStorage first |

---

## Next Steps

Brainstorm complete. Ready for `/plan` to create implementation plan.

