# Stock Massive

Vietnamese stock analysis platform powered by **vnstock** library. Provides real-time charting, data tables, and portfolio tracking for Vietnam stock market (HOSE, HNX, UPCOM).

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard Layout | Done | Sidebar, header, responsive |
| Dashboard Index Cards | Done | Real API integration, market indices |
| Stock Data API | Done | 10 endpoints via vnstock |
| Auth Pages | Scaffolded | Login/register routes exist |
| Charts/Portfolio/Watchlist | Scaffolded | Routes exist, not implemented |
| Database Models | Pending | SQLAlchemy configured, no models |

## Tech Stack

- **Frontend**: Next.js 14.2, TypeScript, TailwindCSS 3.4, ShadCN/UI (new-york)
- **Backend**: FastAPI, Python 3.11+, vnstock >= 3.0.0, SQLAlchemy 2.0
- **Database**: PostgreSQL 16
- **DevOps**: Docker, Docker Compose

## Project Structure

```
Stock_Massive/
├── apps/
│   ├── web/                 # Next.js frontend (port 3000)
│   │   └── src/
│   │       ├── app/         # App Router pages
│   │       ├── components/  # ShadCN + layout components
│   │       ├── hooks/       # useIsMobile, etc.
│   │       └── lib/         # cn() utility
│   │
│   └── api/                 # FastAPI backend (port 8000)
│       └── src/
│           ├── api/v1/      # Versioned routes
│           ├── stocks/      # Stock module (router, service, schemas)
│           ├── auth/        # Auth module (placeholder)
│           └── core/        # Config, database
│
├── packages/                # Shared code (empty placeholders)
├── docker/                  # Docker configs
└── docs/                    # Documentation
```

## API Endpoints

All endpoints prefixed with `/api/v1`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stocks/symbols` | GET | List all stock symbols |
| `/stocks/symbols/group/{group}` | GET | Symbols by group (VN30, HNX30) |
| `/stocks/{symbol}/history` | GET | Historical OHLCV data |
| `/stocks/{symbol}/intraday` | GET | Intraday tick data |
| `/stocks/price-board` | GET | Real-time price board |
| `/stocks/{symbol}/detail` | GET | Comprehensive stock detail data |
| `/stocks/{symbol}/company` | GET | Company overview |
| `/stocks/{symbol}/financials/ratios` | GET | Financial ratios |
| `/stocks/{symbol}/financials/income` | GET | Income statement |
| `/stocks/{symbol}/financials/balance-sheet` | GET | Balance sheet |

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
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## Documentation

- [Project Overview & PDR](docs/project-overview-pdr.md)
- [System Architecture](docs/system-architecture.md)
- [Code Standards](docs/code-standards.md)
- [Tech Stack](docs/tech-stack.md)
- [Codebase Summary](docs/codebase-summary.md)
- [Project Roadmap](docs/project-roadmap.md)
- [Deployment Guide](docs/deployment-guide.md)

## License

MIT