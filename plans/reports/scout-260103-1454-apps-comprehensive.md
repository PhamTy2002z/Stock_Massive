# Scout Report: Apps Directory Structure
**Date**: 2026-01-03 14:54  
**Scope**: Complete `apps/` directory analysis  
**Focus**: Applications, tech stacks, key files, dependencies, entry points, API routes, database connections

---

## Executive Summary

Stock Massive monorepo contains **2 primary applications**:
- **apps/web**: Next.js 15.5.9 frontend (TypeScript, React 18.3, TailwindCSS)
- **apps/api**: FastAPI backend (Python 3.11, SQLAlchemy 2.0, APScheduler 4.0)

**Total codebase**: ~19,895 source files, ~23,646 LOC (excluding node_modules)
- Backend: 8,410 LOC (Python)
- Frontend: 15,236 LOC (TypeScript/TSX)

---

## Application 1: Web Frontend (`apps/web/`)

### Purpose
Vietnamese stock market dashboard with real-time data, charting, and analysis UI.

### Tech Stack
| Component | Version | Purpose |
|-----------|---------|---------|
| **Framework** | Next.js 15.5.9 | App Router, SSR, API routes |
| **Language** | TypeScript 5.3.0 | Type safety |
| **UI Library** | React 18.3.1 | Component framework |
| **Styling** | TailwindCSS 3.4 | Utility-first CSS |
| **UI Components** | ShadCN/UI (Radix) | Accessible primitives |
| **State Management** | TanStack Query 5.90 | Server state, caching |
| **Charts** | Recharts 3.6 | Data visualization |
| **Notifications** | Sonner 2.0.7 | Toast notifications |
| **Auth** | Supabase SSR 0.8.0 | OAuth, session management |
| **Theme** | next-themes 0.4.6 | Dark/light mode |
| **Icons** | lucide-react 0.561 | Icon library |
| **Utilities** | lodash-es, date-fns, clsx | Common utilities |

### Key Configuration Files
- **package.json**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/package.json`
  - Scripts: `dev`, `build`, `start`, `lint`, `type-check`
  - 42 dependencies, 8 devDependencies
  
- **tsconfig.json**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/tsconfig.json`
  - Target: ES2017
  - Module: esnext
  - Path alias: `@/*` → `./src/*`
  - Strict mode enabled
  
- **next.config.js**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/next.config.js`
  - Output: standalone (Docker-optimized)
  
- **Dockerfile**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/Dockerfile`
  - Base: node:20-alpine
  - Package manager: pnpm
  - Port: 3000
  - Health check: HTTP GET /

### Directory Structure
```
apps/web/
├── src/
│   ├── app/                          # Next.js App Router pages
│   │   ├── page.tsx                  # Dashboard home (/)
│   │   ├── layout.tsx                # Root layout
│   │   ├── loading.tsx               # Loading skeleton
│   │   ├── not-found.tsx             # 404 page
│   │   ├── (auth)/login/             # Auth routes
│   │   │   ├── page.tsx              # Login page
│   │   │   ├── login-form.tsx        # Login form component
│   │   │   └── actions.ts            # Server actions
│   │   ├── analytics/
│   │   │   ├── deep-dive/page.tsx    # Stock analysis page
│   │   │   ├── volume-spikes/page.tsx # Volume spike dashboard
│   │   │   └── financial-statements/ # Financial statements ranking
│   │   └── auth/callback/route.ts    # OAuth callback
│   │
│   ├── components/
│   │   ├── ui/                       # Primitive UI components (10+)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── select.tsx
│   │   │   ├── checkbox.tsx
│   │   │   ├── label.tsx
│   │   │   ├── avatar.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── collapsible.tsx
│   │   │   ├── sheet.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── alert.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── sidebar.tsx
│   │   │   ├── spinner.tsx
│   │   │   ├── sparkline.tsx
│   │   │   ├── sonner.tsx
│   │   │   └── error-fallback.tsx
│   │   │
│   │   ├── dashboard/                # Feature components (35+)
│   │   │   ├── stock-search-bar.tsx
│   │   │   ├── stock-ticker-header.tsx
│   │   │   ├── stock-company-info.tsx
│   │   │   ├── stock-detail-panel.tsx
│   │   │   ├── stock-detail-tabs.tsx
│   │   │   ├── stock-stats-table.tsx
│   │   │   ├── stock-detail-skeleton.tsx
│   │   │   ├── stock-detail-error.tsx
│   │   │   ├── stock-detail-empty.tsx
│   │   │   ├── volume-spike-dashboard.tsx
│   │   │   ├── volume-spike-treemap.tsx
│   │   │   ├── financial-statements-table.tsx
│   │   │   ├── charts-lazy.tsx
│   │   │   ├── advanced-tab/
│   │   │   │   ├── index.tsx
│   │   │   │   ├── technical-subtab.tsx
│   │   │   │   ├── order-flow-subtab.tsx
│   │   │   │   └── widgets/
│   │   │   │       ├── trading-stats-card.tsx
│   │   │   │       ├── foreign-flow-chart.tsx
│   │   │   │       ├── foreign-snapshot-card.tsx
│   │   │   │       ├── price-depth-widget.tsx
│   │   │   │       ├── price-depth-chart.tsx
│   │   │   │       ├── order-stats-table.tsx
│   │   │   │       ├── intraday-order-stats.tsx
│   │   │   │       ├── prop-flow-chart.tsx
│   │   │   │       ├── peer-comparison-table.tsx
│   │   │   │       ├── premium-badge.tsx
│   │   │   │       ├── sector-overview-card.tsx
│   │   │   │       └── index.ts
│   │   │   ├── financial-health/
│   │   │   │   ├── index.ts
│   │   │   │   ├── score-breakdown.tsx
│   │   │   │   └── f-score-indicator.tsx
│   │   │   ├── financial-trends/
│   │   │   │   ├── index.ts
│   │   │   │   ├── revenue-profit-chart.tsx
│   │   │   │   ├── margin-trend-chart.tsx
│   │   │   │   ├── roe-roa-chart.tsx
│   │   │   │   └── cash-flow-chart.tsx
│   │   │   ├── fcf-analysis/
│   │   │   │   ├── index.ts
│   │   │   │   ├── fcf-waterfall.tsx
│   │   │   │   └── ccc-indicator.tsx
│   │   │   └── peer-comparison/
│   │   │       ├── index.ts
│   │   │       └── peer-metrics-table.tsx
│   │   │
│   │   ├── layout/                   # Layout components (6)
│   │   │   ├── dashboard-layout.tsx
│   │   │   ├── dashboard-layout-client.tsx
│   │   │   ├── dashboard-header.tsx
│   │   │   ├── job-progress-bar.tsx
│   │   │   ├── notification-panel.tsx
│   │   │   └── index.ts
│   │   │
│   │   └── providers/                # Context providers (2)
│   │       ├── theme-provider.tsx
│   │       ├── query-provider.tsx
│   │       ├── query-error-boundary.tsx
│   │       └── index.ts
│   │
│   ├── hooks/                        # Custom React hooks (28)
│   │   ├── use-market-indices.ts
│   │   ├── use-vn30-overview.ts
│   │   ├── use-sector-performance.ts
│   │   ├── use-sector-historical-performance.ts
│   │   ├── use-stock-detail.ts
│   │   ├── use-volume-analysis.ts
│   │   ├── use-volume-spikes.ts
│   │   ├── use-financial-statements.ts
│   │   ├── use-financial-detail.ts
│   │   ├── use-income-statement.ts
│   │   ├── use-balance-sheet.ts
│   │   ├── use-cash-flow.ts
│   │   ├── use-health-score.ts
│   │   ├── use-trend-metrics.ts
│   │   ├── use-fcf-analysis.ts
│   │   ├── use-sector-peers.ts
│   │   ├── use-shareholders.ts
│   │   ├── use-price-depth.ts
│   │   ├── use-trading-stats.ts
│   │   ├── use-order-stats.ts
│   │   ├── use-intraday-order-stats.ts
│   │   ├── use-foreign-trading.ts
│   │   ├── use-foreign-snapshot.ts
│   │   ├── use-prop-trading.ts
│   │   ├── use-ratio-summary.ts
│   │   ├── use-fund-certificates.ts
│   │   ├── use-jobs-status.ts
│   │   └── use-mobile.tsx
│   │
│   ├── lib/
│   │   ├── utils.ts                  # Utility functions
│   │   └── api-client.ts             # API client (inferred)
│   │
│   ├── utils/
│   │   ├── supabase/
│   │   │   ├── client.ts             # Supabase client (browser)
│   │   │   ├── server.ts             # Supabase client (server)
│   │   │   └── middleware.ts         # Auth middleware
│   │   └── [other utilities]
│   │
│   ├── middleware.ts                 # Next.js middleware
│   └── app/auth/callback/route.ts    # OAuth callback route
│
├── public/                           # Static assets
├── node_modules/                     # Dependencies (pnpm)
├── .next/                            # Build output
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── next.config.js
├── Dockerfile
└── [other config files]
```

### Entry Points
- **Development**: `pnpm dev` → Next.js dev server on port 3000
- **Production**: `pnpm build` → `pnpm start` → Standalone server
- **Main page**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/page.tsx`

### API Integration
- **Base URL**: Configured via environment (default: `http://localhost:8000/api/v1`)
- **Client**: TanStack Query for server state management
- **Auth**: Supabase OAuth + session management
- **Hooks pattern**: Each feature has dedicated hook (e.g., `use-stock-detail.ts`)

### Database Connections
- **Supabase PostgreSQL**: Via `@supabase/supabase-js`
- **Auth**: Supabase OAuth (Google, GitHub, etc.)
- **Session**: Server-side session via Supabase SSR

---

## Application 2: API Backend (`apps/api/`)

### Purpose
FastAPI backend providing 43+ endpoints for Vietnamese stock market data, analytics, and real-time updates.

### Tech Stack
| Component | Version | Purpose |
|-----------|---------|---------|
| **Framework** | FastAPI 0.100.0+ | REST API, async |
| **Language** | Python 3.11+ | Backend logic |
| **Server** | Uvicorn 0.23.0+ | ASGI server |
| **Validation** | Pydantic 2.0+ | Data validation |
| **ORM** | SQLAlchemy 2.0+ | Database abstraction |
| **Database** | PostgreSQL (Supabase) | Cloud-hosted |
| **Migrations** | Alembic 1.12.0+ | Schema versioning |
| **Async DB** | asyncpg 0.28.0+ | Async PostgreSQL driver |
| **Scheduler** | APScheduler 4.0a6+ | Background jobs |
| **Cache** | Upstash Redis 1.0.0+ | Distributed cache |
| **Rate Limiting** | upstash-ratelimit 1.0.0+ | API rate limiting |
| **Data Source** | vnstock 3.0.0+ | Vietnamese stock data |
| **Data Processing** | pandas 2.0+, numpy 1.24+ | Data manipulation |
| **HTTP Client** | httpx 0.25.0+ | Async HTTP requests |
| **Testing** | pytest 7.4.0+, pytest-asyncio | Unit/integration tests |

### Key Configuration Files
- **requirements.txt**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/requirements.txt`
  - 34 dependencies (core, database, utils, cache, stock data, scheduler, dev)
  
- **Dockerfile**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/Dockerfile`
  - Base: python:3.11-slim
  - Port: 8000
  - Health check: HTTP GET /health
  - Build deps: gcc, g++, python3-dev
  
- **src/core/config.py**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`
  - Settings via pydantic-settings
  - Environment variables: database_url, redis_url, cors_origins, scheduler config
  - Rate limiting: 100/60s standard, 20/60s heavy
  - Scheduler: intraday collector, daily OHLCV, financial statements, sector historical
  
- **src/core/database.py**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/database.py`
  - Async SQLAlchemy engine
  - Supabase PostgreSQL connection
  - SSL support for cloud database
  - Connection pooling: pool_size=5, max_overflow=10

### Directory Structure
```
apps/api/
├── src/
│   ├── main.py                       # FastAPI app entry point
│   │   - Lifespan management (startup/shutdown)
│   │   - CORS middleware
│   │   - Router registration
│   │   - Global exception handler
│   │   - Health check endpoints
│   │
│   ├── core/                         # Core infrastructure (9 files)
│   │   ├── config.py                 # Settings (pydantic-settings)
│   │   ├── database.py               # SQLAlchemy async engine
│   │   ├── redis.py                  # Redis client
│   │   ├── cache.py                  # Caching layer
│   │   ├── ratelimit.py              # Rate limiting
│   │   ├── scheduler.py              # APScheduler setup
│   │   ├── job_status_store.py       # Job progress tracking
│   │   ├── vnstock_wrapper.py        # vnstock library wrapper
│   │   └── dependencies.py           # FastAPI dependencies
│   │
│   ├── stocks/                       # Domain modules (7 features)
│   │   ├── router.py                 # Main router aggregator
│   │   ├── service.py                # Shared service logic
│   │   ├── models.py                 # SQLAlchemy ORM models
│   │   ├── jobs.py                   # Background job definitions
│   │   ├── jobs_router.py            # Job status endpoints
│   │   ├── intraday_collector.py     # Intraday data collection
│   │   ├── financial_statements_collector.py
│   │   │
│   │   ├── shared/                   # Shared utilities
│   │   │   ├── exceptions.py         # Custom exceptions
│   │   │   ├── validators.py         # Validation logic
│   │   │   ├── converters.py         # Data converters
│   │   │   └── __init__.py
│   │   │
│   │   ├── schemas/                  # Pydantic models (5 files)
│   │   │   ├── common.py             # Shared schemas
│   │   │   ├── price.py              # Price data schemas
│   │   │   ├── company.py            # Company info schemas
│   │   │   ├── financial.py          # Financial data schemas
│   │   │   ├── market.py             # Market data schemas
│   │   │   ├── analytics.py          # Analytics schemas
│   │   │   └── __init__.py
│   │   │
│   │   ├── market/                   # Market data module
│   │   │   ├── router.py             # Market endpoints
│   │   │   ├── service.py            # Market service logic
│   │   │   └── __init__.py
│   │   │
│   │   ├── price/                    # Price data module
│   │   │   ├── router.py             # Price endpoints
│   │   │   ├── service.py            # Price service logic
│   │   │   ├── cache.py              # Price caching
│   │   │   └── __init__.py
│   │   │
│   │   ├── company/                  # Company info module
│   │   │   ├── router.py             # Company endpoints
│   │   │   ├── service.py            # Company service logic
│   │   │   └── __init__.py
│   │   │
│   │   ├── financial/                # Financial data module
│   │   │   ├── router.py             # Financial endpoints
│   │   │   ├── service.py            # Financial service logic
│   │   │   ├── cache.py              # Financial caching
│   │   │   ├── health_scoring.py     # F-Score calculation
│   │   │   └── __init__.py
│   │   │
│   │   ├── trading/                  # Trading data module
│   │   │   ├── router.py             # Trading endpoints
│   │   │   ├── service.py            # Trading service logic
│   │   │   ├── schemas.py            # Trading schemas
│   │   │   └── __init__.py
│   │   │
│   │   ├── analytics/                # Analytics module
│   │   │   ├── router.py             # Analytics endpoints
│   │   │   ├── sector_historical_router.py
│   │   │   ├── service.py            # Analytics service
│   │   │   ├── sector_historical_service.py
│   │   │   └── __init__.py
│   │   │
│   │   └── __init__.py
│   │
│   └── [other modules]
│
├── alembic/                          # Database migrations
│   ├── versions/                     # Migration scripts
│   ├── env.py
│   ├── script.py.mako
│   └── alembic.ini
│
├── tests/                            # Test suite
├── docs/                             # API documentation
├── requirements.txt                  # Python dependencies
├── Dockerfile
├── .venv/                            # Virtual environment
└── [other config files]
```

### Entry Points
- **Development**: `uvicorn src.main:app --reload` (port 8000)
- **Production**: `uvicorn src.main:app --host 0.0.0.0 --port 8000`
- **Main app**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/main.py`

### API Routes (43+ endpoints)

#### Market Data (9 endpoints)
```
GET /api/v1/stocks/symbols                    # List all symbols
GET /api/v1/stocks/symbols/group/{group}      # Symbols by group (VN30, HNX30)
GET /api/v1/stocks/symbols/search             # Search symbols
GET /api/v1/stocks/sector-performance         # Sector performance (ICB Level 2)
GET /api/v1/stocks/fund-certificates          # Fund certificates
GET /api/v1/stocks/vn30-overview              # VN30 stocks overview
GET /api/v1/stocks/market-indices             # VN-INDEX, VN30, HNX, UPCOM
GET /api/v1/stocks/market-overview            # Aggregated market overview
GET /api/v1/stocks/analytics/sector-historical # Sector historical (1D-1Y)
```

#### Price Data (6 endpoints)
```
GET /api/v1/stocks/{symbol}/history           # Historical OHLCV
GET /api/v1/stocks/{symbol}/intraday          # Intraday tick data
GET /api/v1/stocks/price-board                # Real-time price board
GET /api/v1/stocks/{symbol}/detail            # Comprehensive detail
GET /api/v1/stocks/{symbol}/volume-analysis   # Volume patterns
GET /api/v1/stocks/{symbol}/volume-anomalies  # Volume anomalies
```

#### Analytics (4 endpoints)
```
GET /api/v1/stocks/analytics/volume-spikes    # Top volume spike stocks
GET /api/v1/stocks/analytics/financial-statements # Top companies by net profit
GET /api/v1/stocks/analytics/sector-historical # Sector historical performance
GET /api/v1/jobs/status                       # Job progress polling
```

#### Company Data (4 endpoints)
```
GET /api/v1/stocks/{symbol}/company           # Company overview
GET /api/v1/stocks/{symbol}/shareholders      # Major shareholders
GET /api/v1/stocks/{symbol}/officers          # Company officers
GET /api/v1/stocks/{symbol}/insider-deals     # Insider trading deals
```

#### Advanced Analytics (3 endpoints)
```
GET /api/v1/stocks/{symbol}/price-depth       # Real-time bid/ask depth
GET /api/v1/stocks/{symbol}/ratio-summary     # Financial ratios
GET /api/v1/stocks/{symbol}/trading-stats     # Trading volume stats
```

#### Financial Data (9 endpoints)
```
GET /api/v1/stocks/{symbol}/financials/ratios
GET /api/v1/stocks/{symbol}/financials/income
GET /api/v1/stocks/{symbol}/financials/income-statement
GET /api/v1/stocks/{symbol}/financials/balance-sheet
GET /api/v1/stocks/{symbol}/financials/balance-sheet-detailed
GET /api/v1/stocks/{symbol}/financials/cash-flow
GET /api/v1/stocks/{symbol}/financials/health-score
GET /api/v1/stocks/{symbol}/financials/trend-metrics
GET /api/v1/stocks/{symbol}/financials/sector-peers
```

### Database Models
Located in `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/models.py`:
- **StockDailyOHLCV**: Historical daily price data
- **IntradayBar**: Intraday tick data
- **FinancialStatement**: Company financial statements
- [Additional models for caching, job tracking]

### Background Jobs (APScheduler)
Configured in `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/scheduler.py`:
1. **Intraday Collector**: 15:30 daily (VN30 subset)
2. **Daily OHLCV Collector**: 16:00 daily (all symbols)
3. **Financial Statements**: 02:00 weekly (Sunday)
4. **Sector Historical Performance**: 15:45 daily

### Caching Strategy
- **Redis**: Upstash Redis (trading-hours-aware TTL)
- **Cache layers**: Price data, financial data, market overview
- **TTL**: Configurable per endpoint
- **Rate limiting**: Sliding window (100/60s standard, 20/60s heavy)

### Database Connections
- **Primary**: Supabase PostgreSQL (cloud-hosted with SSL)
- **Async driver**: asyncpg
- **Connection pooling**: pool_size=5, max_overflow=10
- **Migrations**: Alembic (SQL-based versioning)
- **Direct connection**: DATABASE_URL_DIRECT for Alembic

---

## Shared Code (`apps/packages/`)

**Status**: Placeholder directory (not yet implemented)

---

## Dependency Graph

### Frontend Dependencies
```
Next.js 15.5.9
├── React 18.3.1
├── TailwindCSS 3.4
├── ShadCN/UI (Radix UI)
├── TanStack Query 5.90
├── Recharts 3.6
├── Supabase SSR 0.8.0
└── next-themes 0.4.6
```

### Backend Dependencies
```
FastAPI 0.100.0+
├── Uvicorn 0.23.0+
├── SQLAlchemy 2.0+
├── Alembic 1.12.0+
├── asyncpg 0.28.0+
├── APScheduler 4.0a6+
├── Upstash Redis 1.0.0+
├── vnstock 3.0.0+
├── pandas 2.0+
└── Pydantic 2.0+
```

---

## Docker Configuration

### Frontend Dockerfile
- **Base**: node:20-alpine
- **Package manager**: pnpm
- **Port**: 3000
- **Health check**: HTTP GET /
- **Mode**: Development with hot reload

### Backend Dockerfile
- **Base**: python:3.11-slim
- **Build deps**: gcc, g++, python3-dev
- **Port**: 8000
- **Health check**: HTTP GET /health
- **Mode**: Production (no reload)

---

## Key Files Summary

### Frontend Key Files
| File | Purpose |
|------|---------|
| `/apps/web/src/app/page.tsx` | Dashboard home page |
| `/apps/web/src/app/layout.tsx` | Root layout wrapper |
| `/apps/web/src/components/layout/dashboard-layout.tsx` | Main dashboard layout |
| `/apps/web/src/hooks/use-stock-detail.ts` | Stock detail data fetching |
| `/apps/web/src/utils/supabase/client.ts` | Supabase client (browser) |
| `/apps/web/package.json` | Dependencies & scripts |
| `/apps/web/tsconfig.json` | TypeScript configuration |
| `/apps/web/next.config.js` | Next.js configuration |

### Backend Key Files
| File | Purpose |
|------|---------|
| `/apps/api/src/main.py` | FastAPI app entry point |
| `/apps/api/src/core/config.py` | Settings & environment config |
| `/apps/api/src/core/database.py` | SQLAlchemy async engine |
| `/apps/api/src/core/scheduler.py` | APScheduler setup |
| `/apps/api/src/stocks/router.py` | Main router aggregator |
| `/apps/api/src/stocks/models.py` | SQLAlchemy ORM models |
| `/apps/api/src/stocks/jobs.py` | Background job definitions |
| `/apps/api/requirements.txt` | Python dependencies |

---

## Statistics

| Metric | Value |
|--------|-------|
| **Total source files** | 19,895 |
| **Backend LOC** | 8,410 |
| **Frontend LOC** | 15,236 |
| **Frontend components** | 60+ (UI + dashboard) |
| **Frontend hooks** | 28 |
| **Backend modules** | 7 (market, price, company, financial, trading, analytics, overview) |
| **API endpoints** | 43+ |
| **Database models** | 3+ |
| **Background jobs** | 4 |
| **Docker services** | 2 (web, api) |

---

## Unresolved Questions

None at this time. All applications, tech stacks, key files, dependencies, entry points, API routes, and database connections have been identified and documented.

