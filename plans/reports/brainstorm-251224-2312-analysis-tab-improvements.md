# Brainstorm Report: Analysis Tab Improvements

**Date**: 2024-12-24
**Status**: Draft
**Target Users**: Retail investors, Day traders, Fund managers/Analysts

---

## 1. Problem Statement

Tab "Analysis" (Deep-Dive page) hiện có 4 sub-tabs:
- **Overview**: Price, stats, key ratios (EPS, P/E, P/B)
- **Finance**: Financial statements
- **Shareholders**: Major holders, management
- **Volume**: Intraday volume anomaly detection

**Gap identified**: Thiếu các công cụ phân tích kỹ thuật (Technical Analysis) và dữ liệu dòng tiền thông minh (Foreign/Proprietary trading) - 2 yếu tố quan trọng cho quyết định đầu tư.

---

## 2. VNStock Capabilities Analysis (via Context7)

### 2.1 Technical Analysis Features (Available in vnstock)

| Feature | Function | Status in App |
|---------|----------|---------------|
| Candlestick Charts | `candlestick_chart()` | ❌ Not implemented |
| Bollinger Bands | `bollinger_bands()`, `bollinger_bands_chart()` | ❌ Not implemented |
| Moving Averages | Built into candlestick_chart | ❌ Not implemented |
| Support/Resistance | Built into candlestick_chart | ❌ Not implemented |
| Price Depth | `quote.price_depth()` | ❌ Not implemented |

### 2.2 Trading Data Features (Available in vnstock)

| Feature | Function | Status in App |
|---------|----------|---------------|
| Foreign Trading | `trading.foreign_trade()` | ❌ Not implemented |
| Proprietary Trading | `trading.prop_trade()` | ❌ Not implemented |
| Order Statistics | `trading.order_stats()` | ❌ Not implemented |
| Top Foreign Buy/Sell | `top.foreign_buy()`, `top.foreign_sell()` | ❌ Not implemented |
| Price History | `trading.price_history()` | ✅ Implemented |
| Intraday Data | `quote.intraday()` | ✅ Implemented |

### 2.3 Company Data Features

| Feature | Function | Status in App |
|---------|----------|---------------|
| Company Events | `company.events()` | ❌ Not implemented |
| Company News | `company.news()` | ❌ Not implemented |
| Company Profile | `company.profile()` | ⚠️ Partial (description only) |
| Company Overview | `company.overview()` | ✅ Implemented |

### 2.4 Market Data Features

| Feature | Function | Status in App |
|---------|----------|---------------|
| Commodity Prices | `commodity.gold_vn()`, `commodity.oil_crude()` | ❌ Not implemented |
| Exchange Rates | Available via vnstock | ❌ Not implemented |

---

## 3. Proposed Improvements

### Priority 1: Technical Analysis Tab (NEW) ⭐⭐⭐

**Rationale**: Cả 3 target user groups đều cần TA tools

**Features**:
1. **Price Chart with Indicators**
   - Candlestick/Line chart (Lightweight Charts hoặc Recharts)
   - Overlays: SMA(20,50,200), EMA, Bollinger Bands
   - Configurable time range: 1M, 3M, 6M, 1Y, 5Y

2. **Technical Indicators Panel**
   - RSI với overbought/oversold zones (70/30)
   - MACD histogram + signal line
   - Volume with MA overlay

3. **Price Levels**
   - Support/Resistance (auto-calculated)
   - 52-week High/Low markers
   - Price alerts UI (future)

**Backend API needed**:
```python
# New endpoint: /api/v1/stocks/{symbol}/technical
# Response: OHLCV + calculated indicators (SMA, RSI, MACD, BB)
```

**Effort**: Medium-High (3-5 days)

---

### Priority 2: Foreign & Proprietary Trading Tab (NEW) ⭐⭐⭐

**Rationale**: "Smart money" insights - NĐT ngoại và tự doanh thường có thông tin sớm

**Features**:
1. **Foreign Trading Summary Card**
   - Net buy/sell volume & value (daily, weekly trend)
   - Foreign ownership % với room remaining
   - Buy/Sell ratio visualization

2. **Proprietary Trading Summary Card**
   - Daily prop trading net volume/value
   - Prop vs Market participation %

3. **Historical Trend Chart**
   - Stacked area: Foreign + Prop net flow over 30/60/90 days
   - Correlation với price movement

4. **Top Movers Panel**
   - Top 10 foreign net buy/sell của ngày
   - Comparison với previous day

**Backend API needed**:
```python
# New endpoints:
# /api/v1/stocks/{symbol}/foreign-trading
# /api/v1/stocks/{symbol}/prop-trading
# /api/v1/stocks/top-foreign-flow
```

**Effort**: Medium (2-3 days)

---

### Priority 3: UI/UX Improvements for Existing Tabs

#### 3.1 Overview Tab Enhancements
- **Add**: Mini sparkline chart (7-day price trend)
- **Add**: Price change badges (1D, 1W, 1M, YTD)
- **Add**: Quick comparison with VN-INDEX performance
- **Improve**: Better visual hierarchy for key metrics

#### 3.2 Volume Tab Enhancements
- **Add**: Comparison mode (Today vs Average bar chart)
- **Add**: Peak volume time highlighter
- **Add**: Integration với price movement correlation

#### 3.3 Finance Tab Enhancements
- **Add**: QoQ/YoY growth visualization
- **Add**: Key ratios trend (5-quarter chart)
- **Add**: Peer comparison toggle

**Effort**: Low-Medium (1-2 days per enhancement)

---

### Priority 4: Company Events & News Tab (Optional)

**Features**:
- Upcoming dividends, AGM dates
- Recent company announcements
- News feed with sentiment indicators

**Backend API**: `company.events()`, `company.news()`

**Effort**: Medium (2-3 days)

---

## 4. Recommended Approach

### Phase 1: Quick Wins (1-2 weeks)
1. ✅ Foreign/Prop Trading Tab - high value, medium effort
2. ✅ Overview Tab sparkline + price change badges

### Phase 2: Core Features (2-3 weeks)
1. ✅ Technical Analysis Tab with basic charts
2. ✅ Volume Tab enhancements

### Phase 3: Polish (1-2 weeks)
1. Company Events tab
2. Finance Tab improvements
3. Cross-tab linking (click volume spike → jump to TA chart)

---

## 5. Technical Considerations

### Frontend
- **Charts**: Recommend `lightweight-charts` (TradingView open-source) over Recharts for TA
  - Better performance for large datasets
  - Native candlestick support
  - Built-in crosshair, zoom, pan
- **State**: Sử dụng TanStack Query pattern hiện có
- **Responsive**: Mobile-first cho day traders on-the-go

### Backend
- **Caching**: Foreign/Prop data update EOD → 24h cache OK
- **Rate Limiting**: Technical data có thể heavy → consider dedicated limit
- **Aggregation**: Pre-calculate indicators backend để giảm frontend load

### Data Freshness
| Data Type | Update Frequency | Cache TTL |
|-----------|------------------|-----------|
| Price/OHLCV | Real-time/15min | 1-5 min |
| Foreign/Prop | EOD | 24h |
| Technical Indicators | On-demand | 1h |
| Company Events | Weekly | 24h |

---

## 6. Success Metrics

1. **User Engagement**: Time spent on Analysis page ↑
2. **Feature Adoption**: % users using TA/Foreign tabs
3. **Data Freshness**: Avg cache hit rate
4. **Performance**: Chart render time < 500ms

---

## 7. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| vnstock API rate limits | High | Implement smart caching, batch requests |
| Chart performance with large data | Medium | Use lightweight-charts, virtualization |
| Mobile UX complexity | Medium | Progressive disclosure, tab navigation |
| Data accuracy | High | Validate against official sources periodically |

---

## 8. Unresolved Questions

1. **Chart Library Decision**: Lightweight-charts vs Recharts vs ApexCharts?
   - Recommend: Lightweight-charts for TA, keep Recharts for simple charts

2. **Real-time Data**: WebSocket for live price updates trong TA tab?
   - Current: Polling với 10s interval (acceptable for MVP)

3. **Indicator Calculations**: Frontend (JS) vs Backend (Python)?
   - Recommend: Backend - vnstock đã có sẵn, giảm bundle size

4. **TradingView Plans**: Có integrate TradingView widget hay build in-house?
   - TradingView widget: đẹp nhưng limited customization, có branding
   - In-house: Full control, no external dependency

---

## 9. Agreed Structure

**Decision**: Option A - Thêm sub-tabs vào Deep-Dive page

```
/analytics/deep-dive/{symbol}
├── Overview        [Existing] - Price, stats, ratios
├── Finance         [Existing] - Financial statements
├── Shareholders    [Existing] - Major holders, management
├── Volume          [Existing] - Intraday anomaly detection
├── Technical ⭐    [NEW] - Candlestick + Indicators
└── Money Flow ⭐   [NEW] - Foreign + Proprietary trading
```

**Rationale**:
- Tập trung tất cả stock analysis vào 1 workflow
- User chỉ cần search stock 1 lần
- Consistent UX với pattern hiện có

---

## 10. Next Steps

Nếu đồng ý với hướng đề xuất:
1. [ ] Tạo implementation plan chi tiết cho Phase 1
2. [ ] Design UI mockups cho Technical + Money Flow tabs
3. [ ] Setup lightweight-charts trong frontend
4. [ ] Implement backend APIs

---

**Report generated by**: Brainstormer Agent
**Review status**: Structure approved - awaiting implementation decision
