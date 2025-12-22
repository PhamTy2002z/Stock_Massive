# System Architecture - Stock Massive

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Browser                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                 Next.js Frontend (port 3000)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  ShadCN UI  │  │  Dashboard  │  │  TanStack Query v5  │  │
│  │  (19 comp)  │  │  (18 comp)  │  │  + Theme Provider   │  │
│  │             │  │  + VN30     │  │  + Sonner Toasts    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼───────────────────────────────┐
│                 FastAPI Backend (port 8000)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Stocks    │  │  Scheduler  │  │   vnstock Library   │  │
│  │   Module    │  │ (APScheduler)│  │   (VCI Source)      │  │
│  │ (25+ endpts)│  │             │  │   + Fmarket API     │  │
│  │ + Volume    │  │             │  │   + vnstock_wrapper │  │
│  │  Anomaly    │  │             │  │    (rate limit)     │  │
│  │ + Redis     │  │             │  │                     │  │
│  │  Cache      │  │             │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────┬──────────────────┬───────────────────────────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐  ┌───────────────────────────────────────┐
│   PostgreSQL     │  │        Vietnam Stock Exchange         │
│   (port 5432)    │  │   (HOSE, HNX, UPCOM via vnstock)      │
│                  │  │                                       │
│ + Upstash Redis  │  └───────────────────────────────────────┘
│  (Caching)       │
└──────────────────┘
```

---

## Data Sources

### vnstock Integration

- **Library**: vnstock >= 3.0.0
- **Source**: VCI (Vietnam)
- **Data Types**:
  - Historical OHLCV (daily, weekly, monthly)
  - Intraday tick data
  - Real-time price board
  - Company information
  - Financial statements (income, balance sheet, cash flow)
  - Financial ratios
  - Stock indices (VN30, HNX30, etc.)
  - Shareholders, officers, insider deals
  - **Volume Anomaly Data** (via new endpoint)

### Fmarket API Integration

- **Source**: Fmarket API
- **Data Types**:
  - Fund certificates data (for `/fund-certificates` endpoint)

---

## Directory Structure

```
Stock_Massive/
├── apps/
│   ├── web/                      # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/              # App Router pages
│   │   │   ├── components/
│   │   │   │   ├── ui/           # ShadCN components
│   │   │   │   ├── dashboard/    # Feature components
│   │   │   │   ├── layout/       # Layout components
│   │   │   │   └── providers/    # Context providers
│   │   │   ├── hooks/            # Custom hooks
│   │   │   └── lib/              # Utilities
│   │   ├── public/
│   │   └── package.json
│   │
│   └── api/                      # FastAPI backend
│       ├── src/
│       │   ├── stocks/           # Stocks module
│       │   │   ├── market/       # Symbols, sectors, fund certificates
│       │   │   ├── price/        # History, intraday, indices, volume analysis
│       │   │   ├── company/      # Company info
│       │   │   └── financial/    # Financials, ratios
│       │   │   ├── router.py     # HTTP endpoints
│       │   │   ├── service.py    # vnstock integration
│       │   │   ├── schemas/      # Pydantic models (price, market, company, financial, analytics)
│       │   │   │   └── analytics.py # TopPerformerItem, TopPerformersResponse schemas
│       │   │   ├── models.py     # SQLAlchemy models (IntradayBar, TopPerformer)
│       │   │   ├── jobs.py       # Scheduled jobs (intraday collection/cleanup, top performers weekly)
│       │   │   ├── intraday_collector.py # Includes detect_volume_anomalies()
│       │   │   ├── top_performers_collector.py # Weekly top performers collection by net_profit
│       │   │   └── analytics/    # Analytics domain module
│       │   │       ├── __init__.py
│       │   │       ├── service.py # AnalyticsService with get_top_performers()
│       │   │       └── router.py  # Analytics endpoints (/top-performers)
│       │   ├── core/             # Config, database, scheduler
│       │   │   ├── config.py     # Settings, environment variables
│       │   │   ├── database.py   # SQLAlchemy engine, session
│       │   │   ├── scheduler.py  # APScheduler setup
│       │   │   ├── redis.py      # Upstash Redis client
│       │   │   ├── cache.py      # Trading-hours-aware cache
│       │   │   ├── ratelimit.py  # Rate limiting middleware
│       │   │   ├── vnstock_wrapper.py # vnstock wrapper with rate limit protection
│       │   │   └── dependencies.py # FastAPI dependencies
│       │   └── main.py
│       ├── alembic/              # DB migrations
│       └── requirements.txt      # Now includes greenlet and pandas
│
├── packages/                     # Shared code (placeholders)
├── docker/                       # Docker configs
├── docs/                         # Documentation
├── plans/                        # Plans and reports
├── docker-compose.yml
└── README.md
```

---

## API Architecture

### Endpoint Structure

```
/api/v1/stocks/
├── symbols                       # GET - All symbols
├── symbols/group/{group}         # GET - By index group
├── symbols/search                # GET - Search symbols
├── market-indices                # GET - VN-INDEX, VN30, HNX, UPCOM
├── price-board                   # GET - Real-time prices
├── intraday/collect              # POST - Trigger collection
├── {symbol}/
│   ├── history                   # GET - OHLCV data
│   ├── intraday                  # GET - Tick data
│   ├── detail                    # GET - Comprehensive detail
│   ├── company                   # GET - Company info
│   ├── shareholders              # GET - Major shareholders
│   ├── officers                  # GET - Company officers
│   ├── insider-deals             # GET - Insider trades
│   ├── volume-analysis           # GET - Volume patterns
│   ├── volume-anomalies          # GET - Volume anomaly detection results
│   └── financials/
│       ├── ratios                # GET - Financial ratios
│       ├── income                # GET - Income (simple)
│       ├── income-statement      # GET - Income (detailed)
│       ├── balance-sheet         # GET - Balance (simple)
│       ├── balance-sheet-detailed # GET - Balance (detailed)
│       └── cash-flow             # GET - Cash flow
├── analytics/
│   └── top-performers            # GET - Top companies by net profit (limit, exchange, year, quarter params)
├── sector-performance            # GET - Sector performance (ICB Level 2)
├── vn30-overview                 # GET - VN30 stocks overview (price, change, volume, market_cap)
└── fund-certificates             # GET - Fund certificates data
```

### Backend Layers

```
Router (HTTP) → Service (Business Logic) → vnstock/Repository
     ↓                    ↓                        ↓
  Schemas            Validation              Data Access
```

---

## Data Flow

### Stock Detail Request

```
1. User searches for stock symbol
2. Frontend calls /api/v1/stocks/{symbol}/detail
3. StockService fetches from vnstock:
   - Price board data
   - Company overview
   - Financial ratios
4. Data combined into StockDetail response
5. Frontend renders with stock-detail-* components
```

### Intraday Data Collection

```
1. Scheduler triggers at 15:30 ICT daily
2. IntradayCollector fetches tick data via vnstock
3. Ticks aggregated to 5-minute OHLCV bars
4. Bars upserted to PostgreSQL (IntradayBar model)
5. Volume anomaly detection is performed on collected intraday data.
6. Volume anomaly data is available via /volume-anomalies endpoint and visualized on the frontend.
```

---

## Frontend Architecture

### Component Hierarchy

```
RootLayout
└── QueryProvider (TanStack Query)
    └── ThemeProvider
        └── SidebarProvider
        ├── AppSidebar
        └── SidebarInset
            ├── DashboardHeader
            └── Main Content
                ├── MarketIndices
                ├── VN30OverviewTable
                ├── StockSearchBar
                └── Stock Detail Section
                    ├── StockTickerHeader
                    ├── StockDetailPanel
                    └── StockDetailTabs
                        ├── Overview Tab
                        ├── Finance Tab
                        ├── Shareholders Tab
                        └── Volume Anomaly Tab
```

### State Management

- **Local State**: useState for component-level state
- **URL State**: Search params for stock symbol
- **Server State**: TanStack Query v5 for data fetching, caching, and synchronization
- **Theme State**: next-themes for dark/light mode
- **Auto-Refresh**: Market indices update every 10s with loading indicators

### Data Fetching Layer (TanStack Query)

- **QueryProvider**: Wraps app with QueryClient configuration
- **Query Keys**: Centralized key factory at `lib/query-keys.ts`
- **DevTools**: React Query DevTools enabled in development

---

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| web | 3000 | Next.js frontend |
| api | 8000 | FastAPI backend |
| db | 5432 | PostgreSQL 16 |

### Docker Compose Features

- Health checks for all services
- Hot-reload for development
- Volume mounts for code changes
- Network isolation between services

---

## Database Schema

### IntradayBar Table

```sql
CREATE TABLE intraday_bars (
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (symbol, timestamp)
);

CREATE INDEX ix_intraday_bars_symbol ON intraday_bars(symbol);
CREATE INDEX ix_intraday_bars_timestamp ON intraday_bars(timestamp);
```

### TopPerformer Table

```sql
CREATE TABLE top_performers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    company_name VARCHAR(255),
    exchange VARCHAR(10) NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    net_profit FLOAT,
    revenue FLOAT,
    rank INTEGER NOT NULL,
    collected_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (symbol, year, quarter)
);

CREATE INDEX ix_top_performers_symbol ON top_performers(symbol);
CREATE INDEX ix_top_performers_rank ON top_performers(rank);
CREATE INDEX ix_top_performers_collected_at ON top_performers(collected_at);
```

---

## Security Layers

- **Frontend**: HTTPS, CSP headers, XSS protection
- **API**: CORS configuration, input validation via Pydantic
- **Database**: Connection pooling, parameterized queries
- **Infrastructure**: Docker network isolation

---

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Intraday Collection | 15:30 ICT daily | Collect and aggregate tick data, perform volume anomaly detection, with transaction rollback on failure |
| Top Performers Collection | 02:00 ICT Sunday | Fetch quarterly income statements for HOSE+HNX symbols (~700-800), rank by net_profit, store top performers with adaptive rate limiting |

---

## Future Considerations

### Caching Layer

- **Redis Caching (Implemented)**:
    - **Generic Cache Class**: Introduced `TradingHoursCache` in `core/cache.py` for managing time-sensitive data.
    - **Cache Instances**: Seven cache instances are utilized for: `volume_anomaly`, `market_indices`, `price_board`, `symbols`, `sector_performance`, `vn30_overview`, and `top_performers`.
    - **Trading-Hours-Aware TTL**: Cache entries have a Time-To-Live (TTL) that is intelligent about Vietnam market trading hours (09:00-15:00), ensuring data freshness during active periods and longer persistence off-hours.
    - **Graceful Degradation**: The system is designed to handle Redis unavailability gracefully, ensuring continuous operation even if the cache service is down.
    - **Affected Endpoints**:
        - `apps/api/src/stocks/price/router.py`: Caches `market-indices` and `price-board`.
        - `apps/api/src/stocks/market/router.py`: Caches `symbols`, `sector-performance`, and `vn30-overview`.
        - `apps/api/src/stocks/analytics/router.py`: Caches `top-performers` (1h trading, 24h off-hours).

### WebSocket Support (Planned)

- Real-time price updates
- Portfolio value streaming
- Alert notifications

### Authentication (Planned)

- JWT-based authentication
- User registration/login
- Protected routes
