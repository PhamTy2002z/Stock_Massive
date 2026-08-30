"""A board built from what the Turn gathered, when the model composed none.

Two ways a question ends with numbers and no picture. The model wrote a board
that broke the grammar twice, or it never reached for ``render_signal_desk`` at
all and answered in prose. In ``signal_desk`` mode both are the same failure to
the reader: they asked for an analysis surface and got a paragraph.

**So the server draws, and it says so.** ``autoComposed`` travels on the spec and
the panel prints one line under the header. A board nobody claims authorship of
is worse than no board — the reader would read the arrangement as an argument.

**The server does not write sentences.** No captions, ever. Choosing which two
numbers to put in one sentence *is* the analysis, and a system that did it here
would be answering the question in the layer that has no idea what was asked.
What it can do honestly is show every frame the Turn produced, drawn the way its
shape says it should be drawn, in the order they were made.

**And it does not choose which figures lead.** A KPI strip is a claim that these
three numbers are the answer. The strip is filled only from frames that are a
single row — a frame of one row is already somebody's summary, and reading its
cells is transcription rather than selection. A Turn with no such frame gets a
board with no strip, and the grammar's floor of three is waived for exactly this
case (``grammar.validate(..., authored=False)``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from . import composer, format, layout
from .contracts import (
    BoardSection,
    BoardSpec,
    FrameSource,
    KpiCell,
    ResolvedValue,
    VisualBlock,
)
from .grammar import MAX_BLOCKS_PER_SECTION, MAX_KPIS, MAX_VISUALS

#: What a board nobody titled is called. Deliberately about the data rather than
#: about the question: the server does not know what was asked.
DEFAULT_TITLE = "Số liệu đã tính"

#: What the section holding every drawn frame is called.
SECTION_HEADING = "Dữ liệu đã thu thập"


def compose(
    gathered: Sequence[tuple[str, Mapping[str, Any], Mapping[str, Any]]],
    *,
    title: str = DEFAULT_TITLE,
) -> tuple[BoardSpec, dict[str, Mapping[str, Any]]] | None:
    """A ``profile`` board over every frame this Turn made, or ``None`` for none.

    ``gathered`` is what :func:`frames_buffer.frames_in_turn` returns: the
    reference, the frame payload, the provenance the frame was made under.

    Comes back with the frames keyed the way the spec names them, so the caller
    writes one row holding both and nothing has to agree about the naming twice.
    """
    if not gathered:
        return None

    kpis = _kpis(gathered)
    gathered = [entry for entry in gathered if _is_drawable(entry[1])]
    if not gathered:
        return None
    drawn = [entry for entry in gathered if not _is_single_row(entry[1])]
    # A Turn whose only frame is one row is a Turn with a strip and nothing to
    # draw, and a board of nothing is not a board. Draw it as well as read it.
    if not drawn:
        drawn = list(gathered)
    drawn = drawn[:MAX_VISUALS]

    frames: dict[str, Mapping[str, Any]] = {}
    choices: list[tuple[str, composer.Choice, Mapping[str, Any], FrameSource]] = []
    for reference, payload, provenance in drawn:
        key = f"f{len(frames)}"
        frames[key] = payload
        choices.append(
            (key, composer.infer_widget(payload), payload, _source_of(provenance))
        )

    # Split into sections rather than piling every frame into one, because the
    # grammar caps a section at four blocks and a composed board that broke its
    # own rules would be a board the compiler could not have accepted from the
    # model. Eight visuals over two sections is exactly the ceiling.
    sections: list[BoardSection] = []
    for start in range(0, len(choices), MAX_BLOCKS_PER_SECTION):
        run = choices[start : start + MAX_BLOCKS_PER_SECTION]
        placed = layout.assign(
            layout.natural_spans(
                [choice.widget in composer.FULL_WIDTH for _key, choice, _p, _s in run]
            )
        )
        sections.append(
            BoardSection(
                heading=SECTION_HEADING if start == 0 else None,
                blocks=tuple(
                    VisualBlock(
                        widget=choice.widget,
                        widget_version=_version(choice.widget),
                        frame=key,
                        options=composer.presentation(choice.widget, payload),
                        span=placed[index].span,
                        source=source,
                        upgraded_from=choice.upgraded_from,
                        downgraded=choice.downgraded,
                    )
                    for index, (key, choice, payload, source) in enumerate(run)
                ),
            )
        )

    # Every KPI cell has to name a frame the board carries, because the spec is
    # read back with its own frames and nothing else. A single-row frame that is
    # not drawn is added to the row under its own key so its cells resolve.
    kpi_cells = _placed_kpis(kpis, frames, gathered)

    spec = BoardSpec(
        title=title,
        archetype="profile",
        kpis=kpi_cells,
        sections=tuple(sections),
        appendix=None,
        lint={},
        auto_composed=True,
    )
    return spec, frames


#: How tall a frame may be and still be a picture the server offers unasked.
#:
#: A template's plan files every step as an artifact, and some of those steps are
#: working frames rather than pictures — the market-wide screen reads 28.784
#: closes before it ranks anything. This function is what a Turn falls back on
#: when the model drew nothing, so it must not answer with a table of thirty
#: thousand rows: that is not a board, it is the intermediate the Study was on
#: its way through, and drawing it would also copy two megabytes into a second
#: row. Five hundred is the sandbox's own answer ceiling
#: (``compute/runner.MAX_RESULT_ROWS``) — past it, a calculation has stopped
#: being a picture there too.
MAX_DRAWABLE_ROWS = 500


def _is_drawable(frame: Mapping[str, Any]) -> bool:
    return len(frame.get("rows") or ()) <= MAX_DRAWABLE_ROWS


def _is_single_row(frame: Mapping[str, Any]) -> bool:
    return len(frame.get("rows") or ()) == 1


def _source_of(provenance: Mapping[str, Any]) -> FrameSource:
    source = str(provenance.get("source") or "store")
    return source if source in {"store", "web", "derived"} else "store"  # type: ignore[return-value]


def _version(widget: str) -> int:
    from . import widgets

    versions = [version for name, version in widgets.CATALOG if name == widget]
    return max(versions) if versions else 1


def _kpis(
    gathered: Sequence[tuple[str, Mapping[str, Any], Mapping[str, Any]]],
) -> list[tuple[str, str, str, Any, str | None]]:
    """Every cell of every one-row frame, as (reference, label, column, value, unit).

    Transcription, in the order the Turn made them. No ranking, no selection of
    the "interesting" ones: the first six is a rule anybody can check, where
    "the six that matter" is this layer deciding what the answer is.
    """
    out: list[tuple[str, str, str, Any, str | None]] = []
    for reference, payload, _provenance in gathered:
        rows = payload.get("rows") or ()
        if len(rows) != 1:
            continue
        columns = [str(name) for name in (payload.get("columns") or ())]
        labels = dict(payload.get("labels") or {})
        unit = payload.get("unit")
        row = list(rows[0])
        for position, column in enumerate(columns):
            if position >= len(row):
                continue
            value = row[position]
            if value is None or isinstance(value, bool) or not isinstance(
                value, (int, float)
            ):
                continue
            out.append((reference, labels.get(column, column), column, value, unit))
            if len(out) >= MAX_KPIS:
                return out
    return out


def _placed_kpis(
    cells: Sequence[tuple[str, str, str, Any, str | None]],
    frames: dict[str, Mapping[str, Any]],
    gathered: Sequence[tuple[str, Mapping[str, Any], Mapping[str, Any]]],
) -> tuple[KpiCell, ...]:
    if not cells:
        return ()
    by_reference = {reference: payload for reference, payload, _ in gathered}
    keys = {id(payload): key for key, payload in frames.items()}

    spans = layout.kpi_spans(len(cells))
    out: list[KpiCell] = []
    for index, (reference, label, column, value, unit) in enumerate(cells):
        payload = by_reference[reference]
        key = keys.get(id(payload))
        if key is None:
            key = f"f{len(frames)}"
            frames[key] = payload
            keys[id(payload)] = key
        out.append(
            KpiCell(
                label=label,
                value=ResolvedValue(
                    text=format.number(value, unit),
                    raw=value,
                    unit=unit,
                    frame=key,
                    row=0,
                    column=column,
                ),
                delta=None,
                role=None,
                span=spans[index],
            )
        )
    return tuple(out)


__all__ = ["DEFAULT_TITLE", "SECTION_HEADING", "compose"]
