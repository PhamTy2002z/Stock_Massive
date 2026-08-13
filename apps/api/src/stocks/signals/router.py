"""The serving path for signals: stored sessions in, provenance out.

Nothing here reaches a Provider Source, the same way the rest of the store-backed
routes work. A request is a read of what the Collector and the Warm-up already
wrote, so a provider outage costs freshness rather than an error page.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.core.cache import TradingHoursCache
from src.core.database import get_sync_session
from src.core.ratelimit import standard_rate_limit

from ..cohort import CohortStore, cohort_version_active_on
from ..providers.contracts import Exchange
from ..schemas.signals import (
    SignalCohortVersion,
    SignalCoverage,
    UnevaluableSymbol,
    VolumeSpikeItem,
    VolumeSpikeSignalResponse,
)
from ..trading_day import market_generation
from .volume_spike import (
    DEFAULT_THRESHOLD,
    MIN_THRESHOLD,
    SignalScope,
    SymbolReading,
    VolumeSpikeSignal,
    signal_cache_key,
    volume_spike_signal,
)

router = APIRouter(prefix="/signals", tags=["signals"])

# The key carries every input that can change the *finding*, so an entry is only
# reachable by a request that would compute exactly it. Freshness is the one
# thing it cannot carry: `stale` is measured against the wall clock, so an entry
# written at six days old would still read `fresh` when served on day eight. The
# TTL is what bounds that error, which is why it is short and the same on both
# sides of the session — the answer is stable, its age is not.
SIGNAL_CACHE_TTL_SECONDS = 15 * 60

volume_spikes_cache = TradingHoursCache(
    key_prefix="stock:signals:volume_spikes:",
    ttl_trading=SIGNAL_CACHE_TTL_SECONDS,
    ttl_off_hours=SIGNAL_CACHE_TTL_SECONDS,
)


def _item(reading: SymbolReading) -> VolumeSpikeItem:
    """One spiking symbol on the wire.

    The baseline is rounded to whole shares: the fraction is left over from
    dividing twenty sessions, not a quantity anyone traded.
    """
    return VolumeSpikeItem(
        symbol=reading.symbol,
        exchange=reading.exchange,
        volume=reading.volume,
        baseline_average_volume=round(reading.baseline_average_volume or 0),
        ratio=round(reading.ratio, 2),
        close_price=reading.close_price,
        change_pct=reading.change_pct,
        issues=[issue.value for issue in reading.issues],
    )


def _response(signal: VolumeSpikeSignal) -> VolumeSpikeSignalResponse:
    """Turn the computed signal into the shape the interface was promised."""
    return VolumeSpikeSignalResponse(
        scope=signal.scope.value,
        trading_day=signal.trading_day,
        threshold=signal.threshold,
        coverage=SignalCoverage(
            state=signal.coverage.state.value,
            evaluated=signal.coverage.evaluated,
            total=signal.coverage.total,
        ),
        freshness=signal.freshness.value,
        cohort_version=(
            SignalCohortVersion(
                id=signal.cohort_version.id,
                reporting_period=signal.cohort_version.reporting_period,
            )
            if signal.cohort_version
            else None
        ),
        issues=[issue.value for issue in signal.issues],
        spikes=[_item(reading) for reading in signal.spikes],
        unevaluable=[
            UnevaluableSymbol(
                symbol=reading.symbol,
                issues=[issue.value for issue in reading.issues],
            )
            for reading in signal.unevaluable
        ],
    )


def _cohort_version_id(db: Session, trading_day: date | None) -> int | None:
    """Which Cohort Version this request will be answered against.

    Read before the signal is computed because the cache key needs it. A
    historical query resolves the version that was active on the day asked
    about; anything else is answered by the one active now.
    """
    version = (
        cohort_version_active_on(db, trading_day)
        if trading_day is not None
        else CohortStore(db).active()
    )
    return version.id if version is not None else None


@router.get(
    "/volume-spikes",
    response_model=VolumeSpikeSignalResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_volume_spikes(
    scope: SignalScope = Query(
        SignalScope.PROFIT_LEADERS,
        description="Which set of symbols to compute over",
    ),
    threshold: float = Query(
        DEFAULT_THRESHOLD,
        ge=MIN_THRESHOLD,
        description="How many times the twenty-session average counts as a spike",
    ),
    exchange: Exchange | None = Query(
        None, description="Narrow the Universe scope to one board"
    ),
    trading_day: date | None = Query(
        None, description="Answer for this session instead of the newest one"
    ),
    db: Session = Depends(get_sync_session),
) -> VolumeSpikeSignalResponse:
    """Serve the Volume Spike signal with the provenance to judge it by.

    The answer always states which session it is for, how much of the scope was
    evaluable, and how that session relates to the newest market data. A
    partial or empty answer is a 200 carrying its reasons — the request
    succeeded, and what it found is the finding.
    """
    if exchange is not None and scope is SignalScope.PROFIT_LEADERS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Bộ lọc sàn chỉ áp dụng cho phạm vi toàn bộ Universe: nhóm dẫn "
                "đầu lợi nhuận được xếp hạng chung cả HOSE và HNX."
            ),
        )
    if exchange is Exchange.UPCOM:
        raise HTTPException(
            status_code=400,
            detail="Hệ thống chỉ theo dõi cổ phiếu niêm yết trên HOSE và HNX.",
        )

    cache_key = signal_cache_key(
        scope=scope,
        trading_day=trading_day,
        threshold=threshold,
        exchange=exchange,
        cohort_version_id=_cohort_version_id(db, trading_day),
        market_generation=market_generation(db),
    )
    cached = volume_spikes_cache.get(cache_key)
    if cached is not None:
        return VolumeSpikeSignalResponse.model_validate(cached)

    signal = volume_spike_signal(
        db,
        scope=scope,
        threshold=threshold,
        exchange=exchange,
        trading_day=trading_day,
    )
    response = _response(signal)
    volume_spikes_cache.set(cache_key, response.model_dump(mode="json"))
    return response
