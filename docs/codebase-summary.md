# Codebase Summary - Stock Massive

Generated: 2024-12-24
Total Files: 399 analyzed | Frontend: 85+ TS/TSX | Backend: 55+ Python + 4 migrations + 17 tests

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
* **Styling**: TailwindCSS 3.4 + ShadCN/UI (22 Radix-based components)
* **Data Fetching**: TanStack Query v5.90.12 (5min staleTime, 10min gcTime)
* **Auth**: Supabase 2.89.0 (Google OAuth scaffolded)
* **Charts**: Recharts 3.6.0 (sparklines, treemap, pie, composed)
* **State**: useState (local), URL params (shared), next-themes (theme)
* **Notifications**: Sonner
* **Icons**: Lucide React
* **UI Components**: 22 ShadCN primitives, 26 dashboard, 6 layout, 2 providers
* **Custom Hooks**: 14 total (data fetching + responsive + job status)
* **Pages**: 5 routes (home, login, analytics/deep-dive, analytics/volume-spikes, analytics/financial-statements)

**Backend:**
* **Framework**: FastAPI 0.100+
* **Language**: Python 3.11+
* **ORM**: SQLAlchemy 2.0 + Alembic (4 migrations)
* **Validation**: Pydantic 2.x
* **Server**: Uvicorn
* **Data Source**: vnstock >= 3.0.0 (VCI), Fmarket API
* **Scheduler**: APScheduler 4.0 (daily intraday collection, weekly financial statements)
* **Cache/Rate Limit**: Upstash Redis (trading-hours-aware TTL)
* **Analytics**: Pandas, Greenlet
* **Tests**: 17 test files (coverage on critical paths)

**Database:**
* **Primary**: Supabase PostgreSQL (cloud-hosted with SSL, connection pooling)
* **Connection**: DATABASE_URL (async via pooler), DATABASE_URL_DIRECT (sync direct)

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
│   ├── web/                     # Next.js frontend (port 3000) - 85+ files
│   │   └── src/
│   │       ├── app/             # App Router (5 pages)
│   │       │   ├── (auth)/login/       # Auth login page (scaffolded)
│   │       │   └── analytics/          # Analytics pages
│   │       │       ├── deep-dive/      # Stock deep-dive analysis
│   │       │       ├── volume-spikes/  # Volume spike dashboard
│   │       │       └── financial-statements/  # Financial rankings
│   │       ├── components/
│   │       │   ├── ui/          # 22 ShadCN components (button, card, tabs, progress, etc.)
│   │       │   ├── dashboard/   # 26 feature components (market-indices, stock-detail-*, volume-spike-*, etc.)
│   │       │   ├── layout/      # 6 layout components (sidebar, header, job-progress-bar, notification-panel)
│   │       │   └── providers/   # 2 providers (query, theme)
│   │       ├── hooks/           # 14 custom hooks (use-stock-detail, use-volume-spikes, use-jobs-status, etc.)
│   │       └── lib/             # 4 utility files (api.ts, query-keys.ts, utils.ts, api-server.ts)
│   │
│   └── api/                     # FastAPI backend (port 8000) - 55+ source files
│       └── src/
│           ├── stocks/          # Feature-based modules
│           │   ├── router.py    # Main aggregation router (30+ endpoints)
│           │   ├── service.py   # Core vnstock integration
│           │   ├── models.py    # SQLAlchemy models (StockDailyOHLCV, IntradayBar, FinancialStatement)
│           │   ├── jobs.py      # Scheduled background tasks (APScheduler)
│           │   ├── jobs_router.py # Job status polling API
│           │   ├── intraday_collector.py    # Intraday data + volume anomaly
│           │   ├── financial_statements_collector.py  # Weekly financial data
│           │   ├── schemas/     # 6 Pydantic schema files
│           │   │   ├── analytics.py   # VolumeSpikeItem, FinancialStatementItem
│           │   │   ├── common.py      # Shared types
│           │   │   ├── company.py     # Company, shareholders, officers
│           │   │   ├── financial.py   # Income, balance sheet, cash flow
│           │   │   ├── market.py      # VN30Overview, sectors, fund certificates
│           │   │   └── price.py       # OHLCV, intraday, volume
│           │   ├── analytics/   # Volume spikes, financial statements
│           │   │   ├── router.py
│           │   │   └── service.py
│           │   ├── market/      # Symbols, sectors, fund certificates
│           │   │   ├── router.py
│           │   │   └── service.py
│           │   ├── price/       # History, intraday, indices, volume
│           │   │   ├── router.py
│           │   │   ├── service.py
│           │   │   └── cache.py
│           │   ├── company/     # Company info, shareholders, officers
│           │   │   ├── router.py
│           │   │   └── service.py
│           │   └── financial/   # Financials, ratios
│           │       ├── router.py
│           │       └── service.py
│           ├── core/            # 9 core configuration files
│           │   ├── config.py         # Pydantic settings with Supabase support
│           │   ├── database.py       # SQLAlchemy async engine (SSL auto-detection)
│           │   ├── dependencies.py   # FastAPI dependencies
│           │   ├── cache.py          # TradingHoursCache class
│           │   ├── redis.py          # Upstash Redis client
│           │   ├── ratelimit.py      # Rate limiting middleware
│           │   ├── scheduler.py      # APScheduler configuration
│           │   ├── vnstock_wrapper.py # Rate limit protection wrapper
│           │   └── job_status_store.py  # Job progress tracking
│           └── main.py
│       ├── alembic/             # 4 database migrations (Supabase-aware)
│       │   ├── env.py           # DATABASE_URL_DIRECT support
│       │   └── versions/
│       │       ├── d945d0cac5ec_add_stock_daily_ohlcv_table.py
│       │       ├── 60811b8fd9e3_create_stock_intraday_bars_table.py
│       │       ├── 6948fc67_add_top_performers_table.py
│       │       └── a1b2c3d4_rename_top_performers_to_financial_statements.py
│       ├── tests/               # 17 test files
│       │   ├── test_analytics_api.py
│       │   ├── test_database_phase01.py
│       │   ├── test_financial_statements_collector.py
│       │   ├── test_intraday_collector.py
│       │   ├── test_job_status_store.py
│       │   ├── test_jobs_router.py
│       │   ├── test_ratelimit.py
│       │   ├── test_scheduler.py
│       │   ├── test_sector_performance.py
│       │   ├── test_stocks_router.py
│       │   ├── test_stocks_service.py
│       │   ├── test_trading_hours_cache.py
│       │   ├── test_volume_analysis.py
│       │   ├── test_volume_anomaly_api.py
│       │   └── test_volume_anomaly_detection.py
│       └── requirements.txt
│
├── packages/                    # Shared code (placeholders)
│   ├── config/                  # Empty (.gitkeep)
│   └── types/                   # Empty (.gitkeep)
├── docker/                      # Docker configs (placeholder)
├── docs/                        # 9 documentation files
│   ├── project-overview-pdr.md
│   ├── code-standards.md
│   ├── codebase-summary.md
│   ├── design-guidelines.md
│   ├── deployment-guide.md
│   ├── system-architecture.md
│   ├── project-roadmap.md
│   ├── tech-stack.md
│   ├── vps-deployment-guide.md
│   └── journals/
│       └── 251224-ui-ux-performance-optimization-archived.md
├── plans/                       # Project plans and reports
│   ├── 251224-2358-deep-dive-improvements/
│   └── archive/                 # 15+ completed plan folders
├── docker-compose.yml           # Dev configuration
├── docker-compose.prod.yml      # Prod configuration
└── README.md
```

## 4. Key Features and Functionality

**Current (Completed):**
* **Dashboard Layout**: Responsive sidebar, header, dark/light theme toggle
* **Stock Detail Page**: Search bar, ticker header, stats panel, tabbed sections (Overview, Financials, Shareholders, Volume)
* **Analytics Deep-Dive**: Dedicated stock analysis page with SSR
* **Volume Spikes Dashboard**: Treemap, pie chart, composed chart, tabs visualization
* **Financial Statements Page**: Ranking table with exchange/year/quarter filters
* **Market Indices**: VN-INDEX, VN30, HNX, UPCOM cards with sparklines, 10s auto-refresh
* **VN30 Overview Table**: Real-time VN30 stocks with price, change, volume, market cap
* **Stock Data API**: 30+ REST endpoints via vnstock + Fmarket API
* **Financial Data**: Income statements, balance sheets, cash flow (detailed)
* **Shareholders/Officers**: Major holders, management, insider deals
* **Volume Analysis**: 5-min bar aggregation, peak period analysis
* **Volume Anomaly Detection**: Backend API + frontend visualization in stock detail tabs
* **Volume Spikes API**: Aggregated spike detection across all stocks
* **Sector Performance**: ICB Level 2 with sorting, top gainers/losers
* **Fund Certificates**: 7-item display via Fmarket API
* **Intraday Collection**: Scheduled daily (15:30 ICT) + cleanup (16:00 ICT)
* **Daily OHLCV Collection**: Scheduled daily (17:00 ICT)
* **Financial Statements Job**: Weekly (Sun 02:00 ICT) for HOSE+HNX quarterly rankings
* **Job Status API**: `/api/v1/jobs/status` for progress polling
* **Startup Job Recovery**: Non-blocking missed job recovery on API startup
* **Supabase Migration**: PostgreSQL migrated to Supabase cloud (SSL, pooling)
* **Job Progress UI**: Progress bar + notification panel in frontend
* **Auth Scaffold**: Login page UI with Supabase Google OAuth (logic pending)
* **Redis Caching**: Trading-hours-aware cache for 7 high-traffic endpoints
* **Rate Limiting**: Sliding window (100/60s standard, 20/60s heavy)
* **API Documentation**: Auto-generated OpenAPI/Swagger UI

**Planned (Roadmap):**
* **Authentication**: Complete Supabase integration (JWT, protected routes)
* **Stock Charts**: TradingView Lightweight Charts integration
* **Watchlist/Portfolio**: CRUD operations, P&L tracking
* **Technical Analysis**: SMA, EMA, RSI, MACD indicators

## 5. Architecture Patterns

**Overall:**
* **Monorepo Structure**: Simple workspace managed by pnpm
* **REST API**: Frontend and Backend communicate via REST API
* **Containerization**: Docker and Docker Compose for dev/prod

**Frontend (Next.js):**
* **Feature-based Organization**: Components organized by domain (dashboard, layout, ui, providers)
* **Server Components First**: `"use client"` only when needed (hooks, event handlers)
* **Declarative UI**: React + ShadCN/UI for consistency
* **Data Fetching Layer**: TanStack Query for server state management
* **Separation of Concerns**: API client (lib/api.ts), hooks (hooks/), components (components/)

**Backend (FastAPI):**
* **Domain-Driven**: Modules by business domain (market, price, company, financial, analytics)
* **Layered Architecture**: Router -> Service -> vnstock/Repository
* **Async/Await**: Native FastAPI async support
* **Dependency Injection**: FastAPI DI for reusable components
* **Scheduled Jobs**: APScheduler for background tasks (intraday collection, financial statements)
* **Caching**: TradingHoursCache with Upstash Redis (shorter TTL during trading hours)
* **Rate Limiting**: Sliding window algorithm with Redis

## 6. Important Files

**Frontend (apps/web/):**
* `/src/app/layout.tsx`: Root layout with providers (QueryProvider, ThemeProvider)
* `/src/app/page.tsx`: Home dashboard with market indices, VN30 overview, stock search
* `/src/app/analytics/volume-spikes/page.tsx`: Volume spike dashboard
* `/src/app/analytics/financial-statements/page.tsx`: Financial rankings
* `/src/components/ui/`: 22 ShadCN primitives (button, card, tabs, skeleton, progress, etc.)
* `/src/components/dashboard/`: 26 feature components
  * `market-indices.tsx`, `stock-detail-panel.tsx`, `vn30-overview-table.tsx`
  * `volume-spike-dashboard.tsx`, `volume-spike-treemap.tsx`, `volume-spike-pie-chart.tsx`, `volume-spike-composed-chart.tsx`
  * `financial-statements-table.tsx`
* `/src/components/layout/`: 6 layout components
  * `app-sidebar.tsx`, `dashboard-header.tsx`, `job-progress-bar.tsx`, `notification-panel.tsx`
* `/src/hooks/`: 14 custom hooks
  * `use-stock-detail.ts`, `use-market-indices.ts`, `use-volume-spikes.ts`, `use-financial-statements.ts`
  * `use-jobs-status.ts` (job progress polling)
* `/src/lib/api.ts`: Client API (500+ LOC, all endpoints typed with Zod)
* `/src/lib/query-keys.ts`: Centralized query keys for TanStack Query

**Backend (apps/api/):**
* `/src/main.py`: FastAPI app, CORS, routing, scheduler startup, job recovery
* `/src/stocks/router.py`: Main router aggregation (30+ endpoints)
* `/src/stocks/analytics/router.py`: Volume spikes, financial statements endpoints
* `/src/stocks/analytics/service.py`: Analytics business logic
* `/src/stocks/jobs_router.py`: Job status polling API
* `/src/stocks/models.py`: SQLAlchemy models (StockDailyOHLCV, IntradayBar, FinancialStatement)
* `/src/stocks/schemas/`: 6 schema files
  * `analytics.py` - FinancialStatementItem, VolumeSpikeItem
  * `common.py` - Shared types
  * `company.py` - Company, shareholders, officers
  * `financial.py` - Income, balance sheet, cash flow
  * `market.py` - VN30Overview, sectors, fund certificates
  * `price.py` - OHLCV, intraday, volume
* `/src/core/config.py`: Pydantic settings with Supabase support
* `/src/core/database.py`: SQLAlchemy async engine with SSL auto-detection
* `/src/core/cache.py`: TradingHoursCache class (trading-hours-aware TTL)
* `/src/core/vnstock_wrapper.py`: Rate limit protection wrapper
* `/src/core/job_status_store.py`: In-memory job progress tracking
* `/alembic/env.py`: Alembic config with DATABASE_URL_DIRECT support

## 7. Development Setup

**Prerequisites:**
* Docker 20.10+
* Docker Compose 2.0+
* (Optional) Node.js 18+, Python 3.11+, pnpm

**Quick Start (Docker):**
```bash
git clone <repo-url>
cd Stock_Massive

# Copy and configure environment
cp .env.example .env
# Edit .env with Supabase DATABASE_URL

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head
```

* Frontend: `http://localhost:3000`
* Backend API: `http://localhost:8000`
* API Docs: `http://localhost:8000/docs`

**Manual Setup (Local Development):**
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
* Skeleton loading patterns

**Git Conventions:**
* Branch: `feature/`, `fix/`, `refactor/` prefixes
* Commits: Conventional format (`feat(scope): description`)

**API Design:**
* RESTful with `/api/v1/` prefix
* JSON responses with snake_case fields
* Pydantic validation
* Standardized error responses (HTTPException with detail)

**Testing:**
* **Backend**: pytest + TestClient (17 test files)
* **Frontend**: Vitest + React Testing Library (planned)
* **Coverage target**: 80%+ on critical paths

## 9. Data Flow Examples

### Stock Detail Request
1. User searches for stock symbol via `StockSearchBar`
2. Frontend calls `/api/v1/stocks/{symbol}/detail` using `useStockDetail` hook
3. Backend fetches from vnstock (price board, company overview, ratios)
4. Data combined into `StockDetail` response
5. Frontend renders with `stock-detail-*` components (header, panel, tabs)

### Volume Spikes Dashboard
1. User navigates to `/analytics/volume-spikes`
2. Frontend calls `/api/v1/stocks/analytics/volume-spikes` using `useVolumeSpikes` hook
3. Backend queries aggregated volume data from vnstock
4. Returns top volume spike stocks with metrics
5. Frontend renders treemap, pie chart, composed chart with tabs

### Scheduled Intraday Collection
1. APScheduler triggers at 15:30 ICT daily
2. `IntradayCollector` fetches tick data for all HOSE/HNX symbols via vnstock
3. Ticks aggregated to 5-minute OHLCV bars
4. Bars upserted to Supabase PostgreSQL (`intraday_bars` table)
5. Volume anomaly detection performed on collected data
6. Data available via `/volume-anomalies` endpoint

## 10. Recent Major Changes (December 2024)

* **Supabase Migration** (Dec 24): Migrated from local PostgreSQL to Supabase cloud with SSL, connection pooling
* **Job Progress UI** (Dec 24): Added progress bar and notification panel in frontend
* **Job Status API** (Dec 24): `/api/v1/jobs/status` for polling background job progress
* **Startup Job Recovery** (Dec 24): Non-blocking missed job recovery on API startup
* **Volume Spikes Dashboard** (Dec 23): Treemap, pie chart, composed chart visualization
* **Financial Statements Ranking** (Dec 22-23): Top companies by net profit with filters
* **Daily OHLCV Collection** (Dec 24): Scheduled job at 17:00 ICT
* **Redis Caching** (Dec 20): Trading-hours-aware cache for 7 high-traffic endpoints
* **Rate Limiting** (Dec 20): Sliding window algorithm (100/60s standard, 20/60s heavy)

## 11. Known Issues and Tech Debt

* **Packages folder**: Placeholder only, not actively used
* **Frontend tests**: Not yet implemented (Vitest planned)
* **E2E tests**: Not yet implemented (Playwright planned)
* **CI/CD**: No pipeline configured
* **Auth logic**: Scaffolded but not fully implemented
* **Charts page**: Route exists but TradingView integration pending
* **Portfolio/Watchlist**: Routes exist but not implemented

## 12. Performance Metrics

* **Page Load Target**: <2s
* **API Response Target**: <200ms (p95)
* **Bundle Size Target**: <200kb first load JS
* **Test Coverage**: 80%+ on critical paths (backend)
* **Caching Hit Rate**: High during trading hours (Redis)
* **Rate Limiting**: Prevents vnstock API abuse

## 13. Security Considerations

* **Frontend**: HTTPS, CSP headers, XSS protection
* **API**: CORS configuration, input validation via Pydantic
* **Database**: SSL connections (Supabase), parameterized queries
* **Infrastructure**: Docker network isolation
* **Secrets**: Environment variables, no hardcoded credentials
* **Rate Limiting**: Protects against abuse
