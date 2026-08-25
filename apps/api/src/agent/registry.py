"""The one place a tool becomes visible to the model.

A registration carries three things that used to live apart: the schema the
model reads, the handler the executor dispatches to, and the *availability*
question — can this tool run in this deployment at all. Keeping them together
is what lets :func:`definitions` answer "what may the model call right now"
without every caller re-deriving the second and third from configuration.

Three properties are load-bearing rather than incidental.

**A name is owned by one toolset.** Two registrations of the same name from
different toolsets is a shadow: whichever imported last would silently take the
dispatch, and the model would be told about a tool that is not the one it gets.
That is refused. ``override=True`` is the explicit escape hatch for the case
where shadowing is the intent.

**Availability is cached for a bounded window.** ``check_fn`` may talk to
configuration, an environment variable, or a probe. :func:`definitions` runs on
every round of every Turn, so an uncached probe would be paid per round, per
user. The window is short enough (:data:`CHECK_TTL_SECONDS`) that flipping a
flag takes effect without a restart.

**Mutation bumps a generation counter.** Layers above (``definitions.py``)
cache the built schema list; they cannot know when a tool appeared or left
unless the registry says so with a number they can compare.

**A tool names itself twice, for two audiences.** ``name`` is what the model
calls; :attr:`ToolEntry.display_name` is what a person reads on the rail of what
a Turn did. Both are declared on the registration, and a blank display name is
refused, so there is no path by which a raw tool name reaches a screen.

**Provenance is declared, not remembered.** A registration says whether its
results are content from outside this deployment
(:attr:`ToolEntry.reads_external`), and the layer that builds the message asks
this rather than checking a hand-written list of tool names. A list is a thing
somebody has to remember to extend, and the tool that gets forgotten is by
definition the newest one — the failure ``untrusted.py`` describes and, until
this attribute existed, also had.

Which *bundle* a caller selects is still what decides what a lane may call
(``toolsets.py``). This attribute answers a different question: given that it
was called, is what came back somebody else's writing.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from src.core.llm import ToolSchema

logger = logging.getLogger(__name__)

#: How long one ``check_fn`` verdict is trusted. Short, because it is the delay
#: between switching a feature flag and the model seeing the tool; long enough
#: that a multi-round Turn probes each tool once rather than once per round.
CHECK_TTL_SECONDS = 30.0
MAX_RESOLUTION_RETRIES = 3

#: A handler takes the Turn's trusted context and the model's arguments, and may
#: be a coroutine function or a blocking one — the executor decides how to run
#: it from ``ToolEntry.is_async``.
Handler = Callable[["ToolContext", Mapping[str, Any]], "Awaitable[Any] | Any"]


class ToolEffect(str, Enum):
    """Whether invoking a tool changes durable state."""

    READ = "read"
    WRITE = "write"
    UNKNOWN = "unknown"


class ToolIdempotency(str, Enum):
    """Whether repeating the same call has the same externally visible effect."""

    IDEMPOTENT = "idempotent"
    NON_IDEMPOTENT = "non_idempotent"
    UNKNOWN = "unknown"


class ToolAccess(str, Enum):
    """The boundary crossed by a tool invocation."""

    NETWORK = "network"
    STORE = "store"


class ContentTrust(str, Enum):
    """How result content is positioned when returned to the model."""

    UNTRUSTED = "untrusted"
    TRUSTED_STRUCTURED = "trusted_structured"


class ToolConcurrency(str, Enum):
    """Whether calls may overlap without changing their observable order."""

    PARALLEL_SAFE = "parallel_safe"
    SERIALIZED = "serialized"


class AvailabilityReason(str, Enum):
    """Sanitized reasons a declaration was not offered."""

    NOT_REGISTERED = "not_registered"
    REQUIREMENTS_MISSING = "requirements_missing"
    CHECK_REFUSED = "check_refused"
    CHECK_FAILED = "check_failed"


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_json(item) for item in value)
    return value


def _callable_identity(value: Callable[..., Any]) -> str:
    module = getattr(value, "__module__", type(value).__module__)
    qualified = getattr(value, "__qualname__", type(value).__qualname__)
    return f"{module}.{qualified}"


class ToolShadowError(ValueError):
    """Two toolsets claimed the same tool name."""

    def __init__(self, name: str, existing_toolset: str, new_toolset: str) -> None:
        super().__init__(
            f"tool {name!r} is already registered by toolset {existing_toolset!r}; "
            f"toolset {new_toolset!r} may not shadow it without override=True"
        )
        self.name = name
        self.existing_toolset = existing_toolset
        self.new_toolset = new_toolset


@dataclass(frozen=True)
class ToolContext:
    """Trusted facts handed to a handler out of band.

    Never part of a tool schema: the model must not be able to name a user, a
    thread, a symbol or a Trading Day it was not given, so identity arrives here
    and arguments arrive from the model, and the two are never merged.

    **Every field is optional because the callers are not one kind of caller.**
    A Turn is owned by a user and belongs to a Thread; an Analysis is owned by
    neither. An Analysis is keyed by ``(symbol, trading_day)`` and shared
    system-wide (``src/alpha/watchlist.py``), so ``user_id`` on it would be a
    number invented to fill a field. A handler that genuinely needs one refuses
    when it is absent, in the same spirit as ``requires_env``: the condition is
    stated where the handler is rather than assumed by its type.
    """

    user_id: int | None = None
    thread_id: uuid.UUID | None = None
    #: The symbol one Analysis is being produced for. Trusted rather than an
    #: argument for the reason above: an argument naming a symbol is a route to
    #: reading a symbol this call was not opened for.
    symbol: str | None = None
    #: The Trading Day that Analysis is keyed by. Trusted for the same reason,
    #: and for one more: an argument naming a day is a route to a session that
    #: has not closed yet.
    trading_day: date | None = None
    #: The caller's clock. Injected so a handler that stamps a row and a test
    #: that asserts the stamp read the same instant.
    now: datetime | None = None


@dataclass(frozen=True)
class ToolEntry:
    """One registration: what the model sees and what actually runs."""

    name: str
    toolset: str
    #: JSON Schema for the *arguments object*, not for the whole tool. The
    #: model-facing envelope (name, description, schema) is assembled in
    #: :meth:`as_schema` so there is one place that shape is decided.
    schema: Mapping[str, Any]
    handler: Handler
    description: str = ""
    #: The reader-facing name of what this tool does, in the reader's language.
    #:
    #: **Every tool carries two names and they are for different audiences.**
    #: ``name`` is the identifier the model calls and the trace records;
    #: ``display_name`` is the phrase a person reads on the rail of what a Turn
    #: did. They are never the same string: a rail row saying ``get_field`` tells
    #: a reader nothing about what was looked up, and a model asked to call
    #: "Đọc chỉ báo" has nothing to call.
    #:
    #: Required — :func:`register` refuses a blank one. That refusal is the whole
    #: mechanism: the alternative is a table of display names kept somewhere else,
    #: which is a list somebody has to remember to extend, and the tool that gets
    #: forgotten is by definition the newest one. This is the same failure
    #: ``untrusted.py`` used to have with its frozenset.
    display_name: str = ""
    #: Which argument, if any, is worth appending to :attr:`display_name` on that
    #: rail row — a query, a URL. ``None`` for a tool whose arguments say nothing
    #: a reader would recognise.
    summary_detail_arg: str | None = None
    #: A tool that composes its own rail row, when one argument cannot say what
    #: the call was for. ``get_field`` needs a field and a symbol and a curated
    #: label for the field, so it builds the sentence itself. Takes the model's
    #: arguments and returns the whole row, :attr:`display_name` included.
    summarise: Callable[[Mapping[str, Any]], str] | None = None
    #: Whether this tool can run here. ``None`` means unconditionally available.
    #: A raising ``check_fn`` reads as unavailable: a broken probe must not take
    #: the whole schema list down with it.
    check_fn: Callable[[], bool] | None = None
    #: Environment variables that must be set and non-empty. Kept separate from
    #: ``check_fn`` so a missing credential is stated declaratively.
    requires_env: tuple[str, ...] = ()
    #: Whether this tool's results are content somebody outside this deployment
    #: wrote. ``untrusted.py`` wraps those at the layer that builds the message,
    #: and it asks this rather than consulting a list of names it has to
    #: remember to extend.
    #:
    #: **The default is the unsafe answer stated safely.** A registration that
    #: says nothing is treated as external, so a tool added without a thought
    #: about provenance is wrapped rather than trusted. The cost of being wrong
    #: this way is a delimiter around a store read; the cost the other way is a
    #: web page reaching the model in the position the harness's own
    #: instructions occupy.
    reads_external: bool | None = None
    #: ``False`` for a blocking handler; the executor moves those off the event
    #: loop rather than letting them stall every other call in the round.
    is_async: bool = True
    max_result_size_chars: int | None = None
    effect: ToolEffect = ToolEffect.UNKNOWN
    idempotency: ToolIdempotency = ToolIdempotency.NON_IDEMPOTENT
    access: ToolAccess = ToolAccess.NETWORK
    content_trust: ContentTrust | None = None
    concurrency: ToolConcurrency = ToolConcurrency.SERIALIZED
    contract_version: str = "1"

    def __post_init__(self) -> None:
        for field_name, enum_type in (
            ("effect", ToolEffect),
            ("idempotency", ToolIdempotency),
            ("access", ToolAccess),
            ("concurrency", ToolConcurrency),
        ):
            object.__setattr__(self, field_name, enum_type(getattr(self, field_name)))
        trust = (
            None
            if self.content_trust is None
            else ContentTrust(self.content_trust)
        )
        external = self.reads_external
        if trust is None:
            trust = (
                ContentTrust.TRUSTED_STRUCTURED
                if external is False
                else ContentTrust.UNTRUSTED
            )
        object.__setattr__(self, "content_trust", trust)
        projected_external = trust is ContentTrust.UNTRUSTED
        if external is None:
            object.__setattr__(self, "reads_external", projected_external)
        elif external is not projected_external:
            raise ValueError(
                f"tool {self.name!r} has conflicting reads_external and content_trust"
            )
        if not isinstance(self.contract_version, str) or not self.contract_version.strip():
            raise ValueError(f"tool {self.name!r} needs a contract_version")

    def as_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=dict(self.schema),
        )

    @property
    def handler_identity(self) -> str:
        """Stable code identity without a callable repr or object address."""
        return _callable_identity(self.handler)


@dataclass(frozen=True)
class ResolvedTool:
    """One immutable declaration and its availability verdict for a task."""

    name: str
    toolset: str
    schema: ToolSchema
    handler: Handler
    handler_identity: str
    display_name: str
    summary_detail_arg: str | None
    summarise: Callable[[Mapping[str, Any]], str] | None
    summarise_identity: str | None
    available: bool
    unavailable_reason: AvailabilityReason | None
    availability_expires_at: float
    effect: ToolEffect
    idempotency: ToolIdempotency
    access: ToolAccess
    content_trust: ContentTrust
    concurrency: ToolConcurrency
    contract_version: str
    is_async: bool
    max_result_size_chars: int | None

    @property
    def reads_external(self) -> bool:
        """Compatibility projection for trust-aware consumers."""
        return self.content_trust is ContentTrust.UNTRUSTED

    @classmethod
    def from_entry(
        cls,
        entry: ToolEntry,
        *,
        available: bool,
        unavailable_reason: AvailabilityReason | None,
        availability_expires_at: float,
    ) -> "ResolvedTool":
        schema = entry.as_schema()
        return cls(
            name=entry.name,
            toolset=entry.toolset,
            schema=ToolSchema(
                name=schema.name,
                description=schema.description,
                parameters=_freeze_json(schema.parameters),
                strict=schema.strict,
            ),
            handler=entry.handler,
            handler_identity=entry.handler_identity,
            display_name=entry.display_name,
            summary_detail_arg=entry.summary_detail_arg,
            summarise=entry.summarise,
            summarise_identity=(
                None if entry.summarise is None else _callable_identity(entry.summarise)
            ),
            available=available,
            unavailable_reason=unavailable_reason,
            availability_expires_at=availability_expires_at,
            effect=entry.effect,
            idempotency=entry.idempotency,
            access=entry.access,
            content_trust=entry.content_trust,
            concurrency=entry.concurrency,
            contract_version=entry.contract_version,
            is_async=entry.is_async,
            max_result_size_chars=entry.max_result_size_chars,
        )


# Registration order is preserved, and that is deliberate: the schema list is
# part of the cacheable prompt prefix, so a stable order keeps the prefix
# stable across processes that imported the same modules.
_ENTRIES: dict[str, ToolEntry] = {}
_CHECKS: dict[
    str, tuple[float, bool, AvailabilityReason | None, ToolEntry]
] = {}
_GENERATION = 0


def _bump() -> int:
    global _GENERATION
    _GENERATION += 1
    return _GENERATION


def generation() -> int:
    """A number that changes whenever the set of registrations changes."""
    return _GENERATION


def register(entry: ToolEntry, *, override: bool = False) -> ToolEntry:
    """Add or replace one registration.

    Re-registering the same name from the same toolset is allowed and replaces
    it: a module that is imported twice, or a handler rebuilt with different
    settings, is a legitimate refresh rather than a shadow.
    """
    if not entry.name or not entry.name.strip():
        raise ValueError("a tool registration needs a name")
    if not entry.toolset or not entry.toolset.strip():
        raise ValueError(f"tool {entry.name!r} needs a toolset")
    if not entry.description.strip():
        raise ValueError(f"tool {entry.name!r} needs a description the model can read")
    if not entry.display_name.strip():
        # Refused rather than defaulted to the tool's own name. A default here
        # would put `get_field` on a reader's screen and look deliberate, which
        # is exactly what happened before this field existed.
        raise ValueError(
            f"tool {entry.name!r} needs a display_name a person can read; the "
            "model's name for it is not one"
        )
    if not isinstance(entry.schema, Mapping):
        raise TypeError(f"tool {entry.name!r} needs a JSON Schema mapping")
    existing = _ENTRIES.get(entry.name)
    if existing is not None and existing.toolset != entry.toolset and not override:
        raise ToolShadowError(entry.name, existing.toolset, entry.toolset)
    _ENTRIES[entry.name] = entry
    # The old verdict belonged to the old handler and its old gate.
    _CHECKS.pop(entry.name, None)
    _bump()
    return entry


def deregister(name: str) -> bool:
    """Remove one registration. ``False`` when there was nothing to remove."""
    if _ENTRIES.pop(name, None) is None:
        return False
    _CHECKS.pop(name, None)
    _bump()
    return True


def clear() -> None:
    """Drop every registration.

    Used where a process rebuilds its whole tool surface — and by tests, which
    need a registry that is not carrying another test's tools.
    """
    if not _ENTRIES and not _CHECKS:
        return
    _ENTRIES.clear()
    _CHECKS.clear()
    _bump()


def get(name: str) -> ToolEntry | None:
    return _ENTRIES.get(name)


def names(*, toolset: str | None = None) -> tuple[str, ...]:
    return tuple(
        name
        for name, entry in _ENTRIES.items()
        if toolset is None or entry.toolset == toolset
    )


def entries(*, toolset: str | None = None) -> tuple[ToolEntry, ...]:
    return tuple(
        entry for entry in _ENTRIES.values() if toolset is None or entry.toolset == toolset
    )


def is_available(name: str, *, now: float | None = None) -> bool:
    """Whether this tool may be offered and dispatched right now.

    ``now`` is a monotonic reading, injectable so a test can age the cache
    instead of sleeping through :data:`CHECK_TTL_SECONDS`.
    """
    available, _, _ = availability(name, now=now)
    return available


def availability(
    name: str, *, now: float | None = None
) -> tuple[bool, AvailabilityReason | None, float]:
    """Return a cached verdict, sanitized reason, and monotonic expiry."""
    instant = time.monotonic() if now is None else float(now)
    for _ in range(MAX_RESOLUTION_RETRIES):
        entry = _ENTRIES.get(name)
        if entry is None:
            return False, AvailabilityReason.NOT_REGISTERED, instant
        cached = _CHECKS.get(name)
        if cached is not None and cached[3] is entry and instant < cached[0]:
            return cached[1], cached[2], cached[0]
        available, reason = _probe(entry)
        if _ENTRIES.get(name) is not entry:
            continue
        expires_at = instant + CHECK_TTL_SECONDS
        _CHECKS[name] = (expires_at, available, reason, entry)
        if _ENTRIES.get(name) is entry:
            return available, reason, expires_at
    return False, AvailabilityReason.CHECK_FAILED, instant


def _probe(entry: ToolEntry) -> tuple[bool, AvailabilityReason | None]:
    for variable in entry.requires_env:
        if not os.environ.get(variable, "").strip():
            return False, AvailabilityReason.REQUIREMENTS_MISSING
    if entry.check_fn is None:
        return True, None
    try:
        if entry.check_fn():
            return True, None
        return False, AvailabilityReason.CHECK_REFUSED
    except Exception as exc:  # noqa: BLE001 - a broken probe hides one tool, not all
        logger.warning("Availability check for tool %s failed: %s", entry.name, exc)
        return False, AvailabilityReason.CHECK_FAILED


def resolve(name: str, *, now: float | None = None) -> ResolvedTool | None:
    """Snapshot one registered declaration and its current availability."""
    instant = time.monotonic() if now is None else float(now)
    for _ in range(MAX_RESOLUTION_RETRIES):
        entry = _ENTRIES.get(name)
        if entry is None:
            return None
        available, reason, expires_at = availability(name, now=instant)
        if _ENTRIES.get(name) is entry:
            return ResolvedTool.from_entry(
                entry,
                available=available,
                unavailable_reason=reason,
                availability_expires_at=expires_at,
            )
    entry = _ENTRIES.get(name)
    if entry is None:
        return None
    return ResolvedTool.from_entry(
        entry,
        available=False,
        unavailable_reason=AvailabilityReason.CHECK_FAILED,
        availability_expires_at=instant,
    )


def definitions(
    names_wanted: Sequence[str] | None = None, *, now: float | None = None
) -> tuple[ToolSchema, ...]:
    """The schemas the model may be shown, availability already applied.

    Order follows ``names_wanted`` when it is given and registration order
    otherwise, so the caller controls the prompt prefix rather than a dict.
    """
    wanted: Iterable[str] = _ENTRIES.keys() if names_wanted is None else names_wanted
    schemas: list[ToolSchema] = []
    seen: set[str] = set()
    for name in wanted:
        if name in seen:
            continue
        seen.add(name)
        entry = _ENTRIES.get(name)
        if entry is None:
            logger.warning("Toolset asked for tool %s, which is not registered", name)
            continue
        if not is_available(name, now=now):
            continue
        schemas.append(entry.as_schema())
    return tuple(schemas)


def get_max_result_size(name: str) -> int | None:
    """What this registration declared its result may weigh, in characters."""
    entry = _ENTRIES.get(name)
    return None if entry is None else entry.max_result_size_chars


def reads_external(name: str) -> bool:
    """Whether this tool's results are content from outside this deployment.

    An unregistered name answers ``True``. That is not a placeholder: the only
    callers are the wrapper and the external-call ceiling, and both are asking
    "must I be careful about this", where the honest answer about a tool nobody
    registered is yes.
    """
    entry = _ENTRIES.get(name)
    return True if entry is None else entry.reads_external


def accesses_network(name: str) -> bool:
    """Whether a registered tool leaves the deployment.

    This is deliberately separate from :func:`reads_external`, whose legacy
    compatibility meaning is content trust.  Unknown names take the
    conservative network answer so budget and wire projections never grant an
    undeclared call the cheaper store classification.
    """
    entry = get(name)
    return True if entry is None else entry.access is ToolAccess.NETWORK


def object_schema(
    properties: Mapping[str, Mapping[str, Any]], required: Sequence[str] = ()
) -> dict[str, Any]:
    """One argument object, written the way a tool author thinks about it.

    ``required`` names only the genuinely mandatory keys; the LLM boundary
    restates the schema for strict mode when it goes on the wire, so a tool does
    not have to know that strict mode wants every property listed.
    """
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


def declared_result_sizes() -> Mapping[str, int]:
    """Every declared per-tool cap, as ``budget.py``'s registry rung wants it."""
    return {
        entry.name: entry.max_result_size_chars
        for entry in _ENTRIES.values()
        if entry.max_result_size_chars is not None
    }


__all__ = [
    "AvailabilityReason",
    "CHECK_TTL_SECONDS",
    "ContentTrust",
    "Handler",
    "MAX_RESOLUTION_RETRIES",
    "ResolvedTool",
    "ToolAccess",
    "ToolConcurrency",
    "ToolContext",
    "ToolEffect",
    "ToolEntry",
    "ToolIdempotency",
    "ToolShadowError",
    "availability",
    "accesses_network",
    "clear",
    "declared_result_sizes",
    "definitions",
    "deregister",
    "entries",
    "generation",
    "get",
    "get_max_result_size",
    "is_available",
    "names",
    "object_schema",
    "reads_external",
    "register",
    "resolve",
]
