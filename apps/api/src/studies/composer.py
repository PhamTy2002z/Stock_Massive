"""Which picture a frame wants to be, decided from the numbers rather than asked.

A model that names a widget is guessing at a rendering from a summary it was
handed; the frame itself says what it is. Sixty rows against a date column is a
line whatever anybody calls it, and four symbols against six metrics is a
comparison. So the rule is a table in code — deterministic, testable against
fixtures chased out of the real store — and the model's suggestion is a *hint*
that survives only where it does not contradict what the numbers are.

**Two directions of override, and they are not symmetrical.** A hint that names
a widget the frame's kind admits is kept, because a model that has read the
question knows things the shape does not — that these eight quarters are meant
to be compared rather than followed. A hint that breaks a perception rule is
replaced and the replacement is recorded (``upgraded_from``): a pie of eleven
slices is unreadable no matter what the question was, and a plain table where a
series belongs is a model declining to draw.

The rules themselves come from the same place every other charting rule does —
position beats angle beats area for judging quantity — which is why the parts of
a whole stop being a donut at five and a comparison stops being bars at four
symbols.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from . import format, grammar, layout, widgets
from .contracts import (
    FRAME_SOURCES,
    PLAIN_ROLES,
    BoardBlock,
    BoardSection,
    CaptionBlock,
    FrameSource,
    KpiCell,
    ResolvedValue,
    VisualBlock,
)

#: Past this many slices a donut is a legend a reader matches swatches against.
MAX_DONUT_PARTS = 5

#: How many symbols and how many metrics a grouped bar chart can carry beside a
#: comparison table. Past either, the bars are thinner than the gaps between them
#: and the table is the honest picture on its own.
MAX_GROUPED_ENTITIES = 4
MAX_GROUPED_METRICS = 6

#: How many points a grouped bar may carry on a time axis before the eye wants a
#: line instead.
MAX_GROUPED_POINTS = 12

#: Column names that mean "this axis is time". Names rather than value sniffing
#: for the first pass, because a quarter is spelled ``2025Q3`` and a session is a
#: date, and both are strings a parser would have to be taught separately.
#:
#: ``bucket`` is deliberately **not** here, and the reason is the intraday
#: liquidity profile: its buckets are ``09:15``, ``10:00``, ``11:00`` — times, and
#: not an axis. Seventeen windows of one session are groups being compared, which
#: is why the Study that has drawn them since the beginning draws bars. A rule
#: that read the word rather than the axis would have replaced a picture that
#: works with one that implies a continuum between 11:30 and 13:00 where the
#: market is shut.
_TIME_NAMES = frozenset(
    {
        "session",
        "sessions",
        "date",
        "day",
        "trading_day",
        "tradingday",
        "period",
        "quarter",
        "month",
        "year",
    }
)

#: Column names that mean "this axis is a company".
_ENTITY_NAMES = frozenset({"symbol", "symbols", "ticker", "code", "ma"})

#: Column names that mean "this column is a share of a whole".
_SHARE_NAMES = frozenset({"share", "weight", "pct_of_total", "proportion", "ratio_of"})

#: The column a condition list is recognised by. The one Study that draws one
#: writes it, and a frame carrying it is asking for the checklist whatever else
#: it holds.
_CHECKLIST_COLUMN = "status"

_TICKER = re.compile(r"^[A-Z]{3}$")

#: How close to a hundred a column of percentages has to sum before it is read as
#: parts of one whole. Wide because the parts of a real distribution are rounded
#: and a bucket or two is often folded into "other".
_WHOLE_TOLERANCE = 3.0


@dataclass(frozen=True)
class Shape:
    """What a frame is, in the terms the widget rule is written in."""

    kind: str
    rows: int
    label_column: str | None
    numeric_columns: tuple[str, ...]
    time_axis: bool
    entity_axis: bool
    part_of_whole: bool
    checklist: bool

    @property
    def single_row(self) -> bool:
        return self.rows == 1


def shape_of(frame: Mapping[str, Any]) -> Shape:
    """Read one frame payload for the four questions the widget rule asks."""
    kind = str(frame.get("kind") or "table")
    columns = [str(name) for name in (frame.get("columns") or ())]
    rows: Sequence[Sequence[Any]] = [
        list(row) for row in (frame.get("rows") or ())
    ]
    unit = frame.get("unit")

    numeric: list[str] = []
    for position, name in enumerate(columns):
        if _numeric_column(rows, position):
            numeric.append(name)
    label = next((name for name in columns if name not in numeric), None)
    if label is None and columns:
        label = columns[0]

    first = columns[0].lower() if columns else ""
    time_axis = first in _TIME_NAMES or _looks_like_time(rows, 0)
    entity_axis = first in _ENTITY_NAMES or _looks_like_tickers(rows, 0)

    return Shape(
        kind=kind,
        rows=len(rows),
        label_column=label,
        numeric_columns=tuple(numeric),
        time_axis=time_axis,
        entity_axis=entity_axis and not time_axis,
        part_of_whole=_part_of_whole(columns, rows, numeric, unit),
        checklist=_CHECKLIST_COLUMN in columns,
    )


def _numeric_column(rows: Sequence[Sequence[Any]], position: int) -> bool:
    """Whether a column holds numbers, ignoring the cells that hold nothing.

    A refused cell is ``None`` and says nothing about the column's type; a column
    that is *entirely* refused is not numeric, because nothing in it can be drawn
    and calling it a measure would put an empty axis on the page.
    """
    seen = False
    for row in rows:
        if position >= len(row):
            continue
        value = row[position]
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        seen = True
    return seen


def _looks_like_time(rows: Sequence[Sequence[Any]], position: int) -> bool:
    for row in rows[:4]:
        if position >= len(row):
            return False
        text = str(row[position])
        if not re.match(r"^\d{4}[-/Qq]", text):
            return False
    return bool(rows)


def _looks_like_tickers(rows: Sequence[Sequence[Any]], position: int) -> bool:
    for row in rows[:4]:
        if position >= len(row) or not _TICKER.match(str(row[position])):
            return False
    return bool(rows)


def _part_of_whole(
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    numeric: Sequence[str],
    unit: Any,
) -> bool:
    """Whether one column of this frame is the parts of a single whole.

    Named *or* measured. A column called ``share`` says so; a column of
    percentages that adds to roughly a hundred is saying so without the name,
    and that second case is most of the real ones — a volume-at-price profile
    calls its column ``share`` and a sector breakdown calls it ``pct``.
    """
    for name in numeric:
        if name.lower() in _SHARE_NAMES or "share" in name.lower():
            return True
    if unit != "%":
        return False
    for name in numeric:
        position = list(columns).index(name)
        total = 0.0
        for row in rows:
            if position < len(row) and isinstance(row[position], (int, float)):
                total += float(row[position])
        if abs(total - 100.0) <= _WHOLE_TOLERANCE:
            return True
    return False


@dataclass(frozen=True)
class Choice:
    """The widget to draw, and what happened to the model's suggestion."""

    widget: str
    #: What the model asked for, when the server drew something else instead.
    upgraded_from: str | None = None
    #: Why this is a table rather than a picture, when no rule matched.
    downgraded: str | None = None
    #: A second picture the same frame earns. A comparison is a table *and* the
    #: bars beside it: the table is where a reader checks a number and the bars
    #: are where they see the gap, and neither one does the other's job.
    companion: str | None = None


def infer_widget(frame: Mapping[str, Any], hint: str | None = None) -> Choice:
    """The picture this frame wants, with the model's hint honoured where it can be."""
    shape = shape_of(frame)
    chosen = _from_shape(shape)

    if hint is None or hint == chosen.widget:
        return chosen
    if not widgets.known(hint, _newest(hint) or 0):
        return chosen
    version = _newest(hint)
    if version is None or not widgets.accepts(hint, version, shape.kind):  # type: ignore[arg-type]
        return Choice(
            widget=chosen.widget,
            upgraded_from=hint,
            downgraded=chosen.downgraded,
            companion=chosen.companion,
        )
    broken = _perception_rule_broken(hint, shape)
    if broken is not None:
        return Choice(
            widget=chosen.widget,
            upgraded_from=hint,
            downgraded=chosen.downgraded,
            companion=chosen.companion,
        )
    # The hint stands. The companion travels with it, because a comparison
    # earns its bars whichever of the pair the model happened to name.
    return Choice(widget=hint, companion=chosen.companion if hint != chosen.companion else None)


def _perception_rule_broken(widget: str, shape: Shape) -> str | None:
    """Why this widget cannot honestly draw this frame, or ``None``."""
    if widget == "donut" and shape.rows > MAX_DONUT_PARTS:
        return f"a donut of {shape.rows} slices is a legend, not a picture"
    if widget == "data_table":
        return "a table is the appendix's job"
    if widget == "grouped_bar" and shape.time_axis and shape.rows > MAX_GROUPED_POINTS:
        return f"{shape.rows} points on a time axis read as a line"
    return None


def _from_shape(shape: Shape) -> Choice:
    """The rule table, in the order the plan wrote it."""
    if shape.checklist:
        return Choice(widget="condition_checklist")
    if shape.kind == "matrix":
        return Choice(widget="session_heatmap")
    if shape.kind == "series":
        if shape.time_axis:
            if len(shape.numeric_columns) <= 2:
                return Choice(widget="line_series")
            if shape.rows <= MAX_GROUPED_POINTS:
                return Choice(widget="grouped_bar")
            return Choice(
                widget="line_series",
                downgraded=(
                    f"{len(shape.numeric_columns)} measures over {shape.rows} points; "
                    "the first two are drawn and the rest are in the table"
                ),
            )
        # A categorical series is bars whatever its length. A ranking would be
        # the honest alternative and it draws tables only, so reaching for it
        # here would fall straight back to the plain table it exists to avoid —
        # and a price ladder of twenty levels is bars in every Study that has
        # ever drawn one.
        return Choice(widget="bar_series")
    # table
    if shape.single_row:
        return Choice(widget="stat_tiles")
    if shape.entity_axis and len(shape.numeric_columns) >= 2:
        companion = (
            "grouped_bar"
            if shape.rows <= MAX_GROUPED_ENTITIES
            and len(shape.numeric_columns) <= MAX_GROUPED_METRICS
            else None
        )
        return Choice(widget="comparison_table", companion=companion)
    if shape.part_of_whole:
        if shape.rows <= MAX_DONUT_PARTS:
            return Choice(widget="donut")
        return Choice(widget="ranked_bars")
    if len(shape.numeric_columns) >= 2 and shape.label_column is not None:
        return Choice(widget="scatter_quadrant")
    if len(shape.numeric_columns) == 1 and shape.label_column is not None:
        return Choice(widget="ranked_bars")
    return Choice(
        widget="data_table",
        downgraded="no rule matches the shape of this frame, so the numbers are shown",
    )


def _newest(widget: str) -> int | None:
    versions = [version for name, version in widgets.CATALOG if name == widget]
    return max(versions) if versions else None


#: Widgets that are always the full width of the grid. A comparison read at half
#: width is a comparison with its metrics cut off, and a heatmap at half width is
#: a row of grey.
FULL_WIDTH: frozenset[str] = frozenset(
    {"comparison_table", "session_heatmap", "data_table", "waterfall"}
)


def presentation(widget: str, frame: Mapping[str, Any], columns: Sequence[str] = ()) -> dict[str, Any]:
    """Which column a widget draws from, decided by the layer that knows.

    ``columns`` is the model's own narrowing — "these three metrics of the
    fourteen" — and it is applied here rather than by cutting the frame, because
    the frame is the evidence and a reader opening the table under a chart is
    owed all of it.
    """
    shape = shape_of(frame)
    names = [str(name) for name in (frame.get("columns") or ())]
    picked = [name for name in columns if name in names] or None
    numeric = [name for name in shape.numeric_columns if picked is None or name in picked]
    label = shape.label_column or (names[0] if names else "")

    if widget in {"line_series", "bar_series"}:
        options: dict[str, Any] = {"x": label, "y": numeric[0] if numeric else ""}
        if len(numeric) > 1:
            options["secondary"] = numeric[1]
        return options
    if widget == "grouped_bar":
        return {"category": label, "series": numeric[:MAX_GROUPED_METRICS]}
    if widget == "comparison_table":
        return {"entity": label, "metrics": numeric[:MAX_GROUPED_METRICS]}
    if widget == "donut":
        return {"label": label, "value": numeric[0] if numeric else ""}
    if widget == "waterfall":
        return {"label": label, "value": numeric[0] if numeric else ""}
    if widget == "bullet":
        return {
            "label": label,
            "value": numeric[0] if numeric else "",
            "benchmark": numeric[1] if len(numeric) > 1 else None,
        }
    if widget == "ranked_bars":
        return {"label": label, "value": numeric[0] if numeric else ""}
    if widget == "scatter_quadrant":
        return {
            "label": label,
            "x": numeric[0] if numeric else "",
            "y": numeric[1] if len(numeric) > 1 else (numeric[0] if numeric else ""),
        }
    if widget == "stat_tiles":
        return {"label": label, "value": numeric[0] if numeric else ""}
    if widget == "session_heatmap":
        return {"rowKey": label}
    return {}


# -- compiling a board -----------------------------------------------------
#
# Every decision between "the model wrote a board" and "a row is stored" lives
# here rather than in the tool that receives the board, because a template runs
# the same road with no model on it. One compiler, one set of spans, one rule
# for what a figure reads as — a second copy in the tool layer would agree with
# this one until the day somebody fixed a span in only one of them.


#: How many notes about method one board's strip carries. Six, the same ceiling
#: one frame answers to (``compute/frames_io.MAX_METHOD_NOTES``) and for the same
#: reason: past this the strip is a paragraph.
MAX_MERGED_NOTES = 6


@dataclass(frozen=True)
class Compiled:
    """A board with every decision made: widgets, spans, and figures resolved.

    Produced in one pass because the passes are not independent. Which widget a
    frame gets decides whether it takes the whole row, which decides every other
    block's span in that section; and a KPI is only resolvable once the frame it
    names is in hand under the key the spec will file it under.
    """

    frames: dict[str, Mapping[str, Any]]
    kpis: tuple[KpiCell, ...]
    sections: tuple[BoardSection, ...]
    appendix: VisualBlock | None
    shapes: tuple[Shape, ...]


def newest_version(widget: str) -> int | None:
    """The highest version of one widget the catalog holds, or ``None``.

    The server picks, not the model: a version is how an artifact written last
    month keeps rendering, and it is a fact about the drawing rather than about
    the question. A model naming one would be a model pinning a viewer.
    """
    versions = [version for name, version in widgets.CATALOG if name == widget]
    return max(versions) if versions else None


def source_of(provenance: Mapping[str, Any]) -> FrameSource:
    """Which of the three a block's numbers are, defaulting to this store's own.

    Read off the frame's own provenance rather than off the board's, because a
    board is allowed to mix them — a comparison of what the store measured
    against what a filing said is exactly the question this track exists for —
    and the badge is per block for that reason.
    """
    source = str(provenance.get("source") or "store")
    return source if source in FRAME_SOURCES else "store"  # type: ignore[return-value]


def compile_board(
    board: grammar.Board,
    payloads: Mapping[str, Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
) -> Compiled:
    """Turn a validated board into the spec that is stored and drawn.

    Runs even when the board has violations, because the archetype check and the
    lint score are questions about the *compiled* board — which pictures it
    actually holds — and asking them of the model's suggestions would score a
    board nobody would have seen.
    """
    keys: dict[str, str] = {}
    frames: dict[str, Mapping[str, Any]] = {}

    def key_for(reference: str) -> str | None:
        if reference not in payloads:
            return None
        if reference not in keys:
            keys[reference] = f"f{len(frames)}"
            frames[keys[reference]] = payloads[reference]
        return keys[reference]

    shapes: list[Shape] = []
    drawn: list[str] = []
    sections: list[BoardSection] = []

    for section in board.sections:
        # One entry per block the compiled section will hold, which is not one
        # per block the model wrote: a comparison earns the bars beside it, and
        # the server adds them here rather than making the model ask for the
        # same frame twice — which its own grammar would then refuse as a frame
        # drawn twice.
        planned: list[tuple[grammar.Block, str | None, Choice | None]] = []
        for block in section.blocks:
            if not isinstance(block, grammar.Visual) or block.frame_id not in payloads:
                planned.append((block, None, None))
                continue
            payload = payloads[block.frame_id]
            choice = infer_widget(payload, block.widget)
            shapes.append(shape_of(payload))
            drawn.append(choice.widget)
            planned.append((block, choice.widget, choice))
            room = (
                len(planned) < grammar.MAX_BLOCKS_PER_SECTION
                and len(drawn) < grammar.MAX_VISUALS
            )
            if choice.companion is not None and room:
                drawn.append(choice.companion)
                planned.append((block, choice.companion, choice))

        solo = [
            # A caption is a line of prose under a picture; it never shares a row.
            widget is None or widget in FULL_WIDTH
            for _block, widget, _choice in planned
        ]
        placed = layout.assign(layout.natural_spans(solo))

        blocks: list[BoardBlock] = []
        for index, (block, widget, choice) in enumerate(planned):
            span = placed[index].span
            if widget is not None and isinstance(block, grammar.Visual):
                key = key_for(block.frame_id)
                if key is None:
                    continue
                payload = payloads[block.frame_id]
                primary = choice is not None and widget == choice.widget
                blocks.append(
                    VisualBlock(
                        widget=widget,
                        widget_version=newest_version(widget) or 1,
                        frame=key,
                        options=presentation(widget, payload, block.columns),
                        span=span,
                        source=source_of(sources.get(block.frame_id, {})),
                        upgraded_from=choice.upgraded_from if primary else None,
                        downgraded=choice.downgraded if primary else None,
                    )
                )
                continue
            if isinstance(block, grammar.Caption):
                caption = _caption(block, payloads, key_for, span)
                if caption is not None:
                    blocks.append(caption)
        if blocks:
            sections.append(BoardSection(heading=section.heading, blocks=tuple(blocks)))

    kpis = _kpi_cells(board, payloads, key_for)

    appendix: VisualBlock | None = None
    if board.appendix_frame_id is not None:
        key = key_for(board.appendix_frame_id)
        if key is not None:
            appendix = VisualBlock(
                widget=widgets.FALLBACK_WIDGET[0],
                widget_version=widgets.FALLBACK_WIDGET[1],
                frame=key,
                options={},
                span=layout.COLUMNS,
                source=source_of(sources.get(board.appendix_frame_id, {})),
            )

    return Compiled(
        frames=frames,
        kpis=kpis,
        sections=tuple(sections),
        appendix=appendix,
        shapes=tuple(shapes),
    )


def _kpi_cells(
    board: grammar.Board,
    payloads: Mapping[str, Mapping[str, Any]],
    key_for: Callable[[str], str | None],
) -> tuple[KpiCell, ...]:
    spans = layout.kpi_spans(len(board.kpis))
    out: list[KpiCell] = []
    for index, kpi in enumerate(board.kpis):
        value = resolve(kpi.value, payloads, key_for)
        if value is None:
            continue
        delta = None if kpi.delta is None else resolve(kpi.delta, payloads, key_for)
        out.append(
            KpiCell(
                label=kpi.label,
                value=value,
                delta=delta,
                role=kpi.role if kpi.role in PLAIN_ROLES else None,
                span=spans[index],
            )
        )
    return tuple(out)


def _caption(
    block: grammar.Caption,
    payloads: Mapping[str, Mapping[str, Any]],
    key_for: Callable[[str], str | None],
    span: int,
) -> CaptionBlock | None:
    """One caption with every hole filled, or ``None`` when a hole cannot be.

    A caption missing one of its figures is a sentence with a brace in it, which
    is worse than no caption: the reader sees the machinery. The grammar has
    already refused this board, so dropping the block here only decides what the
    lint score is measured against.
    """
    resolved: dict[str, ResolvedValue] = {}
    for key, ref in block.refs.items():
        value = resolve(ref, payloads, key_for)
        if value is None:
            return None
        resolved[key] = value
    text = block.template
    for key, value in resolved.items():
        text = text.replace(f"{{{key}}}", value.text)
    if "{" in text and "}" in text:
        return None
    return CaptionBlock(
        template=block.template, text=text, refs=resolved, span=span
    )


def resolve(
    ref: grammar.Ref,
    payloads: Mapping[str, Mapping[str, Any]],
    key_for: Callable[[str], str | None],
) -> ResolvedValue | None:
    """One reference as the figure it names, formatted, or ``None``.

    Formatted here and stored formatted, so re-opening a board a month later
    draws the string that was written rather than re-deriving one against a
    browser that has since learned a different rule for ``tỷ``.
    """
    payload = payloads.get(ref.frame_id)
    if payload is None:
        return None
    key = key_for(ref.frame_id)
    if key is None:
        return None
    columns = [str(name) for name in (payload.get("columns") or ())]
    if ref.column not in columns:
        return None
    index = grammar.row_index(ref, payload)
    if index is None:
        return None
    rows = payload.get("rows") or ()
    row = list(rows[index])
    position = columns.index(ref.column)
    if position >= len(row):
        return None
    value = row[position]
    return ResolvedValue(
        text=format.number(value, payload.get("unit")),
        raw=value,
        unit=payload.get("unit"),
        frame=key,
        row=index,
        column=ref.column,
    )


def merged_provenance(sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """One claim over several frames: the oldest as-of, the worst health.

    Both in the pessimistic direction, because a strip is read as a statement
    about the whole panel: a Signal Desk holding one week-old frame is a week-old
    signal_desk, and one holding a degraded frame is not a healthy one.

    **The session count is taken from the frames that read the store, and from
    those only.** A derived frame's ``sessionsUsed`` is its own row count — which
    is the honest answer for a calculation and is not a number of sessions at
    all. Maxed across every frame it made a one-session ladder of twenty-four
    rungs report twenty-four sessions, and a thirty-session profile report four
    hundred and eighty: a figure on the strip that was wrong by an order of
    magnitude and read as a claim about how much history the picture rests on.
    A board with nothing but derived frames falls back to the maximum, because
    then the row count is the only count there is.
    """
    order = {"normal": 0, "degraded": 1, "unavailable": 2}
    health = "normal"
    as_of = ""
    read_sessions = 0
    any_sessions = 0
    read_any = False
    reasons: list[str] = []
    notes: list[str] = []
    for source in sources:
        candidate = str(source.get("health") or "normal")
        if order.get(candidate, 0) > order.get(health, 0):
            health = candidate
        stamp = str(source.get("asOf") or "")
        if stamp and (not as_of or stamp < as_of):
            as_of = stamp
        used = source.get("sessionsUsed")
        if isinstance(used, int):
            any_sessions = max(any_sessions, used)
            if str(source.get("source") or "store") != "derived":
                read_any = True
                read_sessions = max(read_sessions, used)
        reason = source.get("reason")
        if isinstance(reason, str) and reason:
            reasons.append(reason)
        for note in source.get("methodNotes") or ():
            if isinstance(note, str) and note:
                notes.append(note)
    # The strip under a panel holds one sentence, and every frame's reason is
    # already one. The first distinct reason takes the strip; the others are
    # limitations of the same picture, so they travel as method notes rather
    # than being glued into a paragraph the strip would have to cut.
    distinct = list(dict.fromkeys(reasons))
    return {
        "source": "store",
        "asOf": as_of,
        "sessionsUsed": read_sessions if read_any else any_sessions,
        "health": health,
        "reason": distinct[0] if distinct else None,
        # Capped for the reason one frame's notes are: a plan of ten steps brings
        # ten engine-written lines about digests and declared assumptions, and a
        # reader checking whether the numbers are thin stops reading a page.
        # Order is step order, so a template's own notes lead and the engine's
        # are what a cap drops.
        "methodNotes": list(dict.fromkeys(distinct[1:] + notes))[:MAX_MERGED_NOTES],
    }


__all__ = [
    "Choice",
    "Compiled",
    "FULL_WIDTH",
    "MAX_DONUT_PARTS",
    "MAX_GROUPED_ENTITIES",
    "MAX_GROUPED_METRICS",
    "MAX_GROUPED_POINTS",
    "Shape",
    "compile_board",
    "infer_widget",
    "merged_provenance",
    "newest_version",
    "presentation",
    "resolve",
    "shape_of",
    "source_of",
]
