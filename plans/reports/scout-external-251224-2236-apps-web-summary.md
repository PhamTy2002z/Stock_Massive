# Scout Report: apps/web Frontend Summary

**Date:** 2024-12-24 22:36
**Scout ID:** a019e79
**Target:** /Users/typham/Documents/GitHub/Stock_Massive/apps/web

---

## 1. Directory Structure

```
apps/web/
├── public/
│   └── images/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── (auth)/             # Auth route group
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (dashboard)/        # Dashboard route group (unused?)
│   │   │   ├── charts/
│   │   │   ├── portfolio/
│   │   │   └── watchlist/
│   │   ├── analytics/          # Analytics pages
│   │   │   ├── deep-dive/
│   │   │   ├── financial-statements/
│   │   │   └── volume-spikes/
│   │   ├── api/auth/           # API routes
│   │   ├── auth/callback/      # Auth callback
│   │   └── actions/
│   ├── components/
│   │   ├── ui/                 # ShadCN UI components (21 files)
│   │   ├── dashboard/          # Dashboard-specific (27 files)
│   │   ├── layout/             # Layout components (6 files)
│   │   ├── providers/          # Context providers
│   │   ├── charts/
│   │   ├── shared/
│   │   ├── tables/
│   │   └── auth/
│   ├── hooks/                  # Custom React hooks (14 files)
│   ├── lib/                    # Utilities & API client
│   ├── services/
│   ├── types/
│   ├── config/
│   └── utils/supabase/         # Supabase client utils
├── package.json
├── tailwind.config.js
└── tsconfig.json
```

---

## 2. Pages & Routing (Next.js App Router)

| Route | File | Description |
|-------|------|-------------|
| `/` | `src/app/page.tsx` | Home dashboard - Market indices, VN30, Sectors |
| `/login` | `src/app/(auth)/login/page.tsx` | Login page |
| `/analytics/deep-dive` | `src/app/analytics/deep-dive/page.tsx` | Stock deep dive analysis |
| `/analytics/financial-statements` | `src/app/analytics/financial-statements/page.tsx` | Financial statements ranking |
| `/analytics/volume-spikes` | `src/app/analytics/volume-spikes/page.tsx` | Volume spike dashboard |
| `/auth/callback` | `src/app/auth/callback/route.ts` | Supabase auth callback |

**Route Groups:**
- `(auth)` - Authentication pages (login, register)
- `(dashboard)` - Dashboard sub-pages (charts, portfolio, watchlist) - appears partially implemented

---

## 3. Key Components

### Layout Components (`/src/components/layout/`)
| File | Purpose |
|------|---------|
| `dashboard-layout.tsx` | Main layout wrapper with Sidebar + Header |
| `dashboard-layout-client.tsx` | Client-side layout wrapper |
| `app-sidebar.tsx` | Navigation sidebar with collapsible menu |
| `dashboard-header.tsx` | Top header with search, theme toggle |
| `job-progress-bar.tsx` | **NEW** - Shows running background jobs progress |
| `notification-panel.tsx` | **NEW** - Notification panel for job status |

### Dashboard Components (`/src/components/dashboard/`)
| File | Purpose |
|------|---------|
| `market-indices.tsx` | VNINDEX, VN30, HNX, UPCOM cards |
| `vn30-overview-table.tsx` | VN30 stocks table |
| `sector-performance.tsx` | Sector performance heatmap |
| `fund-certificates.tsx` | Fund certificates list |
| `stock-detail-panel.tsx` | Stock detail side panel |
| `stock-detail-tabs.tsx` | Tabs for stock info (Finance, Volume, Shareholders) |
| `stock-search-bar.tsx` | Stock symbol search |
| `volume-spike-dashboard.tsx` | **Complex** - Full volume spike analysis dashboard |
| `volume-spike-chart.tsx` | Bar chart for volume spikes |
| `volume-spike-treemap.tsx` | Treemap visualization |
| `volume-spike-pie-chart.tsx` | Pie chart by industry |
| `volume-spike-composed-chart.tsx` | Combined volume/price chart |
| `charts-lazy.tsx` | Lazy-loaded chart components |
| `financial-statements-table.tsx` | Financial statements ranking table |

### UI Components (`/src/components/ui/`) - ShadCN
21 components including: `button`, `card`, `tabs`, `select`, `badge`, `checkbox`, `collapsible`, `dropdown-menu`, `input`, `label`, `progress`, `separator`, `sheet`, `sidebar`, `skeleton`, `sonner`, `sparkline`, `spinner`, `tooltip`, `alert`, `avatar`

---

## 4. State Management & Data Fetching

### Pattern: TanStack Query + Custom Hooks

**Query Provider Config:**
```typescript
// src/components/providers/query-provider.tsx
staleTime: 5 * 60 * 1000,  // 5 minutes
gcTime: 10 * 60 * 1000,    // 10 minutes
refetchOnWindowFocus: false,
retry: 1
```

### Custom Hooks (`/src/hooks/`)
| Hook | Purpose | Polling |
|------|---------|---------|
| `use-stock-detail.ts` | Single stock detail | 15s refetch |
| `use-market-indices.ts` | Market indices | - |
| `use-vn30-overview.ts` | VN30 stocks | - |
| `use-sector-performance.ts` | Sector data | - |
| `use-fund-certificates.ts` | Fund certificates | - |
| `use-volume-spikes.ts` | Volume spike analysis | - |
| `use-volume-analysis.ts` | Volume anomalies | - |
| `use-financial-statements.ts` | Financial rankings | - |
| `use-income-statement.ts` | Income statement | - |
| `use-balance-sheet.ts` | Balance sheet | - |
| `use-cash-flow.ts` | Cash flow | - |
| `use-shareholders.ts` | Shareholders data | - |
| `use-jobs-status.ts` | **NEW** - Background job status | 10s (running) / 60s (idle) |
| `use-mobile.tsx` | Mobile detection | - |

### Query Keys (`/src/lib/query-keys.ts`)
Centralized query key factory for cache management:
- `marketIndices`, `priceBoard`, `sectorPerformance`
- `stockDetail(symbol)`, `incomeStatement(symbol, period, limit)`
- `volumeSpikes(params)`, `financialStatements(limit, exchange)`

---

## 5. API Client (`/src/lib/api.ts`)

**Base URL:** `NEXT_PUBLIC_API_URL` or `http://localhost:8000/api/v1`

**Key Endpoints:**
- `/stocks/market-indices` - Market indices
- `/stocks/vn30-overview` - VN30 overview
- `/stocks/sector-performance` - Sector performance
- `/stocks/{symbol}/detail` - Stock detail
- `/stocks/{symbol}/financials/*` - Financial statements
- `/stocks/{symbol}/shareholders` - Shareholders
- `/stocks/{symbol}/volume-anomalies` olume analysis
- `/stocks/analytics/volume-spikes` - Volume spike detection
- `/stocks/analytics/financial-statements` - Financial rankings
- `/jobs/status` - **NEW** - Background job status

**Type Definitions:** 40+ TypeScript interfaces for API responses

---

## 6. Styling Approach

### Stack
- **TailwindCSS 3.4** - Utility-first CSS
- **ShadCN/UI** - Component library (Radix UI primitives)
- **class-variance-authority (CVA)** - Variant management
- **tailwind-merge** - Class merging
- **tailwindcss-animate** - Animation utilities

### Theme
- Dark mode default (`defaultTheme="dark"`)
- CSS variables for colors (HSL format)
- Custom sidebar colors
- Chart colors (5 variants)

### Tailwind Config Highlights
```javascript
// Custom additions
transitionTimingFunction: { 'sidebar': 'cubic-bezier(0.4, 0, 0.2, 1)' }
colors: { sidebar: {...}, chart: {...} }
```

---

## 7. Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `next` | 15.5.9 | Framework |
| `react` | ^18.3.1 | UI library |
| `@tanstack/react-query` | ^5.90.12 | Data fetching |
| `@supabase/supabase-js` | ^2.89.0 | Auth & DB |
| `recharts` | ^3.6.0 | Charts |
| `lucide-react` | ^0.561.0 | Icons |
| `next-themes` | ^0.4.6 | Theme switching |
| `sonner` | ^2.0.7 | Toast notifications |
| `date-fns` | ^4.1.0 | Date utilities |

**Radix UI Primitives:** avatar, checkbox, collapsible, dialog, dropdown-menu, label, progress, select, separator, slot, tabs, tooltip

---

## 8. Recent UI/UX Changes (from git status)

### New Files
- `job-progress-bar.tsx` - Background job progress indicator
- `notification-panel.tsx` - Job notification panel
- `progress.tsx` - Progress bar UI component
- `use-jobs-status.ts` - Job status polling hook

### Modified Files
- `dashboard-header.tsx` - Updated header
- `dashboard-layout.tsx` - Added JobProgressBar
- `api.ts` - Added job status types & fetch

---

## 9. Architecture Patterns

1. **Server Components + Client Hydration**
   - Pages use `prefetchData()` with `dehydrate()`
   - `HydrationBoundary` for SSR data transfer

2. **Lazy Loading**
   - `charts-lazy.tsx` - Dynamic imports for heavy chart components
   - `Suspense` boundaries with skeleton fallbacks

3. **Component Composition**
   - Dashboard components export from `index.ts`
   - Layout components wrap children with providers

4. **Polling Strategy**
   - Stock detail: 15s interval
   - Job status: 10s (active) / 60s (idle)
   - `refetchIntervalInBackground` for critical data

5. **Error Handling**
   - `ApiError` class with status codes
   - Graceful fallbacks in hooks (`throwOnError: false`)

---

## 10. File Counts Summary

| Category | Count |
|----------|-------|
| Pages/Routes | 6 |
| UI Components | 21 |
| Dashboard Components | 27 |
| Layout Components | 6 |
| Custom Hooks | 14 |
| Total TSX/TS files | ~90 |

---

## Unresolved Questions

1. Route group `(dashboard)` has subdirectories but unclear if actively used
2. `services/` directory exists but appears empty
3. `tables/columns/` structure suggests data table implementation in progress
