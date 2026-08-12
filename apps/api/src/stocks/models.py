"""SQLAlchemy models for stocks module."""
from sqlalchemy import BigInteger, Column, Date, DateTime, Float, Index, Integer, JSON, Numeric, String, UniqueConstraint, text
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


class SymbolBackfill(Base):
    """How far the one-time history load has got for one symbol.

    Durable because the load is the most expensive thing this system asks of
    vnstock and must happen once. Held in the database rather than in memory so
    a restart mid-load resumes where it stopped instead of starting the whole
    stretch of history again — and so a symbol dropped from the Universe and
    added back only fetches what it is still missing.
    """

    __tablename__ = "symbol_backfills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True)
    status = Column(String(16), nullable=False)
    # The newest session already loaded. The next run starts the day after it.
    covered_through = Column(Date, nullable=True)
    last_error = Column(String(500), nullable=True)
    # How many times in a row this symbol has failed, and the soonest a run may
    # take it on again. A run only has a handful of slots and the Universe has a
    # hundred symbols: without a backoff, the same few permanent failures take
    # every slot every night and the symbols behind them are never reached.
    attempts = Column(Integer, nullable=False, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<SymbolBackfill {self.symbol} {self.status} through {self.covered_through}>"


class ProviderSnapshot(Base):
    """Append-only normalized provider data used for last-known-good reads."""

    __tablename__ = "provider_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    capability = Column(String(32), nullable=False)
    symbol = Column(String(20), nullable=False)
    source = Column(String(32), nullable=False)
    effective_at = Column(DateTime(timezone=True), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    schema_version = Column(Integer, nullable=False, default=1)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "capability",
            "symbol",
            "source",
            "effective_at",
            "schema_version",
            name="uq_provider_snapshot_identity",
        ),
        Index(
            "ix_provider_snapshot_latest",
            "capability",
            "symbol",
            "source",
            "observed_at",
        ),
        # Resolving a Trading Day asks which sessions exist across every symbol
        # at once, so it cannot use the index above — that one leads with a
        # symbol. See src/stocks/trading_day.py.
        Index(
            "ix_provider_snapshot_capability_effective",
            "capability",
            effective_at.desc(),
        ),
    )
