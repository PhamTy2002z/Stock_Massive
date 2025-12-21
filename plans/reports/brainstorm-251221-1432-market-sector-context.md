# Brainstorm: Market & Sector Context Analysis

**Date:** 2024-12-21
**Feature:** Deep Dive - Market & Sector Context Tab
**Goal:** Phân tích cổ phiếu đang đi cùng hay ngược xu hướng thị trường và ngành

---

## 1. Problem Statement

Nhà đầu tư cần hiểu:
- Cổ phiếu đang **outperform** hay **underperform** so với thị trường chung (VNINDEX)?
- Cổ phiếu đang **dẫn dắt** hay **đi sau** ngành của nó?
- Xu hướng này có **bền vững** không?

---

## 2. Data Sources (vnstock API)

### 2.1 Stock Price History
```python
stock.quote.history(symbol='VCB', start='2024-01-01', end='2025-03-19', interval='1D')
```

### 2.2 Index History
```python
stock.quote.history(symbol='VNINDEX', start='2024-01-02', end='2025-03-19', interval='1D')
stock.quote.history(symbol='VN30', start='2024-01-02', end='2025-03-19', interval='1D')
```

### 2.3 Industry/Sector Data
```python
stock.listing.symbols_by_industries()  # Get stocks by ICB code
stock.listing.industries_icb()          # Get ICB code mapping
```

### 2.4 Sector Performance (existing API)
```
GET /stocks/sector-performance
```
Returns: `icb_code`, `icb_name`, `change_pct`, `top_gainers`, `top_losers`

---

## 3. Proposed Analysis Components

### 3.1 Relative Performance Chart (Core Feature)

**Concept:** Normalized price chart comparing stock vs VNINDEX vs Sector Index

**Calculation:**
```
Normalized_Price(t) = (Price(t) / Price(t0)) * 100
```
Where `t0` = start of selected period

**Timeframes:** 1W, 1M, 3M, 6M, YTD, 1Y

**Visual:** Line chart with 3 lines (Stock, VNINDEX, Sector avg)

### 3.2 Correlation Analysis

**Metrics:**
| Metric | Description |
|--------|-------------|
| Beta | Độ nhạy với thị trường (>1 = volatile hơn) |
| Correlation | Mức độ đồng pha với VNINDEX (-1 to 1) |
| R-squared | % biến động giải thích bởi thị trường |

**Interpretation:**
- High correlation + Outperform = Strong stock in bull market
- Low correlation + Outperform = Defensive/independent stock
- High correlation + Underperform = Weak stock, avoid

### 3.3 Relative Strength Indicator (RSI vs Market)

**Formula:**
```
RS_Market = Stock_Return / VNINDEX_Return (rolling 20 days)
RS_Sector = Stock_Return / Sector_Return (rolling 20 days)
```

**Signal:**
- RS > 1: Outperforming
- RS < 1: Underperforming
- RS trending up: Gaining strength
- RS trending down: Losing strength

### 3.4 Sector Rank Card

**Display:**
- Stock's sector name
- Stock rank within sector (by performance)
- Sector rank vs all sectors
- Top 3 peers in same sector

**Example:**
```
VCB - Ngân hàng
├── Rank trong ngành: #3/27
├── Ngành rank: #5/19 sectors
└── Peers: BID (+2.1%), TCB (+1.8%), MBB (+1.5%)
```

### 3.5 Divergence Alerts

**Detect when stock diverges from market/sector:**

| Pattern | Signal |
|---------|--------|
| Stock ↑ while Market ↓ | Bullish divergence (strong) |
| Stock ↓ while Market ↑ | Bearish divergence (weak) |
| Stock ↑↑ while Sector ↑ | Sector leader |
| Stock ↓ while Sector ↑ | Sector laggard |

---

## 4. UI/UX Recommendations

### 4.1 Tab Structure
Add new tab: **"Thị Trường"** (Market Context)

```tsx
{
  value: "market" as const,
  label: "Thị Trường",
  icon: TrendingUp, // from lucide-react
}
```

### 4.2 Layout (Desktop)

```
┌─────────────────────────────────────────────────────────┐
│ [1W] [1M] [3M] [6M] [YTD] [1Y]     Period Selector      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│         Relative Performance Chart (60% height)         │
│         - Stock line (primary color)                    │
│         - VNINDEX line (gray)                           │
│         - Sector avg line (dashed)                      │
│                                                         │
├──────────────────────┬──────────────────────────────────┤
│   Correlation Card   │      Sector Rank Card            │
│   ┌───────────────┐  │   ┌────────────────────────┐     │
│   │ Beta: 1.2     │  │   │ Ngành: Ngân hàng       │     │
│   │ Corr: 0.85    │  │   │ Rank: #3/27            │     │
│   │ R²: 0.72      │  │   │ Sector rank: #5/19     │     │
│   └───────────────┘  │   └────────────────────────┘     │
├──────────────────────┴──────────────────────────────────┤
│                  Divergence Alerts                      │
│  ⚡ VCB +2.3% while VNINDEX -0.5% (Bullish divergence)  │
└─────────────────────────────────────────────────────────┘
```

### 4.3 Color Coding

| Element | Color |
|---------|-------|
| Stock outperform | Green gradient |
| Stock underperform | Red gradient |
| Neutral/Market | Gray |
| Sector average | Blue dashed |

---

## 5. Implementation Approach

### Option A: Backend-Heavy (Recommended)

**New API Endpoints:**
```
GET /stocks/{symbol}/market-context?period=3M
GET /stocks/{symbol}/sector-comparison
GET /stocks/{symbol}/correlation?benchmark=VNINDEX
```

**Pros:**
- Pre-calculated metrics, fast frontend
- Caching possible
- Complex calculations on server

**Cons:**
- More backend work
- API versioning needed

### Option B: Frontend-Heavy

**Use existing APIs + client-side calculation:**
- Fetch stock history
- Fetch VNINDEX history
- Calculate correlation/beta in browser

**Pros:**
- No backend changes
- Flexible timeframes

**Cons:**
- Heavy client computation
- Multiple API calls
- No caching benefit

### Option C: Hybrid (Balanced)

**Backend:** Pre-calculate daily correlation, beta, sector rank
**Frontend:** Normalize prices, render charts

---

## 6. Data Requirements

### 6.1 New Backend Endpoints Needed

| Endpoint | Data |
|----------|------|
| `/stocks/{symbol}/price-history` | OHLCV for stock |
| `/stocks/{symbol}/market-context` | Beta, correlation, RS |
| `/stocks/{symbol}/sector-peers` | Same-sector stocks performance |
| `/indices/{symbol}/history` | VNINDEX, VN30 history |

### 6.2 Existing APIs to Leverage

- `fetchStockDetail()` - Has `industry`, `beta`
- `fetchSectorPerformance()` - Has sector rankings
- `fetchMarketIndices()` - Has current index values

---

## 7. MVP Scope (Phase 1)

**Must Have:**
1. Relative performance chart (Stock vs VNINDEX)
2. Period selector (1M, 3M, 6M, 1Y)
3. Basic stats card (Beta, current performance diff)

**Nice to Have (Phase 2):**
4. Sector comparison line
5. Correlation metrics
6. Peer ranking table

**Future (Phase 3):**
7. Divergence alerts
8. Historical RS chart
9. Sector rotation analysis

---

## 8. Technical Considerations

### 8.1 Chart Library
Use existing: **Recharts** (already in project for volume chart)

### 8.2 Data Normalization
```typescript
function normalizeToBase100(prices: number[]): number[] {
  const base = prices[0]
  return prices.map(p => (p / base) * 100)
}
```

### 8.3 Correlation Calculation
```typescript
function pearsonCorrelation(x: number[], y: number[]): number {
  const n = x.length
  const sumX = x.reduce((a, b) => a + b, 0)
  const sumY = y.reduce((a, b) => a + b, 0)
  const sumXY = x.reduce((acc, xi, i) => acc + xi * y[i], 0)
  const sumX2 = x.reduce((acc, xi) => acc + xi * xi, 0)
  const sumY2 = y.reduce((acc, yi) => acc + yi * yi, 0)

  const num = n * sumXY - sumX * sumY
  const den = Math.sqrt((n * sumX2 - sumX ** 2) * (n * sumY2 - sumY ** 2))

  return num / den
}
```

---

## 9. Success Metrics

| Metric | Target |
|--------|--------|
| Chart load time | < 2s |
| Data freshness | EOD (end of day) |
| User engagement | Track tab clicks |

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| vnstock API rate limits | Cache aggressively, batch requests |
| Missing sector data | Fallback to VNINDEX only |
| Calculation errors | Unit tests for correlation/beta |
| Large data payload | Paginate history, limit to 1Y max |

---

## 11. Next Steps

1. **Validate approach** with stakeholder
2. **Design API contracts** for new endpoints
3. **Create UI mockup** in Figma/code
4. **Implement backend** endpoints
5. **Build frontend** components
6. **Test** with real data

---

## 12. Design Decisions (Finalized)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Intraday for 1W? | **No. Daily OHLCV only** | Intraday tốn API calls, giá trị thấp cho context analysis |
| Missing sector? | **Gán "Unclassified" → compare Market only** | Không suy đoán sector (dễ sai), fallback graceful |
| Correlation input? | **Daily returns (simple/log)** | Standard practice, precompute windows: 5D, 20D, 60D |
| Sector benchmark? | **Market-cap weighted avg của stocks trong sector** | Không cần sector index riêng, giảm external dependency |
| Cache strategy? | **Batch EOD pipeline** | Raw data: cache forever. Derived metrics: cache per trading day. UI reads precomputed tables only (zero runtime calc) |

---

## 13. Architecture: EOD Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    EOD BATCH PIPELINE                       │
├─────────────────────────────────────────────────────────────┤
│  1. Fetch raw OHLCV (vnstock) → store in DB                 │
│  2. Compute daily returns for all stocks + indices          │
│  3. Compute rolling metrics (5D, 20D, 60D):                 │
│     - Correlation vs VNINDEX                                │
│     - Beta                                                  │
│     - Relative Strength                                     │
│  4. Compute sector benchmarks (mcap-weighted avg)           │
│  5. Compute sector ranks                                    │
│  6. Store in precomputed tables                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      API LAYER                              │
├─────────────────────────────────────────────────────────────┤
│  GET /stocks/{symbol}/market-context                        │
│  → Read from precomputed tables (no runtime calc)           │
│  → Response time: <100ms                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 14. Database Schema (Precomputed Tables)

```sql
-- Daily returns (computed EOD)
CREATE TABLE stock_daily_returns (
  symbol VARCHAR(10),
  date DATE,
  close_price DECIMAL(10,2),
  return_1d DECIMAL(8,6),      -- simple return
  return_1d_log DECIMAL(8,6),  -- log return
  PRIMARY KEY (symbol, date)
);

-- Rolling metrics (computed EOD)
CREATE TABLE stock_market_metrics (
  symbol VARCHAR(10),
  date DATE,
  -- vs VNINDEX
  corr_5d DECIMAL(5,4),
  corr_20d DECIMAL(5,4),
  corr_60d DECIMAL(5,4),
  beta_20d DECIMAL(6,4),
  beta_60d DECIMAL(6,4),
  rs_market_20d DECIMAL(6,4),  -- relative strength
  -- vs Sector
  corr_sector_20d DECIMAL(5,4),
  rs_sector_20d DECIMAL(6,4),
  sector_rank INT,
  sector_total INT,
  PRIMARY KEY (symbol, date)
);

-- Sector benchmarks (computed EOD)
CREATE TABLE sector_daily_benchmark (
  icb_code VARCHAR(10),
  date DATE,
  mcap_weighted_return DECIMAL(8,6),
  total_mcap BIGINT,
  stock_count INT,
  PRIMARY KEY (icb_code, date)
);
```

---

## 15. API Response Contract

```typescript
// GET /stocks/{symbol}/market-context?period=3M
interface MarketContextResponse {
  symbol: string
  period: "1M" | "3M" | "6M" | "1Y"

  // Normalized price series (base 100)
  chart_data: {
    date: string
    stock: number      // normalized price
    vnindex: number    // normalized price
    sector: number     // normalized price (mcap-weighted)
  }[]

  // Current metrics
  metrics: {
    beta_20d: number
    beta_60d: number
    correlation_20d: number
    correlation_60d: number
    rs_market_20d: number   // >1 = outperform
    rs_sector_20d: number
  }

  // Sector context
  sector: {
    icb_code: string
    icb_name: string
    rank: number           // stock rank in sector
    total: number          // total stocks in sector
    top_peers: {
      symbol: string
      change_pct: number
    }[]
  } | null  // null if Unclassified

  // Performance summary
  performance: {
    stock_return: number   // % change over period
    vnindex_return: number
    sector_return: number | null
    outperform_market: boolean
    outperform_sector: boolean | null
  }

  generated_at: string
}
```

---

## Unresolved Questions

~~1. Intraday data?~~ → **Resolved: No**
~~2. Missing sector?~~ → **Resolved: Unclassified**
~~3. Correlation input?~~ → **Resolved: Daily returns**
~~4. Sector benchmark?~~ → **Resolved: Mcap-weighted avg**
~~5. Cache strategy?~~ → **Resolved: EOD pipeline**

**All questions resolved.**
