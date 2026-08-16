"""A source store shaped so that every fixture role has exactly one candidate.

The capture procedure selects by property, so a test of it has to present a
store where the properties are *findable* — and, so that the assertions can be
about selection rather than about luck, findable in exactly one place each.
Every symbol here is therefore built to satisfy one probe and to fail the others.

Prices are invented and say so. What is not invented is the ceiling of a locked
session: it is asked of ``band_limits`` rather than typed in, because a hand
rounded ceiling would agree with whatever this file believed the HOSE tick
ladder to be, and the fixture would then be built against a second opinion.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.alpha.models import Analysis
from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import Capability, Exchange, PriceBasis, ProviderSource
from src.stocks.providers.contracts import (
    MARKET_SCHEMA_VERSION,
    MarketSnapshot,
    SnapshotMetadata,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.price_band import band_limits
from src.stocks.universe import Universe

TRADING_DAY = date(2026, 8, 14)
OBSERVED_AT = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
SESSIONS = 45
BASE_CLOSE = 10_000.0

# One symbol per property, and the names sort into the order the seats are
# filled in so that a reader can follow the scan.
BANK = "EVB1"
LOCKED = "EVL1"
MIXED = "EVM1"
ORDINARY = "EVO1"
PADDING = ("EVP1", "EVP2", "EVP3")
DEVELOPER = "EVR1"
SHORT = "EVS1"
RETAILER = "EVT1"
OUTSIDERS = ("EVX1", "EVX2", "EVX3")

MEMBERS = (BANK, LOCKED, MIXED, ORDINARY, *PADDING, DEVELOPER, SHORT, RETAILER)
UNIVERSE = Universe(explicit=MEMBERS)

# ICB level-2 codes. ``None`` is UNCLASSIFIED, which is what keeps the three
# bad-case symbols from being eligible for an industry seat.
ICB = {
    BANK: "8300",
    DEVELOPER: "8600",
    RETAILER: "5300",
    ORDINARY: "2700",
    OUTSIDERS[0]: "8300",
    OUTSIDERS[1]: "8600",
    OUTSIDERS[2]: "5300",
}

# Which of the last sessions ``LOCKED`` spends at its ceiling. Six of the
# twenty-one the price-zone window reads, so the share clears the registry's own
# degradation threshold with room to spare, and none of them is adjacent to
# another — a lock on the day after a lock would be measured against a ceiling
# anchor and is a different session to construct.
LOCK_OFFSETS = (2, 5, 8, 11, 14, 17)


def trading_days(count: int = SESSIONS, end: date = TRADING_DAY) -> tuple[date, ...]:
    """``count`` weekdays ending on ``end``, oldest first."""
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(days))


def _stamp(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


def write_session(
    session: Session,
    symbol: str,
    day: date,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
    source: ProviderSource = ProviderSource.FIINQUANT,
    basis: PriceBasis = PriceBasis.RAW,
) -> None:
    snapshot = MarketSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=source,
            effective_at=_stamp(day),
            observed_at=OBSERVED_AT,
            schema_version=MARKET_SCHEMA_VERSION,
        ),
        price_basis=basis,
        total_value_vnd=close * 1_000_000,
        open_price=close,
        high_price=close if high is None else high,
        low_price=close if low is None else low,
        last_price=close,
        volume=1_000_000,
        market_cap_vnd=close * 1_000_000_000,
        foreign_net_value_vnd=0.0,
    )
    session.add(
        ProviderSnapshot(
            capability=Capability.MARKET.value,
            symbol=symbol,
            source=source.value,
            effective_at=_stamp(day),
            observed_at=OBSERVED_AT,
            schema_version=MARKET_SCHEMA_VERSION,
            payload=snapshot.model_dump(mode="json"),
        )
    )


def list_symbol(session: Session, symbol: str, *, listed: bool = True) -> None:
    session.add(
        ListingRoster(
            symbol=symbol,
            exchange=Exchange.HOSE.value,
            is_listed=listed,
            company_name=f"{symbol} Joint Stock Company",
            icb_code=ICB.get(symbol),
            icb_name=None,
            source=ProviderSource.VNSTOCK.value,
            observed_at=OBSERVED_AT,
        )
    )


def build_source_store(session: Session) -> None:
    """Write the whole world, then flush it. The caller owns the transaction."""
    days = trading_days()
    for symbol in (*MEMBERS, *OUTSIDERS):
        list_symbol(session, symbol)

    flat = (BANK, ORDINARY, DEVELOPER, RETAILER, *PADDING, *OUTSIDERS)
    for symbol in flat:
        for day in days:
            write_session(session, symbol, day, close=BASE_CLOSE)

    # Below ``min_sessions``: ten sessions where the price-zone field needs
    # twenty-one, so ``prepare_bars()`` refuses ``insufficient_history``.
    for day in days[-10:]:
        write_session(session, SHORT, day, close=BASE_CLOSE)

    # The ADR-0006 seam: an adjusted-at-source era followed by a raw one. The
    # seam sits well outside the twenty-one-session window, so this symbol is
    # healthy for every probe but the wide one — which is what a real seam looks
    # like.
    for index, day in enumerate(days):
        adjusted = index < len(days) - 25
        write_session(
            session,
            MIXED,
            day,
            close=BASE_CLOSE,
            source=ProviderSource.VNSTOCK if adjusted else ProviderSource.FIINQUANT,
            basis=(
                PriceBasis.ADJUSTED_AT_SOURCE if adjusted else PriceBasis.RAW
            ),
        )

    # Dense limit locks, at the ceiling the band itself computes.
    ceiling = float(band_limits(Exchange.HOSE, Decimal(str(BASE_CLOSE))).ceiling)
    locked_days = {days[-1 - offset] for offset in LOCK_OFFSETS}
    for day in days:
        if day in locked_days:
            write_session(session, LOCKED, day, close=ceiling, high=ceiling, low=ceiling)
        else:
            write_session(session, LOCKED, day, close=BASE_CLOSE)

    # One stored Analysis, so the captured ``analysis`` table is not empty and
    # ``get_analysis`` has something to read back.
    session.add(
        Analysis(
            symbol=BANK,
            trading_day=TRADING_DAY,
            verdict="neutral",
            payload={"symbol": BANK, "verdictLine": "fixture", "citedFieldIds": []},
            schema_version=1,
        )
    )
    session.flush()


def clear_store(session: Session) -> None:
    for model in (Analysis, CorporateAction, ProviderSnapshot, ListingRoster):
        session.query(model).delete()
    session.flush()


__all__ = [
    "BANK",
    "DEVELOPER",
    "LOCKED",
    "MEMBERS",
    "MIXED",
    "ORDINARY",
    "OUTSIDERS",
    "PADDING",
    "RETAILER",
    "SESSIONS",
    "SHORT",
    "TRADING_DAY",
    "UNIVERSE",
    "build_source_store",
    "clear_store",
    "trading_days",
]
