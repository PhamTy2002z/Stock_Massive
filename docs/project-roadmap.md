# Project Roadmap - Stock Massive

Updated: 2026-01-03

## Current State (January 2026)

**Phase 1 MVP Progress: ~85% Complete**

### Completed (December 2024 - January 2026)

- [x] Monorepo structure setup
- [x] Next.js 15.5.9 frontend with App Router
- [x] Dashboard layout (sidebar, header, responsive)
- [x] Dark/light theme support (next-themes)
- [x] ShadCN/UI components (25+ primitives, 35+ dashboard widgets, 6 layout, 2 providers)
- [x] Custom hooks (28 total for data fetching, responsive, job status)
- [x] Stock detail page (search, header, stats, tabs)
- [x] Analytics deep-dive page (SSR + TanStack Query)
- [x] **Volume Spikes Dashboard** (treemap, pie chart, composed chart, tabs)
- [x] **Financial Statements Page** (ranking table with filters)
- [x] **Financial Health Scorecard** (5-dimension radar, Piotroski F-Score)
- [x] **Peer Comparison** (top 5 sector peers with heatmap table)
- [x] **FCF Analysis** (waterfall chart, CCC indicator with DSO/DIO/DPO)
- [x] **Market Overview** (breadth, top movers, foreign flow, top volume)
- [x] Market indices cards with sparklines (10s auto-refresh)
- [x] VN30 Overview Table (price, change, volume, mcap, 1-min refresh)
- [x] **Sector Historical Performance** (1D, 1W, 1M, 3M, 6M, 1Y with horizontal bar chart)
- [x] **Smooth Loading Pattern** (keepPreviousData for tab/filter transitions)
- [x] **Prefetch Optimization** (adjacent tab prefetch on mount + hover-based prefetch)
- [x] FastAPI backend setup
- [x] vnstock integration (43+ endpoints)
- [x] vnstock wrapper with rate limit protection
- [x] Financial statements (income, balance, cash flow)
- [x] Financial health APIs (health-score, trend-metrics, sector-peers)
- [x] Shareholders, officers, insider deals API
- [x] Intraday data collection (5-min bars)
- [x] **Daily OHLCV collection** (17:00 ICT)
- [x] Volume analysis endpoint
- [x] Volume anomaly detection (API + frontend)
- [x] **Volume Spikes API** (aggregated across all stocks)
- [x] **Financial Statements API** (top companies by net profit)
- [x] APScheduler for background jobs
- [x] **Job Status API** (`/api/v1/jobs/status` for progress polling)
- [x] **Startup Job Recovery** (non-blocking missed job recovery)
- [x] **Database via `DATABASE_URL`** (Docker `db` in dev, any Postgres in prod)
- [x] **Job Progress UI** (progress bar + notification panel)
- [x] Docker Compose configuration (dev: db + api, frontend on host; prod: api + web)
- [x] Backend test suite (26 test files)
- [x] Modern + Clean design system established
- [x] Sector Performance (ICB Level 2, top gainers/losers)
- [x] **Sector Historical Performance** (period-based sector returns with horizontal bar chart)
- [x] Toast notifications (Sonner integration)
- [x] Fund certificates endpoint (7 items display)
- [x] Redis caching (Upstash, trading-hours-aware, 7 endpoints)
- [x] Rate limiting (sliding window, 100/60s standard, 20/60s heavy)
- [x] Transaction rollback on intraday data failure
- [x] Loading states and skeletons
- [x] **Smooth Section Loading** (keepPreviousData pattern for tab/filter transitions)
- [x] API documentation (OpenAPI/Swagger)

### In Progress

- [ ] Frontend feature pages (charts, portfolio, watchlist)
- [ ] Authentication system implementation

---

## Phase 1: MVP (Target: Q1 2026)

### 1.1 Authentication System

**Priority: High**

- [ ] User registration endpoint
- [ ] Login/logout with JWT
- [ ] Password hashing (bcrypt)
- [ ] Token refresh mechanism
- [ ] Frontend auth pages implementation
- [ ] Protected route middleware

### 1.2 Stock Charts

**Priority: High**

- [ ] TradingView Lightweight Charts integration
- [ ] Candlestick chart component
- [ ] Line/area chart options
- [ ] Time interval selector (1D, 1W, 1M, 1Y)
- [ ] Volume overlay
- [ ] Connect to `/stocks/{symbol}/history` API

### 1.3 Stock List & Screening

**Priority: Medium**

- [ ] TanStack Table integration
- [ ] Stock list with sorting/filtering
- [ ] Search by symbol/name
- [ ] Filter by exchange (HOSE, HNX, UPCOM)
- [ ] Filter by index (VN30, HNX30)
- [ ] Pagination

### 1.4 Database Models

**Priority: High**

- [x] IntradayBar model (completed)
- [x] FinancialStatement model (completed)
- [ ] User model
- [ ] Watchlist model
- [ ] Portfolio model
- [ ] Alembic migrations for new models

---

## Phase 2: Core Features (Target: Q2 2026)

### 2.1 Watchlist Management

**Priority: Medium**

- [ ] Create/delete watchlists
- [ ] Add/remove stocks from watchlist
- [ ] Watchlist overview with prices
- [ ] Multiple watchlists per user

### 2.2 Portfolio Tracking

**Priority: Medium**

- [ ] Add stock positions (buy/sell)
- [ ] Calculate P&L
- [ ] Portfolio value chart
- [ ] Position history

### 2.3 Company Information Page

**Priority: Medium**

- [x] Company overview (completed)
- [x] Financial ratios display (completed)
- [x] Income statement table (completed)
- [x] Balance sheet table (completed)
- [x] Cash flow statement (completed)
- [x] Shareholders tab (completed)
- [ ] Key metrics cards enhancement

### 2.4 Caching Layer

**Priority: Medium**

- [x] Redis integration (completed)
- [x] Cache vnstock responses (completed)
- [ ] Cache invalidation strategy
- [x] Rate limiting (completed)

---

## Phase 3: Enhanced Features (Target: Q3 2026)

### 3.1 Technical Analysis

**Priority: Low**

- [ ] Moving averages (SMA, EMA)
- [ ] RSI indicator
- [ ] MACD indicator
- [ ] Bollinger Bands
- [ ] Custom indicator support

### 3.2 Alerts & Notifications

**Priority: Low**

- [ ] Price alerts
- [ ] Email notifications
- [ ] In-app notifications (sonner)
- [ ] Alert management UI

### 3.3 Data Export

**Priority: Low**

- [ ] Export to CSV
- [ ] Export to Excel
- [ ] PDF reports

---

## Phase 4: Advanced Features (Target: Q4 2026)

### 4.1 Real-time Updates

**Priority: Low**

- [ ] WebSocket server
- [ ] Real-time price streaming
- [ ] Live portfolio updates

### 4.2 Mobile Optimization

**Priority: Low**

- [ ] PWA support
- [ ] Mobile-first redesign
- [ ] Touch-friendly charts

### 4.3 Social Features

**Priority: Low**

- [ ] Public watchlists
- [ ] User profiles
- [ ] Comments/discussions

---

## Technical Debt & Improvements

### Short-term

- [ ] Add frontend tests (Vitest + RTL)
- [ ] API error handling improvements
- [ ] Form validation (react-hook-form + zod)

### Medium-term

- [ ] Logging and monitoring
- [ ] CI/CD pipeline
- [ ] E2E tests (Playwright)

### Long-term

- [ ] Performance optimization
- [ ] Accessibility audit (WCAG)
- [ ] Internationalization (i18n)
- [ ] Security audit

---

## Milestones

| Milestone | Target Date | Key Deliverables |
|-----------|-------------|------------------|
| MVP | Q1 2026 | Auth, Charts, Stock List |
| Beta | Q2 2026 | Watchlist, Portfolio |
| v1.0 | Q3 2026 | Technical Analysis, Alerts |
| v2.0 | Q4 2026 | Real-time, Mobile, Social |

---

## Dependencies & Blockers

### External Dependencies

- vnstock library stability
- VCI data source availability
- TradingView Lightweight Charts updates

### Potential Blockers

- vnstock API rate limits
- Data accuracy issues
- Performance with large datasets

---

## Recently Completed (December 2024 - January 2026)

| Feature | Date | Notes |
|---------|------|-------|
| Prefetch Optimization | Jan 3, 2026 | Adjacent tab prefetch on mount + hover-based prefetch (200ms delay) for instant tab switching |
| Smooth Section Loading | Jan 2, 2026 | Dashboard sections use keepPreviousData pattern for smooth refetch (no skeleton flash) |
| Documentation Update | Jan 3, 2026 | Comprehensive documentation refresh with accurate file counts (140+ frontend, 53 backend), feature lists, and latest scout findings |
| Sector Historical Performance | Dec 30, 2025 | Period-based sector returns (1D-1Y) with horizontal bar chart |
| Market Overview Frontend | Dec 30, 2025 | Breadth, top movers, foreign flow, top volume components |
| Market Overview API | Dec 30, 2025 | Aggregated market-overview endpoint |
| Financial Health Enhancement (Phase 4) | Dec 28, 2025 | Peer Comparison, FCF Waterfall, CCC indicator with heatmap |
| Financial Health Enhancement (Phase 2) | Dec 28, 2025 | Health Scorecard UI: Radar chart, F-Score, score breakdown |
| Financial Health Enhancement (Phase 1) | Dec 28, 2025 | Backend APIs: health-score, trend-metrics, fcf-analysis, sector-peers |
| Supabase Migration (later reverted) | Dec 24, 2024 | Moved to cloud Postgres; now a single `DATABASE_URL` with SSL auto-detection |
| Job Progress UI | Dec 24, 2024 | Progress bar + notification panel in frontend |
| Job Status API | Dec 24, 2024 | `/api/v1/jobs/status` for progress polling |
| Volume Spikes Dashboard (Frontend) | Dec 23, 2024 | Treemap, pie chart, composed chart, tabs visualization |
| Financial Statements API Endpoint | Dec 22, 2024 | Analytics router with filters (limit, exchange, year, quarter) |
| Redis Caching | Dec 20, 2024 | Trading-hours-aware cache for 7 high-traffic endpoints |
| Rate Limiting | Dec 20, 2024 | Sliding window (100/60s standard, 20/60s heavy) |

### Notes on Reverted Features

- **Market Context Feature** (Dec 21, 2024): Reverted due to vnstock API rate limits. Feature attempted to provide broader market context but exceeded rate limits in production.
