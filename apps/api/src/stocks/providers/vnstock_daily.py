"""Fetching daily sessions market-wide, and the four things that go wrong.

**The provider caps a call at about two thousand rows, filling backward from
``end``.** Measured 2026-08-27: STB and VNINDEX both answered 1,997 rows
starting 2018-08-29 for a request beginning 2016-01-01, and a second call ending
2018-08-28 answered 1,995 more from 2010-08-31. So eight years of depth is one
request, and anything deeper is a second one that pages backward from the
earliest row already received.

**The window is a hint, not a contract.** A request for 2026-06-01..2026-06-15
came back holding 2026-05-29 and 2026-06-16 as well. Paging therefore stops on a
page that failed to move the earliest session backward, not just on an empty
one: a provider that keeps re-answering the same block would otherwise page
forever.

**Equity prices are thousands and index prices are points.** STB closes at 74.5
for a 74,500đ share; VNINDEX closes at 1,821.32 points. The scale is decided by
``series``, once, at ingest, so nothing downstream has to remember which store
it is reading. Same rule as the fifteen-minute bars.

**vnstock has no SLA and calls ``sys.exit()``.** Every call goes through
``safe_vnstock_call``, and a response whose columns are not the documented ones
raises rather than writing a partial history: a 52-week return computed over a
silently half-ingested window is a wrong answer that looks like a right one.

**"No data in this window" is not distinguishable from "the provider failed".**
A window before a symbol's first session raises inside vnstock, and the wrapper
swallows every exception into ``None``. So the paging loop decides what it means
from where it happened: on the first page it is reported as a failure, and on a
later one it is read as the history having ended — which keeps the pages that
did arrive instead of rolling them back.

There is no traded-value column in the response. Callers that want amount
compute ``close * volume`` where they use it; inventing a column would claim the
provider measured something it did not report.

A run during trading hours writes the current session too, with whatever the
provider has of it so far, and the next run's upsert replaces it with the closed
figures. Nothing here decides whether a session has closed — ``observed_at``
records when the row was read, and a reader that needs closed sessions only has
to say so.

pandas and vnstock are imported at module load, not lazily inside the handler.
Only the backfill job imports this module, so the seconds are spent by an
operator's job rather than by whoever asks the first question.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from vnstock.api.quote import Quote

from src.core.quota import quota_arbiter
from src.core.vnstock_wrapper import safe_vnstock_call
from src.stocks.models import BarDaily
from src.stocks.providers.normalize import VN_TZ

logger = logging.getLogger(__name__)

SOURCE = "vnstock"

#: The provider's own source for daily history. VCI answers the full depth of
#: both equity and index series on the community tier.
PROVIDER_SOURCE = "VCI"

#: What every row written today means. Stored per row rather than assumed,
#: because the provider offers no unadjusted daily history for this market and a
#: window whose basis is only implied is how two incomparable price series ended
#: up in one table before.
PRICE_BASIS = "adjusted_at_source"

SERIES_EQUITY = "equity"
SERIES_INDEX = "index"
SERIES = (SERIES_EQUITY, SERIES_INDEX)

#: Equity quotes arrive in thousands of dong (74.5 for a 74,500đ share); an
#: index arrives in points and is already itself.
PRICE_SCALE = {SERIES_EQUITY: Decimal(1000), SERIES_INDEX: Decimal(1)}

REQUIRED_COLUMNS = ("time", "open", "high", "low", "close", "volume")

#: Calendar days asked for per session wanted. The market trades about 250
#: sessions a year, and the request window is padded because the cap — not the
#: window — is what bounds the answer: asking too far back costs nothing, asking
#: too little silently returns a short history.
CALENDAR_DAYS_PER_SESSION = 1.7

#: How many backward pages one ``ensure_daily_bars`` call will walk. Two reach
#: 2010 at the measured cap, which is older than any question this system asks;
#: the limit exists so a provider that answers the same block forever ends the
#: call instead of the job.
MAX_PAGES = 6


class DailyIngestError(RuntimeError):
    """The provider answered with something this code will not write.

    Raised instead of writing what could be parsed. A shape change upstream is a
    thing to fix, and a table half-filled from a best-effort parse hides it
    behind returns that are merely odd.
    """


@dataclass(frozen=True)
class DailyIngestOutcome:
    """What one ``ensure_daily_bars`` call did, in terms a job log can print."""

    symbol: str
    series: str
    calls: int
    rows_written: int
    sessions_stored: int
    first_session: date | None
    last_session: date | None


def fetch_daily(symbol: str, *, end: date, sessions: int) -> pd.DataFrame:
    """One page of daily history ending at ``end``, as the provider gives it.

    ``sessions`` only sizes the requested window. The provider's row cap decides
    how much comes back, so the caller pages rather than trusting this depth.
    """
    start = end - timedelta(days=math.ceil(sessions * CALENDAR_DAYS_PER_SESSION) + 7)
    # Built through the wrapper for the same reason the call is: vnstock exits
    # the process from the constructor too, and a ``SystemExit`` walks past every
    # ``except Exception`` between here and the job.
    quote = safe_vnstock_call(Quote, source=PROVIDER_SOURCE, symbol=symbol)
    if quote is None:
        raise DailyIngestError(f"vnstock would not open a client for {symbol}")

    # The account's allowance, taken from the one arbiter that owns it
    # (``docs/adr/0014``). Not a pacer of this module's own: three uncoordinated
    # pacers over one allowance was the measured failure that arbiter exists to
    # end, and a fourth here would spend the same slots the news lane and the
    # legacy routes are counting. The lane is whatever the entry point declared —
    # ``backfill_daily.run`` says ``BACKFILL``, which stands aside for a caller
    # with a user waiting behind it and then waits as long as it takes.
    #
    # Placed before ``history`` and not before the constructor above, because the
    # constructor reaches no provider — the guarded client makes the same
    # distinction for the same reason.
    #
    # Refusals propagate. ``QuotaRefused`` is not a thin window or a provider
    # hiccup, and it must not become one: ``safe_vnstock_call`` answers every
    # ordinary exception with ``None``, which this function then reports as "the
    # provider answered nothing" — the sentence the paging loop reads as *this
    # window predates the symbol's first session*. A quota refusal dressed as
    # that would mark a symbol not-deep-enough and move on, quietly, forever.
    quota_arbiter().acquire()

    frame = safe_vnstock_call(
        quote.history,
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1D",
    )
    if frame is None:
        # ``safe_vnstock_call`` returns None for every failure it swallows, and
        # a window that predates the symbol's first session is one of them: the
        # provider raises "Không tìm thấy dữ liệu" inside, measured 2026-08-27.
        # The two cannot be told apart from here, so the paging loop — which
        # knows whether earlier pages arrived — decides what it means.
        raise DailyIngestError(
            f"vnstock answered nothing for {symbol} up to {end.isoformat()}"
        )
    return frame


Fetch = Callable[..., pd.DataFrame]


def ensure_daily_bars(
    session: Session,
    symbol: str,
    *,
    sessions: int,
    series: str = SERIES_EQUITY,
    fetch: Fetch | None = None,
    today: date | None = None,
) -> DailyIngestOutcome:
    """Make sure the store holds at least ``sessions`` sessions for ``symbol``.

    Always fetches at least once, even when the store is already deep enough:
    the newest session is the one the provider may have re-stated, and deciding
    to skip a symbol entirely belongs to the job, which can see the whole scope.

    ``fetch`` and ``today`` are injectable so the suite can prove the paging and
    the scaling without reaching the network; production passes neither.
    """
    if series not in SERIES:
        raise DailyIngestError(
            f"{series!r} is not a series this table holds; expected one of {SERIES}"
        )
    symbol = symbol.upper()
    fetch = fetch or fetch_daily
    today = today or datetime.now(VN_TZ).date()

    written = 0
    calls = 0
    cursor = today
    earliest_seen: date | None = None

    for page in range(MAX_PAGES):
        try:
            frame = fetch(symbol, end=cursor, sessions=sessions)
        except DailyIngestError:
            if page == 0:
                raise
            # A window before the symbol's first session and a provider that
            # gave up are the same thing here: ``safe_vnstock_call`` answers
            # None for both (measured — a window with no data raises inside
            # vnstock, and the wrapper swallows it). On a later page the
            # likelier reading by far is that the history ended, and raising
            # would roll back the pages that did arrive. The first page is
            # where a real outage is reported.
            logger.info(
                "%s: page %d answered nothing; treating it as the start of "
                "the history",
                symbol,
                page + 1,
            )
            break
        calls += 1
        rows = _rows_from(symbol, series, frame, today=today)
        written += _upsert(session, rows)

        if not rows:
            break
        page_earliest = min(row["trading_day"] for row in rows)
        if earliest_seen is not None and page_earliest >= earliest_seen:
            # The page did not reach further back than the last one did. Asking
            # again with the same cursor would repeat it forever.
            break
        earliest_seen = page_earliest

        stored, _first, _last = _what_is_stored(session, symbol)
        if stored >= sessions:
            break
        cursor = page_earliest - timedelta(days=1)

    stored, first_session, last_session = _what_is_stored(session, symbol)
    return DailyIngestOutcome(
        symbol=symbol,
        series=series,
        calls=calls,
        rows_written=written,
        sessions_stored=stored,
        first_session=first_session,
        last_session=last_session,
    )


def _what_is_stored(
    session: Session, symbol: str
) -> tuple[int, date | None, date | None]:
    row = session.execute(
        select(
            func.count(BarDaily.trading_day),
            func.min(BarDaily.trading_day),
            func.max(BarDaily.trading_day),
        ).where(BarDaily.symbol == symbol)
    ).one()
    return int(row[0] or 0), row[1], row[2]


def _rows_from(
    symbol: str, series: str, frame: pd.DataFrame, *, today: date
) -> list[dict]:
    """Sessions as rows, scaled to the unit the table stores."""
    missing = [name for name in REQUIRED_COLUMNS if name not in frame.columns]
    if missing:
        raise DailyIngestError(
            f"vnstock answered for {symbol} without {missing}; got "
            f"{list(frame.columns)}"
        )

    scale = PRICE_SCALE[series]
    observed_at = datetime.now(VN_TZ)
    rows: list[dict] = []

    for record in frame.itertuples(index=False):
        if _is_priceless(record):
            # A session the provider carries with no price — a halt, or a row it
            # padded. Left out rather than written as a zero, which would read
            # downstream as a measured collapse.
            continue
        day = _as_day(record.time)
        _refuse_impossible_day(symbol, day, today)
        rows.append(
            {
                "symbol": symbol,
                "trading_day": day,
                "series": series,
                "open": _price(record.open, scale),
                "high": _price(record.high, scale),
                "low": _price(record.low, scale),
                "close": _price(record.close, scale),
                "volume": _volume(record.volume),
                "price_basis": PRICE_BASIS,
                "source": SOURCE,
                "observed_at": observed_at,
            }
        )
    return rows


def _is_priceless(record) -> bool:
    return bool(pd.isna(record.open)) or bool(pd.isna(record.close))


def _refuse_impossible_day(symbol: str, day: date, today: date) -> None:
    """Refuse a session date this market cannot have held, before it is written.

    The Trading Day calendar is derived from this table, so a malformed date is
    not one bad bar — it moves the window every symbol in the market is measured
    against. ``bar_daily`` carries no CHECK constraint on ``trading_day`` and the
    response check above reads column *names* only, so this is the boundary
    where a date is judged at all.

    Two impossibilities, and only two. A date in the future is one the exchange
    has not reached. A Saturday or Sunday is one it does not open on — unlike a
    public holiday, which is indistinguishable from an ordinary quiet day
    without a calendar this system deliberately does not keep. Anything subtler
    than these is a data question rather than a shape question, and refusing it
    here would mean guessing.
    """
    if day > today:
        raise DailyIngestError(
            f"vnstock answered for {symbol} with session {day}, which is after "
            f"{today}: a future session would move the market's calendar forward"
        )
    if day.weekday() >= 5:
        raise DailyIngestError(
            f"vnstock answered for {symbol} with session {day}, a "
            f"{day.strftime('%A')}: this market holds no weekend session"
        )


def _as_day(value: Any) -> date:
    """The session's date, however the provider typed its ``time`` column."""
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _price(value: Any, scale: Decimal) -> Decimal:
    if value is None or bool(pd.isna(value)):
        raise DailyIngestError("a session arrived with a missing price")
    return (Decimal(str(value)) * scale).quantize(Decimal("0.0001"))


def _volume(value: Any) -> int:
    """Traded volume, with a missing one read as no trade rather than as NaN.

    An index series has been seen to answer without volume for a session. Zero
    is the honest reading there — the series has no shares to trade — and it
    keeps one absent number from failing a whole history.
    """
    if value is None or bool(pd.isna(value)):
        return 0
    return int(value)


def _upsert(session: Session, rows: list[dict]) -> int:
    """Write one page, with the provider's own duplicates resolved first.

    ``ON CONFLICT DO UPDATE`` refuses a statement whose *own* values hold a key
    twice — Postgres raises ``CardinalityViolation``, and it aborts the whole
    transaction rather than the statement, taking every other symbol written in
    that session down with it. So the last row for each ``(symbol,
    trading_day)`` wins here, before the statement is built. Last rather than
    first because a re-stated session is the provider correcting an adjustment
    factor, and the later value is the correction.
    """
    rows = _deduplicated(rows)
    if not rows:
        return 0
    statement = insert(BarDaily).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=["symbol", "trading_day"],
        set_={
            "series": statement.excluded.series,
            "open": statement.excluded.open,
            "high": statement.excluded.high,
            "low": statement.excluded.low,
            "close": statement.excluded.close,
            "volume": statement.excluded.volume,
            "price_basis": statement.excluded.price_basis,
            "source": statement.excluded.source,
            "observed_at": statement.excluded.observed_at,
        },
    )
    session.execute(statement)
    return len(rows)


def _deduplicated(rows: list[dict]) -> list[dict]:
    """One row per session, in the order they arrived, the last value kept."""
    by_day: dict[tuple[str, date], dict] = {}
    for row in rows:
        by_day[(row["symbol"], row["trading_day"])] = row
    return list(by_day.values())


__all__ = [
    "CALENDAR_DAYS_PER_SESSION",
    "DailyIngestError",
    "DailyIngestOutcome",
    "MAX_PAGES",
    "PRICE_BASIS",
    "PRICE_SCALE",
    "SERIES",
    "SERIES_EQUITY",
    "SERIES_INDEX",
    "SOURCE",
    "ensure_daily_bars",
    "fetch_daily",
]
