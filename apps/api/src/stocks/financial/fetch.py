"""Reading quarterly statements, and the five ways the response is not a table.

**The response is wide, one column per quarter.** Three meta columns (``item``,
``item_en``, ``item_id``) then a column per period, labelled ``2026-Q2``. It is
turned into one row per (period, line) here, because the set of lines differs
per template — 26 for a bank, 79 for a securities house, 25 for a steelmaker,
measured 2026-08-27 — and a wide table would be mostly nulls.

**How many quarters arrive depends on the client, not on the request.** Measured
2026-08-27 against the same account within minutes: vnstock 4.0.5 printed
"Financial statements limited to 4 periods" and answered four (2026-Q2 back to
2025-Q3), while 4.0.7 answered eight and occasionally nine (back to 2024-Q3, one
symbol to 2024-Q2). Nothing here asks for a depth, and no reader may assume one —
the store is what accumulates history, and a scan that only ever sees the newest
four quarters still reaches a year of depth after a year of scans.

**``item_id`` is not unique inside one response.** SSI answers two
``business_income_tax_deferred`` rows for 2026-Q2 — 4,585,945,424 and
758,786,600 — and the second one's own label reads "Lợi nhuận thuần phân bổ cho
lợi ích của cổ đông không kiểm soát": the minority interest line arriving under
another line's id. Its balance sheet answers ``accumulated_depreciation`` four
times, one per class of asset. So each row carries the 0-based index of its
``item_id`` within the response, and that index is part of the key. Collapsing
duplicates would drop numbers that differ.

**A label can contradict its number.** SSI's ``business_income_tax_expenses``
for 2026-Q2 is +1,528,966,041,130 — positive, and about equal to its
``operating_profit_loss``. Nothing here interprets a label; the names are stored
raw and ``templates.py`` is the single place that decides what a line means.

**Ratios come from a different provider source with a different convention.**
``Finance(source="VCI").ratio()`` answers 2018 quarters for a request made in
2026 — eight years stale — so the ratios are read from ``KBS``, which answers
the current quarter. KBS reports ROE as a percent (4.74) where VCI reports the
same figure as a fraction (0.0589), and it ignores ``lang="en"``, so the key is
``item_id`` and never the label. That convention is recorded in the stored
``source`` rather than assumed by a reader.

**A period label can repeat.** A KBS ratio response answers columns
``['2026-Q2', '2025-Q4', '2026-Q1', '2025-Q4_1']`` — pandas' suffix for a
duplicated column name. Measured: the ``2025-Q4_1`` column's values are
identical to the ``2026-Q2`` column's, so it carries no quarter of its own and
there is no way to tell which of the two labels the provider meant. The first
column for a period wins and later ones are dropped, which is why only about
three distinct quarters of ratios are real.

pandas and vnstock are imported at module load, as in the daily provider: only
an operator's job imports this module, so the seconds are spent there rather
than by whoever asks the first question.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Iterator

import pandas as pd
from vnstock.api.financial import Finance

from src.core.vnstock_wrapper import safe_vnstock_call
from src.stocks.providers.normalize import VN_TZ

from . import (
    STATEMENT_BALANCE,
    STATEMENT_CASHFLOW,
    STATEMENT_INCOME,
    STATEMENTS,
)

logger = logging.getLogger(__name__)

#: The ratio snapshot, asked for alongside the statements because it costs the
#: same one request per symbol. Not a statement — it lands in its own table from
#: its own provider source — but it is one of the parts a scan can be asked for.
PART_RATIO = "ratio"
PARTS = STATEMENTS + (PART_RATIO,)

#: What a stored row says about where its number and its units came from. The
#: sub-source is part of the meaning, not a detail: KBS's ROE is a percent and
#: VCI's is a fraction.
SOURCE_STATEMENT = "vnstock.VCI"
SOURCE_RATIO = "vnstock.KBS"

#: The provider's own sources. ``Finance`` accepts only these two — there is no
#: TCBS behind it.
PROVIDER_SOURCE_STATEMENT = "VCI"
PROVIDER_SOURCE_RATIO = "KBS"

#: Columns that describe the line rather than a quarter of it.
META_COLUMNS = ("item", "item_en", "item_id")

#: A period column. The optional trailing ``_1`` is pandas renaming a duplicated
#: column name, not a period of its own.
PERIOD_PATTERN = re.compile(r"^(\d{4})-Q([1-4])(?:_\d+)?$")

#: Statement values are whole dong; ratios carry two decimals. Four is the
#: table's scale, so the quantize happens here and the database never rounds
#: silently.
VALUE_SCALE = Decimal("0.0001")


class FinancialFetchError(RuntimeError):
    """The provider answered with something this code will not store.

    Raised instead of writing whatever could be parsed. A shape change upstream
    is a thing to fix, and half a quarter written from a best-effort parse hides
    it behind numbers that are merely odd.
    """


def _client(symbol: str, source: str) -> Finance:
    """The provider client, built where a ``sys.exit()`` cannot end the run.

    vnstock exits the process rather than raising when it decides it has had
    enough, and it does so from the constructor as well as from the call. A
    ``SystemExit`` is a ``BaseException``, so the job's per-symbol ``except
    Exception`` does not see it: a market-wide scan would stop mid-run, with
    exit code 0 and no failing symbol named — which is exactly how the first
    1,523-symbol pass ended, after 53 of them. ``safe_vnstock_call`` turns that
    exit into a retry and then into an ordinary exception, so one symbol costs
    one symbol.
    """
    client = safe_vnstock_call(Finance, symbol=symbol, source=source)
    if client is None:
        raise FinancialFetchError(f"vnstock would not open a client for {symbol}")
    return client


def fetch_statement(symbol: str, statement: str) -> pd.DataFrame:
    """One statement's quarters for one symbol, as the provider gives them."""
    if statement not in STATEMENTS:
        raise FinancialFetchError(
            f"{statement!r} is not a statement; expected one of {STATEMENTS}"
        )
    finance = _client(symbol, PROVIDER_SOURCE_STATEMENT)
    method = {
        STATEMENT_INCOME: finance.income_statement,
        STATEMENT_BALANCE: finance.balance_sheet,
        STATEMENT_CASHFLOW: finance.cash_flow,
    }[statement]
    frame = safe_vnstock_call(method, period="quarter", lang="en", dropna=True)
    if frame is None:
        # ``safe_vnstock_call`` swallows every failure into None, and a symbol
        # that has never published a statement is one of them. The two cannot be
        # told apart from here, so the caller — the job, which can see the whole
        # scope — decides what one symbol's silence costs.
        raise FinancialFetchError(
            f"vnstock answered nothing for {symbol} {statement}"
        )
    return frame


def fetch_ratio(symbol: str) -> pd.DataFrame:
    """The reported ratios for one symbol, from the source that has current ones."""
    finance = _client(symbol, PROVIDER_SOURCE_RATIO)
    frame = safe_vnstock_call(finance.ratio, period="quarter", lang="en", dropna=True)
    if frame is None:
        raise FinancialFetchError(f"vnstock answered nothing for {symbol} ratios")
    return frame


Fetch = Callable[[str, str], pd.DataFrame]
RatioFetch = Callable[[str], pd.DataFrame]


def statement_rows(
    symbol: str,
    statement: str,
    frame: pd.DataFrame,
    *,
    observed_at: datetime | None = None,
) -> list[dict]:
    """One statement's response as rows of ``financial_statement_line``."""
    if statement not in STATEMENTS:
        raise FinancialFetchError(
            f"{statement!r} is not a statement; expected one of {STATEMENTS}"
        )
    observed_at = observed_at or datetime.now(VN_TZ)
    return [
        {
            "symbol": symbol.upper(),
            "period": period,
            "statement": statement,
            "item_id": item_id,
            "item_seq": item_seq,
            "value": value,
            "source": SOURCE_STATEMENT,
            "observed_at": observed_at,
        }
        for period, item_id, item_seq, value in _cells(symbol, statement, frame)
    ]


def ratio_rows(
    symbol: str, frame: pd.DataFrame, *, observed_at: datetime | None = None
) -> list[dict]:
    """A ratio response as rows of ``financial_ratio_snapshot``."""
    observed_at = observed_at or datetime.now(VN_TZ)
    return [
        {
            "symbol": symbol.upper(),
            "period": period,
            "item_id": item_id,
            "item_seq": item_seq,
            "value": value,
            "source": SOURCE_RATIO,
            "observed_at": observed_at,
        }
        for period, item_id, item_seq, value in _cells(symbol, PART_RATIO, frame)
    ]


def _cells(
    symbol: str, part: str, frame: pd.DataFrame
) -> Iterator[tuple[str, str, int, Decimal]]:
    """Wide response to ``(period, item_id, item_seq, value)``, in column order.

    A cell the provider left empty is skipped rather than written as a zero: a
    line a company does not report is not a line it reported as nothing, and a
    screener cannot tell those apart after the fact.
    """
    if "item_id" not in frame.columns:
        raise FinancialFetchError(
            f"vnstock answered for {symbol} {part} without item_id; got "
            f"{list(frame.columns)}"
        )
    item_ids = [str(value) for value in frame["item_id"]]
    sequences = _sequences(item_ids)

    for index, period in _period_columns(symbol, part, frame):
        column = frame.iloc[:, index]
        for row, (item_id, item_seq) in enumerate(zip(item_ids, sequences)):
            value = column.iloc[row]
            if value is None or bool(pd.isna(value)):
                continue
            yield period, item_id, item_seq, _value(value)


def _period_columns(
    symbol: str, part: str, frame: pd.DataFrame
) -> list[tuple[int, str]]:
    """The quarter columns by position, first occurrence of each period only.

    Positional rather than by label because a duplicated label makes
    ``frame[label]`` a DataFrame, and because the first column for a period is
    the one kept.
    """
    columns: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, label in enumerate(frame.columns):
        name = str(label)
        if name in META_COLUMNS:
            continue
        match = PERIOD_PATTERN.match(name)
        if match is None:
            # The provider has been seen to carry extra meta columns per source.
            # An unknown column is not a quarter, and ignoring it is safe in a
            # way that guessing a period for it would not be.
            logger.debug("%s %s: ignoring column %r", symbol, part, name)
            continue
        period = f"{match.group(1)}-Q{match.group(2)}"
        if period in seen:
            # Measured on a KBS ratio response: the ``2025-Q4_1`` column repeats
            # the ``2026-Q2`` column's values exactly, so one of the two labels
            # is wrong and neither can be trusted for the later column.
            logger.info(
                "%s %s: dropping a second column for %s (label %r)",
                symbol,
                part,
                period,
                name,
            )
            continue
        seen.add(period)
        columns.append((index, period))

    if not columns:
        raise FinancialFetchError(
            f"vnstock answered for {symbol} {part} with no quarter column; got "
            f"{list(frame.columns)}"
        )
    return columns


def _sequences(item_ids: list[str]) -> list[int]:
    """The 0-based occurrence index of each row's ``item_id`` in the response."""
    counts: dict[str, int] = {}
    sequences: list[int] = []
    for item_id in item_ids:
        sequences.append(counts.get(item_id, 0))
        counts[item_id] = counts.get(item_id, 0) + 1
    return sequences


def _value(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(VALUE_SCALE)


__all__ = [
    "META_COLUMNS",
    "PARTS",
    "PART_RATIO",
    "PERIOD_PATTERN",
    "SOURCE_RATIO",
    "SOURCE_STATEMENT",
    "STATEMENTS",
    "STATEMENT_BALANCE",
    "STATEMENT_CASHFLOW",
    "STATEMENT_INCOME",
    "Fetch",
    "FinancialFetchError",
    "RatioFetch",
    "fetch_ratio",
    "fetch_statement",
    "ratio_rows",
    "statement_rows",
]
