# Codebase Summary - Stock Massive

## Overview

Vietnamese stock market data platform with monorepo architecture. Next.js frontend, FastAPI backend, PostgreSQL database.

## Repository Structure

```
Stock_Massive/
├── apps/
│   ├── web/                    # Next.js 14.2 frontend
│   └── api/                    # FastAPI backend
├── packages/
│   ├── config/                 # Shared configs (placeholder)
│   └── types/                  # Shared types (placeholder)
├── docker/                     # Docker configs
├── docs/                       # Documentation
├── plans/                      # Plans and reports
└── docker-compose.yml
```

---

## Frontend (apps/web)

### Tech Stack

- Next.js 14.2.18 with App Router
- React 18.3.1
- TypeScript 5.3
- TailwindCSS 3.4
- ShadCN/UI (new-york style)
- Radix UI primitives
- next-themes (dark/light mode)
- TanStack Query v5.90 (server state management)

### Directory Structure

```
apps/web/src/
├── app/                        # App Router pages
│   ├── layout.tsx              # Root layout with providers
│   ├── page.tsx                # Dashboard home
│   ├── not-found.tsx           # 404 page
│   └── globals.css             # Global styles + CSS variables
├── components/
│   ├── ui/                     # ShadCN components (16)
│   ├── dashboard/              # Dashboard feature components (14)
│   ├── layout/                 # Layout components (4)
│   └── providers/              # Context providers (2)
├── hooks/
│   └── use-mobile.tsx          # useIsMobile() viewport hook
└── lib/
    ├── api.ts                  # API fetch utility + market data
    ├── query-keys.ts           # TanStack Query key factory
    └── utils.ts                # cn() class merge utility
```

### UI Components (ShadCN)

| Component | File | Purpose |
|-----------|------|---------|
| Alert | alert.tsx | Alert messages |
| Avatar | avatar.tsx | User avatars |
| Button | button.tsx | Action buttons (variants) |
| Card | card.tsx | Content containers |
| Collapsible | collapsible.tsx | Expandable sections |
| Dropdown Menu | dropdown-menu.tsx | Dropdown menus |
| Input | input.tsx | Text inputs |
| Select | select.tsx | Select dropdowns |
| Separator | separator.tsx | Visual dividers |
| Sheet | sheet.tsx | Slide-out panels |
| Sidebar | sidebar.tsx | Navigation sidebar |
| Skeleton | skeleton.tsx | Loading placeholders |
| Sonner | sonner.tsx | Toast notifications |
| Sparkline | sparkline.tsx | Mini charts |
| Tabs | tabs.tsx | Tab navigation |
| Tooltip | tooltip.tsx | Hover tooltips |

### Dashboard Components

| Component | File | Purpose |
|-----------|------|---------|
| MarketIndices | market-indices.tsx | Market index cards grid |
| StockIndexCard | stock-index-card.tsx | Individual index card |
| StockSearchBar | stock-search-bar.tsx | Symbol search with debounce |
| StockTickerHeader | stock-ticker-header.tsx | Stock price header |
| StockDetailPanel | stock-detail-panel.tsx | Stats grid (volume, cap, etc.) |
| StockDetailTabs | stock-detail-tabs.tsx | Tab container |
| StockDetailSkeleton | stock-detail-skeleton.tsx | Loading skeleton |
| StockDetailEmpty | stock-detail-empty.tsx | Empty state |
| StockDetailError | stock-detail-error.tsx | Error state |
| StockCompanyInfo | stock-company-info.tsx | Company overview |
| StockStatsTable | stock-stats-table.tsx | Financial stats table |
| FinanceTabContent | finance-tab-content.tsx | Financial statements tab |
| ShareholdersTabContent | shareholders-tab-content.tsx | Shareholders/officers tab |
| SectorPerformance | sector-performance.tsx | Sector performance table with sorting |

### Layout Components

| Component | File | Purpose |
|-----------|------|---------|
| AppSidebar | app-sidebar.tsx | Main navigation sidebar |
| DashboardHeader | dashboard-header.tsx | Top header bar |
| DashboardLayout | dashboard-layout.tsx | Layout wrapper |

### Hooks (8 custom hooks)

| Hook | Purpose |
|------|---------|
| `useIsMobile()` | Returns boolean for viewport < 768px |
| `useStockDetail()` | Fetches comprehensive stock detail data |
| `useSectorPerformance()` | Fetches sector performance with 5-min auto-refresh |
| `useIncomeStatement()` | Fetches income statement data |
| `useBalanceSheet()` | Fetches balance sheet data |
| `useCashFlow()` | Fetches cash flow statement data |
| `useShareholders()` | Fetches shareholders and officers data |
| `useFundCertificates()` | Fetches fund certificates data |

### Utilities

**lib/utils.ts:**
- `cn()` - Merges Tailwind classes (clsx + tailwind-merge)

**lib/api.ts:**
- `fetchApi<T>()` - Generic fetch wrapper with error handling
- `fetchPriceBoard(symbols)` - Get real-time prices
- `fetchMarketIndices()` - Get market indices data
- `fetchStockDetail(symbol)` - Get comprehensive stock detail
- `searchSymbols(query)` - Search stocks by symbol/name
- `fetchSectorPerformance()` - Get sector performance data
- `fetchFundCertificates()` - Get fund certificates data
- `fetchIncomeStatement()` - Get income statement
- `fetchBalanceSheet()` - Get balance sheet
- `fetchCashFlow()` - Get cash flow statement
- `fetchShareholders()` - Get shareholders data
- Types: `PriceBoardItem`, `MarketIndex`, `StockDetail`, `SectorPerformanceItem`, `SectorPerformanceResponse`, `ApiError`

---

## Backend (apps/api)

### Tech Stack

- Python 3.11+
- FastAPI 0.100+
- Pydantic v2
- SQLAlchemy 2.0 (async)
- Alembic (migrations)
- APScheduler 4.0
- vnstock >= 3.0.0

### Directory Structure

```
apps/api/src/
├── main.py                     # FastAPI app entry
├── api/
│   └── v1/
│       └── router.py           # API v1 router aggregator
├── stocks/
│   ├── router.py               # Stock endpoints (27)
│   ├── service.py              # Business logic (vnstock)
│   ├── schemas.py              # Pydantic models
│   ├── models.py               # SQLAlchemy models
│   ├── jobs.py                 # Scheduled jobs
│   └── intraday_collector.py   # Intraday data collection
├── core/
│   ├── config.py               # Settings (env vars)
│   ├── database.py             # SQLAlchemy setup
│   ├── dependencies.py         # FastAPI dependencies
│   └── scheduler.py            # APScheduler setup
└── workers/                    # Background tasks (placeholder)
```

### API Endpoints (27)

Base URL: `/api/v1/stocks`

#### Symbol Listing
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/symbols` | List all symbols (filter by exchange) |
| GET | `/symbols/group/{group}` | Symbols by group (VN30, HNX30) |
| GET | `/symbols/search` | Search by ticker or company name |

#### Price Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{symbol}/history` | Historical OHLCV |
| GET | `/{symbol}/intraday` | Intraday tick data |
| GET | `/market-indices` | VN-INDEX, VN30, HNX, UPCOM |
| GET | `/price-board` | Real-time prices (multiple symbols) |
| GET | `/{symbol}/detail` | Comprehensive stock detail |

#### Company & Financials
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{symbol}/company` | Company overview |
| GET | `/{symbol}/financials/ratios` | Financial ratios |
| GET | `/{symbol}/financials/income` | Income statement (simple) |
| GET | `/{symbol}/financials/income-statement` | Income statement (detailed) |
| GET | `/{symbol}/financials/balance-sheet` | Balance sheet (simple) |
| GET | `/{symbol}/financials/balance-sheet-detailed` | Balance sheet (detailed) |
| GET | `/{symbol}/financials/cash-flow` | Cash flow statement |

#### Shareholders & Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{symbol}/shareholders` | Major shareholders |
| GET | `/{symbol}/officers` | Company officers |
| GET | `/{symbol}/insider-deals` | Insider trading deals |
| GET | `/{symbol}/volume-analysis` | Volume pattern analysis |
| POST | `/intraday/collect` | Trigger intraday collection |

#### Sector & Fund Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sector-performance` | Sector performance (ICB Level 2) |
| GET | `/fund-certificates` | Fund certificates data |

### Service Layer

**StockService** (`stocks/service.py`):
- Wraps vnstock library
- Data source: VCI (Vietnam)
- Singleton pattern via `get_stock_service()`

**Key Methods:**
- `get_history()` - Historical OHLCV data
- `get_intraday()` - Intraday tick data
- `get_company_overview()` - Company info
- `get_financial_ratios()` - Financial ratios
- `get_income_statement_detailed()` - Income statement
- `get_balance_sheet_detailed()` - Balance sheet
- `get_cash_flow_detailed()` - Cash flow
- `get_shareholders()` - Major shareholders
- `get_officers()` - Company officers
- `get_insider_deals()` - Insider trading
- `get_sector_performance()` - Sector performance aggregation (Phase 1)

### Database Models

**IntradayBar** (`stocks/models.py`):
- 5-minute OHLCV bars
- Composite primary key: (symbol, timestamp)
- Indexes for efficient querying

### Scheduled Jobs

**Intraday Collection** (`stocks/jobs.py`):
- Runs daily at 15:30 ICT (after market close)
- Collects tick data, aggregates to 5-min bars
- Stores in PostgreSQL via upsert

---

## Docker Configuration

### Services (docker-compose.yml)

| Service | Port | Image |
|---------|------|-------|
| db | 5432 | postgres:16-alpine |
| api | 8000 | ./apps/api |
| web | 3000 | ./apps/web |

### Features

- Health checks configured
- Hot-reload for development
- Volume mounts for code changes
- Network isolation

---

## Dependencies

### Frontend (package.json)

```
next: 14.2.18
react: ^18.3.1
typescript: ^5.3
tailwindcss: ^3.4
@radix-ui/*: various
@tanstack/react-query: ^5.90.12
@tanstack/react-query-devtools: ^5.90.12
class-variance-authority
clsx
tailwind-merge
next-themes
lucide-react
sonner
```

### Backend (requirements.txt)

```
fastapi>=0.100
uvicorn
sqlalchemy[asyncio]>=2.0
alembic
asyncpg
pydantic>=2.0
vnstock>=3.0.0
apscheduler>=4.0
python-jose[cryptography]
passlib[bcrypt]
pytest
httpx
```

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Frontend Layout | Done | Sidebar, header, responsive, themes |
| ShadCN Components | Done | 16 components installed |
| Dashboard Components | Done | 14 feature components |
| Stock Detail Page | Done | Search, header, stats, tabs |
| Market Indices | Done | Real API integration |
| Sector Performance | Done | Full-stack: API + hook + UI component |
| API Utility | Done | Generic fetch, error handling |
| Stock API | Done | 27 endpoints working |
| vnstock Integration | Done | VCI data source |
| Database Models | Done | IntradayBar model |
| Scheduler | Done | APScheduler 4.0 |
| Intraday Collection | Done | 5-min bar aggregation |
| Auth Module | Pending | Placeholder exists |
| Frontend Features | Partial | Dashboard done, others scaffolded |
| Tests | Partial | Backend tests exist |
