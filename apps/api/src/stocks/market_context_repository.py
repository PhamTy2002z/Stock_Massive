"""Repository layer for market context data access."""
from datetime import date
from typing import List, Optional, Set

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .models import SectorDailyBenchmark, StockDailyReturn, StockMarketMetric

# Whitelist of allowed metric fields to prevent attribute injection
ALLOWED_METRIC_FIELDS: Set[str] = {
    "corr_5d", "corr_20d", "corr_60d",
    "beta_20d", "beta_60d",
    "rs_market_20d", "corr_sector_20d", "rs_sector_20d",
    "sector_rank", "sector_total",
}


class MarketContextRepository:
    """Data access layer for market context tables."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Daily Returns ====================

    def upsert_daily_return(
        self,
        symbol: str,
        target_date: date,
        close_price: float,
        return_1d: Optional[float],
        return_1d_log: Optional[float],
    ) -> StockDailyReturn:
        """Insert or update daily return record."""
        stmt = select(StockDailyReturn).where(
            and_(StockDailyReturn.symbol == symbol, StockDailyReturn.date == target_date)
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.close_price = close_price
            existing.return_1d = return_1d
            existing.return_1d_log = return_1d_log
        else:
            existing = StockDailyReturn(
                symbol=symbol,
                date=target_date,
                close_price=close_price,
                return_1d=return_1d,
                return_1d_log=return_1d_log,
            )
            self.db.add(existing)

        self.db.commit()
        self.db.refresh(existing)
        return existing

    def get_daily_returns(
        self, symbol: str, start_date: date, end_date: date
    ) -> List[StockDailyReturn]:
        """Get daily returns for symbol in date range."""
        stmt = (
            select(StockDailyReturn)
            .where(
                and_(
                    StockDailyReturn.symbol == symbol,
                    StockDailyReturn.date >= start_date,
                    StockDailyReturn.date <= end_date,
                )
            )
            .order_by(StockDailyReturn.date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_daily_return(self, symbol: str, target_date: date) -> Optional[StockDailyReturn]:
        """Get single daily return record."""
        stmt = select(StockDailyReturn).where(
            and_(StockDailyReturn.symbol == symbol, StockDailyReturn.date == target_date)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    # ==================== Market Metrics ====================

    def upsert_market_metric(self, symbol: str, target_date: date, **metrics) -> StockMarketMetric:
        """Insert or update market metrics."""
        stmt = select(StockMarketMetric).where(
            and_(StockMarketMetric.symbol == symbol, StockMarketMetric.date == target_date)
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            for key, value in metrics.items():
                if key in ALLOWED_METRIC_FIELDS:
                    setattr(existing, key, value)
        else:
            # Filter metrics to only allowed fields
            filtered_metrics = {k: v for k, v in metrics.items() if k in ALLOWED_METRIC_FIELDS}
            existing = StockMarketMetric(symbol=symbol, date=target_date, **filtered_metrics)
            self.db.add(existing)

        self.db.commit()
        self.db.refresh(existing)
        return existing

    def get_latest_metric(self, symbol: str) -> Optional[StockMarketMetric]:
        """Get most recent metric for symbol."""
        stmt = (
            select(StockMarketMetric)
            .where(StockMarketMetric.symbol == symbol)
            .order_by(StockMarketMetric.date.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_market_metrics(
        self, symbol: str, start_date: date, end_date: date
    ) -> List[StockMarketMetric]:
        """Get market metrics for symbol in date range."""
        stmt = (
            select(StockMarketMetric)
            .where(
                and_(
                    StockMarketMetric.symbol == symbol,
                    StockMarketMetric.date >= start_date,
                    StockMarketMetric.date <= end_date,
                )
            )
            .order_by(StockMarketMetric.date)
        )
        return list(self.db.execute(stmt).scalars().all())

    # ==================== Sector Benchmarks ====================

    def upsert_sector_benchmark(
        self,
        icb_code: str,
        target_date: date,
        mcap_weighted_return: float,
        total_mcap: int,
        stock_count: int,
    ) -> SectorDailyBenchmark:
        """Insert or update sector benchmark."""
        stmt = select(SectorDailyBenchmark).where(
            and_(SectorDailyBenchmark.icb_code == icb_code, SectorDailyBenchmark.date == target_date)
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.mcap_weighted_return = mcap_weighted_return
            existing.total_mcap = total_mcap
            existing.stock_count = stock_count
        else:
            existing = SectorDailyBenchmark(
                icb_code=icb_code,
                date=target_date,
                mcap_weighted_return=mcap_weighted_return,
                total_mcap=total_mcap,
                stock_count=stock_count,
            )
            self.db.add(existing)

        self.db.commit()
        self.db.refresh(existing)
        return existing

    def get_sector_benchmark(
        self, icb_code: str, start_date: date, end_date: date
    ) -> List[SectorDailyBenchmark]:
        """Get sector benchmark for date range."""
        stmt = (
            select(SectorDailyBenchmark)
            .where(
                and_(
                    SectorDailyBenchmark.icb_code == icb_code,
                    SectorDailyBenchmark.date >= start_date,
                    SectorDailyBenchmark.date <= end_date,
                )
            )
            .order_by(SectorDailyBenchmark.date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_sector_benchmark_single(
        self, icb_code: str, target_date: date
    ) -> Optional[SectorDailyBenchmark]:
        """Get single sector benchmark record."""
        stmt = select(SectorDailyBenchmark).where(
            and_(SectorDailyBenchmark.icb_code == icb_code, SectorDailyBenchmark.date == target_date)
        )
        return self.db.execute(stmt).scalar_one_or_none()
