# Stock Massive

Vietnamese stock market data platform powered by **vnstock** library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard Layout | Done | Sidebar, header, responsive |
| Stock Detail Page | Done | Search, ticker header, stats, tabs |
| Market Indices | Done | VN-INDEX, VN30, HNX, UPCOM cards |
| Stock Data API | Done | 20+ endpoints via vnstock |
| Financial Data | Done | Income, balance sheet, cash flow |
| Shareholders/Officers | Done | Major holders, management, insider deals |
| Volume Analysis | Done | 5-min bar aggregation, peak periods |
| Auth Pages | Scaffolded | Login/register routes exist |
| Database Models | Done | Intraday bars model, scheduler |

## Tech Stack

- **Frontend**: Next.js 14.2, TypeScript, TailwindCSS 3.4, ShadCN/UI
- **Backend**: FastAPI, Python 3.11+, vnstock >= 3.0.0, SQLAlchemy 2.0
- **Database**: PostgreSQL 16
- **DevOps**: Docker, Docker Compose
- **Design**: Modern + Clean (HSL color system, dark/light themes)

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
│           ├── api/v1/      # Versioned routes
│           ├── stocks/      # Stock module (router, service, schemas)
│           ├── core/        # Config, database, scheduler
│           └── main.py
│
├── packages/                # Shared code (placeholders)
├── docker/                  # Docker configs
└── docs/                    # Documentation
```

## API Endpoints

All endpoints prefixed with `/api/v1/stocks`:

### Symbol Listing
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/symbols` | GET | List all stock symbols |
| `/symbols/group/{group}` | GET | Symbols by group (VN30, HNX30) |
| `/symbols/search` | GET | Search symbols by ticker/name |

### Price Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/history` | GET | Historical OHLCV data |
| `/{symbol}/intraday` | GET | Intraday tick data |
| `/market-indices` | GET | VN-INDEX, VN30, HNX, UPCOM |
| `/price-board` | GET | Real-time price board |
| `/{symbol}/detail` | GET | Comprehensive stock detail |

### Company & Financials
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/company` | GET | Company overview |
| `/{symbol}/financials/ratios` | GET | Financial ratios |
| `/{symbol}/financials/income` | GET | Income statement (simple) |
| `/{symbol}/financials/income-statement` | GET | Income statement (detailed) |
| `/{symbol}/financials/balance-sheet` | GET | Balance sheet (simple) |
| `/{symbol}/financials/balance-sheet-detailed` | GET | Balance sheet (detailed) |
| `/{symbol}/financials/cash-flow` | GET | Cash flow statement |

### Shareholders & Analysis
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/shareholders` | GET | Major shareholders |
| `/{symbol}/officers` | GET | Company officers |
| `/{symbol}/insider-deals` | GET | Insider trading deals |
| `/{symbol}/volume-analysis` | GET | Volume pattern analysis |
| `/intraday/collect` | POST | Trigger intraday collection |
| `/sector-performance` | GET | Sector performance (ICB Level 2) |

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
