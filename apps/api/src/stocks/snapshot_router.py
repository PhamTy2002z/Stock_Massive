"""The serving path: what the store holds for one watched symbol.

Nothing here reaches a Provider Source. The collector is the only place that
does, so an evening when the provider is down still answers with the last
session it wrote.
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.core.database import get_sync_session
from src.core.ratelimit import standard_rate_limit

from .providers import Capability, SnapshotRead, SnapshotStore
from .providers.normalize import VN_TZ
from .providers.contracts import ValuationSnapshot
from .schemas.snapshot import (
    FundamentalSection,
    MarketSection,
    MarketSeriesResponse,
    ReferenceSection,
    SymbolSnapshotResponse,
    ValuationPoint,
    ValuationSection,
    ValuationSeriesResponse,
)
from .series_view import SESSION_INTERVALS, bars
from .shared import StockServiceError, validate_symbol
from .universe import build_universe

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


def _watched(symbol: str, db: Session) -> str:
    """The canonical symbol, or a refusal that says which kind of wrong it is.

    Malformed text and an untracked company are answered apart. Both are
    refusals, but one is the caller's typo and the other is a symbol this
    system has simply not been asked to follow — a user told the wrong one goes
    looking for the wrong fix.

    The untracked case is worded as what this system did or did not do, never
    as a claim about the symbol itself: with no provider in the request path,
    nothing here knows whether an unknown ticker is listed, delisted or a typo.

    Membership is read through the session because half the Universe is the
    active Cohort Version: a symbol the census seated this morning is watched
    from this morning, and a process-lifetime cache would have gone on refusing
    it until the next deploy.
    """
    try:
        canonical = validate_symbol(symbol)
    except StockServiceError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Mã chứng khoán không hợp lệ: {symbol}",
        ) from exc

    if not build_universe(db).contains(canonical):
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
    canonical = _watched(symbol, db)

    store = SnapshotStore(db)
    sections = {}
    for capability in SECTION_BY_CAPABILITY:
        read = store.latest(capability, canonical)
        sections[capability.value] = _section(capability, read) if read else None

    return SymbolSnapshotResponse(symbol=canonical, **sections)


# How far a default window reaches when the caller names neither end of it.
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
    canonical = _watched(symbol, db)
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
        points=bars(series.snapshots, interval),
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
    canonical = _watched(symbol, db)
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
