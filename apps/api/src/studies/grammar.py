"""What a board is allowed to be, and the named reason when it is not.

The model composes a *plan for a picture*, not the picture: sections, a KPI
strip, a caption with holes in it where numbers go. This module is the shape of
that plan and the check that a plan is one.

**Every rule here exists because breaking it produces a board a reader cannot
use.** A board with no KPI strip buries the answer in a chart; a board with ten
of them has no answer at all. A caption carrying a digit is the one place a
model can type a market number without a frame behind it, which is the invariant
this whole track is built on — so a digit outside a placeholder is a violation
even when it is a year, and a period is referenced through a cell like every
other fact.

**A violation is a name and a sentence, never a raise.** The model gets one
round to fix what it wrote, and it can only fix what it can read. So the check
returns a list, the handler relays it, and the second failure is answered by the
server composing a board itself rather than by a Turn ending in prose.

Pure of the store: everything here reads the spec the model sent and the frame
payloads the buffer already fetched. No session, no clock, no settings.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .contracts import ROLES

#: How many sections one board may hold. Four, because a fifth is a report and
#: the surface it lands on is a panel beside an answer.
MAX_SECTIONS = 4

#: How many blocks one section may hold. Four for the same reason a row of the
#: grid is twelve columns wide: past this the section stops being one idea.
MAX_BLOCKS_PER_SECTION = 4

#: How many visuals one board may hold, across every section. The ceiling that
#: replaced ``frames_buffer.MAX_BLOCKS``: that one counted every block the model
#: named, and a board is now three different kinds of block with three different
#: costs to a reader.
MAX_VISUALS = 8

#: How many figures the strip at the top may carry. Three is the floor because a
#: strip of two is a sentence written as boxes; six is the ceiling because a
#: seventh is a table pretending to be a summary.
MIN_KPIS = 3
MAX_KPIS = 6

#: How many captions the board may hold, and how many one section may.
MAX_CAPTIONS = 5
MAX_CAPTIONS_PER_SECTION = 1

#: How long one caption may be. A caption is read *while* looking at the chart
#: above it; past roughly this it becomes a paragraph the eye leaves the picture
#: for.
CAPTION_LIMIT = 280

#: How long a KPI's label may be. It sits in a box four columns wide.
KPI_LABEL_LIMIT = 40

#: The archetypes a board may declare. The set lives in ``archetypes.py``; this
#: is the spelling check, kept here so the grammar does not import the module
#: that imports the grammar.
ARCHETYPES: frozenset[str] = frozenset(
    {"compare", "profile", "screen", "timeline", "decompose"}
)

#: What a caption may put a number into. ``{a}`` through ``{f}`` and nothing
#: else: a fixed alphabet means the schema can describe the reference object once
#: per slot, and a model cannot invent a placeholder with no reference behind it
#: without the check seeing an unknown key rather than a silent literal.
REF_KEYS: tuple[str, ...] = ("a", "b", "c", "d", "e", "f")

_PLACEHOLDER = re.compile(r"\{([a-z])\}")
_DIGIT = re.compile(r"\d")

#: What a widget name looks like. Checked before the catalog is consulted so a
#: model sending an object where a name belongs gets a grammar violation rather
#: than a lookup miss.
_WIDGET_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Violation:
    """One named thing wrong with a board, and where it is.

    ``code`` is what a test asserts on and what the model reads first;
    ``detail`` is the Vietnamese-free English sentence the model is expected to
    act on. The reader never sees either — a board that fails this check is
    never stored.
    """

    code: str
    where: str
    detail: str

    def to_payload(self) -> dict[str, str]:
        return {"code": self.code, "where": self.where, "detail": self.detail}


@dataclass(frozen=True)
class Ref:
    """One cell, named the way a model can name it without seeing the numbers.

    ``row`` is a position and ``row_where`` is a lookup spelled ``column=value``.
    Two spellings because the two situations genuinely differ: a series has a
    last row and no key, and a comparison has ``symbol=VIC`` and no stable
    position once a sort changes. Exactly one of them is given.
    """

    frame_id: str
    column: str
    row: int | None = None
    row_where: str | None = None


@dataclass(frozen=True)
class Kpi:
    """One figure on the strip: what it is called and which cell it is."""

    label: str
    value: Ref
    delta: Ref | None = None
    role: str | None = None


@dataclass(frozen=True)
class Visual:
    """One picture: the frame it draws and, at most, a suggestion about how."""

    frame_id: str
    widget: str | None = None
    columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class Caption:
    """One sentence with holes in it, and the cell that fills each hole."""

    template: str
    refs: Mapping[str, Ref] = field(default_factory=dict)


Block = Visual | Caption


@dataclass(frozen=True)
class Section:
    heading: str | None
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class Board:
    """The plan, parsed. What :func:`validate` is handed and what compiles."""

    title: str
    archetype: str | None
    kpis: tuple[Kpi, ...]
    sections: tuple[Section, ...]
    appendix_frame_id: str | None = None


class BoardMalformed(ValueError):
    """The arguments are not a board at all — a shape failure, not a rule one.

    Separate from :class:`Violation` because the two ask different things of the
    caller. A violation is a board the model can edit; this is arguments that
    never described one, and the honest answer is the tool's own error.
    """


# -- parsing ---------------------------------------------------------------


def parse(arguments: Mapping[str, Any]) -> Board:
    """The wire arguments as a board, or :class:`BoardMalformed`.

    Strict mode spells an absent value as ``null``, so every optional field
    arrives present and empty. Dropping them here rather than in the rules below
    is what keeps the rules about boards instead of about JSON.
    """
    title = str(arguments.get("title") or "").strip()
    if not title:
        raise BoardMalformed("title must say what the board is called")

    archetype = _optional_text(arguments.get("archetype"))
    if archetype is not None and archetype not in ARCHETYPES:
        raise BoardMalformed(
            f"{archetype!r} is not an archetype; the five are "
            + ", ".join(sorted(ARCHETYPES))
        )

    raw_sections = arguments.get("sections")
    if not isinstance(raw_sections, Sequence) or isinstance(raw_sections, (str, bytes)):
        raise BoardMalformed("sections must be a list of at least one section")
    sections = tuple(_section(item, index) for index, item in enumerate(raw_sections))
    if not sections:
        raise BoardMalformed("sections must hold at least one section")

    raw_kpis = arguments.get("kpis")
    kpis: tuple[Kpi, ...] = ()
    if isinstance(raw_kpis, Sequence) and not isinstance(raw_kpis, (str, bytes)):
        kpis = tuple(_kpi(item, index) for index, item in enumerate(raw_kpis))

    return Board(
        title=title,
        archetype=archetype,
        kpis=kpis,
        sections=sections,
        appendix_frame_id=_optional_text(arguments.get("appendix_frame_id")),
    )


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _section(item: Any, index: int) -> Section:
    if not isinstance(item, Mapping):
        raise BoardMalformed(f"section {index} is not a section object")
    raw_blocks = item.get("blocks")
    if not isinstance(raw_blocks, Sequence) or isinstance(raw_blocks, (str, bytes)):
        raise BoardMalformed(f"section {index} has no blocks")
    blocks = tuple(
        _block(block, f"sections[{index}].blocks[{position}]")
        for position, block in enumerate(raw_blocks)
    )
    if not blocks:
        raise BoardMalformed(f"section {index} has no blocks")
    return Section(heading=_optional_text(item.get("heading")), blocks=blocks)


def _block(item: Any, where: str) -> Block:
    if not isinstance(item, Mapping):
        raise BoardMalformed(f"{where} is not a block object")
    kind = str(item.get("kind") or "").strip()
    if kind == "visual":
        frame_id = _optional_text(item.get("frame_id"))
        if frame_id is None:
            raise BoardMalformed(f"{where} is a visual with no frame_id")
        raw_columns = item.get("columns")
        columns: tuple[str, ...] = ()
        if isinstance(raw_columns, Sequence) and not isinstance(
            raw_columns, (str, bytes)
        ):
            columns = tuple(str(name) for name in raw_columns if str(name).strip())
        return Visual(
            frame_id=frame_id,
            widget=_optional_text(item.get("widget")),
            columns=columns,
        )
    if kind == "caption":
        template = str(item.get("template") or "").strip()
        if not template:
            raise BoardMalformed(f"{where} is a caption with no template")
        return Caption(template=template, refs=_refs(item.get("refs"), where))
    raise BoardMalformed(
        f"{where} has kind {kind!r}; a block is a visual or a caption"
    )


def _refs(raw: Any, where: str) -> dict[str, Ref]:
    if not isinstance(raw, Mapping):
        return {}
    refs: dict[str, Ref] = {}
    for key in REF_KEYS:
        value = raw.get(key)
        if value is None:
            continue
        refs[key] = _ref(value, f"{where}.refs.{key}")
    return refs


def _kpi(item: Any, index: int) -> Kpi:
    where = f"kpis[{index}]"
    if not isinstance(item, Mapping):
        raise BoardMalformed(f"{where} is not a kpi object")
    label = str(item.get("label") or "").strip()
    if not label:
        raise BoardMalformed(f"{where} has no label")
    value = item.get("value")
    if value is None:
        raise BoardMalformed(f"{where} names no cell to show")
    delta = item.get("delta")
    return Kpi(
        label=label,
        value=_ref(value, f"{where}.value"),
        delta=None if delta is None else _ref(delta, f"{where}.delta"),
        role=_optional_text(item.get("role")),
    )


def _ref(value: Any, where: str) -> Ref:
    if not isinstance(value, Mapping):
        raise BoardMalformed(f"{where} is not a reference object")
    frame_id = _optional_text(value.get("frame_id"))
    column = _optional_text(value.get("column"))
    if frame_id is None or column is None:
        raise BoardMalformed(f"{where} needs a frame_id and a column")
    row = value.get("row")
    if row is not None and not isinstance(row, int):
        raise BoardMalformed(f"{where}.row is a row number or nothing")
    return Ref(
        frame_id=frame_id,
        column=column,
        row=None if isinstance(row, bool) else row,
        row_where=_optional_text(value.get("row_where")),
    )


# -- the rules -------------------------------------------------------------


def validate(
    board: Board,
    frames: Mapping[str, Mapping[str, Any]],
    *,
    authored: bool = True,
) -> list[Violation]:
    """Every rule this board breaks, named, in the order a reader meets them.

    ``frames`` is keyed by the reference the model wrote, and holds the frame
    payload the buffer resolved for it. A reference with no entry is one the
    Turn does not own; the caller has already turned that into a violation of
    its own rather than letting a lookup miss read as a rule failure.

    ``authored`` is what separates a board the model wrote from one the server
    composed. The KPI floor is a rule about *answering*: three figures is what
    it takes to say something, and a model that has an answer can find three.
    The server has no answer — it has frames — so composing a strip of three
    would be this system deciding which numbers matter, which is the one thing
    it must never do. Every other rule applies to both.
    """
    violations: list[Violation] = []
    violations.extend(_structure(board))
    violations.extend(_kpi_rules(board, frames, authored=authored))
    violations.extend(_caption_rules(board, frames))
    violations.extend(_visual_rules(board, frames))
    return violations


def _structure(board: Board) -> list[Violation]:
    out: list[Violation] = []
    if len(board.sections) > MAX_SECTIONS:
        out.append(
            Violation(
                "sections_over_limit",
                "sections",
                f"a board holds at most {MAX_SECTIONS} sections, {len(board.sections)} "
                "were sent",
            )
        )
    for index, section in enumerate(board.sections):
        if len(section.blocks) > MAX_BLOCKS_PER_SECTION:
            out.append(
                Violation(
                    "blocks_over_limit",
                    f"sections[{index}]",
                    f"a section holds at most {MAX_BLOCKS_PER_SECTION} blocks, "
                    f"{len(section.blocks)} were sent",
                )
            )
        captions = sum(1 for block in section.blocks if isinstance(block, Caption))
        if captions > MAX_CAPTIONS_PER_SECTION:
            out.append(
                Violation(
                    "caption_over_limit",
                    f"sections[{index}]",
                    f"a section carries at most {MAX_CAPTIONS_PER_SECTION} caption, "
                    f"{captions} were sent",
                )
            )
    visuals = sum(
        1
        for section in board.sections
        for block in section.blocks
        if isinstance(block, Visual)
    )
    if visuals > MAX_VISUALS:
        out.append(
            Violation(
                "blocks_over_limit",
                "sections",
                f"a board draws at most {MAX_VISUALS} visuals, {visuals} were sent",
            )
        )
    captions = sum(
        1
        for section in board.sections
        for block in section.blocks
        if isinstance(block, Caption)
    )
    if captions > MAX_CAPTIONS:
        out.append(
            Violation(
                "caption_over_limit",
                "sections",
                f"a board carries at most {MAX_CAPTIONS} captions, {captions} were sent",
            )
        )
    return out


def _kpi_rules(
    board: Board,
    frames: Mapping[str, Mapping[str, Any]],
    *,
    authored: bool,
) -> list[Violation]:
    out: list[Violation] = []
    if authored and len(board.kpis) < MIN_KPIS:
        out.append(
            Violation(
                "board_missing_kpi_strip",
                "kpis",
                f"a board leads with {MIN_KPIS} to {MAX_KPIS} figures; "
                f"{len(board.kpis)} were sent",
            )
        )
    if len(board.kpis) > MAX_KPIS:
        out.append(
            Violation(
                "board_too_many_kpi",
                "kpis",
                f"a strip carries at most {MAX_KPIS} figures; {len(board.kpis)} "
                "were sent",
            )
        )
    for index, kpi in enumerate(board.kpis):
        where = f"kpis[{index}]"
        if len(kpi.label) > KPI_LABEL_LIMIT:
            out.append(
                Violation(
                    "kpi_label_too_long",
                    where,
                    f"a label fits {KPI_LABEL_LIMIT} characters; this one is "
                    f"{len(kpi.label)}",
                )
            )
        if kpi.role is not None and kpi.role not in ROLES:
            out.append(
                Violation(
                    "kpi_role_unknown",
                    where,
                    f"{kpi.role!r} is not a role this system draws",
                )
            )
        for name, ref in (("value", kpi.value), ("delta", kpi.delta)):
            if ref is None:
                continue
            problem = resolve_problem(ref, frames)
            if problem is not None:
                out.append(
                    Violation("kpi_ref_unresolved", f"{where}.{name}", problem)
                )
    return out


def _caption_rules(
    board: Board, frames: Mapping[str, Mapping[str, Any]]
) -> list[Violation]:
    out: list[Violation] = []
    for index, section in enumerate(board.sections):
        for position, block in enumerate(section.blocks):
            if not isinstance(block, Caption):
                continue
            where = f"sections[{index}].blocks[{position}]"
            if len(block.template) > CAPTION_LIMIT:
                out.append(
                    Violation(
                        "caption_too_long",
                        where,
                        f"a caption fits {CAPTION_LIMIT} characters; this one is "
                        f"{len(block.template)}",
                    )
                )
            used = set(_PLACEHOLDER.findall(block.template))
            # A digit anywhere the placeholders are not is a number the model
            # typed. Including a year: a period a reader needs is a cell in a
            # frame, and quoting it from memory is the same act as quoting a
            # price from memory.
            stripped = _PLACEHOLDER.sub("", block.template)
            if _DIGIT.search(stripped):
                out.append(
                    Violation(
                        "caption_has_digit",
                        where,
                        "a caption carries no digits of its own; every figure, a "
                        "year included, is a reference into a frame",
                    )
                )
            for key in sorted(used - set(block.refs)):
                out.append(
                    Violation(
                        "caption_ref_unresolved",
                        f"{where}.refs.{key}",
                        f"the caption uses {{{key}}} and names no cell for it",
                    )
                )
            for key in sorted(set(block.refs) - used):
                out.append(
                    Violation(
                        "caption_ref_unused",
                        f"{where}.refs.{key}",
                        f"a cell is named for {{{key}}} and the caption never uses it",
                    )
                )
            for key in sorted(used & set(block.refs)):
                problem = resolve_problem(block.refs[key], frames)
                if problem is not None:
                    out.append(
                        Violation(
                            "caption_ref_unresolved", f"{where}.refs.{key}", problem
                        )
                    )
    return out


def _visual_rules(
    board: Board, frames: Mapping[str, Mapping[str, Any]]
) -> list[Violation]:
    out: list[Violation] = []
    drawn: dict[str, str] = {}
    for index, section in enumerate(board.sections):
        for position, block in enumerate(section.blocks):
            if not isinstance(block, Visual):
                continue
            where = f"sections[{index}].blocks[{position}]"
            if block.widget is not None and not _WIDGET_NAME.match(block.widget):
                out.append(
                    Violation(
                        "widget_name_invalid",
                        where,
                        f"{block.widget!r} is not a widget name",
                    )
                )
            # The one table a board may carry sits in the appendix. Everywhere
            # else it is the model declining to choose a picture, and the server
            # will choose one from the frame's shape instead.
            if block.widget == "data_table":
                out.append(
                    Violation(
                        "table_not_in_appendix",
                        where,
                        "a plain table belongs in the appendix; leave the widget "
                        "out and the shape of the frame decides the picture",
                    )
                )
            previous = drawn.get(block.frame_id)
            if previous is not None:
                out.append(
                    Violation(
                        "visual_frame_reused",
                        where,
                        f"this frame is already drawn at {previous}",
                    )
                )
            else:
                drawn[block.frame_id] = where
            if block.frame_id not in frames:
                out.append(
                    Violation(
                        "frame_not_available",
                        where,
                        f"{block.frame_id!r} is not a frame this turn produced",
                    )
                )
                continue
            frame = frames[block.frame_id]
            columns = {str(name) for name in (frame.get("columns") or ())}
            for name in block.columns:
                if name not in columns:
                    out.append(
                        Violation(
                            "visual_column_unknown",
                            where,
                            f"the frame has no column named {name!r}",
                        )
                    )
    if board.appendix_frame_id is not None and board.appendix_frame_id not in frames:
        out.append(
            Violation(
                "frame_not_available",
                "appendix_frame_id",
                f"{board.appendix_frame_id!r} is not a frame this turn produced",
            )
        )
    return out


# -- reference resolution --------------------------------------------------


def row_index(ref: Ref, frame: Mapping[str, Any]) -> int | None:
    """Which row this reference names, or ``None`` when it names none.

    A position and a lookup, in that order of preference, because a model that
    sent both meant the position it counted. A lookup compares as text after
    stripping, so ``symbol=VIC`` finds ``VIC`` whether the cell holds a string
    or something that prints as one.
    """
    rows = frame.get("rows") or []
    if ref.row is not None:
        return ref.row if 0 <= ref.row < len(rows) else None
    if ref.row_where is None:
        # A frame of one row needs no address; anything wider does.
        return 0 if len(rows) == 1 else None
    column, _, wanted = ref.row_where.partition("=")
    columns = [str(name) for name in (frame.get("columns") or ())]
    if column.strip() not in columns:
        return None
    position = columns.index(column.strip())
    target = wanted.strip().casefold()
    for index, row in enumerate(rows):
        if position < len(row) and str(row[position]).strip().casefold() == target:
            return index
    return None


def resolve_problem(
    ref: Ref, frames: Mapping[str, Mapping[str, Any]]
) -> str | None:
    """Why this reference names no cell, or ``None`` when it names one."""
    frame = frames.get(ref.frame_id)
    if frame is None:
        return f"{ref.frame_id!r} is not a frame this turn produced"
    columns = [str(name) for name in (frame.get("columns") or ())]
    if ref.column not in columns:
        return (
            f"the frame has no column named {ref.column!r}; it has "
            + ", ".join(columns[:8])
        )
    index = row_index(ref, frame)
    if index is None:
        if ref.row is not None:
            return f"row {ref.row} is past the end of a frame of {len(frame.get('rows') or [])}"
        if ref.row_where is not None:
            return f"no row matches {ref.row_where!r}"
        return "a frame of several rows needs a row number or a row_where"
    return None


def frame_references(board: Board) -> list[str]:
    """Every frame this board names, once each, in the order it names them."""
    seen: dict[str, None] = {}
    for kpi in board.kpis:
        seen.setdefault(kpi.value.frame_id, None)
        if kpi.delta is not None:
            seen.setdefault(kpi.delta.frame_id, None)
    for section in board.sections:
        for block in section.blocks:
            if isinstance(block, Visual):
                seen.setdefault(block.frame_id, None)
            else:
                for ref in block.refs.values():
                    seen.setdefault(ref.frame_id, None)
    if board.appendix_frame_id is not None:
        seen.setdefault(board.appendix_frame_id, None)
    return list(seen)


__all__ = [
    "ARCHETYPES",
    "Board",
    "BoardMalformed",
    "Block",
    "CAPTION_LIMIT",
    "Caption",
    "KPI_LABEL_LIMIT",
    "Kpi",
    "MAX_BLOCKS_PER_SECTION",
    "MAX_CAPTIONS",
    "MAX_CAPTIONS_PER_SECTION",
    "MAX_KPIS",
    "MAX_SECTIONS",
    "MAX_VISUALS",
    "MIN_KPIS",
    "REF_KEYS",
    "Ref",
    "Section",
    "Violation",
    "Visual",
    "frame_references",
    "parse",
    "resolve_problem",
    "row_index",
    "validate",
]
