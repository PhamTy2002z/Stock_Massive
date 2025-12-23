# Scout Report: apps/web Frontend Structure

**Date:** 2023-12-23  
**Scout ID:** ac0a710  
**Target:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web`

---

## 1. Directory Structure Overview

```
apps/web/
├── .env, .env.example          # Environment config
├── .next/                      # Next.js build output
├── node_modules/
├── public/                     # Static assets (logo.png)
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── (auth)/             # Auth route group
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (dashboard)/        # Dashboard route group (unused?)
│   │   │   ├── charts/
│   │   │   ├── portfolio/
│   │   │   └── watchlist/
│   │   ├── actions/
│   │   ├── analytics/          # Analytics pages
│   │   │   ├── deep-dive/
│   │   │   ├── financial-statements/
│   │   │   └── volume-spikes/
│   │   ├── api/auth/[...nextauth]/
│   │   ├── auth/callback/
│   │   ├── dashboard/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   ├── not-found.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── auth/
│   │   ├── charts/
│   │   ├── dashboard/          # 27 dashboard components
│   │   ├── layout/             # Layout components
│   │   ├── providers/          # React context providers
│   │   ├── shared/
│   │   ├── tables/
│   │   └── ui/                 # 21 ShadCN UI components
│   ├── config/                 # Empty (placeholder)
│   ├── hooks/                  # 14 custom React hooks
│   ├── lib/                    # API client, utilities
│   ├── services/
│   ├── types/                  # Empty (placeholder)
│   └── utils/supabase/         # Supabase client utils
├── components.json             # ShadCN config
├── Dockerfile, Dockerfile.prod
├── eslint.config.mjs
├── next.config.js
├── package.json
├── postcss.config.js
├── tailwind.config.js
└── tsconfig.json
```

---

## 2. Key Configuration Files

### package.json
- **Name:** stock-massive-web
- **Next.js:** 15.5.9
- **React:** 18.3.1

### next.config.js
```javascript
output: "standalone"  // Docker production builds
```

### tsconfig.json
- Path alias: `@/*` -> `./src/*`
- Target: ES2017
- Strict mode enabled

### tailwind.config.js
- Dark mode: class-based
- Custom colors: background, foreground, card, primary, secondary, muted, accent, destructive, chart-1-5, sidebar variants
- Plugin: tailwindcss-animate

---

## 3. Pages and Routing Structure

| Route | File | Description |
|-------|------|-------------|
| `/` | `app/page.tsx` | Home dashboard - Market indices, VN30 overview, sector performance, fund certificates |
| `/analytics/deep-dive` | `app/analytics/deep-dive/page.tsx` | Stock detail view with search param `?symbol=` |
| `/analytics/financial-statements` | `app/analytics/financial-statements/page.tsx` | Top 50 companies by profit |
| `/analytics/volume-spikes` | `app/analytics/volume-spikes/page.tsx` | Volume spike dashboard |
| `/login` | `app/(auth)/login/page.tsx` | Login page |
| `/auth/callback` | `app/auth/callback/route.ts` | Supabase auth callback |

### Route Groups
- `(auth)` - Authentication pages
- `(dashboard)` - Dashboard pages (charts, portfolio, watchlist) - appears partially implemented

---

## 4. Components Inventory

### UI Components (ShadCN-based) - 21 files
Location: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/`

| Component | Purpose |
|-----------|---------|
| alert.tsx | Alert messages |
| avatar.tsx | User avatars |
| badge.tsx | Status badges |
| button.tsx | Buttons with variants |
| card.tsx | Card containers |
| checkbox.tsx | Checkbox inputs |
| collapsible.tsx | Collapsible sections |
| dropdown-menu.tsx | Dropdown menus |
| input.tsx | Text inputs |
| label.tsx | Form labels |
| select.tsx | Select dropdowns |
| separator.tsx | Visual separators |
| sheet.tsx | Slide-out panels |
| sidebar.tsx | Main sidebar (24KB) |
| skeleton.tsx | Loading skeletons |
| sonner.tsx | Toast notifications |
| sparkline.tsx | Mini charts |
| spinner.tsx | Loading spinner |
| tabs.tsx | Tab navigation |
| tooltip.tsx | Tooltips |

### Dashboard Components - 27 files
Location: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/`

| Component | Size | Purpose |
|-----------|------|---------|
| finance-tab-content.tsx | 24KB | Financial statements tabs |
| financial-statements-table.tsx | 17KB | Top 50 financial table |
| fund-certificates.tsx | 7KB | Fund certificates display |
| market-indices.tsx | 3KB | Market index cards |
| sector-performance.tsx | 10KB | Sector performance chart |
| shareholders-tab-content.tsx | 9KB | Shareholders info |
| stock-company-info.tsx | 2KB | Company info panel |
| stock-detail-client.tsx | 5KB | Stock detail wrapper |
| stock-detail-empty.tsx | 1KB | Empty state |
| stock-detail-error.tsx | 1KB | Error state |
| stock-detail-panel.tsx | 2KB | Detail panel |
| stock-detail-skeleton.tsx | 2KB | Loading skeleton |
| stock-detail-tabs.tsx | 3KB | Tab navigation |
| stock-index-card.tsx | 3KB | Index card |
| stock-search-bar.tsx | 5KB | Search autocomplete |
| stock-stats-table.tsx | 4KB | Stats table |
| stock-ticker-header.tsx | 3KB | Ticker header |
| vn30-overview-table.tsx | 14KB | VN30 stocks table |
| volume-anomaly-chart.tsx | 7KB | Volume anomaly chart |
| volume-spike-chart.tsx | 4KB | Volume spike bar chart |
| volume-spike-composed-chart.tsx | 5KB | Composed chart |
| volume-spike-dashboard.tsx | 26KB | Main volume spike dashboard |
| volume-spike-pie-chart.tsx | 7KB | Pie chart |
| volume-spike-treemap.tsx | 5KB | Treemap visualization |
| volume-tab-content.tsx | 4KB | Volume tab |

### Layout Components
Location: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/`

| Component | Purpose |
|-----------|---------|
| app-sidebar.tsx | Main navigation sidebar |
| dashboard-header.tsx | Header with search |
| dashboard-layout.tsx | Layout wrapper (server) |
| dashboard-layout-client.tsx | Layout wrapper (client) |

### Provider Components
Location: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/providers/`

| Component | Purpose |
|-----------|---------|
| query-provider.tsx | TanStack Query provider |
| theme-provider.tsx | next-themes provider |

---

## 5. Custom Hooks - 14 files
Location: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/`

| Hook | Purpose |
|------|---------|
| use-balance-sheet.ts | Fetch balance sheet data |
| use-cash-flow.ts | Fetch cash flow data |
| use-financial-statements.ts | Fetch top 50 financial statements |
| use-fund-certificates.ts | Fetch fund certificates |
| use-income-statement.ts | Fetch income statement |
| use-market-indices.ts | Fetch market indices |
| use-mobile.tsx | Mobile breakpoint detection |
| use-sector-performance.ts | Fetch sector performance |
| use-shareholders.ts | Fetch shareholders data |
| use-stock-detail.ts | Fetch stock detail |
| use-vn30-overview.ts | Fetch VN30 overview |
| use-volume-analysis.ts | Volume analysis |
| use-volume-spikes.ts | Fetch volume spikes |

---

## 6. API Client / Lib Utilities
Location: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/`

### api.ts (Client-side API)
- Base URL: `NEXT_PUBLIC_API_URL` or `http://localhost:8000/api/v1`
- Generic `fetchApi<T>()` with error handling
- **Endpoints:**
  - `fetchPriceBoard(symbols)`
  - `fetchMarketIndices()`
  - `searchStocks(query, limit)`
  - `fetchStockDetail(symbol)`
  - `fetchIncomeStatement(symbol, period, limit)`
  - `fetchBalanceSheet(symbol, period, limit)`
  - `fetchCashFlow(symbol, period, limit)`
  - `fetchShareholders(symbol)`
  - `fetchOfficers(symbol, filterBy)`
  - `fetchInsiderDeals(symbol)`
  - `fetchSectorPerformance()`
  - `fetchFundCertificates(fundType)`
  - `fetchVolumeAnomalies(symbol, days)`
  - `fetchVN30Overview()`
  - `fetchFinancialStatements(limit, exchange)`
  - `triggerFinancialStatementsCollection()`
  - `fetchVolumeSpikes(params)`

### api-server.ts (Server-side API)
- Uses `server-only` package
- ISR revalidation: 60 seconds
- **Endpoints:**
  - `fetchMarketIndicesServer()`
  - `fetchSectorPerformanceServer()`
  - `fetchStockDetailServer(symbol)`

### query-keys.ts
- Centralized TanStack Query keys
- Categories: market, stock, financials, ownership, search, analytics

### utils.ts
- `cn()` - Tailwind class merge utility (clsx + tailwind-merge)

---

## 7. Styling Approach

### Stack
- **Tailwind CSS 3.4** - Utility-first CSS
- **ShadCN UI** - Component library (Radix UI primitives)
- **CSS Variables** - Theme tokens in globals.css
- **tailwindcss-animate** - Animation utilities

### Theme System
- Light/dark mode via CSS variables
- Default theme: dark
- Custom chart colors (chart-1 through chart-5)
- Sidebar-specific color tokens

### Custom CSS (globals.css)
- Sidebar animation optimization (GPU acceleration)
- Stock detail fade-in animation
- Custom thin scrollbar for tables

---

## 8. State Management Patterns

### TanStack Query (React Query)
- **Provider:** QueryProvider with default options
  - staleTime: 5 minutes
  - gcTime: 10 minutes
  - refetchOnWindowFocus: false
  - retry: 1
- **DevTools:** Enabled in development
- **Server prefetching:** HydrationBoundary pattern

### Data Flow
1. Server components prefetch data with QueryClient
2. Dehydrate state and pass to HydrationBoundary
3. Client components use custom hooks (useQuery wrappers)
4. Auto-refresh intervals on some queries (e.g., volume spikes: 3 min)

### Authentication
- Supabase SSR integration
- Middleware for session management
- Auth callback route for OAuth

---

## 9. Dependencies

### Production Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| next | 15.5.9 | React framework |
| react | 18.3.1 | UI library |
| @tanstack/react-query | 5.90.12 | Data fetching |
| @supabase/ssr | 0.8.0 | Auth SSR |
| @supabase/supabase-js | 2.89.0 | Supabase client |
| recharts | 3.6.0 | Charts |
| lucide-react | 0.561.0 | Icons |
| next-themes | 0.4.6 | Theme switching |
| sonner | 2.0.7 | Toast notifications |
| @radix-ui/* | Various | UI primitives |
| class-variance-authority | 0.7.1 | Component variants |
| clsx | 2.1.1 | Class names |
| tailwind-merge | 3.4.0 | Tailwind class merge |

### Dev Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| typescript | 5.3.0 | Type checking |
| tailwindcss | 3.4.0 | CSS framework |
| eslint | 9.39.2 | Linting |
| @tanstack/react-query-devtools | 5.91.1 | Query debugging |

---

## 10. Architecture Summary

### Pattern: Feature-based with Separation of Concerns
- **Pages:** Thin, compose components, handle SSR prefetching
- **Components:** Reusable, organized by domain (ui, dashboard, layout)
- **Hooks:** Data fetching abstraction over TanStack Query
- **Lib:** API clients, utilities, query keys

### Key Patterns
1. **Server Components + Client Components** - Hybrid rendering
2. **HydrationBoundary** - SSR data prefetching
3. **Suspense boundaries** - Loading states
4. **Barrel exports** - index.ts for clean imports
5. **Path aliases** - `@/*` for clean imports

### Navigation Structure (from app-sidebar.tsx)
- Overview (/)
- Analytics
  - Deep Dive
  - Financial Statements
  - Volume Spikes
  - Reports (placeholder)
  - Insights (placeholder)
  - Alerts (placeholder)
- Markets (placeholder)
- Charts (placeholder)
- Screener (placeholder)
- Portfolio (placeholder)
- Watchlists (placeholder)

---

## Unresolved Questions

1. Route groups `(dashboard)` with charts/, portfolio/, watchlist/ appear to have `_components` folders but unclear if pages are implemented
2. `services/` directory exists but appears empty - intended purpose?
3. `types/` directory is empty - types defined inline in api.ts instead
4. Several sidebar nav items point to `#` (placeholder) - future features?
