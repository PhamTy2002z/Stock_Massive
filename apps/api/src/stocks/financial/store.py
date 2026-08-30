"""Writing one symbol's quarters idempotently, and why the write is an upsert.

The provider restates a quarter: an audited figure replaces the one published
with the quarterly release, and the community tier's four-period window slides
forward every quarter. So the same (symbol, period, statement, item_id,
item_seq) has to land on the same row rather than beside it, and a scan run
twice writes no new rows the second time.

The duplicate resolution before the statement is not defensive tidiness.
``ON CONFLICT DO UPDATE`` refuses a statement whose *own* values hold a key
twice — Postgres raises ``CardinalityViolation``, and it aborts the transaction
rather than the statement, taking the whole symbol down with it. The occurrence
index makes the provider's repeated ``item_id`` distinct, so what is left here is
the pathological case of a response repeating a period column *and* the label
check letting it through; the last value wins, matching the daily spine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.alpha.models import FinancialStatementItem
from src.stocks.models import FinancialRatioSnapshot, FinancialStatementLine

from . import fetch
from .fetch import PART_RATIO, PARTS, Fetch, FinancialFetchError, RatioFetch

logger = logging.getLogger(__name__)

STATEMENT_KEY = ("symbol", "period", "statement", "item_id", "item_seq")
RATIO_KEY = ("symbol", "period", "item_id", "item_seq")
#: A label is keyed by the id it names and not by the quarter or the symbol it
#: was read from — the same line carries the same heading across every symbol
#: reporting under that template.
ITEM_KEY = ("statement", "item_id")

#: What a re-run of a line write overwrites. A restated quarter replaces the
#: number and says when it was seen; nothing else about the row can move.
_LINE_UPDATE = ("value", "source", "observed_at")

#: What a re-seed of a label overwrites. ``seeded_from`` is in the set on
#: purpose: re-seeding from a different reporting template is how a label filed
#: under the wrong one gets corrected, and a column that recorded only the first
#: symbol ever seen would make that correction invisible.
_ITEM_UPDATE = ("label_vi", "label_en", "seeded_from", "source", "observed_at")


@dataclass(frozen=True)
class IngestOutcome:
    """What one symbol's ingest did, in terms a job log can print."""

    symbol: str
    parts: tuple[str, ...]
    calls: int
    rows_written: int
    periods: tuple[str, ...] = field(default_factory=tuple)


def write_statement_lines(session: Session, rows: Sequence[dict]) -> int:
    """Upsert statement lines and report how many rows the write covered."""
    return _upsert(session, FinancialStatementLine, rows, STATEMENT_KEY, _LINE_UPDATE)


def write_ratio_lines(session: Session, rows: Sequence[dict]) -> int:
    """Upsert ratio rows and report how many rows the write covered."""
    return _upsert(session, FinancialRatioSnapshot, rows, RATIO_KEY, _LINE_UPDATE)


def write_statement_items(session: Session, rows: Sequence[dict]) -> int:
    """Upsert statement-line labels and report how many rows the write covered."""
    return _upsert(session, FinancialStatementItem, rows, ITEM_KEY, _ITEM_UPDATE)


def ingest_symbol(
    session: Session,
    symbol: str,
    *,
    parts: Iterable[str] = PARTS,
    fetch_statement: Fetch | None = None,
    fetch_ratio: RatioFetch | None = None,
    observed_at: datetime | None = None,
) -> IngestOutcome:
    """Fetch and store the requested parts for one symbol, in one transaction.

    The parts are fetched in the order given, and one of them raising leaves the
    caller's session to be rolled back with the earlier ones in it — which is why
    the job calls this once per part rather than once per symbol. Durability
    granularity belongs to whoever owns the session.

    ``fetch_statement``, ``fetch_ratio`` and ``observed_at`` are injectable so
    the suite can prove the normalisation and the upsert without reaching the
    network; production passes none of them.
    """
    wanted = tuple(parts)
    unknown_parts = [part for part in wanted if part not in PARTS]
    if unknown_parts:
        raise FinancialFetchError(
            f"{unknown_parts} are not parts of a scan; expected some of {PARTS}"
        )

    symbol = symbol.upper()
    statement_fetch = fetch_statement or fetch.fetch_statement
    ratio_fetch = fetch_ratio or fetch.fetch_ratio

    written = 0
    calls = 0
    periods: set[str] = set()

    for part in wanted:
        if part == PART_RATIO:
            frame = ratio_fetch(symbol)
            calls += 1
            rows = fetch.ratio_rows(symbol, frame, observed_at=observed_at)
            written += write_ratio_lines(session, rows)
        else:
            frame = statement_fetch(symbol, part)
            calls += 1
            rows = fetch.statement_rows(
                symbol, part, frame, observed_at=observed_at
            )
            written += write_statement_lines(session, rows)
        periods.update(row["period"] for row in rows)

    return IngestOutcome(
        symbol=symbol,
        parts=wanted,
        calls=calls,
        rows_written=written,
        periods=tuple(sorted(periods, reverse=True)),
    )


def _upsert(
    session: Session,
    model: type,
    rows: Sequence[dict],
    key: tuple[str, ...],
    update: tuple[str, ...],
) -> int:
    """One idempotent write, told which columns a re-run is allowed to move.

    ``update`` is an argument rather than a constant because the two things
    written through here restate different columns: a line restates its number,
    a label restates its wording. Left as one hardcoded set, the label write
    would have named a ``value`` column its table does not have.
    """
    rows = _deduplicated(rows, key)
    if not rows:
        return 0
    statement = insert(model).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=list(key),
        set_={name: getattr(statement.excluded, name) for name in update},
    )
    session.execute(statement)
    return len(rows)


def _deduplicated(rows: Sequence[dict], key: tuple[str, ...]) -> list[dict]:
    """One row per key, in the order they arrived, the last value kept.

    Last rather than first because a repeated key inside one response is the
    provider restating a figure later in its own answer.
    """
    by_key: dict[tuple, dict] = {}
    for row in rows:
        by_key[tuple(row[name] for name in key)] = row
    return list(by_key.values())


__all__ = [
    "ITEM_KEY",
    "RATIO_KEY",
    "STATEMENT_KEY",
    "IngestOutcome",
    "ingest_symbol",
    "write_ratio_lines",
    "write_statement_items",
    "write_statement_lines",
]
