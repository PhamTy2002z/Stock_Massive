# FastAPI Backend Structure Report

**apps/api** - Vietnamese stock market data API

## 1. File Structure

apps/api/src/
├── main.py (FastAPI app entry, CORS, scheduler lifecycle)
├── core/ (Core utilities and infrastructure)
│   ├── cache.py (TradingHoursCache with Redis, dynamic TTL)
│   ├── config.py (Pydantic settings from env vars)
│   ├── database.py (SQLAlchemy async/sync engines)
│   ├── dependencies.py (FastAPI dependencies)
│   ├── ratelimit.py (RateLimiter class using Upstash Redis)
│   ├── redis.py (Redis client singleton)
│   ├── scheduler.py (APScheduler setup with 3 cron jobs)
│   └── vnstock_wrapper.py (Safe wrapper for vnstock with SystemExit protection)
└── stocks/ (Stock domain with DDD structure)
    ├── models.py (SQLAlchemy models: StockDailyOHLCV, StockIntradayBar)
    ├── router.py (Main router aggregator including domain routers)
    ├── service.py (StockService facade delegating to domain services)
    ├── intraday_collector.py (Intraday data collection and analysis)
    ├── jobs.py (Scheduled jobs - 3 functions)
    ├── schemas/ (Pydantic schemas - 36 total)
    │   ├── common.py (HistoryParams, ErrorResponse)
    │   ├── company.py (8 schemas)
    │   ├── financial.py (10 schemas)
    │   ├── market.py (6 schemas)
    │   └── price.py (12 schemas)
    ├── shared/ (Shared utilities)
    │   ├── converters.py, exceptions.py, validators.py
    ├── price/ (7 endpoints)
    │   ├── router.py, service.py, cache.py
    ├── market/ (6 endpoints)
    │   ├── router.py, service.py
    ├── company/ (5 endpoints)
    │   ├── router.py, service.py
    └── financial/ (5 endpoints)
        ├── router.py, service.py


## 2. API Endpoints (23 total)

Base URL: /api/v1/stocks

### Price Domain (7 endpoints)
- GET /{symbol}/history - Historical OHLCV (1D/1W/1M intervals)
- GET /{symbol}/intraday - Intraday tick data (up to 50K ticks)
- GET /market-indices - VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX
- GET /price-board - Real-time price board (max 50 symbols)
- POST /intraday/collect - Manual intraday collection trigger
- GET /{symbol}/volume-analysis - Intraday volume pattern analysis
- GET /{symbol}/volume-anomalies - Volume anomaly detection (72 time slots)

### Market Domain (6 endpoints)
- GET /symbols - List all symbols (filter by HOSE/HNX/UPCOM)
- GET /symbols/group/{group} - List by group (VN30, HNX30, VN100)
- GET /symbols/search - Search by ticker or company name
- GET /sector-performance - Market-cap weighted sector performance (ICB L2)
- GET /fund-certificates - ETFs and open-end funds (STOCK/BOND/BALANCED)
- GET /vn30-overview - VN30 index stocks with real-time prices

### Company Domain (5 endpoints)
- GET /{symbol}/company - Company overview
- GET /{symbol}/detail - Comprehensive stock detail (composite endpoint)
- GET /{symbol}/shareholders - Major shareholders
- GET /{symbol}/officers - Company officers (filter: working/resigned/all)
- GET /{symbol}/insider-deals - Insider trading deals

### Financial Domain (5 endpoints)
- GET /{symbol}/financials/ratios - Financial ratios (year/quarter, en/vi)
- GET /{symbol}/financials/income - Income statement simplified
- GET /{symbol}/financials/income-statement - Detailed income statement
- GET /{symbol}/financials/balance-sheet - Balance sheet simplified
- GET /{symbol}/financials/balance-sheet-detailed - Detailed balance sheet
- GET /{symbol}/financials/cash-flow - Detailed cash flow statement


## 3. Database Models and Schemas

### SQLAlchemy Models
File: D:/Stock_Massive/apps/api/src/stocks/models.py

- StockDailyOHLCV - Daily OHLCV data (symbol, trade_date, prices, volume)
- StockIntradayBar - 5-minute intraday bars (symbol, bar_time, OHLCV)

### Pydantic Schemas (36 total across 5 schema files)

Price schemas (12):
VolumeAnomalyLevel, StockPrice, IntradayTick, PriceBoardItem, MarketIndexItem,
IntradayBarCreate, IntradayBar, IntradayCollectionResult, VolumeTimePeriod,
VolumeAnalysisResponse, VolumeTimeSlot, VolumeAnomalyResponse

Market schemas (6):
SectorPerformanceItem, SectorPerformanceResponse, FundCertificateItem,
FundCertificatesResponse, VN30OverviewItem, VN30OverviewResponse

Company schemas (8):
CompanyOverview, StockSymbol, StockDetail, ShareholderItem, ShareholdersResponse,
OfficerItem, OfficersResponse, InsiderDealItem, InsiderDealsResponse

Financial schemas (10):
FinancialRatio, IncomeStatementItem, IncomeStatementRow, IncomeStatementResponse,
BalanceSheetItem, BalanceSheetRow, BalanceSheetResponse, CashFlowRow, CashFlowResponse

Common schemas (2):
HistoryParams, ErrorResponse


## 4. Service Layer Patterns

### Facade Pattern
File: D:/Stock_Massive/apps/api/src/stocks/service.py

- StockService aggregates 4 domain services (Price, Company, Financial, Market)
- Singleton pattern via @lru_cache(maxsize=1) on get_stock_service()
- Delegates all methods to specialized domain services
- Composite method: get_stock_detail() orchestrates price + company + ratios

### Domain Services
- PriceService (stocks/price/service.py) - Wraps vnstock Quote, Trading
- CompanyService (stocks/company/service.py) - Wraps Vnstock().stock()
- FinancialService (stocks/financial/service.py) - Wraps vnstock.Finance
- MarketService (stocks/market/service.py) - Wraps vnstock Listing, Trading, Fund

### Dependency Injection
- Services: get_stock_service() dependency
- Database: Depends(get_db) for async sessions
- Rate limiting: Depends(standard_rate_limit or heavy_rate_limit)


## 6. vnstock Library Integration

### Core Wrapper (core/vnstock_wrapper.py)

Problem: vnstock calls sys.exit() on rate limits, crashing entire application

Solution: Safe wrapper with SystemExit protection
- safe_vnstock_call() - Catches SystemExit, implements exponential backoff retry
- VnstockRateLimitError exception for rate limit failures
- Adaptive delay based on consecutive failures (1x to 8x multiplier)
- Failure tracking with 5-minute reset window

Wrapper Functions:
- get_stock_history() - Safely fetch OHLCV with retry logic
- get_all_symbols() - Safely fetch symbol list
- get_adaptive_delay() - Dynamic delay calculation based on failure rate

### Usage Across Codebase
- stocks/service.py - Uses Vnstock().stock() for company and financial data
- stocks/price/service.py - Uses vnstock.Quote and vnstock.Trading
- stocks/market/service.py - Uses vnstock.Listing, Trading, Fund
- stocks/company/service.py - Uses Vnstock().stock() for company info
- stocks/financial/service.py - Uses vnstock.Finance for financial statements
- stocks/jobs.py - Uses wrapper functions with rate limit handling

### Data Source
- Primary source: VCI (most reliable, configured in settings)
- TCBS discontinued and removed from codebase


## 7. Caching Implementation

### Redis-backed Cache (Upstash)

TradingHoursCache (core/cache.py):
- Dynamic TTL based on trading hours (9:00-15:00 Vietnam time)
- Short TTL during trading hours (15-300s)
- Longer TTL during off-hours (1-24h)
- Graceful degradation when Redis unavailable

Cache Instances:

Price router:
- market_indices_cache: 30s trading, 1h off-hours
- price_board_cache: 15s trading, 1h off-hours
- volume_anomaly_cache: From price.cache module

Market router:
- symbols_cache: 1h trading, 24h off-hours
- sector_performance_cache: 5min trading, 1h off-hours
- vn30_overview_cache: 5min trading, 1h off-hours

### In-Memory Cache
- @lru_cache(maxsize=1) on get_stock_service() for singleton pattern
- @lru_cache on specific methods in stocks/service.py

### Redis Client (core/redis.py)
- Singleton pattern via get_redis() function
- Uses upstash_redis.Redis client
- Supports dual naming conventions (upstash_redis_* and upstash_redis_rest_*)
- Logs warning if Redis credentials not configured


## 8. Rate Limiting Implementation

### RateLimiter (core/ratelimit.py)
- Sliding window algorithm using Upstash Redis
- Graceful degradation (allows requests if Redis unavailable)
- Two rate limit tiers:
  * standard_rate_limit: 100 requests per 60 seconds
  * heavy_rate_limit: 20 requests per 60 seconds

### Applied as Dependencies
All endpoints use dependencies=[Depends(standard_rate_limit)] or heavy_rate_limit

Heavy rate limit endpoints:
- All financial endpoints (ratios, income, balance sheet, cash flow)
- POST /intraday/collect
- GET /{symbol}/volume-anomalies

### vnstock-specific Rate Limiting
- Separate from API-level rate limiting
- Handled by vnstock_wrapper.py with SystemExit protection and retry logic
- VnstockRateLimitError raised when retries exhausted
- Scheduled jobs catch and skip rate-limited symbols


## Key Design Decisions

1. Domain-Driven Design
   - Price, Market, Company, Financial domains with dedicated routers and services
   - Clear separation of concerns and bounded contexts

2. Facade Pattern
   - StockService aggregates domain services
   - Provides backward compatibility while allowing modular architecture

3. Async/Sync Separation
   - Async for API endpoints (FastAPI)
   - Sync for background jobs (vnstock is blocking)

4. Resilient vnstock Integration
   - Safe wrapper prevents app crashes from SystemExit
   - Exponential backoff retry with adaptive delays
   - Graceful error handling for rate limits

5. Trading-aware Caching
   - Dynamic TTL based on market hours
   - Aggressive caching during off-hours to reduce API calls
   - Short TTL during trading for real-time data

6. Two-tier Rate Limiting
   - API-level rate limiting for endpoint protection
   - vnstock-level rate limiting for external API resilience
   - Graceful degradation when Redis unavailable

7. Scheduled Data Collection
   - Three cron jobs: intraday (15:30), cleanup (16:00), daily OHLCV (20:00)
   - Batch processing with configurable delays
   - Automatic retry and error handling

8. PostgreSQL + Redis Architecture
   - PostgreSQL for persistent OHLCV storage
   - Redis (Upstash) for caching and rate limiting
   - Dual async/sync database engines

## Key File Paths

Core:
- D:/Stock_Massive/apps/api/src/main.py
- D:/Stock_Massive/apps/api/src/core/config.py
- D:/Stock_Massive/apps/api/src/core/database.py
- D:/Stock_Massive/apps/api/src/core/vnstock_wrapper.py
- D:/Stock_Massive/apps/api/src/core/cache.py
- D:/Stock_Massive/apps/api/src/core/ratelimit.py
- D:/Stock_Massive/apps/api/src/core/scheduler.py

Stocks:
- D:/Stock_Massive/apps/api/src/stocks/service.py
- D:/Stock_Massive/apps/api/src/stocks/models.py
- D:/Stock_Massive/apps/api/src/stocks/jobs.py
- D:/Stock_Massive/apps/api/src/stocks/price/router.py
- D:/Stock_Massive/apps/api/src/stocks/market/router.py
- D:/Stock_Massive/apps/api/src/stocks/company/router.py
- D:/Stock_Massive/apps/api/src/stocks/financial/router.py

## Unresolved Questions

- Retention policy for StockDailyOHLCV? Only StockIntradayBar has 30-day cleanup.
- API authentication/authorization mechanisms? None visible in current scout.
- Error monitoring/logging strategy beyond standard Python logging?
- Database migration strategy? Alembic setup not visible in scout.
