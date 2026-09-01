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

**Permission and time are declared here too, and only here.** A registration
says whether it may run at all (:attr:`ToolEntry.permission`) and how long one
call of it may take (:attr:`ToolEntry.timeout_seconds`). The executor enforces
both from this declaration rather than from a table of its own, for the reason
every other axis lives here: a second place that knows which tools are
permitted is a second place that can disagree with the one the model was shown.
"""

from __future__ import annotations

import logging
import math
import os
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from fnmatch import fnmatchcase
from types import MappingProxyType
from typing import Any

from src.core.llm import ToolSchema

from .permissions import PermissionRule, ToolPermission
from .schema_validation import assert_supported_schema

logger = logging.getLogger(__name__)

#: How long one ``check_fn`` verdict is trusted. Short, because it is the delay
#: between switching a feature flag and the model seeing the tool; long enough
#: that a multi-round Turn probes each tool once rather than once per round.
CHECK_TTL_SECONDS = 30.0
MAX_RESOLUTION_RETRIES = 3

#: How long one call of a tool that declared nothing else may take. A default
#: exists here, and deliberately does not exist for permission: a tool whose
#: author did not think about time still has to end, while a tool whose author
#: did not think about permission must not be granted one by omission.
DEFAULT_TOOL_TIMEOUT_SECONDS = 20.0

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

    Never part of a tool schema: the model must not be able to choose trusted
    identity or scope, so those arrive here and arguments arrive from the model.

    Every field is optional because tests and offline harnesses may execute a
    capability without a persisted Turn. A handler that needs one refuses when
    it is absent, in the same spirit as ``requires_env``.
    """

    user_id: int | None = None
    thread_id: uuid.UUID | None = None
    #: The Turn this call belongs to, where there is one. A handler that writes
    #: a row a reader will re-open needs to say which answer it belongs to, and
    #: an *argument* naming a Turn would be a route to attaching a picture to
    #: somebody else's conversation. ``None`` outside a persisted Turn.
    turn_id: uuid.UUID | None = None
    #: Reserved trusted domain scope; current web and memory tools do not use it.
    symbol: str | None = None
    #: Reserved trusted temporal scope; current tools do not use it.
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
    #: did. They are never the same string: a raw function name tells
    #: a reader nothing about what was looked up, and a model asked to call
    #: a display label with no handler has nothing to call.
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
    #: the call was for. Some tools need several arguments and a curated
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
    #: Whether this tool may be dispatched at all. Required — :func:`register`
    #: refuses a registration that leaves it unset, and ``None`` is that unset
    #: state rather than a value with a meaning.
    #:
    #: **There is no default, and that is the point.** Any default is a rule
    #: about tools nobody thought about: ``ALLOW`` grants the newest, least
    #: reviewed capability the same standing as a tool that was argued over,
    #: and ``DENY`` makes forgetting the field look like a deployment decision.
    #: Both are answers this layer is not entitled to give, so it declines to
    #: give one and refuses the registration instead.
    permission: ToolPermission | None = None
    #: Ordered capability/resource policy. ``permission`` above is the concise
    #: spelling for one exact-capability, all-resource rule; declarations that
    #: need resource exceptions use this tuple instead. Supplying both is
    #: refused so there is never a hidden order between two policy sources.
    permission_rules: tuple[PermissionRule, ...] = ()
    #: Model argument whose value is the resource permission rules match. A
    #: declaration with only ``resource="*"`` needs none.
    resource_arg: str | None = None
    #: How long one call of this tool may take before the executor gives up on
    #: it and tells the model so. Declared per tool because the honest bound is
    #: a property of the work: reading a page that redirects twice is not the
    #: same wait as one store query.
    #:
    #: This is not the round's backstop. That one ends the Turn; this one ends
    #: one call and leaves the round to finish, which is the difference between
    #: an answer built from the evidence that did arrive and no answer at all.
    timeout_seconds: float = DEFAULT_TOOL_TIMEOUT_SECONDS
    contract_version: str = "1"

    def __post_init__(self) -> None:
        for field_name, enum_type in (
            ("effect", ToolEffect),
            ("idempotency", ToolIdempotency),
            ("access", ToolAccess),
            ("concurrency", ToolConcurrency),
        ):
            object.__setattr__(self, field_name, enum_type(getattr(self, field_name)))
        if self.permission is not None and self.permission_rules:
            action = ToolPermission(self.permission)
            generated = (PermissionRule(self.name, "*", action),)
            # ``dataclasses.replace`` reconstructs the object with every field,
            # including the rules this shorthand generated on the first pass.
            # Accept that exact reconstruction; any independently supplied
            # second source still conflicts and is refused.
            if tuple(self.permission_rules) != generated:
                raise ValueError(
                    f"tool {self.name!r} must declare permission or "
                    "permission_rules, not both"
                )
        if self.permission is not None:
            action = ToolPermission(self.permission)
            object.__setattr__(self, "permission", action)
            object.__setattr__(
                self,
                "permission_rules",
                (PermissionRule(self.name, "*", action),),
            )
        else:
            object.__setattr__(
                self,
                "permission_rules",
                tuple(
                    rule if isinstance(rule, PermissionRule) else PermissionRule(*rule)
                    for rule in self.permission_rules
                ),
            )
        if self.resource_arg is not None:
            resource_arg = str(self.resource_arg).strip()
            if not resource_arg:
                raise ValueError(f"tool {self.name!r} has a blank resource_arg")
            object.__setattr__(self, "resource_arg", resource_arg)
        timeout = float(self.timeout_seconds)
        if not math.isfinite(timeout) or timeout <= 0:
            # A tool that may take forever has no bound at all, and a bound of
            # zero or less can only refuse. Both read as a declaration, and
            # neither is one, so neither is accepted.
            raise ValueError(
                f"tool {self.name!r} needs a finite, positive timeout_seconds"
            )
        object.__setattr__(self, "timeout_seconds", timeout)
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
    """One immutable declaration and its availability verdict for a task.

    Every axis the executor, the message layer and the budget need is carried
    here, so a task decides once what a tool is and no consumer re-derives it
    from the live registry half a round later. :attr:`permission` is one of
    those axes and is never absent on a snapshot of a *registered* declaration,
    because :func:`register` refuses one that leaves it unset.
    """

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
    permission_rules: tuple[PermissionRule, ...]
    resource_arg: str | None
    timeout_seconds: float
    contract_version: str
    is_async: bool
    max_result_size_chars: int | None

    @property
    def reads_external(self) -> bool:
        """Compatibility projection for trust-aware consumers."""
        return self.content_trust is ContentTrust.UNTRUSTED

    @property
    def permission(self) -> ToolPermission | None:
        """Compatibility view for a single all-resource declaration."""

        if len(self.permission_rules) != 1:
            return None
        rule = self.permission_rules[0]
        if rule.capability == self.name and rule.resource == "*":
            return rule.action
        return None

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
            permission_rules=entry.permission_rules,
            resource_arg=entry.resource_arg,
            timeout_seconds=entry.timeout_seconds,
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
        # would put a raw function name on a reader's screen and look deliberate,
        # is exactly what happened before this field existed.
        raise ValueError(
            f"tool {entry.name!r} needs a display_name a person can read; the "
            "model's name for it is not one"
        )
    if not entry.permission_rules:
        # Refused rather than defaulted, for the reason a display name is:
        # a default here would be a rule about every tool nobody thought about,
        # decided by whoever picked the default rather than by whoever ships the
        # capability. The refusal makes the omission loud at import time instead
        # of quiet at dispatch time.
        raise ValueError(
            f"tool {entry.name!r} needs permission rules; whether it may run is a "
            "decision its registration has to state"
        )
    if not isinstance(entry.schema, Mapping):
        raise TypeError(f"tool {entry.name!r} needs a JSON Schema mapping")
    assert_supported_schema(entry.schema)
    for rule in entry.permission_rules:
        if not fnmatchcase(entry.name, rule.capability):
            raise ValueError(
                f"tool {entry.name!r} carries a permission rule for another capability"
            )
        if rule.action is ToolPermission.ASK and entry.effect is not ToolEffect.WRITE:
            raise ValueError(
                f"tool {entry.name!r} may use ask only for a declared write effect"
            )
    if any(rule.resource != "*" for rule in entry.permission_rules) and not entry.resource_arg:
        raise ValueError(
            f"tool {entry.name!r} has resource rules but no resource_arg"
        )
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
    "DEFAULT_TOOL_TIMEOUT_SECONDS",
    "Handler",
    "MAX_RESOLUTION_RETRIES",
    "PermissionRule",
    "ResolvedTool",
    "ToolAccess",
    "ToolConcurrency",
    "ToolContext",
    "ToolEffect",
    "ToolEntry",
    "ToolIdempotency",
    "ToolPermission",
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
