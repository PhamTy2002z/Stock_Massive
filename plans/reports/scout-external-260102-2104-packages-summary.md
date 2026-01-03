# Packages Directory Scout Report

**Date:** 2026-01-02 21:04
**Scout ID:** a4f4a4b
**Target:** `/Users/typham/Documents/GitHub/Stock_Massive/packages/`

---

## 1. Directory Structure and Organization

### packages/ Directory (Placeholder)
```
packages/
├── config/
│   └── .gitkeep
└── types/
    └── .gitkeep
```

**Finding:** The `packages/` directory contains only placeholder directories with `.gitkeep` files. No actual shared packages implemented yet.

### Actual Shared Code Location
Shared code lives within the `apps/` monorepo structure:

```
apps/
├── api/src/
│   ├── core/           # Shared backend infrastructure
│   └── stocks/shared/  # Domain-specific shared utilities
└── web/src/
    ├── lib/            # Shared frontend utilities
    ├── hooks/          # 27+ reusable React hooks
    └── components/
        ├── ui/         # 25+ ShadCN/Radix primitives
        └── shared/     # Cross-feature components
```

---

## 2. Shared Packages and Purposes

### Backend Core (`/apps/api/src/core/`)

| File | Purpose |
|------|---------|
| `config.py` | Pydantic-settings based config (env vars, Redis, scheduler) |
| `database.py` | SQLAlchemy async database setup |
| `cache.py` | Trading-hours-aware Redis cache with dynamic TTL |
| `redis.py` | Upstash Redis client wrapper |
| `ratelimit.py` | Sliding window rate limiting (100/60s standard, 20/60s heavy) |
| `scheduler.py` | APScheduler 4.0 job scheduling |
| `job_status_store.py` | Job progress tracking |
| `dependencies.py` | FastAPI dependency injection |
| `vnstock_wrapper.py` | vnstock library wrapper |

### Backend Shared (`/apps/api/src/stocks/shared/`)

| File | Purpose |
|------|---------|
| `validators.py` | Symbol validation (regex: `^[A-Z0-9]{1,10}$`) |
| `converters.py` | DataFrame to Pydantic conversion (`safe_float()`) |
| `exceptions.py` | Custom `StockServiceError` exception |

### Frontend Lib (`/apps/web/src/lib/`)

| File | Purpose |
|------|---------|
| `api.ts` | API client with 40+ typed fetch functions, error handling |
| `query-keys.ts` | TanStack Query key factory (type-safe cache keys) |
| `utils.ts` | Tailwind `cn()` utility (clsx + tailwind-merge) |
| `api-server.ts` | Server-side API utilities |

### Frontend Hooks (`/apps/web/src/hooks/`) - 27 hooks

Key hooks: `use-market-indices`, `use-stock-detail`, `use-volume-spikes`, `use-health-score`, `use-sector-performance`, `use-financial-statements`, etc.

### Frontend UI Components (`/apps/web/src/components/ui/`) - 25+ components

ShadCN/Radix primitives: Button, Card, Input, Select, Tabs, Dialog, Dropdown, Tooltip, Badge, Avatar, Sidebar, Progress, Skeleton, etc.

---

## 3. Dependencies and Relationships

### Backend Dependencies (`requirements.txt`)
```
fastapi>=0.100.0, uvicorn, pydantic>=2.0.0, pydantic-settings>=2.0.0
sqlalchemy>=2.0.0, alembic, asyncpg, psycopg2-binary
upstash-redis>=1.0.0, upstash-ratelimit>=1.0.0
vnstock>=3.0.0, pandas>=2.0.0, numpy>=1.24.0
apscheduler>=4.0.0a6
```

### Frontend Dependencies (`package.json`)
```
next@15.5.9, react@18.3.1, typescript@5.3.0
@tanstack/react-query@5.90, recharts@3.6.0
@radix-ui/* (10+ packages), tailwindcss@3.4.0
@supabase/ssr, @supabase/supabase-js
```

### Inter-App Communication
- Frontend -> Backend: REST API via `fetchApi()` in `/apps/web/src/lib/api.ts`
- Docker internal: `INTERNAL_API_URL` for SSR, `NEXT_PUBLIC_API_URL` for client

---

## 4. Key Utilities and Common Code

### TradingHoursCache (Backend)
```python
# /apps/api/src/core/cache.py
class TradingHoursCache:
    MARKET_OPEN = time(9, 0)
    MARKET_CLOSE = time(15, 0)
    # Dynamic TTL: shorter during trading, longer off-hours
```

### API Client Pattern (Frontend)
```typescript
// /apps/web/src/lib/api.ts
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T>
// 40+ typed API functions: fetchStockDetail, fetchMarketIndices, etc.
```

### Query Keys Factory (Frontend)
```typescript
// /apps/web/src/lib/query-keys.ts
export const queryKeys = {
  marketIndices: ["market", "indices"] as const,
  stock: (symbol: string) => ["stock", symbol] as const,
  // ... 20+ key factories
}
```

---

## 5. Configuration and Build Setup

### Backend Config (`/apps/api/src/core/config.py`)
- Pydantic-settings with `.env` file support
- Database: PostgreSQL via Supabase
- Cache: Upstash Redis
- Scheduler: APScheduler with configurable job times
- Rate limiting: Configurable windows and limits

### Frontend Config
- **tsconfig.json**: Path alias `@/*` -> `./src/*`, ES2017 target
- **tailwind.config.js**: HSL color system, ShadCN theme tokens, dark mode
- **next.config**: Next.js 15 App Router

---

## 6. Notable Patterns and Architectural Decisions

### Vertical Slice Architecture (Backend)
Each feature module contains: `router.py`, `service.py`, `schemas/`, `cache.py`
```
stocks/
├── analytics/  (router, service, sector_historical_*)
├── company/    (router, service)
├── financial/  (router, service, cache, health_scoring)
├── market/     (router, service)
├── price/      (router, service, cache)
├── trading/    (router, service, schemas)
└── shared/     (validators, converters, exceptions)
```

### Component Composition (Frontend)
```
components/
├── ui/           # Primitives (ShadCN)
├── shared/       # Cross-feature
├── layout/       # App shell
├── dashboard/    # Feature-specific
│   ├── advanced-tab/widgets/
│   ├── financial-health/
│   ├── financial-trends/
│   ├── fcf-analysis/
│   └── peer-comparison/
└── charts/       # Recharts wrappers
```

### Trading-Hours-Aware Caching
- Short TTL (10s) during market hours (9:00-15:00 ICT)
- Long TTL (5min+) outside trading hours
- Weekend detection

### Type Safety
- Backend: Pydantic v2 schemas with strict validation
- Frontend: TypeScript with 50+ interface definitions in `api.ts`

---

## Summary

The `packages/` directory is a **placeholder** for future shared packages. Currently, shared code is organized within the monorepo:

| Location | Purpose | Files |
|----------|---------|-------|
| `apps/api/src/core/` | Backend infrastructure | 9 files |
| `apps/api/src/stocks/shared/` | Domain utilities | 4 files |
| `apps/web/src/lib/` | Frontend utilities | 4 files |
| `apps/web/src/hooks/` | React hooks | 27 files |
| `apps/web/src/components/ui/` | UI primitives | 25+ files |

**Recommendation:** If cross-app type sharing is needed, populate `packages/types/` with shared TypeScript/Python types.

---

## Unresolved Questions

1. Is there a plan to extract shared types to `packages/types/`?
2. Should `packages/config/` contain shared ESLint/Prettier configs?
3. Any plans for a shared validation library between frontend/backend?
