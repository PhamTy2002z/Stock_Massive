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
    "periods_for",
    "ratios_for",
]
