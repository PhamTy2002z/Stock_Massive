"""Turning stored frames into what a calculation reads, and back again.

Two conversions, and they are not symmetric.

**Going in** is nearly nothing: a stored frame is already positional rows
against named columns, which is what a DataFrame is, so the child is handed the
columns and the rows and builds the DataFrame itself. Labels do not go with
them. A label is the Vietnamese a person reads above a column and a calculation
has no use for one; sending them would be sending the reader's half of the
frame into a process that only does arithmetic.

**Coming back** is where the frame is actually made, and where three things a
calculation cannot be trusted to get right are decided here instead.

*Labels are inherited.* A column the calculation kept — ``roe``, ``symbol`` —
keeps the heading it had in the frame it came from, so a table of ratios does
not lose its Vietnamese by being divided by another table. A column the
calculation invented gets its own name until something better names it.

*Provenance is pessimistic.* ``as_of`` is the oldest of the inputs, because a
number derived from a stale input is stale; health is the worst of them, for the
same reason. A calculation that touched a number read off a web page says so in
its notes, because the derived number is no better than that page.

*Roles are checked, not trusted.* A calculation says which cell won by setting
``result.attrs``, and :class:`~src.studies.contracts.Frame` refuses a role that
names a row or column it does not have. The refusal is turned into a named
answer here rather than an exception, since a mislabelled role is a mistake the
model can fix on its next round.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ..contracts import Frame, FrameKind, Health, Provenance

#: The health words, worst last. Comparing by position is what makes "the worst
#: of the inputs" a lookup rather than a chain of conditionals that has to be
#: rewritten when a fourth word appears.
_HEALTH_ORDER: tuple[Health, ...] = ("normal", "degraded", "unavailable")

#: The three shapes a calculation may declare its answer to be.
OUTPUT_KINDS: tuple[FrameKind, ...] = ("series", "table", "matrix")

INVALID_RESULT = "compute_invalid_result"


def input_payload(frame: Mapping[str, Any]) -> dict[str, Any]:
    """One stored frame as the columns and rows the child builds a DataFrame from."""
    return {
        "columns": [str(name) for name in (frame.get("columns") or [])],
        "rows": [list(row) for row in (frame.get("rows") or [])],
    }


def frame_from_result(
    result: Mapping[str, Any], *, inputs: Sequence[Mapping[str, Any]]
) -> Frame | str:
    """The calculation's answer as a Frame, or a sentence saying why it is not.

    Returned rather than raised for the reason every refusal in this plane is
    returned: a role naming a column that is not there is the model's mistake to
    fix, and an exception would spend the call as a failure instead of as an
    answer it can read.
    """
    columns = tuple(str(name) for name in (result.get("columns") or []))
    if not columns:
        return "phép tính trả về một bảng không có cột nào."
    rows = tuple(tuple(row) for row in (result.get("rows") or []))
    labels = _labels(columns, result.get("labels") or {}, inputs)
    kind = result.get("kind") if result.get("kind") in OUTPUT_KINDS else "table"

    cell_roles: dict[tuple[int, str], str] = {}
    for entry in result.get("cellRoles") or []:
        try:
            cell_roles[(int(entry["row"]), str(entry["column"]))] = str(entry["role"])
        except (KeyError, TypeError, ValueError):
            return "một vai trò của ô không đọc được; cần hàng, cột và tên vai trò."

    try:
        return Frame(
            kind=kind,  # type: ignore[arg-type]
            columns=columns,
            rows=rows,
            unit=result.get("unit"),
            labels=labels,
            column_roles={
                str(key): str(value)
                for key, value in (result.get("columnRoles") or {}).items()
            },
            point_roles=tuple(result.get("pointRoles") or ()),
            cell_roles=cell_roles,
        )
    except ValueError as exc:
        return str(exc)


def _labels(
    columns: Sequence[str],
    declared: Mapping[str, Any],
    inputs: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    """A Vietnamese heading for every column: the calculation's, the input's, the name."""
    inherited: dict[str, str] = {}
    for frame in inputs:
        for column, label in (frame.get("labels") or {}).items():
            inherited.setdefault(str(column), str(label))
    return {
        name: str(declared.get(name) or inherited.get(name) or name)
        for name in columns
    }


def derived_provenance(
    *,
    provenances: Sequence[Mapping[str, Any]],
    rows: int,
    code_digest: str,
    constants: Mapping[str, Any],
    now: datetime | None = None,
) -> Provenance:
    """What a derived frame may claim, given what it was derived from.

    Pessimistic on every axis a reader would be misled by an optimistic answer
    on. A number computed from a frame that was frozen last Tuesday is a number
    from last Tuesday, whatever time it is now.
    """
    stamps = [_when(entry.get("asOf")) for entry in provenances]
    stamps = [stamp for stamp in stamps if stamp is not None]
    as_of = min(stamps) if stamps else (now or datetime.now(timezone.utc))

    health: Health = "normal"
    reason: str | None = None
    for entry in provenances:
        candidate = str(entry.get("health") or "normal")
        if candidate not in _HEALTH_ORDER:
            continue
        if _HEALTH_ORDER.index(candidate) > _HEALTH_ORDER.index(health):
            health = candidate  # type: ignore[assignment]
            reason = _sentence(entry.get("reason"))

    notes: list[str] = []
    for entry in provenances:
        for note in entry.get("methodNotes") or []:
            text = _sentence(note)
            if text and text not in notes:
                notes.append(text)
    if any(str(entry.get("source")) == "web" for entry in provenances):
        notes.append("Có số lấy từ trang đã đọc, không phải số của hệ thống")
    # Counted over the *figures* only. A constant carrying a column heading or a
    # status word is how a Vietnamese label reaches the sandbox — the only door
    # into it — and an assumption is a number somebody asserted. Told that a
    # checklist rests on eight declared assumptions when five of them are label
    # maps, a reader would be reading a warning about nothing.
    asserted = sum(
        1
        for value in constants.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    if asserted:
        notes.append(f"Phép tính dùng {asserted} giả định đã khai báo")
    notes.append(f"Số liệu tính lại, phép tính mã {code_digest}")

    return Provenance(
        source="derived",
        as_of=as_of,
        sessions_used=rows,
        health=health,
        reason=reason,
        method_notes=tuple(notes[:MAX_METHOD_NOTES]),
    )


#: How many notes a derived frame carries. Inputs bring their own and a chain of
#: calculations would otherwise accumulate every one of them; past this the strip
#: a reader looks at to check whether the numbers are thin is a paragraph.
MAX_METHOD_NOTES = 6


def _sentence(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _when(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


__all__ = [
    "INVALID_RESULT",
    "MAX_METHOD_NOTES",
    "OUTPUT_KINDS",
    "derived_provenance",
    "frame_from_result",
    "input_payload",
]
