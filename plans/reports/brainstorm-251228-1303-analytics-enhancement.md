# Brainstorm Report: Analytics Tab Enhancement

**Date**: 2024-12-28
**Author**: Solution Brainstormer
**Status**: Approved

---

## Problem Statement

Hệ thống phân tích chứng khoán cần mở rộng tab Analytics để phục vụ tốt hơn nhóm Institutional investors với:
- Phân tích so sánh sâu hơn
- Độ tin cậy dữ liệu cao (chỉ dùng VCI source)
- Tối ưu rate limit khi kéo dữ liệu

---

## Requirements Gathered

| Aspect | Decision |
|--------|----------|
| Target Users | Institutional investors |
| Priority | Features mới + Độ sâu phân tích + UX |
| Rate Limit | Cân bằng (cache thông minh) |
| Data Depth | Ngắn hạn (1-2 quý) |
| Chosen Approach | Sector Comparison Dashboard |

---

## Current State Analysis

### Existing Analytics Features
1. **Deep-Dive Page** - Chi tiết cổ phiếu đơn lẻ
2. **Volume Spikes** - Phát hiện đột biến khối lượng theo ngành ICB
3. **Financial Statements** - Ranking top companies by net profit
4. **Advanced Tab** (trong stock detail):
   - Order Flow - Buy/sell order analysis
   - Technical - Chỉ số kỹ thuật (placeholder)
   - Money Flow - NĐTNN & Tự doanh tracking

### Available VCI Data Sources (Unused)
```python
# Financial ratios (37+ metrics)
Finance(symbol, source='VCI').ratio(period='quarter', lang='en')

# Sector peers lookup
Listing().symbols_by_industries()  # ICB Level 2/3

# Company trading stats
Company(symbol).trading_stats()  # Foreign room, ownership
```

### Backend Already Implemented
- `get_sector_peers()` in `financial/service.py`
- `SectorPeersResponse` schema with `PeerMetrics`
- `/analytics/sector-peers` endpoint

---

## Evaluated Approaches

### Approach 1: Sector Comparison Dashboard ⭐ SELECTED

**Description**: So sánh cổ phiếu với peers cùng ngành ICB Level 3

**Components**:
1. **Peer Ranking Table**
   - So sánh P/E, P/B, ROE, ROA, Market Cap
   - Highlight target stock position
   - Sort by any metric

2. **Relative Valuation Widget**
   - Premium/Discount vs sector median
   - Bar chart visualization
   - Phát hiện undervalued opportunities

3. **Sector Overview Card**
   - ICB sector name + code
   - Number of peers in sector
   - Sector average metrics

**Pros**:
- ✅ Trực tiếp phục vụ institutional decision-making
- ✅ Backend API đã có (`/analytics/sector-peers`)
- ✅ Rate limit friendly - cache theo symbol, 1hr TTL
- ✅ Dữ liệu từ VCI source duy nhất

**Cons**:
- ⚠️ Cần fetch ratio cho 5-6 symbols mỗi request
- ⚠️ UI complexity (table + chart)

**Risk Mitigation**:
- Cache peers data 24hr off-hours
- Pre-warm cache cho VN30 symbols

---

### Approach 2: Financial Health Score UI

**Description**: Visualize existing health score data

**Components**:
- Radar chart (4 dimensions)
- Piotroski F-Score badge
- Trend sparkline

**Pros**:
- ✅ Backend 100% implemented
- ✅ Low effort UI
- ✅ No additional API calls

**Cons**:
- ⚠️ Less "wow factor"
- ⚠️ Chỉ tổng hợp data có sẵn

---

### Approach 3: Market Screener Page

**Description**: Filter stocks by multiple criteria

**Pros**:
- ✅ High value for discovery
- ✅ Core institutional feature

**Cons**:
- ⚠️ High rate limit impact
- ⚠️ Need batch processing infrastructure
- ⚠️ Complex filter UI

**Verdict**: Postpone to Phase 2

---

## Final Recommended Solution

### Sector Comparison Implementation Plan

#### Backend Tasks
1. **Enhance sector_peers endpoint**
   - Add sector median calculations
   - Add premium/discount metrics
   - Return more peers (10 instead of 5)

2. **Add sector overview endpoint** (optional)
   - `/analytics/sector-overview?icb_code=XXX`
   - Sector stats aggregation

#### Frontend Tasks
1. **Create SectorComparisonWidget component**
   - Table with sortable columns
   - Highlight target stock row
   - Premium/discount badges

2. **Add to Advanced Tab as new subtab**
   - "Sector" subtab alongside Order Flow, Technical, Money Flow

3. **Responsive design**
   - Mobile: Stack cards
   - Desktop: Side-by-side table + chart

#### Rate Limit Strategy
```
Cache Strategy:
- Trading hours: 30min TTL
- Off hours: 24hr TTL
- Key format: sector_peers:{symbol}:{limit}

Request Optimization:
- Batch fetch peer ratios (single API call per peer)
- Pre-warm cache for VN30 + HNX30 symbols via scheduled job
```

---

## Implementation Considerations

### VCI Data Source Constraints
- TCBS đã ngừng service → chỉ dùng VCI
- Rate limit: ~100 requests/minute (observed)
- Batch requests: Limit 5-10 symbols/request

### UI/UX Guidelines
- Follow existing Modern + Clean design
- Vietnamese labels for metrics
- Color coding: Green (above median), Red (below), Gray (at median)

### Success Metrics
| Metric | Target |
|--------|--------|
| Page load time | < 2s with cache |
| Cache hit ratio | > 80% during trading |
| User engagement | Time on page > 30s |

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| VCI API downtime | High | Graceful fallback, cached data |
| Rate limit exceeded | Medium | Queue + backoff, larger cache TTL |
| ICB code missing | Low | Default to "Unknown sector" |
| No peers found | Low | Show "No comparable peers" message |

---

## Next Steps

1. **Create implementation plan** với chi tiết task breakdown
2. **Backend**: Enhance sector_peers endpoint
3. **Frontend**: Build SectorComparisonWidget
4. **Testing**: Unit tests + integration tests
5. **Documentation**: Update API docs

---

## Unresolved Questions

1. Có cần thêm filter theo exchange (HOSE/HNX only) cho peer comparison?
2. Có hiển thị thêm metrics như Dividend Yield, Beta không?
3. Có cần export peer comparison to CSV?

---

## Appendix: VCI API Reference

### Finance.ratio() columns (partial)
- `ROE (%)`, `ROA (%)`, `P/E`, `P/B`
- `Gross Profit Margin (%)`, `Net Profit Margin (%)`
- `Current Ratio`, `Quick Ratio`, `Debt/Equity`
- `Market Capital (Bn. VND)`

### Listing.symbols_by_industries() columns
- `symbol`, `organ_name`
- `icb_code2`, `icb_name2` (Level 2)
- `icb_code3`, `icb_name3` (Level 3)
