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

from .contracts import SignalDeskBlock, SignalDeskSpec, Frame, Provenance

#: What a gathered series is filed under. Not a registered Study: nobody chose
#: this shape as a recipe, and it has no ``compute``. It is a name on a row, so
#: an operator reading the table can tell a composed picture from a Study's.
SERIES_KIND = "field_series"

#: What a table read straight out of the store is filed under. Its own name and
#: not ``SERIES_KIND``, for the reason that one has its own name: an operator
#: reading ``agent_artifact`` should be able to tell what kind of question made a
#: row without opening its params.
QUERY_KIND = "query_frame"

#: What a symbols-against-fields comparison is filed under.
COMPARE_KIND = "compare_frame"

#: What a calculation the model wrote is filed under. Its own kind and not
#: ``QUERY_KIND``, because the difference is the one a reader most needs: a query
#: frame is what the store holds and a computed frame is arithmetic somebody did
#: on it, and a row that could not say which is a row nobody can audit.
COMPUTE_KIND = "compute_frame"

#: What numbers read off a page somebody else published are filed under. Never
#: mixed with the three above: those are this deployment's own measurements and
#: this one is a claim it copied, and the badge a reader sees turns on exactly
#: that distinction.
EVIDENCE_KIND = "evidence_frame"

#: Every kind a frame may be filed under, and the check that a caller cannot
#: invent a sixth. Closed because the name is what an operator reads the table
#: by, and a typo would file a row under a kind nobody queries for.
FRAME_KINDS: frozenset[str] = frozenset(
    {SERIES_KIND, QUERY_KIND, COMPARE_KIND, COMPUTE_KIND, EVIDENCE_KIND}
)

#: What a Signal Desk the model composed is filed under, for the same reason.
COMPOSITION_KIND = "composed_signal_desk"

#: How many signal_desks one Turn may compose. Two, because a comparison is the
#: honest second picture and a third is a model drawing rather than answering.
MAX_SIGNAL_DESKS_PER_TURN = 2

# How large a board may be is three ceilings now, and they live in
# ``studies/grammar.py`` beside the rules they belong to: sections, blocks per
# section, and visuals across the whole board. One number here — ``MAX_BLOCKS``,
# six — counted every block the model named, at a time when every block was a
# picture. A board is three kinds of block with three different costs to a
# reader, and a single count cannot say that a fifth caption is worse than a
# fifth chart.


class FrameNotAvailable(LookupError):
    """The frame named is not one this Turn made, so it may not be drawn.

    One exception for "no such row", "a row from another Turn" and "a name that
    row does not hold", deliberately: they are the same answer to the caller and
    telling them apart would tell a model whether an id it guessed exists.
    """


def store_frame(
    session: Session,
    *,
    kind: str,
    frame: Frame,
    provenance: Provenance,
    params: Mapping[str, Any],
    title: str,
    turn_id: UUID | None,
    thread_id: UUID | None,
    name: str = "frame",
) -> UUID:
    """Persist one gathered frame and hand back the id that addresses it.

    Written with a Signal Desk of its own — a plain table — so the row is
    complete and openable on its own terms. A row whose ``signal_desk_spec`` was
    a placeholder would be a row the artifact endpoint could serve and the panel
    could not draw.

    ``kind`` and ``title`` are arguments rather than derived from ``params``,
    which is what the series-only version did: it read ``params["field_id"]`` for
    a title, and a table of eight quarters of two symbols has no field id to
    read. Deriving a title from whatever key happened to be there is how a panel
    ends up headed ``None``.

    ``name`` is the key the frame is filed under inside the row, and it is what
    ``read_frame`` resolves a bare id to. It defaults rather than being required
    because every caller here writes exactly one frame, and a scheme that made
    them all pass ``"frame"`` would be a required argument with one legal value.
    """
    if kind not in FRAME_KINDS:
        raise ValueError(
            f"{kind!r} is not a frame kind; use one of {', '.join(sorted(FRAME_KINDS))}"
        )
    spec = SignalDeskSpec(
        title=title,
        blocks=(
            SignalDeskBlock(
                widget="data_table",
                widget_version=1,
                frame=name,
                options={},
            ),
        ),
    )
    row = AgentArtifact(
        id=uuid4(),
        turn_id=turn_id,
        thread_id=thread_id,
        study_name=kind,
        study_version=1,
        params=dict(params),
        frames={name: frame.to_payload()},
        signal_desk_spec=spec.to_payload(),
        provenance=provenance.to_payload(),
    )
    session.add(row)
    session.flush()
    return row.id


def store_series(
    session: Session,
    *,
    frame: Frame,
    provenance: Provenance,
    params: Mapping[str, Any],
    turn_id: UUID | None,
    thread_id: UUID | None,
) -> UUID:
    """Persist one gathered series, under the name and title a series has.

    A thin wrapper over :func:`store_frame` and kept as one rather than inlined
    at its caller: ``"series"`` is the frame name every series row already on
    disk was written under, and a row read back by a name it was not written
    under is a row nothing can draw.
    """
    return store_frame(
        session,
        kind=SERIES_KIND,
        frame=frame,
        provenance=provenance,
        params=params,
        title=str(params.get("field_id") or "Chuỗi số"),
        turn_id=turn_id,
        thread_id=thread_id,
        name="series",
    )


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
    spec: Mapping[str, Any],
    provenance: Mapping[str, Any],
    turn_id: UUID | None,
    thread_id: UUID | None,
) -> UUID:
    """Persist a Signal Desk the model composed out of frames it had already made.

    ``spec`` is the whole ``signal_desk_spec`` payload rather than a list of
    blocks, because there are two spellings of one now and this layer is not the
    place that knows which. It writes the row; ``studies/contracts.py`` decides
    what a board is, and the version travels on the payload so a reader never has
    to infer it from which keys happen to be present.
    """
    row = AgentArtifact(
        id=uuid4(),
        turn_id=turn_id,
        thread_id=thread_id,
        study_name=COMPOSITION_KIND,
        study_version=1,
        params={"title": title},
        frames={key: dict(value) for key, value in frames.items()},
        signal_desk_spec=dict(spec),
        provenance=dict(provenance),
    )
    session.add(row)
    session.flush()
    return row.id


def frames_in_turn(
    session: Session, turn_id: UUID | None
) -> list[tuple[str, Mapping[str, Any], Mapping[str, Any]]]:
    """Every frame this Turn gathered, oldest first, with its provenance.

    The reference is spelled exactly the way the model would have spelled it —
    a bare id for a row holding one frame, ``id#name`` for a row holding
    several — so a board composed from this reads identically to a board the
    model composed by hand, and one function resolves both.

    Composed boards are excluded. They hold copies of frames that are already in
    this list under their own rows, and drawing a board out of a previous board's
    copies would draw every picture twice.
    """
    if turn_id is None:
        return []
    rows = session.execute(
        select(AgentArtifact)
        .where(
            AgentArtifact.turn_id == turn_id,
            AgentArtifact.study_name != COMPOSITION_KIND,
        )
        .order_by(AgentArtifact.created_at, AgentArtifact.id)
    ).scalars()

    out: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for row in rows:
        frames = dict(row.frames or {})
        provenance = dict(row.provenance or {})
        if len(frames) == 1:
            out.append((str(row.id), next(iter(frames.values())), provenance))
            continue
        for name in sorted(frames):
            out.append((f"{row.id}#{name}", frames[name], provenance))
    return out


def signal_desks_composed(session: Session, turn_id: UUID | None) -> int:
    """How many signal_desks this Turn has already composed."""
    if turn_id is None:
        return 0
    rows = session.execute(
        select(AgentArtifact.id).where(
            AgentArtifact.turn_id == turn_id,
            AgentArtifact.study_name == COMPOSITION_KIND,
        )
    ).scalars()
    return len(list(rows))


def frames_of_kind_in_turn(session: Session, turn_id: UUID | None, kind: str) -> int:
    """How many frames of one kind this Turn has already made.

    One function for every per-Turn ceiling rather than one per kind: the
    ceilings differ in their number and their reason, and none of them differs in
    how it is counted.
    """
    if turn_id is None:
        return 0
    rows = session.execute(
        select(AgentArtifact.id).where(
            AgentArtifact.turn_id == turn_id,
            AgentArtifact.study_name == kind,
        )
    ).scalars()
    return len(list(rows))


__all__ = [
    "COMPARE_KIND",
    "COMPUTE_KIND",
    "EVIDENCE_KIND",
    "COMPOSITION_KIND",
    "FRAME_KINDS",
    "frames_in_turn",
    "MAX_SIGNAL_DESKS_PER_TURN",
    "QUERY_KIND",
    "SERIES_KIND",
    "FrameNotAvailable",
    "frames_of_kind_in_turn",
    "signal_desks_composed",
    "read_frame",
    "store_composition",
    "store_frame",
    "store_series",
]
