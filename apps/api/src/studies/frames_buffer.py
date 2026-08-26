"""Frames a model made this Turn, and the rule about which ones it may draw.

A Study answers a question somebody wrote a recipe for. The questions nobody
wrote a recipe for still deserve a picture, and the way to draw one is to let
the model gather numbers — a field across sixty sessions, then another — and
then say what to do with them. That needs somewhere to put a series between the
call that produced it and the call that draws it, because the one place it must
not go is a message.

So a gathered series is persisted the same way a Study run is: an
``agent_artifact`` row, holding the numbers, keyed by the Turn that made it. The
model is handed the row's id and a handful of summary statistics.

**Ownership is the Turn, and it is checked rather than trusted.** A frame id is
a UUID the model has seen, and a model that has seen one could name it in a
later Turn — or, if it invented a plausible one, in somebody else's. So every
read asks *was this frame made by the Turn asking for it*, and a frame from any
other Turn is refused as though it did not exist. Nothing about this rests on
the id being unguessable.

**A frame is addressed by artifact, and by name where an artifact has several.**
``<artifact-id>`` means "the one frame this row holds" and refuses a row holding
more; ``<artifact-id>#<frame>`` names one of a Study's four. Two spellings
rather than one because the two sources genuinely differ, and a scheme that made
the model write ``#series`` after every gathered series would be a step nobody
could explain.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.alpha.models import AgentArtifact

from .contracts import CanvasBlock, CanvasSpec, Frame, Provenance

#: What a gathered series is filed under. Not a registered Study: nobody chose
#: this shape as a recipe, and it has no ``compute``. It is a name on a row, so
#: an operator reading the table can tell a composed picture from a Study's.
SERIES_KIND = "field_series"

#: What a canvas the model composed is filed under, for the same reason.
COMPOSITION_KIND = "composed_canvas"

#: How many canvases one Turn may compose. Two, because a comparison is the
#: honest second picture and a third is a model drawing rather than answering.
MAX_CANVASES_PER_TURN = 2

#: How many blocks one composed canvas may hold. A panel a reader scrolls past
#: is a panel nobody reads.
MAX_BLOCKS = 6


class FrameNotAvailable(LookupError):
    """The frame named is not one this Turn made, so it may not be drawn.

    One exception for "no such row", "a row from another Turn" and "a name that
    row does not hold", deliberately: they are the same answer to the caller and
    telling them apart would tell a model whether an id it guessed exists.
    """


def store_series(
    session: Session,
    *,
    frame: Frame,
    provenance: Provenance,
    params: Mapping[str, Any],
    turn_id: UUID | None,
    thread_id: UUID | None,
) -> UUID:
    """Persist one gathered series and hand back the id that addresses it.

    Written with a canvas of its own — a plain table — so the row is complete
    and openable on its own terms. A row whose ``canvas_spec`` was a placeholder
    would be a row the artifact endpoint could serve and the panel could not
    draw.
    """
    spec = CanvasSpec(
        title=str(params.get("field_id") or "Chuỗi số"),
        blocks=(
            CanvasBlock(
                widget="data_table",
                widget_version=1,
                frame="series",
                options={},
            ),
        ),
    )
    row = AgentArtifact(
        id=uuid4(),
        turn_id=turn_id,
        thread_id=thread_id,
        study_name=SERIES_KIND,
        study_version=1,
        params=dict(params),
        frames={"series": frame.to_payload()},
        canvas_spec=spec.to_payload(),
        provenance=provenance.to_payload(),
    )
    session.add(row)
    session.flush()
    return row.id


def read_frame(
    session: Session, reference: str, *, turn_id: UUID | None
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """One frame this Turn made, with the provenance it was made under.

    Both, because a block drawn from gathered numbers carries the same claim a
    Study's does — where these came from and when — and a caller that had to
    fetch the provenance separately would be a caller that could forget to.
    """
    artifact_id, _, name = reference.partition("#")
    try:
        identifier = UUID(artifact_id.strip())
    except (TypeError, ValueError):
        raise FrameNotAvailable(
            f"{reference!r} is not a frame id this turn produced"
        ) from None

    row = session.execute(
        select(AgentArtifact).where(AgentArtifact.id == identifier)
    ).scalar_one_or_none()
    # A frame from another Turn is refused as though it were not there. The id
    # is not a secret and must not be treated as one.
    if row is None or turn_id is None or row.turn_id != turn_id:
        raise FrameNotAvailable(f"{reference!r} is not a frame id this turn produced")

    frames = dict(row.frames or {})
    if name:
        frame = frames.get(name)
        if frame is None:
            raise FrameNotAvailable(
                f"{reference!r} names no frame; {artifact_id} holds "
                + ", ".join(sorted(frames))
            )
        return frame, dict(row.provenance or {})

    if len(frames) != 1:
        raise FrameNotAvailable(
            f"{artifact_id} holds {len(frames)} frames, so one has to be named: "
            + ", ".join(f"{artifact_id}#{key}" for key in sorted(frames))
        )
    return next(iter(frames.values())), dict(row.provenance or {})


def store_composition(
    session: Session,
    *,
    title: str,
    frames: Mapping[str, Mapping[str, Any]],
    blocks: tuple[Mapping[str, Any], ...],
    provenance: Mapping[str, Any],
    turn_id: UUID | None,
    thread_id: UUID | None,
) -> UUID:
    """Persist a canvas the model composed out of frames it had already made."""
    row = AgentArtifact(
        id=uuid4(),
        turn_id=turn_id,
        thread_id=thread_id,
        study_name=COMPOSITION_KIND,
        study_version=1,
        params={"title": title},
        frames={key: dict(value) for key, value in frames.items()},
        canvas_spec={"title": title, "blocks": [dict(block) for block in blocks]},
        provenance=dict(provenance),
    )
    session.add(row)
    session.flush()
    return row.id


def canvases_composed(session: Session, turn_id: UUID | None) -> int:
    """How many canvases this Turn has already composed."""
    if turn_id is None:
        return 0
    rows = session.execute(
        select(AgentArtifact.id).where(
            AgentArtifact.turn_id == turn_id,
            AgentArtifact.study_name == COMPOSITION_KIND,
        )
    ).scalars()
    return len(list(rows))


__all__ = [
    "COMPOSITION_KIND",
    "MAX_BLOCKS",
    "MAX_CANVASES_PER_TURN",
    "SERIES_KIND",
    "FrameNotAvailable",
    "canvases_composed",
    "read_frame",
    "store_composition",
    "store_series",
]
