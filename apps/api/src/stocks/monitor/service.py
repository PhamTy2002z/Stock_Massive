"""Application service for deterministic Market Monitor analytics."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster, ProviderSnapshot
from src.stocks.providers.contracts import Capability
from src.stocks.signals.corporate_actions import corporate_action_generation
from src.stocks.trading_day import market_generation
from src.stocks.universe import build_universe

from .analytics import (
    AdvanceDeclinePoint,
    BreadthReading,
    IndexReading,
    SectorReading,
    StockReading,
    ValuationReading,
    advance_decline_line,
    breadth,
    index_pulse,
    sector_rotation,
    stock_readings,
    valuation_regime,
)
from .frames import MarketFrameLoader, MonitorFrameSet
from .schemas import MonitorExchange


METHOD_VERSIONS = {
    "breadth": "breadth-v1",
    "index_pulse": "index-pulse-v1",
    "sector_rotation": "sector-rotation-v1",
    "valuation_regime": "valuation-regime-v1",
    "stock_screen": "stock-screen-v1",
    "foreign_flow": "foreign-flow-v1",
    "dnse_active_flow": "dnse-active-flow-v1",
}


@dataclass(frozen=True)
class MonitorAnalyticsSnapshot:
    frames: MonitorFrameSet
    breadth: BreadthReading
    indices: tuple[IndexReading, ...]
    sectors: tuple[SectorReading, ...]
    valuation: ValuationReading
    stocks: tuple[StockReading, ...]
    advance_decline_line: tuple[AdvanceDeclinePoint, ...]


class MarketMonitorService:
    """Compute every stored-data lens once over one common frame set."""

    def __init__(
        self,
        session: Session,
        *,
        universe_symbols: tuple[str, ...] | None = None,
    ) -> None:
        self.session = session
        self.loader = MarketFrameLoader(
            session,
            universe_symbols=universe_symbols,
        )

    def snapshot(
        self,
        exchange: MonitorExchange,
        *,
        as_of: date | None = None,
        window_days: int = 253,
        sector_code: str | None = None,
        sort_by: str = "symbol",
        descending: bool = False,
    ) -> MonitorAnalyticsSnapshot:
        frames = self.loader.load(
            exchange,
            as_of=as_of,
            window_days=window_days,
        )
        return MonitorAnalyticsSnapshot(
            frames=frames,
            breadth=breadth(frames.symbols, eligible=frames.eligible),
            indices=tuple(
                index_pulse(item)
                for _, item in sorted(
                    frames.indices.items(),
                    key=lambda pair: pair[0].value,
                )
            ),
            sectors=sector_rotation(
                frames.symbols,
                dict(frames.indices),
                dict(frames.sector_eligible_counts),
            ),
            valuation=valuation_regime(frames.valuations, eligible=frames.eligible),
            stocks=stock_readings(
                frames.symbols,
                sector_code=sector_code,
                sort_by=sort_by,
                descending=descending,
            ),
            advance_decline_line=advance_decline_line(frames.symbols),
        )


def monitor_cache_key(
    session: Session,
    *,
    exchange: MonitorExchange,
    as_of: date | None,
    window_days: int,
) -> str:
    """Name every mutable stored input so stale entries become unreachable."""
    valuation = session.execute(
        select(func.max(ProviderSnapshot.observed_at)).where(
            ProviderSnapshot.capability == Capability.VALUATION.value
        )
    ).scalar_one_or_none()
    roster = session.execute(
        select(func.max(ListingRoster.observed_at))
    ).scalar_one_or_none()
    universe_digest = hashlib.sha256(
        ",".join(build_universe(session).symbols).encode()
    ).hexdigest()[:16]

    def token(value: datetime | None) -> str:
        if value is None:
            return "none"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    versions = ",".join(f"{key}={value}" for key, value in sorted(METHOD_VERSIONS.items()))
    return ":".join(
        (
            exchange.value,
            as_of.isoformat() if as_of is not None else "latest",
            str(window_days),
            token(market_generation(session)),
            token(valuation),
            token(roster),
            token(corporate_action_generation(session)),
            universe_digest,
            versions,
        )
    )
