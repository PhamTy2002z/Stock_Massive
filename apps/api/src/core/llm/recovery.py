"""One recovery action per route failure, in one table.

Phase 1 of ``plans/260821-0020-agent-upgrade-hermes-lessons`` split the shapeless
``route_error`` into classes. Classes on their own changed nothing: 36% of Turns
still died on the route, because knowing *what* failed is not the same as knowing
what to do about it. This module is the second half — every class either names an
action or names the reason it is terminal, and a test walks the table so a class
added later cannot arrive without one.

Two decisions are recorded here rather than in a branch somewhere:

**Compress, not failover.** ``ContextOverflow`` means the input did not fit. A
second call with the same input does not fit either, and a different model has a
different window rather than a bigger one — so the only thing that can change the
outcome is sending less. The action belongs to whoever owns the transcript, which
is the agent loop, so the client hands the class up rather than acting on it.

**A rate limit is still never retried.** ``errors.RouteRateLimited`` records why:
the route answered, precisely, and what it said was *not now*; a second identical
request half a second later spends an attempt to be told the same thing. What is
new is that the refusal is written to a shared breaker, so the *next* caller —
the Collector on one side, an interactive Turn on the other — waits instead of
asking. That is not a retry; it is the opposite of one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import (
    AuthUnavailable,
    ContentPolicyBlocked,
    ContextOverflow,
    DeadlineExpired,
    GatewayTimeout,
    LLMError,
    MalformedArguments,
    ModelRefusal,
    ModelUnavailable,
    OutputCapExceeded,
    RouteRateLimited,
    SchemaRejected,
)


class RouteAction(str, Enum):
    """What may be done about one failed call, and who does it.

    ``REBUILD_AND_RETRY``, ``SWITCH_MODEL`` and ``TERMINAL`` are the client's;
    ``COMPRESS`` and ``LOWER_OUTPUT_CAP`` belong to the caller that owns the
    request, because neither the transcript nor the output ceiling is the
    client's to change.
    """

    REBUILD_AND_RETRY = "rebuild_and_retry"
    SWITCH_MODEL = "switch_model"
    COMPRESS = "compress"
    LOWER_OUTPUT_CAP = "lower_output_cap"
    TERMINAL = "terminal"


@dataclass(frozen=True)
class Recovery:
    """The action, and the sentence that justifies it.

    The sentence is not decoration. A terminal branch with no stated reason is
    indistinguishable from a branch nobody finished writing, and that ambiguity
    is what made 36% of route failures unactionable in the first place.
    """

    action: RouteAction
    reason: str

    @property
    def terminal(self) -> bool:
        return self.action is RouteAction.TERMINAL


#: Exact class to recovery. Looked up by MRO, so a subclass added later inherits
#: its parent's action until somebody decides it deserves its own.
RECOVERIES: dict[type[LLMError], Recovery] = {
    ContextOverflow: Recovery(
        RouteAction.COMPRESS,
        "the input did not fit, so the only thing that can change the outcome is "
        "sending less of it; the transcript belongs to the caller",
    ),
    OutputCapExceeded: Recovery(
        RouteAction.LOWER_OUTPUT_CAP,
        "the transcript fits and the reserved output ceiling is what pushed the "
        "total over, so trimming the transcript would discard evidence and fix "
        "nothing",
    ),
    DeadlineExpired: Recovery(
        RouteAction.REBUILD_AND_RETRY,
        "our own deadline expired, which a wedged connection in the pool would "
        "reproduce on the next call, so the transport is rebuilt before asking "
        "again",
    ),
    GatewayTimeout: Recovery(
        RouteAction.REBUILD_AND_RETRY,
        "the route did not answer or answered that it could not; a fresh "
        "connection costs one handshake and rules out the half of the causes "
        "that live on this side",
    ),
    ModelUnavailable: Recovery(
        RouteAction.SWITCH_MODEL,
        "nothing about a retired or unserved model is transient, and the other "
        "model of the configured pair is reachable through a fresh reservation "
        "at its own prices",
    ),
    RouteRateLimited: Recovery(
        RouteAction.TERMINAL,
        "the route answered, and what it said was not now; the refusal is "
        "recorded in the shared breaker so the next caller waits instead of "
        "asking",
    ),
    ContentPolicyBlocked: Recovery(
        RouteAction.TERMINAL,
        "the route's own filter refused this text and refuses it again; this is "
        "the route talking, so there are no words of the model's to carry",
    ),
    SchemaRejected: Recovery(
        RouteAction.TERMINAL,
        "the Tool Catalog wrote the schemas the route refused, so a retry "
        "replays them unchanged; this is ours to fix",
    ),
    AuthUnavailable: Recovery(
        RouteAction.TERMINAL,
        "the configured credential died and this deployment holds exactly one, "
        "so there is no pool to rotate into",
    ),
    ModelRefusal: Recovery(
        RouteAction.TERMINAL,
        "the model declined and its own words are the answer; re-prompting to "
        "get around a refusal is arguing with the model on the user's behalf",
    ),
    MalformedArguments: Recovery(
        RouteAction.TERMINAL,
        "the route violated its contract by returning arguments that are not "
        "JSON, which is counted and logged loudly rather than worked around",
    ),
    LLMError: Recovery(
        RouteAction.TERMINAL,
        "an unclassified failure has no known remedy, and guessing one is how a "
        "recovery path ends up lowering a ceiling that was never too high",
    ),
}

#: The classes this table deliberately does not cover. ``ToolError`` is a tool's
#: failure handed back to the model as a structured result rather than the route
#: failing, so it never reaches a recovery.
UNCOVERED: frozenset[str] = frozenset({"ToolError"})


def route_error_classes() -> tuple[type[LLMError], ...]:
    """Every ``LLMError`` this package defines, from the class tree itself.

    Derived rather than listed, and not from :data:`RECOVERIES`: a completeness
    check that reads the table it is checking proves only that the table equals
    itself. A class added to ``errors.py`` next month has to appear here, which
    is what makes the test able to notice it has no entry.
    """

    def descendants(klass: type[LLMError]) -> list[type[LLMError]]:
        found = [klass]
        for child in klass.__subclasses__():
            found.extend(descendants(child))
        return found

    return tuple(
        klass
        for klass in dict.fromkeys(descendants(LLMError))
        # This package's own classes only. A subclass declared in a test or by a
        # caller is that caller's business, and ``recovery_for`` already answers
        # for it by MRO.
        if klass.__module__ == LLMError.__module__
        and klass.__name__ not in UNCOVERED
    )


def recovery_for(error: BaseException) -> Recovery:
    """The action for this failure, inherited along the MRO.

    Falls back to the ``LLMError`` entry, so an exception this table has never
    seen is terminal rather than retried — the safe direction, and the behaviour
    that existed before the table did.
    """
    for klass in type(error).__mro__:
        recovery = RECOVERIES.get(klass)  # type: ignore[arg-type]
        if recovery is not None:
            return recovery
    return RECOVERIES[LLMError]


__all__ = [
    "RECOVERIES",
    "UNCOVERED",
    "Recovery",
    "RouteAction",
    "recovery_for",
    "route_error_classes",
]
