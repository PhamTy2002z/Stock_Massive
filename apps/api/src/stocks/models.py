"""SQLAlchemy models for stocks module."""
from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, Numeric, String, UniqueConstraint
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
