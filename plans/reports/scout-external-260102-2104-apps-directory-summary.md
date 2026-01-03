# Apps Directory Scout Report

**Generated:** 2026-01-02 21:04
**Scout ID:** af5a8c3

---

## 1. Directory Structure and Organization

```
apps/
├── api/                    # Python FastAPI backend
│   ├── src/
│   │   ├── core/          # Core infrastructure (config, db, cache, scheduler)
│   │   ├── stocks/        # Domain modules
│   │   │   ├── analytics/ # Analytics endpoints (volume spikes, sector historical)
│   │   │   ├── company/   # Company info endpoints
│   │   │   ├── financial/ # Financial statements, health scoring
│   │   │   ├── market/    # Market data (indices, sectors)
│   │   │   ├── price/     # Price data endpoints
│   │   │   ├── trading/   # Trading stats (foreign, prop trading)
│   │   │   └── schemas/   # Pydantic schemas
│   │   └── main.py        # FastAPI app entry
│   ├── alembic/           # Database migrations
│   └── tests/             # API tests
│
└── web/                    # Next.js frontend
    ├── src/
    │   ├── app/           # Next.js App Router pages
    │   │   ├── (auth)/    # Auth routes (login)
    │   │   ├── analytics/ # Analytics pages
    │   │   └── auth/      # Auth callback
    │   ├── components/
    │   │   ├── dashboard/ # Dashboard widgets (30+ components)
    │   │   ├── layout/    # Layout components (sidebar, header)
    │   │   ├── providers/ # React providers (query, theme)
    │   │   └── ui/        # shadcn/ui components
    │   ├── hooks/         # React Query hooks (25+ hooks)
    │   └── lib/           # API client, utilities
    └── public/            # Static assets
```

---

## 2. Key Files and Purposes

### API (Backend)

| File | Purpose |
|------|---------|
| `/apps/api/src/main.py` | FastAPI app entry, CORS, scheduler lifecycle |
| `/apps/api/src/core/config.py` | Settings via pydantic-settings |
| `/apps/api/src/core/database.py` | SQLAlchemy async engine |
| `/apps/api/src/core/cache.py` | Caching layer |
| `/apps/api/src/core/scheduler.py` | APScheduler job setup |
| `/apps/api/src/stocks/router.py` | Main router aggregating domain routers |
| `/apps/api/src/stocks/financial/health_scoring.py` | F-Score, health metrics |
| `/apps/api/src/stocks/analytics/sector_historical_service.py` | Sector historical performance |

### Web (Frontend)

| File | Purpose |
|------|---------|
| `/apps/web/src/app/page.tsx` | Main dashboard page with SSR prefetch |
| `/apps/web/src/lib/api.ts` | API client with 50+ typed endpoints |
| `/apps/web/src/lib/query-keys.ts` | React Query key management |
| `/apps/web/src/components/dashboard/index.ts` | Dashboard component exports |
| `/apps/web/src/hooks/use-stock-detail.ts` | Stock detail data hook |
| `/apps/web/src/components/layout/dashboard-layout.tsx` | Main layout wrapper |

---

## 3. Technologies and Frameworks

### Backend (apps/api)
- **Framework:** FastAPI 0.100+
- **Runtime:** Python 3.11, uvicorn
- **Database:** PostgreSQL via SQLAlchemy 2.0 (async), Alembic migrations
- **Cache:** Upstash Redis
- **Rate Limiting:** upstash-ratelimit
- **Scheduler:** APScheduler 4.0
- **Data Source:** vnstock 3.0 (Vietnamese stock data)
- **Data Processing:** pandas, numpy

### Frontend (apps/web)
- **Framework:** Next.js 15.5.9 (App Router, RSC)
- **UI Library:** React 18.3
- **State/Data:** TanStack React Query 5.90
- **Styling:** Tailwind CSS 3.4, tailwindcss-animate
- **Components:** shadcn/ui (Radix primitives)
- **Charts:** Recharts 3.6
- **Auth:** Supabase SSR
- **Icons:** Lucide React

---

## 4. Main Features and Functionality

### Market Data
- Market indices (VNINDEX, VN30, HNX, UPCOM)
- VN30 overview table
- Sector performance (ICB classification)
- Fund certificates

### Stock Analysis
- Stock detail panel (price, ratios, company info)
- Financial statements (income, balance sheet, cash flow)
- Health score with F-Score indicator
- FCF analysis with waterfall chart
- Trend metrics (revenue, profit, margins)

### Trading Analytics
- Order statistics (buy/sell volume)
- Foreign trading flow
- Proprietary trading data
- Intraday order stats
- Price depth (bid/ask levels)

### Volume Analysis
- Volume spike detection by industry
- Volume anomaly charts
- 20-day average comparisons

### Sector Analytics
- Sector historical performance (1W, 2W, 1M)
- Sector peer comparison
- Premium/discount to sector median

---

## 5. Configuration Files

### API
| File | Role |
|------|------|
| `/apps/api/requirements.txt` | Python dependencies |
| `/apps/api/Dockerfile` | Dev container (Python 3.11-slim) |
| `/apps/api/Dockerfile.prod` | Production container |
| `/apps/api/alembic.ini` | Migration config |

### Web
| File | Role |
|------|------|
| `/apps/web/package.json` | Node dependencies, scripts |
| `/apps/web/next.config.js` | Next.js config (standalone output) |
| `/apps/web/tailwind.config.js` | Tailwind with CSS variables, sidebar theme |
| `/apps/web/components.json` | shadcn/ui config (new-york style) |
| `/apps/web/tsconfig.json` | TypeScript config |
| `/apps/web/eslint.config.mjs` | ESLint flat config |

---

## 6. Architectural Patterns

### Backend Patterns
1. **Domain-Driven Structure:** Stocks module split by domain (market, price, company, financial, trading, analytics)
2. **Router Aggregation:** Main router includes domain routers with path ordering
3. **Service Layer:** Each domain has service.py for business logic
4. **Schema Separation:** Pydantic schemas in dedicated schemas/ folder
5. **Async-First:** Full async/await with SQLAlchemy 2.0 async
6. **Lifespan Management:** Scheduler and DB lifecycle via FastAPI lifespan

### Frontend Patterns
1. **Server Components:** RSC with HydrationBoundary for SSR prefetch
2. **Custom Hooks:** One hook per API endpoint (use-*.ts pattern)
3. **Component Composition:** Dashboard widgets as self-contained units
4. **Skeleton Loading:** Dedicated skeleton components per widget type
5. **Error Boundaries:** QueryErrorBoundary for graceful failures
6. **Lazy Loading:** charts-lazy.tsx for code splitting

### Data Flow
```
API (FastAPI) <-- vnstock --> Vietnamese Stock Exchanges
     |
     v
PostgreSQL (historical) + Redis (cache)
     |
     v
Next.js (SSR prefetch + client hydration)
     |
     v
React Query (cache, refetch, optimistic updates)
```

---

## File Counts

| Directory | Count |
|-----------|-------|
| API Python files | 53 |
| Web TypeScript files | 140+ |
| Dashboard components | 35+ |
| React Query hooks | 25+ |
| UI components | 25+ |

---

## Unresolved Questions

None - comprehensive analysis completed.
