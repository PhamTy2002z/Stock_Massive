"""The one visual a Signal Desk Turn can leave behind, assembled by the host.

Nothing in this module comes from the model. It reads the market calls the Turn
actually made, checks that the ledger admitted the figures they returned, and
writes a chart input whose every value is a field of a named call. The model
never sees this file's output and never contributes a number to it, so the
question "did the model invent this price" has no way to be asked.

**Why the shape is decided here rather than proposed.** There is one dataset
and one chart family, and both are fixed by what ``get_market_data`` returns:
one symbol's bars means candles, several symbols' closes means lines. A model
pass that chose between two answers a table already gives would be a round of
tokens spent to reach a conclusion this function reaches for free — and it
would open a payload the host would then have to refuse numbers out of. When a
third dataset arrives and the shape stops following from the call, the model
picks the *kind* and this module keeps the data.

**Two assemblies, not one.** The pinned Flint candlestick template has no
volume channel (``components/signal-desk/flint-contract.test.ts`` asserts it),
so price and volume are two chart inputs stacked in the pane. Merging them
would mean editing what Flint compiled, which the plan forbids outright.

**Flint validates nothing.** The same contract test proves it: a missing
channel returns an option with no series, and an encoding naming a column no
row has returns a chart that renders nonsense. So every refusal a bad input
deserves is made here, before the payload is persisted — and a refusal is the
absence of the part rather than a part carrying an error, because the reason a
Turn has no chart is already written in the ledger's gaps.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from .evidence.contracts import ClaimLedger, VerificationVerdict
from .evidence.pipeline import MARKET_TOOL, evidence_from_calls
from .messages import ToolCallStatus, TurnToolCall
from .tools.market_data import MAX_ROWS as MARKET_MAX_ROWS

#: The payload's own version. Bumped when a reader written against version 1
#: would misread version 2 — not when a field is added that older readers ignore.
VERSION = 1

#: Which browser-side runtime turns the assembly into pixels. Written down so a
#: persisted part from a build with a different renderer is recognisably not
#: this one rather than silently handed to the wrong compiler.
RENDERER = "flint-echarts"

#: The Flint release this assembly was written for, exact. It has to match the
#: pin in ``apps/web/package.json``; ``tests/test_agent_visual.py`` reads both.
FLINT_VERSION = "0.5.1"

#: The chart templates this module may name. Two, because two are what the two
#: shapes below need, and an unknown type is the one input Flint does throw on.
CANDLESTICK = "Candlestick Chart"
BAR = "Bar Chart"
LINE = "Line Chart"

#: The pane's usable width and the heights a stacked pair gets, as the contract
#: test measured them. Flint needs a base size; the panel scales what it gets.
PANE_WIDTH = 420
CANDLE_HEIGHT = 260
#: The volume panel is short, but not as short as it reads: Flint reserves the
#: axis area out of the height it is given, and 36px of header plus 61px of
#: category axis left a 110px chart with 13px of bars in it. This is that
#: reservation plus a band the eye can actually compare.
VOLUME_HEIGHT = 190
LINE_HEIGHT = 300

#: The caps. This is the trust boundary to a browser, so each one is a refusal
#: and not a truncation: a chart drawn from half a series is a wrong chart,
#: where a missing chart is an honest one the ledger already explains.
MAX_SERIES = 4
MAX_ROWS_PER_SERIES = MARKET_MAX_ROWS
MAX_POINTS = 1_000
MAX_LABEL_CHARS = 120
MAX_BYTES = 96_000

#: The verdicts that admit a market figure into a chart. ``SINGLE_SOURCE`` is
#: the *expected* one and not a concession: the rows came from a securities
#: company's feed, so ``SourceClass.STORE`` stays outside the primary set and a
#: market-only material claim settles here by design (Phase 3). What is refused
#: is a figure the ledger could not support at all or could not place in time.
ADMITTED_VERDICTS = frozenset(
    {VerificationVerdict.VERIFIED, VerificationVerdict.SINGLE_SOURCE}
)

#: The columns the assembled rows carry, by the names the encodings use.
#:
#: They are English words rather than opaque field names because Flint titles
#: an axis with the name of the column encoded on it. ``time`` and ``volume``
#: were reaching the reader as the axis titles of a chart in the pane, and
#: renaming a column is host input rather than a change to what the package
#: compiled. The webapp UI is English (owner decision 2026-09-27), so the
#: labels drawn on the axes are English regardless of the answer's language.
_TIME = "Session"
_SYMBOL = "Symbol"
_OPEN = "Open"
_HIGH = "High"
_LOW = "Low"
_CLOSE = "Close"
_VOLUME = "Volume"

#: How a bar's close is written on the category axis, shortest form first.
#:
#: Not a cosmetic choice. Flint measures the *raw* value to decide whether the
#: labels fit, and a full ISO instant is 25 characters: the bar template turned
#: them on their side and reserved 151px of margin under a 110px chart, which
#: is the volume panel being mostly axis. A five-character label removes the
#: reservation and is also the form a reader here expects.
#:
#: The first format that keeps every label distinct wins, because two rows
#: sharing a category label are one column on the axis: a fortnight of
#: quarter-hour bars written as ``09:15`` would draw one day on top of another.
LABEL_FORMATS: Mapping[str, tuple[str, ...]] = {
    "1D": ("%d/%m", "%d/%m/%y"),
    "15m": ("%H:%M", "%d/%m %H:%M"),
}

#: Which market field each chart column carries. Public because the release
#: grader checks that every drawn value was read, and it can only do that if it
#: knows which column holds which figure — a second copy of this map there would
#: pass the day the two disagreed.
COLUMNS: Mapping[str, str] = {
    "bar_closed_at": _TIME,
    "open": _OPEN,
    "high": _HIGH,
    "low": _LOW,
    "close": _CLOSE,
    "volume": _VOLUME,
    "symbol": _SYMBOL,
}


def build_visual(
    *,
    calls: Sequence[TurnToolCall],
    ledger: ClaimLedger | None,
    as_of: datetime,
) -> dict[str, Any] | None:
    """The visual part for this Turn, or ``None`` when it has not earned one.

    ``None`` is a first-class answer and by far the common one: a Turn that read
    no market data, whose figures the ledger refused, or whose calls do not add
    up to one comparable series has no chart to show, and says so by having no
    key rather than by carrying a status nobody can act on.
    """
    if ledger is None:
        return None
    reads = _market_reads(calls)
    if not reads or len(reads) > MAX_SERIES:
        return None
    admitted = _admitted_evidence_ids(ledger)
    # The figure check's ledger (an answer the deep pipeline could only take
    # from prose) names a market read by its feed, not by this module's id.
    cited_feeds = {row.source for row in ledger.evidence if row.evidence_id in admitted}
    if any(
        read["evidence_id"] not in admitted and read["feed"] not in cited_feeds
        for read in reads
    ):
        return None

    assemblies = _assemblies(reads)
    if assemblies is None:
        return None

    part = {
        "version": VERSION,
        "renderer": RENDERER,
        "flintVersion": FLINT_VERSION,
        "asOf": as_of.isoformat(),
        "title": _title(reads),
        "assemblies": assemblies,
        "evidenceIds": [read["evidence_id"] for read in reads],
        "sourceCallIds": [read["call_id"] for read in reads],
    }
    encoded = json.dumps(part, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        return None
    return part


def _market_reads(calls: Sequence[TurnToolCall]) -> list[dict[str, Any]]:
    """Every successful market call, with the evidence row it became.

    The evidence id is recomputed by running the call back through
    ``evidence_from_calls`` rather than by repeating its hash here. One call in,
    one row out: the id is derived from the payload, so this is the same string
    the ledger holds and there is no second formula to drift from the first.
    """
    reads: list[dict[str, Any]] = []
    # Two calls that returned the same rows are one series, not two. The model
    # re-reads a range it has already read often enough that leaving the repeat
    # in would cost the chart outright: two entries for one symbol fail the
    # comparability rule in ``_lines`` and the Turn ends with no visual at all.
    # ``evidence_from_calls`` collapses the same pair on the same id, so this is
    # the ledger's own notion of sameness rather than a second one.
    seen: set[str] = set()
    for call in calls:
        if call.name != MARKET_TOOL or call.status is not ToolCallStatus.OK:
            continue
        if not call.id:
            continue
        payload = _payload(call.result_text)
        if payload is None:
            continue
        refs = evidence_from_calls((call,))
        if len(refs) != 1:
            continue
        rows = payload.get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        if len(rows) > MAX_ROWS_PER_SERIES:
            continue
        symbol = str(payload.get("symbol") or "").strip()
        interval = str(payload.get("interval") or "").strip()
        unit = str(payload.get("price_unit") or "").strip()
        currency = str(payload.get("currency") or "").strip()
        if not symbol or not interval or not unit or not currency:
            continue
        if len(symbol) > MAX_LABEL_CHARS or len(interval) > MAX_LABEL_CHARS:
            continue
        if refs[0].evidence_id in seen:
            continue
        seen.add(refs[0].evidence_id)
        reads.append(
            {
                "call_id": call.id,
                "evidence_id": refs[0].evidence_id,
                # How the figure check names this feed (``grounding._structured``).
                "feed": f"{payload.get('source') or call.name}/{symbol}",
                "symbol": symbol,
                "interval": interval,
                "unit": unit,
                "currency": currency,
                "actual": payload.get("actual") if isinstance(payload.get("actual"), Mapping) else {},
                "rows": rows,
            }
        )
    # A follow-up read of the same symbol on the same interval — usually the
    # model topping up the most recent bars — is the same series again, not a
    # second one. Two entries for one symbol would fail the comparability rule
    # and cost the Turn its chart, so the widest read stands for the symbol.
    widest: dict[tuple[str, str], dict[str, Any]] = {}
    for read in reads:
        key = (read["symbol"], read["interval"])
        kept = widest.get(key)
        if kept is None or len(read["rows"]) > len(kept["rows"]):
            widest[key] = read
    return [read for read in reads if widest[(read["symbol"], read["interval"])] is read]


def _payload(result_text: str | None) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(result_text or "")
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _admitted_evidence_ids(ledger: ClaimLedger) -> frozenset[str]:
    """The evidence a validated claim actually rested on, and was allowed to.

    Read off the claims rather than off ``ledger.evidence``, because a row being
    present is not the same as it having survived: ``validate_claim_ledger``
    drops an id from a claim's support when the row is temporally inadmissible,
    and a chart built from figures no surviving claim could cite would be a
    picture of evidence the answer itself refused to use.
    """
    return frozenset(
        evidence_id
        for claim in ledger.claims
        if claim.verdict in ADMITTED_VERDICTS
        for evidence_id in claim.supporting_evidence_ids
    )


def _assemblies(reads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]] | None:
    """The chart inputs these calls add up to, or ``None`` if they add up to none."""
    if len(reads) == 1:
        return _candles(reads[0])
    return _lines(reads)


def _candles(read: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    """One symbol: candles over volume, as two inputs and two compiled options."""
    labels = _labels(read)
    if labels is None:
        return None
    values: list[dict[str, Any]] = []
    for label, row in zip(labels, read["rows"], strict=True):
        point = _ohlcv(row, label)
        if point is None:
            return None
        values.append(point)
    if len(values) > MAX_POINTS:
        return None
    return [
        _spec(
            CANDLESTICK,
            values,
            {
                "x": _TIME,
                "open": _OPEN,
                "high": _HIGH,
                "low": _LOW,
                "close": _CLOSE,
            },
            CANDLE_HEIGHT,
        ),
        _spec(BAR, values, {"x": _TIME, "y": _VOLUME}, VOLUME_HEIGHT),
    ]


def _lines(reads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]] | None:
    """Several symbols: closing prices on one scale, or nothing at all.

    Two series measured in different units or sampled at different intervals are
    not comparable, and a chart that drew them on one axis would be an argument
    the data does not make. There is no partial answer here: the whole visual is
    withheld and the ledger's gaps say why.
    """
    intervals = {read["interval"] for read in reads}
    units = {(read["unit"], read["currency"]) for read in reads}
    symbols = [read["symbol"] for read in reads]
    if len(intervals) != 1 or len(units) != 1 or len(set(symbols)) != len(symbols):
        return None
    values: list[dict[str, Any]] = []
    for read in reads:
        labels = _labels(read)
        if labels is None:
            return None
        for label, row in zip(labels, read["rows"], strict=True):
            point = _close(row, read["symbol"], label)
            if point is None:
                return None
            values.append(point)
    if len(values) > MAX_POINTS:
        return None
    return [
        _spec(
            LINE,
            values,
            {"x": _TIME, "y": _CLOSE, "color": _SYMBOL},
            LINE_HEIGHT,
        )
    ]


def _spec(
    chart_type: str,
    values: Sequence[Mapping[str, Any]],
    encodings: Mapping[str, str],
    height: int,
) -> dict[str, Any]:
    """One ``ChartAssemblyInput``, in exactly the shape the package documents."""
    return {
        "data": {"values": [dict(value) for value in values]},
        "chart_spec": {
            "chartType": chart_type,
            "encodings": dict(encodings),
            "baseSize": {"width": PANE_WIDTH, "height": height},
        },
    }


def _labels(read: Mapping[str, Any]) -> list[str] | None:
    """One category label per row, in the shortest form that stays unambiguous.

    ``None`` when a row carries no readable close, or when even the longest
    format leaves two rows sharing a label — a chart whose axis silently merges
    two bars is the kind of wrong picture this module refuses rather than draws.
    """
    stamps: list[datetime] = []
    for row in read["rows"]:
        if not isinstance(row, Mapping):
            return None
        try:
            stamps.append(datetime.fromisoformat(str(row.get("bar_closed_at") or "")))
        except (TypeError, ValueError):
            return None
    for pattern in LABEL_FORMATS.get(read["interval"], ()):
        labels = [stamp.strftime(pattern) for stamp in stamps]
        if len(set(labels)) == len(labels):
            return labels
    return None


def _ohlcv(row: Any, label: str) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    try:
        return {
            _TIME: label,
            _OPEN: int(row["open"]),
            _HIGH: int(row["high"]),
            _LOW: int(row["low"]),
            _CLOSE: int(row["close"]),
            _VOLUME: int(row["volume"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _close(row: Any, symbol: str, label: str) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    try:
        return {_TIME: label, _CLOSE: int(row["close"]), _SYMBOL: symbol}
    except (KeyError, TypeError, ValueError):
        return None


def _title(reads: Sequence[Mapping[str, Any]]) -> str:
    """What the panel puts above the chart: the symbols, the bar, the window.

    Composed from the call's own arguments rather than from anything a model
    wrote, for the same reason the values are: a caption is a claim about what
    is drawn, and this one can only ever say what was actually read.
    """
    symbols = " · ".join(read["symbol"] for read in reads)
    interval = reads[0]["interval"]
    actual = reads[0]["actual"] or {}
    start = str(actual.get("start") or "")
    end = str(actual.get("end") or "")
    window = f" · {start} → {end}" if start and end else ""
    return f"{symbols} · {interval}{window}"[: MAX_LABEL_CHARS * 2]


__all__ = [
    "ADMITTED_VERDICTS",
    "COLUMNS",
    "FLINT_VERSION",
    "LABEL_FORMATS",
    "MAX_BYTES",
    "MAX_POINTS",
    "MAX_ROWS_PER_SERIES",
    "MAX_SERIES",
    "RENDERER",
    "VERSION",
    "build_visual",
]
