"""Five shapes an analysis takes, and the slots each one has to fill.

An archetype is not a template — it does not decide what is drawn. It is the
claim the board is making about *what kind of question this was*, and the check
is that the board actually contains the picture that kind of question needs. A
board declaring ``compare`` with no comparison in it has said one thing and
drawn another, and the reader is the one who finds out.

Five and not fifty, because these are the shapes of *questions* rather than of
data: how do these stack up, what is this one like, which of these many, what
happened over time, what is this made of. A sixth would be one of the five under
another name.

Declaring none is allowed and means ``profile``: a question that named no shape
is a question about one thing, which is the shape with the loosest requirement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .composer import Shape
from .grammar import Violation

#: What a board that declared nothing is checked against.
DEFAULT = "profile"


@dataclass(frozen=True)
class Slot:
    """One picture an archetype needs, said in terms of the frame behind it."""

    name: str
    #: What the frame under this slot has to be. ``None`` accepts any shape.
    predicate: str
    required: bool


def _is(shape: Shape, predicate: str) -> bool:
    if predicate == "any":
        return True
    if predicate == "entity_table":
        return shape.kind == "table" and shape.entity_axis
    if predicate == "time_series":
        return shape.kind == "series" and shape.time_axis
    if predicate == "ranking":
        return shape.kind == "table" and not shape.single_row
    if predicate == "parts":
        return shape.part_of_whole
    return False


@dataclass(frozen=True)
class Archetype:
    name: str
    slots: tuple[Slot, ...]
    #: The order sections read in, as headings a composer may use. Advisory: the
    #: model writes its own headings and this is what auto-compose falls back to.
    section_order: tuple[str, ...]


CATALOG: Mapping[str, Archetype] = {
    "compare": Archetype(
        name="compare",
        slots=(
            Slot("matrix", "entity_table", required=True),
            Slot("detail", "any", required=False),
        ),
        section_order=("Đối chiếu", "Chi tiết"),
    ),
    "profile": Archetype(
        name="profile",
        slots=(Slot("overview", "any", required=True),),
        section_order=("Tổng quan", "Chi tiết"),
    ),
    "screen": Archetype(
        name="screen",
        slots=(Slot("ranking", "ranking", required=True),),
        section_order=("Xếp hạng", "Chi tiết"),
    ),
    "timeline": Archetype(
        name="timeline",
        slots=(Slot("trend", "time_series", required=True),),
        section_order=("Diễn biến", "Chi tiết"),
    ),
    "decompose": Archetype(
        name="decompose",
        slots=(Slot("parts", "parts", required=True),),
        section_order=("Cấu phần", "Chi tiết"),
    ),
}


def check(archetype: str | None, shapes: Sequence[Shape]) -> list[Violation]:
    """Whether the board holds the pictures the archetype it declared needs.

    Only the required slots are checked, and only for *presence*. An archetype
    is a claim about the question, not a layout: a comparison that also holds a
    trend is still a comparison, and refusing the extra picture would make the
    archetype a cage rather than a check.
    """
    entry = CATALOG.get(archetype or DEFAULT)
    if entry is None:
        return [
            Violation(
                "slot_type_mismatch",
                "archetype",
                f"{archetype!r} is not an archetype this system knows",
            )
        ]
    out: list[Violation] = []
    for slot in entry.slots:
        if not slot.required:
            continue
        if not any(_is(shape, slot.predicate) for shape in shapes):
            out.append(
                Violation(
                    "slot_type_mismatch",
                    f"archetype.{slot.name}",
                    f"a {entry.name} board needs one frame that is a "
                    f"{slot.predicate.replace('_', ' ')}, and none of the frames "
                    "drawn is",
                )
            )
    return out


__all__ = ["Archetype", "CATALOG", "DEFAULT", "Slot", "check"]
