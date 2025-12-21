"""Main stocks router aggregating domain routers.

Path matching order is critical:
- Market router first: /symbols, /symbols/*, /sector-performance, /fund-certificates
- Market context router: /market-context/* (manual triggers)
- Price router: /market-indices, /price-board, /intraday/collect, /{symbol}/history, etc.
- Company router: /{symbol}/company, /{symbol}/detail, /{symbol}/shareholders, etc.
- Financial router: /{symbol}/financials/*
"""

from fastapi import APIRouter

# Import routers directly from router modules to avoid circular imports
from .market.router import router as market_router
from .market_context_router import router as market_context_router
from .price.router import router as price_router
from .company.router import router as company_router
from .financial.router import router as financial_router

# Main router with prefix and tags
router = APIRouter(prefix="/stocks", tags=["stocks"])

# Include domain routers in order (path matching order matters)
# 1. Market router first - matches /symbols, /sector-performance, /fund-certificates
router.include_router(market_router)

# 2. Market context router - matches /market-context/*
router.include_router(market_context_router)

# 3. Price router - matches /market-indices, /price-board, /intraday/collect, /{symbol}/*
router.include_router(price_router)

# 4. Company router - matches /{symbol}/company, /{symbol}/detail, etc.
router.include_router(company_router)

# 5. Financial router - matches /{symbol}/financials/*
router.include_router(financial_router)
