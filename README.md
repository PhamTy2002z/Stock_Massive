# Stock Massive

Vietnamese stock market data platform powered by **vnstock** library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

## Current Status (Updated: 2025-12-21)

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard Layout | ✅ Done | Sidebar, header, responsive |
| Market Indices | ✅ Done | VN-INDEX, VN30, HNX, UPCOM cards (1min auto-refresh) |
| VN30 Overview Table | ✅ Done | Real-time VN30 stocks with price, volume, market cap |
| Sector Performance | ✅ Done | ICB Level 2 with sorting, top gainers/losers |
| Stock Detail Page | ✅ Done | Search, ticker header, stats, tabs (Overview, Finance, Shareholders, Volume) |
| Stock Data API | ✅ Done | 24+ endpoints via vnstock + Fmarket |
| Financial Data | ✅ Done | Income, balance sheet, cash flow (detailed) |
| Shareholders/Officers | ✅ Done | Major holders, management, insider deals |
| Volume Anomaly Detection | ✅ Done | Backend API + Frontend visualization |
| Fund Certificates | ✅ Done | Display 7 items via Fmarket API |
| Redis Caching | ✅ Done | Trading-hours-aware cache (Upstash Redis) |
| Rate Limiting | ✅ Done | Sliding window (100/60s standard, 20/60s heavy) |
| Database Models | ✅ Done | IntradayBar model, APScheduler jobs |
| Auth Pages | 🚧 Scaffolded | Login/register routes, Supabase OAuth UI |
| Charts Page | 🚧 Planned | TradingView Lightweight Charts |
| Portfolio/Watchlist | 🚧 Planned | CRUD operations, P&L tracking |

## Tech Stack

- **Frontend**: Next.js 15.5.9, TypeScript, TailwindCSS 3.4, ShadCN/UI, TanStack Query v5, Sonner
- **Backend**: FastAPI, Python 3.11+, vnstock >= 3.0.0, SQLAlchemy 2.0, APScheduler 4.0
- **Database**: PostgreSQL 16
- **Caching**: Upstash Redis (trading-hours-aware TTL)
- **DevOps**: Docker, Docker Compose, pnpm
- **Design**: Modern + Clean (HSL color system, dark/light themes, next-themes)

## Project Structure

```
Stock_Massive/
├── apps/
│   ├── web/                 # Next.js frontend (port 3000)
│   │   └── src/
│   │       ├── app/         # App Router pages
│   │       ├── components/  # UI + dashboard + layout components
│   │       ├── hooks/       # Custom hooks
│   │       └── lib/         # Utilities
│   │
│   └── api/                 # FastAPI backend (port 8000)
│       └── src/
│           ├── stocks/      # Feature-based modules (market, price, company, financial)
│           │   ├── router.py, service.py, schemas/, models.py
│           │   ├── market/  # Symbols, sectors, fund certificates
│           │   ├── price/   # History, intraday, indices, volume analysis
│           │   ├── company/ # Company info
│           │   └── financial/ # Financials, ratios
│           ├── core/        # Config, database, scheduler
│           └── main.py
│
├── packages/                # Shared code (placeholders)
├── docker/                  # Docker configs
└── docs/                    # Documentation
```

## API Endpoints (24+ Total)

All endpoints prefixed with `/api/v1/stocks`:

### Market Data (6 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/symbols` | GET | List all stock symbols |
| `/symbols/group/{group}` | GET | Symbols by group (VN30, HNX30) |
| `/symbols/search` | GET | Search symbols by ticker/name |
| `/sector-performance` | GET | Sector performance (ICB Level 2) |
| `/fund-certificates` | GET | Fund certificates data |
| `/vn30-overview` | GET | VN30 stocks overview (NEW) |

### Price Data (7 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/history` | GET | Historical OHLCV data |
| `/{symbol}/intraday` | GET | Intraday tick data |
| `/market-indices` | GET | VN-INDEX, VN30, HNX, UPCOM |
| `/price-board` | GET | Real-time price board |
| `/{symbol}/detail` | GET | Comprehensive stock detail |
| `/{symbol}/volume-analysis` | GET | Volume pattern analysis |
| `/{symbol}/volume-anomalies` | GET | Volume anomaly detection |
| `/intraday/collect` | POST | Trigger intraday collection |

### Company Data (5 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/company` | GET | Company overview |
| `/{symbol}/shareholders` | GET | Major shareholders |
| `/{symbol}/officers` | GET | Company officers |
| `/{symbol}/insider-deals` | GET | Insider trading deals |

### Financial Data (6 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/financials/ratios` | GET | Financial ratios |
| `/{symbol}/financials/income` | GET | Income statement (simple) |
| `/{symbol}/financials/income-statement` | GET | Income statement (detailed) |
| `/{symbol}/financials/balance-sheet` | GET | Balance sheet (simple) |
| `/{symbol}/financials/balance-sheet-detailed` | GET | Balance sheet (detailed) |
| `/{symbol}/financials/cash-flow` | GET | Cash flow statement |

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- pnpm

### Quick Start (Docker)

```bash
git clone <repo-url>
cd Stock_Massive
docker-compose up -d
```

Services: `http://localhost:3000` (web), `http://localhost:8000` (api), `http://localhost:8000/docs` (swagger)

### Manual Setup

```bash
# Frontend
cd apps/web
pnpm install
pnpm dev

# Backend
cd apps/api
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## Documentation

- [Project Overview & PDR](docs/project-overview-pdr.md)
- [System Architecture](docs/system-architecture.md)
- [Code Standards](docs/code-standards.md)
- [Design Guidelines](docs/design-guidelines.md)
- [Codebase Summary](docs/codebase-summary.md)
- [Project Roadmap](docs/project-roadmap.md)
- [Deployment Guide](docs/deployment-guide.md)

## License

MIT
