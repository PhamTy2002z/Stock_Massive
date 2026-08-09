# Codebase Summary - Stock Massive

Generated: 2026-08-09
Total Files: 610+ analyzed | Frontend: 140+ TS/TSX | Backend: 53 Python + 6 migrations + 26 tests
Code Statistics: ~23,646 total lines of code | ~50 Python source files | ~100+ TypeScript source files

## 1. Project Overview and Purpose

Stock Massive is a Vietnamese stock market data platform powered by the `vnstock` library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

**Goals:**
* Display Vietnamese stock data with interactive charts
* Provide sortable/filterable data tables for stock screening
* Enable portfolio tracking and watchlist management (planned)
* Secure user authentication (self-hosted JWT + bcrypt, refresh-token rotation)
* Integrate `vnstock` library for comprehensive Vietnam market data
* Implement advanced analytical features (volume anomaly, volume spikes, financial statements, financial health)

## 2. Tech Stack

**Frontend:**
* **Framework**: Next.js 15.5.9 (App Router)
* **Language**: TypeScript 5.3.0
* **Styling**: TailwindCSS 3.4 + ShadCN/UI (26 Radix-based components)
* **Data Fetching**: TanStack Query v5.90.12 (5min staleTime, 10min gcTime)
* **Auth**: httpOnly cookie sessions against the app's own `/api/v1/auth` endpoints
* **Charts**: Recharts 3.6.0 (sparklines, treemap, pie, composed, radar, waterfall)
* **State**: useState (local), URL params (shared), next-themes (theme)
* **Notifications**: Sonner
* **Icons**: Lucide React
* **UI Components**: 25+ ShadCN primitives, 35+ dashboard widgets, 6 layout, 2 providers
* **Custom Hooks**: 28 total (data fetching + responsive + job status)
* **Pages**: 5 routes (home, login, analytics/deep-dive, analytics/volume-spikes, analytics/financial-statements)

**Backend:**
* **Framework**: FastAPI 0.100+
* **Language**: Python 3.11+
* **ORM**: SQLAlchemy 2.0 + Alembic (6 migrations)
* **Validation**: Pydantic 2.x
* **Server**: Uvicorn
* **Data Source**: vnstock 4.x (VCI), Fmarket API
* **Scheduler**: APScheduler 4.0 (daily intraday collection, weekly financial statements)
* **Cache/Rate Limit**: Upstash Redis (trading-hours-aware TTL)
* **Analytics**: Pandas, Greenlet
* **Auth**: bcrypt + PyJWT (self-hosted), refresh tokens hashed and rotated
* **Tests**: 26 test files (coverage on critical paths, including advanced endpoints Phase 4)

**Database:**
* **Primary**: PostgreSQL 16 — container `db` in dev, external/managed Postgres in prod
* **Connection**: single `DATABASE_URL`; append `?sslmode=require` for managed hosts

**DevOps:**
* **Containerization**: Docker
* **Dev**: Docker Compose runs `db` + `api`; frontend runs on the host (`next dev`, port 3000)
* **Prod**: Docker Compose runs `api` + `web`; `db` is opt-in via profile `db`
* **Package Manager (Frontend)**: pnpm
* **Package Manager (Backend)**: pip/uv

**Design:**
* Modern + Clean philosophy
* HSL color system with CSS variables (Orange #F97316 primary, neutral grays in dark mode)
* Dark/light themes support (no blue tint)

## 3. Directory Structure

```
stock-massive/
├── apps/
│   ├── web/                     # Next.js frontend (port 3000, host in dev) - 140+ files
│   │   └── src/
│   │       ├── app/             # App Router (5 pages)
│   │       │   ├── (auth)/login/       # Email/password login + register
│   │       │   └── analytics/          # Analytics pages
│   │       │       ├── deep-dive/      # Stock deep-dive analysis
│   │       │       ├── volume-spikes/  # Volume spike dashboard
│   │       │       └── financial-statements/  # Financial rankings
│   │       ├── components/
│   │       │   ├── ui/          # 25+ ShadCN components (button, card, tabs, progress, etc.)
│   │       │   ├── dashboard/   # 35+ feature components (market-indices, stock-detail-*, volume-spike-*, etc.)
│   │       │   ├── layout/      # 6 layout components (sidebar, header, job-progress-bar, notification-panel)
│   │       │   └── providers/   # 2 providers (query, theme)
│   │       ├── hooks/           # 28 custom hooks (use-stock-detail, use-volume-spikes, use-jobs-status, etc.)
│   │       └── lib/             # 4 utility files (api.ts, query-keys.ts, utils.ts, api-server.ts)
│   │
│   └── api/                     # FastAPI backend (port 8000) - 53 source files
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
│           │   ├── analytics/   # Volume spikes, financial statements, sector historical
│           │   │   ├── router.py
│           │   │   ├── service.py
│           │   │   ├── sector_historical_router.py
│           │   │   └── sector_historical_service.py
│           │   ├── overview/    # Market overview (breadth, movers, foreign flow)
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
│           │   ├── config.py         # Pydantic settings (env-driven)
│           │   ├── database.py       # SQLAlchemy async engine (SSL auto-detection)
│           │   ├── dependencies.py   # FastAPI dependencies
│           │   ├── cache.py          # TradingHoursCache class
│           │   ├── redis.py          # Upstash Redis client
│           │   ├── ratelimit.py      # Rate limiting middleware
│           │   ├── scheduler.py      # APScheduler configuration
│           │   ├── vnstock_wrapper.py # Rate limit protection wrapper
│           │   └── job_status_store.py  # Job progress tracking
│           └── main.py
│       ├── alembic/             # 6 database migrations
│       │   ├── env.py           # Reads DATABASE_URL
│       │   └── versions/
│       │       ├── d945d0cac5ec_add_stock_daily_ohlcv_table.py
│       │       ├── 60811b8fd9e3_create_stock_intraday_bars_table.py
│       │       ├── 6948fc67_add_top_performers_table.py
│       │       ├── a1b2c3d4_rename_top_performers_to_financial_statements.py
│       │       ├── 402fb4577ace_add_users_and_refresh_tokens_tables.py
│       │       └── 0399ab15140e_add_is_admin_to_users.py
│       ├── tests/               # 26 test files
│       │   ├── test_advanced_endpoints.py     # 5 classes, 19 tests (Phase 4)
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
├── docker/                      # Placeholder (.gitkeep)
├── docs/                        # Documentation
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
├── docker-compose.yml           # Dev: db + api (web behind profile `full`)
├── docker-compose.prod.yml      # Prod: api + web (db behind profile `db`)
└── README.md
```

## 4. Key Features and Functionality

**Current (Completed):**
* **Dashboard Layout**: Responsive sidebar, header, dark/light theme toggle
* **Stock Detail Page**: Search bar, ticker header, stats panel, tabbed sections (Overview, Financials, Shareholders, Volume)
* **Analytics Deep-Dive**: Dedicated stock analysis page with SSR
* **Volume Spikes Dashboard**: Treemap, pie chart, composed chart, tabs visualization
* **Financial Statements Page**: Ranking table with exchange/year/quarter filters
* **Market Overview**: Aggregated market breadth, top movers, foreign flow, top volume
* **Financial Health Scorecard**: 5-dimension radar, Piotroski F-Score, score breakdown
* **Peer Comparison**: Top 5 sector peers with heatmap table
* **FCF Analysis**: Waterfall chart, CCC indicator with DSO/DIO/DPO
* **Market Indices**: VN-INDEX, VN30, HNX, UPCOM cards with sparklines, 10s auto-refresh
* **VN30 Overview Table**: Real-time VN30 stocks with price, change, volume, market cap
* **Sector Historical Performance**: Period-based sector returns (1D, 1W, 1M, 3M, 6M, 1Y) with horizontal bar chart
* **Stock Data API**: 43+ REST endpoints via vnstock + Fmarket API
* **Financial Data**: Income statements, balance sheets, cash flow, trend charts
* **Shareholders/Officers**: Major holders, management, insider deals
* **Volume Analysis**: 5-min bar aggregation, peak period analysis
* **Volume Anomaly Detection**: Backend API + frontend visualization in stock detail tabs
* **Volume Spikes API**: Aggregated spike detection across all stocks
* **Sector Performance**: ICB Level 2 with sorting, top gainers/losers
* **Sector Historical Performance**: Period-based sector returns (1D, 1W, 1M, 3M, 6M, 1Y) with horizontal bar chart
* **Fund Certificates**: 7-item display via Fmarket API
* **Intraday Collection**: Scheduled daily (15:30 ICT) + cleanup (16:00 ICT)
* **Daily OHLCV Collection**: Scheduled daily (16:00 ICT)
* **Financial Statements Job**: Weekly (Sun 02:00 ICT) for HOSE+HNX quarterly rankings
* **Job Status API**: `/api/v1/jobs/status` for progress polling
* **Startup Job Recovery**: Non-blocking missed job recovery on API startup
* **Job Progress UI**: Progress bar + notification panel in frontend
* **Authentication**: Self-hosted JWT + bcrypt, refresh-token rotation with reuse detection, httpOnly cookie sessions
* **Redis Caching**: Trading-hours-aware cache for 7 high-traffic endpoints
* **Rate Limiting**: Sliding window (100/60s standard, 20/60s heavy)
* **API Documentation**: Auto-generated OpenAPI/Swagger UI

**Planned (Roadmap):**
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
* `/src/components/dashboard/`: 35+ feature components
  * `market-indices.tsx`, `stock-detail-panel.tsx`, `vn30-overview-table.tsx`
  * `volume-spike-dashboard.tsx`, `volume-spike-treemap.tsx`, `volume-spike-pie-chart.tsx`, `volume-spike-composed-chart.tsx`
  * `financial-statements-table.tsx`
  * `sector-historical-performance.tsx` (horizontal bar chart for sector returns)
  * `market-overview.tsx` (breadth, movers, foreign flow components)
* `/src/components/layout/`: 6 layout components
  * `app-sidebar.tsx`, `dashboard-header.tsx`, `job-progress-bar.tsx`, `notification-panel.tsx`
* `/src/hooks/`: 28 custom hooks
  * `use-stock-detail.ts`, `use-market-indices.ts`, `use-volume-spikes.ts`, `use-financial-statements.ts`
  * `use-jobs-status.ts` (job progress polling)
  * `use-sector-historical-performance.ts` (sector historical data fetching)
  * `use-market-overview.ts` (market overview data)
* `/src/lib/api.ts`: Client API (500+ LOC, all endpoints typed with Zod)
* `/src/lib/query-keys.ts`: Centralized query keys for TanStack Query

**Backend (apps/api/):**
* `/src/main.py`: FastAPI app, CORS, routing, scheduler startup, job recovery
* `/src/stocks/router.py`: Main router aggregation (30+ endpoints)
* `/src/stocks/analytics/router.py`: Volume spikes, financial statements endpoints
* `/src/stocks/analytics/service.py`: Analytics business logic
* `/src/stocks/analytics/sector_historical_router.py`: Sector historical performance endpoint
* `/src/stocks/analytics/sector_historical_service.py`: Sector historical business logic
* `/src/stocks/jobs_router.py`: Job status polling API
* `/src/stocks/models.py`: SQLAlchemy models (StockDailyOHLCV, IntradayBar, FinancialStatement)
* `/src/stocks/schemas/`: 6 schema files
  * `analytics.py` - FinancialStatementItem, VolumeSpikeItem
  * `common.py` - Shared types
  * `company.py` - Company, shareholders, officers
  * `financial.py` - Income, balance sheet, cash flow
  * `market.py` - VN30Overview, sectors, fund certificates, SectorHistoricalItem, SectorHistoricalResponse
  * `price.py` - OHLCV, intraday, volume
* `/src/core/config.py`: Pydantic settings (all values env-driven)
* `/src/core/database.py`: SQLAlchemy async engine with SSL auto-detection
* `/src/core/cache.py`: TradingHoursCache class (trading-hours-aware TTL)
* `/src/core/vnstock_wrapper.py`: Rate limit protection wrapper
* `/src/core/job_status_store.py`: In-memory job progress tracking
* `/alembic/env.py`: Alembic config reading `DATABASE_URL` via app settings

**Backend Tests (apps/api/tests/):**
* `/test_advanced_endpoints.py`: Phase 4 integration tests (5 test classes, 19 tests)
  * `TestAdvancedEndpointsRouter` - Endpoint success/error cases
  * `TestAdvancedEndpointsService` - Service layer validation
  * `TestAdvancedEndpointsErrorHandling` - Invalid symbols, null data, special chars
  * `TestAdvancedEndpointsPerformance` - P95 <2s response time validation
  * `TestAdvancedEndpointsCaching` - Cache behavior, data consistency

## 7. Development Setup

**Prerequisites:**
* Docker 20.10+ and Docker Compose v2 (backend + database)
* Node.js 20+ and pnpm 9+ (frontend, runs on the host)

**Quick Start:**
```bash
git clone <repo-url>
cd stock-massive

# Configure environment
cp .env.example .env                          # containers: db + api
cp apps/web/.env.example apps/web/.env.local  # host: frontend
# Set AUTH_SECRET in .env: openssl rand -base64 32

# 1. Backend + database in Docker (migrations run on api startup)
docker compose up -d --build

# 2. Frontend on the host
pnpm dev:web:install   # first run only
pnpm dev:web
```

* Frontend: `http://localhost:3000` (host, `next dev`)
* Backend API: `http://localhost:8000` (container `api`)
* API Docs: `http://localhost:8000/docs`

**Notes:**
* The frontend is deliberately not containerised in dev — `next dev` on the host
  gets native file watching. Opt in with `docker compose --profile full up` if needed.
* `pnpm build:web` needs the API running: some analytics pages fetch during prerender.

**Manual Setup (unsupported, outside Docker):**
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
4. Bars upserted to PostgreSQL (`stock_intraday_bars` table)
5. Volume anomaly detection performed on collected data
6. Data available via `/volume-anomalies` endpoint

## 10. Recent Major Changes (December 2024 - January 2026)

* **Prefetch Optimization** (Jan 3, 2026): Adjacent tab prefetch on mount + hover-based prefetch with 200ms delay for instant tab switching
* **Smooth Section Loading** (Jan 2, 2026): Dashboard sections use `keepPreviousData` pattern for smooth refetch (no skeleton flash)
* **Documentation Update** (Jan 3, 2026): Comprehensive documentation refresh with accurate file counts, feature lists, and latest scout findings
* **Sector Historical Performance** (Dec 30, 2025): Period-based sector returns with horizontal bar chart visualization
* **Market Overview Frontend** (Dec 30, 2025): Market overview components with breadth, top movers, foreign flow
* **Market Overview API** (Dec 30, 2025): Aggregated market-overview endpoint
* **Financial Health Enhancement Phase 4** (Dec 28, 2025): Peer Comparison, FCF Waterfall, CCC indicator with heatmap
* **Financial Health Enhancement Phase 2** (Dec 28, 2025): Health Scorecard UI: Radar chart, F-Score, score breakdown
* **Financial Health Enhancement Phase 1** (Dec 28, 2025): Backend APIs: health-score, trend-metrics, fcf-analysis, sector-peers
* **Advanced Endpoints Phase 4 Testing** (Dec 27): 19 integration tests covering price-depth, ratio-summary, trading-stats endpoints
* **Supabase Migration** (Dec 24): Moved to Supabase cloud — since reverted; the app now uses a Docker `db` container in dev and any Postgres via `DATABASE_URL`
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
* **Database**: SSL auto-detected for managed hosts, parameterized queries
* **Infrastructure**: Docker network isolation
* **Secrets**: Environment variables, no hardcoded credentials
* **Rate Limiting**: Protects against abuse
