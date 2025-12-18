# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Browser                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                 Next.js Frontend (port 3000)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  ShadCN UI  │  │  TradingView │  │  TanStack Table    │  │
│  │  Components │  │  Charts      │  │  Data Tables       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼───────────────────────────────┐
│                 FastAPI Backend (port 8000)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    Auth     │  │   Stocks    │  │   vnstock Library   │  │
│  │   Module    │  │   Module    │  │   (VCI Source)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────┬──────────────────┬───────────────────────────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐  ┌───────────────────────────────────────┐
│   PostgreSQL     │  │        Vietnam Stock Exchange         │
│   (port 5432)    │  │   (HOSE, HNX, UPCOM via vnstock)      │
└──────────────────┘  └───────────────────────────────────────┘
```

## Data Sources

### vnstock Integration
- **Library**: vnstock >= 3.0.0
- **Source**: VCI (Vietnam)
- **Data Types**:
  - Historical OHLCV (daily, weekly, monthly)
  - Intraday tick data
  - Real-time price board
  - Company information
  - Financial statements
  - Stock indices (VN30, HNX30, etc.)

## Directory Structure

```
Stock_Massive/
├── apps/
│   ├── web/                      # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/              # App Router pages
│   │   │   ├── components/       # React components
│   │   │   ├── hooks/            # Custom hooks
│   │   │   └── lib/              # Utilities
│   │   ├── public/
│   │   └── package.json
│   │
│   └── api/                      # FastAPI backend
│       ├── src/
│       │   ├── api/v1/           # Versioned API routes
│       │   ├── auth/             # Auth module (placeholder)
│       │   ├── stocks/           # Stocks module
│       │   │   ├── router.py     # HTTP endpoints
│       │   │   ├── service.py    # vnstock integration
│       │   │   └── schemas.py    # Pydantic models
│       │   ├── core/             # Config, database
│       │   └── main.py
│       ├── alembic/              # DB migrations
│       └── requirements.txt
│
├── packages/                     # Shared code (empty)
├── docker/                       # Docker configs
├── docs/                         # Documentation
├── docker-compose.yml
└── README.md
```

## API Architecture

### Endpoint Structure
```
/api/v1/
├── stocks/
│   ├── symbols                   # GET - All symbols
│   ├── symbols/group/{group}     # GET - By index group
│   ├── {symbol}/history          # GET - OHLCV data
│   ├── {symbol}/intraday         # GET - Tick data
│   ├── price-board               # GET - Real-time prices
│   ├── {symbol}/company          # GET - Company info
│   └── {symbol}/financials/
│       ├── ratios                # GET - Financial ratios
│       ├── income                # GET - Income statement
│       └── balance-sheet         # GET - Balance sheet
└── auth/                         # (Planned)
    ├── login
    ├── register
    └── refresh
```

### Backend Layers
```
Router (HTTP) → Service (Business Logic) → vnstock/Repository
     ↓                    ↓                        ↓
  Schemas            Validation              Data Access
```

## Data Flow

1. **User Request** → Next.js handles routing and SSR
2. **API Call** → Next.js calls FastAPI endpoints
3. **Service Layer** → StockService wraps vnstock library
4. **External Data** → vnstock fetches from VCI/Vietnam exchanges
5. **Response** → Data flows back through layers as JSON

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

## Security Layers

- **Frontend**: HTTPS, CSP headers, XSS protection
- **API**: JWT auth (planned), CORS, input validation via Pydantic
- **Database**: Connection pooling, parameterized queries
- **Infrastructure**: Docker network isolation

## Future Considerations

### Caching Layer
- Redis for vnstock response caching
- Reduce API calls to external data source
- Cache invalidation on market close

### WebSocket Support
- Real-time price updates
- Portfolio value streaming
- Alert notifications
