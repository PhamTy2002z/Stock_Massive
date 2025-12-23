# Codebase Summary - Stock Massive

Generated: 2025-12-23
Total Files: ~130 source | Frontend: 75 | Backend: 52 source + 4 migrations + 7 tests

## 1. Project Overview and Purpose

Stock Massive is a Vietnamese stock market data platform powered by the `vnstock` library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

**Goals:**
* Display Vietnamese stock data with interactive charts
* Provide sortable/filterable data tables for stock screening
* Enable portfolio tracking and watchlist management (planned)
* Secure user authentication via Supabase (scaffolded)
* Integrate `vnstock` library for comprehensive Vietnam market data
* Implement advanced analytical features (volume anomaly, volume spikes, financial statements)

## 2. Tech Stack

**Frontend:**
* **Framework**: Next.js 15.5.9 (App Router)
* **Language**: TypeScript 5.3.0
* **Styling**: TailwindCSS 3.4 + ShadCN/UI (20 Radix-based components)
* **Data Fetching**: TanStack Query v5.90.12 (5min staleTime, 10min gcTime)
* **Auth**: Supabase 2.89.0 (Google OAuth scaffolded)
* **Charts**: Recharts 3.6.0 (sparklines, treemap, pie, composed)
* **State**: useState (local), URL params (shared), next-themes (theme)
* **Notifications**: Sonner
* **Icons**: Lucide React
* **UI Components**: 20 ShadCN primitives, 27 dashboard, 4 layout, 2 providers
* **Custom Hooks**: 12 total (data fetching + responsive)
* **Pages**: 5 routes (home, login, analytics/deep-dive, analytics/volume-spikes, analytics/financial-statements)

**Backend:**
* **Framework**: FastAPI 0.100+
* **Language**: Python 3.11+
* **ORM**: SQLAlchemy 2.0 + Alembic (4 migrations)
* **Validation**: Pydantic 2.x
* **Server**: Uvicorn
* **Data Source**: vnstock >= 3.0.0 (VCI), Fmarket API
* **Scheduler**: APScheduler 4.0 (daily intraday collection, weekly financial statements)
* **Cache/Rate Limit**: Upstash Redis
* **Analytics**: Pandas, Greenlet
* **Tests**: 7 test files (46+ tests)

**Database:**
* **Primary**: PostgreSQL 16

**DevOps:**
* **Containerization**: Docker
* **Orchestration (local)**: Docker Compose (dev + prod configs)
* **Package Manager (Frontend)**: pnpm
* **Package Manager (Backend)**: pip/uv

**Design:**
* Modern + Clean philosophy
* HSL color system with CSS variables
* Dark/light themes support

## 3. Directory Structure

```
Stock_Massive/
├── apps/
│   ├── web/                     # Next.js frontend (port 3000) - 75 files
│   │   └── src/
│   │       ├── app/             # App Router (5 pages)
│   │       │   ├── (auth)/login/       # Auth login page
│   │       │   └── analytics/          # Analytics pages
│   │       │       ├── deep-dive/      # Stock deep-dive
│   │       │       ├── volume-spikes/  # Volume spike dashboard
│   │       │       └── financial-statements/  # Financial rankings
│   │       ├── components/
│   │       │   ├── ui/          # 20 ShadCN components
│   │       │   ├── dashboard/   # 27 feature components
│   │       │   ├── layout/      # 4 layout components
│   │       │   └── providers/   # 2 providers (query, theme)
│   │       ├── hooks/           # 12 custom hooks
│   │       └── lib/             # 4 utility files
│   │
│   └── api/                     # FastAPI backend (port 8000) - 52 source files
│       └── src/
│           ├── stocks/          # Feature-based modules
│           │   ├── router.py    # Main aggregation router
│           │   ├── service.py   # Core vnstock integration
│           │   ├── models.py    # SQLAlchemy models
│           │   ├── jobs.py      # Scheduled background tasks
│           │   ├── intraday_collector.py    # Intraday data + volume anomaly
│           │   ├── financial_statements_collector.py  # Weekly financial data
│           │   ├── schemas/     # 6 Pydantic schema files
│           │   ├── analytics/   # Volume spikes, financial statements
│           │   ├── market/      # Symbols, sectors, fund certificates
│           │   ├── price/       # History, intraday, indices, volume
│           │   ├── company/     # Company info, shareholders, officers
│           │   └── financial/   # Financials, ratios
│           ├── core/            # 8 core configuration files
│           │   ├── config.py, database.py, dependencies.py
│           │   ├── cache.py, redis.py, ratelimit.py
│           │   ├── scheduler.py, vnstock_wrapper.py
│           └── main.py
│       ├── alembic/             # 4 database migrations
│       ├── tests/               # 7 test files
│       └── requirements.txt
│
├── packages/                    # Shared code (placeholders)
│   ├── config/                  # Empty
│   └── types/                   # Empty
├── docker/                      # Docker configs
├── docs/                        # 9 documentation files
├── plans/                       # Project plans and reports
├── docker-compose.yml           # Dev configuration
├── docker-compose.prod.yml      # Prod configuration
└── README.md
```

## 4. Key Features and Functionality

**Current (Completed):**
* **Dashboard Layout**: Responsive sidebar, header, dark/light theme
* **Stock Detail Page**: Search, ticker header, stats, tabbed sections (Overview, Financials, Shareholders, Volume)
* **Analytics Deep-Dive**: Dedicated stock analysis page with SSR
* **Volume Spikes Dashboard**: Treemap, pie chart, composed chart, tabs visualization
* **Financial Statements Page**: Ranking table with exchange/year/quarter filters
* **Market Indices**: VN-INDEX, VN30, HNX, UPCOM cards with sparklines, 10s auto-refresh
* **VN30 Overview Table**: Real-time VN30 stocks with price, change, volume, market cap
* **Stock Data API**: 30+ endpoints via vnstock + Fmarket API
* **Financial Data**: Income statements, balance sheets, cash flow (detailed)
* **Shareholders/Officers**: Major holders, management, insider deals
* **Volume Analysis**: 5-min bar aggregation, peak period analysis
* **Volume Anomaly Detection**: Backend API + frontend visualization
* **Volume Spikes API**: Aggregated spike detection across all stocks
* **Sector Performance**: ICB Level 2 with sorting, top gainers/losers
* **Fund Certificates**: 7-item display via Fmarket API
* **Intraday Collection**: Scheduled daily (15:30 ICT) + cleanup (16:00 ICT)
* **Financial Statements Job**: Weekly (Sun 02:00 ICT) for HOSE+HNX quarterly rankings
* **Auth Scaffold**: Login page UI with Supabase Google OAuth
* **Redis Caching**: Trading-hours-aware cache for 7 high-traffic endpoints
* **Rate Limiting**: Sliding window (100/60s standard, 20/60s heavy)
* **API Documentation**: Auto-generated OpenAPI/Swagger UI

**Planned (Roadmap):**
* **Authentication**: Complete Supabase integration (JWT, protected routes)
* **Stock Charts**: TradingView Lightweight Charts integration
* **Watchlist/Portfolio**: CRUD operations, P&L tracking
* **Technical Analysis**: SMA, EMA, RSI, MACD

## 5. Architecture Patterns

**Overall:**
* **Monorepo Structure**: Simple workspace managed by pnpm
* **Microservices-like**: Frontend and Backend as distinct apps via REST API
* **Containerization**: Docker and Docker Compose for dev/prod

**Frontend (Next.js):**
* **Feature-based Organization**: Components organized by domain
* **Server Components First**: `"use client"` only when needed
* **Declarative UI**: React + ShadCN/UI for consistency
* **Data Fetching Layer**: TanStack Query for server state

**Backend (FastAPI):**
* **Domain-Driven**: Modules by business domain (market, price, company, financial, analytics)
* **Layered Architecture**: Router -> Service -> Repository/vnstock
* **Async/Await**: Native FastAPI async support
* **Dependency Injection**: FastAPI DI for reusable components
* **Scheduled Jobs**: APScheduler for background tasks

## 6. Important Files

**Frontend (apps/web/):**
* `/src/app/layout.tsx`: Root layout with providers
* `/src/app/page.tsx`: Home dashboard
* `/src/app/analytics/volume-spikes/page.tsx`: Volume spike dashboard
* `/src/app/analytics/financial-statements/page.tsx`: Financial rankings
* `/src/components/ui/`: 20 ShadCN primitives
* `/src/components/dashboard/`: 27 feature components
  * `volume-spike-dashboard.tsx`, `volume-spike-chart.tsx`, `volume-spike-pie-chart.tsx`
  * `volume-spike-composed-chart.tsx`, `volume-spike-treemap.tsx`
  * `financial-statements-table.tsx`
  * `stock-detail-panel.tsx`, `market-indices.tsx`, `vn30-overview-table.tsx`
* `/src/hooks/`: 12 custom hooks (use-volume-spikes, use-financial-statements, etc.)
* `/src/lib/api.ts`: Client API (500 LOC, all types)
* `/src/lib/query-keys.ts`: Centralized query keys

**Backend (apps/api/):**
* `/src/main.py`: FastAPI app, CORS, routing
* `/src/stocks/router.py`: Main router aggregation
* `/src/stocks/analytics/router.py`: Volume spikes, financial statements endpoints
* `/src/stocks/analytics/service.py`: Analytics business logic
* `/src/stocks/models.py`: IntradayBar, FinancialStatement models
* `/src/stocks/schemas/`: 6 schema files (analytics.py, common.py, company.py, financial.py, market.py, price.py)
* `/src/core/cache.py`: TradingHoursCache class
* `/src/core/vnstock_wrapper.py`: Rate limit protection wrapper

## 7. Development Setup

**Prerequisites:**
* Node.js 18+
* Python 3.11+
* Docker & Docker Compose
* pnpm

**Quick Start (Docker):**
```bash
git clone <repo-url>
cd Stock_Massive
docker-compose up -d
```
* Frontend: `http://localhost:3000`
* Backend API: `http://localhost:8000`
* API Docs: `http://localhost:8000/docs`

**Manual Setup:**
* **Frontend**: `cd apps/web && pnpm install && pnpm dev`
* **Backend**: `cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn src.main:app --reload`

**Database Migrations:**
```bash
cd apps/api
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## 8. Conventions and Patterns

**Code Standards:**
* **Principles**: DRY, KISS, YAGNI
* **Frontend Naming**: `kebab-case.tsx` components, `use-kebab-case.ts` hooks
* **Backend Naming**: `snake_case.py` modules, `PascalCase` classes
* **Type Hinting**: TypeScript + Python type hints throughout

**Design Guidelines:**
* HSL color system with CSS variables
* Dark/light theme via next-themes
* ShadCN/UI as standard component library
* Mobile-first responsive design

**Git Conventions:**
* Branch: `feature/`, `fix/`, `refactor/` prefixes
* Commits: Conventional format (`feat(scope): description`)

**API Design:**
* RESTful with `/api/v1/` prefix
* JSON responses with snake_case fields
* Pydantic validation
* Standardized error responses
