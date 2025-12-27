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
│   │   └── ui/           # shadcn/ui components
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

#### Advanced Tab (New)
**Order Flow Analysis**
- `fetchOrderStats(symbol, days)` - Buy/sell order statistics (30 days default)
- `fetchPriceDepth(symbol)` - Real-time bid/ask price depth (3 levels)

**Technical Indicators**
- `fetchRatioSummary(symbol)` - Financial ratios (PE, PB, PS, ROE, ROA, ROIC, Current Ratio, D/E)
- `fetchTradingStats(symbol)` - Trading statistics (volume, value, high/low)

**Money Flow Analysis**
- `fetchForeignTrading(symbol, days)` - Foreign investor trading (30 days default)
- `fetchPropTrading(symbol, days)` - Proprietary trading data (30 days default)

**Helper Functions**
- `formatDateParam(date)` - Convert Date to YYYY-MM-DD
- `getDateRange(days)` - Generate start/end date range

#### Jobs & System
- `fetchJobsStatus()` - Background job status monitoring

## React Hooks

### Market Hooks
- `useMarketIndices()` - Market indices with 30s stale time
- `usePriceBoard(symbols)` - Price board for watchlist symbols (30s polling)
- `useSectorPerformance()` - Sector performance (5min stale)
- `useFundCertificates(fundType?)` - Fund certificates (5min stale)
- `useVN30Overview()` - VN30 overview (5min stale)

### Stock Hooks
- `useStockSearch(query, limit)` - Debounced stock search
- `useStockDetail(symbol)` - Stock detail with 1min stale time

### Financial Hooks
- `useIncomeStatement(symbol, period, limit)` - Income statement (1h stale)
- `useBalanceSheet(symbol, period, limit)` - Balance sheet (1h stale)
- `useCashFlow(symbol, period, limit)` - Cash flow (1h stale)

### Ownership Hooks
- `useShareholders(symbol)` - Shareholders (1h stale)
- `useOfficers(symbol, filterBy)` - Officers (1h stale)
- `useInsiderDeals(symbol)` - Insider deals (1h stale)

### Analytics Hooks
- `useFinancialStatements(limit, exchange?)` - Financial statements ranking (5min stale)
- `useVolumeSpikes(params)` - Volume spike analysis (1min stale)
- `useVolumeAnomalies(symbol, days)` - Volume anomaly detection (5min stale)

### Advanced Tab Hooks (New - Phase 2)
**Order Flow**
- `useOrderStats(symbol, days)` - Order statistics (5min stale time)
- `usePriceDepth(symbol)` - Price depth with **30s real-time polling** (auto-refresh, stops when inactive)

**Technical**
- `useRatioSummary(symbol)` - Ratio summary (1h stale time)
- `useTradingStats(symbol)` - Trading stats (15min stale time)

**Money Flow**
- `useForeignTrading(symbol, days)` - Foreign trading (15min stale time)
- `usePropTrading(symbol, days)` - Prop trading (15min stale time)

## TypeScript Types

### Advanced Tab Types (New)
```typescript
// Price Depth
interface PriceLevel { price: number; volume: number }
interface PriceDepthResponse {
  symbol: string
  bid_1/2/3: PriceLevel
  ask_1/2/3: PriceLevel
  total_bid_volume: number
  total_ask_volume: number
  spread: number
  spread_percent: number
  timestamp: string
}

// Ratio Summary
interface RatioSummaryResponse {
  pe, pb, ps, roe, roa, roic: number | null
  current_ratio, debt_to_equity: number | null
}

// Trading Stats
interface TradingStatsResponse {
  total_volume, avg_volume: number | null
  total_value, avg_value: number | null
  high_price, low_price: number | null
}

// Order Stats
interface OrderStatsItem {
  date: string
  buy_order_count, sell_order_count: number
  buy_order_volume, sell_order_volume: number
}

// Foreign Trading
interface ForeignTradingItem {
  date: string
  buy_volume, sell_volume, net_volume: number
  buy_value, sell_value, net_value: number
}

// Prop Trading
interface PropTradingItem {
  date: string
  buy_volume, sell_volume, net_volume: number
}
```

## Caching Strategy

### Stale Times
- **Real-time (30s)**: Price board, market indices, price depth (with auto-polling)
- **Near real-time (1min)**: Stock detail, volume spikes
- **Short-term (5min)**: Order stats, sector performance, analytics
- **Medium-term (15min)**: Trading stats, foreign/prop trading
- **Long-term (1h)**: Financial statements, ratios, ownership data

### Query Keys Pattern
```typescript
queryKeys.stock(symbol) => ["stock", symbol]
queryKeys.orderStats(symbol, days) => ["stock", symbol, "orderStats", days]
queryKeys.priceDepth(symbol) => ["stock", symbol, "priceDepth"]
```

## Components

### Dashboard Components
- `FinanceTabContent` - Financial statements viewer with period toggle
- `OwnershipTabContent` - Shareholders and officers tables
- `InsiderDealsTabContent` - Insider trading timeline
- `VolumeSpikesDashboard` - Industry-grouped volume spike analysis
- `VolumeAnomalyChart` - Intraday volume anomaly visualization
- `FinancialStatementsComposed` - Top companies financial comparison chart

### UI Components (shadcn/ui)
- Form controls: Button, Input, Select, Switch, Tabs
- Data display: Table, Card, Badge, Dialog, Sheet
- Layout: Sidebar, Separator, ScrollArea
- Feedback: Toast, Alert, Skeleton, Loading Spinner

### Layout Components
- `Header` - Top navigation with market indices
- `Sidebar` - Navigation menu with route management

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

## Recent Updates (Phase 2: Frontend Hooks & API)

### Added Advanced Tab API Layer
- 6 new TypeScript interfaces for Advanced tab data
- 6 new API fetch functions with date range helpers
- 6 new query keys following project conventions

### Added Advanced Tab React Hooks
- Real-time polling for price depth (30s auto-refresh)
- Optimized caching for technical indicators (15min-1h stale)
- Smart date range handling for historical data (30 days default)

## Metrics
- **Total Files**: 113
- **Total Tokens**: 215,974
- **Total Characters**: 652,901
- **Largest Files**:
  1. tsconfig.tsbuildinfo (55.3% of tokens)
  2. volume-spike-dashboard.tsx (4.1%)
  3. finance-tab-content.tsx (4.0%)
  4. ui/sidebar.tsx (2.8%)
  5. lib/api.ts (1.9%)

---

*Last updated: 2025-12-27*
*Generated from: repomix-output.xml*
