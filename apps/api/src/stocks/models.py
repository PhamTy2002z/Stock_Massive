"""SQLAlchemy models for stocks module."""
from sqlalchemy import BigInteger, Column, Date, DateTime, Float, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.sql import func

from src.core.database import Base


class StockDailyOHLCV(Base):
    """Daily OHLCV data for stocks."""
    __tablename__ = "stock_daily_ohlcv"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    trade_date = Column(Date, nullable=False)
    open_price = Column(Numeric(12, 2))
    high_price = Column(Numeric(12, 2))
    low_price = Column(Numeric(12, 2))
    close_price = Column(Numeric(12, 2))
    volume = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_daily_symbol_date"),
        Index("idx_daily_symbol_date", "symbol", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StockDailyOHLCV {self.symbol} {self.trade_date}>"


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


class FinancialStatement(Base):
    """Financial statements - quarterly financial metrics for companies."""
    __tablename__ = "financial_statements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    company_name = Column(String(255))
    exchange = Column(String(10))  # HOSE, HNX
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    net_profit = Column(BigInteger)  # VND
    revenue = Column(BigInteger)  # VND
    profit_margin = Column(Float)  # percentage
    eps = Column(Float)
    rank = Column(Integer, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "year", "quarter", name="uq_financial_statements_symbol_period"),
        Index("ix_financial_statements_period", "year", "quarter"),
        Index("ix_financial_statements_exchange", "exchange"),
    )

    def __repr__(self) -> str:
        return f"<FinancialStatement {self.symbol} Q{self.quarter}/{self.year}>"
