# Scout Report: apps/web (Next.js Frontend)

**Generated:** 2025-12-23 23:00  
**Scope:** /Users/typham/Documents/GitHub/Stock_Massive/apps/web

---

## 1. Pages (src/app/)

| Route | File | Purpose |
|-------|------|---------|
| `/` | `src/app/page.tsx` | Homepage/Dashboard |
| `/login` | `src/app/(auth)/login/page.tsx` | Auth login page |
| `/analytics/deep-dive` | `src/app/analytics/deep-dive/page.tsx` | Stock deep-dive analysis |
| `/analytics/volume-spikes` | `src/app/analytics/volume-spikes/page.tsx` | Volume spike detection |
| `/analytics/financial-statements` | `src/app/analytics/financial-statements/page.tsx` | Financial statements ranking |

**Layout:**
- `src/app/layout.tsx` - Root layout w/ ThemeProvider, QueryProvider, Toaster

---

## 2. Components (src/components/)

### UI Components (ShadCN/Radix)
| File | Purpose |
|------|---------|
| `ui/alert.tsx` | Alert messages |
| `ui/avatar.tsx` | User avatars |
| `ui/badge.tsx` | Status badges |
| `ui/button.tsx` | Button variants |
| `ui/card.tsx` | Card containers |
| `ui/checkbox.tsx` | Checkbox input |
| `ui/collapsible.tsx` | Collapsible sections |
| `ui/dropdown-menu.tsx` | Dropdown menus |
| `ui/input.tsx` | Text input |
| `ui/label.tsx` | Form labels |
| `ui/select.tsx` | Select dropdowns |
| `ui/separator.tsx` | Visual dividers |
| `ui/sheet.tsx` | Side panels |
| `ui/sidebar.tsx` | App sidebar |
| `ui/skeleton.tsx` | Loading skeletons |
| `ui/sonner.tsx` | Toast notifications |
| `ui/sparkline.tsx` | Mini charts |
| `ui/spinner.tsx` | Loading spinner |
| `ui/tabs.tsx` | Tab navigation |
| `ui/tooltip.tsx` | Hover tooltips |

### Layout Components
| File | Purpose |
|------|---------|
| `layout/dashboard-layout.tsx` | Main dashboard wrapper |
| `layout/dashboard-layout-client.tsx` | Client-side dashboard logic |
| `layout/dashboard-header.tsx` | Top navigation header |
| `layout/app-sidebar.tsx` | Navigation sidebar |

### Dashboard/Feature Components
| File | Purpose |
|------|---------|
| `dashboard/stock-search-bar.tsx` | Stock symbol search |
| `dashboard/stock-detail-panel.tsx` | Stock info panel |
| `dashboard/stock-detail-client.tsx` | Client-side stock detail |
| `dashboard/stock-detail-tabs.tsx` | Stock info tabs |
| `dashboard/stock-detail-skeleton.tsx` | Loading state |
| `dashboard/stock-detail-error.tsx` | Error state |
| `dashboard/stock-detail-empty.tsx` | Empty state |
| `dashboard/stock-company-info.tsx` | Company info display |
| `dashboard/stock-ticker-header.tsx` | Stock ticker header |
| `dashboard/stock-stats-table.tsx` | Stats table display |
| `dashboard/stock-index-card.tsx` | Market index cards |
| `dashboard/market-indices.tsx` | Market index list |
| `dashboard/vn30-overview-table.tsx` | VN30 stocks table |
| `dashboard/sector-performance.tsx` | Sector performance |
| `dashboard/fund-certificates.tsx` | Fund certificates list |
| `dashboard/finance-tab-content.tsx` | Financial statements tab |
| `dashboard/volume-tab-content.tsx` | Volume analysis tab |
| `dashboard/shareholders-tab-content.tsx` | Shareholders tab |
| `dashboard/volume-anomaly-chart.tsx` | Volume anomaly viz |
| `dashboard/volume-spike-dashboard.tsx` | Volume spike main dashboard |
| `dashboard/volume-spike-chart.tsx` | Volume spike bar chart |
| `dashboard/volume-spike-pie-chart.tsx` | Volume spike pie viz |
| `dashboard/volume-spike-composed-chart.tsx` | Combined chart |
| `dashboard/volume-spike-treemap.tsx` | Treemap viz |
| `dashboard/financial-statements-table.tsx` | Financial statements ranking |
| `dashboard/charts-lazy.tsx` | Lazy-loaded chart components |

### Provider Components
| File | Purpose |
|------|---------|
| `providers/theme-provider.tsx` | Dark/light theme (next-themes) |
| `providers/query-provider.tsx` | TanStack Query provider |

---

## 3. Hooks (src/hooks/)

| File | Purpose |
|------|---------|
| `use-stock-detail.ts` | Fetch single stock detail |
| `use-market-indices.ts` | Fetch VNINDEX, VN30, HNX, UPCOM |
| `use-vn30-overview.ts` | Fetch VN30 stocks overview |
| `use-sector-performance.ts` | Fetch sector performance data |
| `use-fund-certificates.ts` | Fetch fund certificates |
| `use-income-statement.ts` | Fetch income statement |
| `use-balance-sheet.ts` | Fetch balance sheet |
| `use-cash-flow.ts` | Fetch cash flow statement |
| `use-shareholders.ts` | Fetch shareholders data |
| `use-volume-analysis.ts` | Fetch volume anomaly data |
| `use-volume-spikes.ts` | Fetch volume spike analytics |
| `use-financial-statements.ts` | Fetch financial statements ranking |

---

## 4. Utilities (src/lib/)

| File | Purpose |
|------|---------|
| `api.ts` | API client + all type definitions (500 LOC) |
| `api-server.ts` | Server-side API utilities |
| `query-keys.ts` | TanStack Query key factory |
| `utils.ts` | General utilities (cn helper) |

### Key Types in api.ts:
- `StockDetail` - Full stock info (price, financials, company)
- `IncomeStatementResponse`, `BalanceSheetResponse`, `CashFlowResponse`
- `ShareholdersResponse`, `OfficersResponse`
- `VolumeSpikeResponse`, `VolumeSpikeItem`
- `FinancialStatementsResponse`
- `MarketIndex`, `SectorPerformanceItem`, `VN30OverviewItem`

---

## 5. Key Features

1. **Stock Dashboard** - Homepage with market indices, VN30 overview, sector performance
2. **Stock Detail Panel** - Search + view individual stock w/ tabs (financials, volume, shareholders)
3. **Volume Spike Analytics** - Detect abnormal volume across market (treemap, pie, composed charts)
4. **Financial Statements** - Ranked list by net profit (filterable by exchange)
5. **Deep Dive** - Detailed stock analysis page

---

## 6. Recent Changes (Last 20 Commits)

- `d55692f` - Rename top performers to financial statements + UI/UX optimizations
- `fd8ac4d` - Translate financial statements page to Vietnamese
- `513d95b` - Add treemap, composed chart, tabs for volume spike dashboard
- `7be9fee` - Add pie chart for top volume spike stocks
- `404d539` - Add volume spike dashboard frontend
- `d02b919` - Add top performers analytics UI
- `0f5859f` - Add 10s refetch interval for real-time updates
- `fb05678` - Add 10s auto-refresh with loading indicators
- `e0d4211` - Remove market-context feature (vnstock rate limits)
- `5ee6ee0` - Implement Phase 4 frontend components

---

## 7. Dependencies

### Core
- `next@15.5.9` - Next.js framework
- `react@18.3.1` / `react-dom@18.3.1`
- `typescript@5.3.0`

### State & Data
- `@tanstack/react-query@5.90.12` - Server state management
- `@supabase/supabase-js@2.89.0` - Supabase client
- `@supabase/ssr@0.8.0` - SSR support

### UI Components (Radix/ShadCN)
- `@radix-ui/react-*` (avatar, checkbox, collapsible, dialog, dropdown-menu, label, select, separator, slot, tabs, tooltip)
- `class-variance-authority@0.7.1`
- `tailwind-merge@3.4.0`
- `tailwindcss@3.4.0`
- `tailwindcss-animate@1.0.7`

### Visualization
- `recharts@3.6.0` - Charts library
- `lucide-react@0.561.0` - Icons

### Utilities
- `clsx@2.1.1` - Class names
- `next-themes@0.4.6` - Theme switching
- `sonner@2.0.7` - Toast notifications

---

## File Count Summary

| Category | Count |
|----------|-------|
| Pages | 5 |
| Layouts | 1 |
| UI Components | 20 |
| Layout Components | 4 |
| Dashboard Components | 27 |
| Provider Components | 2 |
| Hooks | 12 |
| Lib/Utils | 4 |
| **Total** | **75** |

---

## Unresolved Questions

None - comprehensive scan complete.
