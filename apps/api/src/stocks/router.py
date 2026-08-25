"""Main stocks router aggregating domain routers.

Path matching order is critical:
- News router first: /news/feed, which a /{symbol} route would otherwise claim
  with symbol="news"
- Market router: /symbols, /symbols/*, /sector-performance, /fund-certificates
- Snapshot router: /{symbol}/snapshot, served from the store rather than upstream
- Price router: /market-indices, /price-board, /intraday/collect, /{symbol}/history, etc.
- Company router: /{symbol}/company, /{symbol}/detail, /{symbol}/shareholders, etc.
- Financial router: /{symbol}/financials/*
- Trading router: /{symbol}/intraday-order-stats
"""

from fastapi import APIRouter

# Import routers directly from router modules to avoid circular imports
from .news.router import router as news_router
from .market.router import router as market_router
from .price.router import router as price_router
from .company.router import router as company_router
from .financial.router import router as financial_router
from .analytics.router import router as analytics_router
from .trading.router import router as trading_router
from .snapshot_router import router as snapshot_router
from .monitor.router import router as monitor_router

# Main router with prefix and tags
router = APIRouter(prefix="/stocks", tags=["stocks"])

# Include domain routers in order (path matching order matters)
# 1. News router first - matches /news/feed, ahead of every /{symbol} route so
#    the feed is never served as the company news of a symbol called "news"
router.include_router(news_router)

# 2. Market router - matches /symbols, /sector-performance, /fund-certificates
router.include_router(market_router)

# Market Monitor routes precede every symbol-shaped route.
router.include_router(monitor_router)

# 3. Snapshot router - matches /{symbol}/snapshot, the store-backed serving path
router.include_router(snapshot_router)

# 4. Price router - matches /market-indices, /price-board, /intraday/collect, /{symbol}/*
router.include_router(price_router)

# 5. Company router - matches /{symbol}/company, /{symbol}/detail, etc.
router.include_router(company_router)

# 6. Financial router - matches /{symbol}/financials/*
router.include_router(financial_router)

# 7. Analytics router - matches /analytics/*
router.include_router(analytics_router)

# 8. Trading router - matches /{symbol}/intraday-order-stats
router.include_router(trading_router)
