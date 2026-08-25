"""Read DNSE foreign-share evidence without writing it into EOD snapshots."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import RealtimeEvent
from src.stocks.realtime.contracts import (
    EventFamily,
    ForeignFlowSnapshot,
    MarketDataSource,
    QualityState,
)
from src.stocks.realtime.storage import deserialize_event


def foreign_share_flows_for_sessions(
    session: Session,
    symbol: str,
    sessions: Sequence[date],
) -> dict[date, int]:
    """Return the latest DNSE cumulative G1 net share flow for each session."""
    days = tuple(dict.fromkeys(sessions))
    if not days:
        return {}
    rows = session.scalars(
        select(RealtimeEvent)
        .where(
            RealtimeEvent.event_family == EventFamily.FOREIGN_FLOW.value,
            RealtimeEvent.source == MarketDataSource.DNSE.value,
            RealtimeEvent.symbol == symbol.upper(),
            RealtimeEvent.trading_day.in_(days),
        )
        .order_by(
            RealtimeEvent.provider_time,
            RealtimeEvent.observed_time,
            RealtimeEvent.evidence_id,
        )
    )
    latest: dict[date, ForeignFlowSnapshot] = {}
    for row in rows:
        event = deserialize_event(row.payload)
        if (
            isinstance(event, ForeignFlowSnapshot)
            and event.metadata.board == "G1"
        ):
            latest[event.metadata.trading_day] = event
    return {
        day: event.buy_volume - event.sell_volume
        for day, event in latest.items()
        if event.metadata.quality_state is QualityState.VALID
    }
