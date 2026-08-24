"""Executable policy tests for normalization, outcomes, and provenance."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.stocks.realtime import (
    AggressorSide,
    ComparisonScope,
    DataDomain,
    DataOutcome,
    DataOutcomeKind,
    EvidenceReference,
    EventFamily,
    MarketDataSource,
    MetricComparison,
    NormalizationMeasure,
    OutcomeDisposition,
    ProductGroup,
    QualityState,
    ReconciliationResult,
    ReconciliationStatus,
    RETENTION_POLICY,
    SOURCE_OWNERSHIP,
    RetentionClass,
    TradeTick,
    merge_evidence,
    normalize_dnse_value,
    retention_rule,
)

from .test_realtime_contracts import metadata


def test_source_ownership_keeps_dnse_realtime_only():
    realtime = SOURCE_OWNERSHIP[DataDomain.REALTIME_MICROSTRUCTURE]
    historical = SOURCE_OWNERSHIP[DataDomain.HISTORICAL_EOD]
    valuation = SOURCE_OWNERSHIP[DataDomain.VALUATION]

    assert realtime.main is MarketDataSource.DNSE
    assert realtime.cover == ()
    assert not historical.admits(MarketDataSource.DNSE)
    assert historical.main is MarketDataSource.FIINQUANT
    assert historical.cover == (MarketDataSource.VNSTOCK,)
    assert valuation == historical


def test_dnse_normalization_is_versioned_and_board_specific():
    assert normalize_dnse_value(
        "71.4",
        version=1,
        product_group=ProductGroup.EQUITY,
        board="G1",
        measure=NormalizationMeasure.CASH_PRICE,
    ) == Decimal("71400.0")
    assert normalize_dnse_value(
        10,
        version=1,
        product_group=ProductGroup.EQUITY,
        board="G1",
        measure=NormalizationMeasure.TRADE_QUANTITY,
    ) == 100
    assert normalize_dnse_value(
        10,
        version=1,
        product_group=ProductGroup.EQUITY,
        board="G4",
        measure=NormalizationMeasure.TRADE_QUANTITY,
    ) == 10
    assert normalize_dnse_value(
        "1285.42",
        version=1,
        product_group=ProductGroup.FUTURES,
        board="F1",
        measure=NormalizationMeasure.FUTURES_PRICE,
    ) == Decimal("1285.42")


def test_unproven_normalization_rules_refuse_instead_of_guessing():
    with pytest.raises(ValueError, match="unknown normalization version"):
        normalize_dnse_value(
            10,
            version=2,
            product_group=ProductGroup.EQUITY,
            board="G1",
            measure=NormalizationMeasure.TRADE_QUANTITY,
        )

    with pytest.raises(ValueError, match="no audited normalization rule"):
        normalize_dnse_value(
            10,
            version=1,
            product_group=ProductGroup.EQUITY,
            board="G9",
            measure=NormalizationMeasure.TRADE_QUANTITY,
        )

    # Quote quantity is deliberately not inferred from trade quantity.
    assert "quote_quantity" not in {item.value for item in NormalizationMeasure}

    with pytest.raises(ValueError, match="invalid board identity"):
        normalize_dnse_value(
            "71.4",
            version=1,
            product_group=ProductGroup.EQUITY,
            board="",
            measure=NormalizationMeasure.CASH_PRICE,
        )

    with pytest.raises(ValueError, match="canonical decimal"):
        normalize_dnse_value(
            "not-a-number",
            version=1,
            product_group=ProductGroup.EQUITY,
            board="G1",
            measure=NormalizationMeasure.CASH_PRICE,
        )


def test_all_roadmap_outcomes_have_closed_dispositions():
    expected = {
        DataOutcomeKind.INVALID_REQUEST,
        DataOutcomeKind.UNKNOWN_SYMBOL,
        DataOutcomeKind.NO_SESSION,
        DataOutcomeKind.RETENTION_MISS,
        DataOutcomeKind.SILENT_EMPTY,
        DataOutcomeKind.STALE_DATA,
        DataOutcomeKind.DUPLICATE,
        DataOutcomeKind.GAP,
        DataOutcomeKind.PROVIDER_FAILURE,
    }

    outcomes = {
        kind: DataOutcome(kind=kind, source=MarketDataSource.DNSE, request_id="req-1")
        for kind in DataOutcomeKind
    }
    assert set(outcomes) == expected
    assert outcomes[DataOutcomeKind.INVALID_REQUEST].disposition is OutcomeDisposition.REFUSE
    assert outcomes[DataOutcomeKind.NO_SESSION].disposition is OutcomeDisposition.ABSENT
    assert outcomes[DataOutcomeKind.DUPLICATE].disposition is OutcomeDisposition.IGNORE
    assert outcomes[DataOutcomeKind.GAP].disposition is OutcomeDisposition.RECONCILE
    assert outcomes[DataOutcomeKind.PROVIDER_FAILURE].retryable is True

    with pytest.raises(ValidationError):
        DataOutcome(
            kind=DataOutcomeKind.PROVIDER_FAILURE,
            source=MarketDataSource.DNSE,
            request_id="req-1",
            raw_payload={"authorization": "secret"},
        )

    with pytest.raises(ValidationError, match="canonical event identities"):
        DataOutcome(
            kind=DataOutcomeKind.GAP,
            source=MarketDataSource.DNSE,
            request_id="req-2",
            evidence_ids=("provider-row-1",),
        )


def trade(source: MarketDataSource, raw_hash: str) -> TradeTick:
    return TradeTick(
        metadata=metadata(
            EventFamily.TRADE,
            source=source,
            raw_payload_hash=raw_hash,
        ),
        price=Decimal("71400"),
        quantity=100,
        gross_trade_value_vnd=Decimal("7140000"),
        aggressor_side=AggressorSide.BUY,
    )


def test_provider_additions_cannot_overwrite_existing_evidence():
    dnse = trade(MarketDataSource.DNSE, "a" * 64)
    fiinquant = trade(MarketDataSource.FIINQUANT, "b" * 64)

    merged = merge_evidence((dnse, fiinquant))

    assert len(merged) == 2
    assert merged[dnse.metadata.evidence_id].metadata.source is MarketDataSource.DNSE
    assert merged[fiinquant.metadata.evidence_id].metadata.source is MarketDataSource.FIINQUANT

    with pytest.raises(ValueError, match="explicit duplicate semantics"):
        merge_evidence((dnse, dnse))

    explicit_duplicate = TradeTick(
        metadata=metadata(
            EventFamily.TRADE,
            source=MarketDataSource.DNSE,
            raw_payload_hash="c" * 64,
            provider_time=dnse.metadata.provider_time.replace(microsecond=1),
            observed_time=dnse.metadata.observed_time.replace(microsecond=1),
            quality_state=QualityState.DUPLICATE,
            duplicate_of=dnse.metadata.evidence_id,
        ),
        price=Decimal("71400"),
        quantity=100,
        gross_trade_value_vnd=Decimal("7140000"),
        aggressor_side=AggressorSide.BUY,
    )
    with_duplicate = merge_evidence((dnse, explicit_duplicate))
    assert len(with_duplicate) == 2

    with pytest.raises(ValueError, match="already in the batch"):
        merge_evidence((explicit_duplicate,))


def test_reconciliation_keeps_both_sources_and_validates_claimed_status():
    dnse = trade(MarketDataSource.DNSE, "a" * 64)
    fiinquant = trade(MarketDataSource.FIINQUANT, "b" * 64)
    comparison = MetricComparison(
        metric="volume",
        left_value=Decimal("100"),
        right_value=Decimal("100"),
        absolute_tolerance=Decimal("0"),
    )

    result = ReconciliationResult(
        scope=ComparisonScope.CROSS_PROVIDER,
        status=ReconciliationStatus.MATCH,
        left=EvidenceReference.from_event(dnse),
        right=EvidenceReference.from_event(fiinquant),
        comparisons=(comparison,),
        method_version=1,
    )

    assert result.left.source is MarketDataSource.DNSE
    assert result.right.source is MarketDataSource.FIINQUANT
    assert result.left.evidence_id != result.right.evidence_id

    with pytest.raises(ValidationError, match="conflicts"):
        ReconciliationResult(
            scope=ComparisonScope.CROSS_PROVIDER,
            status=ReconciliationStatus.MISMATCH,
            left=result.left,
            right=result.right,
            comparisons=(comparison,),
            method_version=1,
        )

    with pytest.raises(ValidationError, match="timezone-aware"):
        EvidenceReference(
            evidence_id=dnse.metadata.evidence_id,
            source=MarketDataSource.DNSE,
            event_family=EventFamily.TRADE,
            symbol="FPT",
            trading_day=dnse.metadata.trading_day,
            observed_time=datetime(2026, 8, 24, 10, 0),
            schema_version=1,
        )


def test_daily_and_intraday_reconciliation_accept_same_source_distinct_evidence():
    first = trade(MarketDataSource.DNSE, "a" * 64)
    second = trade(MarketDataSource.DNSE, "b" * 64)

    result = ReconciliationResult(
        scope=ComparisonScope.INTRADAY,
        status=ReconciliationStatus.MISMATCH,
        left=EvidenceReference.from_event(first),
        right=EvidenceReference.from_event(second),
        comparisons=(
            MetricComparison(
                metric="volume",
                left_value=Decimal("100"),
                right_value=Decimal("90"),
                absolute_tolerance=Decimal("0"),
            ),
        ),
        method_version=1,
    )

    assert result.status is ReconciliationStatus.MISMATCH


def test_retention_policy_declares_every_class_and_is_immutable():
    expected = {
        RetentionClass.RAW_EVENT,
        RetentionClass.NORMALIZED_EVENT,
        RetentionClass.PROJECTION,
        RetentionClass.REPLAY_ARTIFACT,
        RetentionClass.OPERATIONAL_METADATA,
    }

    assert set(RETENTION_POLICY[1]) == expected
    assert retention_rule(RetentionClass.RAW_EVENT).days == 30
    assert retention_rule(RetentionClass.RAW_EVENT).contains_raw_payload is True
    assert retention_rule(RetentionClass.NORMALIZED_EVENT).contains_raw_payload is False

    with pytest.raises(TypeError):
        RETENTION_POLICY[1][RetentionClass.RAW_EVENT] = retention_rule(
            RetentionClass.RAW_EVENT
        )
    with pytest.raises(ValueError, match="unknown retention policy version"):
        retention_rule(RetentionClass.RAW_EVENT, version=2)
