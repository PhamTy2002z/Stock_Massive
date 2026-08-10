"""The serving path: what the store holds for one watched symbol.

Nothing here reaches a Provider Source. The collector is the only place that
does, so an evening when the provider is down still answers with the last
session it wrote.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.database import get_sync_session
from src.core.ratelimit import standard_rate_limit

from .providers import Capability, SnapshotRead, SnapshotStore
from .schemas.snapshot import (
    FundamentalSection,
    MarketSection,
    ReferenceSection,
    SymbolSnapshotResponse,
    ValuationSection,
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

    Malformed text and an untracked company are answered apart. Both are
    refusals, but one is the caller's typo and the other is a symbol this
    system has simply not been asked to follow — a user told the wrong one goes
    looking for the wrong fix.
    """
    try:
        canonical = validate_symbol(symbol)
    except StockServiceError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Mã chứng khoán không hợp lệ: {symbol}",
        ) from exc

    # Worded as what this system did or did not do, never as a claim about the
    # symbol itself: with no provider in the request path, nothing here knows
    # whether an unknown ticker is listed, delisted or a typo.
    if not get_universe().contains(canonical):
        raise HTTPException(
            status_code=404,
            detail=f"Hệ thống chưa thu thập dữ liệu cho mã {canonical}.",
        )

    store = SnapshotStore(db)
    sections = {}
    for capability in SECTION_BY_CAPABILITY:
        read = store.latest(capability, canonical)
        sections[capability.value] = _section(capability, read) if read else None

    return SymbolSnapshotResponse(symbol=canonical, **sections)
