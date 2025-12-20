# Project Roadmap - Stock Massive

## Current State (December 2024)

### Completed

- [x] Monorepo structure setup
- [x] Next.js frontend with App Router
- [x] Dashboard layout (sidebar, header, responsive)
- [x] Dark/light theme support (next-themes)
- [x] ShadCN/UI components (16 installed)
- [x] Dashboard components (14 feature components)
- [x] Stock detail page (search, header, stats, tabs)
- [x] Market indices cards with sparklines
- [x] FastAPI backend setup
- [x] vnstock integration (27 endpoints)
- [x] Financial statements (income, balance, cash flow)
- [x] Shareholders, officers, insider deals API
- [x] Intraday data collection (5-min bars)
- [x] Volume analysis endpoint
- [x] APScheduler for background jobs
- [x] Docker Compose configuration
- [x] Backend test suite (30+ tests)
- [x] Modern + Clean design system established

### In Progress

- [ ] Frontend feature pages (charts, portfolio, watchlist)
- [x] Sector Performance (100% - Full-stack complete)
- [x] Toast notifications (Sonner integration)
- [x] Fund certificates endpoint

---

## Phase 1: MVP (Target: Q1 2025)

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
- [ ] User model
- [ ] Watchlist model
- [ ] Portfolio model
- [ ] Alembic migrations for new models

---

## Phase 2: Core Features (Target: Q2 2025)

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

- [ ] Redis integration
- [ ] Cache vnstock responses
- [ ] Cache invalidation strategy
- [ ] Rate limiting

---

## Phase 3: Enhanced Features (Target: Q3 2025)

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

## Phase 4: Advanced Features (Target: Q4 2025)

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
- [x] Loading states and skeletons (completed)
- [ ] Form validation (react-hook-form + zod)

### Medium-term

- [x] API documentation (OpenAPI/Swagger) (completed)
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
| MVP | Q1 2025 | Auth, Charts, Stock List |
| Beta | Q2 2025 | Watchlist, Portfolio |
| v1.0 | Q3 2025 | Technical Analysis, Alerts |
| v2.0 | Q4 2025 | Real-time, Mobile, Social |

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

## Recently Completed (December 2024)

| Feature | Date | Notes |
|---------|------|-------|
| Toast Notifications | Dec 19, 2024 | Sonner integration on stock search |
| Sector Performance | Dec 19, 2024 | Full-stack: API + hook + UI component |
| Fund Certificates | Dec 2024 | New endpoint for fund data |
| Shareholders API | Dec 2024 | Major holders endpoint |
| Officers API | Dec 2024 | Company management endpoint |
| Insider Deals API | Dec 2024 | Insider trading endpoint |
| Volume Analysis | Dec 2024 | Peak period analysis |
| Volume Anomaly Detection (Backend API) | Dec 20, 2025 | New API for detailed anomaly detection |
| Volume Anomaly Detection (Frontend Chart) | Dec 20, 2025 | Frontend chart component with anomaly highlighting |
| Intraday Collection | Dec 2024 | 5-min bar aggregation |
| Stock Detail Page | Dec 2024 | Search, header, stats, tabs |
| Finance Tab | Dec 2024 | Income, balance, cash flow tables |
| Shareholders Tab | Dec 2024 | Holders, officers, insider deals |
| Design System | Dec 2024 | Modern + Clean established as standard |
| Custom Hooks | Dec 2024 | 8 hooks for data fetching |
