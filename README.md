# Stock Massive

Vietnamese stock market data platform powered by **vnstock** library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

## Current Status (Updated: 2025-12-23)

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard Layout | Done | Sidebar, header, responsive |
| Market Indices | Done | VN-INDEX, VN30, HNX, UPCOM cards (10s auto-refresh) |
| VN30 Overview Table | Done | Real-time VN30 stocks with price, volume, market cap |
| Sector Performance | Done | ICB Level 2 with sorting, top gainers/losers |
| Stock Detail Page | Done | Search, ticker header, stats, tabs (Overview, Finance, Shareholders, Volume) |
| Analytics Deep-Dive | Done | Dedicated stock analysis page |
| Volume Spikes Dashboard | Done | Volume spike detection with treemap, pie chart, composed chart |
| Financial Statements | Done | Ranking by net profit with filters (exchange, year, quarter) |
| Stock Data API | Done | 30+ endpoints via vnstock + Fmarket |
| Financial Data | Done | Income, balance sheet, cash flow (detailed) |
| Shareholders/Officers | Done | Major holders, management, insider deals |
| Volume Anomaly Detection | Done | Backend API + Frontend visualization |
| Fund Certificates | Done | Display 7 items via Fmarket API |
| Redis Caching | Done | Trading-hours-aware cache (Upstash Redis) |
| Rate Limiting | Done | Sliding window (100/60s standard, 20/60s heavy) |
| Database Models | Done | IntradayBar, FinancialStatement models |
| Auth Pages | Scaffolded | Login/register routes, Supabase OAuth UI |
| Charts Page | Planned | TradingView Lightweight Charts |
| Portfolio/Watchlist | Planned | CRUD operations, P&L tracking |

## Tech Stack

- **Frontend**: Next.js 15.5.9, TypeScript 5.3.0, TailwindCSS 3.4, ShadCN/UI (Radix), TanStack Query 5.90, Recharts 3.6, Sonner
- **Backend**: FastAPI, Python 3.11+, vnstock >= 3.0.0, SQLAlchemy 2.0, APScheduler 4.0, Pydantic 2
- **Database**: PostgreSQL 16
- **Caching**: Upstash Redis (trading-hours-aware TTL)
- **DevOps**: Docker, Docker Compose, pnpm
- **Design**: Modern + Clean (HSL color system, dark/light themes, next-themes)

## Project Structure

```
Stock_Massive/
├── apps/
│   ├── web/                 # Next.js frontend (port 3000) - 75 files
│   │   └── src/
│   │       ├── app/         # App Router pages (5 pages)
│   │       ├── components/  # UI (20) + dashboard (27) + layout (4) + providers (2)
│   │       ├── hooks/       # 12 custom hooks
│   │       └── lib/         # 4 utility files
│   │
│   └── api/                 # FastAPI backend (port 8000) - 52 source files
│       └── src/
│           ├── stocks/      # Feature-based modules
│           │   ├── analytics/  # Volume spikes, financial statements
│           │   ├── market/     # Symbols, sectors, fund certificates
│           │   ├── price/      # History, intraday, indices, volume
│           │   ├── company/    # Company info, shareholders, officers
│           │   └── financial/  # Financials, ratios
│           ├── core/        # Config, database, scheduler, cache
│           └── main.py
│
├── packages/                # Shared code (placeholders)
├── docker/                  # Docker configs
└── docs/                    # Documentation (9 files)
```

## API Endpoints (30+ Total)

All endpoints prefixed with `/api/v1/stocks`:

### Market Data (7 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/symbols` | GET | List all stock symbols |
| `/symbols/group/{group}` | GET | Symbols by group (VN30, HNX30) |
| `/symbols/search` | GET | Search symbols by ticker/name |
| `/sector-performance` | GET | Sector performance (ICB Level 2) |
| `/fund-certificates` | GET | Fund certificates data |
| `/vn30-overview` | GET | VN30 stocks overview |
| `/market-indices` | GET | VN-INDEX, VN30, HNX, UPCOM |

### Price Data (6 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{symbol}/history` | GET | Historical OHLCV data |
| `/{symbol}/intraday` | GET | Intraday tick data |
| `/price-board` | GET | Real-time price board |
| `/{symbol}/detail` | GET | Comprehensive stock detail |
| `/{symbol}/volume-analysis` | GET | Volume pattern analysis |
| `/{symbol}/volume-anomalies` | GET | Volume anomaly detection |

### Analytics (2 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analytics/volume-spikes` | GET | Top volume spike stocks |
| `/analytics/financial-statements` | GET | Top companies by net profit |

### Company Data (4 endpoints)
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

> **Note**: Project chạy hoàn toàn bằng Docker. Không cần cài đặt Node.js, Python, hay PostgreSQL trên máy local.

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

### Quick Start

```bash
# Clone repository
git clone <repo-url>
cd Stock_Massive

# Copy và cấu hình environment
cp .env.example .env
# Chỉnh sửa .env với các giá trị của bạn

# Khởi động tất cả services
docker-compose up -d

# Chạy database migrations
docker-compose exec api alembic upgrade head
```

### Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Next.js web app |
| API | http://localhost:8000 | FastAPI backend |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Database | localhost:5432 | PostgreSQL (Docker) |

### Docker Commands

```bash
# Khởi động services
docker-compose up -d

# Xem logs
docker-compose logs -f
docker-compose logs -f api    # Chỉ API logs
docker-compose logs -f web    # Chỉ Web logs

# Dừng services
docker-compose down

# Rebuild sau khi thay đổi code
docker-compose up -d --build

# Database migrations
docker-compose exec api alembic upgrade head

# Truy cập database shell
docker-compose exec db psql -U postgres -d stockmassive

# Reset database (xóa data)
docker-compose down -v

# Kiểm tra trạng thái services
docker-compose ps
```

### Production Deployment

```bash
# Build và chạy production
docker-compose -f docker-compose.prod.yml up -d --build

# Xem logs production
docker-compose -f docker-compose.prod.yml logs -f
```

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard with market indices, VN30 overview, sector performance |
| `/login` | Auth login page (scaffolded) |
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
- [Deployment Guide](docs/deployment-guide.md)
- [VPS Deployment Guide](docs/vps-deployment-guide.md)

## License

MIT
