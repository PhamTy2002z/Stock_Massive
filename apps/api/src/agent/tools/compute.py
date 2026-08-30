"""Arithmetic on frames the model already gathered, written by the model.

``query`` opens the store's tables and ``compare_fields`` puts symbols against
figures, and between them they answer *what is there*. What neither answers is
the question a reader asks next: whether the growth is faster, whether the ratio
is improving, which of two companies is stronger once you look at the trend
rather than the level. Those are arithmetic, and there is no list of them.

That is why this exists and why it is not an enumeration of operations. A closed
set of verbs — ``yoy``, ``share_of_total``, ``rank`` — is the same mistake as a
closed set of Studies, made one layer lower: it guesses the questions in advance
and answers the eleventh one with prose. So the calculation is code, written per
question, over frames.

**Which puts the whole weight on one invariant: the model never types a market
number.** With a closed verb list that was true by construction. Here it is true
because ``studies/compute/validator.py`` reads the code before anything runs and
refuses any numeric literal that is not structural — a column position, a
hundred for a percentage, the sessions in a year. A figure the question itself
asserts goes through ``constants``, where it is stored with the reason the model
gave for it, and the artifact carries a flag saying the picture rests on one.

**Frames go in and a frame comes out; numbers never come back.** The answer is a
``frameId`` and a shape — how many rows, which columns, the range of each numeric
one. The same rule ``run_study`` and ``query`` hold, for the same reason: a
matrix in a message is a matrix the model will read the wrong cell of, and it is
context nobody gets back.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session

from src.core.database import get_sync_db
from src.studies import frames_buffer
from src.studies.compute import frames_io, runner, validator

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolContext,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
    object_schema,
    register,
)

TOOLSET = "studies"

#: Where a runaway result is cut, in characters. A bug-stop: what this returns is
#: a summary of fixed shape, and the largest honest one is far under this.
MAX_RESULT_CHARS = 8_000

#: How many frames one calculation may read. Six because a calculation joining a
#: seventh table has stopped being a step in an answer and become a pipeline, and
#: a pipeline belongs in a Study where it can be named and tested.
MAX_INPUTS = 6

#: How many assumptions one calculation may declare. Four, because an answer
#: resting on a fifth asserted figure is an answer about the assumptions.
MAX_CONSTANTS = 4

#: How many calculations one Turn may run. Six: enough for gather, derive,
#: compare, rank and two attempts that went wrong, and few enough that a model
#: looping on a rejected calculation runs out before the Turn does.
MAX_COMPUTE_PER_TURN = 6

#: How long the name of a declared assumption may be, and how long its reason.
MAX_CONSTANT_NAME = 40
MAX_CONSTANT_REASON = 160

#: How many columns the summary describes one by one. Past this the model is told
#: how wide the frame is and shown the first of them, which is what it needs to
#: know it got the shape it asked for.
SUMMARY_COLUMNS = 12

REJECTED = "compute_rejected"
INPUT_NOT_AVAILABLE = "compute_input_not_available"
TOO_MANY = "compute_too_many_this_turn"

SessionOpener = Any


COMPUTE_DESCRIPTION = (
    "Do arithmetic on frames already gathered this turn, by writing pandas. The "
    "frames named in inputs arrive as f0, f1, ... as DataFrames, in the order "
    "given; the code must end by assigning result, a DataFrame or a Series. "
    "Returns a new frameId and the shape of what it built — never the numbers. "
    "Use it for anything query cannot read directly: growth between quarters, a "
    "ratio of two lines, a share of a total, a rank, a rolling mean, a pivot of "
    "symbols against periods, or a comparison of two companies on a derived "
    "figure. Numbers must come from the frames: any numeric literal in the code "
    "other than a structural one (0-12, 100, 252, 365, 1000, 1000000, "
    "1000000000) is refused, and a figure the question itself assumes must be "
    "declared in constants with the reason for it. To say what the numbers mean "
    "— which column is the subject, which cell wins a comparison — set "
    "result.attrs['column_roles'], result.attrs['point_roles'] or "
    "result.attrs['cell_roles'] before assigning result."
)

COMPUTE_SCHEMA = object_schema(
    {
        "code": {
            "type": "string",
            "minLength": 1,
            "maxLength": validator.MAX_CODE_CHARS,
            "description": (
                "Python over pandas. f0..f5 are the input frames as DataFrames; "
                "pd, np, math and statistics are available. Must assign result."
            ),
        },
        "inputs": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "maxItems": MAX_INPUTS,
            "description": (
                f"Up to {MAX_INPUTS} frameIds produced earlier in this turn, in "
                "the order they should appear as f0, f1, ..."
            ),
        },
        "constants": {
            "type": "object",
            "description": (
                "Figures the question itself asserts, which therefore may not be "
                "read from a frame. Each is {\"value\": <number>, \"reason\": "
                "\"<why this number>\"} and is available in the code under its "
                "own name. At most four."
            ),
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "value": {"type": "number"},
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["value", "reason"],
            },
        },
        "output_kind": {
            "type": "string",
            "enum": list(frames_io.OUTPUT_KINDS),
            "description": (
                "What shape the answer is, when it is not obvious from the "
                "result: a series over time, a flat table, or a matrix."
            ),
        },
    },
    ("code", "inputs"),
)


def summarise_compute(arguments: Mapping[str, Any]) -> str:
    """The rail row for a calculation: how many tables it worked on."""
    inputs = arguments.get("inputs")
    count = len(inputs) if isinstance(inputs, list) else 0
    if count == 1:
        return "Tính trên 1 bảng số"
    if count:
        return f"Tính trên {count} bảng số"
    return "Tính trên số đã đọc"


class ComputeTool:
    """Run one model-written calculation over frames this Turn already made."""

    def __init__(self, *, session_opener: SessionOpener = get_sync_db) -> None:
        self._session_opener = session_opener

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name="compute",
                toolset=TOOLSET,
                description=COMPUTE_DESCRIPTION,
                schema=COMPUTE_SCHEMA,
                handler=self.compute,
                display_name="Tính trên số đã đọc",
                summarise=summarise_compute,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                # The boundary crossed is this deployment's own store: frames in,
                # a row out. The subprocess is an isolation mechanism and not a
                # boundary — it reaches nothing this process could not.
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                # One at a time within a Turn. Each call spawns a process holding
                # up to half a gigabyte, and a round issuing six of them at once
                # is six of those at once.
                concurrency=ToolConcurrency.SERIALIZED,
                contract_version="1",
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
        )

    def compute(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Validate, run, and file the answer as a frame this Turn owns."""
        code = str(arguments.get("code") or "")
        if not code.strip():
            raise ValueError("code must be the calculation to run")
        if len(code) > validator.MAX_CODE_CHARS:
            raise ValueError(
                f"code is {len(code)} characters against a ceiling of "
                f"{validator.MAX_CODE_CHARS}; a calculation is an expression, "
                "not a script"
            )
        references = _inputs(arguments.get("inputs"))
        constants = _constants(arguments.get("constants"))
        output_kind = arguments.get("output_kind") or None

        violations = validator.validate(code)
        if violations:
            return _rejected(violations)

        with self._open() as session:
            already = frames_buffer.frames_of_kind_in_turn(
                session, context.turn_id, frames_buffer.COMPUTE_KIND
            )
            if already >= MAX_COMPUTE_PER_TURN:
                return {
                    "error": TOO_MANY,
                    "detail": (
                        f"This turn has already run {already} calculations, "
                        f"which is the ceiling of {MAX_COMPUTE_PER_TURN}. Draw "
                        "what is already computed rather than deriving more."
                    ),
                }

            frames: list[Mapping[str, Any]] = []
            provenances: list[Mapping[str, Any]] = []
            for reference in references:
                try:
                    frame, provenance = frames_buffer.read_frame(
                        session, reference, turn_id=context.turn_id
                    )
                except frames_buffer.FrameNotAvailable as exc:
                    return {"error": INPUT_NOT_AVAILABLE, "detail": str(exc)}
                frames.append(frame)
                provenances.append(provenance)

            outcome = runner.run(
                code=code,
                frames=[frames_io.input_payload(frame) for frame in frames],
                constants={name: entry["value"] for name, entry in constants.items()},
                output_kind=output_kind,
            )
            if not outcome.get("ok"):
                return {
                    "error": str(outcome.get("error") or runner.RUNTIME_ERROR),
                    "detail": str(outcome.get("detail") or ""),
                }

            built = frames_io.frame_from_result(
                outcome.get("frame") or {}, inputs=frames
            )
            if isinstance(built, str):
                return {"error": frames_io.INVALID_RESULT, "detail": built}

            digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]
            provenance = frames_io.derived_provenance(
                provenances=provenances,
                rows=len(built.rows),
                code_digest=digest,
                constants=constants,
                now=context.now,
            )
            params = {
                "code": code,
                "inputs": list(references),
                "constants": {
                    name: dict(entry) for name, entry in constants.items()
                },
                "output_kind": output_kind,
                "code_digest": digest,
            }
            frame_id = frames_buffer.store_frame(
                session,
                kind=frames_buffer.COMPUTE_KIND,
                frame=built,
                provenance=provenance,
                params=params,
                title=f"Số liệu tính lại từ {len(references)} bảng",
                turn_id=context.turn_id,
                thread_id=context.thread_id,
            )

        # ``frameId`` first, on ``tools/query.py``'s reasoning: a result over its
        # declared size is replaced by a preview of its head, so whatever is
        # written last is what a long answer loses — and losing the frame id
        # loses the only thing that can be drawn.
        return {
            "frameId": str(frame_id),
            "rows": len(built.rows),
            "columnCount": len(built.columns),
            "columnSample": [
                {"name": name, "label": built.labels[name]}
                for name in built.columns[:SUMMARY_COLUMNS]
            ],
            "kind": built.kind,
            "unit": built.unit,
            "asOf": provenance.as_of.isoformat(),
            "health": provenance.health,
            # Ranges and not values. The model needs to know the arithmetic
            # landed somewhere plausible — that a growth column is not every cell
            # null — and a range says that without handing back the numbers.
            "columnRanges": _ranges(built),
            "hasConstants": bool(constants),
            "computesLeft": MAX_COMPUTE_PER_TURN - already - 1,
        }

    @contextmanager
    def _open(self) -> Iterator[Session]:
        with self._session_opener() as session:
            yield session


def _inputs(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("inputs must name at least one frameId from this turn")
    if len(raw) > MAX_INPUTS:
        raise ValueError(
            f"compute reads at most {MAX_INPUTS} frames and {len(raw)} were named"
        )
    return tuple(str(value).strip() for value in raw)


def _constants(raw: Any) -> dict[str, dict[str, Any]]:
    """The declared assumptions, each with the reason that makes it declarable.

    A reason is required rather than encouraged. The whole difference between a
    constant and a literal typed into the code is that somebody said why, and a
    constant with an empty reason is a literal that found a way in.
    """
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("constants must be an object of name to {value, reason}")
    if len(raw) > MAX_CONSTANTS:
        raise ValueError(
            f"compute takes at most {MAX_CONSTANTS} declared constants and "
            f"{len(raw)} were given"
        )
    declared: dict[str, dict[str, Any]] = {}
    for name, entry in raw.items():
        key = str(name).strip()
        if not key.isidentifier() or len(key) > MAX_CONSTANT_NAME:
            raise ValueError(
                f"{name!r} is not usable as a constant name; use a plain "
                "identifier the code can refer to"
            )
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"constant {key!r} must be {{\"value\": <number>, \"reason\": "
                "\"<why>\"}}"
            )
        value = entry.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"constant {key!r} must have a numeric value")
        reason = str(entry.get("reason") or "").strip()
        if not reason:
            raise ValueError(
                f"constant {key!r} needs a reason; a number with no reason is a "
                "figure typed into the calculation"
            )
        declared[key] = {"value": value, "reason": reason[:MAX_CONSTANT_REASON]}
    return declared


def _rejected(violations: Sequence[validator.Violation]) -> dict[str, Any]:
    """A refusal the model can act on, naming every reason at once.

    Returned rather than raised, on ``tools/signals.py``'s reasoning: the request
    was well formed and the answer is that this code may not run, which is a fact
    to relay and rewrite from rather than a tool failure to retry.
    """
    return {
        "error": validator.first_code(violations),
        "detail": (
            f"Phép tính bị từ chối vì {len(violations)} lý do; sửa rồi gọi lại."
        ),
        "rejected": REJECTED,
        "violations": [violation.to_payload() for violation in violations],
    }


def _ranges(frame: Any) -> list[dict[str, Any]]:
    """The smallest and largest value of each numeric column, and how many are there.

    Not a sample of the numbers: a sample *is* the numbers, and the frame's whole
    point is that they stay where a reader sees them. A range is a statement
    about the shape of a column, which is what tells a model the calculation
    landed somewhere plausible.
    """
    ranges: list[dict[str, Any]] = []
    for position, name in enumerate(frame.columns[:SUMMARY_COLUMNS]):
        values = [
            row[position]
            for row in frame.rows
            if isinstance(row[position], (int, float))
            and not isinstance(row[position], bool)
        ]
        if not values:
            continue
        ranges.append(
            {
                "column": name,
                "answered": len(values),
                "min": min(values),
                "max": max(values),
            }
        )
    return ranges


def register_compute_tool(
    *, session_opener: SessionOpener = get_sync_db
) -> tuple[ToolEntry, ...]:
    """Register the calculation tool and hand back what was registered."""
    tool = ComputeTool(session_opener=session_opener)
    return tuple(register(entry) for entry in tool.entries())


__all__ = [
    "COMPUTE_DESCRIPTION",
    "COMPUTE_SCHEMA",
    "INPUT_NOT_AVAILABLE",
    "MAX_COMPUTE_PER_TURN",
    "MAX_CONSTANTS",
    "MAX_INPUTS",
    "MAX_RESULT_CHARS",
    "REJECTED",
    "SUMMARY_COLUMNS",
    "TOO_MANY",
    "ComputeTool",
    "register_compute_tool",
    "summarise_compute",
]
