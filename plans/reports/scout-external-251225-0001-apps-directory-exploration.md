# Apps Directory Exploration Report

**Scout ID**: a09b24a  
**Date**: 2025-12-25 00:01  
**Scope**: /Users/typham/Documents/GitHub/Stock_Massive/apps

---

## Executive Summary

Thư mục `apps/` chứa 2 ứng dụng chính trong monorepo:
- **apps/web**: Next.js 15 frontend (TypeScript, React 18)
- **apps/api**: FastAPI backend (Python 3.11+)

**Architecture**: Full-stack separated với frontend/backend độc lập, kết nối qua REST API.

---

## 1. Directory Structure

```
apps/
├── api/                    # Python FastAPI Backend
│   ├── alembic/           # Database migrations
│   │   └── versions/      # Migration scripts
│   ├── src/               # Source code
│   │   ├── core/          # Core infrastructure
│   │   ├── stocks/        # Feature modules (stocks domain)
│   │   └── main.py        # Application entry point
│   ├── tests/             # Test suite
│   ├── requirements.txt   # Python dependencies
│   ├── alembic.ini        # Alembic config
│   ├── Dockerfile         # Development container
│   └── Dockerfile.prod    # Production container
│
└── web/                   # Next.js 15 Frontend
    ├── src/
    │   ├── app/           # Next.js App Router pages
    │   ├── components/    # React components
    │   ├── hooks/         # Custom React hooks
    │   ├── lib/           # Utilities & API clients
    │   └── utils/         # Helper functions
    ├── public/            # Static assets
    ├── package.json       # Node dependencies
    ├── tsconfig.json      # TypeScript config
    ├── next.config.js     # Next.js config
    └── tailwind.config.js # Tailwind CSS config
```

---

## 2. apps/web - Next.js Frontend

### 2.1 Entry Points & Routing

**Main Entry Points:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/layout.tsx` - Root layout (global structure, providers)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/page.tsx` - Home/Dashboard page
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/middleware.ts` - Supabase auth middleware

**App Router Pages:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/(auth)/login/page.tsx` - Login page
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/analytics/deep-dive/page.tsx` - Stock deep dive
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/analytics/financial-statements/page.tsx` - Financial statements
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/analytics/volume-spikes/page.tsx` - Volume analysis
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/not-found.tsx` - 404 page

**API Routes:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/auth/callback/route.ts` - OAuth callback handler

### 2.2 Component Organization

**UI Components (Shadcn + Radix UI):**
```
src/components/ui/
├── alert.tsx, avatar.tsx, badge.tsx, button.tsx, card.tsx
├── checkbox.tsx, collapsible.tsx, dropdown-menu.tsx
├── input.tsx, label.tsx, progress.tsx, select.tsx
├── separator.tsx, sheet.tsx, skeleton.tsx, sonner.tsx
├── sparkline.tsx, spinner.tsx, tabs.tsx, tooltip.tsx
└── sidebar.tsx
```

**Dashboard Components:**
```
src/components/dashboard/
├── stock-search-bar.tsx
├── stock-index-card.tsx
├── stock-ticker-header.tsx
├── stock-company-info.tsx
├── stock-detail-panel.tsx
├── stock-detail-client.tsx
├── stock-detail-skeleton.tsx
├── stock-detail-error.tsx
├── stock-detail-empty.tsx
├── finance-tab-content.tsx
├── shareholders-tab-content.tsx
├── volume-tab-content.tsx
├── financial-statements-table.tsx
├── stock-stats-table.tsx
├── vn30-overview-table.tsx
├── fund-certificates.tsx
├── sector-performance.tsx
├── market-indices.tsx
├── charts-lazy.tsx
├── volume-anomaly-chart.tsx
├── volume-spike-chart.tsx
├── volume-spike-composed-chart.tsx
├── volume-spike-pie-chart.tsx
├── volume-spike-treemap.tsx
└── volume-spike-dashboard.tsx
```

**Layout Components:**
```
src/components/layout/
├── dashboard-layout.tsx
├── dashboard-layout-client.tsx
├── dashboard-header.tsx
├── app-sidebar.tsx
├── notification-panel.tsx
└── job-progress-bar.tsx
```

**Forms:**
```
src/app/(auth)/login/
└── login-form.tsx
```

**Providers:**
```
src/components/providers/
├── query-provider.tsx      # React Query
└── theme-provider.tsx      # next-themes
```

### 2.3 Custom Hooks (Data Fetching)

```
src/hooks/
├── use-mobile.tsx                  # Responsive breakpoint
├── use-jobs-status.ts              # Job status polling
├── use-balance-sheet.ts            # Balance sheet data
├── use-cash-flow.ts                # Cash flow data
├── use-financial-statements.ts     # Financial statements
├── use-fund-certificates.ts        # Fund certificates
├── use-income-statement.ts         # Income statement
├── use-market-indices.ts           # Market indices
├── use-sector-performance.ts       # Sector performance
├── use-shareholders.ts             # Shareholder data
├── use-stock-detail.ts             # Stock details
├── use-vn30-overview.ts            # VN30 overview
├── use-volume-analysis.ts          # Volume analysis
└── use-volume-spikes.ts            # Volume spikes
```

### 2.4 Services & APIs

**API Clients:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api.ts` - Client-side API calls
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api-server.ts` - Server-side API calls
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/query-keys.ts` - React Query key factory

**Supabase Integration:**
```
src/utils/supabase/
├── client.ts      # Browser client
├── server.ts      # Server components
└── middleware.ts  # Auth middleware
```

**Utilities:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/utils.ts` - Common utilities (cn, etc.)

### 2.5 Configuration Files

| File | Purpose |
|------|---------|
| `package.json` | Dependencies: Next.js 15.5.9, React 18, Shadcn, Supabase, React Query |
| `tsconfig.json` | TypeScript strict mode, path aliases (@/*) |
| `next.config.js` | Standalone output for Docker |
| `tailwind.config.js` | Tailwind CSS + custom theme |

### 2.6 Technologies & Frameworks (Web)

**Core:**
- Next.js 15.5.9 (App Router, Server Components)
- React 18.3.1
- TypeScript 5.3+ (strict mode)

**UI/Styling:**
- Tailwind CSS 3.4+ (utility-first)
- Shadcn UI (Radix UI primitives)
- next-themes 0.4+ (dark mode)
- Lucide Icons 0.561+
- Recharts 3.6+ (data visualization)
- Sonner 2.0+ (toast notifications)

**State & Data:**
- @tanstack/react-query 5.90+ (server state)
- @supabase/ssr 0.8+ (auth & data)
- date-fns 4.1+ (date utilities)

**Dev Tools:**
- ESLint 9.39+ (linting)
- Prettier (formatting - inferred from config)
- TypeScript ESLint 8.50+

---

## 3. apps/api - FastAPI Backend

### 3.1 Entry Point

**Main Application:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/main.py`
  - FastAPI app initialization
  - CORS middleware configuration
  - Router registration (stocks, jobs)
  - Global exception handler
  - Health check endpoints (/, /health)
  - Lifespan management (scheduler, database)

### 3.2 Feature Modules (Domain-Driven)

**Stocks Module Structure:**
```
src/stocks/
├── router.py                   # Main stocks router
├── service.py                  # Main stocks service
├── models.py                   # SQLAlchemy models
├── jobs.py                     # Background jobs logic
├── jobs_router.py              # Jobs API endpoints
├── intraday_collector.py       # Intraday data collector
├── financial_statements_collector.py  # Financial data collector
│
├── analytics/                  # Analytics subdomain
│   ├── router.py
│   └── service.py
│
├── company/                    # Company subdomain
│   ├── router.py
│   └── service.py
│
├── financial/                  # Financial subdomain
│   ├── router.py
│   └── service.py
│
├── market/                     # Market subdomain
│   ├── router.py
│   └── service.py
│
├── price/                      # Price subdomain
│   ├── router.py
│   └── service.py
│
├── schemas/                    # Pydantic schemas
│   ├── __init__.py
│   ├── common.py
│   ├── company.py
│   ├── market.py
│   ├── financial.py
│   ├── analytics.py
│   └── price.py
│
└── shared/                     # Shared utilities
    ├── __init__.py
    ├── validators.py
    ├── exceptions.py
    └── converters.py
```

### 3.3 Core Infrastructure

```
src/core/
├── config.py              # Settings (Pydantic Settings)
├── database.py            # SQLAlchemy async engine & session
├── dependencies.py        # FastAPI dependencies
├── cache.py               # Caching logic
├── redis.py               # Redis client
├── ratelimit.py           # Rate limiting (Upstash)
├── vnstock_wrapper.py     # vnstock API wrapper
├── job_status_store.py    # Job status management
└── scheduler.py           # APScheduler setup
```

### 3.4 Database Migrations (Alembic)

```
alembic/
├── env.py                 # Migration environment
└── versions/              # Migration scripts
    ├── a1b2c3d4_rename_top_performers_to_financial_statements.py
    ├── 60811b8fd9e3_create_stock_intraday_bars_table.py
    ├── 6948fc67_add_top_performers_table.py
    └── d945d0cac5ec_add_stock_daily_ohlcv_table.py
```

### 3.5 Testing

**Test Coverage:**
```
tests/
├── conftest.py                          # Pytest fixtures
├── test_financial_statements_collector.py
├── test_volume_analysis.py
├── test_jobs_router.py
├── test_job_status_store.py
├── test_intraday_collector.py
├── test_scheduler.py
├── test_database_phase01.py
├── test_sector_performance.py
├── test_stocks_router.py
├── test_volume_anomaly_detection.py
├── test_volume_anomaly_api.py
├── test_analytics_api.py
├── test_stocks_service.py
├── test_trading_hours_cache.py
└── test_ratelimit.py
```

### 3.6 Configuration Files (API)

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies (FastAPI, SQLAlchemy, vnstock, etc.) |
| `alembic.ini` | Alembic migration config |
| `Dockerfile` | Development Docker image |
| `Dockerfile.prod` | Production Docker image |
| `Makefile` | Development commands |

### 3.7 Technologies & Frameworks (API)

**Core:**
- FastAPI 0.100+ (async web framework)
- Uvicorn (ASGI server with uvloop)
- Pydantic 2.0+ (data validation)
- Pydantic Settings 2.0+ (config management)

**Database:**
- SQLAlchemy 2.0+ (async ORM)
- Alembic 1.12+ (migrations)
- asyncpg 0.28+ (PostgreSQL async driver)
- psycopg2-binary 2.9+ (PostgreSQL sync driver)
- Greenlet 3.0+ (async support)

**Data & Analytics:**
- vnstock 3.0+ (Vietnamese stock data)
- pandas 2.0+ (data manipulation)
- numpy 1.24+ (numerical computing)

**Infrastructure:**
- Upstash Redis 1.0+ (caching)
- Upstash Ratelimit 1.0+ (rate limiting)
- APScheduler 4.0+ (job scheduling)

**HTTP & Utils:**
- httpx 0.25+ (async HTTP client)
- python-multipart 0.0.6+ (file uploads)
- tenacity 8.2+ (retry logic)

**Testing:**
- pytest 7.4+
- pytest-asyncio 0.21+

---

## 4. Architecture Patterns

### 4.1 Frontend Patterns

**Pattern**: **Feature-based Component Architecture + Server/Client Separation**

- **App Router** cho routing & layouts
- **Server Components** mặc định (data fetching on server)
- **Client Components** cho interactive UI ("use client")
- **React Query** cho client-side caching & mutations
- **Shadcn UI** cho reusable component library
- **Custom hooks** cho business logic abstraction
- **Lazy loading** cho charts (performance optimization)

**Data Flow:**
1. Server Components → fetch initial data → SSR
2. Client Components → React Query → API calls
3. Mutations → React Query → invalidate cache
4. Real-time updates → polling hooks (use-jobs-status)

### 4.2 Backend Patterns

**Pattern**: **Feature-based Modular Architecture + Separation of Concerns**

**Layering:**
```
Routers (HTTP) → Services (Business Logic) → Models (Data Access)
                      ↓
                  Schemas (Validation)
```

**Feature Modules:**
- Mỗi subdomain (analytics, company, financial, market, price) có router + service riêng
- Shared logic trong `stocks/shared/`
- Core infrastructure trong `core/`

**Data Collection:**
- Background jobs với APScheduler
- Collectors (intraday, financial statements)
- Job status tracking cho UI progress

**Caching Strategy:**
- Upstash Redis cho external API responses
- Trading hours cache
- Rate limiting per endpoint

---

## 5. Key Features & Capabilities

### 5.1 Web Features

**Dashboard:**
- Market indices overview
- VN30 stock table
- Sector performance
- Fund certificates

**Analytics:**
- Deep dive stock analysis (financials, shareholders, volume)
- Financial statements viewer (top 50 HOSE/HNX)
- Volume spike detection & visualization

**Real-time:**
- Job progress tracking (notification panel)
- Toast notifications (Sonner)
- Loading states & skeletons

**Auth:**
- Supabase authentication
- Protected routes via middleware
- OAuth callback handling

### 5.2 API Features

**Stock Data:**
- Market indices
- Stock prices (intraday, daily OHLCV)
- Company information
- Financial statements (balance sheet, income, cash flow)
- Shareholder data

**Analytics:**
- Volume spike detection
- Volume anomaly analysis
- Sector performance
- VN30 overview

**Jobs & Scheduling:**
- Background data collection
- Job status API
- Scheduled updates

**Infrastructure:**
- Rate limiting (Upstash)
- Caching (Redis)
- Health checks
- Error handling & logging

---

## 6. File Count Summary

**apps/web:**
- **Total key files**: ~85 TypeScript/TSX files
  - Pages: 7
  - UI Components: 22
  - Dashboard Components: 26
  - Layout Components: 6
  - Hooks: 14
  - Utils/Libs: 10

**apps/api:**
- **Total key files**: ~55 Python files
  - Routers: 7
  - Services: 7
  - Models: 1 (centralized)
  - Schemas: 7
  - Core: 10
  - Tests: 18
  - Migrations: 4

---

## 7. Integration Points

**Web → API:**
- Base URL: Configured via environment variables
- API clients: `lib/api.ts` (client), `lib/api-server.ts` (server)
- Authentication: Supabase tokens passed to API

**API → External:**
- vnstock: Vietnamese stock market data
- PostgreSQL: Primary database
- Upstash Redis: Caching & rate limiting
- Supabase: Auth validation (inferred)

**Internal:**
- Web: React Query DevTools (development)
- API: APScheduler for background jobs
- Both: Docker containers (standalone)

---

## 8. Development Workflow

**Web Commands:**
```bash
cd apps/web
pnpm dev          # Development server
pnpm build        # Production build
pnpm start        # Production server
pnpm lint         # ESLint
pnpm type-check   # TypeScript check
```

**API Commands:**
```bash
cd apps/api
make <command>    # See Makefile for available commands
# Likely: make dev, make test, make migrate, etc.
```

**Docker:**
- Web: Standalone output configured
- API: `Dockerfile` (dev), `Dockerfile.prod` (production)

---

## 9. Notable Observations

### Strengths
✅ **Clean separation**: Frontend/backend fully decoupled  
✅ **Type safety**: TypeScript strict + Pydantic validation  
✅ **Modular**: Feature-based organization on both sides  
✅ **Modern stack**: Next.js 15, FastAPI, React Query, Supabase  
✅ **Testing**: Comprehensive test coverage on API  
✅ **Reusable UI**: Shadcn component library standardized  
✅ **Performance**: Server components, lazy loading, caching  
✅ **Production-ready**: Docker, standalone builds, migrations  

### Potential Areas
⚠️ **Web tests**: No test files found in apps/web (consider adding)  
⚠️ **API docs**: No OpenAPI/Swagger config visible (may be auto-generated)  
⚠️ **Monorepo tooling**: No workspace config (pnpm-workspace.yaml) visible in apps/  
⚠️ **Environment management**: Ensure env files documented & validated  

---

## 10. Recommended Next Steps

1. **Documentation**: Review/update API endpoint documentation
2. **Testing**: Add frontend tests (Vitest, Playwright)
3. **Monitoring**: Consider adding observability (Sentry, logging)
4. **CI/CD**: Ensure GitHub Actions for both apps
5. **Performance**: Bundle analysis for web app (<200kb target)

---

## Unresolved Questions

1. Is there a pnpm-workspace.yaml at root level for monorepo management?
2. How is the API_URL configured for different environments (dev/staging/prod)?
3. Is OpenAPI/Swagger documentation auto-generated or custom?
4. What is the deployment strategy (Docker Compose, Kubernetes, Serverless)?
5. Are there any shared packages between apps/web and apps/api?

---

**End of Report**
