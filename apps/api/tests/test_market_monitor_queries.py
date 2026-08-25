"""Bulk-read guarantees for the Market Monitor frame loader."""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import (
    CohortMember,
    CohortVersion,
    CorporateAction,
    ListingRoster,
    ProviderSnapshot,
)
from src.stocks.monitor.frames import MarketFrameLoader
from src.stocks.monitor.schemas import MonitorExchange
from src.stocks.monitor.service import MarketMonitorService, monitor_cache_key
from src.stocks.providers import Capability, Exchange, ProviderSource
from src.stocks.providers.contracts import (
    MARKET_SCHEMA_VERSION,
    MarketIndexSnapshot,
    MarketSnapshot,
    PriceBasis,
    SnapshotMetadata,
    ValuationSnapshot,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.issues import SignalIssue


TODAY = date(2026, 8, 24)
NOW = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)


def open_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        ProviderSnapshot.__table__,
        ListingRoster.__table__,
        CohortVersion.__table__,
        CohortMember.__table__,
        CorporateAction.__table__,
    ):
        table.create(engine)
    return Session(engine)


def trading_calendar(count: int, last: date = TODAY) -> tuple[date, ...]:
    days: list[date] = []
    cursor = last
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(days))


def stamp(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


def list_symbol(
    session: Session,
    symbol: str,
    exchange: Exchange,
    *,
    listed: bool = True,
) -> None:
    session.add(
        ListingRoster(
            symbol=symbol,
            exchange=exchange.value,
            is_listed=listed,
            company_name=f"Company {symbol}",
            icb_code="10",
            icb_name="Ngân hàng",
            source=ProviderSource.VNSTOCK.value,
            observed_at=NOW,
        )
    )


def write_market(session: Session, symbol: str, days: tuple[date, ...]) -> None:
    for index, day in enumerate(days):
        close = 20_000.0 + index * 100
        snapshot = MarketSnapshot(
            symbol=symbol,
            metadata=SnapshotMetadata(
                source=ProviderSource.FIINQUANT,
                effective_at=stamp(day),
                observed_at=NOW,
                schema_version=MARKET_SCHEMA_VERSION,
            ),
            price_basis=PriceBasis.RAW,
            open_price=close,
            high_price=close,
            low_price=close,
            last_price=close,
            volume=1_000_000,
            total_value_vnd=20_000_000_000,
        )
        session.add(
            ProviderSnapshot(
                capability=Capability.MARKET.value,
                symbol=symbol,
                source=ProviderSource.FIINQUANT.value,
                effective_at=stamp(day),
                observed_at=NOW,
                schema_version=MARKET_SCHEMA_VERSION,
                payload=snapshot.model_dump(mode="json"),
            )
        )


def write_index(
    session: Session,
    symbol: str,
    days: tuple[date, ...],
) -> None:
    for index, day in enumerate(days):
        level = 1_200.0 + index
        snapshot = MarketIndexSnapshot(
            symbol=symbol,
            metadata=SnapshotMetadata(
                source=ProviderSource.FIINQUANT,
                effective_at=stamp(day),
                observed_at=NOW,
                schema_version=MARKET_SCHEMA_VERSION,
            ),
            price_basis=PriceBasis.RAW,
            open_price=level,
            high_price=level,
            low_price=level,
            last_price=level,
            volume=100_000,
            total_value_vnd=1_000_000_000,
        )
        session.add(
            ProviderSnapshot(
                capability=Capability.MARKET_INDEX.value,
                symbol=symbol,
                source=ProviderSource.FIINQUANT.value,
                effective_at=stamp(day),
                observed_at=NOW,
                schema_version=MARKET_SCHEMA_VERSION,
                payload=snapshot.model_dump(mode="json"),
            )
        )


def write_valuation(
    session: Session,
    symbol: str,
    day: date,
    pe: float,
) -> None:
    snapshot = ValuationSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=stamp(day),
            observed_at=NOW,
        ),
        provider_pe=pe,
        provider_pb=1.5,
    )
    session.add(
        ProviderSnapshot(
            capability=Capability.VALUATION.value,
            symbol=symbol,
            source=ProviderSource.FIINQUANT.value,
            effective_at=stamp(day),
            observed_at=NOW,
            schema_version=1,
            payload=snapshot.model_dump(mode="json"),
        )
    )


def test_loader_applies_exchange_and_listing_scope_and_keeps_as_of() -> None:
    session = open_session()
    days = trading_calendar(3)
    list_symbol(session, "AAA", Exchange.HOSE)
    list_symbol(session, "BBB", Exchange.HNX)
    list_symbol(session, "OLD", Exchange.HOSE, listed=False)
    for symbol in ("AAA", "BBB", "OLD"):
        write_market(session, symbol, days)
    write_index(session, "VNINDEX", days)
    write_valuation(session, "AAA", days[-1], 12.0)
    session.flush()

    loaded = MarketFrameLoader(
        session, universe_symbols=("AAA", "BBB", "OLD")
    ).load(MonitorExchange.HOSE, as_of=days[-1], window_days=3)

    assert loaded.as_of == days[-1]
    assert loaded.eligible_symbols == ("AAA",)
    assert tuple(item.symbol for item in loaded.symbols) == ("AAA",)
    assert loaded.valuations[0].symbol == "AAA"
    assert tuple(loaded.indices) == (Exchange.HOSE,)
    assert loaded.index_refusals == {}


def test_loader_refuses_a_symbol_missing_the_target_session() -> None:
    session = open_session()
    days = trading_calendar(3)
    for symbol in ("AAA", "BBB"):
        list_symbol(session, symbol, Exchange.HOSE)
    write_market(session, "AAA", days)
    write_market(session, "BBB", days[:-1])
    session.flush()

    loaded = MarketFrameLoader(
        session, universe_symbols=("AAA", "BBB")
    ).load(MonitorExchange.HOSE, as_of=days[-1], window_days=3)

    assert tuple(item.symbol for item in loaded.symbols) == ("AAA",)
    refusal = next(item for item in loaded.refusals if item.symbol == "BBB")
    assert refusal.issues == (SignalIssue.MISSING_TARGET_SESSION,)


def _load_query_count(size: int) -> int:
    session = open_session()
    days = trading_calendar(3)
    symbols = tuple(f"S{index:03d}" for index in range(size))
    for symbol in symbols:
        list_symbol(session, symbol, Exchange.HOSE)
        write_market(session, symbol, days)
        write_valuation(session, symbol, days[-1], 10.0 + size)
    write_index(session, "VNINDEX", days)
    session.flush()

    count = 0

    def count_query(*_args) -> None:
        nonlocal count
        count += 1

    event.listen(session.bind, "before_cursor_execute", count_query)
    try:
        MarketFrameLoader(session, universe_symbols=symbols).load(
            MonitorExchange.HOSE,
            as_of=days[-1],
            window_days=3,
        )
    finally:
        event.remove(session.bind, "before_cursor_execute", count_query)
    return count


def test_query_count_is_bounded_as_the_cohort_grows() -> None:
    assert _load_query_count(20) == _load_query_count(2)


def test_service_reconciles_exchange_and_sector_coverage() -> None:
    session = open_session()
    days = trading_calendar(3)
    for symbol in ("AAA", "BBB"):
        list_symbol(session, symbol, Exchange.HOSE)
    write_market(session, "AAA", days)
    write_market(session, "BBB", days[:-1])
    session.flush()

    result = MarketMonitorService(
        session,
        universe_symbols=("AAA", "BBB"),
    ).snapshot(MonitorExchange.HOSE, as_of=days[-1], window_days=3)

    assert (result.breadth.eligible, result.breadth.evaluated) == (2, 1)
    assert len(result.sectors) == 1
    assert (result.sectors[0].eligible, result.sectors[0].evaluated) == (2, 1)


def test_cache_key_changes_when_reference_generation_moves() -> None:
    session = open_session()
    list_symbol(session, "AAA", Exchange.HOSE)
    session.flush()
    before = monitor_cache_key(
        session,
        exchange=MonitorExchange.HOSE,
        as_of=TODAY,
        window_days=253,
    )

    row = session.get(ListingRoster, "AAA")
    assert row is not None
    row.observed_at = NOW + timedelta(seconds=1)
    session.flush()
    after = monitor_cache_key(
        session,
        exchange=MonitorExchange.HOSE,
        as_of=TODAY,
        window_days=253,
    )

    assert after != before
