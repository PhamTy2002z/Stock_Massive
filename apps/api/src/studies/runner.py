"""Validate, read, calculate, draw, persist — the one path a template runs.

A Study is no longer a function that computes and a function that draws. It is a
*plan*: a sequence of steps, and a board written against their names. This module
is what executes one, and everything in it exists so that the properties the
Signal Desk rests on hold for every Study rather than for the careful ones:

**A template has no private road.** Its reads go through the same reader chat
reads the store by (``agent/tools/query.py``, injected), its arithmetic goes
through the same sandbox and the same validator a model's ``compute`` does, and
its board compiles through the same composer ``render_signal_desk`` uses. There
is one renderer, one persistence path and one kind of artifact — so a picture a
Study draws and a picture a model composes cannot disagree about what a number
reads as.

**Every step is an artifact.** A plan of four steps writes four frame rows plus
one composition, and each frame row is addressable — which is what lets a model
that ran a template go on to re-mix one of its frames into a board of its own
(``render_signal_desk`` takes ``"<artifactId>#<step>"``).

**As-of is frozen once.** The instant is taken here, before the first step reads
anything, and written into every row. Re-opening a thread renders the artifacts,
never a recomputation — a picture that quietly moved is worse than a stale one,
because nothing on screen says it moved.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from src.stocks.signals.issues import SignalIssue
from src.stocks.universe import build_universe

from . import archetypes, composer, frames_buffer, grammar, lint
from .compute import frames_io, runner as compute_runner
from .contracts import (
    BoardSpec,
    ComputeStep,
    Frame,
    Provenance,
    QueryStep,
    ReadStep,
    Step,
    StoredArtifact,
    StudyContext,
    StudyDefinition,
    StudyRefused,
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

#: Reads one of the store's tables into a stamped frame.
#:
#: Injected for the reason the whole package is: ``src/studies`` is imported by
#: ``src/agent`` and imports nothing from it, and the readers live in
#: ``agent/tools/query.py``. Passing the function in is what lets a template use
#: *that* reader — the one a model's ``query`` call uses — rather than a second
#: copy of it here that would answer the same question differently the first
#: time either was fixed.
Read = Callable[..., Any]


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
    read: Read,
    turn_id: UUID | None = None,
    thread_id: UUID | None = None,
    warm: Warm | None = None,
    as_of: datetime | None = None,
) -> StoredArtifact:
    """Run a registered template and persist every frame it produced.

    ``turn_id`` and ``thread_id`` are optional because the runner is also driven
    outside a Turn — the smoke script, and any later precompute. An artifact
    with neither is reachable by id and by nothing else, which is exactly what a
    smoke run wants.

    ``as_of`` is the instant every row is frozen at. Supplied only by a caller
    that needs the run to be reproducible — the fixture builder both apps
    develop against, and any later precompute — and left at the clock
    otherwise, because a live question is asked now.

    ``warm`` runs after the parameters are validated and before the first step
    reads anything, so a question about a symbol the store has never held gets
    its bars fetched rather than a refusal that reads as a statement about the
    company. It runs inside the same session: the rows it writes are what the
    reads that follow see, and a caller that rolls back loses the fetch with the
    artifacts rather than keeping half of it.
    """
    definition = study(name)

    try:
        validated = definition.params_model.model_validate(dict(params))
    except ValidationError as error:
        raise StudyParamsInvalid(_readable(error)) from error

    context = StudyContext(
        params=validated,
        session=session,
        as_of=as_of or datetime.now(timezone.utc),
        universe=build_universe(session).symbols,
    )

    if definition.precheck is not None:
        definition.precheck(context)

    if warm is not None:
        warm(definition, context)

    frames, provenances, references = _execute(definition, context, read, turn_id, thread_id)

    board, spec, drawn, merged = _draw(
        definition, context, frames, provenances, references
    )

    artifact_id = frames_buffer.store_composition(
        session,
        title=board.title,
        frames=drawn,
        spec=spec.to_payload(),
        provenance=merged,
        turn_id=turn_id,
        thread_id=thread_id,
    )

    return StoredArtifact(
        id=artifact_id,
        study_name=definition.name,
        study_version=definition.version,
        headline=definition.headline(validated, frames),
        provenance=Provenance(
            source=composer.source_of(merged),
            as_of=context.as_of,
            sessions_used=int(merged.get("sessionsUsed") or 0),
            health=merged.get("health") or "normal",  # type: ignore[arg-type]
            reason=merged.get("reason"),
            method_notes=tuple(merged.get("methodNotes") or ()),
            query={"study": definition.name, "steps": list(definition.step_names)},
        ),
        signal_desk_spec=spec,
        # Handed over rather than stored: a model that ran a template can draw
        # one of its frames into a board of its own, and the ids are fresh every
        # run so a row carrying them could never be regenerated byte-for-byte.
        steps=references,
    )


# -- executing the plan ----------------------------------------------------


def _execute(
    definition: StudyDefinition,
    context: StudyContext,
    read: Read,
    turn_id: UUID | None,
    thread_id: UUID | None,
) -> tuple[
    dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]], dict[str, str]
]:
    """Every step, in order, each one filed as its own addressable artifact.

    Frames are carried forward as payloads rather than as :class:`Frame`
    objects, because that is what both consumers want: the sandbox is handed
    columns and rows, and the composer reads a payload. Building a ``Frame`` to
    take it apart again would be a conversion nothing asks for.
    """
    frames: dict[str, Mapping[str, Any]] = {}
    provenances: dict[str, Mapping[str, Any]] = {}
    references: dict[str, str] = {}

    for step in definition.plan:
        frame, provenance = _run_step(
            definition, step, context, read, frames, provenances
        )
        provenance = _with_declared_notes(step, provenance)
        if step.check is not None:
            step.check(frame, context)
        artifact_id = frames_buffer.store_frame(
            context.session,
            kind=(
                frames_buffer.COMPUTE_KIND
                if isinstance(step, ComputeStep)
                else frames_buffer.QUERY_KIND
            ),
            frame=frame,
            provenance=provenance,
            params={"study": definition.name, "step": step.name},
            title=step.title,
            turn_id=turn_id,
            thread_id=thread_id,
            name=step.name,
        )
        frames[step.name] = frame.to_payload()
        provenances[step.name] = provenance.to_payload()
        references[step.name] = f"{artifact_id}#{step.name}"

    return frames, provenances, references


def _with_declared_notes(step: Step, provenance: Provenance) -> Provenance:
    """The step's own notes about method, ahead of the engine's.

    Ahead rather than after, and it is the whole reason they are declared: the
    strip is capped, and what a cap should drop is "the calculation's code is
    ``a1b2c3``" rather than "the concentration zone is two adjacent bins of
    twenty". The first is a fact about this deployment; the second is what the
    number means.
    """
    if not step.method_notes:
        return provenance
    kept = [note for note in provenance.method_notes if note not in step.method_notes]
    return replace(provenance, method_notes=tuple(step.method_notes) + tuple(kept))


def _run_step(
    definition: StudyDefinition,
    step: Step,
    context: StudyContext,
    read: Read,
    frames: Mapping[str, Mapping[str, Any]],
    provenances: Mapping[str, Mapping[str, Any]],
) -> tuple[Frame, Provenance]:
    if isinstance(step, ReadStep):
        return step.read(context)

    if isinstance(step, QueryStep):
        try:
            result = read(
                context.session,
                source=step.source,
                symbols=list(step.symbols(context)),
                arguments=dict(step.arguments(context)),
                now=context.as_of,
            )
        except LookupError as unavailable:
            raise StudyRefused(
                SignalIssue.UNAVAILABLE,
                f"{definition.name}.{step.name}: {unavailable}",
            ) from unavailable
        return result.frame, result.provenance

    inputs = [frames[name] for name in step.inputs]
    constants = dict(step.constants(context))
    answer = compute_runner.run(
        code=step.code,
        frames=[frames_io.input_payload(frame) for frame in inputs],
        constants=constants,
        output_kind=step.output_kind,
        **({} if step.max_rows is None else {"max_rows": step.max_rows}),
        **({} if step.max_columns is None else {"max_columns": step.max_columns}),
    )
    if not answer.get("ok"):
        # A template whose calculation will not run is a bug in this repository,
        # not an answer for a reader — so it raises rather than refusing. The
        # code and the sandbox's own sentence travel with it, because the two
        # together are the whole diagnosis.
        raise RuntimeError(
            f"{definition.name}.{step.name} did not compute: "
            f"{answer.get('error')} — {answer.get('detail')}"
        )
    built = frames_io.frame_from_result(answer["frame"], inputs=inputs)
    if isinstance(built, str):
        raise RuntimeError(f"{definition.name}.{step.name} returned no frame: {built}")
    return built, frames_io.derived_provenance(
        provenances=[provenances[name] for name in step.inputs],
        rows=len(built.rows),
        code_digest=hashlib.sha256(step.code.encode("utf-8")).hexdigest()[:12],
        constants=constants,
        now=context.as_of,
    )


# -- drawing ---------------------------------------------------------------


def _draw(
    definition: StudyDefinition,
    context: StudyContext,
    frames: Mapping[str, Mapping[str, Any]],
    provenances: Mapping[str, Mapping[str, Any]],
    references: Mapping[str, str],
) -> tuple[grammar.Board, BoardSpec, dict[str, Mapping[str, Any]], dict[str, Any]]:
    """The template's board, compiled by the composer every board goes through.

    The rules are run rather than trusted, and a template that breaks one raises
    here. A model's board that breaks a rule gets a round to fix it; a
    template's is a fact about this repository, and the run that finds it is a
    test run.
    """
    board = grammar.parse(_titled(definition.board, context.params))
    violations = grammar.validate(board, frames)
    compiled = composer.compile_board(board, frames, provenances)
    violations.extend(archetypes.check(board.archetype, compiled.shapes))
    report = lint.score(compiled.sections, len(compiled.kpis))
    violations.extend(report.violations)
    if violations:
        raise RuntimeError(
            f"template {definition.name!r} composes a board that breaks its own "
            "rules: "
            + "; ".join(
                f"{violation.code} at {violation.where}" for violation in violations
            )
        )

    spec = BoardSpec(
        title=board.title,
        archetype=board.archetype or archetypes.DEFAULT,
        kpis=compiled.kpis,
        sections=compiled.sections,
        appendix=compiled.appendix,
        lint=report.to_payload(),
        auto_composed=False,
    )
    merged = composer.merged_provenance(
        [provenances[name] for name in definition.step_names]
    )
    return board, spec, compiled.frames, merged


def _titled(board: Mapping[str, Any], params: BaseModel) -> dict[str, Any]:
    """The board with its title filled in from the parameters, and nothing else.

    Only the title, deliberately. A caption's holes are ``{a}``…``{f}`` and are
    filled from *frames* by the composer; running the whole board through
    ``format`` would let a parameter reach a sentence without passing a cell,
    which is the one thing this track exists to prevent.
    """
    filled = dict(board)
    title = str(filled.get("title") or "")
    filled["title"] = title.format(**params.model_dump(mode="json"))
    return filled


def _readable(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'params'}: {item['msg']}"
        for item in error.errors()
    )


__all__ = ["Read", "StudyParamsInvalid", "Warm", "run"]
