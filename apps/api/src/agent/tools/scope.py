"""The shared deterministic Universe boundary for every symbol tool."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster, ProviderSnapshot
from src.stocks.providers import Capability, main_source
from src.stocks.universe import Universe

ADTV_SESSIONS = 20
UniverseFactory = Callable[[Session], Universe]


def adtv_by_symbol(
    session: Session,
    symbols: Sequence[str],
    end: date | None,
) -> dict[str, float]:
    """Rank suggestions and screens from the same dated stored-money measure."""

    if not symbols:
        return {}
    value = cast(ProviderSnapshot.payload["total_value_vnd"].as_string(), Float)
    filters = [
        ProviderSnapshot.capability == Capability.MARKET.value,
        ProviderSnapshot.source == main_source(Capability.MARKET).value,
        ProviderSnapshot.symbol.in_(symbols),
        value.is_not(None),
    ]
    if end is not None:
        filters.append(
            ProviderSnapshot.effective_at
            < datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )
    numbered = (
        select(
            ProviderSnapshot.symbol.label("symbol"),
            value.label("value"),
            func.row_number()
            .over(
                partition_by=ProviderSnapshot.symbol,
                order_by=ProviderSnapshot.effective_at.desc(),
            )
            .label("position"),
        )
        .where(*filters)
        .subquery()
    )
    rows = session.execute(
        select(numbered.c.symbol, func.avg(numbered.c.value))
        .where(numbered.c.position <= ADTV_SESSIONS)
        .group_by(numbered.c.symbol)
    ).all()
    return {str(symbol): float(average) for symbol, average in rows}


def structured_universe_refusal(
    session: Session,
    universe_factory: UniverseFactory,
    symbol: str,
    trading_day: date,
) -> Mapping[str, Any] | None:
    """Return the shared refusal, including dated same-industry alternatives."""

    universe = universe_factory(session)
    if universe.contains(symbol):
        return None
    industry = session.execute(
        select(ListingRoster.icb_code).where(ListingRoster.symbol == symbol)
    ).scalar_one_or_none()
    if not industry or not universe.symbols:
        suggestions: list[str] = []
    else:
        candidates = tuple(
            session.execute(
                select(ListingRoster.symbol).where(
                    ListingRoster.icb_code == industry,
                    ListingRoster.is_listed.is_(True),
                    ListingRoster.symbol.in_(universe.symbols),
                )
            ).scalars()
        )
        ranked = adtv_by_symbol(session, candidates, trading_day)
        suggestions = sorted(
            candidates,
            key=lambda item: (ranked.get(item, -1), item),
            reverse=True,
        )[:3]
    return {"reason": "not_in_universe", "suggestions": suggestions}


__all__ = ["ADTV_SESSIONS", "adtv_by_symbol", "structured_universe_refusal"]
