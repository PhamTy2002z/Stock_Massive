"""Main stocks router aggregating domain routers.

Path matching order is critical:
- Market router first: /symbols, /symbols/*, /sector-performance, /fund-certificates
- Price router: /market-indices, /price-board, /intraday/collect, /{symbol}/history, etc.
- Company router: /{symbol}/company, /{symbol}/detail, /{symbol}/shareholders, etc.
- Financial router: /{symbol}/financials/*
"""

from fastapi import APIRouter

# Import routers directly from router modules to avoid circular imports
from .market.router import router as market_router
from .price.router import router as price_router
from .company.router import router as company_router
from .financial.router import router as financial_router

# Main router with prefix and tags
router = APIRouter(prefix="/stocks", tags=["stocks"])

# Include domain routers in order (path matching order matters)
# 1. Market router first - matches /symbols, /sector-performance, /fund-certificates
router.include_router(market_router)

# 2. Price router - matches /market-indices, /price-board, /intraday/collect, /{symbol}/*
router.include_router(price_router)

# 3. Company router - matches /{symbol}/company, /{symbol}/detail, etc.
router.include_router(company_router)

# 4. Financial router - matches /{symbol}/financials/*
router.include_router(financial_router)
