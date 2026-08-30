"""How a number becomes the string a Vietnamese reader sees.

One place, because two layers need the same answer. A KPI is resolved out of a
frame *here*, on the server, and stored already-formatted so re-opening a board
a month later does not depend on the browser still agreeing about what ``tỷ``
means. The browser draws the string it is handed.

**The unit decides the shape, not the magnitude alone.** ``VND`` shortens to
``tỷ``/``triệu`` because that is how the number is spoken; a percentage keeps one
decimal because the second one is noise on a figure computed from sixty
sessions; a count keeps none because half a session does not exist. A formatter
that only looked at how big a number is would render 1.500.000.000 sessions as
"1,5 tỷ".

**Vietnamese punctuation, always.** Decimal comma, thousands full stop. The
alternative is a page where the chart axis and the KPI beside it disagree about
which mark separates what.
"""

from __future__ import annotations

from typing import Any

#: Where a plain integer stops being read and starts being scanned. Past this a
#: reader counts digit groups instead of reading a figure, so the unit-aware
#: shortening below takes over.
_BILLION = 1_000_000_000
_MILLION = 1_000_000
_TRILLION = 1_000_000_000_000

#: Units that mean money in đồng. Named rather than sniffed from the column,
#: because a column called ``value`` holding đồng is exactly the case a sniffer
#: gets wrong.
_MONEY_UNITS = frozenset({"VND", "vnd", "đồng", "dong"})

#: Units that are already a proportion out of a hundred.
_PERCENT_UNITS = frozenset({"%", "pct", "percent"})


def _vi(text: str) -> str:
    """An ASCII-formatted number restated with Vietnamese separators."""
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _fixed(value: float, places: int) -> str:
    return _vi(f"{value:,.{places}f}")


def number(value: Any, unit: str | None = None) -> str:
    """One cell as a reader reads it, or the value itself when it is not a number.

    A non-numeric cell comes back as its own text rather than as an error: a
    comparison table's first column is a ticker, and a KPI naming it is a label
    the reader wants, not a failure.
    """
    if isinstance(value, bool) or value is None:
        return "" if value is None else ("Có" if value else "Không")
    if not isinstance(value, (int, float)):
        return str(value)

    numeric = float(value)
    if unit in _PERCENT_UNITS:
        return f"{_fixed(numeric, 1)}%"
    if unit in _MONEY_UNITS:
        return _money(numeric)
    if numeric == int(numeric) and abs(numeric) < _MILLION:
        return _fixed(numeric, 0)
    if abs(numeric) >= _BILLION:
        return _money(numeric)
    return _fixed(numeric, 2)


def _money(value: float) -> str:
    """Đồng, shortened at the two scales the language actually has words for.

    ``nghìn tỷ`` and not ``nghìn tỉ``: the store, the prompt and the panel all
    spell it with a ``y``, and one string with two spellings is one string a
    reader reads as two different things.
    """
    magnitude = abs(value)
    if magnitude >= _TRILLION:
        return f"{_fixed(value / _TRILLION, 2)} nghìn tỷ"
    if magnitude >= _BILLION:
        return f"{_fixed(value / _BILLION, 2)} tỷ"
    if magnitude >= _MILLION:
        return f"{_fixed(value / _MILLION, 2)} triệu"
    return _fixed(value, 0)


__all__ = ["number"]
