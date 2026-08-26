"""Fetching fifteen-minute bars, and the four things that go wrong.

**The grid is padding.** Ninety-six buckets come back for a day that has at most
seventeen. ``session_window`` decides which survive, and they are filtered before
the write rather than after, so no consumer inherits the problem.

**The provider revises.** A session's last bucket can change after the close, so
the write is an upsert on ``(symbol, bucket_start)`` rather than an insert. A
second row for the same quarter hour would double the volume every liquidity
statistic is built from.

**A cold symbol needs a year and a warm one needs a day.** One request answers
either, so the first fetch takes the full year the provider will give and every
later one starts from the last stored session — re-fetching that session
deliberately, because it is the one the provider may have revised.

**vnstock has no SLA and calls ``sys.exit()``.** Every call goes through
``safe_vnstock_call``, and a response whose columns are not the ones documented
raises rather than writing a partial day: a liquidity profile over a silently
half-ingested session is a wrong answer that looks like a right one.

pandas and vnstock are imported here at module load, not lazily inside the
handler. The import costs seconds, and a lazy import spends them on whoever asks
the first question rather than on the container starting up.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from vnstock.api.quote import Quote

from src.core.vnstock_wrapper import safe_vnstock_call
from src.stocks.models import BarIntraday15m
from src.stocks.providers.normalize import VN_TZ

from . import session_window

logger = logging.getLogger(__name__)

SOURCE = "vnstock"

#: The provider's own source for intraday history. VCI is the one observed to
#: answer a year of 15-minute bars in a single request on the community tier.
PROVIDER_SOURCE = "VCI"

#: Quotes come back in thousands of dong (74.5 for a 74,500đ share). The store
#: speaks VND, like ``provider_snapshots.payload.price_unit``.
PRICE_SCALE = Decimal(1000)

#: How far back a first fetch reaches. The provider's hard ceiling for
#: 15-minute bars is one year, and asking for it costs the same single request
#: as asking for a month.
COLD_START_DAYS = 365

#: A warm fetch starts at the last stored session rather than after it, so a
#: bucket the provider revised is corrected instead of frozen.
REQUIRED_COLUMNS = ("time", "open", "high", "low", "close", "volume")


class IntradayIngestError(RuntimeError):
    """The provider answered with something this code will not write.

    Raised instead of writing what could be parsed. A shape change upstream is
    a thing to fix, and a table half-filled from a best-effort parse hides it
    behind statistics that are merely odd.
    """


@dataclass(frozen=True)
class IngestOutcome:
    """What one ``ensure_bars`` call did, in terms a smoke test can assert on."""

    symbol: str
    fetched_from: date
    rows_written: int
    padding_dropped: int
    sessions_stored: int
    last_session: date | None


def _fetch_from_vnstock(symbol: str, start: date, end: date) -> pd.DataFrame:
    quote = Quote(source=PROVIDER_SOURCE, symbol=symbol)
    frame = safe_vnstock_call(
        quote.history,
        start=start.isoformat(),
        end=end.isoformat(),
        interval="15m",
    )
    if frame is None:
        raise IntradayIngestError(
            f"vnstock gave up on {symbol} after its retries; nothing was written"
        )
    return frame


Fetch = Callable[[str, date, date], pd.DataFrame]


def ensure_bars(
    session: Session,
    symbol: str,
    *,
    sessions: int,
    fetch: Fetch | None = None,
    today: date | None = None,
) -> IngestOutcome:
    """Make sure the store holds at least ``sessions`` sessions for ``symbol``.

    ``fetch`` and ``today`` are injectable so the suite can prove the delta
    logic and the padding filter without reaching the network; production passes
    neither.
    """
    symbol = symbol.upper()
    fetch = fetch or _fetch_from_vnstock
    today = today or datetime.now(VN_TZ).date()

    stored_days, last_session = _what_is_stored(session, symbol)
    start = _start_from(stored_days, last_session, sessions, today)

    frame = fetch(symbol, start, today)
    rows, padding = _rows_from(symbol, frame)
    written = _upsert(session, rows)

    stored_days, last_session = _what_is_stored(session, symbol)
    return IngestOutcome(
        symbol=symbol,
        fetched_from=start,
        rows_written=written,
        padding_dropped=padding,
        sessions_stored=stored_days,
        last_session=last_session,
    )


def _what_is_stored(session: Session, symbol: str) -> tuple[int, date | None]:
    row = session.execute(
        select(
            func.count(func.distinct(BarIntraday15m.trading_day)),
            func.max(BarIntraday15m.trading_day),
        ).where(BarIntraday15m.symbol == symbol)
    ).one()
    return int(row[0] or 0), row[1]


def _start_from(
    stored_days: int, last_session: date | None, sessions: int, today: date
) -> date:
    """Where to ask from: the last stored session, or a year back.

    A store holding fewer sessions than the question needs is treated as cold
    even when it is not empty — asking for the gap costs the same one request as
    asking for the year, and a gap filled from its own edge would keep the store
    permanently one backfill short.
    """
    if last_session is None or stored_days < sessions:
        return today - timedelta(days=COLD_START_DAYS)
    return last_session


def _rows_from(symbol: str, frame: pd.DataFrame) -> tuple[list[dict], int]:
    """Session buckets as rows, and how many padding buckets were dropped."""
    missing = [name for name in REQUIRED_COLUMNS if name not in frame.columns]
    if missing:
        raise IntradayIngestError(
            f"vnstock answered for {symbol} without {missing}; got "
            f"{list(frame.columns)}"
        )

    observed_at = datetime.now(VN_TZ)
    rows: list[dict] = []
    padding = 0

    for record in frame.itertuples(index=False):
        moment: pd.Timestamp = record.time
        phase = session_window.phase_of(moment.time())
        if phase is None or _is_blank(record):
            padding += 1
            continue
        rows.append(
            {
                "symbol": symbol,
                "bucket_start": moment.to_pydatetime().replace(tzinfo=VN_TZ),
                "trading_day": moment.date(),
                "phase": phase,
                "open": _vnd(record.open),
                "high": _vnd(record.high),
                "low": _vnd(record.low),
                "close": _vnd(record.close),
                "volume": int(record.volume),
                "source": SOURCE,
                "observed_at": observed_at,
            }
        )
    return rows, padding


def _is_blank(record) -> bool:
    """A bucket inside session hours that nobody traded in.

    Dropped rather than written as a zero. Zero volume with no price is the
    provider saying "no data for this quarter hour"; written as a number it
    becomes the claim that nobody wanted to trade, which is a different and
    unsupported statement — and it is the claim a heatmap would colour.
    """
    return bool(pd.isna(record.open)) or bool(pd.isna(record.close))


def _vnd(value: float) -> Decimal:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise IntradayIngestError("a session bucket arrived with no price")
    return (Decimal(str(value)) * PRICE_SCALE).quantize(Decimal("0.0001"))


def _upsert(session: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    statement = insert(BarIntraday15m).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=["symbol", "bucket_start"],
        set_={
            "trading_day": statement.excluded.trading_day,
            "phase": statement.excluded.phase,
            "open": statement.excluded.open,
            "high": statement.excluded.high,
            "low": statement.excluded.low,
            "close": statement.excluded.close,
            "volume": statement.excluded.volume,
            "source": statement.excluded.source,
            "observed_at": statement.excluded.observed_at,
        },
    )
    session.execute(statement)
    return len(rows)


__all__ = [
    "COLD_START_DAYS",
    "IngestOutcome",
    "IntradayIngestError",
    "PRICE_SCALE",
    "SOURCE",
    "ensure_bars",
]
