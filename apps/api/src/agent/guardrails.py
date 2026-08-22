"""When a Turn is going round in circles, and what to do about it.

Retry policy already exists at the LLM boundary: a call that raises is retried
and then abandoned. What that cannot see is the Turn that is failing while every
individual call behaves — the same tool, the same arguments, again, because the
model did not know what to do with what came back. Nothing errored, so nothing
counted, and the Turn spends its whole round budget re-reading one answer.

This module counts that instead, on a four-rung ladder:

``allow``
    Nothing about this call is a repetition.
``warn``
    Dispatch it, and fold a sentence of guidance into the result so the model
    reads *why* it is being told. A warning never withholds data: the failure
    mode being treated is a model that lost the thread, and taking the result
    away from it would not help it find it.
``block``
    Do not dispatch. Hand back the guidance in place of a result, which costs
    the Turn no round and no upstream call.
``halt``
    Stop calling tools and answer with what is already gathered. Taken after the
    current batch finishes, never mid-batch, so a parallel round is not left
    half-recorded.

A call's identity is ``(tool_name, sha256(canonical_json(arguments)))``. The hash
rather than the arguments themselves because the arguments can be long, and
canonical JSON because ``{"a":1,"b":2}`` and ``{"b":2,"a":1}`` are the same call
and a model that reorders its own keys is not making progress.

It decides; it does not act. Every method takes what it judges and returns a
verdict, because the runtime is what owns a message, a transcript and a
publisher — and a guardrail holding any of those could not be called a hundred
times in a test.

Counters are per Turn. The instance is built with the Turn and discarded with
it, and :meth:`TurnGuardrails.reset` exists for the caller that reuses one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    """What the runtime is being told to do about a call."""

    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    HALT = "halt"

    @property
    def rank(self) -> int:
        """Where this sits on the ladder, so a batch can take its strongest."""
        return _LADDER.index(self)


_LADDER = (Verdict.ALLOW, Verdict.WARN, Verdict.BLOCK, Verdict.HALT)

#: Stable reason codes, for the trace and for the operational counter. The
#: signal that this module has stopped working is a ``halt`` count that stays at
#: zero forever, so the codes are never rewritten to read better in a log.
REPEATED_FAILURE = "repeated_failure"
REPEATED_TOOL_FAILURE = "repeated_tool_failure"
NO_PROGRESS = "no_progress"


@dataclass(frozen=True)
class GuardrailThresholds:
    """The rungs, counted in observations within one Turn.

    ``warn_after=2`` means the second observation warns — the count is compared
    with ``>=``, so a threshold of 1 would fire on the first call and a threshold
    of 0 would fire before anything happened.

    The two upper rungs are arithmetic against the runtime that dispatches them,
    not taste. A Turn gets four tool rounds (``loop.MAX_TOOL_ROUNDS``) and six
    calls to the tools that leave this deployment
    (``loop.MAX_EXTERNAL_TOOL_CALLS``), so a rung set above either of those is a
    rung nothing can ring: a warn-only ladder that reads strict.

    ``exact_failure_block_after=3``: the count is compared with ``>=`` in
    :meth:`TurnGuardrails.before_call`, so three recorded failures refuse the
    *fourth* call. Failing in rounds one, two and three leaves round four
    blocked — the rung lands inside the round budget with nothing to spare. At
    five it needed five byte-identical calls fanned out inside a single round,
    which is the one shape the ladder should not have to depend on.

    ``same_tool_failure_halt_after=6``: the external-call ceiling itself. Six
    failures of one tool is that whole allowance spent on nothing, so the two
    numbers are one fact and are written as one — change either and change
    both. Reached by an ordinary two-calls-a-round fan-out over three rounds.
    At eight it was unreachable by construction for ``web_search`` and
    ``fetch_url``: the Turn ran out of calls before the tool ran out of
    failures.

    No import backs those two sentences: this module stays free of the runtime
    it judges, and the equality is held by a test instead.
    """

    exact_failure_warn_after: int = 2
    same_tool_failure_warn_after: int = 3
    no_progress_warn_after: int = 2
    exact_failure_block_after: int = 3
    same_tool_failure_halt_after: int = 6


DEFAULT_THRESHOLDS = GuardrailThresholds()


@dataclass(frozen=True)
class Decision:
    """One verdict, the code it is recorded under, and what to tell the model."""

    verdict: Verdict
    reason: str | None = None
    guidance: str | None = None

    @property
    def blocked(self) -> bool:
        return self.verdict is Verdict.BLOCK

    @property
    def halts(self) -> bool:
        return self.verdict is Verdict.HALT


_ALLOWED = Decision(Verdict.ALLOW)


def canonical_json(arguments: Mapping[str, Any] | None) -> str:
    """The arguments in one stable textual form.

    ``default=str`` rather than a raise: an unserialisable argument is still a
    repetition, and a guardrail that raised on it would turn a bad argument into
    a failed Turn.
    """
    return json.dumps(
        dict(arguments or {}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def call_signature(tool_name: str, arguments: Mapping[str, Any] | None) -> str:
    """One call's identity: the tool it names and the arguments it carries."""
    digest = hashlib.sha256(canonical_json(arguments).encode("utf-8")).hexdigest()
    return f"{tool_name}:{digest}"


def result_signature(text: str) -> str:
    """One result's identity, for deciding whether a repeat learned anything."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class TurnGuardrails:
    """The ladder, counted over one Turn."""

    thresholds: GuardrailThresholds = DEFAULT_THRESHOLDS
    _exact_failures: dict[str, int] = field(default_factory=dict, init=False)
    _tool_failures: dict[str, int] = field(default_factory=dict, init=False)
    _last_results: dict[str, str] = field(default_factory=dict, init=False)
    _no_progress: int = field(default=0, init=False)
    _halted: bool = field(default=False, init=False)

    @property
    def halted(self) -> bool:
        """Whether a halt has already been decided in this Turn."""
        return self._halted

    def reset(self) -> None:
        self._exact_failures.clear()
        self._tool_failures.clear()
        self._last_results.clear()
        self._no_progress = 0
        self._halted = False

    def before_call(
        self, tool_name: str, arguments: Mapping[str, Any] | None = None
    ) -> Decision:
        """Judge a call before it is dispatched, so a refusal costs nothing.

        A blocked call is itself an observation: it counts against the tool, so a
        model that keeps hammering something broken still reaches the halt rung
        instead of being blocked forever inside its round budget.
        """
        signature = call_signature(tool_name, arguments)
        if self._halted:
            return Decision(Verdict.HALT, REPEATED_TOOL_FAILURE, HALT_GUIDANCE)
        failures = self._exact_failures.get(signature, 0)
        if failures < self.thresholds.exact_failure_block_after:
            return _ALLOWED
        self._tool_failures[tool_name] = self._tool_failures.get(tool_name, 0) + 1
        if self._tool_failures[tool_name] >= self.thresholds.same_tool_failure_halt_after:
            self._halted = True
            return Decision(Verdict.HALT, REPEATED_TOOL_FAILURE, HALT_GUIDANCE)
        return Decision(
            Verdict.BLOCK,
            REPEATED_FAILURE,
            f"This exact call to {tool_name} has already failed {failures} times. "
            "Do not repeat it. Change the arguments, use a different tool, or "
            "answer with what you have.",
        )

    def after_call(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        ok: bool,
        result_hash: str | None = None,
    ) -> Decision:
        """Record one completed call and judge what it means for the next one.

        ``result_hash`` is how "no progress" is measured: a call that succeeded
        and returned exactly what the same call returned earlier taught the Turn
        nothing, which is the failure mode retry policy is blind to.
        """
        signature = call_signature(tool_name, arguments)
        if ok:
            return self._after_success(signature, tool_name, result_hash)
        self._exact_failures[signature] = self._exact_failures.get(signature, 0) + 1
        self._tool_failures[tool_name] = self._tool_failures.get(tool_name, 0) + 1
        # Progress is about learning something; a failure is not a repetition of
        # a result, so the no-progress streak is left where it is.
        if self._tool_failures[tool_name] >= self.thresholds.same_tool_failure_halt_after:
            self._halted = True
            return Decision(Verdict.HALT, REPEATED_TOOL_FAILURE, HALT_GUIDANCE)
        exact = self._exact_failures[signature]
        if exact >= self.thresholds.exact_failure_warn_after:
            return Decision(
                Verdict.WARN,
                REPEATED_FAILURE,
                f"This exact call to {tool_name} has now failed {exact} times. "
                "Repeating it will be refused; change the arguments or the approach.",
            )
        tool_total = self._tool_failures[tool_name]
        if tool_total >= self.thresholds.same_tool_failure_warn_after:
            return Decision(
                Verdict.WARN,
                REPEATED_TOOL_FAILURE,
                f"{tool_name} has failed {tool_total} times in this turn. "
                "Try another route to the same answer, or say what is missing.",
            )
        return _ALLOWED

    def _after_success(
        self, signature: str, tool_name: str, result_hash: str | None
    ) -> Decision:
        previous = self._last_results.get(signature)
        if result_hash is not None:
            self._last_results[signature] = result_hash
        if result_hash is None or previous != result_hash:
            self._no_progress = 0
            return _ALLOWED
        self._no_progress += 1
        if self._no_progress >= self.thresholds.no_progress_warn_after:
            return Decision(
                Verdict.WARN,
                NO_PROGRESS,
                f"The last {self._no_progress} calls to {tool_name} returned exactly "
                "what you already had. Use the evidence you have, or ask the user "
                "for what is genuinely missing.",
            )
        return _ALLOWED


#: What a halted Turn is told to do. Public because the executor reports it to
#: the loop, and two spellings of the same sentence is one too many.
HALT_GUIDANCE = "Stop calling tools and answer with the evidence already gathered."


__all__ = [
    "DEFAULT_THRESHOLDS",
    "HALT_GUIDANCE",
    "NO_PROGRESS",
    "REPEATED_FAILURE",
    "REPEATED_TOOL_FAILURE",
    "Decision",
    "GuardrailThresholds",
    "TurnGuardrails",
    "Verdict",
    "call_signature",
    "canonical_json",
    "result_signature",
]
