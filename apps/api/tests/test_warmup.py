"""The bounded, repeatable load that makes a symbol evaluable."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot
from src.stocks.providers import (
    MARKET_SCHEMA_VERSION,
    Capability,
    MarketSnapshot,
    ProviderSource,
    SnapshotMetadata,
    SnapshotStore,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.warmup import Warmup, WarmupUnavailable

from .conftest import basis_of

NOW = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)


def open_store() -> tuple[SnapshotStore, Session]:
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    session = Session(engine)
    return SnapshotStore(session, redis=None), session


def market_snapshot(
    day: date,
    symbol: str = "VCB",
    source: ProviderSource = ProviderSource.FIINQUANT,
) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=source,
            effective_at=datetime.combine(day, datetime.min.time(), tzinfo=VN_TZ),
            observed_at=NOW,
            schema_version=MARKET_SCHEMA_VERSION,
        ),
        price_basis=basis_of(source),
        last_price=59_700,
        volume=1_000,
    )


class RecordingHistory:
    """A Main Source that answers with the sessions it was given."""

    source = ProviderSource.FIINQUANT

    def __init__(self, sessions_by_symbol: dict[str, list[date]]):
        self._sessions = sessions_by_symbol
        self.windows: list[tuple[str, date, date]] = []

    def fetch_market_history(self, symbol, from_date, to_date):
        self.windows.append((symbol, from_date, to_date))
        return tuple(
            market_snapshot(day, symbol=symbol)
            for day in self._sessions.get(symbol, [])
        )


class BrokenHistory:
    source = ProviderSource.FIINQUANT

    def fetch_market_history(self, symbol, from_date, to_date):
        raise ConnectionError("gateway unavailable")


class CoverHistory:
    source = ProviderSource.VNSTOCK

    def fetch_market_history(self, symbol, from_date, to_date):  # pragma: no cover
        raise AssertionError("a Warm-up must never read the Cover Source")


def stored_sessions(session: Session, symbol: str = "VCB") -> list[date]:
    rows = session.execute(
        select(ProviderSnapshot.effective_at)
        .where(
            ProviderSnapshot.capability == Capability.MARKET.value,
            ProviderSnapshot.symbol == symbol,
        )
        .order_by(ProviderSnapshot.effective_at.asc())
    ).scalars()
    return [stamp.date() for stamp in rows]


def build(history, window: int = 25) -> tuple[Warmup, Session]:
    store, session = open_store()
    return (
        Warmup(
            store=store,
            history=history,
            now=lambda: NOW,
            window_trading_days=window,
        ),
        session,
    )


def test_warmup_writes_every_session_in_the_window():
    days = [date(2026, 8, 3) + timedelta(days=offset) for offset in range(5)]
    warmup, session = build(RecordingHistory({"VCB": days}))

    summary = warmup.run(["VCB"])

    assert summary.completed == ("VCB",)
    assert summary.sessions_written == 5
    assert stored_sessions(session) == days


def test_re_running_the_same_window_writes_no_duplicates():
    """Repeatability is the point: it is how a missed cycle gets repaired."""
    days = [date(2026, 8, 3) + timedelta(days=offset) for offset in range(5)]
    history = RecordingHistory({"VCB": days})
    warmup, session = build(history)

    warmup.run(["VCB"])
    warmup.run(["VCB"])

    total = session.execute(
        select(func.count()).select_from(ProviderSnapshot)
    ).scalar_one()
    assert total == 5


def test_warmup_keeps_only_the_newest_sessions_in_the_window():
    """The calendar span reaches past the window to survive the holidays.

    Bounded has to be a property of what is written, not only of what was asked
    for, or a quiet stretch of market silently turns a Warm-up into a Backfill.
    """
    days = [date(2026, 7, 1) + timedelta(days=offset) for offset in range(10)]
    warmup, session = build(RecordingHistory({"VCB": days}), window=4)

    warmup.run(["VCB"])

    assert stored_sessions(session) == days[-4:]


def test_the_window_asked_for_reaches_back_past_the_sessions_needed():
    """Five sessions a week is seven calendar days, plus room for a holiday."""
    history = RecordingHistory({"VCB": []})
    warmup, _ = build(history, window=25)

    warmup.run(["VCB"])

    _, from_date, to_date = history.windows[0]
    assert to_date == date(2026, 8, 13)
    assert (to_date - from_date).days > 25


def test_warmup_reads_only_the_market_capability():
    days = [date(2026, 8, 10)]
    warmup, session = build(RecordingHistory({"VCB": days}))

    warmup.run(["VCB"])

    capabilities = set(
        session.execute(select(ProviderSnapshot.capability)).scalars()
    )
    assert capabilities == {Capability.MARKET.value}


def test_warmup_refuses_the_cover_source():
    """ADR-0002: the two sources disagree on units, so a swap is never silent."""
    store, _ = open_store()

    with pytest.raises(WarmupUnavailable):
        Warmup(store=store, history=CoverHistory())


def test_one_failed_symbol_costs_only_that_symbol():
    class HalfBroken:
        source = ProviderSource.FIINQUANT

        def fetch_market_history(self, symbol, from_date, to_date):
            if symbol == "FPT":
                raise ConnectionError("gateway unavailable")
            return (market_snapshot(date(2026, 8, 10), symbol=symbol),)

    warmup, session = build(HalfBroken())

    summary = warmup.run(["FPT", "VCB"])

    assert summary.completed == ("VCB",)
    assert [item.symbol for item in summary.failed] == ["FPT"]
    assert "ConnectionError" in summary.failed[0].reason
    assert stored_sessions(session, "VCB") == [date(2026, 8, 10)]


def test_a_provider_outage_is_reported_rather_than_raised():
    warmup, _ = build(BrokenHistory())

    summary = warmup.run(["VCB"])

    assert summary.completed == ()
    assert summary.sessions_written == 0
    assert len(summary.failed) == 1
