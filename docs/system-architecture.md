# System Architecture - Stock Massive

Updated: 2026-01-02

> **Note**: Toàn bộ hệ thống chạy trong Docker containers. Database sử dụng Supabase PostgreSQL cloud với SSL và connection pooling.

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
│  │  (25+ comp) │  │  (35+ comp) │  │  + Theme Provider   │  │
│  │             │  │  + Charts   │  │  + Sonner Toasts    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼───────────────────────────────┐
│                 FastAPI Backend (port 8000)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Stocks    │  │  Analytics  │  │   vnstock Library   │  │
│  │   Module    │  │   Module    │  │   (VCI Source)      │  │
│  │ (43+ endpts)│  │ (3 endpts)  │  │   + Fmarket API     │  │
│  │ + Volume    │  │ - vol spike │  │   + vnstock_wrapper │  │
│  │  Anomaly    │  │ - financials│  │    (rate limit)     │  │
│  │ + Redis     │  │ - sector    │  │                     │  │
│  │  Cache      │  │  historical │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────┬──────────────────┬───────────────────────────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐  ┌───────────────────────────────────────┐
│   PostgreSQL     │  │        Vietnam Stock Exchange         │
│   (Docker or     │  │   (HOSE, HNX, UPCOM via vnstock)      │
│    Supabase)     │  │                                       │
│                  │  └───────────────────────────────────────┘
│ + Upstash Redis  │
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
  - Volume Anomaly Data

### Fmarket API Integration

- **Source**: Fmarket API
- **Data Types**:
  - Fund certificates data (for `/fund-certificates` endpoint)

---

## Directory Structure

```
Stock_Massive/
├── apps/
│   ├── web/                      # Next.js frontend (140+ files)
│   │   ├── src/
│   │   │   ├── app/              # App Router (5 pages)
│   │   │   │   ├── (auth)/login/
│   │   │   │   └── analytics/
│   │   │   │       ├── deep-dive/
│   │   │   │       ├── volume-spikes/
│   │   │   │       └── financial-statements/
│   │   │   ├── components/
│   │   │   │   ├── ui/           # 25+ ShadCN components
│   │   │   │   ├── dashboard/    # 35+ feature components
│   │   │   │   ├── layout/       # 6 layout components (+ job-progress-bar, notification-panel)
│   │   │   │   └── providers/    # 2 providers
│   │   │   ├── hooks/            # 28 custom hooks (+ use-jobs-status, use-market-overview)
│   │   │   └── lib/              # API client, utils
│   │   ├── public/
│   │   └── package.json
│   │
│   └── api/                      # FastAPI backend (53 source + 4 migrations + 18 tests)
│       ├── src/
│       │   ├── stocks/           # Stocks module
│       │   │   ├── analytics/    # Volume spikes, financial statements
│       │   │   │   ├── router.py
│       │   │   │   └── service.py
│       │   │   ├── market/       # Symbols, sectors, fund certificates
│       │   │   ├── price/        # History, intraday, indices, volume
│       │   │   ├── company/      # Company info
│       │   │   ├── financial/    # Financials, ratios, health scoring
│       │   │   ├── trading/      # Price depth, trading stats
│       │   │   ├── overview/     # Market overview (breadth, movers, foreign flow)
│       │   │   │   ├── router.py
│       │   │   │   └── service.py
│       │   │   ├── router.py     # Main router aggregation
│       │   │   ├── service.py    # vnstock integration
│       │   │   ├── schemas/      # 6 Pydantic schema files
│       │   │   ├── models.py     # IntradayBar, FinancialStatement
│       │   │   ├── jobs.py       # Scheduled jobs
│       │   │   ├── intraday_collector.py
│       │   │   └── financial_statements_collector.py
│       │   ├── core/             # 9 core config files
│       │   │   ├── config.py, database.py, dependencies.py
│       │   │   ├── cache.py, redis.py, ratelimit.py
│       │   │   ├── scheduler.py, vnstock_wrapper.py
│       │   │   └── job_status_store.py  # Job progress tracking
│       │   └── main.py
│       ├── alembic/              # 4 DB migrations
│       ├── tests/                # 18 test files
│       └── requirements.txt
│
├── packages/                     # Shared code (placeholders)
├── docker/                       # Docker configs
├── docs/                         # 10 documentation files
├── plans/                        # Plans and reports
├── docker-compose.yml            # Dev config
├── docker-compose.prod.yml       # Prod config
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
├── market-overview               # GET - Aggregated market overview (breadth, movers, foreign flow)
├── price-board                   # GET - Real-time prices
├── intraday/collect              # POST - Trigger collection
├── sector-performance            # GET - ICB Level 2
├── vn30-overview                 # GET - VN30 stocks overview
├── fund-certificates             # GET - Fund certificates
├── analytics/
│   ├── volume-spikes             # GET - Top volume spike stocks
│   ├── financial-statements      # GET - Top companies by net profit
│   └── sector-historical         # GET - Sector historical performance (1D, 1W, 1M, 3M, 6M, 1Y)
├── {symbol}/
│   ├── history                   # GET - OHLCV data
│   ├── intraday                  # GET - Tick data
│   ├── detail                    # GET - Comprehensive detail
│   ├── company                   # GET - Company info
│   ├── shareholders              # GET - Major shareholders
│   ├── officers                  # GET - Company officers
│   ├── insider-deals             # GET - Insider trades
│   ├── volume-analysis           # GET - Volume patterns
│   ├── volume-anomalies          # GET - Volume anomaly detection
│   ├── price-depth               # GET - Bid/ask price depth
│   ├── ratio-summary             # GET - Financial ratios summary
│   ├── trading-stats             # GET - Trading volume statistics
│   └── financials/
│       ├── ratios                # GET - Financial ratios
│       ├── income                # GET - Income (simple)
│       ├── income-statement      # GET - Income (detailed)
│       ├── balance-sheet         # GET - Balance (simple)
│       ├── balance-sheet-detailed # GET - Balance (detailed)
│       ├── cash-flow             # GET - Cash flow
│       ├── health-score          # GET - Financial health scoring
│       ├── trend-metrics         # GET - Financial trend charts
│       └── sector-peers          # GET - Top 5 sector peers
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

### Volume Spikes Dashboard

```
1. User navigates to /analytics/volume-spikes
2. Frontend calls /api/v1/stocks/analytics/volume-spikes
3. AnalyticsService queries aggregated volume data
4. Returns top volume spike stocks with metrics
5. Frontend renders treemap, pie chart, composed chart
```

### Intraday Data Collection

```
1. Scheduler triggers at 15:30 ICT daily
2. IntradayCollector fetches tick data via vnstock
3. Ticks aggregated to 5-minute OHLCV bars
4. Bars upserted to PostgreSQL (IntradayBar model)
5. Volume anomaly detection performed on collected data
6. Data available via /volume-anomalies endpoint
```

### Financial Statements Collection

```
1. Scheduler triggers at 02:00 ICT Sunday
2. Collector fetches quarterly income statements for HOSE+HNX (~700-800 symbols)
3. Data ranked by net_profit
4. Stored in PostgreSQL (FinancialStatement model)
5. Available via /analytics/financial-statements endpoint
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
                ├── Stock Detail Section
                │   ├── StockTickerHeader
                │   ├── StockDetailPanel
                │   └── StockDetailTabs
                │       ├── Overview Tab
                │       ├── Finance Tab
                │       ├── Shareholders Tab
                │       └── Volume Anomaly Tab
                └── Analytics Pages
                    ├── VolumeSpikesDashboard
                    │   ├── VolumeSpikePieChart
                    │   ├── VolumeSpikeTreemap
                    │   └── VolumeSpikeComposedChart
                    └── FinancialStatementsTable
```

### State Management

- **Local State**: useState for component-level state
- **URL State**: Search params for stock symbol
- **Server State**: TanStack Query v5.90 for data fetching, caching, synchronization
- **Theme State**: next-themes for dark/light mode
- **Auto-Refresh**: Market indices update every 10s with loading indicators

### Data Fetching Layer (TanStack Query)

- **QueryProvider**: Wraps app with QueryClient configuration
- **Query Keys**: Centralized key factory at `lib/query-keys.ts`
- **DevTools**: React Query DevTools enabled in development
- **Hooks**: 28 custom hooks for data fetching

---

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| web | 3000 | Next.js frontend |
| api | 8000 | FastAPI backend |
| db | Supabase | PostgreSQL (cloud-hosted with SSL) |

### Docker Compose Features

- Health checks for all services
- Hot-reload for development
- Volume mounts for code changes
- Network isolation between services
- Separate prod config (docker-compose.prod.yml) with restart policies
- Supabase cloud database (no local db container needed)

---

## Database Schema (Supabase PostgreSQL)

### Connection Configuration

- **DATABASE_URL**: Async connection (asyncpg) via session pooler for API endpoints
- **DATABASE_URL_DIRECT**: Sync connection (psycopg2) bypassing pooler for Alembic migrations
- **SSL**: Auto-detected for Supabase URLs, required for cloud connections
- **Connection Pooling**: pool_size=5, max_overflow=10

### StockDailyOHLCV Table

```sql
CREATE TABLE stock_daily_ohlcv (
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (symbol, date)
);
```

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

### FinancialStatement Table

```sql
CREATE TABLE financial_statements (
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

CREATE INDEX ix_financial_statements_symbol ON financial_statements(symbol);
CREATE INDEX ix_financial_statements_rank ON financial_statements(rank);
CREATE INDEX ix_financial_statements_collected_at ON financial_statements(collected_at);
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
| Intraday Collection | 15:30 ICT daily | Collect tick data, aggregate to 5-min bars, volume anomaly detection |
| Intraday Cleanup | 16:00 ICT daily | Clean up old intraday data |
| Daily OHLCV Collection | 17:00 ICT daily | Collect daily OHLCV data for all symbols |
| Financial Statements | 02:00 ICT Sunday | Fetch quarterly income statements for HOSE+HNX (~700-800 symbols) |
| Sector Historical Collection | Configurable | Collect sector historical performance data |

### Job Status API

- **Endpoint**: `GET /api/v1/jobs/status`
- **Purpose**: Poll background job progress
- **Implementation**: In-memory store (`job_status_store.py`)

### Startup Job Recovery

- Checks for missed jobs on API startup
- Runs missed jobs in background (non-blocking)
- Prevents API startup blocking from synchronous jobs

---

## Caching Architecture

### Redis Caching (Implemented)

- **Generic Cache Class**: `TradingHoursCache` in `core/cache.py`
- **Trading-Hours-Aware TTL**: Shorter TTL during market hours (09:00-15:00 ICT), longer off-hours
- **Graceful Degradation**: System continues operation if Redis unavailable

### Cached Endpoints (7 total)

| Endpoint | Trading Hours TTL | Off-Hours TTL |
|----------|-------------------|---------------|
| `market-indices` | 5 min | 1 hour |
| `price-board` | 5 min | 1 hour |
| `symbols` | 1 hour | 24 hours |
| `sector-performance` | 5 min | 1 hour |
| `vn30-overview` | 5 min | 1 hour |
| `volume-anomaly` | 5 min | 1 hour |
| `financial-statements` | 1 hour | 24 hours |

---

## Rate Limiting

- **Standard Endpoints**: 100 requests / 60 seconds
- **Heavy Endpoints**: 20 requests / 60 seconds
- **Implementation**: Redis sliding window algorithm
- **vnstock Protection**: `vnstock_wrapper.py` for graceful rate limit handling

---

## Future Considerations

### WebSocket Support (Planned)

- Real-time price updates
- Portfolio value streaming
- Alert notifications

### Authentication (Planned)

- JWT-based authentication via Supabase
- User registration/login
- Protected routes
