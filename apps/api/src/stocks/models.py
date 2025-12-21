"""SQLAlchemy models for stocks module."""
from sqlalchemy import BigInteger, Column, Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.sql import func

from src.core.database import Base


class StockIntradayBar(Base):
    """5-minute OHLCV bar for intraday trading data."""
    __tablename__ = "stock_intraday_bars"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    bar_time = Column(DateTime, nullable=False)
    open_price = Column(Numeric(12, 2))
    high_price = Column(Numeric(12, 2))
    low_price = Column(Numeric(12, 2))
    close_price = Column(Numeric(12, 2))
    volume = Column(BigInteger, nullable=False)
    trade_value = Column(Numeric(18, 2))
    trade_count = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "bar_time", name="uq_symbol_bar_time"),
        Index("idx_intraday_symbol_date", "symbol", func.date(bar_time)),
    )

    def __repr__(self) -> str:
        return f"<StockIntradayBar {self.symbol} {self.bar_time}>"


class StockDailyReturn(Base):
    """Daily returns for stocks and indices (precomputed for market context)."""
    __tablename__ = "stock_daily_returns"

    symbol = Column(String(10), primary_key=True, nullable=False)
    date = Column(Date, primary_key=True, nullable=False)
    close_price = Column(Numeric(12, 2), nullable=False)
    return_1d = Column(Numeric(10, 6), nullable=True)  # Simple return
    return_1d_log = Column(Numeric(10, 6), nullable=True)  # Log return

    __table_args__ = (
        Index("ix_stock_daily_returns_symbol", "symbol"),
        Index("ix_stock_daily_returns_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<StockDailyReturn {self.symbol} {self.date}>"


class StockMarketMetric(Base):
    """Precomputed market correlation and beta metrics."""
    __tablename__ = "stock_market_metrics"

    symbol = Column(String(10), primary_key=True, nullable=False)
    date = Column(Date, primary_key=True, nullable=False)

    # vs VNINDEX
    corr_5d = Column(Numeric(6, 4), nullable=True)
    corr_20d = Column(Numeric(6, 4), nullable=True)
    corr_60d = Column(Numeric(6, 4), nullable=True)
    beta_20d = Column(Numeric(8, 4), nullable=True)
    beta_60d = Column(Numeric(8, 4), nullable=True)
    rs_market_20d = Column(Numeric(8, 4), nullable=True)  # Relative strength

    # vs Sector
    corr_sector_20d = Column(Numeric(6, 4), nullable=True)
    rs_sector_20d = Column(Numeric(8, 4), nullable=True)
    sector_rank = Column(Integer, nullable=True)
    sector_total = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_stock_market_metrics_symbol", "symbol"),
        Index("ix_stock_market_metrics_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<StockMarketMetric {self.symbol} {self.date}>"


class SectorDailyBenchmark(Base):
    """Market-cap weighted sector benchmarks."""
    __tablename__ = "sector_daily_benchmark"

    icb_code = Column(String(10), primary_key=True, nullable=False)
    date = Column(Date, primary_key=True, nullable=False)
    mcap_weighted_return = Column(Numeric(10, 6), nullable=False)
    total_mcap = Column(BigInteger, nullable=False)  # VND
    stock_count = Column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_sector_daily_benchmark_icb_code", "icb_code"),
        Index("ix_sector_daily_benchmark_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<SectorDailyBenchmark {self.icb_code} {self.date}>"
