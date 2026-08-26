"""Which fifteen-minute buckets are a Vietnamese trading session, and which are padding.

The provider answers an intraday request on a **twenty-four hour grid**: ninety-six
buckets a day, every one of them present, the ones outside trading hours carrying
``NaN`` prices and a volume of zero (OBSERVED 2026-08-26, ``Quote(source="VCI")``).
A statistic taken over that grid is diluted five and a half times over, and a
"quiet bucket" at four in the morning is not quiet — it does not exist.

So the grid below is a **closed set, measured rather than assumed**. Over 75
sessions of STB (HOSE) and 70 of SHS (HNX), exactly these bucket starts ever
carried volume:

* ``09:00`` — HNX and UPCoM open continuous trading here. HOSE does not: its
  opening call auction (ATO) runs 09:00–09:15 and the provider stamps the matched
  volume into the ``09:15`` bucket. So a HOSE symbol has no ``09:00`` row at all,
  and its ``09:15`` row is the auction plus the first minutes of continuous trade.
  Both facts are load-bearing for anyone reading ``ato`` in a phase summary.
* ``09:15`` … ``11:15`` — the morning. ``11:15`` is the last one; ``11:30`` is the
  bell, and its bucket is empty on every session observed.
* ``13:00`` … ``14:15`` — the afternoon. Continuous trading stops at 14:30, so
  ``14:15`` is the last continuous bucket.
* ``14:45`` — the closing call auction (ATC). This is the correction that matters
  most: the auction *runs* 14:30–14:45, and the plan for this phase said to label
  ``14:30`` as ATC. But nothing matches until the close, so the ``14:30`` bucket is
  empty on every session observed and the entire ATC volume — the largest single
  bucket of the day for most symbols — arrives stamped ``14:45``. A window written
  from the auction's clock rather than from the data would have discarded it.

Lunch (``11:30``–``12:45``), the ``14:30`` hole, and everything before 09:00 or
after 14:45 are dropped before anything is written, so no consumer has to know
they existed.

Pure: no I/O, no clock, no session. Everything here is a function of a timestamp.
"""

from __future__ import annotations

from datetime import time
from typing import Literal, Mapping
from types import MappingProxyType

#: The four parts of a session a bucket can belong to. ``ato`` and ``atc`` are
#: call auctions — one price, everyone at once — and ``am``/``pm`` are continuous
#: trading. Keeping them apart matters because auction volume answers a different
#: question from continuous volume: it is where a participant who must trade goes,
#: not where one who is choosing goes.
Phase = Literal["ato", "am", "pm", "atc"]

BUCKET_MINUTES = 15

#: Bucket start → phase, and the whole of it. A time that is not a key here is
#: not part of a session, whatever the provider sent for it.
SESSION_GRID: Mapping[time, Phase] = MappingProxyType(
    {
        time(9, 0): "ato",
        time(9, 15): "am",
        time(9, 30): "am",
        time(9, 45): "am",
        time(10, 0): "am",
        time(10, 15): "am",
        time(10, 30): "am",
        time(10, 45): "am",
        time(11, 0): "am",
        time(11, 15): "am",
        time(13, 0): "pm",
        time(13, 15): "pm",
        time(13, 30): "pm",
        time(13, 45): "pm",
        time(14, 0): "pm",
        time(14, 15): "pm",
        time(14, 45): "atc",
    }
)

#: The bucket starts in the order a session runs, for anyone aligning columns.
#: A heatmap has to place every session against the same axis or the picture is
#: a shuffle, and a symbol missing a bucket has to leave a hole rather than shift
#: its neighbours left.
SESSION_BUCKETS: tuple[time, ...] = tuple(sorted(SESSION_GRID))

#: What a bucket is called on screen. The start rather than a range, because a
#: range is twice the width for the same information and every bucket is
#: fifteen minutes wide.
def label_of(moment: time) -> str:
    return f"{moment.hour:02d}:{moment.minute:02d}"


SESSION_BUCKET_LABELS: tuple[str, ...] = tuple(
    label_of(moment) for moment in SESSION_BUCKETS
)


def phase_of(moment: time) -> Phase | None:
    """The phase this bucket start belongs to, or ``None`` if it is padding."""
    return SESSION_GRID.get(moment.replace(second=0, microsecond=0))


def in_session(moment: time) -> bool:
    return phase_of(moment) is not None


__all__ = [
    "BUCKET_MINUTES",
    "Phase",
    "SESSION_BUCKETS",
    "SESSION_BUCKET_LABELS",
    "SESSION_GRID",
    "in_session",
    "label_of",
    "phase_of",
]
