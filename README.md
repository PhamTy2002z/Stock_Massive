# Stock Massive

Vietnamese stock market data platform powered by **vnstock** library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

## Current Status (Updated: 2026-08-09)

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard Layout | Done | Sidebar, header, responsive |
| Market Indices | Done | VN-INDEX, VN30, HNX, UPCOM cards (10s auto-refresh) |
| Market Overview | Done | Breadth, top movers, foreign flow, top volume |
| VN30 Overview Table | Done | Real-time VN30 stocks with price, volume, market cap |
| Sector Performance | Done | ICB Level 2 with sorting, top gainers/losers |
| Sector Historical | Done | Period-based returns (1D-1Y) with horizontal bar chart, prefetch optimization |
| Smooth Loading | Done | keepPreviousData pattern for tab/filter transitions (no skeleton flash) |
| Stock Detail Page | Done | Search, ticker header, stats, tabs (Overview, Finance, Shareholders, Volume) |
| Analytics Deep-Dive | Done | Dedicated stock analysis page |
| Volume Spikes Dashboard | Done | Volume spike detection with treemap, pie chart, composed chart |
| Financial Statements | Done | Ranking by net profit with filters (exchange, year, quarter) |
| Financial Health | Done | Radar chart, Piotroski F-Score, peer comparison, FCF waterfall |
| Stock Data API | Done | 43+ endpoints via vnstock + Fmarket |
| Sector Historical | Done | Period-based returns (1D-1Y) with horizontal bar chart |
| Financial Data | Done | Income, balance sheet, cash flow, trend charts |
| Shareholders/Officers | Done | Major holders, management, insider deals |
| Volume Anomaly Detection | Done | Backend API + Frontend visualization |
| Fund Certificates | Done | Display 7 items via Fmarket API |
| Redis Caching | Done | Trading-hours-aware cache (Upstash Redis) |
| Rate Limiting | Done | Sliding window (100/60s standard, 20/60s heavy) |
| Database Models | Done | StockDailyOHLCV, IntradayBar, FinancialStatement |
| Job Status API | Done | `/api/v1/jobs/status` for progress polling |
| Startup Job Recovery | Done | Non-blocking missed job recovery on API startup |
| Authentication | Done | Self-hosted JWT + bcrypt, refresh-token rotation with reuse detection |
| Dev Runtime Split | Done | Backend + database in Docker; frontend runs on the host (port 3000) |
| Auth Pages | Done | Email/password login + register, httpOnly cookie sessions |
| Job Progress UI | Done | Progress bar + notification panel |
| Charts Page | Planned | TradingView Lightweight Charts integration |
| Portfolio/Watchlist | Planned | CRUD operations, P&L tracking |
| Frontend Tests | Planned | Vitest + React Testing Library |
| E2E Tests | Planned | Playwright |
| CI/CD Pipeline | Planned | Not yet configured |

## Tech Stack

- **Frontend**: Next.js 15.5.9, TypeScript 5.3.0, TailwindCSS 3.4, ShadCN/UI (Radix), TanStack Query 5.90, Recharts 3.6, Sonner
- **Backend**: FastAPI, Python 3.11+, vnstock 4.x, SQLAlchemy 2.0, APScheduler 4.0, Pydantic 2, bcrypt, PyJWT
- **Database**: PostgreSQL 16 (self-hosted via Docker; any Postgres works via `DATABASE_URL`)
- **Caching**: Upstash Redis (trading-hours-aware TTL)
- **DevOps**: Docker Compose (backend + database in dev, everything in prod), pnpm (frontend on the host in dev)
- **Design**: Modern + Clean (HSL color system, dark/light themes, next-themes)

## Architecture

### Frontend: Reusable UI Components
- **Component-based**: ShadCN/UI + TailwindCSS as foundation
- **Composable**: Small, highly reusable components (Button, Card, Input, Dialog...)
- **Consistent**: Unified design tokens via HSL color system
- **Structure**: `components/ui/` (primitives) → `components/dashboard/` (features)

### Backend: Feature-based Modular (Vertical Slice) + SoC
- **Vertical Slice**: Each feature contains complete router, service, schema, models
- **Separation of Concerns**: Clear separation between layers
  - `routers/` - HTTP endpoints, request/response handling
  - `services/` - Business logic, data processing
  - `schemas/` - Pydantic models, validation
  - `models/` - SQLAlchemy ORM entities
- **Structure**: `stocks/{feature}/` (analytics, market, price, company, financial)

## Project Structure

```
stock-massive/
├── apps/
│   ├── web/                 # Next.js frontend (port 3000, runs on the host in dev) - 140+ files
│   │   └── src/
│   │       ├── app/         # App Router pages (5 routes)
│   │       ├── components/  # UI (25+) + dashboard (35+) + layout (6) + providers (2)
│   │       ├── hooks/       # 28 custom hooks
│   │       └── lib/         # API client, utils
│   │
│   └── api/                 # FastAPI backend (port 8000, always in Docker) - 53 source files
│       └── src/
│           ├── stocks/      # 7 domain modules (analytics, market, price, company, financial, trading, overview)
│           │   ├── analytics/  # Volume spikes, financial statements, sector historical
│           │   ├── market/     # Symbols, sectors, fund certificates
│           │   ├── price/      # History, intraday, indices, volume
│           │   ├── company/    # Company info, shareholders, officers
│           │   ├── financial/  # Financials, ratios, health scoring
│           │   ├── trading/    # Price depth, trading stats
│           │   ├── overview/   # Market overview (breadth, movers, foreign flow)
│           │   ├── schemas/    # 6 Pydantic schema files
│           │   ├── models.py   # SQLAlchemy ORM models
│           │   ├── jobs.py     # Background job definitions
│           │   └── intraday_collector.py, financial_statements_collector.py
│           ├── core/        # 9 core config files (config, database, cache, scheduler, etc.)
│           └── main.py
│
├── docker-compose.yml       # Dev: db + api (web behind the `full` profile)
├── docker-compose.prod.yml  # Prod: api + web (db behind the `db` profile)
└── docs/                    # Documentation
```

## API Endpoints

### Auth (5 endpoints)

Prefixed with `/api/v1/auth`. Access tokens are short-lived; refresh tokens are
opaque, stored hashed, and rotated on every use.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/register` | POST | Create an account, returns a token pair |
| `/login` | POST | Exchange credentials for a token pair |
| `/refresh` | POST | Rotate a refresh token |
| `/logout` | POST | Revoke a refresh token |
| `/me` | GET | Current user (requires `Authorization: Bearer`) |

## Stock Endpoints (43+ Total)

All endpoints prefixed with `/api/v1/stocks`:

### Market Data (9 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/symbols` | GET | List all stock symbols |
| `/symbols/group/{group}` | GET | Symbols by group (VN30, HNX30) |
| `/symbols/search` | GET | Search symbols by ticker/name |
| `/sector-performance` | GET | Sector performance (ICB Level 2) |
| `/fund-certificates` | GET | Fund certificates data |
| `/vn30-overview` | GET | VN30 stocks overview |
| `/market-indices` | GET | VN-INDEX, VN30, HNX, UPCOM |
| `/market-overview` | GET | Aggregated market overview (breadth, top gainers/losers, foreign flow, top volume) |
| `/analytics/sector-historical` | GET | Sector historical performance (1D, 1W, 1M, 3M, 6M, 1Y) |

### Price Data (6 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/history` | GET | Historical OHLCV data |
| `/{symbol}/intraday` | GET | Intraday tick data |
| `/price-board` | GET | Real-time price board |
| `/{symbol}/detail` | GET | Comprehensive stock detail |
| `/{symbol}/volume-analysis` | GET | Volume pattern analysis |
| `/{symbol}/volume-anomalies` | GET | Volume anomaly detection |

### Analytics (4 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analytics/volume-spikes` | GET | Top volume spike stocks |
| `/analytics/financial-statements` | GET | Top companies by net profit |
| `/analytics/sector-historical` | GET | Sector historical performance |
| `/api/v1/jobs/status` | GET | Poll background job progress |

### Company Data (4 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/company` | GET | Company overview |
| `/{symbol}/shareholders` | GET | Major shareholders |
| `/{symbol}/officers` | GET | Company officers |
| `/{symbol}/insider-deals` | GET | Insider trading deals |

### Advanced Analytics (3 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/price-depth` | GET | Real-time bid/ask price depth |
| `/{symbol}/ratio-summary` | GET | Financial ratios summary |
| `/{symbol}/trading-stats` | GET | Trading volume statistics |

### Financial Data (9 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/financials/ratios` | GET | Financial ratios |
| `/{symbol}/financials/income` | GET | Income statement (simple) |
| `/{symbol}/financials/income-statement` | GET | Income statement (detailed) |
| `/{symbol}/financials/balance-sheet` | GET | Balance sheet (simple) |
| `/{symbol}/financials/balance-sheet-detailed` | GET | Balance sheet (detailed) |
| `/{symbol}/financials/cash-flow` | GET | Cash flow statement |
| `/{symbol}/financials/health-score` | GET | Financial health scoring |
| `/{symbol}/financials/trend-metrics` | GET | Financial trend charts |
| `/{symbol}/financials/sector-peers` | GET | Top 5 sector peers comparison |

## Getting Started

> **Development setup**: the backend and database run in Docker; the frontend
> runs directly on your machine on port 3000. Next.js gets native file watching
> that way, which is much faster than a bind mount inside a container.

### Prerequisites
- Docker 20.10+ and Docker Compose v2
- Node.js 20+ and pnpm 9+ (for the frontend)

### Quick Start

```bash
# Clone repository
git clone <repo-url>
cd stock-massive

# Configure environment
cp .env.example .env                        # containers: db + api
cp apps/web/.env.example apps/web/.env.local # host: frontend
# Set AUTH_SECRET in .env — generate with: openssl rand -base64 32

# 1. Backend + database in Docker (api applies migrations on startup)
docker compose up -d --build

# 2. Frontend on your machine
pnpm dev:web:install    # first run only
pnpm dev:web

# Optional: load the bundled data snapshot into the fresh database
pnpm db:restore
```

`pnpm dev` does both steps in one go: starts the backend detached, then the
frontend in the foreground.

### Services

| Service | URL | Runs in |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Host (`next dev`) |
| API | http://localhost:8000 | Container `api` |
| API Docs | http://localhost:8000/docs | Container `api` |
| Database | localhost:5432 | Container `db` (PostgreSQL 16) |

### Common Commands

```bash
# Backend (Docker)
pnpm dev:api            # start db + api in the foreground
pnpm dev:api:detach     # same, detached
pnpm logs:api           # follow API logs
pnpm stop               # docker compose down
pnpm stop:clean         # down -v — also drops the database volume

# Frontend (host)
pnpm dev:web            # next dev on port 3000
pnpm build:web          # next build — requires the API to be running
pnpm start:web          # serve the production build

# Database
pnpm db:migrate         # alembic upgrade head (also runs on api startup)
pnpm db:shell           # psql into the db container
pnpm db:restore         # load data_export.sql

# Optional: run the frontend in Docker too
pnpm dev:full           # docker compose --profile full up
```

> `pnpm build:web` fails with `fetch failed` / `ECONNREFUSED` when the API is
> down — some analytics pages fetch during prerender. Start the backend first.

### Production Deployment

Production runs **both** apps in Docker (`stockmassive-api`, `stockmassive-web`).

```bash
docker compose -f docker-compose.prod.yml up -d --build

# Self-host Postgres on the same machine as well:
docker compose -f docker-compose.prod.yml --profile db up -d --build
```

`DATABASE_URL` and `AUTH_SECRET` are required. See the
[Deployment Guide](docs/deployment-guide.md) and
[VPS Deployment Guide](docs/vps-deployment-guide.md).

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard with market indices, VN30 overview, sector performance |
| `/login` | Email/password sign in |
| `/register` | Account creation |
| `/analytics/deep-dive` | Stock deep-dive analysis |
| `/analytics/volume-spikes` | Volume spike detection dashboard |
| `/analytics/financial-statements` | Financial statements ranking |

## Documentation

- [Project Overview & PDR](docs/project-overview-pdr.md)
- [System Architecture](docs/system-architecture.md)
- [Code Standards](docs/code-standards.md)
- [Design Guidelines](docs/design-guidelines.md)
- [Codebase Summary](docs/codebase-summary.md)
- [Project Roadmap](docs/project-roadmap.md)
- [Tech Stack](docs/tech-stack.md)
- [Deployment Guide](docs/deployment-guide.md)
- [VPS Deployment Guide](docs/vps-deployment-guide.md)

## License

MIT
