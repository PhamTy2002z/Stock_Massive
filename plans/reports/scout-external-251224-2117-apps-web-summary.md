# apps/web/ Directory Summary

**Scout Report** | ID: a1d2700 | Date: 2024-12-24

---

## 1. Directory Structure

```
apps/web/src/
├── app/                    # Next.js App Router pages
│   ├── (auth)/            # Auth route group (login, register)
│   ├── (dashboard)/       # Dashboard route group (charts, portfolio, watchlist)
│   ├── analytics/         # Analytics pages (deep-dive, financial-statements, volume-spikes)
│   ├── api/               # API routes (auth callback)
│   ├── auth/              # Auth callback handler
│   └── dashboard/         # Dashboard page
├── components/
│   ├── auth/              # Auth components
│   ├── charts/            # Chart components
│   ├── dashboard/         # Dashboard widgets (30+ components)
│   ├── layout/            # Layout components (sidebar, header)
│   ├── providers/         # Context providers (theme, query)
│   ├── shared/            # Shared components
│   ├── tables/            # Table components
│   └── ui/                # ShadCN UI primitives (20+ components)
├── hooks/                 # Custom React hooks (12 hooks)
├── lib/                   # Utilities (api.ts, api-server.ts, query-keys.ts)
├── services/              # Service layer
├── types/                 # TypeScript types
├── utils/
│   └── supabase/          # Supabase client utilities
└── middleware.ts          # Next.js middleware (auth session)
```

## 2. Framework

| Aspect | Details |
|--------|---------|
| **Framework** | Next.js 15.5.9 |
| **Router** | App Router (src/app/) |
| **React** | 18.3.1 |
| **TypeScript** | 5.3.0+ |
| **Build Output** | Standalone (Docker-ready) |

## 3. Key Components

### UI Components (ShadCN/Radix)
- `/src/components/ui/`: avatar, badge, button, card, checkbox, collapsible, dropdown-menu, input, label, select, separator, sheet, sidebar, skeleton, sonner, sparkline, spinner, tabs, tooltip

### Dashboard Components
- `MarketIndices` - Market index cards (VNINDEX, VN30, etc.)
- `VN30OverviewTable` - VN30 stocks overview
- `SectorPerformance` - Sector performance visualization
- `FundCertificates` - Fund certificates listing
- `StockDetailClient` - Stock detail panel with tabs
- `VolumeSpikeDashboard` - Volume spike analytics
- `FinancialStatementsTable` - Financial statements ranking

### Layout Components
- `DashboardLayout` / `DashboardLayoutClient` - Main layout wrapper
- `AppSidebar` - Collapsible navigation sidebar
- `DashboardHeader` - Top header with search

## 4. State Management

| Library | Purpose |
|---------|---------|
| **TanStack Query v5** | Server state, caching, prefetching |
| **React Context** | Theme provider (next-themes) |

**Query Configuration:**
- staleTime: 5 minutes
- gcTime: 10 minutes
- refetchOnWindowFocus: false
- retry: 1

## 5. API Integration

### Client-side API (`/src/lib/api.ts`)
- Base URL: `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000/api/v1`)
- Generic `fetchApi<T>()` wrapper with error handling
- Endpoints:
  - `/stocks/price-board` - Price board data
  - `/stocks/market-indices` - Market indices
  - `/stocks/{symbol}/detail` - Stock detail
  - `/stocks/{symbol}/financials/*` - Financial statements
  - `/stocks/{symbol}/shareholders` - Shareholders
  - `/stocks/{symbol}/officers` - Officers
  - `/stocks/sector-performance` - Sector performance
  - `/stocks/fund-certificates` - Fund certificates
  - `/stocks/analytics/volume-spikes` - Volume spike analytics
  - `/stocks/analytics/financial-statements` - Financial rankings

### Server-side API (`/src/lib/api-server.ts`)
- Server-only fetch functions for SSR prefetching

### Custom Hooks (`/src/hooks/`)
- `use-market-indices.ts` - Market indices data
- `use-stock-detail.ts` - Stock detail
- `use-income-statement.ts` - Income statement
- `use-balance-sheet.ts` - Balance sheet
- `use-cash-flow.ts` - Cash flow
- `use-shareholders.ts` - Shareholders
- `use-sector-performance.ts` - Sector performance
- `use-fund-certificates.ts` - Fund certificates
- `use-vn30-overview.ts` - VN30 overview
- `use-volume-spikes.ts` - Volume spikes
- `use-financial-statements.ts` - Financial statements
- `use-volume-analysis.ts` - Volume analysis

## 6. Styling

| Technology | Usage |
|------------|-------|
| **Tailwind CSS** | 3.4.0 - Primary styling |
| **ShadCN UI** | Component library (Radix primitives) |
| **tailwindcss-animate** | Animation utilities |
| **class-variance-authority** | Variant styling |
| **tailwind-merge** | Class merging |
| **clsx** | Conditional classes |

**Theme:** Dark mode default, CSS variables for theming

## 7. Dependencies

### Core
- `next`: 15.5.9
- `react` / `react-dom`: 18.3.1
- `typescript`: 5.3.0+

### UI/Styling
- `@radix-ui/*`: Dialog, Dropdown, Select, Tabs, Tooltip, etc.
- `lucide-react`: Icons
- `recharts`: Charts/visualizations
- `sonner`: Toast notifications
- `next-themes`: Theme switching

### Data/State
- `@tanstack/react-query`: 5.90.12
- `@supabase/ssr`: 0.8.0
- `@supabase/supabase-js`: 2.89.0

## 8. User-Facing Features

### Implemented Pages
1. **Home (/)** - Market overview dashboard
   - Market indices (VNINDEX, VN30, HNXINDEX, UPCOMINDEX)
   - VN30 stocks overview table
   - Sector performance
   - Fund certificates

2. **Deep Dive (/analytics/deep-dive)** - Stock analysis
   - Stock search
   - Price/volume data
   - Financial tabs (Income, Balance, Cash Flow)
   - Shareholders info
   - Volume anomaly charts

3. **Financial Statements (/analytics/financial-statements)** - Rankings
   - Top performers by net profit
   - Exchange filtering

4. **Volume Spikes (/analytics/volume-spikes)** - Volume analytics
   - Volume spike detection
   - Industry grouping
   - Treemap/charts visualization

5. **Login (/login)** - Authentication
   - Supabase auth integration

### Planned (Sidebar placeholders)
- Markets (Overview, Stocks, Indices, Sectors)
- Charts (TradingView, Technical Analysis)
- Screener (Stock Screener, Top Gainers/Losers)
- Portfolio (Holdings, Performance, Transactions)
- Watchlists

## 9. Authentication

- **Provider:** Supabase Auth
- **Implementation:** SSR-compatible (`@supabase/ssr`)
- **Middleware:** Session refresh on all routes
- **Files:**
  - `/src/utils/supabase/client.ts` - Browser client
  - `/src/utils/supabase/server.ts` - Server client
  - `/src/utils/supabase/middleware.ts` - Session middleware

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `/apps/web/src/app/layout.tsx` | Root layout with providers |
| `/apps/web/src/app/page.tsx` | Home page with SSR prefetch |
| `/apps/web/src/lib/api.ts` | API client (497 lines, 20+ endpoints) |
| `/apps/web/src/lib/query-keys.ts` | TanStack Query key factory |
| `/apps/web/src/components/layout/app-sidebar.tsx` | Navigation sidebar |
| `/apps/web/src/middleware.ts` | Auth middleware |
| `/apps/web/package.json` | Dependencies |
| `/apps/web/tailwind.config.js` | Tailwind + ShadCN config |

---

## Unresolved Questions

1. What is the purpose of `/src/app/(dashboard)/` route group vs `/src/app/analytics/`?
2. Are `/src/services/` and `/src/config/` directories in use?
3. What is the status of NextAuth integration (`/src/app/api/auth/[...nextauth]/`)?
