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

**What comes back is a headline and an id.** ``StudyResult.frames`` — the matrix
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
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src import studies
from src.core.database import get_sync_db
from src.studies import frames_buffer, warmup, widgets
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

RENDER_SIGNAL_DESK_DESCRIPTION = (
    "Draw a Signal Desk out of frames you gathered earlier in this same turn with "
    "get_series or run_study. Each block names a widget and one frameId; the "
    "server picks the widget's version and its presentation. A block it cannot "
    "draw is dropped with the reason and the rest of the Signal Desk is still shown, "
    "so a mistake in one block costs one block. Use it when there is no study "
    "for the question and you have gathered the numbers yourself."
)

#: The widgets a model may name, and what each is for.
#:
#: Built from the same catalog the Studies are checked against, so a widget
#: added for a Study is composable the moment it exists and a widget retired
#: stops being offered without a second list to remember.
def render_signal_desk_schema() -> dict[str, Any]:
    """The argument object: a title, and the blocks in the order they read."""
    names = sorted({name for name, _ in widgets.CATALOG})
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "minLength": 1,
                "description": "What the panel is called, in the reader's language.",
            },
            "blocks": {
                "type": "array",
                "minItems": 1,
                "maxItems": frames_buffer.MAX_BLOCKS,
                "description": (
                    f"Up to {frames_buffer.MAX_BLOCKS} blocks, in the order a "
                    "reader meets them."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "widget": {
                            "type": "string",
                            "enum": names,
                            "description": _widget_guide(),
                        },
                        "frame_id": {
                            "type": "string",
                            "minLength": 1,
                            "description": (
                                "A frameId from get_series, or an artifactId "
                                "from run_study with #frameName appended."
                            ),
                        },
                    },
                    "required": ["widget", "frame_id"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "blocks"],
        "additionalProperties": False,
    }


def _widget_guide() -> str:
    """One line per widget: its name and what it is for."""
    seen: dict[str, str] = {}
    for (name, _version), entry in widgets.CATALOG.items():
        seen.setdefault(name, entry.purpose)
    return "Which drawing to use. " + "; ".join(
        f"{name} — {purpose}" for name, purpose in sorted(seen.items())
    )


def summarise_render_signal_desk(arguments: Mapping[str, Any]) -> str:
    """The rail row for a composed signal_desk: its title and how many blocks."""
    title = str(arguments.get("title") or "").strip()
    blocks = arguments.get("blocks")
    count = len(blocks) if isinstance(blocks, list) else 0
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
            try:
                with _artifact_write(name):
                    artifact = studies.run(
                        name,
                        _params_for(definition, arguments),
                        session=session,
                        turn_id=context.turn_id,
                        thread_id=context.thread_id,
                        warm=warmup.warm,
                    )
            except StudyParamsInvalid as invalid:
                raise ValueError(
                    f"{name} cannot run with those parameters — {invalid}"
                ) from invalid
            except StudyRefused as refused:
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
                "blockCount": len(artifact.signal_desk_spec.blocks),
                "headline": dict(artifact.headline),
                "provenance": _provenance_for_model(artifact.provenance.to_payload()),
            }

    def render_signal_desk(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Draw the frames this Turn gathered, dropping only what cannot be drawn.

        **Degrading is per block.** A model that named the wrong widget for one
        frame has still gathered four good ones, and refusing the Signal Desk would
        throw those away over a mistake it could fix in the next round. So a bad
        block is dropped with its reason returned, and the reasons are what the
        model reads.

        **Ownership is the Turn.** Every frame is checked against the Turn that
        made it (``studies/frames_buffer.py``), so an id from another
        conversation draws nothing here.
        """
        title = str(arguments.get("title") or "").strip()
        if not title:
            raise ValueError("title must say what the panel is called")
        raw = arguments.get("blocks")
        if not isinstance(raw, list) or not raw:
            raise ValueError("blocks must name at least one widget and frame")
        if len(raw) > frames_buffer.MAX_BLOCKS:
            raise ValueError(
                f"a Signal Desk holds at most {frames_buffer.MAX_BLOCKS} blocks; "
                f"{len(raw)} were asked for"
            )

        with self._open() as session:
            already = frames_buffer.signal_desks_composed(session, context.turn_id)
            if already >= frames_buffer.MAX_SIGNAL_DESKS_PER_TURN:
                return {
                    "error": "cannot_read",
                    "detail": (
                        f"this turn has already drawn {already} signal_desks, which "
                        "is the most it may draw"
                    ),
                }

            frames: dict[str, Mapping[str, Any]] = {}
            blocks: list[Mapping[str, Any]] = []
            dropped: list[Mapping[str, str]] = []
            sources: list[Mapping[str, Any]] = []

            for index, item in enumerate(raw):
                if not isinstance(item, Mapping):
                    dropped.append({"block": str(index), "reason": "not a block"})
                    continue
                widget = str(item.get("widget") or "").strip()
                reference = str(item.get("frame_id") or "").strip()
                try:
                    frame, provenance = frames_buffer.read_frame(
                        session, reference, turn_id=context.turn_id
                    )
                except frames_buffer.FrameNotAvailable as missing:
                    dropped.append({"block": reference or str(index), "reason": str(missing)})
                    continue

                version = _newest_version(widget)
                kind = str(frame.get("kind") or "")
                if version is None:
                    dropped.append(
                        {"block": reference, "reason": f"no widget named {widget!r}"}
                    )
                    continue
                if not widgets.accepts(widget, version, kind):  # type: ignore[arg-type]
                    dropped.append(
                        {
                            "block": reference,
                            "reason": (
                                f"{widget} cannot draw a {kind} frame; "
                                f"it draws {', '.join(widgets.CATALOG[(widget, version)].frame_kinds)}"
                            ),
                        }
                    )
                    continue

                key = f"f{len(frames)}"
                frames[key] = frame
                blocks.append(
                    {
                        "widget": widget,
                        "widgetVersion": version,
                        "frame": key,
                        # Presentation is the server's, as it is for a Study: the
                        # choices that change what a chart claims belong with the
                        # layer that knows what the numbers mean.
                        "options": _presentation(widget, frame),
                    }
                )
                sources.append(provenance)

            if not blocks:
                return {
                    "error": "cannot_read",
                    "detail": "no block could be drawn",
                    "dropped": dropped,
                }

            provenance = _merged_provenance(sources)
            with _artifact_write(frames_buffer.COMPOSITION_KIND):
                artifact_id = frames_buffer.store_composition(
                    session,
                    title=title,
                    frames=frames,
                    blocks=tuple(blocks),
                    provenance=provenance,
                    turn_id=context.turn_id,
                    thread_id=context.thread_id,
                )

        return {
            "studyName": frames_buffer.COMPOSITION_KIND,
            "studyVersion": 1,
            "artifactId": str(artifact_id),
            "title": title,
            "blockCount": len(blocks),
            "dropped": dropped,
            "provenance": _provenance_for_model(provenance),
        }

    @contextmanager
    def _open(self) -> Iterator[Session]:
        with self._session_opener() as session:
            yield session


def _newest_version(widget: str) -> int | None:
    """The highest version of one widget the catalog holds, or ``None``.

    The server picks, not the model: a version is how an artifact written last
    month keeps rendering, and it is a fact about the drawing rather than about
    the question. A model naming one would be a model pinning a viewer.
    """
    versions = [version for name, version in widgets.CATALOG if name == widget]
    return max(versions) if versions else None


#: Which column a widget draws from, given a frame it accepts.
#:
#: Positional rather than by name: a gathered series is ``(session, value)`` and
#: a Study's frame names its own columns, so the honest general rule is "the
#: first column labels and the second measures". A widget that needs more than
#: that says so here rather than guessing in the browser.
def _presentation(widget: str, frame: Mapping[str, Any]) -> dict[str, Any]:
    columns = [str(name) for name in (frame.get("columns") or [])]
    first = columns[0] if columns else ""
    second = columns[1] if len(columns) > 1 else ""
    if widget in {"line_series", "bar_series"}:
        options: dict[str, Any] = {"x": first, "y": second}
        if len(columns) > 2:
            options["secondary"] = columns[2]
        return options
    if widget == "ranked_bars":
        return {"label": first, "value": second}
    if widget == "scatter_quadrant":
        return {
            "label": first,
            "x": second,
            "y": columns[2] if len(columns) > 2 else second,
        }
    if widget == "stat_tiles":
        return {"label": first, "value": second}
    if widget == "session_heatmap":
        return {"rowKey": first}
    return {}


def _provenance_for_model(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """The provenance as the model reads it: without the method notes.

    The notes are for the reader who opens "Cách tính" under a picture. The
    model is owed the headline and the strip — as-of, sessions, health, one
    reason — inside a budget of roughly three hundred tokens, and five sentences
    of method per Study would spend most of it on something the model cannot
    act on. The artifact keeps them; the browser draws them.
    """
    return {key: value for key, value in provenance.items() if key != "methodNotes"}


def _merged_provenance(sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """One claim over several frames: the oldest as-of, the worst health.

    Both in the pessimistic direction, because a strip is read as a statement
    about the whole panel: a Signal Desk holding one week-old frame is a week-old
    signal_desk, and one holding a degraded frame is not a healthy one.
    """
    order = {"normal": 0, "degraded": 1, "unavailable": 2}
    health = "normal"
    as_of = ""
    sessions = 0
    reasons: list[str] = []
    notes: list[str] = []
    for source in sources:
        candidate = str(source.get("health") or "normal")
        if order.get(candidate, 0) > order.get(health, 0):
            health = candidate
        stamp = str(source.get("asOf") or "")
        if stamp and (not as_of or stamp < as_of):
            as_of = stamp
        used = source.get("sessionsUsed")
        if isinstance(used, int):
            sessions = max(sessions, used)
        reason = source.get("reason")
        if isinstance(reason, str) and reason:
            reasons.append(reason)
        for note in source.get("methodNotes") or ():
            if isinstance(note, str) and note:
                notes.append(note)
    # The strip under a panel holds one sentence, and every frame's reason is
    # already one. The first distinct reason takes the strip; the others are
    # limitations of the same picture, so they travel as method notes rather
    # than being glued into a paragraph the strip would have to cut.
    distinct = list(dict.fromkeys(reasons))
    return {
        "source": "store",
        "asOf": as_of,
        "sessionsUsed": sessions,
        "health": health,
        "reason": distinct[0] if distinct else None,
        "methodNotes": list(dict.fromkeys(distinct[1:] + notes)),
    }


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
