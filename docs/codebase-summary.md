# Codebase Summary - Stock Massive

## Overview
Vietnamese stock analysis platform with monorepo architecture. Next.js frontend, FastAPI backend, PostgreSQL database.

## Repository Structure

```
Stock_Massive/
├── apps/
│   ├── web/                    # Next.js 14.2 frontend
│   └── api/                    # FastAPI backend
├── packages/
│   ├── config/                 # Shared configs (empty)
│   └── types/                  # Shared types (empty)
├── docker/                     # Docker configs
├── docs/                       # Documentation
└── docker-compose.yml
```

---

## Frontend (apps/web)

### Tech Stack
- Next.js 14.2.18 with App Router
- TypeScript 5.x
- TailwindCSS 3.4
- ShadCN/UI (new-york style)
- Radix UI primitives

### Directory Structure
```
apps/web/src/
├── app/                        # App Router pages
│   ├── (auth)/                 # Auth route group
│   │   ├── login/page.tsx      # Scaffolded
│   │   └── register/page.tsx   # Scaffolded
│   ├── (dashboard)/            # Dashboard route group
│   │   ├── layout.tsx          # Dashboard layout wrapper
│   │   ├── page.tsx            # Main dashboard (implemented)
│   │   ├── charts/page.tsx     # Scaffolded
│   │   ├── portfolio/page.tsx  # Scaffolded
│   │   └── watchlist/page.tsx  # Scaffolded
│   ├── layout.tsx              # Root layout
│   └── globals.css             # Global styles
├── components/
│   ├── ui/                     # ShadCN components (10)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── label.tsx
│   │   ├── separator.tsx
│   │   ├── sheet.tsx
│   │   ├── sidebar.tsx
│   │   ├── skeleton.tsx
│   │   ├── tooltip.tsx
│   │   └── ...
│   ├── app-sidebar.tsx         # Main navigation sidebar
│   ├── dashboard-header.tsx    # Top header bar
│   └── dashboard-layout.tsx    # Layout wrapper
├── hooks/
│   └── use-mobile.tsx          # useIsMobile() viewport hook
└── lib/
    ├── api.ts                  # API fetch utility + market data
    └── utils.ts                # cn() class merge utility
```

### Routes

| Route | Status | Description |
|-------|--------|-------------|
| `/` | Implemented | Dashboard home |
| `/login` | Scaffolded | Login page |
| `/register` | Scaffolded | Registration page |
| `/charts` | Scaffolded | Stock charts |
| `/portfolio` | Scaffolded | Portfolio tracking |
| `/watchlist` | Scaffolded | Watchlist management |

### Key Components

**Layout Components:**
- `app-sidebar.tsx` - Navigation sidebar with links
- `dashboard-header.tsx` - Top header with user menu
- `dashboard-layout.tsx` - Wraps dashboard pages

**Dashboard Components:**
- `market-indices.tsx` - Market index cards grid with loading/error states
- `stock-index-card.tsx` - Individual index card with sparkline

**ShadCN UI Components (11):**
- button, card, input, label, separator, sheet, sidebar, skeleton, sparkline, tooltip

### Hooks
- `useIsMobile()` - Returns boolean for viewport < 768px

### Utilities

**lib/utils.ts:**
- `cn()` - Merges Tailwind classes (clsx + tailwind-merge)

**lib/api.ts:**
- `fetchApi<T>()` - Generic fetch wrapper with error handling
- `fetchPriceBoard(symbols)` - Get real-time prices for symbols
- `fetchMarketIndices()` - Get VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX data
- Types: `PriceBoardItem`, `MarketIndex`, `ApiError`
- Config: `API_BASE_URL` from `NEXT_PUBLIC_API_URL` env var

---

## Backend (apps/api)

### Tech Stack
- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.0
- Alembic (migrations)
- vnstock >= 3.0.0

### Directory Structure
```
apps/api/src/
├── main.py                     # FastAPI app entry
├── api/
│   └── v1/
│       └── router.py           # API v1 router aggregator
├── stocks/
│   ├── router.py               # Stock endpoints
│   ├── service.py              # Business logic (vnstock)
│   └── schemas.py              # Pydantic models
├── auth/
│   └── (placeholder)           # Auth module (empty)
├── core/
│   ├── config.py               # Settings (env vars)
│   └── database.py             # SQLAlchemy setup
└── workers/                    # Background tasks (empty)
```

### API Endpoints

Base URL: `/api/v1`

#### Stock Symbols
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stocks/symbols` | List all stock symbols |
| GET | `/stocks/symbols/group/{group}` | Symbols by group (VN30, HNX30, etc.) |

#### Stock Data
| Method | Endpoint | Query Params | Description |
|--------|----------|--------------|-------------|
| GET | `/stocks/{symbol}/history` | `start`, `end`, `interval` | Historical OHLCV |
| GET | `/stocks/{symbol}/intraday` | - | Intraday tick data |
| GET | `/stocks/price-board` | `symbols` (list) | Real-time prices |

#### Company Info
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stocks/{symbol}/company` | Company overview |

#### Financials
| Method | Endpoint | Query Params | Description |
|--------|----------|--------------|-------------|
| GET | `/stocks/{symbol}/financials/ratios` | `period` | Financial ratios |
| GET | `/stocks/{symbol}/financials/income` | `period`, `limit` | Income statement |
| GET | `/stocks/{symbol}/financials/balance-sheet` | `period`, `limit` | Balance sheet |

### Service Layer

**StockService** (`stocks/service.py`):
- Wraps vnstock library
- Data source: VCI (Vietnam)
- Methods:
  - `get_all_symbols()` - All listed symbols
  - `get_symbols_by_group(group)` - Filter by index
  - `get_history(symbol, start, end, interval)` - OHLCV data
  - `get_intraday(symbol)` - Tick data
  - `get_price_board(symbols)` - Real-time quotes
  - `get_company_overview(symbol)` - Company info
  - `get_financial_ratios(symbol, period)` - Ratios
  - `get_income_statement(symbol, period, limit)` - P&L
  - `get_balance_sheet(symbol, period, limit)` - Balance sheet

### Schemas (Pydantic)

**Request/Response Models:**
- `StockSymbol` - Symbol info
- `StockHistory` - OHLCV record
- `IntradayTick` - Tick data
- `PriceBoard` - Real-time quote
- `CompanyOverview` - Company details
- `FinancialRatio` - Ratio data
- `IncomeStatement` - P&L line items
- `BalanceSheet` - Balance sheet items

### Database

**Configuration:**
- PostgreSQL 16
- SQLAlchemy 2.0 async
- Alembic for migrations
- Connection via asyncpg

**Status:** Configured but no models defined yet.

### Tests

**Coverage:** 30 tests
- `tests/stocks/test_router.py` - API endpoint tests
- `tests/stocks/test_service.py` - Service layer tests

---

## Shared Packages

### packages/config/
- Status: Empty placeholder
- Purpose: Shared configuration

### packages/types/
- Status: Empty placeholder
- Purpose: Shared TypeScript types

---

## Docker Configuration

### Services (docker-compose.yml)

| Service | Port | Image |
|---------|------|-------|
| db | 5432 | postgres:16 |
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
react: ^18
tailwindcss: ^3.4
@radix-ui/*: various
class-variance-authority
clsx
tailwind-merge
```

### Backend (requirements.txt)
```
fastapi
uvicorn
sqlalchemy[asyncio]>=2.0
alembic
asyncpg
pydantic>=2.0
vnstock>=3.0.0
python-jose[cryptography]
passlib[bcrypt]
pytest
httpx
```

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Frontend Layout | Done | Sidebar, header, responsive |
| ShadCN Components | Done | 11 components installed |
| Dashboard Index Cards | Done | Real API integration, loading/error states |
| API Utility | Done | Generic fetch, market indices |
| Stock API | Done | 10 endpoints working |
| vnstock Integration | Done | VCI data source |
| Auth Module | Pending | Placeholder exists |
| Database Models | Pending | SQLAlchemy configured |
| Frontend Features | Partial | Dashboard implemented, others scaffolded |
| Tests | Partial | Backend tests exist |
