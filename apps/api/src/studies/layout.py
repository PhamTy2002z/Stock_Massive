"""How wide each block is, on a grid of twelve, decided here and not in the browser.

The browser knows the width of the panel; it does not know that these two charts
are a pair and that one below them is a summary. So the server assigns a span
and the browser honours it, with exactly one thing left to the far end: a
narrow viewport collapses a third of a row to a half and a half to the whole,
which is a fact about the reader's screen and nothing this layer can see.

**Every row adds to twelve.** Not as an aesthetic — as the property that makes
the grid predictable enough to test. A row that adds to eight leaves a gap that
looks like a missing block, and a reader cannot tell a gap from a failure. So
blocks are packed into rows, and a row that comes up short widens its last block
until it does not.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: The grid. Twelve because it divides by two, three and four, which is exactly
#: the set of row shapes a board of at most four blocks per section can want.
COLUMNS = 12

#: How many flexible visuals share one row before a second row starts. Three,
#: because a quarter of twelve is where a chart stops having room for its axis
#: labels on the panel this draws into.
MAX_PER_ROW = 3


@dataclass(frozen=True)
class Placed:
    """One block's width, and which row of the section it landed in."""

    span: int
    row: int


def assign(natural: Sequence[int]) -> list[Placed]:
    """Pack one section's blocks into rows of twelve.

    ``natural`` is what each block would like to be — twelve for a full-width
    widget, a share of twelve for a chart that sits beside its neighbours. The
    packer honours it where the row has room and widens the last block of a
    short row rather than leaving the gap.
    """
    placed: list[Placed] = []
    row = 0
    used = 0
    start = 0
    for span in natural:
        want = max(1, min(COLUMNS, span))
        if used + want > COLUMNS and used > 0:
            _fill(placed, start, used)
            row += 1
            used = 0
            start = len(placed)
        placed.append(Placed(span=want, row=row))
        used += want
    if placed:
        _fill(placed, start, used)
    return placed


def _fill(placed: list[Placed], start: int, used: int) -> None:
    """Widen the last block of a row that came up short of twelve."""
    if used >= COLUMNS or start >= len(placed):
        return
    last = placed[-1]
    placed[-1] = Placed(span=last.span + (COLUMNS - used), row=last.row)


def natural_spans(full_width: Sequence[bool]) -> list[int]:
    """What each block in one section wants, before packing.

    ``full_width`` says which blocks refuse to share a row. The rest are split
    into runs, and a run of *n* blocks is drawn *n* to a row up to three — one
    gets the width, two get halves, three get thirds. Four splits into two rows
    of halves rather than a row of thirds and a lonely full-width block, because
    four charts of a section are four of one thing.
    """
    spans: list[int] = []
    run: list[int] = []

    def flush() -> None:
        if not run:
            return
        for chunk in _chunks(len(run)):
            spans.extend([COLUMNS // chunk] * chunk)
        run.clear()

    for solo in full_width:
        if solo:
            flush()
            spans.append(COLUMNS)
        else:
            run.append(1)
    flush()
    return spans


def _chunks(count: int) -> list[int]:
    """How a run of *n* flexible blocks divides into rows."""
    if count <= MAX_PER_ROW:
        return [count]
    if count == 4:
        return [2, 2]
    rows: list[int] = []
    remaining = count
    while remaining > MAX_PER_ROW:
        rows.append(MAX_PER_ROW)
        remaining -= MAX_PER_ROW
    rows.append(remaining)
    return rows


#: How the KPI strip divides. Three across, four across, and five or six over two
#: rows — the same twelve, and the reason six is the ceiling: a seventh box would
#: be a third row of a strip that is meant to be read in one glance.
def kpi_spans(count: int) -> list[int]:
    if count <= 0:
        return []
    if count == 1:
        return [COLUMNS]
    if count == 2:
        return [6, 6]
    if count == 3:
        return [4, 4, 4]
    if count == 4:
        return [3, 3, 3, 3]
    if count == 5:
        return [4, 4, 4, 6, 6]
    return [4, 4, 4, 4, 4, 4]


__all__ = ["COLUMNS", "MAX_PER_ROW", "Placed", "assign", "kpi_spans", "natural_spans"]
