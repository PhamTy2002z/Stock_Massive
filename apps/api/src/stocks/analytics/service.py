"""Analytics domain service."""

import logging
import time
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.vnstock_client import Listing
from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported

from src.core.cache import TradingHoursCache
from src.stocks.models import CohortMember, CohortVersion, StockDailyOHLCV
from src.stocks.shared import StockServiceError, fetch_industry_mapping
from src.stocks.schemas.analytics import (
    VolumeSpikeItem,
    IndustryVolumeSpikeGroup,
    VolumeSpikeMetadata,
    VolumeSpikeResponse,
)
from src.stocks.schemas.price import VolumeAnomalyLevel
from src.stocks.shared import StockServiceError, validate_symbol

logger = logging.getLogger(__name__)

# The HOSE/HSX aliasing this file used to carry went with the profit ranking it
# served. Board names are settled at the provider boundary now — see
# Exchange.parse in providers/contracts.py — so there is one place that knows
# "HSX" and "HOSE" are the same exchange.

# Constants for volume spike calculation
VOLUME_LOOKBACK_DAYS = 20
VOLUME_BUFFER_DAYS = 30  # Extra days for weekends/holidays
MIN_DATA_POINTS = VOLUME_LOOKBACK_DAYS + 1  # Current + 20 prior

# Volume spikes cache: 5min trading, 1hr off-hours
volume_spikes_cache = TradingHoursCache(
    key_prefix="stock:volume_spikes:",
    ttl_trading=300,       # 5 min during trading
    ttl_off_hours=3600,    # 1 hour off-hours
)


def build_volume_spikes_cache_key(
    target_date: Optional[date],
    min_ratio: float,
    exchange: Optional[str],
    include_upcom: bool,
    limit: int,
    top_profitable_only: bool,
) -> str:
    """Build cache key for volume spikes detection."""
    date_str = target_date.isoformat() if target_date else "latest"
    return f"{date_str}:{min_ratio}:{exchange or 'all'}:{include_upcom}:{limit}:{top_profitable_only}"


class AnalyticsService:
    """Service for analytics endpoints."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_volume_spikes(
        self,
        target_date: Optional[date] = None,
        min_ratio: float = 1.5,
        exchange: Optional[str] = None,
        include_upcom: bool = False,
        limit: int = 50,
        top_profitable_only: bool = False,
    ) -> VolumeSpikeResponse:
        """Detect volume spikes grouped by ICB industry.

        Args:
            target_date: Date to analyze (default: latest available)
            min_ratio: Minimum spike ratio threshold (default: 1.5x)
            exchange: Filter by exchange (HOSE/HNX)
            include_upcom: Include UPCOM stocks (default: False)
            limit: Max results per industry group
            top_profitable_only: Only show Top 50 profitable companies

        Returns:
            VolumeSpikeResponse with stocks grouped by ICB Level 2
        """
        start_time = time.time()

        # Get top 50 symbols if filter enabled
        top_symbols: Optional[set[str]] = None
        if top_profitable_only:
            top_symbols = await self._get_top_profitable_symbols()
            # No active cohort means the filter has nothing to filter by, and an
            # unfiltered answer is not the answer that was asked for.
            if not top_symbols:
                logger.info("Top 50 filter enabled but no active cohort - returning empty")
                return self._empty_response(target_date or date.today(), start_time)

        # 1. Get latest available date if not specified
        if target_date is None:
            latest_result = await self.db.execute(
                select(StockDailyOHLCV.trade_date)
                .order_by(desc(StockDailyOHLCV.trade_date))
                .limit(1)
            )
            latest_row = latest_result.scalar()
            if not latest_row:
                return self._empty_response(date.today(), start_time)
            target_date = latest_row

        # 2. Calculate date range for 20-day average (need 21 days: target + 20 prior)
        start_date = target_date - timedelta(days=VOLUME_BUFFER_DAYS)

        # 3. Fetch OHLCV data for date range
        query = select(
            StockDailyOHLCV.symbol,
            StockDailyOHLCV.trade_date,
            StockDailyOHLCV.volume,
            StockDailyOHLCV.close_price,
        ).where(
            and_(
                StockDailyOHLCV.trade_date >= start_date,
                StockDailyOHLCV.trade_date <= target_date,
                StockDailyOHLCV.volume > 0,
            )
        ).order_by(StockDailyOHLCV.symbol, desc(StockDailyOHLCV.trade_date))

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return self._empty_response(target_date, start_time)

        # 4. Group data by symbol and calculate spike ratios
        symbol_data = defaultdict(list)
        for row in rows:
            symbol_data[row.symbol].append({
                "date": row.trade_date,
                "volume": row.volume,
                "close_price": float(row.close_price) if row.close_price else None,
            })

        # 5. Get ICB mapping
        icb_mapping = self._get_icb_mapping()

        # 6. Calculate volume spikes
        spike_items = []
        for symbol, data_list in symbol_data.items():
            # Skip if not in top 50 (when filter enabled)
            if top_symbols is not None and symbol not in top_symbols:
                continue

            # Need at least 21 days of data (1 current + 20 for average)
            if len(data_list) < MIN_DATA_POINTS:
                continue

            # Sort by date descending (most recent first)
            data_list.sort(key=lambda x: x["date"], reverse=True)

            # Current day volume (target_date)
            current_data = data_list[0]
            if current_data["date"] != target_date:
                continue

            current_volume = current_data["volume"]
            close_price = current_data["close_price"]

            # Calculate 20-day average (excluding current day)
            prior_volumes = [d["volume"] for d in data_list[1:21]]
            if not prior_volumes:
                continue

            avg_volume = sum(prior_volumes) / len(prior_volumes)
            if avg_volume <= 0:
                continue

            spike_ratio = current_volume / avg_volume

            # Filter by minimum ratio
            if spike_ratio < min_ratio:
                continue

            # Get ICB info
            icb_info = icb_mapping.get(symbol, {})
            symbol_exchange = icb_info.get("exchange", "")

            # Filter by exchange
            if exchange and symbol_exchange != exchange.upper():
                continue
            if not include_upcom and symbol_exchange == "UPCOM":
                continue

            # Calculate price change (vs previous day)
            price_change_pct = None
            if len(data_list) > 1 and close_price and data_list[1]["close_price"]:
                prev_close = data_list[1]["close_price"]
                if prev_close > 0:
                    price_change_pct = round(((close_price - prev_close) / prev_close) * 100, 2)

            # Determine anomaly level
            anomaly_level = self._get_anomaly_level(spike_ratio)

            spike_items.append(VolumeSpikeItem(
                symbol=symbol,
                company_name=icb_info.get("company_name"),
                exchange=symbol_exchange or None,
                current_volume=current_volume,
                avg_volume_20d=int(avg_volume),
                spike_ratio=round(spike_ratio, 2),
                price_change_pct=price_change_pct,
                close_price=close_price,
                anomaly_level=anomaly_level,
                icb_code=icb_info.get("icb_code"),
                icb_name=icb_info.get("icb_name"),
            ))

        # 7. Group by ICB industry
        industry_groups = self._group_by_industry(spike_items, limit)

        # 8. Build response
        calc_time_ms = int((time.time() - start_time) * 1000)

        return VolumeSpikeResponse(
            trade_date=target_date,
            total_spikes=len(spike_items),
            industries=industry_groups,
            metadata=VolumeSpikeMetadata(
                calculation_time_ms=calc_time_ms,
                cache_hit=False,
                symbols_processed=len(symbol_data),
                symbols_with_spikes=len(spike_items),
            ),
        )

    def _get_icb_mapping(self) -> dict:
        """Get ICB industry mapping for all symbols.

        Raises:
            HTTPException: If ICB data unavailable from vnstock API
        """
        try:
            return fetch_industry_mapping(Listing())

        except HTTPException:
            raise
        except StockServiceError as e:
            logger.error(f"ICB mapping unavailable: {e}")
            raise HTTPException(
                status_code=503,
                detail="Industry classification data unavailable"
            )
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error fetching ICB mapping: {e}")
            raise HTTPException(
                status_code=503,
                detail="Industry classification service unavailable"
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ICB mapping: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to load industry classification data"
            )

    def _get_anomaly_level(self, ratio: float) -> VolumeAnomalyLevel:
        """Determine anomaly level based on spike ratio."""
        if ratio >= 3.0:
            return VolumeAnomalyLevel.VERY_HIGH
        elif ratio >= 2.0:
            return VolumeAnomalyLevel.HIGH
        elif ratio >= 1.5:
            return VolumeAnomalyLevel.ELEVATED
        return VolumeAnomalyLevel.NORMAL

    def _group_by_industry(
        self, items: list[VolumeSpikeItem], limit: int
    ) -> list[IndustryVolumeSpikeGroup]:
        """Group spike items by ICB industry."""
        groups = defaultdict(list)

        for item in items:
            key = (item.icb_code or "UNKNOWN", item.icb_name or "Chưa phân loại")
            groups[key].append(item)

        result = []
        for (icb_code, icb_name), stocks in groups.items():
            # Sort by spike ratio descending, limit per group
            stocks.sort(key=lambda x: x.spike_ratio, reverse=True)
            limited_stocks = stocks[:limit]

            avg_ratio = sum(s.spike_ratio for s in limited_stocks) / len(limited_stocks)

            result.append(IndustryVolumeSpikeGroup(
                icb_code=icb_code,
                icb_name=icb_name,
                spike_count=len(stocks),
                avg_spike_ratio=round(avg_ratio, 2),
                stocks=limited_stocks,
            ))

        # Sort groups by spike count descending
        result.sort(key=lambda x: x.spike_count, reverse=True)
        return result

    async def _get_top_profitable_symbols(self) -> set[str]:
        """The members of the active Cohort Version.

        Read from the cohort rather than re-derived here. There is one answer to
        "the fifty most profitable listed companies" in this system and the census
        owns it — two rankings computed in two places is what the removal of
        `financial_statements` was for.

        Only the *active* version, and no fallback to the newest candidate: a
        candidate is a ranking whose members are not evaluable yet, so filtering
        by it would ask for a signal on symbols with no baseline stored.
        """
        result = await self.db.execute(
            select(CohortMember.symbol)
            .join(CohortVersion, CohortVersion.id == CohortMember.cohort_version_id)
            .where(CohortVersion.state == "active")
        )
        symbols = {row.symbol for row in result.all()}
        if not symbols:
            logger.warning("No active Cohort Version for the top 50 filter")
        return symbols

    def _empty_response(self, target_date: date, start_time: float) -> VolumeSpikeResponse:
        """Return empty response when no data available."""
        return VolumeSpikeResponse(
            trade_date=target_date,
            total_spikes=0,
            industries=[],
            metadata=VolumeSpikeMetadata(
                calculation_time_ms=int((time.time() - start_time) * 1000),
                cache_hit=False,
                symbols_processed=0,
                symbols_with_spikes=0,
            ),
        )
