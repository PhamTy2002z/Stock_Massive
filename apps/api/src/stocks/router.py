"""Main stocks router aggregating domain routers.

Path matching order is critical:
- Market router first: /symbols, /symbols/*, /sector-performance, /fund-certificates
- Price router: /market-indices, /price-board, /intraday/collect, /{symbol}/history, etc.
- Company router: /{symbol}/company, /{symbol}/detail, /{symbol}/shareholders, etc.
- Financial router: /{symbol}/financials/*
- Trading router: /{symbol}/intraday-order-stats
"""

from fastapi import APIRouter

# Import routers directly from router modules to avoid circular imports
from .market.router import router as market_router
from .price.router import router as price_router
from .company.router import router as company_router
from .financial.router import router as financial_router
from .analytics.router import router as analytics_router
from .trading.router import router as trading_router
from .snapshot_router import router as snapshot_router

# Main router with prefix and tags
router = APIRouter(prefix="/stocks", tags=["stocks"])

# Include domain routers in order (path matching order matters)
# 1. Market router first - matches /symbols, /sector-performance, /fund-certificates
router.include_router(market_router)

# 2. Snapshot router - matches /{symbol}/snapshot, the store-backed serving path
router.include_router(snapshot_router)

# 3. Price router - matches /market-indices, /price-board, /intraday/collect, /{symbol}/*
router.include_router(price_router)

# 3. Company router - matches /{symbol}/company, /{symbol}/detail, etc.
router.include_router(company_router)

# 4. Financial router - matches /{symbol}/financials/*
router.include_router(financial_router)

# 5. Analytics router - matches /analytics/*
router.include_router(analytics_router)

# 6. Trading router - matches /{symbol}/intraday-order-stats
router.include_router(trading_router)
