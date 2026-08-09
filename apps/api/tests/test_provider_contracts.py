"""Contract tests for normalized hybrid-provider snapshots."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.stocks.providers import (
    Capability,
    FundamentalSnapshot,
    MarketSnapshot,
    PriceUnit,
    PRIMARY_SOURCE_BY_CAPABILITY,
    ProviderSource,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SnapshotMetadata,
)


NOW = datetime(2026, 8, 9, 9, 0, tzinfo=timezone.utc)


def metadata(source: ProviderSource = ProviderSource.VNSTOCK) -> SnapshotMetadata:
    return SnapshotMetadata(
        source=source,
        effective_at=NOW,
        observed_at=NOW,
    )


def test_market_snapshot_normalizes_symbol_and_locks_vnd_unit():
    snapshot = MarketSnapshot(
        symbol="vcb",
        metadata=metadata(ProviderSource.FIINQUANT),
        last_price=59_700,
        volume=1_000,
    )

    assert snapshot.symbol == "VCB"
    assert snapshot.price_unit is PriceUnit.VND
    assert snapshot.metadata.source is ProviderSource.FIINQUANT

    with pytest.raises(ValidationError):
        MarketSnapshot(
            symbol="VCB",
            metadata=metadata(ProviderSource.FIINQUANT),
            price_unit="thousand_vnd",
        )

    with pytest.raises(ValidationError, match="Invalid symbol format"):
        MarketSnapshot(
            symbol="VCB;DROP",
            metadata=metadata(ProviderSource.FIINQUANT),
        )


def test_capability_registry_keeps_hot_and_scheduled_owners_separate():
    assert PRIMARY_SOURCE_BY_CAPABILITY == {
        Capability.MARKET: ProviderSource.FIINQUANT,
        Capability.REFERENCE: ProviderSource.VNSTOCK,
        Capability.FUNDAMENTAL: ProviderSource.VNSTOCK,
    }


def test_snapshot_metadata_requires_aware_ordered_timestamps():
    with pytest.raises(ValidationError, match="timezone-aware"):
        SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=datetime(2026, 8, 9, 9, 0),
            observed_at=datetime(2026, 8, 9, 9, 1),
        )

    with pytest.raises(ValidationError, match="cannot be later"):
        SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=NOW.replace(minute=1),
            observed_at=NOW,
        )


def test_reference_snapshot_preserves_share_meaning_and_fallback_order():
    snapshot = ReferenceSnapshot(
        symbol="VCB",
        metadata=metadata(),
        shares=(
            ShareCount(share_type=ShareType.ISSUED, value=8_900_000_000),
            ShareCount(share_type=ShareType.LISTED, value=8_500_000_000),
            ShareCount(share_type=ShareType.OUTSTANDING, value=8_355_675_094),
        ),
        current_foreign_room=100,
        total_foreign_room=200,
    )

    canonical = snapshot.canonical_shares()
    assert canonical is not None
    assert canonical.share_type is ShareType.OUTSTANDING
    assert canonical.value == 8_355_675_094


def test_reference_snapshot_rejects_ambiguous_or_invalid_room_data():
    duplicate = ShareCount(share_type=ShareType.LISTED, value=1_000)

    with pytest.raises(ValidationError, match="share types must be unique"):
        ReferenceSnapshot(
            symbol="FPT",
            metadata=metadata(),
            shares=(duplicate, duplicate),
        )

    with pytest.raises(ValidationError, match="cannot exceed"):
        ReferenceSnapshot(
            symbol="FPT",
            metadata=metadata(),
            current_foreign_room=201,
            total_foreign_room=200,
        )


def test_fundamental_snapshot_is_internal_and_strict():
    with pytest.raises(ValidationError):
        FundamentalSnapshot(
            symbol="FPT",
            metadata=metadata(),
            period_end=date(2026, 6, 30),
            provider_pe=12.5,
            unknown_provider_field=1,
        )
