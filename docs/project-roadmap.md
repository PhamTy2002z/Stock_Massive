# Project Roadmap - Stock Massive

Updated: 2025-12-24

## Current State (December 2025)

### Completed (December 2025)

- [x] Monorepo structure setup
- [x] Next.js 15.5.9 frontend with App Router
- [x] Dashboard layout (sidebar, header, responsive)
- [x] Dark/light theme support (next-themes)
- [x] ShadCN/UI components (20 primitives, 27 dashboard, 4 layout, 2 providers)
- [x] Stock detail page (search, header, stats, tabs)
- [x] Analytics deep-dive page (SSR + TanStack Query)
- [x] **Volume Spikes Dashboard** (treemap, pie chart, composed chart, tabs)
- [x] **Financial Statements Page** (ranking table with filters)
- [x] Market indices cards with sparklines (10s auto-refresh)
- [x] VN30 Overview Table (price, change, volume, mcap, 1-min refresh)
- [x] FastAPI backend setup
- [x] vnstock integration (30+ endpoints)
- [x] vnstock wrapper with rate limit protection
- [x] Financial statements (income, balance, cash flow)
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
- [x] **Supabase Migration** (PostgreSQL cloud with SSL, connection pooling)
- [x] **Job Progress UI** (progress bar + notification panel)
- [x] Docker Compose configuration (dev + prod)
- [x] Backend test suite (17+ tests in 9 files)
- [x] Modern + Clean design system established
- [x] Sector Performance (ICB Level 2, top gainers/losers)
- [x] Toast notifications (Sonner integration)
- [x] Fund certificates endpoint (7 items display)
- [x] Redis caching (Upstash, trading-hours-aware, 7 endpoints)
- [x] Rate limiting (sliding window, 100/60s standard, 20/60s heavy)
- [x] Transaction rollback on intraday data failure
- [x] Loading states and skeletons
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

## Recently Completed (December 2025)

| Feature | Date | Notes |
|---------|------|-------|
| Supabase Migration (Complete) | Dec 24, 2025 | DATABASE_URL_DIRECT, SSL config, connection pooling |
| Job Progress UI | Dec 24, 2025 | Progress bar + notification panel in frontend |
| Job Status API | Dec 24, 2025 | `/api/v1/jobs/status` for progress polling |
| Startup Job Recovery | Dec 24, 2025 | Non-blocking missed job recovery on API startup |
| Daily OHLCV Collection | Dec 24, 2025 | Scheduled job at 17:00 ICT |
| Supabase Migration (Phase 1) | Dec 24, 2025 | DATABASE_URL_DIRECT, SSL config |
| Volume Spikes Dashboard (Frontend) | Dec 23, 2025 | Treemap, pie chart, composed chart, tabs visualization |
| Rename Top Performers to Financial Statements | Dec 23, 2025 | UI/UX optimizations, Vietnamese translation |
| Financial Statements API Endpoint | Dec 22, 2025 | Analytics router with filters (limit, exchange, year, quarter) |
| Financial Statements Batch Job | Dec 22, 2025 | Weekly scheduled job for HOSE+HNX quarterly rankings |
| 10s Auto-Refresh | Dec 22, 2025 | Market indices refresh every 10s with loading indicators |
| vnstock Wrapper | Dec 22, 2025 | Rate limit protection wrapper for vnstock API calls |
| Transaction Rollback | Dec 22, 2025 | Added rollback on intraday data collection failures |
| VN30 Overview (Frontend) | Dec 21, 2025 | Dashboard table with pagination, auto-refresh (1min) |
| VN30 Overview (API) | Dec 21, 2025 | Backend endpoint with Redis caching (5min/1hr TTL) |
| Analytics Deep-Dive Page | Dec 21, 2025 | SSR + TanStack Query integration |
| Extended Caching | Dec 20, 2025 | 7 high-traffic endpoints with trading-hours-aware cache |
| Rate Limiting | Dec 20, 2025 | Sliding window (100/60s standard, 20/60s heavy) |
| Volume Anomaly (Frontend) | Dec 20, 2025 | Chart integration into stock detail page |
| Volume Anomaly (On-Demand) | Dec 20, 2025 | Auto-collect intraday data on endpoint request |
| Custom Hooks | Dec 20, 2025 | 12 hooks for data fetching |
| Shareholders Tab | Dec 20, 2025 | Holders, officers, insider deals |
| Finance Tab | Dec 20, 2025 | Income, balance, cash flow tables |
| Stock Detail Page | Dec 20, 2025 | Search, header, stats, tabs |
| Intraday Collection | Dec 20, 2025 | 5-min bar aggregation |
| Volume Anomaly (Backend) | Dec 20, 2025 | API for detailed anomaly detection |
| Volume Analysis | Dec 20, 2025 | Peak period analysis |
| Officers API | Dec 20, 2025 | Company management endpoint |
| Shareholders API | Dec 20, 2025 | Major holders endpoint |
| Fund Certificates | Dec 20, 2025 | New endpoint, adjusted to 7 items |
| Sector Performance | Dec 19, 2025 | Full-stack: API + hook + UI, top gainers/losers |
| Toast Notifications | Dec 19, 2025 | Sonner integration on stock search |
| Design System | Dec 20, 2025 | Modern + Clean established as standard |

### Notes on Reverted Features

- **Market Context Feature** (Dec 21, 2025): Reverted due to vnstock API rate limits. Feature attempted to provide broader market context but exceeded rate limits in production.
