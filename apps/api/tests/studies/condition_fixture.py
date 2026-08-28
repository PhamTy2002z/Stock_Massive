"""A synthetic year of sessions whose every answer is known before it runs.

The window is built so that each figure the Study reports is derivable by hand
from this file, which is what makes the golden test a check rather than a
snapshot:

* **The 52-week band.** Every bar's high is its close plus
  :data:`WICK` and its low is its close minus it, so the band is
  ``max(close) + WICK`` to ``min(close) - WICK`` — :data:`HIGH_52W` and
  :data:`LOW_52W`.
* **The twelve-month return.** The window is exactly 250 sessions, so the return
  is the last close over the first one.
* **The accumulation zone.** The last sixty closes run from 68.000 to 74.000, so
  the twenty bins are 300đ wide; thirty of those sixty sit at 71.050 and 71.350,
  which fall in the eleventh and twelfth bins. Three of the ramp's closes land
  there too, so the winning adjacent pair holds 33 of 60 sessions and spans
  71.000–71.600 — :data:`ZONE_LOW`, :data:`ZONE_HIGH`, :data:`ZONE_SESSIONS_IN`.
* **The earnings axis.** Eight quarters of strictly rising profit, so all four
  year-on-year readings improve and the latest is positive.

The symbol is not a real ticker. The fixture deletes its own rows, and a real
ticker would mean a suite pointed at a store with a market-wide backfill in it
deleting sessions somebody collected.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import delete

from src.stocks.models import BarDaily, ProviderSnapshot
from src.stocks.providers.normalize import VN_TZ

SYMBOL = "TSTZ"
SOURCE = "vnstock"
PRICE_BASIS = "adjusted_at_source"
SERIES = "equity"

#: The last stored session, and an as-of after its close.
LAST_SESSION = date(2026, 8, 21)
AS_OF = datetime(2026, 8, 21, 16, 0, tzinfo=VN_TZ)

TOTAL_SESSIONS = 250

#: How far each bar's high and low sit from its close. Fixed so the 52-week band
#: is a statement about the close series plus a constant.
WICK = 100

FLAT_SESSIONS = 50
FLAT_CLOSE = 80_000

DECLINE_SESSIONS = 140
DECLINE_STEP = 85

RAMP_SESSIONS = 29
RAMP_START = 68_000
RAMP_STEP = 200

RAMP_PEAK = 74_000

CLUSTER_SESSIONS = 30
CLUSTER_LOW_CLOSE = 71_050
CLUSTER_HIGH_CLOSE = 71_350

HIGH_52W = FLAT_CLOSE + WICK
LOW_52W = RAMP_START - WICK
FIRST_CLOSE = FLAT_CLOSE
LAST_CLOSE = CLUSTER_HIGH_CLOSE

#: The zone the histogram must find: bins eleven and twelve of a 300đ grid that
#: starts at 68.000.
ZONE_LOW = 71_000
ZONE_HIGH = 71_600
ZONE_SESSIONS_IN = 33

#: Eight quarters, oldest first, in billions of dong. Strictly rising, so every
#: year-on-year reading improves and the trend is unambiguous.
QUARTER_PROFITS_VND = (
    1_000e9,
    1_100e9,
    1_200e9,
    1_300e9,
    1_500e9,
    1_600e9,
    1_700e9,
    1_800e9,
)


def closes() -> list[int]:
    """The 250 closes, oldest first: a plateau, a decline, a ramp, a cluster."""
    series = [FLAT_CLOSE] * FLAT_SESSIONS
    series += [
        FLAT_CLOSE - DECLINE_STEP * (step + 1) for step in range(DECLINE_SESSIONS)
    ]
    series += [RAMP_START + RAMP_STEP * step for step in range(RAMP_SESSIONS)]
    series.append(RAMP_PEAK)
    series += [
        CLUSTER_LOW_CLOSE if step % 2 == 0 else CLUSTER_HIGH_CLOSE
        for step in range(CLUSTER_SESSIONS)
    ]
    assert len(series) == TOTAL_SESSIONS, len(series)
    return series


def sessions() -> list[date]:
    """Consecutive calendar days ending at :data:`LAST_SESSION`.

    ``bar_daily`` holds whatever sessions the provider answered with and derives
    no calendar of its own, so the fixture does not need to skip weekends to be
    a valid window — and a plain sequence is one fewer thing a reader of the
    golden numbers has to reconstruct.
    """
    return [
        LAST_SESSION - timedelta(days=offset)
        for offset in range(TOTAL_SESSIONS - 1, -1, -1)
    ]


def load_bars(session, *, symbol: str = SYMBOL, keep: int | None = None) -> None:
    """Store the window for one symbol, newest ``keep`` sessions only if asked."""
    clear_bars(session, symbol=symbol)
    days = sessions()
    prices = closes()
    if keep is not None:
        days, prices = days[-keep:], prices[-keep:]
    session.add_all(
        BarDaily(
            symbol=symbol,
            trading_day=day,
            series=SERIES,
            open=close,
            high=close + WICK,
            low=close - WICK,
            close=close,
            volume=1_000_000,
            price_basis=PRICE_BASIS,
            source=SOURCE,
            observed_at=AS_OF,
        )
        for day, close in zip(days, prices)
    )


def load_quarters(
    session,
    *,
    symbol: str = SYMBOL,
    profits: tuple[float, ...] = QUARTER_PROFITS_VND,
) -> list[date]:
    """Store one snapshot per quarter, oldest first, and hand back the periods."""
    clear_quarters(session, symbol=symbol)
    periods = quarter_ends(len(profits))
    for period_end, profit in zip(periods, profits):
        session.add(
            ProviderSnapshot(
                capability="fundamental",
                symbol=symbol,
                source=SOURCE,
                # The collector writes a quarter at the VN midnight that opens
                # its period end, which is what makes ``effective_at`` order the
                # quarters.
                effective_at=datetime(
                    period_end.year, period_end.month, period_end.day, tzinfo=VN_TZ
                ),
                observed_at=AS_OF,
                schema_version=1,
                payload=quarter_payload(symbol, period_end, profit),
            )
        )
    return periods


def quarter_payload(
    symbol: str,
    period_end: date,
    profit: float | None,
    *,
    parent: bool = True,
) -> dict:
    """The payload shape the collector writes, metadata block included.

    Copied from a real row rather than reduced to the keys this reader looks at:
    the reader validates the payload against ``FundamentalSnapshot``, so a
    fixture missing the envelope would pass a test the store never could.
    """
    payload: dict = {
        "symbol": symbol,
        "metadata": {
            "source": SOURCE,
            "effective_at": datetime(
                period_end.year, period_end.month, period_end.day, tzinfo=VN_TZ
            ).isoformat(),
            "observed_at": AS_OF.isoformat(),
            "schema_version": 1,
        },
        "period_end": period_end.isoformat(),
    }
    if profit is not None:
        payload["net_profit_after_tax_vnd"] = profit
        if parent:
            payload["parent_net_profit_vnd"] = profit
    return payload


def quarter_ends(count: int) -> list[date]:
    """``count`` quarter ends, oldest first, the newest being 2026-06-30."""
    ends = [date(2026, 6, 30)]
    while len(ends) < count:
        previous = ends[-1]
        month = previous.month - 3
        year = previous.year if month > 0 else previous.year - 1
        month = month if month > 0 else month + 12
        ends.append(date(year, month, _last_day(year, month)))
    return list(reversed(ends))


def _last_day(year: int, month: int) -> int:
    following = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return (following - timedelta(days=1)).day


def clear_bars(session, *, symbol: str = SYMBOL) -> None:
    session.execute(delete(BarDaily).where(BarDaily.symbol == symbol))


def clear_quarters(session, *, symbol: str = SYMBOL) -> None:
    session.execute(
        delete(ProviderSnapshot).where(ProviderSnapshot.symbol == symbol)
    )


__all__ = [
    "AS_OF",
    "CLUSTER_HIGH_CLOSE",
    "CLUSTER_LOW_CLOSE",
    "FIRST_CLOSE",
    "HIGH_52W",
    "LAST_CLOSE",
    "LAST_SESSION",
    "LOW_52W",
    "QUARTER_PROFITS_VND",
    "SERIES",
    "SOURCE",
    "SYMBOL",
    "TOTAL_SESSIONS",
    "WICK",
    "ZONE_HIGH",
    "ZONE_LOW",
    "ZONE_SESSIONS_IN",
    "clear_bars",
    "clear_quarters",
    "closes",
    "load_bars",
    "quarter_payload",
    "load_quarters",
    "quarter_ends",
    "sessions",
]
