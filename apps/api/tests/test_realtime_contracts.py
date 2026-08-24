"""Contract and mutation tests for the S0 realtime event boundary."""

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.stocks.realtime import (
    AggressorSide,
    AuctionSnapshot,
    BarResolution,
    BookLevel,
    BookSide,
    BookSnapshot,
    CanonicalUnits,
    ClosedBar,
    EventFamily,
    EventMetadata,
    Exchange,
    ForeignFlowSnapshot,
    IndexTick,
    MarketDataSource,
    NO_UNITS,
    PriceBasis,
    PriceUnit,
    ProductGroup,
    QualityState,
    QuantityUnit,
    SecurityDefinition,
    SessionState,
    TradeTick,
    TradingSession,
    ValueUnit,
)


PROVIDER_TIME = datetime(2026, 8, 24, 3, 0, tzinfo=timezone.utc)
OBSERVED_TIME = PROVIDER_TIME + timedelta(milliseconds=30)
RAW_HASH = "a" * 64

CASH_UNITS = CanonicalUnits(
    price=PriceUnit.VND,
    quantity=QuantityUnit.SHARE,
    value=ValueUnit.VND,
)
BOOK_UNITS = CASH_UNITS.model_copy(update={"value": ValueUnit.NONE})
FLOW_UNITS = CanonicalUnits(
    price=PriceUnit.NONE,
    quantity=QuantityUnit.SHARE,
    value=ValueUnit.VND,
)
INDEX_UNITS = CanonicalUnits(
    price=PriceUnit.INDEX_POINT,
    quantity=QuantityUnit.NONE,
    value=ValueUnit.NONE,
)


def metadata(
    family: EventFamily,
    *,
    units: CanonicalUnits = CASH_UNITS,
    product_group: ProductGroup = ProductGroup.EQUITY,
    session: TradingSession = TradingSession.CONTINUOUS,
    symbol: str = "FPT",
    source: MarketDataSource = MarketDataSource.DNSE,
    **changes,
) -> EventMetadata:
    values = {
        "source": source,
        "event_family": family,
        "symbol": symbol,
        "exchange": Exchange.HOSE,
        "board": "G1",
        "product_group": product_group,
        "trading_day": date(2026, 8, 24),
        "session": session,
        "provider_time": PROVIDER_TIME,
        "observed_time": OBSERVED_TIME,
        "units": units,
        "schema_version": 1,
        "normalization_version": 1,
        "raw_payload_hash": RAW_HASH,
        "quality_state": QualityState.VALID,
    }
    values.update(changes)
    return EventMetadata(**values)


def valid_events():
    bar_end = PROVIDER_TIME
    return (
        TradeTick(
            metadata=metadata(EventFamily.TRADE),
            price=Decimal("71400"),
            quantity=100,
            gross_trade_value_vnd=Decimal("7140000"),
            aggressor_side=AggressorSide.BUY,
        ),
        BookSnapshot(
            metadata=metadata(EventFamily.BOOK, units=BOOK_UNITS),
            levels=(
                BookLevel(
                    side=BookSide.BID,
                    level=1,
                    price=Decimal("71300"),
                    quantity=100,
                ),
                BookLevel(
                    side=BookSide.OFFER,
                    level=1,
                    price=Decimal("71400"),
                    quantity=200,
                ),
            ),
        ),
        ForeignFlowSnapshot(
            metadata=metadata(EventFamily.FOREIGN_FLOW, units=FLOW_UNITS),
            buy_volume=100,
            sell_volume=50,
            buy_value_vnd=Decimal("7140000"),
            sell_value_vnd=Decimal("3570000"),
            current_room=1_000,
            total_room=2_000,
        ),
        AuctionSnapshot(
            metadata=metadata(
                EventFamily.AUCTION,
                units=BOOK_UNITS,
                session=TradingSession.ATC,
            ),
            expected_price=Decimal("71400"),
            expected_quantity=500,
        ),
        SessionState(
            metadata=metadata(EventFamily.SESSION, units=NO_UNITS),
            provider_session_id="continuous-afternoon",
            provider_event_id="session-42",
            is_trading=True,
        ),
        IndexTick(
            metadata=metadata(
                EventFamily.INDEX,
                units=INDEX_UNITS,
                product_group=ProductGroup.INDEX,
                symbol="VNINDEX",
            ),
            index_value=Decimal("1285.42"),
            change=Decimal("3.1"),
            change_percent=Decimal("0.24"),
            estimated=False,
        ),
        SecurityDefinition(
            metadata=metadata(
                EventFamily.SECURITY_DEFINITION,
                units=CanonicalUnits(
                    price=PriceUnit.VND,
                    quantity=QuantityUnit.NONE,
                    value=ValueUnit.NONE,
                ),
                session=TradingSession.REFERENCE,
            ),
            instrument_type="stock",
            status="listed",
            isin="VN000000FPT1",
            reference_price=Decimal("71400"),
            ceiling_price=Decimal("76300"),
            floor_price=Decimal("66500"),
            price_basis=PriceBasis.RAW,
        ),
        ClosedBar(
            metadata=metadata(
                EventFamily.CLOSED_BAR,
                provider_time=bar_end,
                observed_time=bar_end + timedelta(milliseconds=30),
            ),
            resolution=BarResolution.MINUTE_1,
            window_start=bar_end - timedelta(minutes=1),
            window_end=bar_end,
            open_price=Decimal("71500"),
            high_price=Decimal("71600"),
            low_price=Decimal("71300"),
            close_price=Decimal("71400"),
            volume=1_000,
            total_value_vnd=Decimal("71400000"),
            price_basis=PriceBasis.RAW,
        ),
    )


def test_all_eight_event_contracts_are_strict_immutable_and_serializable():
    events = valid_events()

    assert {event.metadata.event_family for event in events} == set(EventFamily)
    assert len({event.metadata.evidence_id for event in events}) == 8
    for event in events:
        payload = event.model_dump(mode="json")
        assert payload["metadata"]["quality_state"] == "valid"
        assert payload["metadata"]["raw_payload_hash"] == RAW_HASH
        with pytest.raises(ValidationError, match="frozen"):
            event.metadata.symbol = "HPG"


def test_metadata_requires_every_roadmap_field():
    required = {
        "source",
        "event_family",
        "symbol",
        "exchange",
        "board",
        "product_group",
        "trading_day",
        "session",
        "provider_time",
        "observed_time",
        "units",
        "schema_version",
        "normalization_version",
        "raw_payload_hash",
        "quality_state",
    }

    assert required <= set(EventMetadata.model_fields)
    for field in required:
        values = metadata(EventFamily.TRADE).model_dump()
        values.pop(field)
        with pytest.raises(ValidationError):
            EventMetadata(**values)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"board": "g1"}, "board"),
        ({"raw_payload_hash": "not-a-sha256"}, "raw_payload_hash"),
        ({"provider_time": PROVIDER_TIME.replace(tzinfo=None)}, "timezone-aware"),
        ({"observed_time": PROVIDER_TIME - timedelta(seconds=1)}, "cannot be later"),
        ({"schema_version": 0}, "schema_version"),
        ({"normalization_version": 0}, "normalization_version"),
    ],
)
def test_metadata_mutations_fail_before_persistence(change, message):
    with pytest.raises(ValidationError, match=message):
        metadata(EventFamily.TRADE, **change)


def test_wrong_event_family_and_units_fail_before_persistence():
    with pytest.raises(ValidationError, match="requires event family trade"):
        TradeTick(
            metadata=metadata(EventFamily.BOOK),
            price=Decimal("71400"),
            quantity=100,
            aggressor_side=AggressorSide.BUY,
        )

    wrong_units = CanonicalUnits(
        price=PriceUnit.INDEX_POINT,
        quantity=QuantityUnit.SHARE,
        value=ValueUnit.VND,
    )
    with pytest.raises(ValidationError, match="incompatible canonical units"):
        TradeTick(
            metadata=metadata(EventFamily.TRADE, units=wrong_units),
            price=Decimal("71.4"),
            quantity=100,
            aggressor_side=AggressorSide.BUY,
        )


def test_wrong_price_basis_and_bar_shape_fail_before_persistence():
    bar = valid_events()[-1]
    with pytest.raises(ValidationError, match="raw prices"):
        ClosedBar(**{
            **bar.model_dump(),
            "price_basis": PriceBasis.ADJUSTED_AT_SOURCE,
        })

    with pytest.raises(ValidationError, match="high"):
        ClosedBar(**{
            **bar.model_dump(),
            "high_price": Decimal("70000"),
        })


def test_derivative_and_index_events_cannot_cross_unit_domains():
    futures_units = CanonicalUnits(
        price=PriceUnit.INDEX_POINT,
        quantity=QuantityUnit.CONTRACT,
        value=ValueUnit.NONE,
    )
    with pytest.raises(ValidationError, match="gross value as VND"):
        TradeTick(
            metadata=metadata(
                EventFamily.TRADE,
                units=futures_units,
                product_group=ProductGroup.FUTURES,
            ),
            price=Decimal("1285.4"),
            quantity=1,
            gross_trade_value_vnd=Decimal("1000000"),
            aggressor_side=AggressorSide.BUY,
        )

    index_bar = ClosedBar(
        metadata=metadata(
            EventFamily.CLOSED_BAR,
            units=INDEX_UNITS,
            product_group=ProductGroup.INDEX,
            symbol="VNINDEX",
        ),
        resolution=BarResolution.MINUTE_1,
        window_start=PROVIDER_TIME - timedelta(minutes=1),
        window_end=PROVIDER_TIME,
        open_price=Decimal("1284.2"),
        high_price=Decimal("1285.8"),
        low_price=Decimal("1283.9"),
        close_price=Decimal("1285.4"),
        volume=0,
        price_basis=PriceBasis.RAW,
    )
    assert index_bar.metadata.units.price is PriceUnit.INDEX_POINT

    with pytest.raises(ValidationError, match="traded quantity"):
        ClosedBar(**{**index_bar.model_dump(), "volume": 1})

def test_duplicate_semantics_are_explicit_and_collision_safe():
    with pytest.raises(ValidationError, match="duplicate_of"):
        metadata(
            EventFamily.BOOK,
            units=BOOK_UNITS,
            quality_state=QualityState.DUPLICATE,
        )

    original = metadata(EventFamily.BOOK, units=BOOK_UNITS)
    duplicate = metadata(
        EventFamily.BOOK,
        units=BOOK_UNITS,
        provider_time=PROVIDER_TIME + timedelta(seconds=1),
        observed_time=OBSERVED_TIME + timedelta(seconds=1),
        quality_state=QualityState.DUPLICATE,
        duplicate_of=original.evidence_id,
    )
    assert duplicate.duplicate_of == original.evidence_id
    assert duplicate.evidence_id != original.evidence_id


@pytest.mark.parametrize(
    "secret_field",
    ["api_key", "api_secret", "authorization", "raw_payload", "access_token"],
)
def test_normalized_contracts_reject_secrets_and_raw_payloads(secret_field):
    values = metadata(EventFamily.TRADE).model_dump()
    values[secret_field] = "must-not-cross-boundary"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EventMetadata(**values)

    serialized = TradeTick(
        metadata=metadata(EventFamily.TRADE),
        price=Decimal("71400"),
        quantity=100,
        aggressor_side=AggressorSide.UNKNOWN,
    ).model_dump_json()
    payload = json.loads(serialized)
    serialized_keys = set(payload) | set(payload["metadata"])
    assert secret_field not in serialized_keys
    assert "must-not-cross-boundary" not in serialized


def test_source_is_part_of_identity_but_not_observation_grouping():
    dnse = metadata(EventFamily.TRADE, source=MarketDataSource.DNSE)
    fiinquant = metadata(EventFamily.TRADE, source=MarketDataSource.FIINQUANT)

    assert dnse.evidence_id != fiinquant.evidence_id
    assert dnse.observation_key == fiinquant.observation_key
