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
│  │  ShadCN UI  │  │  Dashboard  │  │  Theme Provider     │  │
│  │  (16 comp)  │  │  (19 comp)  │  │  + Sonner Toasts    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼───────────────────────────────┐
│                 FastAPI Backend (port 8000)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Stocks    │  │  Scheduler  │  │   vnstock Library   │  │
│  │   Module    │  │ (APScheduler)│  │   (VCI Source)      │  │
│  │ (incl. Volume│  │             │  │   + Fmarket API     │  │
│  │  Anomaly Det.│  │             │  │                     │  │
│  │ + Redis Cache)│  │             │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────┬──────────────────┬───────────────────────────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐  ┌───────────────────────────────────────┐
│   PostgreSQL     │  │        Vietnam Stock Exchange         │
│   (port 5432)    │  │   (HOSE, HNX, UPCOM via vnstock)      │
└──────────────────┘  └───────────────────────────────────────┘
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
│       │   │   ├── schemas/      # Pydantic models (price.py now includes VolumeAnomalyLevel, VolumeTimeSlot, VolumeAnomalyResponse)
│       │   │   ├── models.py     # SQLAlchemy models
│       │   │   ├── jobs.py       # Scheduled jobs
│       │   │   └── intraday_collector.py # Includes detect_volume_anomalies()
│       │   ├── core/             # Config, database, scheduler
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
├── sector-performance            # GET - Sector performance (ICB Level 2)
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
| Intraday Collection | 15:30 ICT daily | Collect and aggregate tick data and perform volume anomaly detection |

---

## Future Considerations

### Caching Layer
- Redis caching has been implemented for volume anomaly detection results, reducing redundant computations and improving response times.
- Keyed by symbol and baseline days (`{symbol}:{days}`), with TTL based on trading hours.
- Plans for vnstock response caching are still pending.

### WebSocket Support (Planned)

- Real-time price updates
- Portfolio value streaming
- Alert notifications

### Authentication (Planned)

- JWT-based authentication
- User registration/login
- Protected routes
