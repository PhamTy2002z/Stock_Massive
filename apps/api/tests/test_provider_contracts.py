"""Contract tests for normalized hybrid-provider snapshots."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.stocks.providers import (
    Capability,
    FundamentalSnapshot,
    MarketSnapshot,
    PriceUnit,
    ProviderSource,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SOURCE_OWNERSHIP_BY_CAPABILITY,
    SnapshotMetadata,
    SourceOwnership,
    ValuationSnapshot,
    cover_source,
    main_source,
    owns_capability,
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


def test_market_snapshot_separates_volume_fields_from_value_fields():
    snapshot = MarketSnapshot(
        symbol="HPG",
        metadata=metadata(ProviderSource.FIINQUANT),
        last_price=22_000,
        volume=12_000_000,
        total_value_vnd=264_000_000_000,
        active_buy_volume=7_000_000,
        active_sell_volume=5_000_000,
        foreign_buy_volume=900_000,
        foreign_sell_volume=400_000,
        foreign_buy_value_vnd=19_800_000_000,
        foreign_sell_value_vnd=8_800_000_000,
        foreign_net_value_vnd=11_000_000_000,
        ceiling_price=23_500,
        floor_price=20_500,
        market_cap_vnd=140_000_000_000_000,
    )

    assert snapshot.price_unit is PriceUnit.VND
    assert snapshot.active_buy_volume == 7_000_000
    assert snapshot.foreign_buy_value_vnd == 19_800_000_000
    assert snapshot.market_cap_vnd == 140_000_000_000_000

    volume_fields = {name for name in MarketSnapshot.model_fields if "volume" in name}
    value_fields = {name for name in MarketSnapshot.model_fields if name.endswith("_value_vnd")}
    assert volume_fields.isdisjoint(value_fields)
    assert value_fields == {
        "total_value_vnd",
        "foreign_buy_value_vnd",
        "foreign_sell_value_vnd",
        "foreign_net_value_vnd",
    }


def test_market_snapshot_allows_negative_foreign_net_value_only():
    outflow = MarketSnapshot(
        symbol="HPG",
        metadata=metadata(ProviderSource.FIINQUANT),
        foreign_net_value_vnd=-11_000_000_000,
    )
    assert outflow.foreign_net_value_vnd == -11_000_000_000

    for field in ("total_value_vnd", "foreign_buy_value_vnd", "foreign_sell_value_vnd"):
        with pytest.raises(ValidationError):
            MarketSnapshot(
                symbol="HPG",
                metadata=metadata(ProviderSource.FIINQUANT),
                **{field: -1},
            )

    for field in ("ceiling_price", "floor_price"):
        with pytest.raises(ValidationError):
            MarketSnapshot(
                symbol="HPG",
                metadata=metadata(ProviderSource.FIINQUANT),
                **{field: 0},
            )


def test_valuation_snapshot_carries_ratios_without_statement_inputs():
    snapshot = ValuationSnapshot(
        symbol="hpg",
        metadata=metadata(ProviderSource.FIINQUANT),
        provider_pe=12.5,
        provider_pb=1.8,
    )

    assert snapshot.symbol == "HPG"
    assert snapshot.provider_pe == 12.5
    assert snapshot.provider_pb == 1.8

    with pytest.raises(ValidationError):
        ValuationSnapshot(
            symbol="HPG",
            metadata=metadata(ProviderSource.FIINQUANT),
            trailing_12_month_net_income_vnd=1_000,
        )


def test_fundamental_snapshot_no_longer_carries_valuation_ratios():
    assert "provider_pe" not in FundamentalSnapshot.model_fields
    assert "provider_pb" not in FundamentalSnapshot.model_fields

    with pytest.raises(ValidationError):
        FundamentalSnapshot(
            symbol="FPT",
            metadata=metadata(),
            period_end=date(2026, 6, 30),
            provider_pe=12.5,
        )


def test_market_snapshot_keeps_foreign_net_flow_within_gross_flow():
    balanced = MarketSnapshot(
        symbol="HPG",
        metadata=metadata(ProviderSource.FIINQUANT),
        foreign_buy_value_vnd=19_800_000_000,
        foreign_sell_value_vnd=8_800_000_000,
        foreign_net_value_vnd=11_000_000_000,
    )
    assert balanced.foreign_net_value_vnd == 11_000_000_000

    # Net below gross is normal: put-through deals and rounding move the
    # reported net away from buy minus sell without breaking the bound.
    MarketSnapshot(
        symbol="HPG",
        metadata=metadata(ProviderSource.FIINQUANT),
        foreign_buy_value_vnd=19_800_000_000,
        foreign_sell_value_vnd=8_800_000_000,
        foreign_net_value_vnd=-1_000_000_000,
    )

    with pytest.raises(ValidationError, match="cannot exceed"):
        MarketSnapshot(
            symbol="HPG",
            metadata=metadata(ProviderSource.FIINQUANT),
            foreign_buy_value_vnd=19_800_000,
            foreign_sell_value_vnd=8_800_000,
            foreign_net_value_vnd=11_000_000_000,
        )


def test_source_ownership_matches_the_measured_main_cover_table():
    assert SOURCE_OWNERSHIP_BY_CAPABILITY == {
        Capability.MARKET: SourceOwnership(
            main=ProviderSource.FIINQUANT,
            cover=ProviderSource.VNSTOCK,
        ),
        Capability.VALUATION: SourceOwnership(
            main=ProviderSource.FIINQUANT,
            cover=ProviderSource.VNSTOCK,
        ),
        Capability.REFERENCE: SourceOwnership(main=ProviderSource.VNSTOCK),
        Capability.FUNDAMENTAL: SourceOwnership(main=ProviderSource.VNSTOCK),
    }

    assert main_source(Capability.VALUATION) is ProviderSource.FIINQUANT
    assert cover_source(Capability.VALUATION) is ProviderSource.VNSTOCK
    assert cover_source(Capability.FUNDAMENTAL) is None


def test_source_ownership_answers_which_sources_may_own_a_capability():
    assert owns_capability(Capability.MARKET, ProviderSource.FIINQUANT)
    assert owns_capability(Capability.MARKET, ProviderSource.VNSTOCK)
    assert owns_capability(Capability.FUNDAMENTAL, ProviderSource.VNSTOCK)
    assert not owns_capability(Capability.FUNDAMENTAL, ProviderSource.FIINQUANT)


def test_source_ownership_rejects_a_capability_owning_the_same_source_twice():
    with pytest.raises(ValidationError, match="cover source must differ"):
        SourceOwnership(
            main=ProviderSource.VNSTOCK,
            cover=ProviderSource.VNSTOCK,
        )


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
            trailing_12_month_net_income_vnd=1_000,
            unknown_provider_field=1,
        )
