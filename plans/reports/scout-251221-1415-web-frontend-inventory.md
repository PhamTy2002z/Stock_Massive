# Scout Report: Web Frontend Inventory

**Date:** 2025-12-21  
**Directory:** `apps/web/`  
**Purpose:** Complete inventory of Next.js frontend application structure

---

## Overview

Next.js 15.5.9 application using App Router with TypeScript, React 18, TanStack Query, ShadCN UI, and Tailwind CSS. Configured for standalone Docker builds with server-side rendering and ISR (Incremental Static Regeneration).

---

## 1. Page Routes (`src/app/`)

### Public Routes
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/page.tsx` - **Home Dashboard**: Market indices, VN30 overview, sector performance, fund certificates
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/not-found.tsx` - **404 Page**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/layout.tsx` - **Root Layout**: Theme provider (dark default), Query provider, Toaster, Inter font

### Auth Routes (Route Group)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/(auth)/login/page.tsx` - **Login Page**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/(auth)/login/login-form.tsx` - **Login Form Component**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/(auth)/login/actions.ts` - **Login Server Actions**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/auth/callback/route.ts` - **Auth Callback Route Handler**

### Analytics Routes
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/analytics/deep-dive/page.tsx` - **Stock Deep Dive Analysis**: Default symbol VCB, detailed stock info with tabs (financials, shareholders, volume)

---

## 2. Components (`src/components/`)

### Dashboard Components (27 files)
**Market Overview:**
- `market-indices.tsx` - Displays 4 market indices (VNINDEX, VN30, HNXINDEX, UPCOMINDEX)
- `stock-index-card.tsx` - Individual index card with value/change display
- `vn30-overview-table.tsx` - Table of VN30 stocks with price/volume/market cap
- `sector-performance.tsx` - Sector performance cards with top gainers/losers
- `fund-certificates.tsx` - Fund certificate listings with NAV/price data

**Stock Detail:**
- `stock-detail-client.tsx` - Client wrapper for stock detail page
- `stock-detail-panel.tsx` - Main stock detail container
- `stock-ticker-header.tsx` - Stock symbol, price, change header
- `stock-company-info.tsx` - Company description, website, employees
- `stock-stats-table.tsx` - Key stats table (P/E, P/B, ROE, etc.)
- `stock-search-bar.tsx` - Stock symbol search with autocomplete

**Tabs & Financial Data:**
- `stock-detail-tabs.tsx` - Tab navigation (Overview, Finance, Shareholders, Volume)
- `finance-tab-content.tsx` - Income statement, balance sheet, cash flow tables
- `shareholders-tab-content.tsx` - Shareholders, officers, insider deals
- `volume-tab-content.tsx` - Volume analysis wrapper
- `volume-anomaly-chart.tsx` - Recharts visualization of volume anomalies

**UI States:**
- `stock-detail-skeleton.tsx` - Loading skeletons for all stock components
- `stock-detail-error.tsx` - Error state component
- `stock-detail-empty.tsx` - Empty state component

**Index:**
- `index.ts` - Centralized exports for all dashboard components

### Layout Components (5 files)
- `dashboard-layout.tsx` - Server-side dashboard wrapper
- `dashboard-layout-client.tsx` - Client-side layout with sidebar provider
- `dashboard-header.tsx` - Header with sidebar toggle, breadcrumbs, user menu
- `app-sidebar.tsx` - Collapsible sidebar with nav (Overview, Analytics, Markets, Charts, Screener, Portfolio) and watchlists
- `index.ts` - Layout component exports

### UI Components (18 files) - ShadCN Components
**Form Elements:**
- `input.tsx`, `label.tsx`, `checkbox.tsx`, `select.tsx`, `button.tsx`

**Layout:**
- `card.tsx`, `separator.tsx`, `sheet.tsx`, `sidebar.tsx`, `tabs.tsx`, `collapsible.tsx`

**Feedback:**
- `alert.tsx`, `skeleton.tsx`, `spinner.tsx`, `tooltip.tsx`, `sonner.tsx` (toast)

**Data Display:**
- `avatar.tsx`, `dropdown-menu.tsx`, `sparkline.tsx`

### Providers (3 files)
- `theme-provider.tsx` - next-themes integration (dark mode)
- `query-provider.tsx` - TanStack Query client setup (5min staleTime, 10min gcTime)
- `index.ts` - Provider exports

---

## 3. Hooks (`src/hooks/`)

**Stock Data:**
- `use-stock-detail.ts` - Fetch stock detail with validation (30s staleTime)
- `use-income-statement.ts` - Income statement data (quarter/year periods)
- `use-balance-sheet.ts` - Balance sheet data (quarter/year periods)
- `use-cash-flow.ts` - Cash flow statement data (quarter/year periods)
- `use-shareholders.ts` - Shareholder ownership data
- `use-fund-certificates.ts` - Fund certificate data
- `use-volume-analysis.ts` - Volume anomaly analysis data
- `use-vn30-overview.ts` - VN30 stocks overview (1min auto-refresh)
- `use-sector-performance.ts` - Sector performance metrics (1min auto-refresh)

**Utilities:**
- `use-mobile.tsx` - Responsive breakpoint detection hook

---

## 4. Libraries & Utilities (`src/lib/`)

**API Clients:**
- `api.ts` - **Client-side API**: fetchApi helper, types, endpoints for stocks, financials, market data, VN30, sectors, funds, volume anomalies
- `api-server.ts` - **Server-side API**: ISR with 60s revalidation for market indices, sector performance, stock detail
- `query-keys.ts` - TanStack Query key factory for cache management

**Utilities:**
- `utils.ts` - `cn()` helper (clsx + tailwind-merge)

### API Types Defined
- `PriceBoardItem`, `MarketIndex`, `StockSymbol`, `StockDetail`
- `IncomeStatementResponse`, `BalanceSheetResponse`, `CashFlowResponse`
- `ShareholdersResponse`, `OfficersResponse`, `InsiderDealsResponse`
- `SectorPerformanceResponse`, `FundCertificatesResponse`
- `VolumeAnomalyResponse`, `VN30OverviewResponse`

---

## 5. Configuration Files

**Build & Runtime:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/package.json` - Dependencies, scripts (dev, build, start, lint, type-check)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/next.config.js` - Standalone output for Docker
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/tsconfig.json` - TypeScript config with `@/*` path alias
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/postcss.config.js` - PostCSS with Tailwind

**Styling:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/tailwind.config.js` - Custom theme with HSL CSS variables, sidebar colors, chart colors
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/components.json` - ShadCN UI config (new-york style, RSC enabled)

---

## 6. Key Features Implemented

**Market Overview:**
- Real-time market indices (VNINDEX, VN30, HNX, UPCOM)
- VN30 stocks overview table with sorting
- Sector performance dashboard with gainers/losers
- Fund certificates listing

**Stock Analysis:**
- Stock search with autocomplete
- Detailed stock information panel
- Financial statements (Income, Balance, Cash Flow) with quarter/year toggle
- Shareholder ownership and insider deals
- Volume anomaly detection with visualization
- 52-week highs/lows, P/E, P/B, ROE, ROA ratios

**UX Features:**
- Dark theme (default)
- Responsive sidebar (collapsible)
- Loading skeletons for all components
- Error boundaries and retry mechanisms
- Toast notifications
- Auto-refresh for market data (1min intervals)

---

## 7. Component Hierarchy

```
RootLayout (layout.tsx)
├── ThemeProvider (dark default)
├── QueryProvider (TanStack Query)
└── Toaster (Sonner)
    │
    ├── Home (page.tsx)
    │   └── DashboardLayoutClient
    │       ├── MarketIndices
    │       ├── VN30OverviewTable
    │       ├── SectorPerformanceSection
    │       └── FundCertificates
    │
    └── Analytics/DeepDive (analytics/deep-dive/page.tsx)
        └── DashboardLayoutClient
            └── StockDetailClient
                ├── StockSearchBar
                ├── StockTickerHeader
                ├── StockDetailTabs
                ├── StockDetailPanel (conditional on tab)
                ├── StockStatsTable
                └── StockCompanyInfo
```

---

## 8. Dependencies Used

**Core:**
- `next@15.5.9`, `react@18.3.1`, `typescript@5.3.0`

**State & Data:**
- `@tanstack/react-query@5.90.12` - Server state management
- `@tanstack/react-query-devtools@5.91.1` - Dev tools

**UI Framework:**
- `tailwindcss@3.4.0`, `tailwindcss-animate@1.0.7`
- `@radix-ui/*` - 11 headless components
- `lucide-react@0.561.0` - Icons
- `recharts@3.6.0` - Charts
- `sonner@2.0.7` - Toast notifications
- `next-themes@0.4.6` - Theme management

**Auth:**
- `@supabase/ssr@0.8.0`, `@supabase/supabase-js@2.89.0`

**Utilities:**
- `clsx@2.1.1`, `tailwind-merge@3.4.0`, `class-variance-authority@0.7.1`
- `server-only@0.0.1` - Server-side code markers

---

## 9. File Counts Summary

- **Pages:** 8 files (3 public, 3 auth, 1 analytics, 1 layout)
- **Dashboard Components:** 27 files
- **Layout Components:** 5 files
- **UI Components:** 18 files
- **Providers:** 3 files
- **Hooks:** 10 files
- **Libraries:** 4 files
- **Config:** 6 files

**Total TypeScript/TSX Files:** 81 files

---

## 10. Architectural Patterns

**Data Fetching:**
- Server-side: ISR with 60s revalidation via `api-server.ts`
- Client-side: TanStack Query with 5min default staleTime
- Prefetching on server for initial page loads
- Auto-refresh for real-time data (market indices, sectors)

**Component Structure:**
- Feature-based organization (dashboard, layout, ui)
- Barrel exports via `index.ts` files
- Separation of client/server components
- Skeleton/error/empty states for each feature

**Styling:**
- CSS Variables for theming
- ShadCN component library
- Tailwind utility classes
- Responsive design with breakpoints

**Type Safety:**
- Shared API types in `lib/api.ts`
- Query key factory pattern
- TypeScript strict mode enabled

---

## Unresolved Questions

None. Inventory complete.

---

**End of Report**
