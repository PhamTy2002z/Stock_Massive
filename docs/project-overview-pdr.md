# Project Overview - Stock Massive

## Purpose

Vietnamese stock market data platform powered by **vnstock** library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

## Goals

1. Display Vietnamese stock data with interactive charts
2. Provide sortable/filterable data tables for stock screening
3. Enable portfolio tracking and watchlist management
4. Secure user authentication and data persistence
5. Integrate vnstock library for comprehensive Vietnam market data
6. Implement and visualize advanced analytical features (Volume Anomaly, Volume Spikes, Financial Statements)

---

## Current Implementation Status (Updated: 2024-12-24)

| Feature | Status | Details |
|---------|--------|---------|
| Dashboard Layout | Done | Responsive sidebar, header, theme toggle |
| Stock Detail Page | Done | Search, ticker header, stats panel, tabs |
| Analytics Deep-Dive | Done | Dedicated analytics page with SSR + TanStack Query |
| Analytics Volume Spikes | Done | Volume spike dashboard with treemap, pie chart, composed chart, tabs |
| Analytics Financial Statements | Done | Ranking table with filters (exchange, year, quarter) |
| Market Indices | Done | VN-INDEX, VN30, HNX, UPCOM cards with sparklines, 10s auto-refresh |
| VN30 Overview Table | Done | Real-time VN30 stocks (price, change, volume, mcap), 1-min refresh |
| Stock Data API | Done | 30+ endpoints via vnstock + Fmarket |
| Financial Data | Done | Income, balance sheet, cash flow (detailed) |
| Shareholders/Officers | Done | Major holders, management, insider deals |
| Volume Analysis | Done | 5-min bar aggregation, peak period analysis |
| Volume Spikes API | Done | Aggregated volume spike detection across all stocks |
| Intraday Collection | Done | Scheduled data collection (15:30 ICT) |
| Daily OHLCV Collection | Done | Scheduled daily (17:00 ICT) |
| Database Models | Done | StockDailyOHLCV, IntradayBar, FinancialStatement with SQLAlchemy |
| Sector Performance | Done | ICB Level 2 with sorting, auto-refresh, top gainers/losers |
| Toast Notifications | Done | Sonner integration for user feedback |
| Volume Anomaly Detection | Done | API endpoint + core logic, frontend visualization |
| Fund Certificates | Done | 7-item display via Fmarket API |
| Redis Caching | Done | Trading-hours-aware cache (7 endpoints) |
| Rate Limiting | Done | Sliding window (100/60s standard, 20/60s heavy) |
| Job Status API | Done | `/api/v1/jobs/status` for progress polling |
| Startup Job Recovery | Done | Non-blocking missed job recovery on API startup |
| Supabase Migration | Done | PostgreSQL migrated to Supabase cloud (SSL, pooling) |
| Job Progress UI | Done | Progress bar + notification panel in frontend |
| Auth Pages | Scaffolded | Routes exist, Supabase OAuth UI, logic pending |
| Charts Page | Planned | Route exists, TradingView integration planned |
| Portfolio Page | Planned | Route exists, not implemented |
| Watchlist Page | Planned | Route exists, not implemented |

---

## Scope

### In Scope (Phase 1 - Current)

- Stock detail page with comprehensive data
- Market indices dashboard
- Data tables with financial statements
- REST API via vnstock integration
- Intraday data collection and storage
- Volume pattern analysis
- Volume Anomaly Detection with API endpoint and Frontend Visualization
- Volume Spikes Dashboard with multiple visualization types
- Financial Statements ranking with filtering

### In Scope (Phase 2 - Planned)

- Stock charting (candlestick, line, area)
- User authentication (JWT)
- Watchlist management
- Portfolio tracking

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
  - Volume Anomaly Data
- **Fmarket API**: Used for `/fund-certificates` endpoint

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
| Frontend | Next.js 15.5.9 App Router | Modern React, SSR support, excellent DX |
| UI Library | ShadCN/UI | Accessible, customizable, Radix-based |
| Design Style | Modern + Clean | HSL colors, dark/light themes, consistent patterns |
| Tables | TanStack Table | Headless, powerful sorting/filtering |
| Charts | Recharts + TradingView | Sparklines now, full charts planned |
| Data Fetching | TanStack Query v5.90 | Server state management, caching, background sync |
| Backend | FastAPI | Fast, async, auto-docs, type-safe |
| Data Source | vnstock >= 3.0.0 | Comprehensive Vietnam stock data |
| Rate Limit Protection | vnstock_wrapper.py | Wraps vnstock calls with rate limit handling |
| ORM | SQLAlchemy 2.0 | Mature, async support, migrations |
| Database | Supabase PostgreSQL | Cloud-hosted, SSL, connection pooling, reliable |
| Scheduler | APScheduler 4.0 | Background job scheduling |
| Caching | Upstash Redis | Trading-hours-aware TTL, serverless-friendly |
| Rate Limiting | Redis sliding window | Efficient, distributed, granular control |
| Analytics | Pandas, Greenlet | Efficient data manipulation, async processing |

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
| `GET /{symbol}/volume-anomalies` | Retrieve volume anomaly detection results |

#### Analytics
| Endpoint | Purpose |
|----------|---------|
| `GET /analytics/volume-spikes` | Top volume spike stocks across market |
| `GET /analytics/financial-statements` | Top companies by net profit (limit, exchange, year, quarter) |

#### Company & Financials
| Endpoint | Purpose |
|----------|---------|
| `GET /{symbol}/company` | Company overview |
| `GET /{symbol}/financials/ratios` | Financial ratios |
| `GET /{symbol}/financials/income` | Income statement (simple) |
| `GET /{symbol}/financials/income-statement` | Income statement (detailed) |
| `GET /{symbol}/financials/balance-sheet` | Balance sheet (simple) |
| `GET /{symbol}/financials/balance-sheet-detailed` | Balance sheet (detailed) |
| `GET /{symbol}/financials/cash-flow` | Cash flow statement |

#### Shareholders & Analysis
| Endpoint | Purpose |
|----------|---------|
| `GET /{symbol}/shareholders` | Major shareholders |
| `GET /{symbol}/officers` | Company officers/management |
| `GET /{symbol}/insider-deals` | Insider trading deals |
| `GET /{symbol}/volume-analysis` | Volume pattern analysis |
| `POST /intraday/collect` | Trigger intraday collection |
| `GET /sector-performance` | Sector performance (ICB Level 2) |
| `GET /fund-certificates` | Fund certificates data |
| `GET /vn30-overview` | VN30 stocks overview |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| vnstock API rate limits | Implement caching layer, request throttling, vnstock_wrapper |
| Large dataset performance | Pagination, virtualization, lazy loading |
| Security vulnerabilities | OWASP guidelines, input validation |
| vnstock library changes | Pin version, monitor updates |
| Data accuracy | Cross-validate with official sources |
| Complexity of Analytics | Modularize logic, extensive testing, clear schema definitions |

---

## Success Metrics

- Page load < 2s
- API response < 200ms (p95)
- Zero critical security vulnerabilities
- 80%+ test coverage on critical paths
- Support all VN30 stocks without errors
- Accurate and timely detection and visualization of volume anomalies

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
- [x] API provides and Frontend visualizes volume anomaly detection results
- [x] User can view volume spikes dashboard with multiple chart types
- [x] User can view financial statements ranking with filters
- [ ] User can view stock price charts
- [ ] User can register and login
- [ ] User can create watchlists

### Phase 2 (Planned)

- [ ] User can track portfolio positions
- [ ] User can set price alerts
- [ ] User can export data to CSV/Excel
