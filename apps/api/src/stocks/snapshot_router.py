"""The serving path: what the store holds for one watched symbol.

Nothing here reaches a Provider Source. The collector is the only place that
does, so an evening when the provider is down still answers with the last
session it wrote.
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.core.database import get_sync_session
from src.core.ratelimit import standard_rate_limit

from .providers import Capability, SnapshotRead, SnapshotStore
from .providers.normalize import VN_TZ
from .providers.contracts import MarketSnapshot, SymbolSnapshot, ValuationSnapshot
from .schemas.snapshot import (
    FundamentalSection,
    MarketBar,
    MarketSection,
    MarketSeriesResponse,
    ReferenceSection,
    SymbolSnapshotResponse,
    ValuationPoint,
    ValuationSection,
    ValuationSeriesResponse,
)
from .shared import StockServiceError, validate_symbol
from .universe import get_universe

router = APIRouter()

# One row per part of the answer. Adding a capability here is all it takes to
# serve it, because the section is built from the stored snapshot rather than
# field by field.
SECTION_BY_CAPABILITY = {
    Capability.MARKET: MarketSection,
    Capability.VALUATION: ValuationSection,
    Capability.REFERENCE: ReferenceSection,
    Capability.FUNDAMENTAL: FundamentalSection,
}


def _section(capability: Capability, read: SnapshotRead):
    """Turn one stored snapshot into the part of the answer it belongs to."""
    metadata = read.snapshot.metadata
    return SECTION_BY_CAPABILITY[capability](
        source=metadata.source.value,
        effective_at=metadata.effective_at,
        observed_at=metadata.observed_at,
        age_seconds=read.age_seconds,
        stale=read.stale,
        data=read.snapshot.model_dump(mode="json", exclude={"symbol", "metadata"}),
    )


def _watched(symbol: str) -> str:
    """The canonical symbol, or a refusal that says which kind of wrong it is.

    Malformed text and an untracked company are answered apart. Both are
    refusals, but one is the caller's typo and the other is a symbol this
    system has simply not been asked to follow — a user told the wrong one goes
    looking for the wrong fix.

    The untracked case is worded as what this system did or did not do, never
    as a claim about the symbol itself: with no provider in the request path,
    nothing here knows whether an unknown ticker is listed, delisted or a typo.
    """
    try:
        canonical = validate_symbol(symbol)
    except StockServiceError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Mã chứng khoán không hợp lệ: {symbol}",
        ) from exc

    if not get_universe().contains(canonical):
        raise HTTPException(
            status_code=404,
            detail=f"Hệ thống chưa thu thập dữ liệu cho mã {canonical}.",
        )
    return canonical


@router.get(
    "/{symbol}/snapshot",
    response_model=SymbolSnapshotResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_symbol_snapshot(
    symbol: str,
    db: Session = Depends(get_sync_session),
) -> SymbolSnapshotResponse:
    """Serve the last session this system collected for one watched symbol.

    Malformed text and an untracked company are answered apart, the same way
    every store-backed route here answers them.
    """
    canonical = _watched(symbol)

    store = SnapshotStore(db)
    sections = {}
    for capability in SECTION_BY_CAPABILITY:
        read = store.latest(capability, canonical)
        sections[capability.value] = _section(capability, read) if read else None

    return SymbolSnapshotResponse(symbol=canonical, **sections)


# What the store can be asked to draw. Anything finer than a session is not in
# it: the collector writes one bar a day, and #6 puts in-session flow out of
# scope, so sub-daily granularity stays on the frozen provider-backed route.
SESSION_INTERVALS = ("1D", "1W", "1M")

# How far a default window reaches when the caller names only its start.
DEFAULT_SERIES_DAYS = 365


def _window(start: date | None, end: date | None) -> tuple[date, date]:
    """Settle the asked-for window, refusing one that runs backwards."""
    end = end or datetime.now(VN_TZ).date()
    start = start or end - timedelta(days=DEFAULT_SERIES_DAYS)
    if start > end:
        raise HTTPException(
            status_code=400,
            detail="Ngày bắt đầu phải trước ngày kết thúc.",
        )
    return start, end


def _bucket(session: date, interval: str) -> date:
    """The day a session's bar is filed under.

    A week is filed under its Monday and a month under its first day, so the
    bar is dated by the period it covers rather than by whichever session
    happened to open it — two symbols with different holidays then line up.
    """
    if interval == "1W":
        return session - timedelta(days=session.weekday())
    if interval == "1M":
        return session.replace(day=1)
    return session


def _summed(values: list[float | int | None]) -> float | int | None:
    """Add what is there, or report nothing when nothing is.

    A bar whose sessions all lack volume must not claim zero traded: that is a
    figure, and the honest answer is that the store does not hold it.
    """
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _bar(sessions: Sequence[MarketSnapshot]) -> MarketBar:
    """Fold one period's sessions into the bar a chart draws.

    Open is the first session's open and close the last one's, so the bar spans
    the period rather than sampling it. The source is the last session's: a week
    that straddles the seam between providers is mostly the newer one, and the
    field answers "who measured this bar" rather than "who measured every part".
    """
    return MarketBar(
        effective_at=sessions[0].metadata.effective_at,
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


def _bars(snapshots: Sequence[SymbolSnapshot], interval: str) -> list[MarketBar]:
    """Group the sessions into periods, oldest first."""
    periods: dict[date, list[MarketSnapshot]] = {}
    for snapshot in snapshots:
        session_day = snapshot.metadata.effective_at.astimezone(VN_TZ).date()
        periods.setdefault(_bucket(session_day, interval), []).append(snapshot)
    return [_bar(sessions) for _, sessions in sorted(periods.items())]


@router.get(
    "/{symbol}/series/market",
    response_model=MarketSeriesResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_market_series(
    symbol: str,
    start: date | None = Query(None, description="First session (YYYY-MM-DD)"),
    end: date | None = Query(None, description="Last session (YYYY-MM-DD)"),
    interval: str = Query("1D", description=f"One of: {', '.join(SESSION_INTERVALS)}"),
    db: Session = Depends(get_sync_session),
) -> MarketSeriesResponse:
    """Serve a stretch of sessions for one watched symbol, out of the store.

    Nothing here reaches a Provider Source. The deep years were loaded once by
    `Backfill` and each session since by the `Collector`, and both stretches are
    read together — every bar says which of them answered for it.
    """
    canonical = _watched(symbol)
    if interval not in SESSION_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Khoảng thời gian không hợp lệ. Dùng một trong: "
                f"{', '.join(SESSION_INTERVALS)}."
            ),
        )
    from_date, to_date = _window(start, end)

    series = SnapshotStore(db).series(Capability.MARKET, canonical, from_date, to_date)
    return MarketSeriesResponse(
        symbol=canonical,
        interval=interval,
        age_seconds=series.age_seconds,
        stale=series.stale,
        points=_bars(series.snapshots, interval),
    )


@router.get(
    "/{symbol}/series/valuation",
    response_model=ValuationSeriesResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_valuation_series(
    symbol: str,
    start: date | None = Query(None, description="First session (YYYY-MM-DD)"),
    end: date | None = Query(None, description="Last session (YYYY-MM-DD)"),
    db: Session = Depends(get_sync_session),
) -> ValuationSeriesResponse:
    """Serve P/E and P/B session by session, so a symbol can be read against itself.

    No interval: a weekly P/E would have to be an average, and an average of a
    ratio is a claim this system has no basis to make.
    """
    canonical = _watched(symbol)
    from_date, to_date = _window(start, end)

    series = SnapshotStore(db).series(
        Capability.VALUATION, canonical, from_date, to_date
    )
    return ValuationSeriesResponse(
        symbol=canonical,
        age_seconds=series.age_seconds,
        stale=series.stale,
        points=[
            ValuationPoint(
                effective_at=snapshot.metadata.effective_at,
                source=snapshot.metadata.source.value,
                provider_pe=snapshot.provider_pe,
                provider_pb=snapshot.provider_pb,
            )
            for snapshot in series.snapshots
            if isinstance(snapshot, ValuationSnapshot)
        ],
    )
