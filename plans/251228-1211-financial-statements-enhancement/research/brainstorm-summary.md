# Financial Statements Enhancement - Brainstorm Summary

## Context
Enhance Financial Statements tab with advanced visualization and analysis features using vnstock VCI data source.

## Agreed Features (4 Groups)

### 1. Financial Health Scorecard
- Radar chart with 5 dimensions: Profitability, Liquidity, Leverage, Efficiency, Valuation
- Scoring algorithm: normalize metrics to 0-100 scale
- VCI data available: ROE, ROA, Net Margin, Current Ratio, Quick Ratio, D/E, Interest Coverage, Asset Turnover, DSO, P/E, P/B

### 2. Trend Analysis Charts
- Revenue & Profit trend: ComposedChart (Bar + Line)
- Margin trend: AreaChart (Gross%, Operating%, Net%)
- ROE/ROA trend: LineChart
- Cash Flow trend: StackedBar (CFO, CFI, CFF)
- Data: 8 quarters from `Finance.ratio()` and `Finance.cash_flow()`

### 3. Peer Comparison
- Sector classification via ICB codes (icbCode3, icbName3)
- Compare top 5 peers in same sector
- Heatmap coloring for metrics
- Scatter plot: P/E vs ROE with bubble size = Market Cap

### 4. FCF & Cash Analysis
- FCF = CFO - CapEx (calculated)
- FCF Yield = FCF / Market Cap
- CCC = DSO + DIO - DPO (available from ratio())
- Waterfall chart: Net Income → CFO → FCF

## Approach
Hybrid: Market-wide Overview + Single Stock Deep Dive panel

## VCI Data Verification
| Feature | Feasibility | Notes |
|---------|-------------|-------|
| Health Scorecard | 100% | All metrics available |
| Trend Charts | 100% | 48 quarters data |
| Peer Comparison | 100% | ICB codes available |
| FCF Analysis | 95% | CCC may be NULL for banks |

## Rate Limit Strategy
- Background batch job at 2AM daily
- Stale-while-revalidate caching
- 150ms delay between VCI calls
- Redis cache with trading-hours-aware TTL
