# Brainstorm: Deep Dive - Advanced Tab

**Date**: 2024-12-27
**Status**: ✅ DECISIONS FINALIZED
**Context**: Thiết kế tab "Advanced" mới cho Deep Dive với focus Order Flow & Technical Stats

---

## 🎯 CONFIRMED DECISIONS

| Category | Decision |
|----------|----------|
| **New Tab** | 1 tab "Advanced" |
| **Structure** | Nested sub-tabs (3 sub-tabs) |
| **Sub-tabs** | Order Flow → Technical → Money Flow |
| **Data Depth** | 30 ngày (mặc định) |
| **Priority** | Order Flow first |

### Final Layout
```
┌──────────────────────────────────────────────────────────────────┐
│ Deep Dive Tabs Bar                                                │
│ [Tổng Quan] [Tài Chính] [Cổ Đông] [Khối Lượng] [ADVANCED ▼]      │
├──────────────────────────────────────────────────────────────────┤
│ Advanced Sub-tabs                                                 │
│ [Order Flow] [Technical] [Money Flow]                             │
├──────────────────────────────────────────────────────────────────┤
│ Sub-tab Content (lazy load)                                       │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ Order Stats Table (30D)                                     │   │
│ │ Date    │ Buy Orders │ Sell Orders │ Avg Buy │ Avg Sell    │   │
│ ├─────────┼────────────┼─────────────┼─────────┼─────────────┤   │
│ │ 27/12   │   6,520    │    6,883    │  2,040  │   2,081     │   │
│ └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ Price Depth (Real-time)                                     │   │
│ │ Bid 3: 92,200 × 5,000  │  Ask 1: 92,400 × 3,200            │   │
│ │ Bid 2: 92,300 × 8,500  │  Ask 2: 92,500 × 2,100            │   │
│ │ Bid 1: 92,350 × 12,000 │  Ask 3: 92,600 × 4,500            │   │
│ └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. Problem Statement

Tab Deep Dive cần mở rộng với các tính năng phân tích chuyên sâu:
- **Order Flow**: Phân tích dòng lệnh và độ sâu giá
- **Technical Stats**: Chỉ số kỹ thuật và thống kê giao dịch
- **Money Flow**: Dòng tiền khối ngoại và tự doanh (backend đã có)

Yêu cầu chính:
- Chỉ sử dụng nguồn **VCI** (TCBS đã ngưng dịch vụ)
- Chú ý **rate limit** khi kéo dữ liệu
- Đảm bảo Vnstock có thể lấy được data

---

## 2. Current State Analysis

### 2.1 Existing Tabs (4 tabs)

| Tab | Content | API Status |
|-----|---------|------------|
| **Tổng Quan** | Price stats, 52-week range | ✅ Có |
| **Tài Chính** | Financial statements, ratios | ✅ Có |
| **Cổ Đông** | Shareholders, officers | ✅ Có |
| **Khối Lượng** | Volume analysis | ✅ Có |

### 2.2 Backend APIs Status

| API | Service | Router | Frontend Hook |
|-----|---------|--------|---------------|
| `foreign-trading` | ✅ TradingService | ✅ Có | ❌ Chưa có |
| `prop-trading` | ✅ TradingService | ✅ Có | ❌ Chưa có |
| `order-stats` | ✅ TradingService | ✅ Có | ❌ Chưa có |
| `price-depth` | ❌ Chưa có | ❌ Chưa có | ❌ Chưa có |
| `ratio-summary` | ❌ Chưa có | ❌ Chưa có | ❌ Chưa có |
| `trading-stats` | ❌ Chưa có | ❌ Chưa có | ❌ Chưa có |
| `news` | ✅ CompanyService | ❌ Chưa có | ❌ Chưa có |
| `dividends` | ✅ CompanyService | ❌ Chưa có | ❌ Chưa có |

---

## 3. Vnstock VCI APIs - Available Methods

### 3.1 Quote APIs

```python
from vnstock import Quote

quote = Quote(symbol='VCB', source='VCI')

# Historical data
quote.history(start='2024-01-01', end='2024-12-27', interval='1D')

# Intraday data
quote.intraday(page_size=10000)

# Price depth - NEW
quote.price_depth()  # Returns bid/ask levels
```

### 3.2 Company APIs

```python
from vnstock import Vnstock

company = Vnstock().stock(symbol='VCB', source='VCI').company

# Existing
company.overview()
company.shareholders()
company.officers()
company.insider_deals()
company.news()
company.dividends()

# NEW - to implement
company.ratio_summary()  # P/E, P/B, ROE, ROA
company.trading_stats()  # Volume, turnover
```

### 3.3 Trading APIs

```python
stock = Vnstock().stock(symbol='VCB', source='VCI')

# Existing in backend
stock.trading.foreign_trade(start='2024-12-01', end='2024-12-27')
stock.trading.prop_trade(start='2024-12-01', end='2024-12-27', resolution='1D')
stock.trading.order_stats(start='2024-12-01', end='2024-12-27')
```

---

## 4. Feature Proposals

### 4.1 Sub-tab 1: Order Flow ⭐ PRIORITY

**Content:**
1. **Order Stats Table** (30D)
   - Daily buy/sell order counts
   - Average order sizes
   - Order imbalance indicator

2. **Price Depth Widget** (Real-time)
   - Bid/Ask 3 levels
   - Total bid/ask volume
   - Spread indicator

**Backend Requirements:**
| API | Method | Data Source |
|-----|--------|-------------|
| `GET /{symbol}/order-stats` | ✅ Đã có | VCI |
| `GET /{symbol}/price-depth` | ❌ Cần thêm | VCI quote.price_depth() |

**UI Components:**
```
OrderFlowSubTab
├── OrderStatsSection
│   ├── OrderStatsChart (Recharts)
│   └── OrderStatsTable
└── PriceDepthSection
    ├── BidAskLevels (real-time)
    └── SpreadIndicator
```

---

### 4.2 Sub-tab 2: Technical Stats

**Content:**
1. **Ratio Summary Card**
   - P/E, P/B, EPS
   - ROE, ROA, ROS
   - Debt/Equity

2. **Trading Stats Card**
   - Average volume (5D, 20D)
   - Turnover rate
   - Volatility

**Backend Requirements:**
| API | Method | Data Source |
|-----|--------|-------------|
| `GET /{symbol}/ratio-summary` | ❌ Cần thêm | VCI company.ratio_summary() |
| `GET /{symbol}/trading-stats` | ❌ Cần thêm | VCI company.trading_stats() |

**UI Components:**
```
TechnicalSubTab
├── RatioSummaryCard
│   ├── ValuationRatios (P/E, P/B, EPS)
│   └── ProfitabilityRatios (ROE, ROA, ROS)
└── TradingStatsCard
    ├── VolumeStats
    └── VolatilityIndicator
```

---

### 4.3 Sub-tab 3: Money Flow

**Content:**
1. **Foreign Trading Chart** (30D)
   - Net buy/sell bar chart
   - Cumulative flow line
   - Foreign ownership %

2. **Prop Trading Chart** (30D)
   - Securities firm trading
   - Net position trend

**Backend Requirements:**
| API | Method | Data Source |
|-----|--------|-------------|
| `GET /{symbol}/foreign-trading` | ✅ Đã có | VCI |
| `GET /{symbol}/prop-trading` | ✅ Đã có | VCI |

**UI Components:**
```
MoneyFlowSubTab
├── ForeignTradingSection
│   ├── ForeignFlowChart (Recharts)
│   └── ForeignSummaryCard
└── PropTradingSection
    ├── PropFlowChart (Recharts)
    └── PropSummaryCard
```

---

## 5. Technical Implementation

### 5.1 Backend Changes

#### New Service Methods

```python
# stocks/company/service.py - ADD
def get_ratio_summary(self, symbol: str) -> RatioSummaryResponse:
    """Get financial ratio summary."""
    stock = Vnstock().stock(symbol=symbol, source=self.source)
    df = stock.company.ratio_summary()
    # Parse and return

def get_trading_stats(self, symbol: str) -> TradingStatsResponse:
    """Get trading statistics."""
    stock = Vnstock().stock(symbol=symbol, source=self.source)
    df = stock.company.trading_stats()
    # Parse and return

# stocks/price/service.py - ADD
def get_price_depth(self, symbol: str) -> PriceDepthResponse:
    """Get real-time price depth (bid/ask levels)."""
    quote = Quote(symbol=symbol, source='VCI')
    df = quote.price_depth()
    # Parse and return
```

#### New Router Endpoints

```python
# stocks/company/router.py - ADD
@router.get("/{symbol}/ratio-summary")
async def get_ratio_summary(symbol: str)

@router.get("/{symbol}/trading-stats")
async def get_trading_stats(symbol: str)

# stocks/price/router.py - ADD
@router.get("/{symbol}/price-depth")
async def get_price_depth(symbol: str)
```

### 5.2 Frontend Changes

#### New Hooks

```typescript
// hooks/use-order-stats.ts - CREATE
export function useOrderStats(symbol: string, days = 30)

// hooks/use-price-depth.ts - CREATE
export function usePriceDepth(symbol: string)

// hooks/use-ratio-summary.ts - CREATE
export function useRatioSummary(symbol: string)

// hooks/use-trading-stats.ts - CREATE
export function useTradingStats(symbol: string)

// hooks/use-foreign-trading.ts - CREATE
export function useForeignTrading(symbol: string, days = 30)

// hooks/use-prop-trading.ts - CREATE
export function usePropTrading(symbol: string, days = 30)
```

#### New Components

```typescript
// components/dashboard/
├── advanced-tab/
│   ├── index.tsx              // Main Advanced tab container
│   ├── order-flow-subtab.tsx  // Order Flow sub-tab
│   ├── technical-subtab.tsx   // Technical sub-tab
│   ├── money-flow-subtab.tsx  // Money Flow sub-tab
│   ├── order-stats-table.tsx  // Order stats table
│   ├── price-depth-widget.tsx // Bid/ask levels widget
│   ├── ratio-summary-card.tsx // Financial ratios card
│   ├── trading-stats-card.tsx // Trading stats card
│   ├── foreign-flow-chart.tsx // Foreign trading chart
│   └── prop-flow-chart.tsx    // Prop trading chart
```

### 5.3 Caching Strategy

| Endpoint | TTL Trading | TTL Off-hours | Priority |
|----------|-------------|---------------|----------|
| price-depth | 30s | 5min | Heavy (real-time) |
| order-stats | 15min | 1h | Standard |
| ratio-summary | 1h | 6h | Light |
| trading-stats | 15min | 1h | Standard |
| foreign-trading | 15min | 1h | Standard |
| prop-trading | 15min | 1h | Standard |

---

## 6. Rate Limit Considerations

### Current Load per Stock View
```
Existing calls:
- 1x detail API
- 1x shareholders (lazy)
- 1x financials (lazy)
- 1x volume analysis (lazy)
= ~4 requests/stock

New calls (Advanced tab - lazy):
- 1x order-stats
- 1x price-depth (heavy - short cache)
- 1x ratio-summary
- 1x trading-stats
- 1x foreign-trading
- 1x prop-trading
= +6 requests/stock (max, only if Advanced tab opened)
```

### Mitigation Strategies
1. **Lazy load** - Only fetch when sub-tab opened
2. **Aggressive caching** - Redis with trading-hours-aware TTL
3. **Batch requests** - Combine ratio-summary + trading-stats if possible
4. **Stale-while-revalidate** - Show cached data while fetching

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VCI API rate limit | Medium | High | Lazy-load, aggressive cache |
| price_depth không có data | Low | Medium | Fallback UI, show N/A |
| ratio_summary format khác | Medium | Low | Flexible parsing, defaults |
| UI performance với nested tabs | Low | Medium | Lazy components, skeletons |

---

## 8. Success Metrics

- **Engagement:** Advanced tab clicks ≥15% of Deep Dive users
- **Performance:** P95 load time <1.5s cho mỗi sub-tab
- **API Health:** Rate limit errors <0.1%
- **Data Quality:** Null/empty responses <5%

---

## 9. Implementation Phases

### Phase 1: Order Flow (Priority)
1. ✅ Backend: order-stats endpoint (có sẵn)
2. ❌ Backend: price-depth endpoint (mới)
3. ❌ Frontend: useOrderStats, usePriceDepth hooks
4. ❌ Frontend: OrderFlowSubTab component

### Phase 2: Technical Stats
1. ❌ Backend: ratio-summary endpoint
2. ❌ Backend: trading-stats endpoint
3. ❌ Frontend: useRatioSummary, useTradingStats hooks
4. ❌ Frontend: TechnicalSubTab component

### Phase 3: Money Flow
1. ✅ Backend: foreign-trading endpoint (có sẵn)
2. ✅ Backend: prop-trading endpoint (có sẵn)
3. ❌ Frontend: useForeignTrading, usePropTrading hooks
4. ❌ Frontend: MoneyFlowSubTab component

### Phase 4: Integration
1. ❌ Frontend: AdvancedTab container với nested sub-tabs
2. ❌ Frontend: Update StockDetailTabs với Advanced tab
3. ❌ Testing: E2E tests, rate limit validation
4. ❌ Polish: Animations, loading states, error handling

---

## 10. Final Recommendation

**Implement tất cả 3 sub-tabs theo thứ tự ưu tiên:**

1. **Order Flow** - Backend có sẵn order-stats, chỉ cần thêm price-depth
2. **Technical Stats** - Cần thêm 2 endpoints mới
3. **Money Flow** - Backend hoàn toàn sẵn, chỉ cần frontend

**Estimated scope:**
- Backend: 3 new endpoints + 3 new schemas
- Frontend: 1 main component + 3 sub-tabs + 6 hooks + 8 widgets
- Testing: API tests + component tests + E2E

---

## Unresolved Questions

Không có câu hỏi chưa giải quyết. Tất cả quyết định đã được finalize.

---

## Next Steps

Brainstorm complete. Ready for `/plan` to create detailed implementation plan.
