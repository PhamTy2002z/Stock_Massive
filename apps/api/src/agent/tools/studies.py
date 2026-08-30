"""Asking for a picture instead of a figure.

``get_field`` hands the model one number. A question like *thanh khoản của STB
tập trung vào khung giờ nào* is not one number and never was: the honest answer
is seventeen buckets across thirty sessions, and no amount of asking for figures
one at a time assembles it. A **Study** is that answer as a recipe — named,
versioned, deterministic — and these two tools are how a model reaches one.

**The catalog arrives as a schema, not as prose.** ``run_study``'s own parameter
schema carries the enum of registered Study names, and its description carries
what each one answers. So a Study added later changes the tool signature, which
the resolved-surface cache already keys on, and changes nothing in the prompt —
no ``PROMPT_VERSION`` bump, no voided prefix, no new formatting hole in
``prompt/contract.py``.

**The parameters are flat, and that is the wire's doing rather than a
preference.** The natural shape is ``{name, params: {...}}``, and strict mode
restates every object with ``additionalProperties: false`` (``core/llm/
protocol.py``) — which turns a free-form ``params`` into an object that accepts
nothing at all. So every Study's parameters live side by side on one object,
:func:`_check_the_parameters_agree` refuses a build where two Studies disagree
about what a name means, and the handler passes each Study only the keys it
declared.

**What comes back is a headline and an id.** A template's frames — the matrix
the picture is drawn from — is persisted and served to the browser, and never
enters a message. That is not a size decision: a model handed thirty rows of
seventeen numbers reads the wrong cell and says so confidently, where a model
handed ``peakWindow`` and ``peakShare`` can only say what was measured.

**Trust: this reads the store, and the store's numbers are ours.** ``run_study``
can reach a provider — a symbol nobody has asked about has no bars until it does
— but what it hands the model is arithmetic this deployment performed over rows
it validated against a schema. Untrusted wrapping exists for *somebody else's
prose* arriving in the position the harness's own instructions occupy, and a
bucket average is not that. So ``reads_external=False``: no wrapper, and no
charge against the six external calls a Turn may make.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src import studies
from src.core.database import get_sync_db
from src.studies import (
    archetypes,
    auto_compose,
    composer,
    contracts,
    frames_buffer,
    grammar,
    lint,
    warmup,
    widgets,
)
from src.studies.contracts import StudyDefinition, StudyRefused
from src.studies.runner import StudyParamsInvalid

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolContext,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
    register,
)
from . import query

TOOLSET = "studies"

#: Where a runaway result is cut. A bug-stop rather than a budget, the same way
#: ``tools/signals.py`` sets its own: the largest honest answer either tool gives
#: is the catalog, which is a few kilobytes, and a headline is budgeted at three
#: hundred tokens by the Study that wrote it.
MAX_RESULT_CHARS = 32_000

#: The argument naming which Study to run. Reserved: no Study may declare a
#: parameter under it, because the flattening below would then have two meanings
#: for one key.
STUDY_ARGUMENT = "name"

#: How many Turns a process remembers having already refused a board for. A
#: bound rather than a lifetime: the question ("has this Turn had its one round
#: to fix a board?") is meaningless once the Turn ends, and a process that served
#: a hundred thousand Turns should not still be holding the first one's id.
REJECTED_TURNS_REMEMBERED = 512

RENDER_SIGNAL_DESK_DESCRIPTION = (
    "Compose the board for this answer out of frames you gathered earlier in the "
    "same turn with query, compare_fields, compute, get_series, run_study or "
    "frame_from_evidence. You write the structure — a strip of 3 to 6 leading "
    "figures, one to four sections of visuals, at most one caption per section, "
    "an optional appendix table. You never write a market number: every figure is "
    "a reference to one cell, {frame_id, column, and either row or "
    "row_where:\"column=value\"}, and the server looks it up and formats it. A "
    "caption is a sentence with {a}..{f} where its numbers go; a digit typed into "
    "a caption — a year included — is refused. Leave widget out and the shape of "
    "the frame decides the picture; name one only when the question calls for a "
    "different reading of the same numbers. A board that breaks a rule comes back "
    "with the rules it broke, named, so you can send it again."
)

#: The widgets a model may name, and what each is for.
#:
#: Built from the same catalog the Studies are checked against, so a widget
#: added for a Study is composable the moment it exists and a widget retired
#: stops being offered without a second list to remember.
def _ref_schema(what: str) -> dict[str, Any]:
    """One cell, as a model can name it without ever seeing the numbers.

    Written out at each use rather than referenced through ``$defs``: the strict
    restatement (``core/llm/protocol.py``) walks ``properties`` and ``items``
    only, so a definition behind a ``$ref`` would reach the route without
    ``additionalProperties`` on it and be refused before a token is generated.

    **The fields carry no descriptions of their own, and that is a measurement.**
    Eight of these travel on one schema — two per KPI, six per caption — so a
    sentence per field is eight copies of it. Described once, they cost 2,580
    tokens against the 763 of the block list they replace; bare, with the meaning
    stated once in the tool's own description where it is read once, they cost a
    third of that. The rules are all still here: what is trimmed is the prose,
    never a constraint.
    """
    return {
        "type": "object",
        "description": what + " Give row or row_where, not both.",
        "properties": {
            "frame_id": {"type": "string"},
            "column": {"type": "string"},
            "row": {"type": "integer"},
            "row_where": {"type": "string"},
        },
        "required": ["frame_id", "column"],
        "additionalProperties": False,
    }


#: Widgets that are not a picture a model may ask for.
#:
#: ``kpi_strip`` and ``caption`` are block kinds of the board rather than
#: drawings of a frame — the model reaches them by writing a KPI or a caption,
#: and naming one as a visual's widget is a category error the grammar would
#: have to refuse anyway. ``data_table`` is refused by name
#: (``table_not_in_appendix``). Offering the three would be offering three
#: choices whose only outcome is a violation.
_NOT_A_VISUAL: frozenset[str] = frozenset({"kpi_strip", "caption", "data_table"})


def render_signal_desk_schema() -> dict[str, Any]:
    """The board: a strip of figures, sections of blocks, and an appendix."""
    names = sorted(
        {name for name, _ in widgets.CATALOG if name not in _NOT_A_VISUAL}
    )
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "minLength": 1,
                "description": "What the board is called, in the reader's language.",
            },
            "archetype": {
                "type": "string",
                "enum": sorted(grammar.ARCHETYPES),
                "description": (
                    "The kind of question: compare, profile, screen, timeline, "
                    "decompose. Omit for profile."
                ),
            },
            "kpis": {
                "type": "array",
                "minItems": grammar.MIN_KPIS,
                "maxItems": grammar.MAX_KPIS,
                "description": (
                    f"The {grammar.MIN_KPIS}-{grammar.MAX_KPIS} figures leading "
                    "the board."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "maxLength": grammar.KPI_LABEL_LIMIT,
                            "description": "What it is, in the reader's language.",
                        },
                        "value": _ref_schema("The cell this figure is."),
                        "delta": _ref_schema("A change shown beside it. Optional."),
                        "role": {
                            "type": "string",
                            "enum": sorted(contracts.PLAIN_ROLES),
                            "description": "What it means, for colour. Optional.",
                        },
                    },
                    "required": ["label", "value"],
                    "additionalProperties": False,
                },
            },
            "sections": {
                "type": "array",
                "minItems": 1,
                "maxItems": grammar.MAX_SECTIONS,
                "description": (
                    f"Up to {grammar.MAX_SECTIONS} sections, in reading order."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "blocks": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": grammar.MAX_BLOCKS_PER_SECTION,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "kind": {
                                        "type": "string",
                                        "enum": ["visual", "caption"],
                                        "description": "A picture, or a sentence.",
                                    },
                                    "frame_id": {"type": "string"},
                                    "widget": {
                                        "type": "string",
                                        "enum": names,
                                        "description": _widget_guide(),
                                    },
                                    "columns": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "visual: only these columns.",
                                    },
                                    "template": {
                                        "type": "string",
                                        "maxLength": grammar.CAPTION_LIMIT,
                                        "description": (
                                            "caption: one sentence with {a}..{f} "
                                            "where its figures go. No digits."
                                        ),
                                    },
                                    "refs": {
                                        "type": "object",
                                        "description": "caption: a cell per {key} used.",
                                        "properties": {
                                            key: _ref_schema(f"Cell {{{key}}}.")
                                            for key in grammar.REF_KEYS
                                        },
                                        "required": [],
                                        "additionalProperties": False,
                                    },
                                },
                                "required": ["kind"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["blocks"],
                    "additionalProperties": False,
                },
            },
            "appendix_frame_id": {
                "type": "string",
                "description": (
                    "One frame as a plain table at the end — the only place a "
                    "table belongs. Optional."
                ),
            },
        },
        "required": ["title", "kpis", "sections"],
        "additionalProperties": False,
    }


def _widget_guide() -> str:
    """One line per drawable widget: its name and what it is for.

    The three that are not drawings of a frame are left out for the reason the
    enum leaves them out — a line describing a choice that is always a violation
    is a line spent teaching a mistake.
    """
    seen: dict[str, str] = {}
    for (name, _version), entry in widgets.CATALOG.items():
        if name in _NOT_A_VISUAL:
            continue
        seen.setdefault(name, entry.purpose)
    return "Optional. Leave out and the frame's shape decides. " + "; ".join(
        f"{name} — {purpose}" for name, purpose in sorted(seen.items())
    )


def summarise_render_signal_desk(arguments: Mapping[str, Any]) -> str:
    """The rail row for a composed board: its title and how many blocks."""
    title = str(arguments.get("title") or "").strip()
    sections = arguments.get("sections")
    count = 0
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, Mapping) and isinstance(section.get("blocks"), list):
                count += len(section["blocks"])
    span = f" · {count} khối" if count else ""
    return f"Vẽ signal_desk: {title}{span}" if title else f"Vẽ signal_desk{span}"


SessionOpener = Callable[[], Any]


def study_parameters() -> dict[str, dict[str, Any]]:
    """Every registered Study's parameters, side by side on one object.

    Derived from the pydantic models rather than written out, so a Study that
    adds a parameter is callable the moment it is registered. Descriptions are
    prefixed with the Studies that accept the key, because on one flat object
    the model cannot otherwise tell which parameter belongs to what it asked for.

    **Where two Studies describe one key differently, both descriptions travel.**
    They may legitimately share a name with different ranges, and keeping only
    the first would tell the model the second Study's range is the first's —
    which it would then respect, and be silently clamped for.
    """
    merged: dict[str, dict[str, Any]] = {}
    owners: dict[str, list[str]] = {}
    described: dict[str, dict[str, list[str]]] = {}
    for definition in _registered():
        schema = definition.params_schema
        for name, property_schema in (schema.get("properties") or {}).items():
            owners.setdefault(name, []).append(definition.name)
            merged.setdefault(name, dict(property_schema))
            text = str(property_schema.get("description") or "").strip()
            described.setdefault(name, {}).setdefault(text, []).append(
                definition.name
            )
    for name, schema in merged.items():
        readings = described[name]
        if len(readings) == 1:
            text = next(iter(readings))
            schema["description"] = f"[{', '.join(owners[name])}] {text}".strip()
        else:
            schema["description"] = " · ".join(
                f"[{', '.join(studies_named)}] {text}".strip()
                for text, studies_named in readings.items()
            )
        # Nothing is required on this object except the Study's name: a
        # parameter that is mandatory for one Study is meaningless for the next,
        # and a schema that said otherwise would refuse every other call.
        schema.pop("default", None)
    return merged


def run_study_schema() -> dict[str, Any]:
    """The argument object, with the registered names as an enum."""
    names = [definition.name for definition in _registered()]
    return {
        "type": "object",
        "properties": {
            STUDY_ARGUMENT: {
                "type": "string",
                "enum": names,
                "description": "Which Study to run, exactly as it is named here.",
            },
            **study_parameters(),
        },
        "required": [STUDY_ARGUMENT],
        "additionalProperties": False,
    }


def run_study_description() -> str:
    """What ``run_study`` is for, and one line per Study it can run.

    The per-Study lines are here rather than behind ``list_studies`` on purpose:
    the chain worth reaching is one round of ``run_study`` and one of prose, and
    a model that has to look up a catalog before it can choose has spent a round
    on a list of one. ``list_studies`` stays for the catalog that is long enough
    to be worth reading.
    """
    lines = [
        "Run one Study — a named, versioned analysis recipe computed from this "
        "system's own store — and get back the headline figures plus the id of "
        "the Signal Desk it produced. Use it whenever the honest answer is a shape "
        "over time or across buckets rather than a single number: a session "
        "profile, a distribution, a ranking, anything a reader would want drawn. "
        "The reader is shown the whole picture; you are shown the headline, "
        "which is everything a sentence can honestly say about it. Read the "
        "list below against what was actually asked rather than against the "
        "words used to ask it: a study's question is written to cover the "
        "several ways a reader phrases the same one.",
        "",
        "Available studies:",
    ]
    for definition in _registered():
        lines.append(
            f"- {definition.name} — {definition.question} "
            f"Parameters: {_parameter_summary(definition)}."
        )
    return "\n".join(lines)


LIST_STUDIES_DESCRIPTION = (
    "List every Study this system can run, with the question each one answers "
    "and the parameters it takes. run_study already names them, so reach for "
    "this only when you want the full parameter schema of one before calling it."
)

LIST_STUDIES_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}


def _registered() -> tuple[StudyDefinition, ...]:
    """Every Study, by name, so the schema and the prefix cache do not move."""
    return tuple(
        studies.REGISTRY[name] for name in sorted(studies.REGISTRY)
    )


def _parameter_summary(definition: StudyDefinition) -> str:
    """One sentence naming a Study's parameters and which are mandatory."""
    schema = definition.params_schema
    required = set(schema.get("required") or ())
    parts = [
        f"{name} (required)" if name in required else name
        for name in (schema.get("properties") or {})
    ]
    return ", ".join(parts) if parts else "none"


def _params_for(
    definition: StudyDefinition, arguments: Mapping[str, Any]
) -> dict[str, Any]:
    """The keys this Study declared, taken off the flat argument object.

    Filtered rather than passed whole: pydantic ignores a key it does not know,
    so passing everything would silently drop a parameter aimed at the wrong
    Study, and the model would read a default as though it were its own value.
    A ``None`` is dropped too — strict mode makes every optional property
    nullable, so ``null`` is how the wire spells "not this call".
    """
    declared = set((definition.params_schema.get("properties") or {}))
    return {
        name: value
        for name, value in arguments.items()
        if name in declared and value is not None
    }


def summarise_run_study(arguments: Mapping[str, Any]) -> str:
    """The rail row: which analysis, for which company, over how long.

    Composed rather than taken from one argument, for the reason ``get_field``
    composes its own: the Study alone reads the same for every symbol, and the
    symbol alone does not say what was computed.
    """
    name = str(arguments.get(STUDY_ARGUMENT) or "").strip()
    definition = studies.REGISTRY.get(name)
    label = definition.display_name if definition is not None else "phân tích"
    detail = []
    symbol = str(arguments.get("symbol") or "").strip().upper()
    if symbol:
        detail.append(symbol)
    sessions = arguments.get("sessions")
    if isinstance(sessions, int):
        detail.append(f"{sessions} phiên")
    return f"{label}: {' · '.join(detail)}" if detail else label


def summarise_list_studies(_arguments: Mapping[str, Any]) -> str:
    return "Xem danh mục phân tích"



logger = logging.getLogger(__name__)

class ArtifactNotStored(RuntimeError):
    """The numbers were computed and the store would not take them.

    Its own type, and its message says nothing but that, because of where the
    message ends up. ``executor`` renders a failed tool call as ``f"{name}
    failed: {exc}"`` and hands that text to the model — and a SQLAlchemy error
    stringifies to the statement **and its bound parameters**, which for this
    write is the whole ``frames`` payload. The rule that frames never enter a
    message the model sees would then hold only while the database was healthy.
    So the driver's text is logged and never re-raised.
    """


@contextmanager
def _artifact_write(what: str) -> Iterator[None]:
    """Let a store failure end the call without the payload riding along."""
    try:
        yield
    except SQLAlchemyError as exc:
        # ``orig`` is the driver's own error — a constraint name or a connection
        # message — without SQLAlchemy's rendered statement and parameters.
        driver = getattr(exc, "orig", None) or exc.__class__.__name__
        logger.warning("Storing the %s artifact failed: %s", what, driver)
        raise ArtifactNotStored(f"the {what} artifact could not be stored") from exc


class StudyTools:
    """List the recipes, and run one of them into an artifact."""

    def __init__(self, *, session_opener: SessionOpener = get_sync_db) -> None:
        # Opened and closed around one run, like the signal tools': a session is
        # not a trusted fact and does not travel in ``ToolContext``. It matters
        # more here than there, because this one writes: the artifact and the
        # bars fetched for it commit together or not at all.
        self._session_opener = session_opener
        # Which Turns have already spent their one round to fix a board. A dict
        # rather than a set because insertion order is what makes the bound
        # cheap to enforce: the oldest key is the first one.
        self._rejected: dict[str, None] = {}

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name="list_studies",
                toolset=TOOLSET,
                description=LIST_STUDIES_DESCRIPTION,
                schema=LIST_STUDIES_SCHEMA,
                handler=self.list_studies,
                display_name="Xem danh mục phân tích",
                summarise=summarise_list_studies,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.SERIALIZED,
                contract_version="1",
                # A registry read: no session, no socket, nothing to move off
                # the event loop.
                is_async=True,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
            ToolEntry(
                name="run_study",
                toolset=TOOLSET,
                description=run_study_description(),
                schema=run_study_schema(),
                handler=self.run_study,
                display_name="Chạy phân tích",
                summarise=summarise_run_study,
                # ``READ`` is about this system's evidence rather than about the
                # row: an artifact is the answer written down, and running the
                # same Study twice with the same parameters produces the same
                # numbers under a second id. Nothing a reader holds changes.
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                # Serialized because it writes a row and may fetch bars; two
                # overlapping calls for one symbol would each fetch the same
                # year of buckets.
                concurrency=ToolConcurrency.SERIALIZED,
                contract_version="1",
                # A synchronous session and, on a cold symbol, a provider call.
                # ``False`` puts it on a worker thread rather than letting one
                # ingest stall every other Turn this process is streaming.
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
            ToolEntry(
                name="render_signal_desk",
                toolset=TOOLSET,
                description=RENDER_SIGNAL_DESK_DESCRIPTION,
                schema=render_signal_desk_schema(),
                handler=self.render_signal_desk,
                display_name="Vẽ signal_desk",
                summarise=summarise_render_signal_desk,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.SERIALIZED,
                contract_version="1",
                # Reads rows and writes one. No network, but a synchronous
                # session all the same.
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
        )

    async def list_studies(
        self, _context: ToolContext, _arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        catalog = [
            {
                **entry,
                # Whether the inputs this Study names can be made present at
                # all. Registration already refuses one that names an input
                # nothing fetches, so this is ``True`` for everything listed —
                # and it is listed anyway, because the day a Study depends on a
                # feed a deployment has switched off, the answer changes here
                # rather than in a refusal a reader has to interpret.
                "inputsReachable": all(
                    warmup.known(name) for name in entry.get("requires", ())
                ),
            }
            for entry in studies.catalog()
        ]
        return {"count": len(catalog), "studies": catalog}

    def run_study(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        name = str(arguments.get(STUDY_ARGUMENT) or "").strip()
        if not name:
            raise ValueError(
                f"{STUDY_ARGUMENT} must name a registered study; the registered "
                f"names are {', '.join(sorted(studies.REGISTRY))}"
            )
        definition = studies.REGISTRY.get(name)
        if definition is None:
            # Raised rather than returned, like ``get_field``'s unknown field:
            # the model asked for something that does not exist, and a refused
            # result would tell it the store had looked.
            raise ValueError(
                f"{name!r} is not a registered study. The registered names are "
                f"{', '.join(sorted(studies.REGISTRY))}."
            )

        with self._open() as session:
            # The same ceiling ``render_signal_desk`` answers to, and it is new
            # here only because a template's board is now a composition like any
            # other. Before the port a Study wrote a row under its own name and
            # this count never saw it, so a Turn could draw two composed boards
            # *and* four Studies. Two boards a Turn is a claim about what a
            # reader can take in, and it does not depend on who drew them.
            already = frames_buffer.signal_desks_composed(session, context.turn_id)
            if already >= frames_buffer.MAX_SIGNAL_DESKS_PER_TURN:
                return {
                    "error": "cannot_read",
                    "detail": (
                        f"this turn has already drawn {already} boards, which is "
                        "the most it may draw"
                    ),
                }

            try:
                with _artifact_write(name):
                    artifact = studies.run(
                        name,
                        _params_for(definition, arguments),
                        session=session,
                        # The reader a model's own ``query`` call uses. Passed in
                        # rather than imported by the runner, because
                        # ``src/studies`` is imported by this package and imports
                        # nothing from it — and a template reading the store by a
                        # second road is a template whose numbers could differ
                        # from the same question asked in chat.
                        read=query.read_source,
                        turn_id=context.turn_id,
                        thread_id=context.thread_id,
                        warm=warmup.warm,
                    )
            except StudyParamsInvalid as invalid:
                raise ValueError(
                    f"{name} cannot run with those parameters — {invalid}"
                ) from invalid
            except StudyRefused as refused:
                # Every step that ran before the refusal wrote a frame row, and a
                # plan that stops halfway leaves them behind: this method returns
                # rather than raises, so the session would commit on the way out.
                # They are not merely litter — ``auto_compose_for_turn`` draws
                # *every* frame a Turn gathered, so a Study that declined to
                # answer would end the Turn as a board built out of its offcuts.
                # Rolling back loses the warm fetch too, which is the trade the
                # runner already documents: half a run is not a thing to keep.
                session.rollback()
                # The Study ran and has no numbers, which is an answer rather
                # than a failure. It comes back as a result so the model relays
                # the reason instead of reading a raise as the tool being broken.
                return {
                    "studyName": name,
                    "studyVersion": definition.version,
                    "issue": refused.issue.value,
                    "detail": refused.detail,
                }

            return {
                "studyName": artifact.study_name,
                "studyVersion": artifact.study_version,
                # What the browser fetches the picture by. The model is given it
                # so it can say a Signal Desk exists, and it has no way to read one.
                "artifactId": str(artifact.id),
                "title": artifact.signal_desk_spec.title,
                "blockCount": artifact.signal_desk_spec.block_count,
                "kpiCount": len(artifact.signal_desk_spec.kpis),
                # Never, for a template: a board written by hand and checked at
                # import is the opposite of the case ``autoComposed`` marks.
                # Stated anyway so the browser reads one shape from both roads.
                "autoComposed": False,
                # Each step's frame, addressable. A model that ran a template
                # and wants one of its numbers beside something it fetched can
                # draw the step rather than re-derive it.
                "frames": dict(artifact.steps),
                "headline": dict(artifact.headline),
                "provenance": _provenance_for_model(artifact.provenance.to_payload()),
            }

    def render_signal_desk(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Compile the board the model composed, or say exactly what is wrong.

        **The whole board passes or none of it does, which is the opposite of
        what this used to do.** The old tool dropped a block it could not draw
        and kept the rest, because a block was an independent picture and losing
        one cost one. A board is not independent blocks: the strip is a claim
        about the sections under it, and a section silently missing turns a
        comparison into a profile of whichever side survived. So a violation is
        the whole answer, named, and the model gets a round to fix it.

        **The second failure is answered by drawing rather than by refusing.**
        A ``signal_desk`` Turn that ends in prose is the failure the mode exists
        to prevent, and two rounds spent on grammar is a model that will not get
        there. So the server composes a board from the same frames and stamps it
        ``autoComposed`` — worse than the model's, and infinitely better than a
        paragraph.

        **Ownership is the Turn.** Every frame is checked against the Turn that
        made it (``studies/frames_buffer.py``), so an id from another
        conversation draws nothing here.
        """
        try:
            board = grammar.parse(arguments)
        except grammar.BoardMalformed as malformed:
            raise ValueError(str(malformed)) from malformed

        with self._open() as session:
            already = frames_buffer.signal_desks_composed(session, context.turn_id)
            if already >= frames_buffer.MAX_SIGNAL_DESKS_PER_TURN:
                return {
                    "error": "cannot_read",
                    "detail": (
                        f"this turn has already drawn {already} boards, which is "
                        "the most it may draw"
                    ),
                }

            # Every frame the board names, fetched once. A reference the Turn
            # does not own comes back missing rather than raising, so the rule it
            # breaks is a named violation like every other one.
            payloads: dict[str, Mapping[str, Any]] = {}
            sources: dict[str, Mapping[str, Any]] = {}
            unavailable: list[Mapping[str, str]] = []
            for reference in grammar.frame_references(board):
                try:
                    payload, provenance = frames_buffer.read_frame(
                        session, reference, turn_id=context.turn_id
                    )
                except frames_buffer.FrameNotAvailable as missing:
                    unavailable.append(
                        {"frame_id": reference, "reason": str(missing)}
                    )
                    continue
                payloads[reference] = payload
                sources[reference] = provenance

            violations = grammar.validate(board, payloads)
            compiled = composer.compile_board(board, payloads, sources)
            violations.extend(archetypes.check(board.archetype, compiled.shapes))
            report = lint.score(compiled.sections, len(compiled.kpis))
            violations.extend(report.violations)

            if violations:
                if not self._spend_the_retry(context.turn_id):
                    return {
                        "error": "board_rejected",
                        "detail": (
                            "the board breaks the rules below; send it again with "
                            "them fixed"
                        ),
                        "violations": [
                            violation.to_payload() for violation in violations
                        ],
                        "unavailableFrames": unavailable,
                    }
                composed = self._auto_compose(session, context, title=board.title)
                if composed is None:
                    return {
                        "error": "board_rejected",
                        "detail": (
                            "the board breaks the rules below and this turn has "
                            "gathered no frame the server could draw instead"
                        ),
                        "violations": [
                            violation.to_payload() for violation in violations
                        ],
                        "unavailableFrames": unavailable,
                    }
                return composed

            spec = contracts.BoardSpec(
                title=board.title,
                archetype=board.archetype or archetypes.DEFAULT,
                kpis=compiled.kpis,
                sections=compiled.sections,
                appendix=compiled.appendix,
                lint=report.to_payload(),
                auto_composed=False,
            )
            provenance = composer.merged_provenance(
                [sources[reference] for reference in payloads]
            )
            with _artifact_write(frames_buffer.COMPOSITION_KIND):
                artifact_id = frames_buffer.store_composition(
                    session,
                    title=board.title,
                    frames=compiled.frames,
                    spec=spec.to_payload(),
                    provenance=provenance,
                    turn_id=context.turn_id,
                    thread_id=context.thread_id,
                )

        return {
            "studyName": frames_buffer.COMPOSITION_KIND,
            "studyVersion": 1,
            "artifactId": str(artifact_id),
            "title": board.title,
            "blockCount": spec.block_count,
            "kpiCount": len(spec.kpis),
            "autoComposed": False,
            "lint": report.to_payload(),
            "provenance": _provenance_for_model(provenance),
        }

    def _spend_the_retry(self, turn_id: Any) -> bool:
        """Whether this Turn has already had its one round to fix a board.

        Held in memory rather than in a row, and bounded, because the question
        is about the *conversation in flight* — a Turn that ended never asks it
        again, and a row written to answer it would outlive the only moment it
        means anything. The bound is what keeps a long-lived process from
        remembering every Turn it ever served.
        """
        if turn_id is None:
            return False
        key = str(turn_id)
        if key in self._rejected:
            return True
        self._rejected[key] = None
        while len(self._rejected) > REJECTED_TURNS_REMEMBERED:
            self._rejected.pop(next(iter(self._rejected)))
        return False

    def _auto_compose(
        self, session: Session, context: ToolContext, *, title: str | None = None
    ) -> Mapping[str, Any] | None:
        """Draw every frame this Turn gathered, and say the server drew it."""
        gathered = frames_buffer.frames_in_turn(session, context.turn_id)
        composed = auto_compose.compose(
            gathered, title=title or auto_compose.DEFAULT_TITLE
        )
        if composed is None:
            return None
        spec, frames = composed
        provenance = composer.merged_provenance(
            [provenance for _reference, _payload, provenance in gathered]
        )
        with _artifact_write(frames_buffer.COMPOSITION_KIND):
            artifact_id = frames_buffer.store_composition(
                session,
                title=spec.title,
                frames=frames,
                spec=spec.to_payload(),
                provenance=provenance,
                turn_id=context.turn_id,
                thread_id=context.thread_id,
            )
        return {
            "studyName": frames_buffer.COMPOSITION_KIND,
            "studyVersion": 1,
            "artifactId": str(artifact_id),
            "title": spec.title,
            "blockCount": spec.block_count,
            "kpiCount": len(spec.kpis),
            "autoComposed": True,
            "provenance": _provenance_for_model(provenance),
        }

    @contextmanager
    def _open(self) -> Iterator[Session]:
        with self._session_opener() as session:
            yield session


def _provenance_for_model(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """The provenance as the model reads it: without the method notes.

    The notes are for the reader who opens "Cách tính" under a picture. The
    model is owed the headline and the strip — as-of, sessions, health, one
    reason — inside a budget of roughly three hundred tokens, and five sentences
    of method per Study would spend most of it on something the model cannot
    act on. The artifact keeps them; the browser draws them.
    """
    return {key: value for key, value in provenance.items() if key != "methodNotes"}


def auto_compose_for_turn(
    turn_id: Any,
    thread_id: Any,
    *,
    session_opener: SessionOpener = get_sync_db,
) -> Mapping[str, Any] | None:
    """Draw what a ``signal_desk`` Turn gathered, when it composed nothing itself.

    The loop's one hook, and it lives here rather than there for the reason
    every store read does: ``agent/loop.py`` opens no sessions and knows no
    tables, and a Turn's frames are rows. What the loop passes in is two ids and
    what it gets back is the same announcement payload ``render_signal_desk``
    returns, so :func:`messages.signal_desk_of` reads one shape either way.

    Synchronous, because the session is. The caller puts it on a thread.
    """
    tools = StudyTools(session_opener=session_opener)
    context = ToolContext(turn_id=turn_id, thread_id=thread_id)
    with tools._open() as session:
        if (
            frames_buffer.signal_desks_composed(session, turn_id)
            >= frames_buffer.MAX_SIGNAL_DESKS_PER_TURN
        ):
            return None
        return tools._auto_compose(session, context)


def _check_the_parameters_agree() -> None:
    """Refuse a build where two Studies mean different things by one key.

    The flat argument object is what strict mode leaves available, and its cost
    is exactly this: ``sessions`` is one property on one schema, so two Studies
    declaring it with different types would put one of them on the wire wrongly
    and the model would be told a lie about what it may send. Names may be
    shared — that is the point of a shared vocabulary — but a shared name has to
    be the same thing.

    Checked at import so it fails where the second Study is written, rather than
    on the first question that happens to use the disputed key.
    """
    seen: dict[str, tuple[str, Any]] = {}
    for definition in _registered():
        properties = definition.params_schema.get("properties") or {}
        if STUDY_ARGUMENT in properties:
            raise ValueError(
                f"study {definition.name!r} declares a parameter named "
                f"{STUDY_ARGUMENT!r}, which is the argument that says which "
                "study to run"
            )
        for key, schema in properties.items():
            kind = schema.get("type") or schema.get("anyOf") or schema.get("$ref")
            owner, previous = seen.get(key, (definition.name, kind))
            if previous != kind:
                raise ValueError(
                    f"studies {owner!r} and {definition.name!r} both declare a "
                    f"parameter {key!r} and disagree about its type ({previous!r} "
                    f"against {kind!r}); one flat argument object cannot carry both"
                )
            seen[key] = (owner, kind)


_check_the_parameters_agree()


def register_study_tools(**kwargs: Any) -> tuple[ToolEntry, ...]:
    """Register both study tools and hand the registrations back to the caller."""
    tools = StudyTools(**kwargs)
    return tuple(register(entry) for entry in tools.entries())


__all__ = [
    "LIST_STUDIES_DESCRIPTION",
    "auto_compose_for_turn",
    "REJECTED_TURNS_REMEMBERED",
    "RENDER_SIGNAL_DESK_DESCRIPTION",
    "LIST_STUDIES_SCHEMA",
    "MAX_RESULT_CHARS",
    "STUDY_ARGUMENT",
    "TOOLSET",
    "StudyTools",
    "register_study_tools",
    "render_signal_desk_schema",
    "run_study_description",
    "run_study_schema",
    "study_parameters",
    "summarise_list_studies",
    "summarise_render_signal_desk",
    "summarise_run_study",
]
