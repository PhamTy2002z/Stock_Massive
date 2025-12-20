# Project Overview - Stock Massive

## Purpose

Vietnamese stock market data platform powered by **vnstock** library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

## Goals

1. Display Vietnamese stock data with interactive charts
2. Provide sortable/filterable data tables for stock screening
3. Enable portfolio tracking and watchlist management
4. Secure user authentication and data persistence
5. Integrate vnstock library for comprehensive Vietnam market data
6. Implement advanced analytical features like Volume Anomaly Detection

---

## Current Implementation Status (December 2024)

| Feature | Status | Details |
|---------|--------|---------|
| Dashboard Layout | Done | Responsive sidebar, header, theme toggle |
| Stock Detail Page | Done | Search, ticker header, stats panel, tabs |
| Market Indices | Done | VN-INDEX, VN30, HNX, UPCOM cards with sparklines |
| Stock Data API | Done | 27 endpoints via vnstock |
| Financial Data | Done | Income, balance sheet, cash flow (detailed) |
| Shareholders/Officers | Done | Major holders, management, insider deals |
| Volume Analysis | Done | 5-min bar aggregation, peak period analysis |
| Intraday Collection | Done | Scheduled data collection (15:30 ICT) |
| Database Models | Done | IntradayBar model with SQLAlchemy |
| Sector Performance | Done | ICB Level 2 with sorting, auto-refresh |
| Toast Notifications | Done | Sonner integration for user feedback |
| Volume Anomaly Detection API | Done | New endpoint and core logic for detecting volume anomalies |
| Auth Pages | Scaffolded | Routes exist, logic pending |
| Charts Page | Scaffolded | Route exists, not implemented |
| Portfolio Page | Scaffolded | Route exists, not implemented |
| Watchlist Page | Scaffolded | Route exists, not implemented |

---

## Scope

### In Scope (Phase 1 - Current)

- Stock detail page with comprehensive data
- Market indices dashboard
- Data tables with financial statements
- REST API via vnstock integration
- Intraday data collection and storage
- Volume pattern analysis
- **Volume Anomaly Detection with API endpoint**

### In Scope (Phase 2 - Planned)

- Stock charting (candlestick, line, area)
- User authentication (JWT)
- Watchlist management
- Portfolio tracking
- **Frontend integration for Volume Anomaly Detection visualization**

### Data Sources

- **vnstock library** (VCI source): Primary data provider
  - Historical OHLCV data (daily, weekly, monthly)
  - Intraday tick data
  - Company information
  - Financial statements (income, balance sheet, cash flow)
  - Financial ratios
  - Price board (real-time)
  - Stock groups (VN30, HNX30, etc.)
  - Shareholders, officers, insider deals
  - **Volume Anomaly Data**

### Out of Scope (Phase 1)

- Real-time WebSocket streaming
- Mobile application
- Social features
- Automated trading
- Technical indicators calculation

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Monorepo | Simple workspace | Lower complexity, sufficient for single team |
| Frontend | Next.js 14.2 App Router | Modern React, SSR support, excellent DX |
| UI Library | ShadCN/UI | Accessible, customizable, Radix-based |
| Design Style | Modern + Clean | HSL colors, dark/light themes, consistent patterns |
| Tables | TanStack Table | Headless, powerful sorting/filtering |
| Charts | TradingView Lightweight | Industry standard, performant |
| Backend | FastAPI | Fast, async, auto-docs, type-safe |
| Data Source | vnstock >= 3.0.0 | Comprehensive Vietnam stock data |
| ORM | SQLAlchemy 2.0 | Mature, async support, migrations |
| Database | PostgreSQL 16 | Reliable, feature-rich, scalable |
| Scheduler | APScheduler 4.0 | Background job scheduling |
| **Volume Anomaly Detection Libraries** | **Pandas, Greenlet** | **Efficient data manipulation and asynchronous processing for anomaly detection** |

---

## API Design

### Endpoint Structure

All endpoints prefixed with `/api/v1/stocks`:

#### Symbol Listing
| Endpoint | Purpose |
|----------|---------|
| `GET /symbols` | List all symbols (filter by exchange) |
| `GET /symbols/group/{group}` | Symbols by group (VN30, HNX30) |
| `GET /symbols/search` | Search by ticker or company name |

#### Price Data
| Endpoint | Purpose |
|----------|---------|
| `GET /{symbol}/history` | Historical OHLCV |
| `GET /{symbol}/intraday` | Intraday ticks |
| `GET /market-indices` | VN-INDEX, VN30, HNX, UPCOM |
| `GET /price-board` | Real-time prices (multiple symbols) |
| `GET /{symbol}/detail` | Comprehensive stock detail |
| `GET /{symbol}/volume-anomalies` | **Retrieve volume anomaly detection results** |

#### Company & Financials
| Endpoint | Purpose |
|----------|---------|
| `GET /{symbol}/company` | Company overview |
| `GET /{symbol}/financials/ratios` | Financial ratios |
| `GET /{symbol}/financials/income` | Income statement (simple) |
| `GET /{symbol}/financials/income-statement` | Income statement (detailed) |
| `GET /{symbol}/financials/balance-sheet` | Balance sheet (simple) |
| `GET /{symbol}/financial-statement-detailed` | Balance sheet (detailed) |
| `GET /{symbol}/financials/cash-flow` | Cash flow statement |

#### Shareholders & Analysis
| Endpoint | Purpose |
|----------|---------|
| `GET /{symbol}/shareholders` | Major shareholders |
| `GET /{symbol}/officers` | Company officers/management |
| `GET /{symbol}/insider-deals` | Insider trading deals |
| `GET /{symbol}/volume-analysis` | Volume pattern analysis |
| `POST /intraday/collect` | Trigger intraday collection and **volume anomaly detection** |
| `GET /sector-performance` | Sector performance (ICB Level 2) |
| `GET /fund-certificates` | Fund certificates data |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| vnstock API rate limits | Implement caching layer, request throttling |
| Large dataset performance | Pagination, virtualization, lazy loading |
| Security vulnerabilities | OWASP guidelines, input validation |
| vnstock library changes | Pin version, monitor updates |
| Data accuracy | Cross-validate with official sources |
| **Complexity of Volume Anomaly Detection** | **Modularize logic, extensive testing, clear schema definitions** |

---

## Success Metrics

- Page load < 2s
- API response < 200ms (p95)
- Zero critical security vulnerabilities
- 80%+ test coverage on critical paths
- Support all VN30 stocks without errors
- **Accurate and timely detection of volume anomalies**

---

## Acceptance Criteria

### Phase 1 MVP (Current Focus)

- [x] User can view stock detail with price, company info, financials
- [x] User can search stocks by symbol or name
- [x] User can view market indices (VN-INDEX, VN30, HNX, UPCOM)
- [x] User can view financial statements (income, balance, cash flow)
- [x] User can view shareholders and insider deals
- [x] User can view sector performance (ICB Level 2)
- [x] User receives toast notifications on actions
- [x] API handles concurrent requests efficiently
- [x] **API provides volume anomaly detection results**
- [ ] User can view stock price charts
- [ ] User can register and login
- [ ] User can create watchlists

### Phase 2 (Planned)

- [ ] User can track portfolio positions
- [ ] User can set price alerts
- [ ] User can export data to CSV/Excel
- [ ] **Frontend visualization of volume anomalies on charts**
