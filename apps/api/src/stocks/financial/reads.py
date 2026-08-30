"""The two reads the store exists for: one symbol's quarters, one quarter's market.

Everything here reads ``item_seq = 0``. Where the provider repeats an
``item_id`` inside one response, the later occurrences have been measured to be a
different line arriving under the wrong id (SSI's second
``business_income_tax_deferred`` is its minority interest), so the first
occurrence is the one a named concept resolves against. The repeats are still
stored — dropping them would lose numbers — and a caller that wants them asks
the table directly.

Periods are text and sort correctly as text: ``2026-Q2`` > ``2026-Q1`` >
``2025-Q4`` lexicographically, because the year leads and the quarter is one
digit. So "the newest quarter" is ``max(period)`` and needs no parsing.

The market-wide read asks for the handful of lines the resolver can use rather
than a whole statement. A quarter of the market is over a hundred thousand rows
across 25 to 208 lines per symbol; a screener needs eight of them.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Sequence

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from src.stocks.models import FinancialRatioSnapshot, FinancialStatementLine

from . import templates
from .templates import Concept, ConceptValue

#: The occurrence a concept resolves against.
PRIMARY_SEQ = 0


def latest_period(session: Session, symbol: str | None = None) -> str | None:
    """The newest quarter stored, for one symbol or across the whole store."""
    statement = select(func.max(FinancialStatementLine.period))
    if symbol is not None:
        statement = statement.where(FinancialStatementLine.symbol == symbol.upper())
    return session.execute(statement).scalar_one_or_none()


def periods_for(
    session: Session, symbol: str, *, statement: str | None = None
) -> tuple[str, ...]:
    """One symbol's stored quarters, newest first."""
    query = (
        select(FinancialStatementLine.period)
        .where(FinancialStatementLine.symbol == symbol.upper())
        .distinct()
        .order_by(FinancialStatementLine.period.desc())
    )
    if statement is not None:
        query = query.where(FinancialStatementLine.statement == statement)
    return tuple(session.execute(query).scalars())


def lines_for(
    session: Session, symbol: str, period: str
) -> dict[tuple[str, str], Decimal]:
    """One symbol's lines for one quarter, keyed ``(statement, item_id)``."""
    rows = session.execute(
        select(
            FinancialStatementLine.statement,
            FinancialStatementLine.item_id,
            FinancialStatementLine.value,
        ).where(
            FinancialStatementLine.symbol == symbol.upper(),
            FinancialStatementLine.period == period,
            FinancialStatementLine.item_seq == PRIMARY_SEQ,
        )
    ).all()
    return {(statement, item_id): value for statement, item_id, value in rows}


def lines_for_many(
    session: Session,
    symbols: Sequence[str],
    periods: Sequence[str],
    items: Sequence[tuple[str, str]] | None = None,
) -> dict[tuple[str, str, str, str], Decimal]:
    """Many symbols' lines for many quarters, keyed ``(symbol, period, statement, item_id)``.

    One query rather than a loop over :func:`lines_for`, because the question
    this answers is a *table* — ten symbols against eight quarters against a
    chosen set of lines — and a loop would be eighty round trips to build one.

    ``items`` narrows to the lines actually wanted. Passing ``None`` reads every
    line the symbols report, which for ten symbols across eight quarters of an
    insurer's balance sheet is thousands of rows; the caller that means "the
    whole statement" says so by leaving it out, and the ceiling that stops that
    being a mistake lives in the tool layer where the model's request arrives.

    ``item_seq = 0`` here as everywhere: the first occurrence is the one a named
    concept resolves against, and the repeats are a different line filed under
    the wrong id.

    A pair the store does not hold is simply absent from the mapping. Absent and
    zero are different answers, and a caller building a frame writes ``null`` for
    the first — a line a company does not report is not a line it reported as
    nothing.
    """
    wanted_symbols = [symbol.upper() for symbol in symbols]
    wanted_periods = list(periods)
    if not wanted_symbols or not wanted_periods:
        return {}

    query = select(
        FinancialStatementLine.symbol,
        FinancialStatementLine.period,
        FinancialStatementLine.statement,
        FinancialStatementLine.item_id,
        FinancialStatementLine.value,
    ).where(
        FinancialStatementLine.symbol.in_(wanted_symbols),
        FinancialStatementLine.period.in_(wanted_periods),
        FinancialStatementLine.item_seq == PRIMARY_SEQ,
    )
    if items is not None:
        wanted_items = list(items)
        if not wanted_items:
            return {}
        query = query.where(_wanted_items(wanted_items))

    return {
        (symbol, period, statement, item_id): value
        for symbol, period, statement, item_id, value in session.execute(query).all()
    }


def ratios_for_many(
    session: Session,
    symbols: Sequence[str],
    periods: Sequence[str],
    items: Sequence[str] | None = None,
) -> dict[tuple[str, str, str], Decimal]:
    """Many symbols' reported ratios for many quarters, keyed ``(symbol, period, item_id)``.

    The same read as :func:`ratios_for` widened the same way, and with the same
    warning it carries: the units follow the source that reported them, so a
    caller comparing two sources reads the ``source`` column instead of this.
    """
    wanted_symbols = [symbol.upper() for symbol in symbols]
    wanted_periods = list(periods)
    if not wanted_symbols or not wanted_periods:
        return {}

    query = select(
        FinancialRatioSnapshot.symbol,
        FinancialRatioSnapshot.period,
        FinancialRatioSnapshot.item_id,
        FinancialRatioSnapshot.value,
    ).where(
        FinancialRatioSnapshot.symbol.in_(wanted_symbols),
        FinancialRatioSnapshot.period.in_(wanted_periods),
        FinancialRatioSnapshot.item_seq == PRIMARY_SEQ,
    )
    if items is not None:
        wanted_items = list(items)
        if not wanted_items:
            return {}
        query = query.where(FinancialRatioSnapshot.item_id.in_(wanted_items))

    return {
        (symbol, period, item_id): value
        for symbol, period, item_id, value in session.execute(query).all()
    }


def periods_for_many(
    session: Session,
    symbols: Sequence[str],
    *,
    statement: str | None = None,
) -> tuple[str, ...]:
    """Every quarter any of these symbols filed a statement line for, newest first.

    The union rather than the intersection. A frame of two symbols where one
    reports a quarter the other does not still has that quarter as a row; the
    cell that is missing becomes ``null``, which is the honest answer and the one
    the intersection would silently delete along with the whole row.
    """
    wanted = [symbol.upper() for symbol in symbols]
    if not wanted:
        return ()
    query = (
        select(FinancialStatementLine.period)
        .where(FinancialStatementLine.symbol.in_(wanted))
        .distinct()
        .order_by(FinancialStatementLine.period.desc())
    )
    if statement is not None:
        query = query.where(FinancialStatementLine.statement == statement)
    return tuple(session.execute(query).scalars())


def ratio_periods_for_many(
    session: Session, symbols: Sequence[str]
) -> tuple[str, ...]:
    """Every quarter any of these symbols holds a *ratio* for, newest first.

    Its own read and not :func:`periods_for_many` with a different filter,
    because the two tables are filled from two independent provider responses
    and a scan writes them one part at a time (``store.ingest_symbol``): a symbol
    whose statement fetch failed and whose ratio fetch succeeded holds a quarter
    in one table and not the other. Asking the statement table which quarters
    exist would silently drop exactly those, with no refusal saying why — and the
    provider only ever answers about three distinct quarters of ratios anyway
    (``fetch.py``), so the set really is smaller and really is different.
    """
    wanted = [symbol.upper() for symbol in symbols]
    if not wanted:
        return ()
    return tuple(
        session.execute(
            select(FinancialRatioSnapshot.period)
            .where(FinancialRatioSnapshot.symbol.in_(wanted))
            .distinct()
            .order_by(FinancialRatioSnapshot.period.desc())
        ).scalars()
    )


def periods_held_by(
    session: Session, symbols: Sequence[str]
) -> dict[str, frozenset[str]]:
    """Which quarters each symbol actually filed, so a gap can name itself.

    A frame's rows are the *union* of the quarters any symbol holds, so a symbol
    that filed four of eight has four rows of nulls. Without this, every one of
    those cells is counted as a line the company did not report — which is the
    wrong input to blame. ``CLAUDE.md``: a refusal code has to point at the input
    that is actually missing.
    """
    wanted = [symbol.upper() for symbol in symbols]
    if not wanted:
        return {}
    held: dict[str, set[str]] = {}
    for symbol, period in session.execute(
        select(FinancialStatementLine.symbol, FinancialStatementLine.period)
        .where(FinancialStatementLine.symbol.in_(wanted))
        .distinct()
    ).all():
        held.setdefault(symbol, set()).add(period)
    return {symbol: frozenset(periods) for symbol, periods in held.items()}


def concepts_for(
    session: Session, symbol: str, period: str
) -> dict[Concept, ConceptValue]:
    """Every named concept for one symbol and quarter, unknowns included."""
    return templates.resolve_all(lines_for(session, symbol, period))


def concepts_for_period(
    session: Session,
    period: str,
    *,
    symbols: Iterable[str] | None = None,
) -> dict[str, dict[Concept, ConceptValue]]:
    """Every named concept for one quarter, market-wide, in one query.

    Only symbols with at least one of the resolver's lines stored appear. A
    symbol that appears with unknowns is a symbol whose statement was stored and
    did not carry what the concept needs — which is the distinction a screener
    reports as "excluded" rather than "not covered".
    """
    query = select(
        FinancialStatementLine.symbol,
        FinancialStatementLine.statement,
        FinancialStatementLine.item_id,
        FinancialStatementLine.value,
    ).where(
        FinancialStatementLine.period == period,
        FinancialStatementLine.item_seq == PRIMARY_SEQ,
        _wanted_items(templates.REQUIRED_ITEMS),
    )
    if symbols is not None:
        wanted = [symbol.upper() for symbol in symbols]
        if not wanted:
            return {}
        query = query.where(FinancialStatementLine.symbol.in_(wanted))

    per_symbol: dict[str, dict[tuple[str, str], Decimal]] = {}
    for symbol, statement, item_id, value in session.execute(query).all():
        per_symbol.setdefault(symbol, {})[(statement, item_id)] = value
    return {
        symbol: templates.resolve_all(lines) for symbol, lines in per_symbol.items()
    }


def ratios_for(session: Session, symbol: str, period: str) -> dict[str, Decimal]:
    """One symbol's reported ratios for one quarter, keyed by ``item_id``.

    The units follow the source that reported them — KBS answers ROE as a
    percent — which is why the caller that compares two sources reads the
    ``source`` column instead of this shortcut.
    """
    rows = session.execute(
        select(FinancialRatioSnapshot.item_id, FinancialRatioSnapshot.value).where(
            FinancialRatioSnapshot.symbol == symbol.upper(),
            FinancialRatioSnapshot.period == period,
            FinancialRatioSnapshot.item_seq == PRIMARY_SEQ,
        )
    ).all()
    return {item_id: value for item_id, value in rows}


def _wanted_items(items: Sequence[tuple[str, str]]):
    """A ``(statement, item_id) IN (...)`` clause the index can use.

    Written as a tuple comparison rather than an OR of equalities so the read
    stays one predicate however many lines the resolver grows to need.
    """
    return tuple_(
        FinancialStatementLine.statement, FinancialStatementLine.item_id
    ).in_(list(items))


__all__ = [
    "PRIMARY_SEQ",
    "concepts_for",
    "concepts_for_period",
    "latest_period",
    "lines_for",
    "lines_for_many",
    "periods_for",
    "periods_for_many",
    "periods_held_by",
    "ratio_periods_for_many",
    "ratios_for",
    "ratios_for_many",
]
