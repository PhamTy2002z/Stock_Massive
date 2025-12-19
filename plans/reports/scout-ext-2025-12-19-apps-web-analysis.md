# Scout Report: apps/web Frontend Analysis

**Date:** 2025-12-19
**Scope:** D:\Stock_Massive\apps\web
**Type:** Frontend Web Application Analysis

---

## 1. Project Structure

```
apps/web/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── globals.css         # Global styles + CSS variables
│   │   ├── layout.tsx          # Root layout with providers
│   │   ├── page.tsx            # Main dashboard page
│   │   └── not-found.tsx       # 404 page
│   ├── components/
│   │   ├── dashboard/          # Stock-specific components (14 files)
│   │   ├── layout/             # App layout components (4 files)
│   │   ├── providers/          # Context providers (2 files)
│   │   └── ui/                 # ShadCN UI primitives (16 files)
│   ├── hooks/                  # Custom React hooks (8 files)
│   ├── lib/                    # Utilities + API client (2 files)
│   ├── config/                 # Empty placeholder
│   ├── services/               # Empty placeholder
│   └── types/                  # Empty placeholder
├── package.json
├── components.json             # ShadCN configuration
├── tailwind.config.js
└── next.config.js
```

---

## 2. Framework and Tech Stack

| Category | Technology | Version |
|----------|------------|---------|
| Framework | Next.js (App Router) | 14.2.18 |
| Language | TypeScript | ^5.3.0 |
| UI Library | ShadCN/UI (new-york style) | - |
| Styling | TailwindCSS | ^3.4.0 |
| Icons | Lucide React | ^0.561.0 |
| Theme | next-themes | ^0.4.6 |
| Notifications | Sonner | ^2.0.7 |

**Key Radix Primitives:** Avatar, Collapsible, Dialog, Dropdown Menu, Select, Separator, Slot, Tabs, Tooltip

---

## 3. Key Pages and Components

### Pages (App Router)
| Path | File | Description |
|------|------|-------------|
| / | src/app/page.tsx | Main dashboard with market indices, stock detail, sector performance |
| 404 | src/app/not-found.tsx | Not found page |

### Dashboard Components
| Component | File | Purpose |
|-----------|------|---------|
| MarketIndices | market-indices.tsx | VN-INDEX, VN30, HNX, UPCOM cards |
| SectorPerformance | sector-performance.tsx | Top 5 gainers/losers by sector |
| StockTickerHeader | stock-ticker-header.tsx | Stock symbol, price, change display |
| StockDetailPanel | stock-detail-panel.tsx | Volume, exchange, market cap, industry |
| StockStatsTable | stock-stats-table.tsx | OHLC, 52-week stats, ratios |
| StockCompanyInfo | stock-company-info.tsx | Company sidebar info |
| StockSearchBar | stock-search-bar.tsx | Autocomplete stock search |
| StockDetailTabs | stock-detail-tabs.tsx | Overview/Finance/Shareholders tabs |
| FinanceTabContent | finance-tab-content.tsx | Income/Balance/CashFlow tables |
| ShareholdersTabContent | shareholders-tab-content.tsx | Major shareholders, officers |
| FundCertificates | fund-certificates.tsx | Fund certificate listings |

### Layout Components
| Component | File | Purpose |
|-----------|------|---------|
| DashboardLayout | dashboard-layout.tsx | Main layout wrapper with sidebar |
| AppSidebar | app-sidebar.tsx | Collapsible navigation sidebar |
| DashboardHeader | dashboard-header.tsx | Top header with search |

---

## 4. State Management Approach

**Pattern:** Custom hooks with React useState/useEffect (no Redux/Zustand)

### Custom Hooks
| Hook | File | Purpose |
|------|------|---------|
| useStockDetail | use-stock-detail.ts | Fetch stock detail with debounce (300ms) |
| useSectorPerformance | use-sector-performance.ts | Sector data with 5-min auto-refresh |
| useIncomeStatement | use-income-statement.ts | Income statement data |
| useBalanceSheet | use-balance-sheet.ts | Balance sheet data |
| useCashFlow | use-cash-flow.ts | Cash flow statement data |
| useShareholders | use-shareholders.ts | Shareholders data |
| useFundCertificates | use-fund-certificates.ts | Fund certificates data |
| useMobile | use-mobile.tsx | Mobile breakpoint detection |

**State Patterns:**
- URL state sync via useSearchParams + useRouter
- Debounced API calls (300ms)
- Auto-refresh intervals (5 min for sector data)
- Mounted ref pattern for cleanup

---

## 5. API Integration Patterns

**API Client:** src/lib/api.ts
**Base URL:** NEXT_PUBLIC_API_URL or http://localhost:8000/api/v1

### API Functions
| Function | Endpoint | Description |
|----------|----------|-------------|
| fetchMarketIndices | /stocks/market-indices | Market index data |
| fetchStockDetail | /stocks/{symbol}/detail | Comprehensive stock info |
| searchStocks | /stocks/symbols/search | Symbol search |
| fetchPriceBoard | /stocks/price-board | Real-time prices |
| fetchIncomeStatement | /stocks/{symbol}/financials/income-statement | Income data |
| fetchBalanceSheet | /stocks/{symbol}/financials/balance-sheet-detailed | Balance sheet |
| fetchCashFlow | /stocks/{symbol}/financials/cash-flow | Cash flow |
| fetchShareholders | /stocks/{symbol}/shareholders | Major shareholders |
| fetchOfficers | /stocks/{symbol}/officers | Company officers |
| fetchInsiderDeals | /stocks/{symbol}/insider-deals | Insider trading |
| fetchSectorPerformance | /stocks/sector-performance | Sector performance |
| fetchFundCertificates | /stocks/fund-certificates | Fund certificates |

**Error Handling:** Custom ApiError class with status code

---

## 6. UI Library and Styling

### ShadCN Configuration
- Style: new-york
- RSC: enabled
- Base color: neutral
- CSS Variables: enabled
- Icon library: lucide

### CSS Architecture
- TailwindCSS with HSL color system
- Dark/Light theme support (default: dark)
- CSS variables for theming in globals.css
- Custom utilities: scrollbar-thin, stock-detail-enter animation
- Sidebar transition optimizations (GPU acceleration)

---

## 7. Dependencies Summary

### Production
- next: 14.2.18
- react/react-dom: ^18.3.1
- @radix-ui/* (7 packages)
- class-variance-authority: ^0.7.1
- clsx: ^2.1.1
- lucide-react: ^0.561.0
- next-themes: ^0.4.6
- sonner: ^2.0.7
- tailwind-merge: ^3.4.0
- tailwindcss-animate: ^1.0.7

### Dev
- typescript: ^5.3.0
- tailwindcss: ^3.4.0
- eslint: ^9.39.2

---

## 8. Recent Features

1. Toast Notifications - sonner for stock search selection feedback
2. Sector Performance - ICB Level 2 sectors with top gainers/losers
3. Financial Statements - Income, balance sheet, cash flow with quarter/year toggle
4. URL State Sync - Stock symbol persisted in URL params
5. Skeleton Loading - Comprehensive loading states for all components
6. Auto-refresh - 5-minute interval for sector performance data
7. Vietnamese Localization - UI labels in Vietnamese

---

## Unresolved Questions

1. Empty placeholder directories (config/, services/, types/) - planned for future use?
2. Duplicate file app-sidebar 2.tsx - cleanup needed?
3. Auth pages mentioned in README as scaffolded but not found in current structure
