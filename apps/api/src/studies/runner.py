"""Validate, compute, check, persist — the one path a Study runs through.

Everything here exists so that the two properties the Signal Desk rests on hold for
every Study rather than for the careful ones:

**The frames the browser gets are the frames the Study promised.** ``compute``
is checked against ``StudyDefinition.frames`` and every Signal Desk block against the
frames that came back. A ``view`` naming a frame that is not there fails on the
run that produced it, with both names in the message, instead of half-rendering
a panel.

**As-of is frozen once.** The instant is taken here, before ``compute`` reads
anything, and written into the row. Re-opening a thread renders the artifact,
never a recomputation — a picture that quietly moved is worse than a stale one,
because nothing on screen says it moved.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.alpha.models import AgentArtifact
from src.stocks.universe import build_universe

from . import widgets
from .contracts import (
    SignalDeskSpec,
    StoredArtifact,
    StudyContext,
    StudyDefinition,
    StudyResult,
)
from .registry import study

#: Makes a Study's declared inputs present before it reads the store.
#:
#: Injected rather than imported, because the module that implements it holds
#: the provider client: the suite, a smoke run and a live question should each
#: choose whether this call reaches the network, and a default of ``None`` means
#: the store is served exactly as it stands. ``tools/studies.py`` passes
#: ``warmup.warm``; nothing else does.
Warm = Callable[["StudyDefinition", "StudyContext"], None]


class StudyParamsInvalid(ValueError):
    """The model filled the parameters wrongly, and is told how.

    Its own type because the caller's response differs: a refusal
    (``StudyRefused``) is an answer to give a reader, and this is a call to make
    again. The pydantic message travels with it — a model that is told
    ``sessions must be <= 60`` fixes it on the next round; one told "invalid
    parameters" guesses.
    """


def run(
    name: str,
    params: Mapping[str, Any],
    *,
    session: Session,
    turn_id: UUID | None = None,
    thread_id: UUID | None = None,
    warm: Warm | None = None,
) -> StoredArtifact:
    """Run a registered Study and persist what it produced.

    ``turn_id`` and ``thread_id`` are optional because the runner is also driven
    outside a Turn — the smoke script, and any later precompute. An artifact
    with neither is reachable by id and by nothing else, which is exactly what a
    smoke run wants.

    ``warm`` runs after the parameters are validated and before ``compute``
    reads anything, so a question about a symbol the store has never held gets
    its bars fetched rather than a refusal that reads as a statement about the
    company. It runs inside the same session: the rows it writes are what the
    read that follows sees, and a caller that rolls back loses the fetch with
    the artifact rather than keeping half of it.
    """
    definition = study(name)

    try:
        validated = definition.params_model.model_validate(dict(params))
    except ValidationError as error:
        raise StudyParamsInvalid(_readable(error)) from error

    context = StudyContext(
        params=validated,
        session=session,
        as_of=datetime.now(timezone.utc),
        universe=build_universe(session).symbols,
    )

    if warm is not None:
        warm(definition, context)

    result = definition.compute(context)
    _check_frames_match_declaration(name, definition.frames, result)

    spec = definition.view(result)
    _check_signal_desk_draws_what_exists(name, spec, result, definition)

    row = AgentArtifact(
        id=uuid4(),
        turn_id=turn_id,
        thread_id=thread_id,
        study_name=definition.name,
        study_version=definition.version,
        params=validated.model_dump(mode="json"),
        frames={key: frame.to_payload() for key, frame in result.frames.items()},
        signal_desk_spec=spec.to_payload(),
        provenance=result.provenance.to_payload(),
    )
    session.add(row)
    session.flush()

    return StoredArtifact(
        id=row.id,
        study_name=definition.name,
        study_version=definition.version,
        headline=result.headline,
        provenance=result.provenance,
        signal_desk_spec=spec,
    )


def _readable(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'params'}: {item['msg']}"
        for item in error.errors()
    )


def _check_frames_match_declaration(
    name: str, declared: tuple[str, ...], result: StudyResult
) -> None:
    produced = set(result.frames)
    expected = set(declared)
    if produced != expected:
        missing = sorted(expected - produced)
        extra = sorted(produced - expected)
        raise RuntimeError(
            f"study {name!r} declared frames {sorted(expected)} but produced "
            f"{sorted(produced)}"
            + (f"; missing {missing}" if missing else "")
            + (f"; undeclared {extra}" if extra else "")
        )


def _check_signal_desk_draws_what_exists(
    name: str, spec: SignalDeskSpec, result: StudyResult, definition: StudyDefinition
) -> None:
    declared = set(definition.widgets)
    for block in spec.blocks:
        frame = result.frames.get(block.frame)
        if frame is None:
            raise RuntimeError(
                f"study {name!r} draws block {block.widget!r} from frame "
                f"{block.frame!r}, which it did not produce"
            )
        if (block.widget, block.widget_version) not in declared:
            raise RuntimeError(
                f"study {name!r} emitted undeclared widget {block.widget} "
                f"v{block.widget_version}"
            )
        if not widgets.accepts(block.widget, block.widget_version, frame.kind):
            raise RuntimeError(
                f"widget {block.widget} v{block.widget_version} cannot draw a "
                f"{frame.kind} frame ({block.frame!r} in study {name!r})"
            )


__all__ = ["StudyParamsInvalid", "Warm", "run"]
