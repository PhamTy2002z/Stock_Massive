# Codebase Summary

## Project Overview
Stock Massive Web Application - A Next.js-based stock market analysis platform providing real-time market data, financial statements, trading analytics, and advanced technical indicators.

## Tech Stack
- **Frontend**: Next.js 15.1, React 19, TypeScript
- **UI Framework**: Tailwind CSS, shadcn/ui components
- **State Management**: TanStack Query (React Query)
- **Charts**: Recharts
- **Deployment**: Vercel-ready

## Architecture

### Directory Structure
```
apps/web/
├── src/
│   ├── app/              # Next.js app router pages
│   ├── components/       # React components
│   │   ├── dashboard/    # Dashboard-specific components
│   │   ├── layout/       # Layout components (header, sidebar)
│   │   ├── providers/    # React providers (query, error boundary, theme)
│   │   └── ui/           # shadcn/ui components + error fallback
│   ├── hooks/            # React Query hooks
│   ├── lib/              # API client, utilities, query keys
│   └── styles/           # Global styles
├── public/               # Static assets
└── docs/                 # Documentation
```

### Key Files
- `src/lib/api.ts` - API client with TypeScript types and fetch functions
- `src/lib/query-keys.ts` - Centralized React Query key management
- `src/hooks/` - Data fetching hooks with caching strategies
- `src/app/` - Next.js pages and routing

## API Integration

### Base Configuration
- API Base URL: `process.env.NEXT_PUBLIC_API_URL` (default: `http://localhost:8000/api/v1`)
- Error Handling: Custom `ApiError` class with status codes
- Fetch Wrapper: Centralized `fetchApi<T>()` function

### API Endpoints Coverage

#### Market Data
- `fetchPriceBoard(symbols)` - Real-time price board for multiple symbols
- `fetchMarketIndices()` - Market indices (VNINDEX, VN30, HNXINDEX, UPCOMINDEX)
- `fetchMarketOverview()` - Market overview (breadth, top gainers/losers, foreign flow, top volume)
- `fetchSectorPerformance()` - Sector performance with top gainers/losers
- `fetchFundCertificates(fundType?)` - Fund certificates data
- `fetchVN30Overview()` - VN30 stocks overview

#### Stock Search & Detail
- `searchStocks(query, limit)` - Stock symbol search
- `fetchStockDetail(symbol)` - Comprehensive stock detail (price, financials, company info)

#### Financial Statements
- `fetchIncomeStatement(symbol, period, limit)` - Income statement data
- `fetchBalanceSheet(symbol, period, limit)` - Balance sheet data
- `fetchCashFlow(symbol, period, limit)` - Cash flow statement

#### Ownership & Governance
- `fetchShareholders(symbol)` - Major shareholders data
- `fetchOfficers(symbol, filterBy)` - Company officers (working/resigned/all)
- `fetchInsiderDeals(symbol)` - Insider trading deals

#### Analytics
- `fetchFinancialStatements(limit, exchange?)` - Top companies by profit
- `fetchVolumeSpikes(params)` - Volume spike analysis by industry
- `fetchVolumeAnomalies(symbol, days)` - Intraday volume anomaly detection
- `triggerFinancialStatementsCollection()` - Trigger data collection job
- `fetchSectorPeers(symbol, limit)` - Sector peer metrics with median/premium/discount (Phase 2)
- `fetchFCFAnalysis(symbol)` - Free cash flow waterfall analysis (Phase 4)

#### Advanced Tab
**Order Flow Analysis**
- `fetchIntradayOrderStats(symbol)` - Latest-session buy/sell order statistics

**Technical Indicators**
- `fetchRatioSummary(symbol)` - Financial ratios (PE, PB, PS, ROE, ROA, ROIC, Current Ratio, D/E)

**Helper Functions**
- `formatDateParam(date)` - Convert Date to YYYY-MM-DD
- `getDateRange(days)` - Generate start/end date range

#### Jobs & System
- `fetchJobsStatus()` - Background job status monitoring

## React Hooks

### Market Hooks
- `useMarketIndices()` - Market indices with 30s stale time
- `useMarketOverview()` - Market overview with 10s stale time and auto-refresh
- `usePriceBoard(symbols)` - Price board for watchlist symbols (30s polling)
- `useSectorPerformance()` - Sector performance (5min stale)
- `useFundCertificates(fundType?)` - Fund certificates (5min stale)
- `useVN30Overview()` - VN30 overview (5min stale)

### Stock Hooks
- `useStockSearch(query, limit)` - Debounced stock search
- `useStockDetail(symbol)` - Stock detail with 1min stale time

### Financial Hooks
- `useIncomeStatement(symbol, period, limit)` - Income statement (1h stale, keepPreviousData)
- `useBalanceSheet(symbol, period, limit)` - Balance sheet (1h stale, keepPreviousData)
- `useCashFlow(symbol, period, limit)` - Cash flow (1h stale, keepPreviousData)

### Ownership Hooks
- `useShareholders(symbol)` - Shareholders (1h stale, keepPreviousData)
- `useOfficers(symbol, filterBy)` - Officers (1h stale)
- `useInsiderDeals(symbol)` - Insider deals (1h stale)

### Analytics Hooks
- `useFinancialStatements(limit, exchange?)` - Financial statements ranking (5min stale)
- `useVolumeSpikes(params)` - Volume spike analysis (1min stale)
- `useVolumeAnomalies(symbol, days)` - Volume anomaly detection (5min stale, keepPreviousData)

### Advanced Tab Hooks
**Order Flow**
- `useIntradayOrderStats(symbol)` - Latest-session order statistics

**Technical**
- `useRatioSummary(symbol)` - Ratio summary (1h stale time)

### Financial Health Hooks (Phase 2)
- `useHealthScore(symbol)` - Health score with dimensions and F-Score (5min stale, keepPreviousData)

### Trend Analysis Hooks (Phase 3)
- `useTrendMetrics(symbol)` - Historical metrics for revenue, profit, margins, ROE, ROA, cash flow (5min stale, keepPreviousData)

### Peer Comparison & FCF Hooks (Phase 4)
- `useSectorPeers(symbol, limit)` - Sector peer metrics with median/premium/discount (10min stale)
- `useFCFAnalysis(symbol)` - Free Cash Flow analysis with waterfall metrics (5min stale)

### Integration Hooks (Phase 5)
- `useFinancialDetail(symbol)` - Combined hook for parallel loading of health score, trend metrics, sector peers, and FCF analysis

## TypeScript Types

### Market Overview Types
```typescript
// Market Breadth
interface MarketBreadth {
  advances: number
  declines: number
  unchanged: number
  total: number
}

// Top Movers
interface TopMoverItem {
  symbol: string
  change_pct: number
}

// Foreign Flow
interface ForeignFlowData {
  net_buy: Array<{ symbol: string; net_value: number }>
  net_sell: Array<{ symbol: string; net_value: number }>
  total_net_value: number
}

// Top Volume
interface TopVolumeItem {
  symbol: string
  volume: number
}

// Market Overview Response
interface MarketOverviewResponse {
  market_breadth: MarketBreadth
  top_gainers: TopMoverItem[]
  top_losers: TopMoverItem[]
  foreign_flow: ForeignFlowData
  top_volume: TopVolumeItem[]
  generated_at: string
}
```

### Advanced Tab Types
```typescript
// Ratio Summary
interface RatioSummaryResponse {
  pe, pb, ps, roe, roa, roic: number | null
  current_ratio, debt_to_equity: number | null
}

// Intraday Order Stats
interface IntradayOrderStatsResponse {
  symbol, date, last_updated: string
  buy_orders, sell_orders: number
  buy_volume, sell_volume, net_volume: number
  ato_volume, atc_volume: number
}

// Health Score (Phase 2)
interface HealthScoreDimension {
  score: number
  metrics: Record<string, number | null>
}

interface FScoreDetails {
  positive_roa, positive_cfo, roa_improving: boolean
  accrual_quality, leverage_decreasing, liquidity_improving: boolean
}

interface HealthScoreResponse {
  symbol: string
  health_score: number
  dimensions: Record<string, HealthScoreDimension>
  f_score: number
  f_score_details: FScoreDetails
}

// Peer Comparison (Phase 2)
interface PeerMetrics {
  symbol, company_name: string | null
  roe, roa, pe, pb, market_cap: number | null
}

interface SectorMedian {
  median_roe, median_roa, median_pe, median_pb: number | null
}

interface SectorPeersResponse {
  symbol, icb_code, icb_name: string
  peers: PeerMetrics[]
  median: SectorMedian
}

// FCF Analysis (Phase 4)
interface FCFAnalysisResponse {
  symbol, period: string
  net_income, cfo, capex, fcf: number | null
  fcf_margin, ccc, dso, dio, dpo: number | null
  market_cap, fcf_yield: number | null
}
```

## Caching Strategy

### Stale Times
- **Real-time (30s)**: Price board, market indices
- **Near real-time (1min)**: Stock detail, volume spikes
- **Short-term (2-5min)**: Intraday order stats, sector performance, analytics
- **Long-term (1h)**: Financial statements, ratios, ownership data

### Query Keys Pattern
```typescript
queryKeys.stock(symbol) => ["stock", symbol]
queryKeys.intradayOrderStats(symbol) => ["stock", symbol, "intradayOrderStats"]
```

## Components

### Dashboard Components
- `FinanceTabContent` - Financial statements viewer with period toggle
- `OwnershipTabContent` - Shareholders and officers tables
- `InsiderDealsTabContent` - Insider trading timeline
- `VolumeSpikesDashboard` - Industry-grouped volume spike analysis
- `VolumeAnomalyChart` - Intraday volume anomaly visualization
- `FinancialStatementsComposed` - Top companies financial comparison chart

### Market Overview Components (Phase 2 - Frontend)
- `CollapsibleSection` - Reusable collapsible section with localStorage persistence
- `MarketBreadth` - Market breadth visualization (advances/declines/unchanged)
- `TopMovers` - Top gainers and losers display
- `ForeignFlow` - Foreign investor flow analysis (net buy/sell)

### Financial Health Components (Phase 2)
- `HealthScoreCard` - Main health score card with overall score, radar chart, and F-Score
- `HealthRadarChart` - Radar chart visualization for 5 financial dimensions
- `ScoreBreakdown` - Detailed breakdown of dimension scores
- `FScoreIndicator` - Piotroski F-Score indicator with 6-factor checklist

### Sector Comparison Components (Phase 2)
- `SectorSubTab` - Main container for sector comparison in Advanced tab
- `SectorOverviewCard` - Sector metadata card with ICB code/name
- `PeerComparisonTable` - Table showing peer metrics with median and premium/discount
- `PremiumBadge` - Badge indicator for premium/discount percentage

### Peer Comparison Components (Phase 4)
- `PeerComparisonCard` - Main container for peer comparison with sector context
- `PeerMetricsTable` - Table showing peer metrics (ROE, ROA, PE, PB, Market Cap)

### Trend Analysis Components (Phase 3)
- `TrendChartsCard` - Main container for trend charts
- `RevenueProfitChart` - Dual-axis chart for revenue and profit trends
- `MarginTrendChart` - Line chart for profit margins over time
- `RoeRoaChart` - ROE/ROA trend comparison
- `CashFlowChart` - Operating cash flow trend visualization

### FCF Analysis Components (Phase 4)
- `FCFAnalysisCard` - Main container for FCF analysis
- `FCFWaterfall` - Waterfall chart showing Net Income → CFO → FCF breakdown
- `CCCIndicator` - Cash Conversion Cycle indicator with DSO/DIO/DPO breakdown

### Integration Components (Phase 5)
- `FinancialDetailSheet` - Sheet overlay displaying all 4 analysis components (health, trends, peers, FCF)
- `FinancialStatementsTable` - Updated with row click handler to open detail sheet

### UI Components (shadcn/ui)
- Form controls: Button, Input, Select, Switch, Tabs
- Data display: Table, Card, Badge, Dialog, Sheet
- Layout: Sidebar, Separator, ScrollArea
- Feedback: Toast, Alert, Skeleton, Loading Spinner
- Error Handling: `ErrorFallback` - Reusable error display with compact/full variants, network error detection
- Skeleton Library: `CardSkeleton`, `ChartSkeleton`, `TableSkeleton` - Reusable loading skeletons for common UI patterns

### Provider Components
- `QueryProvider` - TanStack Query provider with default options (5min stale time, error propagation)
- `QueryErrorBoundary` - Error boundary wrapper combining React Error Boundary + Query Error Reset
- `ThemeProvider` - Dark mode theme provider

### Layout Components
- `Header` - Top navigation with market indices
- `Sidebar` - Navigation menu with route management
- `GlobalLoadingIndicator` - Global progress bar at top of viewport when any query fetching (Phase 2 UX Enhancement)

## Environment Variables
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Development Workflow

### Commands
- `npm run dev` - Start development server
- `npm run build` - Production build
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

### Code Standards
- TypeScript strict mode enabled
- ESLint + Prettier for code formatting
- React Query for all data fetching
- Centralized API types and fetch functions
- Component-based architecture with shadcn/ui

## Recent Updates (Phase 2)

### Advanced Tab API Layer (Dec 27)
- 5 TypeScript interfaces for Advanced tab data
- 5 API fetch functions with date range helpers
- 5 query keys following project conventions

### Advanced Tab React Hooks (Dec 27)
- Optimized caching for technical indicators (15min-1h stale)
- Smart date range handling for historical data (30 days default)

### Financial Health Scorecard (Dec 28)
- Added `HealthScoreResponse`, `FScoreDetails`, `HealthScoreDimension` types
- Added `fetchHealthScore()` API function
- Added `useHealthScore()` hook with 5min stale time
- Created 4 new UI components: `HealthScoreCard`, `HealthRadarChart`, `ScoreBreakdown`, `FScoreIndicator`
- Displays overall health score (0-100), 5-dimension radar chart, and Piotroski F-Score (0-9)

### Trend Analysis Components (Phase 3 - Dec 28)
- Added `TrendMetricsResponse` type to API layer
- Added `fetchTrendMetrics()` API function
- Added `useTrendMetrics()` hook (5min stale)
- Created 5 new trend components: `TrendChartsCard`, `RevenueProfitChart`, `MarginTrendChart`, `RoeRoaChart`, `CashFlowChart`
- Features: Revenue/profit trends, margin trends, profitability trends, cash flow trends

### Peer Comparison & FCF Analysis (Phase 4 - Dec 28)
- Added `FCFAnalysisResponse` types to API layer
- Added `fetchFCFAnalysis()` API function
- Added `useFCFAnalysis()` hook (5min stale)
- Created 3 new FCF components: `FCFAnalysisCard`, `FCFWaterfall`, `CCCIndicator`
- Features: FCF waterfall visualization, Cash Conversion Cycle analysis

### Integration & Testing (Phase 5 - Dec 28)
- Added `useFinancialDetail()` combined hook for parallel data loading
- Created `FinancialDetailSheet` component as sheet overlay
- Updated `FinancialStatementsTable` with row click handler to open detail sheet
- Integration: All 4 analysis sections (health, trends, peers, FCF) load in parallel when sheet opens

### Sector Comparison Dashboard (Phase 2 - Dec 28)
- Updated `SectorPeersResponse` with `median` field (`SectorMedian` type)
- Updated `fetchSectorPeers()` API function with median calculations
- Updated `useSectorPeers()` hook
- Created 4 new components in `advanced-tab/`:
  - Widgets: `PremiumBadge`, `SectorOverviewCard`, `PeerComparisonTable`
  - SubTab: `SectorSubTab`
- Features: Sector peer comparison with median benchmarking, premium/discount indicators

### Loading UX Enhancement (Phase 1 - Dec 28)
- Added `react-error-boundary` dependency
- Created `ErrorFallback` component with compact/full variants, network error detection
- Created `QueryErrorBoundary` wrapper combining React Error Boundary + Query Error Reset Boundary
- Updated `QueryProvider` with `throwOnError: true` for error propagation
- Integrated error boundary at app layout level (`layout.tsx`)
- Architecture: Global error handling for all React Query operations

### Loading UX Enhancement (Phase 2 - Dec 28)
- Added `GlobalLoadingIndicator` component - animated progress bar at top of viewport using `useIsFetching()`
- Integrated in `layout.tsx` for global loading state visualization
- Updated 7 hooks with `keepPreviousData` option for smooth data transitions:
  - `useVolumeAnalysis`, `useIncomeStatement`, `useBalanceSheet`, `useCashFlow`
  - `useShareholders`, `useHealthScore`, `useTrendMetrics`
- All updated hooks now return `isPlaceholderData` and `isFetching` for visual hints during refetches
- Benefits: No loading flickers, smooth skeleton/stale data transitions, clear global loading feedback

### Loading UX Enhancement (Phase 3 - Dec 28)
- Migrated all hooks to `useSuspenseQuery` for guaranteed data types (no undefined checks needed)
- Updated hooks include `useMarketIndices`, `useSectorPerformance`, `useVN30Overview`, `useFundCertificates`, `useStockDetail`, financial statement hooks, `useVolumeSpikes`, `useRatioSummary`, `useIntradayOrderStats`, `useHealthScore`, `useTrendMetrics`, `useSectorPeers`, `useFCFAnalysis`, and `useFinancialDetail`
- All hooks now return guaranteed data (no null/undefined)
- Components simplified with removed optional chaining and null checks
- Enabled smooth transitions with `keepPreviousData` on relevant hooks

### Loading UX Enhancement (Phase 4 - Dec 28)
- Created skeleton component library: `CardSkeleton`, `ChartSkeleton`, `TableSkeleton` in `src/components/ui/skeletons/`
- Updated all `loading.tsx` files to use skeleton library instead of generic spinners:
  - `app/loading.tsx`, `app/dashboard/loading.tsx`, `app/dashboard/[symbol]/loading.tsx`, `app/volume-spikes/loading.tsx`
- Optimized chart components with `React.memo()` for render efficiency:
  - `FinancialStatementsComposed`, `VolumeAnomalyChart`, `VolumeSpikesDashboard`, `FinancialStatementsTable`
- All chart components now utilize `isPlaceholderData` for smooth data transitions during refetches
- Benefits: Consistent loading UX, better perceived performance, reduced unnecessary re-renders

### Market Overview Frontend Components (Phase 2 Step 2 - Dec 28)
- Added `MarketOverviewResponse` and related types (`MarketBreadth`, `TopMoverItem`, `ForeignFlowData`, `TopVolumeItem`)
- Added `fetchMarketOverview()` API function for market overview data
- Added `useMarketOverview()` hook with 10s stale time and auto-refresh
- Added `marketOverview` query key to centralized key management
- Created 4 new dashboard components:
  - `CollapsibleSection` - Reusable collapsible section with localStorage persistence
  - `MarketBreadth` - Visual representation of market advances/declines/unchanged
  - `TopMovers` - Top gainers and losers display with color-coded changes
  - `ForeignFlow` - Foreign investor trading flow analysis
- Features: Real-time market breadth, top movers tracking, foreign flow monitoring
- Code Review: PASS (0 critical issues, SSR-safe, follows project patterns)

### Market Overview Integration & Polish (Phase 3 - Dec 28)
- Added `fetchMarketOverviewServer()` in `api-server.ts` for SSR data fetching with 60s ISR revalidation
- Created skeleton components library in `market-overview-skeleton.tsx`:
  - `MarketBreadthSkeleton` - Skeleton for market breadth widget
  - `TopMoversSkeleton` - Skeleton for top movers widget
  - `ForeignFlowSkeleton` - Skeleton for foreign flow widget
  - `MarketOverviewSkeleton` - Combined skeleton for all three widgets
- Updated `page.tsx` (dashboard home) with Suspense boundaries:
  - Prefetch `marketOverview` data alongside `marketIndices` and `sectorPerformance`
  - Wrapped each widget in CollapsibleSection + Suspense with dedicated skeleton
  - Granular loading states prevent layout shift and enable progressive rendering
- Updated barrel exports in `components/dashboard/index.ts` for all skeleton components
- Architecture: SSR + ISR (60s) + client-side Suspense for optimal performance
- Benefits: No layout shift, smooth loading transitions, improved perceived performance
- Code Review: PASS (0 critical issues, proper SSR/Suspense patterns, type-safe)

## Metrics
- **Total Files**: 204
- **Total Tokens**: 337,558
- **Total Characters**: 1,073,038
- **Largest Files**:
  1. tsconfig.tsbuildinfo (152,305 tokens, 45.1%)
  2. volume-spike-dashboard.tsx (8,767 tokens, 2.6%)
  3. finance-tab-content.tsx (8,520 tokens, 2.5%)
  4. ui/sidebar.tsx (6,350 tokens, 1.9%)
  5. lib/api.ts (5,615 tokens, 1.7%)

---

*Last updated: 2025-12-28 21:16*
*Generated from: repomix-output.xml*
