"""S3 reconciliation preserves disagreements instead of adjusting data."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base
from src.stocks.models import RealtimeEvent, RealtimeReconciliationAudit
from src.stocks.realtime import (
    ComparisonScope,
    CompositeProjector,
    MarketDataSource,
    ReconciliationStatus,
    ReconciliationToleranceProfile,
    ReconciliationProjector,
    RealtimeEventStore,
    STRICT_RECONCILIATION_PROFILE_V1,
    QualityState,
    aggregate_bars_to_daily,
    aggregate_trades,
    reconcile_bars,
    reconciliation_quality,
    build_reconciliation_audit,
    TradeBarProjector,
)

from .test_realtime_aggregation import trade


STRICT = ReconciliationToleranceProfile(
    version=1,
    price=Decimal(0),
    volume=Decimal(0),
    value=Decimal(0),
)


def provider_copy(bar, *, source=MarketDataSource.DNSE, **changes):
    payload = bar.model_dump()
    payload.update(changes)
    payload["metadata"] = {
        **bar.metadata.model_dump(),
        "source": source,
        "schema_version": 1,
        "raw_payload_hash": (
            "d" * 64 if source is MarketDataSource.DNSE else "f" * 64
        ),
    }
    payload["method_version"] = None
    payload["input_evidence_ids"] = ()
    return type(bar).model_validate(payload)


def test_exact_trade_bar_and_provider_bar_match_under_explicit_profile():
    derived = aggregate_trades((trade(1), trade(2, second=30)))[0]
    provider = provider_copy(derived)

    result = reconcile_bars(
        derived, provider, STRICT, scope=ComparisonScope.INTRADAY
    )

    assert result.status is ReconciliationStatus.MATCH
    assert result.method_version == STRICT.version
    assert all(comparison.matches for comparison in result.comparisons)


def test_owner_approved_profile_v1_is_exact_zero_and_shadow_audit_has_deltas():
    assert STRICT_RECONCILIATION_PROFILE_V1 == STRICT
    derived = aggregate_trades((trade(1),))[0]
    provider = provider_copy(derived, volume=derived.volume + 1)

    result = reconcile_bars(
        derived,
        provider,
        STRICT_RECONCILIATION_PROFILE_V1,
        scope=ComparisonScope.INTRADAY,
    )
    audit = build_reconciliation_audit(
        result, STRICT_RECONCILIATION_PROFILE_V1
    )
    volume = next(item for item in result.comparisons if item.metric == "volume")
    payload = audit.model_dump(mode="json")

    assert audit.enforcement_mode.value == "shadow"
    assert volume.absolute_delta == 1
    assert volume.matches is False
    assert payload["comparison_outcomes"][4]["absolute_delta"] == "1"
    assert payload["comparison_outcomes"][4]["matches"] is False


def test_mismatch_remains_beside_unchanged_source_evidence():
    derived = aggregate_trades((trade(1),))[0]
    provider = provider_copy(derived, volume=derived.volume + 10)

    result = reconcile_bars(
        derived, provider, STRICT, scope=ComparisonScope.INTRADAY
    )

    assert result.status is ReconciliationStatus.MISMATCH
    assert derived.volume == 100
    assert provider.volume == 110
    assert result.left.evidence_id == derived.metadata.evidence_id
    assert result.right.evidence_id == provider.metadata.evidence_id


def test_missing_value_is_incomplete_instead_of_fabricated():
    derived = aggregate_trades((trade(1),))[0]
    provider = provider_copy(derived, total_value_vnd=None)

    result = reconcile_bars(
        derived, provider, STRICT, scope=ComparisonScope.DAILY
    )

    assert result.status is ReconciliationStatus.INCOMPLETE
    assert {item.metric for item in result.comparisons} == {
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    }


def test_known_mismatch_is_not_hidden_by_another_missing_metric():
    derived = aggregate_trades((trade(1),))[0]
    provider = provider_copy(
        derived,
        volume=derived.volume + 1,
        total_value_vnd=None,
    )

    result = reconcile_bars(
        derived,
        provider,
        STRICT,
        scope=ComparisonScope.DAILY,
    )

    assert result.status is ReconciliationStatus.MISMATCH
    assert reconciliation_quality(result) is QualityState.DEGRADED


def test_cross_provider_comparison_retains_dnse_and_fiinquant_sources():
    derived = aggregate_trades((trade(1),))[0]
    dnse = provider_copy(derived)
    fiinquant = provider_copy(derived, source=MarketDataSource.FIINQUANT)

    result = reconcile_bars(
        dnse,
        fiinquant,
        STRICT,
        scope=ComparisonScope.CROSS_PROVIDER,
    )

    assert result.status is ReconciliationStatus.MATCH
    assert result.left.source is MarketDataSource.DNSE
    assert result.right.source is MarketDataSource.FIINQUANT


def test_minute_bars_roll_up_to_daily_without_losing_input_evidence():
    trades = (trade(1, minute=0), trade(2, minute=1, quantity=200))
    minutes = aggregate_trades(trades)

    daily = aggregate_bars_to_daily(minutes)[0]

    assert daily.volume == 300
    assert daily.input_evidence_ids == tuple(
        bar.metadata.evidence_id for bar in minutes
    )
    assert daily.method_version == 1


def test_minute_rollup_reconciles_to_dnse_daily_without_adjusting_either_bar():
    minutes = aggregate_trades(
        (trade(1, minute=0), trade(2, minute=1, quantity=200))
    )
    derived = aggregate_bars_to_daily(minutes)[0]
    dnse = provider_copy(derived)

    result = reconcile_bars(
        derived,
        dnse,
        STRICT,
        scope=ComparisonScope.DAILY,
    )

    assert result.status is ReconciliationStatus.MATCH
    assert result.method_version == STRICT.version
    assert derived.metadata.source is MarketDataSource.INTERNAL
    assert dnse.metadata.source is MarketDataSource.DNSE


def test_reconciliation_status_maps_to_explicit_quality():
    derived = aggregate_trades((trade(1),))[0]
    mismatch = reconcile_bars(
        derived,
        provider_copy(derived, volume=derived.volume + 1),
        STRICT,
        scope=ComparisonScope.INTRADAY,
    )

    assert reconciliation_quality(mismatch) is QualityState.DEGRADED


@pytest.fixture
def reconciliation_store():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            RealtimeEvent.__table__,
            RealtimeReconciliationAudit.__table__,
        ],
    )
    yield RealtimeEventStore(sessionmaker(bind=engine, expire_on_commit=False))
    engine.dispose()


@pytest.mark.asyncio
async def test_shadow_projector_persists_mismatch_once_without_adjusting_sources(
    reconciliation_store,
):
    derived = aggregate_trades((trade(1),))[0]
    provider = provider_copy(derived, volume=derived.volume + 1)
    assert await reconciliation_store.append(derived)
    assert await reconciliation_store.append(provider)
    projector = ReconciliationProjector(reconciliation_store)

    assert await projector.project(provider) == ()
    assert await projector.project(provider) == ()

    audits = await reconciliation_store.read_reconciliations(
        "FPT", derived.metadata.trading_day
    )
    assert len(audits) == 1
    assert audits[0].result.status is ReconciliationStatus.MISMATCH
    assert audits[0].quality_state is QualityState.DEGRADED
    assert audits[0].profile == STRICT_RECONCILIATION_PROFILE_V1
    assert derived.volume == 100
    assert provider.volume == 101


@pytest.mark.asyncio
async def test_daily_fiinquant_projection_records_cross_provider_sources(
    reconciliation_store,
):
    daily = aggregate_bars_to_daily(
        aggregate_trades((trade(1, minute=0), trade(2, minute=1)))
    )[0]
    dnse = provider_copy(daily)
    fiinquant = provider_copy(daily, source=MarketDataSource.FIINQUANT)
    assert await reconciliation_store.append(dnse)
    assert await reconciliation_store.append(fiinquant)

    await ReconciliationProjector(reconciliation_store).project(fiinquant)

    audits = await reconciliation_store.read_reconciliations(
        "FPT",
        daily.metadata.trading_day,
        scope=ComparisonScope.CROSS_PROVIDER,
    )
    assert len(audits) == 1
    assert audits[0].result.left.source is MarketDataSource.DNSE
    assert audits[0].result.right.source is MarketDataSource.FIINQUANT


class ProjectionSink:
    async def apply(self, _event):
        return None


@pytest.mark.asyncio
async def test_production_projector_order_builds_bar_before_shadow_audit(
    reconciliation_store,
):
    inputs = (trade(1, second=1), trade(2, second=30, quantity=200))
    for item in inputs:
        assert await reconciliation_store.append(item)
    derived = aggregate_trades(inputs)[0]
    provider = provider_copy(derived)
    assert await reconciliation_store.append(provider)
    projector = CompositeProjector(
        TradeBarProjector(reconciliation_store, ProjectionSink()),
        ReconciliationProjector(reconciliation_store),
    )

    projected = await projector.project(provider)

    audits = await reconciliation_store.read_reconciliations(
        "FPT", derived.metadata.trading_day
    )
    assert projected == (derived,)
    assert len(audits) == 1
    assert audits[0].result.status is ReconciliationStatus.MATCH
