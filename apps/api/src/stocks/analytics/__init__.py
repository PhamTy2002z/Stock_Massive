"""Analytics domain module."""
from .router import router as analytics_router
from .service import AnalyticsService

__all__ = ["analytics_router", "AnalyticsService"]
