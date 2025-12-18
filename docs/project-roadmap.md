# Project Roadmap - Stock Massive

## Current State (December 2024)

### Completed
- [x] Monorepo structure setup
- [x] Next.js frontend with App Router
- [x] Dashboard layout (sidebar, header)
- [x] ShadCN/UI components (10 installed)
- [x] FastAPI backend setup
- [x] vnstock integration (10 endpoints)
- [x] Docker Compose configuration
- [x] Backend test suite (30 tests)

### In Progress
- [ ] Frontend feature pages (scaffolded only)

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
**Priority: High**
- [ ] TanStack Table integration
- [ ] Stock list with sorting/filtering
- [ ] Search by symbol/name
- [ ] Filter by exchange (HOSE, HNX, UPCOM)
- [ ] Filter by index (VN30, HNX30)
- [ ] Pagination

### 1.4 Database Models
**Priority: High**
- [ ] User model
- [ ] Watchlist model
- [ ] Portfolio model
- [ ] Alembic migrations

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

### 2.3 Company Information
**Priority: Medium**
- [ ] Company overview page
- [ ] Financial ratios display
- [ ] Income statement table
- [ ] Balance sheet table
- [ ] Key metrics cards

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
- [ ] In-app notifications
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
- [ ] Loading states and skeletons
- [ ] Form validation (react-hook-form + zod)

### Medium-term
- [ ] API documentation (OpenAPI/Swagger)
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
| Beta | Q2 2025 | Watchlist, Portfolio, Company Info |
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
