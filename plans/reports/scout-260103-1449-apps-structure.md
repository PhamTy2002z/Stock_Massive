# Scout Report: Stock_Massive/apps Directory
**Generated:** 2026-01-03 14:49 UTC+7

## 1. Directory Structure Overview

```
apps/
├── api/                    # FastAPI backend (Python)
│   ├── src/
│   │   ├── core/          # Configuration, database, cache, scheduler
│   │   ├── stocks/        # Domain modules (7 features)
│   │   │   ├── analytics/
│   │   │   ├── company/
│   │   │   ├── financial/
│   │   │   ├── market/
│   │   │   ├── price/
│   │   │   ├── trading/
│   │   │   ├── shared/    # Validators, converters, exceptions
│   │   │   └── schemas/   # Pydantic models
│   │   └── workers/       # Background tasks
│   ├── tests/             # 23 test files
│   ├── alembic/           # Database migrations
│   ├── Dockerfile & Dockerfile.prod
│   ├── requirements.txt
│   └── pyproject.toml (missing - uses requirements.txt)
│
└── web/                    # Next.js frontend (TypeScript/React)
    ├── src/
    │   ├── app/           # App Router pages (5+ routes)
    │   │   ├── (auth)/    # Login/register routes
    │   │   ├── (dashboard)/ # Charts, portfolio, watchlist
    │   │   ├── analytics/ # Deep-dive, volume-spikes, financial-statements
    │   │   └── api/       # API routes (auth callbacks)
    │   ├── components/    # 70+ components
    │   │   ├── ui/        # 15+ ShadCN/UI primitives
    │   │   ├── dashboard/ # 30+ feature components
    │   │   ├── layout/    # 6 layout components
    │   │   ├── providers/ # Query, theme providers
    │   │   ├── auth/      # Auth components
    │   │   ├── charts/    # Chart components
    │   │   ├── tables/    # Data table components
    │   │   └── shared/    # Shared utilities
    │   ├── hooks/         # 28+ custom React hooks
    │   ├── lib/           # API client, utilities, query keys
    │   ├── services/      # API service layer
    │   ├── types/         # TypeScript type definitions
    │   ├── utils/         # Utility functions (Supabase, etc.)
    │   └── config/        # Configuration
    ├── package.json
    ├── tsconfig.json
    ├── next.config.js
    ├── components.json    # ShadCN config
    ├── Dockerfile & Dockerfile.prod
    └── pnpm-lock.yaml
```

## 2. Key Files and Their Purposes

### Backend (API) - Core Infrastructure
| File | Purpose |
|------|---------|
| `/apps/api/src/main.py` | FastAPI app entry point, lifespan management, CORS, routers |
| `/apps/api/src/core/config.py` | Settings management (Pydantic) |
| `/apps/api/src/core/database.py` | SQLAlchemy engine, session factory |
| `/apps/api/src/core/cache.py` | Redis caching layer |
| `/apps/api/src/core/redis.py` | Upstash Redis client |
| `/apps/api/src/core/ratelimit.py` | Rate limiting (sliding window) |
| `/apps/api/src/core/scheduler.py` | APScheduler setup for background jobs |
| `/apps/api/src/core/job_status_store.py` | Job progress tracking |
| `/apps/api/src/core/vnstock_wrapper.py` | vnstock library wrapper |
| `/apps/api/src/core/dependencies.py` | FastAPI dependency injection |

### Backend - Domain Modules (Vertical Slice Architecture)
| Module | Files | Purpose |
|--------|-------|---------|
| **market** | router, service | Symbols, sectors, fund certificates |
| **price** | router, service, cache | Historical/intraday OHLCV, indices |
| **company** | router, service | Company info, shareholders, officers |
| **financial** | router, service, cache, health_scoring | Financials, ratios, health scores |
| **trading** | router, service, schemas | Order stats, foreign/prop trading |
| **analytics** | router, service, sector_historical_* | Volume spikes, financial statements |
| **shared** | validators, converters, exceptions | Cross-module utilities |

### Backend - Database & Jobs
| File | Purpose |
|------|---------|
| `/apps/api/src/stocks/models.py` | SQLAlchemy ORM: StockDailyOHLCV, StockIntradayBar, FinancialStatement |
| `/apps/api/src/stocks/jobs.py` | Background job definitions |
| `/apps/api/src/stocks/intraday_collector.py` | Intraday data collection job |
| `/apps/api/src/stocks/financial_statements_collector.py` | Financial data collection job |
| `/apps/api/alembic/` | Database migrations |

### Frontend (Web) - Pages & Routing
| Route | File | Purpose |
|-------|------|---------|
| `/` | `/app/page.tsx` | Dashboard (market indices, VN30, sectors) |
| `/login` | `/app/(auth)/login/page.tsx` | Authentication page |
| `/analytics/deep-dive` | `/app/analytics/deep-dive/page.tsx` | Stock analysis |
| `/analytics/volume-spikes` | `/app/analytics/volume-spikes/page.tsx` | Volume spike detection |
| `/analytics/financial-statements` | `/app/analytics/financial-statements/page.tsx` | Financial ranking |
| `/charts` | `/app/(dashboard)/charts/page.tsx` | TradingView charts (planned) |
| `/portfolio` | `/app/(dashboard)/portfolio/page.tsx` | Portfolio tracking (planned) |
| `/watchlist` | `/app/(dashboard)/watchlist/page.tsx` | Watchlist management (planned) |

### Frontend - Core Components (70+)
| Category | Count | Examples |
|----------|-------|----------|
| **UI Primitives** | 15+ | Button, Card, Input, Dialog, Tabs, Select, Tooltip, Badge, etc. |
| **Dashboard** | 30+ | MarketIndices, VN30OverviewTable, SectorPerformance, StockDetail, VolumeSpikeTreemap, etc. |
| **Layout** | 6 | DashboardLayout, DashboardHeader, AppSidebar, JobProgressBar, NotificationPanel |
| **Advanced** | 10+ | PriceDepthChart, ForeignFlowChart, PropFlowChart, PeerComparison, FCFWaterfall, FinancialHealth |
| **Tables** | 5+ | DataTable components with columns definitions |

### Frontend - Custom Hooks (28+)
| Hook | Purpose |
|------|---------|
| `use-market-indices` | Fetch market indices |
| `use-sector-performance` | Fetch sector data |
| `use-stock-detail` | Fetch stock details |
| `use-volume-spikes` | Fetch volume spike data |
| `use-financial-statements` | Fetch financial data |
| `use-price-depth` | Fetch bid/ask depth |
| `use-trading-stats` | Fetch trading statistics |
| `use-foreign-trading` | Fetch foreign investor data |
| `use-prop-trading` | Fetch proprietary trading data |
| `use-jobs-status` | Poll background job progress |
| `use-mobile` | Responsive design detection |

### Frontend - API & Services
| File | Purpose |
|------|---------|
| `/app/lib/api-client.ts` | HTTP client (fetch wrapper) |
| `/app/lib/api-server.ts` | Server-side API calls |
| `/app/lib/query-keys.ts` | TanStack Query key factory |
| `/app/services/` | API service layer |
| `/app/utils/supabase/` | Supabase client (auth, server/client) |

## 3. Technologies & Frameworks

### Backend Stack
- **Framework**: FastAPI 0.100+
- **Server**: Uvicorn
- **Database**: PostgreSQL (Supabase cloud) + SQLAlchemy 2.0 ORM
- **Migrations**: Alembic
- **Cache**: Upstash Redis (trading-hours-aware TTL)
- **Rate Limiting**: Upstash Rate Limit (sliding window: 100/60s standard, 20/60s heavy)
- **Scheduler**: APScheduler 4.0 (background jobs)
- **Data Source**: vnstock >= 3.0.0 (Vietnamese stock market)
- **Data Processing**: Pandas, NumPy
- **Validation**: Pydantic 2.0
- **Testing**: pytest, pytest-asyncio
- **HTTP Client**: httpx

### Frontend Stack
- **Framework**: Next.js 15.5.9 (App Router)
- **Language**: TypeScript 5.3.0
- **UI Library**: React 18.3.1
- **Component Library**: ShadCN/UI (Radix UI primitives)
- **Styling**: TailwindCSS 3.4 + tailwind-merge
- **State Management**: TanStack Query 5.90 (server state)
- **Charting**: Recharts 3.6
- **Notifications**: Sonner 2.0
- **Auth**: Supabase OAuth + next-auth (scaffolded)
- **Themes**: next-themes (dark/light mode)
- **Icons**: Lucide React
- **Date Handling**: date-fns
- **Utilities**: clsx, lodash-es, class-variance-authority
- **Error Boundary**: react-error-boundary
- **Linting**: ESLint 9.39 + TypeScript ESLint
- **Package Manager**: pnpm

## 4. Main Entry Points

### Backend
- **HTTP Server**: `http://localhost:8000` (FastAPI)
- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Health Check**: `GET /health`
- **Scheduler Status**: `GET /scheduler/status`
- **Main Router**: `/api/v1/stocks` (43+ endpoints)

### Frontend
- **Web App**: `http://localhost:3000` (Next.js)
- **Entry Point**: `/apps/web/src/app/page.tsx`
- **Auth Callback**: `/app/auth/callback/route.ts`

## 5. Configuration Files

### Backend Configuration
| File | Purpose |
|------|---------|
| `/apps/api/requirements.txt` | Python dependencies |
| `/apps/api/alembic.ini` | Alembic migration config |
| `/apps/api/Dockerfile` | Development Docker image |
| `/apps/api/Dockerfile.prod` | Production Docker image |
| `/apps/api/entrypoint.sh` | Docker entrypoint script |

### Frontend Configuration
| File | Purpose |
|------|---------|
| `/apps/web/package.json` | npm/pnpm dependencies & scripts |
| `/apps/web/tsconfig.json` | TypeScript compiler options |
| `/apps/web/next.config.js` | Next.js config (standalone output) |
| `/apps/web/components.json` | ShadCN/UI component config |
| `/apps/web/Dockerfile` | Development Docker image |
| `/apps/web/Dockerfile.prod` | Production Docker image |
| `/apps/web/pnpm-lock.yaml` | Locked dependency versions |

## 6. Code Statistics

- **Total Lines of Code**: ~23,646 (Python + TypeScript)
- **Backend Python Files**: ~50 source files
- **Frontend TypeScript Files**: ~100+ source files
- **Test Files**: 23 (API tests)
- **Database Models**: 3 (StockDailyOHLCV, StockIntradayBar, FinancialStatement)
- **API Endpoints**: 43+
- **React Components**: 70+
- **Custom Hooks**: 28+

## 7. Architecture Patterns

### Backend: Vertical Slice + Separation of Concerns
- **Routers**: HTTP endpoints, request/response handling
- **Services**: Business logic, data processing
- **Schemas**: Pydantic models, validation
- **Models**: SQLAlchemy ORM entities
- **Shared**: Cross-module utilities (validators, converters, exceptions)

### Frontend: Component-Based + Server-Side Rendering
- **App Router**: File-based routing (Next.js 15)
- **Server Components**: Prefetch data at build/request time
- **Client Components**: Interactive UI with React Query
- **Hooks**: Reusable logic extraction
- **Providers**: Context-based state (Query, Theme)

## 8. Key Observations

1. **Modular Design**: Backend uses vertical slice architecture; frontend uses component-based design
2. **Caching Strategy**: Trading-hours-aware Redis caching for market data
3. **Rate Limiting**: Dual-tier (standard 100/60s, heavy 20/60s)
4. **Background Jobs**: APScheduler for data collection (intraday, financial statements)
5. **Database**: Supabase PostgreSQL with Alembic migrations
6. **Authentication**: Supabase OAuth (scaffolded, not fully implemented)
7. **Testing**: Comprehensive pytest suite (23 test files)
8. **Docker**: Multi-stage builds for both dev and prod
9. **Type Safety**: Full TypeScript frontend, Pydantic validation backend
10. **UI/UX**: Modern design with dark/light theme support, responsive layout

---

## Unresolved Questions

- Are auth pages (login/register) fully implemented or scaffolded?
- Is the charts page (TradingView integration) implemented?
- Are portfolio/watchlist features implemented?
- What is the current test coverage percentage?
