"""Analytics domain service."""

import logging
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.stocks.models import TopPerformer
from src.stocks.schemas.analytics import TopPerformerItem, TopPerformersResponse

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics endpoints."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_top_performers(
        self,
        limit: int = 50,
        exchange: Optional[str] = None,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
    ) -> TopPerformersResponse:
        """Get top performers ranked by net profit."""

        # If no period specified, get latest available
        if year is None or quarter is None:
            latest = await self.db.execute(
                select(TopPerformer.year, TopPerformer.quarter)
                .order_by(desc(TopPerformer.year), desc(TopPerformer.quarter))
                .limit(1)
            )
            row = latest.first()
            if row:
                year, quarter = row.year, row.quarter
            else:
                # No data yet
                return TopPerformersResponse(
                    period="N/A",
                    updated_at=None,
                    total=0,
                    data=[]
                )

        # Build query
        query = select(TopPerformer).where(
            TopPerformer.year == year,
            TopPerformer.quarter == quarter
        )

        if exchange:
            query = query.where(TopPerformer.exchange == exchange.upper())

        query = query.order_by(TopPerformer.rank.asc()).limit(limit)

        result = await self.db.execute(query)
        rows = result.scalars().all()

        # Get total count
        count_query = select(func.count()).select_from(TopPerformer).where(
            TopPerformer.year == year,
            TopPerformer.quarter == quarter
        )
        if exchange:
            count_query = count_query.where(TopPerformer.exchange == exchange.upper())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get latest update time
        updated_at = None
        if rows:
            updated_at = max(r.updated_at for r in rows if r.updated_at)

        return TopPerformersResponse(
            period=f"Q{quarter}-{year}",
            updated_at=updated_at,
            total=total,
            data=[TopPerformerItem.model_validate(r) for r in rows]
        )
