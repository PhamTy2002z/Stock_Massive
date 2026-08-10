"""Folding stored sessions into the bars a chart draws.

Kept apart from the router because it is arithmetic, not routing: a week's high
is the highest of its sessions whether it is being served over HTTP or checked
in a test. Kept apart from ``SnapshotStore`` too — the store answers in
ingestion contracts, and a bar is a shape the interface asked for.
"""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta

from .providers.contracts import MarketSnapshot, SymbolSnapshot
from .providers.normalize import VN_TZ
from .schemas.snapshot import MarketBar

# What the store can be asked to draw. Anything finer than a session is not in
# it: the collector writes one bar a day, and #6 puts in-session flow out of
# scope, so sub-daily granularity stays on the frozen provider-backed route.
SESSION_INTERVALS = ("1D", "1W", "1M")


def bucket(session: date, interval: str) -> date:
    """The period a session's bar is filed under.

    A week is filed under its Monday and a month under its first day, so two
    symbols that took different holidays still line up bar for bar.
    """
    if interval == "1W":
        return session - timedelta(days=session.weekday())
    if interval == "1M":
        return session.replace(day=1)
    return session


def _summed(values: Sequence[float | int | None]) -> float | int | None:
    """Add the sessions' figures, or refuse when any of them is missing.

    A partial sum is the worst of both answers: a smaller number that looks
    like a total, with nothing on the wire to say part of the period was left
    out. It happens at the seam between sources — the Cover Source's history
    carries volume but no traded value — so a week straddling it would have
    reported a few days' turnover as the week's.
    """
    if not values or any(value is None for value in values):
        return None
    return sum(values)  # type: ignore[arg-type]


def _bar(period_start: date, sessions: Sequence[MarketSnapshot]) -> MarketBar:
    """Fold one period's sessions into the bar a chart draws.

    Open is the first session's open and close the last one's, so the bar spans
    the period rather than sampling it, and it is dated by the period rather
    than by whichever session happened to open it. The source is the last
    session's: a period straddling the seam between providers is mostly the
    newer one, and the field answers "who measured the close of this bar".
    """
    return MarketBar(
        effective_at=datetime.combine(period_start, time.min, tzinfo=VN_TZ),
        source=sessions[-1].metadata.source.value,
        open_price=sessions[0].open_price,
        high_price=max(
            (s.high_price for s in sessions if s.high_price is not None), default=None
        ),
        low_price=min(
            (s.low_price for s in sessions if s.low_price is not None), default=None
        ),
        close_price=sessions[-1].last_price,
        volume=_summed([s.volume for s in sessions]),
        total_value_vnd=_summed([s.total_value_vnd for s in sessions]),
    )


def bars(snapshots: Sequence[SymbolSnapshot], interval: str) -> list[MarketBar]:
    """Group stored sessions into periods, oldest first."""
    periods: dict[date, list[MarketSnapshot]] = {}
    for snapshot in snapshots:
        if not isinstance(snapshot, MarketSnapshot):
            continue
        session_day = snapshot.metadata.effective_at.astimezone(VN_TZ).date()
        periods.setdefault(bucket(session_day, interval), []).append(snapshot)
    return [_bar(period_start, sessions) for period_start, sessions in sorted(periods.items())]
