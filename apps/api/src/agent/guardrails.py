"""When a Turn is going round in circles, and what to do about it one rung early.

The loop already has one guardrail, and it is not this one.
``core.llm.errors.ToolAttempts`` counts *failures* per tool and ``admit_round``
spends that allowance before dispatch, so a tool that is broken gets two goes
and then stops being dispatched.  That is retry policy, and it is complete.

What it cannot see is a Turn that is failing while every tool reports success:
the same call, with the same arguments, made again — and again — because the
model did not know what to do with what came back.  Nothing failed, so nothing
counts, and the Turn spends its whole round budget re-reading one answer.  This
module counts that instead.

Two decisions shape it.

**It decides, it does not act.**  Every function here is pure and every method
takes the history it judges.  The runtime owns what a verdict becomes — a
sentence of guidance folded into the next round's message, a synthetic result
handed back in place of a dispatch, or a controlled end to the Turn — because
those three all need a session, a publisher and a transcript, and a controller
that held any of them could not be tested by calling it a hundred times.

**The ladder scales with the round budget, and is not copied.**  The pattern
this borrows from warns after two identical failures and halts after eight,
which is sound for a harness with room for eight rounds.  ``MAX_TOOL_ROUNDS``
here is 4, so a halt at eight is a halt that never happens and a guardrail that
never halts is decoration.  The rungs are therefore a function of the budget,
passed in as ``max_rounds`` — the loop's constant is not imported, both to keep
the dependency pointing one way and because a test has to be able to ask what
the ladder looks like at other budgets.

At four rounds the ladder reads: the second identical call is warned, the third
is blocked before dispatch, and a fourth — a model that has been told twice —
halts the Turn on the evidence it already has.  A blocked call still counts as
an observation, because the signal the last rung acts on is precisely that the
guidance did not land.

Effect-capable tools skip the first rung.  Reading the same rows twice is a
wasted round; writing the same fact twice has a consequence, so the second
identical write is refused rather than mentioned.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from .tools.catalog import omit_nulls

#: Tools that answer a question and change nothing. Every one of them is a read:
#: the store-backed four, the ranking and watchlist reads, the registered-field
#: clusters, the two open-web reads, the news read, and the recall half of the
#: knowledge pair. Listed by name rather than derived from ``ToolDataAccess``
#: because that enum records *where a tool gets its data*, which is a different
#: question — ``fetch_url`` is external and idempotent, ``remember_fact`` is
#: store-only and not.
IDEMPOTENT_TOOLS = frozenset(
    {
        "cross_sectional",
        "fetch_url",
        "foreign_flow",
        "get_analysis",
        "get_company_profile",
        "get_financials",
        "get_price_series",
        "get_watchlist",
        "indicator_pack",
        "market_behavior",
        "price_zone",
        "recall_facts",
        "risk_metrics",
        "screen_universe",
        "search_news",
        "web_search",
    }
)

#: The tools known to leave something behind. ``remember_fact`` writes to the
#: knowledge store. ``run_python`` is here because its payload is code the model
#: wrote: the executor is networkless, but the *shape* of what runs inside it is
#: unknown to this module, and unknown is the case the rule below decides.
EFFECT_CAPABLE_TOOLS = frozenset({"remember_fact", "run_python"})


def is_idempotent(tool_name: str) -> bool:
    """Whether calling this tool twice is merely wasteful.

    Anything not named in :data:`IDEMPOTENT_TOOLS` is treated as effect-capable,
    and that default is the point of the function rather than a fallback. An MCP
    server's tools arrive at runtime under ``mcp__server__tool`` names nobody
    here has read; a plugin's shape is whatever it was configured to be. Guessing
    "harmless" about an unknown write is the one guess with a consequence, so the
    unknown side of the line is the safe side.

    :data:`EFFECT_CAPABLE_TOOLS` is consulted first so that a name which ends up
    in both sets — the shape a future edit takes when a read grows a write —
    resolves to the stricter reading rather than to whichever set was checked.
    """
    if tool_name in EFFECT_CAPABLE_TOOLS:
        return False
    return tool_name in IDEMPOTENT_TOOLS


class Verdict(str, Enum):
    """What the runtime is being told to do about the next call."""

    #: Dispatch it. Nothing about this call is a repetition.
    ALLOW = "allow"
    #: Dispatch it, and tell the model what it is repeating.
    WARN = "warn"
    #: Do not dispatch it; hand the model the guidance in its place.
    BLOCK = "block"
    #: Stop calling tools and answer with the evidence already gathered.
    HALT = "halt"

    @property
    def rank(self) -> int:
        """Where this sits on the ladder, so a round can take its strongest."""
        return _LADDER.index(self)


_LADDER = (Verdict.ALLOW, Verdict.WARN, Verdict.BLOCK, Verdict.HALT)

#: Stable reason codes. They are for the trace and the operational counter — the
#: plan's own signal that this module has stopped working is a ``halt`` count
#: that stays at zero forever — and never for a reader.
REPEATED_CALL = "repeated_call"
REPEATED_WRITE = "repeated_write"
FRUITLESS_REPEAT = "fruitless_repeat"

_HALT_GUIDANCE = (
    "Stop calling tools and answer with the evidence already gathered."
)


@dataclass(frozen=True)
class GuardrailThresholds:
    """How many prior observations each rung needs, for one round budget.

    Only the last rung scales. The first two are where they are because a
    repetition is worth mentioning the first time and worth refusing the second,
    at any budget; stretching them with the budget would produce the same
    unreachable ladder the docstring above rejects, one rung lower.
    """

    warn_repeats: int
    block_repeats: int
    halt_repeats: int
    #: How many results from one idempotent tool may add nothing before the
    #: model is told that tool is not the way in.
    fruitless_repeats: int

    @classmethod
    def for_rounds(cls, max_rounds: int) -> GuardrailThresholds:
        rounds = max(1, int(max_rounds))
        # A repetition can only be observed from the second round onwards, so
        # ``rounds - 1`` is the most a Turn can ever show — which makes it the
        # last rung that is still reachable, and reachability is the whole
        # requirement.
        halt = max(1, rounds - 1)
        return cls(
            warn_repeats=1,
            block_repeats=min(2, halt),
            halt_repeats=halt,
            fruitless_repeats=min(2, halt),
        )

    def block_at(self, *, effect_capable: bool) -> int:
        if effect_capable:
            return max(1, self.block_repeats - 1)
        return self.block_repeats

    def halt_at(self, *, effect_capable: bool) -> int:
        if effect_capable:
            return max(1, self.halt_repeats - 1)
        return self.halt_repeats


@dataclass(frozen=True)
class ObservedCall:
    """One call this Turn has already made, as the ladder needs to see it.

    ``progressed`` is the runtime's judgement, not this module's: whether the
    result added evidence the Turn did not already hold is a question about the
    Turn's evidence set, and answering it here would mean reading one. A call
    that was blocked rather than dispatched is still recorded — see the module
    docstring — with whatever the runtime knows about it.
    """

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    progressed: bool = True


@dataclass(frozen=True)
class PlannedCall:
    """One call the model has just asked for and nobody has dispatched yet."""

    call_id: str
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """One verdict, the code it is counted under, and the sentence to pass on.

    ``guidance`` is one sentence and it names the next action. A paragraph of
    diagnosis is what the model is already stuck in; what it lacks is an
    instruction, and a second sentence is a second thing to weigh.
    """

    verdict: Verdict
    reason: str = ""
    guidance: str = ""


@dataclass(frozen=True)
class RoundJudgement:
    """The ladder's reading of one whole round, before any of it is dispatched."""

    verdict: Verdict
    #: Every planned call, by call id, so a caller never has to ask twice.
    decisions: Mapping[str, Decision]
    #: The sentences to pass to the model, deduplicated, in call order.
    guidance: tuple[str, ...] = ()

    @property
    def blocked(self) -> tuple[str, ...]:
        """The calls the runtime must answer itself instead of dispatching."""
        return tuple(
            call_id
            for call_id, decision in self.decisions.items()
            if decision.verdict is Verdict.BLOCK
        )

    @property
    def refused(self) -> tuple[str, ...]:
        """Every call not to be dispatched — blocked, and the one that halted.

        A halt stops the *loop*, and the call that earned it is a repetition
        nobody needs an answer to. Its siblings are a different matter: they were
        emitted in the same round and may be the first time this Turn asked for
        what they ask for. So a halt refuses itself and lets them run, and the
        Turn answers after them rather than instead of them.
        """
        return tuple(
            call_id
            for call_id, decision in self.decisions.items()
            if decision.verdict in (Verdict.BLOCK, Verdict.HALT)
        )


_ALLOWED = Decision(Verdict.ALLOW)


def _fingerprint(tool_name: str, arguments: Mapping[str, Any]) -> str:
    """One canonical spelling of "this exact call".

    ``omit_nulls`` runs first because strict mode gives the model two ways to
    write the same call — an absent optional key, and the same key set to null
    (``tools.catalog``) — and a guardrail that told them apart could be walked
    straight past by alternating between them.
    """
    return json.dumps(
        [tool_name, omit_nulls(arguments)],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


class GuardrailLadder:
    """The decision table, holding nothing but its thresholds.

    Constructed once per Turn with the round budget that Turn was admitted
    against. Nothing is recorded on it: the history arrives with every question,
    which is what makes the same question answerable a hundred times over with
    the same answer.
    """

    def __init__(self, *, max_rounds: int) -> None:
        self.thresholds = GuardrailThresholds.for_rounds(max_rounds)

    def judge_call(
        self,
        planned: PlannedCall,
        history: Sequence[ObservedCall] = (),
    ) -> Decision:
        """What to do about one call, given everything the Turn already did."""
        candidates = (
            self._repetition(planned, history),
            self._fruitlessness(planned, history),
        )
        # ``max`` keeps the first of equal ranks, so repetition — the more
        # specific complaint, and the one whose guidance names an argument the
        # model can change — wins a tie against fruitlessness.
        return max(candidates, key=lambda decision: decision.verdict.rank)

    def judge_round(
        self,
        planned: Sequence[PlannedCall],
        history: Sequence[ObservedCall] = (),
    ) -> RoundJudgement:
        """What to do about a whole round of parallel calls.

        A copy of a call already in this same round is **blocked outright**,
        whatever rung the ladder would otherwise have reached. The rungs are
        about a model asking again after reading an answer, and inside one round
        nobody has read anything: every call in it was decided before any of them
        ran. So the first one runs, the copies are answered by it, and neither the
        tolerance the first rung grants nor the halt the last one would reach
        applies to a duplicate that cost the Turn nothing to notice.

        The one exception is a call the *Turn's own history* already halts on.
        That halt is not the round's doing and stands.

        Earlier calls of the same round still join the history as the round is
        read, so the count behind a verdict is the whole round. They join it as
        having progressed, because a call whose result nobody has seen cannot be
        evidence that a tool is fruitless.
        """
        seen = list(history)
        decisions: dict[str, Decision] = {}
        guidance: list[str] = []
        within_round: set[str] = set()
        for call in planned:
            fingerprint = _fingerprint(call.tool_name, call.arguments)
            decision = self.judge_call(call, seen)
            if fingerprint in within_round:
                standing = self.judge_call(call, history)
                decision = (
                    standing
                    if standing.verdict is Verdict.HALT
                    else self._duplicate(call, decision)
                )
            within_round.add(fingerprint)
            decisions[call.call_id] = decision
            if decision.guidance and decision.guidance not in guidance:
                guidance.append(decision.guidance)
            seen.append(
                ObservedCall(
                    tool_name=call.tool_name,
                    arguments=call.arguments,
                    progressed=True,
                )
            )
        verdict = max(
            (decision.verdict for decision in decisions.values()),
            key=lambda value: value.rank,
            default=Verdict.ALLOW,
        )
        return RoundJudgement(
            verdict=verdict,
            decisions=MappingProxyType(decisions),
            guidance=tuple(guidance),
        )

    def _duplicate(self, planned: PlannedCall, ladder: Decision) -> Decision:
        """A copy of a call already in this round, refused as one.

        The reason travels from the ladder so the counter still records which
        kind of repetition this was, and the guidance says what is true of *this*
        call rather than what a rung would have said: the copies are refused and
        the first one is about to answer them all.
        """
        return Decision(
            Verdict.BLOCK,
            ladder.reason or (
                REPEATED_CALL if is_idempotent(planned.tool_name) else REPEATED_WRITE
            ),
            f"{planned.tool_name} is already in this round with these exact "
            "arguments — one answer covers all of them.",
        )

    def _repetition(
        self,
        planned: PlannedCall,
        history: Sequence[ObservedCall],
    ) -> Decision:
        """The same call, asked again."""
        effect_capable = not is_idempotent(planned.tool_name)
        target = _fingerprint(planned.tool_name, planned.arguments)
        repeats = sum(
            1
            for observed in history
            if _fingerprint(observed.tool_name, observed.arguments) == target
        )
        if not repeats:
            return _ALLOWED
        reason = REPEATED_WRITE if effect_capable else REPEATED_CALL
        if repeats >= self.thresholds.halt_at(effect_capable=effect_capable):
            return Decision(Verdict.HALT, reason, _HALT_GUIDANCE)
        if repeats >= self.thresholds.block_at(effect_capable=effect_capable):
            if effect_capable:
                guidance = (
                    f"{planned.tool_name} has already recorded this — continue "
                    "with the evidence you have instead of writing it again."
                )
            else:
                guidance = (
                    f"{planned.tool_name} has already answered these exact "
                    "arguments — use that answer or call a different tool."
                )
            return Decision(Verdict.BLOCK, reason, guidance)
        if repeats >= self.thresholds.warn_repeats:
            return Decision(
                Verdict.WARN,
                reason,
                f"You already called {planned.tool_name} with these arguments; "
                "change the arguments or move on to the answer.",
            )
        return _ALLOWED

    def _fruitlessness(
        self,
        planned: PlannedCall,
        history: Sequence[ObservedCall],
    ) -> Decision:
        """One tool asked repeatedly, answering nothing new each time.

        Counted per tool and not per argument, which is why it never blocks and
        **never halts**: the same tool asked about a second symbol is a different
        question, and refusing it would cost the Turn evidence it was right to go
        looking for. Only an effectless tool is judged here — a write that changed
        nothing is the write's own business, and this module cannot see it.

        The ceiling was a halt when this was first written, and that was wrong in
        a way worth recording. A Structured Refusal is what the runtime reads as
        "no progress", and refusals arrive in ordinary bunches: three symbols
        outside the Universe, three searches while the open web is down, three
        windows too short for the field. Counting per tool, the fourth call —
        with arguments nobody had tried — reached the halt rung and ended the tool
        loop, and because a round is judged whole it took every sibling call with
        it. A tool that keeps coming back empty is worth a sentence, not the rest
        of the Turn's evidence budget.
        """
        if not is_idempotent(planned.tool_name):
            return _ALLOWED
        fruitless = sum(
            1
            for observed in history
            if observed.tool_name == planned.tool_name and not observed.progressed
        )
        if fruitless >= self.thresholds.fruitless_repeats:
            return Decision(
                Verdict.WARN,
                FRUITLESS_REPEAT,
                f"{planned.tool_name} has returned nothing new {fruitless} "
                "times; try another tool or state what is unavailable.",
            )
        return _ALLOWED


__all__ = [
    "EFFECT_CAPABLE_TOOLS",
    "FRUITLESS_REPEAT",
    "IDEMPOTENT_TOOLS",
    "REPEATED_CALL",
    "REPEATED_WRITE",
    "Decision",
    "GuardrailLadder",
    "GuardrailThresholds",
    "ObservedCall",
    "PlannedCall",
    "RoundJudgement",
    "Verdict",
    "is_idempotent",
]
