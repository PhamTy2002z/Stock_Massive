# Project Overview - Stock Massive

## Purpose
Stock analysis platform providing real-time charting, data tables, and portfolio tracking for stock market analysis.

## Goals
1. Display real-time stock data with TradingView charts
2. Provide sortable/filterable data tables for stock screening
3. Enable portfolio tracking and watchlist management
4. Secure user authentication and data persistence

## Scope

### In Scope
- Stock charting (candlestick, line, area)
- Data tables with TanStack Table
- User authentication (JWT)
- Watchlist management
- Portfolio tracking
- REST API for data access

### Out of Scope (Phase 1)
- Real-time WebSocket streaming
- Mobile application
- Social features
- Automated trading

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Monorepo | Simple workspace | Lower complexity, sufficient for single team |
| Frontend | Next.js 14+ App Router | Modern React, SSR support, excellent DX |
| UI Library | ShadCN/UI | Accessible, customizable, Radix-based |
| Tables | TanStack Table | Headless, powerful sorting/filtering |
| Charts | TradingView Lightweight | Industry standard, performant |
| Backend | FastAPI | Fast, async, auto-docs, type-safe |
| ORM | SQLAlchemy 2.0 | Mature, async support, migrations |
| Database | PostgreSQL 16 | Reliable, feature-rich, scalable |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| API rate limits from data providers | Implement caching layer |
| Large dataset performance | Pagination, virtualization |
| Security vulnerabilities | OWASP guidelines, input validation |

## Success Metrics
- Page load < 2s
- API response < 200ms (p95)
- Zero critical security vulnerabilities
- 90%+ test coverage on critical paths
