# Project Overview - Stock Massive

## Purpose
Vietnamese stock analysis platform powered by **vnstock** library. Provides real-time charting, data tables, and portfolio tracking for Vietnam stock market (HOSE, HNX, UPCOM).

## Goals
1. Display Vietnamese stock data with TradingView charts
2. Provide sortable/filterable data tables for stock screening
3. Enable portfolio tracking and watchlist management
4. Secure user authentication and data persistence
5. Integrate vnstock library for comprehensive Vietnam market data

## Current Implementation Status

| Feature | Status | Details |
|---------|--------|---------|
| Dashboard Layout | Done | Responsive sidebar, header |
| Stock Data API | Done | 10 endpoints via vnstock |
| Auth Pages | Scaffolded | Routes exist, logic pending |
| Charts Page | Scaffolded | Route exists, not implemented |
| Portfolio Page | Scaffolded | Route exists, not implemented |
| Watchlist Page | Scaffolded | Route exists, not implemented |
| Database Models | Pending | SQLAlchemy configured |
| User Auth | Pending | JWT config exists |

## Scope

### In Scope (Phase 1)
- Stock charting (candlestick, line, area) for VN stocks
- Data tables with TanStack Table
- User authentication (JWT)
- Watchlist management
- Portfolio tracking
- REST API via vnstock integration

### Data Sources
- **vnstock library** (VCI source): Primary data provider
  - Historical OHLCV data
  - Intraday tick data
  - Company information
  - Financial statements (income, balance sheet)
  - Financial ratios
  - Price board (real-time)
  - Stock groups (VN30, HNX30, etc.)

### Out of Scope (Phase 1)
- Real-time WebSocket streaming
- Mobile application
- Social features
- Automated trading
- Technical indicators calculation

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Monorepo | Simple workspace | Lower complexity, sufficient for single team |
| Frontend | Next.js 14.2 App Router | Modern React, SSR support, excellent DX |
| UI Library | ShadCN/UI (new-york) | Accessible, customizable, Radix-based |
| Tables | TanStack Table | Headless, powerful sorting/filtering |
| Charts | TradingView Lightweight | Industry standard, performant |
| Backend | FastAPI | Fast, async, auto-docs, type-safe |
| Data Source | vnstock >= 3.0.0 | Comprehensive Vietnam stock data |
| ORM | SQLAlchemy 2.0 | Mature, async support, migrations |
| Database | PostgreSQL 16 | Reliable, feature-rich, scalable |

## API Design

### Endpoint Structure
All endpoints prefixed with `/api/v1/stocks`:

| Endpoint | Purpose |
|----------|---------|
| `GET /symbols` | List all symbols |
| `GET /symbols/group/{group}` | Symbols by group |
| `GET /{symbol}/history` | Historical OHLCV |
| `GET /{symbol}/intraday` | Intraday ticks |
| `GET /price-board` | Real-time prices |
| `GET /{symbol}/company` | Company overview |
| `GET /{symbol}/financials/ratios` | Financial ratios |
| `GET /{symbol}/financials/income` | Income statement |
| `GET /{symbol}/financials/balance-sheet` | Balance sheet |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| vnstock API rate limits | Implement caching layer, request throttling |
| Large dataset performance | Pagination, virtualization, lazy loading |
| Security vulnerabilities | OWASP guidelines, input validation |
| vnstock library changes | Pin version, monitor updates |
| Data accuracy | Cross-validate with official sources |

## Success Metrics
- Page load < 2s
- API response < 200ms (p95)
- Zero critical security vulnerabilities
- 80%+ test coverage on critical paths
- Support all VN30 stocks without errors

## Acceptance Criteria

### Phase 1 MVP
- [ ] User can view stock price charts
- [ ] User can browse stock list with filtering
- [ ] User can view company financial data
- [ ] User can register and login
- [ ] User can create watchlists
- [ ] API handles 100 concurrent users
