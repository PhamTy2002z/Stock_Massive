"""Running the tool calls one round produced, and recording what happened.

The model emits a batch of calls. Some of them can run at the same time and some
cannot, and the difference is not a performance detail: two reads overlapping is
free, while a write overlapping anything makes the order the model asked for
unobservable. So the batch is planned into segments before anything runs —
consecutive parallel-safe calls become one ``parallel`` segment, and everything
else becomes its own ``sequential`` barrier.

Three rules hold throughout.

**Unknown means sequential.** A tool this module has never heard of gets a
barrier, because the only thing we know about it is that we do not know whether
it writes. Guessing "safe" about an unknown write is the guess with a
consequence.

**The model's order is preserved.** Results come back in the order the calls were
issued, whatever order they executed in. The model reads its own batch back.

**Every call produces exactly one result.** A blocked call, an unknown tool, a
handler that raised, a call skipped because the Turn halted, a call this module
itself failed to dispatch, a call past the round's ceiling, a call the reader's
stop tore down in flight — each returns a result carrying the reason. A tool call
with no result is a conversation the provider will reject, so there is no path
here that drops one. That includes this module's own failures: ``_dispatch``
guards the handler and the arguments, but the registry lookup, the availability
check and the trace write sit outside those guards, and an exception there used
to cancel every sibling in the ``gather`` and take the round's gathered results
with it.

**A stop ends the reads and lets a write finish.** Given a ``cancel_event``, this
module stops at the next segment boundary and answers everything still owed a
result with :data:`CANCELLED_CALL`. Inside a parallel segment — reads only, by
construction of :func:`plan_segments` — the calls still in flight are cancelled,
and each of them reports that it *was* dispatched, because it was: the read left
here, and whether the other side served it is not knowable from this side. A
sequential barrier that has already started is never cancelled, which is where
the property that no external effect happens twice is held: the one tool that
writes runs to its end and answers with what it did, and the calls behind it are
settled by the boundary check when it returns.

**A round has two ceilings, because a round has two kinds of call.**
:data:`MAX_EXTERNAL_CALLS_PER_ROUND` bounds the calls that leave this deployment
and :data:`MAX_STORE_CALLS_PER_ROUND` the ones that do not; the rest are answered
with the reason, in the order the model issued them, so the head of a batch runs
and the tail is told it was cut. Unbounded fan-out is two problems at once: a
round timeout shared by forty concurrent reads, and a way past the repetition
ladder, whose ``before_call`` verdicts for one batch are all decided before its
first ``after_call`` records anything.

Two ceilings rather than one because the single ceiling this replaces was derived
from the *external* allowance and then applied to every call — which is the same
conflation ``loop.MAX_EXTERNAL_TOOL_CALLS`` already refuses to make. Reading a
symbol's field catalog is thirty Postgres queries inside the deployment, and it
is the shape a question about one symbol legitimately has; refusing it under a
number that exists because a web search costs money spends the web allowance on
evidence that costs nothing.

**What a call is allowed to do, and for how long, is read off its declaration.**
A tool whose registration says it may not run, or needs a person's agreement
first, is refused here before its arguments are even parsed, and a call that
outlives the bound its registration declared is given up on and answered. Both
are typed results rather than exceptions, for the same reason as everything
else on this page: the model is owed one result per call, and "you were not
allowed to do that" and "that took too long" are two things it can act on.

Concurrency is ``asyncio`` and not a thread pool: this codebase is async
throughout, and the one case that genuinely blocks — a handler that declares
``is_async=False`` — is moved to a worker thread individually rather than making
every call pay for a pool.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from . import registry
from .definitions import ResolvedToolSurface
from .guardrails import HALT_GUIDANCE, TurnGuardrails, Verdict, result_signature
from .untrusted import scan_for_threats

logger = logging.getLogger(__name__)

UNKNOWN_TOOL = "unknown_tool"
TOOL_UNAVAILABLE = "tool_unavailable"
INVALID_ARGUMENTS = "invalid_arguments"
BLOCKED_CALL = "blocked_call"
HALTED_TURN = "halted_turn"
TOOL_FAILED = "tool_failed"
#: The declaration says this call may not be made. One code for every reason a
#: permission rule withholds a call, because the model's move is the same in all
#: of them: this route is closed, find another one.
PERMISSION_DENIED = "permission_denied"
#: The call outlived the bound its own declaration set. Distinct from
#: ``tool_failed`` because the tool did not fail — it was still working — and the
#: model's move is different: ask for less, not something else.
TOOL_CALL_TIMEOUT = "tool_call_timeout"
#: This module broke, rather than the tool or the route. Its own code, so its
#: own name: ``tool_failed`` would file a harness bug under the tool that was
#: working, and the operational count that matters is the one nobody expects to
#: be non-zero.
DISPATCH_FAILED = "dispatch_failed"
#: Answered rather than dropped, and answered rather than raised: the round's
#: ceiling is a limit on what runs, not on what the model hears back.
ROUND_FANOUT_EXCEEDED = "round_fanout_exceeded"
#: The reader stopped the Turn before this call could answer. Its own code, and
#: not ``halted_turn``: a halt is this harness deciding the tool loop has gone
#: wrong, and this is a person deciding they no longer want the answer. Nothing
#: is wrong with the tool, and nothing about it should be retried on that
#: account.
CANCELLED_CALL = "cancelled"

#: How many calls that leave this deployment one round dispatches. Arithmetic
#: rather than taste: a Turn gets seven of them in total
#: (``loop.MAX_EXTERNAL_TOOL_CALLS``, raised from six on 2026-08-29), so a round
#: asking for more than eight has already asked for more than the whole Turn can
#: fund. Eight rather than seven keeps the refusal here about the *shape* of the
#: batch and leaves the budget itself to be spent, and refused, where it is
#: counted. The margin is now one call rather than two, and that is the reason
#: the Turn ceiling was held below eight: at eight the two gates would coincide
#: and this one would start firing on batches the budget was going to fund.
MAX_EXTERNAL_CALLS_PER_ROUND = 8

#: How many calls that stay inside this deployment one round dispatches. Also
#: arithmetic: the Signal Field catalog holds thirty fields
#: (``tools/signals.py``), so a question about one symbol can legitimately want
#: all thirty in a single round, and two spare leave room for control calls
#: that found them and a price claim checked beside them.
#:
#: It is a ceiling and not an absence of one. Thirty-two concurrent reads share a
#: round timeout, and the repetition ladder still decides a whole batch's
#: ``before_call`` verdicts before its first ``after_call`` records anything —
#: both of those hold however cheap the individual read is.
MAX_STORE_CALLS_PER_ROUND = 32

Mode = Literal["parallel", "sequential"]
Segment = tuple[Mode, tuple["ToolCall", ...]]
TraceWriter = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ToolCall:
    """One call as the model issued it.

    ``arguments`` is whatever the provider handed over: the raw JSON string in
    the normal case, an already-parsed mapping when a caller has one. Parsing is
    this module's job because a malformed argument object is a *result* — the
    model has to be told what was wrong with it — and not an exception the loop
    has to catch.
    """

    id: str
    name: str
    arguments: str | Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ToolResult:
    """What one call produced, in the shape the message layer needs."""

    call_id: str
    tool_name: str
    ok: bool
    text: str = ""
    payload: Any = None
    error: str | None = None
    guidance: str | None = None
    dispatched: bool = True
    duration_ms: int = 0
    #: What the advisory threat scan made of this result, or ``None`` where
    #: there was nothing to scan.
    #:
    #: ``None`` for every call whose text this deployment wrote itself — a
    #: refusal, a ceiling, a tool that raised. Scanning our own sentences would
    #: put a risk verdict on the harness talking to itself, which is noise in the
    #: one place the signal has to stay readable.
    scan: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ExecutionOutcome:
    """One batch, executed. ``halted`` ends the Turn after this batch."""

    results: tuple[ToolResult, ...]
    halted: bool = False
    halt_reason: str | None = None
    guidance: str | None = None


ToolDeclaration = registry.ToolEntry | registry.ResolvedTool
ToolLookup = Callable[[str], ToolDeclaration | None]


def plan_segments(
    calls: Sequence[ToolCall], *, lookup: ToolLookup = registry.get
) -> tuple[Segment, ...]:
    """Group a batch into what may overlap and what must not, order intact."""
    segments: list[Segment] = []
    run: list[ToolCall] = []
    for call in calls:
        try:
            declared = lookup(call.name)
        except Exception:  # noqa: BLE001 - unknown policy is a serial barrier
            declared = None
        if (
            declared is not None
            and declared.effect is registry.ToolEffect.READ
            and declared.concurrency is registry.ToolConcurrency.PARALLEL_SAFE
        ):
            run.append(call)
            continue
        if run:
            segments.append(("parallel", tuple(run)))
            run = []
        segments.append(("sequential", (call,)))
    if run:
        segments.append(("parallel", tuple(run)))
    return tuple(segments)


@dataclass
class ToolExecutor:
    """Dispatch a batch of calls under one Turn's guardrails."""

    context: registry.ToolContext
    guardrails: TurnGuardrails = field(default_factory=TurnGuardrails)
    trace: TraceWriter | None = None
    #: Set when the reader stops the Turn this batch belongs to. Absent means a
    #: batch that cannot be stopped, which is what every caller without a Turn
    #: behind it — a test, a harness — legitimately is.
    cancel_event: asyncio.Event | None = None
    #: The immutable lane-selected declaration snapshot for this task. When it
    #: is present, a globally registered name outside the selection is unknown
    #: to this executor and cannot dispatch.
    surface: ResolvedToolSurface | None = None
    #: Injectable so a test can register tools without touching the process-wide
    #: registry, and so a future per-user surface can narrow what is visible.
    lookup: ToolLookup = registry.get
    availability: Callable[[str], bool] = registry.is_available

    def _lookup(self, name: str) -> ToolDeclaration | None:
        if self.surface is not None:
            return self.surface.by_name.get(name)
        return self.lookup(name)

    def _reads_external(self, name: str) -> bool:
        """Whether this call leaves the deployment, asked through ``lookup``.

        Through ``lookup`` rather than ``registry.reads_external`` so the two
        reasons ``lookup`` is injectable still hold for the ceiling: a test
        registers tools without touching the process-wide registry, and a
        per-user surface narrows what is visible. Reading the global registry
        here would answer for a tool this executor cannot even dispatch.

        Unknown means external, which is the registry's own default and the same
        direction of caution: a tool nobody classified is charged the expensive
        ceiling rather than the cheap one.

        A ``lookup`` that *raises* is unknown too, and is caught here rather than
        left to propagate. This runs while admitting the batch — before anything
        is dispatched and outside ``_dispatch``'s guards — so an exception
        escaping would take the whole round down over a classification, which is
        the failure the module docstring's third rule exists to prevent. The call
        still meets its real lookup on the dispatch path, and is answered there.
        """
        try:
            entry = self._lookup(name)
        except Exception:  # noqa: BLE001 - classification must not end a round
            return True
        return True if entry is None else entry.access is registry.ToolAccess.NETWORK

    def _admit(self, calls: Sequence[ToolCall]) -> set[str]:
        """Which of this batch's calls are dispatched, by kind and in issued order."""
        remaining = {
            True: MAX_EXTERNAL_CALLS_PER_ROUND,
            False: MAX_STORE_CALLS_PER_ROUND,
        }
        admitted: set[str] = set()
        for call in calls:
            kind = self._reads_external(call.name)
            if remaining[kind] > 0:
                remaining[kind] -= 1
                admitted.add(call.id)
        return admitted

    async def run(self, calls: Sequence[ToolCall]) -> ExecutionOutcome:
        """Execute one batch and return its results in the issued order."""
        results: dict[str, ToolResult] = {}
        halt_reason: str | None = None
        guidance: str | None = None
        # The ceilings are taken over the batch as the model issued it rather
        # than segment by segment: the head of the batch runs and the tail is
        # refused, so the model reads its own order back with the cut where it
        # made it. Each kind of call is counted against its own ceiling, so a
        # batch of thirty store reads does not push a single web search out and
        # a batch of thirty searches does not push a store read out.
        admitted = self._admit(calls)
        for mode, segment in plan_segments(calls, lookup=self._lookup):
            for call in segment:
                if call.id not in admitted:
                    results[call.id] = await self._over_ceiling(call, len(calls))
            runnable = tuple(call for call in segment if call.id in admitted)
            if not runnable:
                continue
            if self._stopped():
                # The boundary check, and the only place a not-yet-started call
                # meets a cancellation. It is also what settles the tail of a
                # batch whose barrier was allowed to finish: the write returns,
                # this check sees the stop, and everything behind it is answered
                # rather than dispatched into a Turn that has ended.
                for call in runnable:
                    results[call.id] = self._cancelled(call, dispatched=False)
                continue
            if self.guardrails.halted:
                for call in runnable:
                    results[call.id] = self._skipped(call)
                continue
            completed: list[ToolResult | BaseException]
            # One call gets the concurrent path too when there is a stop to race
            # it against: whether a read can be given up on must not depend on
            # how many calls the model happened to put in one round.
            if mode == "parallel" and (
                len(runnable) > 1 or self.cancel_event is not None
            ):
                completed = await self._parallel(runnable)
            else:
                completed = [await self._attempt(call) for call in runnable]
            for call, finished in zip(runnable, completed, strict=True):
                results[call.id] = (
                    finished
                    if isinstance(finished, ToolResult)
                    else self._dispatch_failed(call, finished)
                )
        if self.guardrails.halted:
            halt_reason = HALTED_TURN
            guidance = HALT_GUIDANCE
        ordered = tuple(
            results.get(call.id) or self._skipped(call) for call in calls
        )
        return ExecutionOutcome(
            results=ordered,
            halted=self.guardrails.halted,
            halt_reason=halt_reason,
            guidance=guidance,
        )

    def _stopped(self) -> bool:
        """Whether the reader has stopped the Turn this batch belongs to."""
        return self.cancel_event is not None and self.cancel_event.is_set()

    async def _parallel(
        self, runnable: Sequence[ToolCall]
    ) -> list[ToolResult | BaseException]:
        """Run one parallel segment, given up on the moment the reader stops.

        ``return_exceptions`` because the alternative is a sibling's failure
        cancelling calls that were about to succeed, and then a Turn that ends
        under ``turn_failed`` having thrown away everything the round had already
        paid for.

        The stop is raced against the batch rather than polled between calls:
        polling would mean the reader waits out whichever read is slowest, which
        on a page fetch is the whole reason they pressed stop. A call that had
        already answered keeps its real result — it is paid for, and throwing it
        away would make the trace of a cancelled Turn less true than the Turn was.
        """
        tasks = [asyncio.ensure_future(self._dispatch(call)) for call in runnable]
        stop = self.cancel_event
        if stop is None:
            return list(await asyncio.gather(*tasks, return_exceptions=True))
        stopped = asyncio.ensure_future(stop.wait())
        pending: set[asyncio.Future[Any]] = {*tasks, stopped}
        try:
            while not stopped.done() and any(not task.done() for task in tasks):
                _done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
        except asyncio.CancelledError:
            # This batch's own ceiling, or the process being torn down. Neither
            # is survivable here, and neither may leave a dispatch running with
            # nobody waiting for it.
            for task in tasks:
                task.cancel()
            raise
        finally:
            stopped.cancel()
        for task in tasks:
            # A no-op for everything that already answered, and the teardown for
            # everything that had not.
            task.cancel()
        # Awaited rather than abandoned: a cancelled task nobody awaits is a
        # warning on the event loop and a handler that never got to run its
        # ``finally``.
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            self._cancelled(call, dispatched=True)
            if isinstance(outcome, asyncio.CancelledError)
            else outcome
            for call, outcome in zip(runnable, gathered, strict=True)
        ]

    def _cancelled(self, call: ToolCall, *, dispatched: bool) -> ToolResult:
        """The reader stopped the Turn, and this call is told apart by when.

        ``dispatched`` is a fact about this call rather than a policy: a call torn
        down in flight had already been sent, and one the stop reached before its
        segment ran had not. Neither will be read by the model — the Turn is over
        — but the transcript, the trace and a recovered draft all will be, and a
        record claiming a read never left when it did is the record that hides
        whatever it did on the way.
        """
        return ToolResult(
            call_id=call.id,
            tool_name=call.name,
            ok=False,
            error=CANCELLED_CALL,
            text=(
                "The reader stopped this turn while this call was running."
                if dispatched
                else "The reader stopped this turn before this call ran."
            ),
            dispatched=dispatched,
        )

    async def _dispatch(self, call: ToolCall) -> ToolResult:
        entry = self._lookup(call.name)
        if entry is None:
            return await self._record(
                call,
                {},
                ToolResult(
                    call_id=call.id,
                    tool_name=call.name,
                    ok=False,
                    error=UNKNOWN_TOOL,
                    text=f"No tool named {call.name} exists.",
                    dispatched=False,
                ),
            )
        # A tool absent from the offered schema cannot become callable during
        # the task.  The live check may only revoke an offered capability; it
        # cannot widen the frozen surface after the model request was built.
        if (
            isinstance(entry, registry.ResolvedTool) and not entry.available
        ) or not self.availability(call.name):
            return await self._record(
                call,
                {},
                ToolResult(
                    call_id=call.id,
                    tool_name=call.name,
                    ok=False,
                    error=TOOL_UNAVAILABLE,
                    text=f"{call.name} is not available in this deployment.",
                    dispatched=False,
                ),
            )
        refusal = _permission_refusal(call.name, entry.permission)
        if refusal is not None:
            return await self._record(
                call,
                {},
                ToolResult(
                    call_id=call.id,
                    tool_name=call.name,
                    ok=False,
                    error=PERMISSION_DENIED,
                    text=refusal,
                    dispatched=False,
                ),
            )
        try:
            arguments = _parse_arguments(call.arguments)
        except ValueError as exc:
            return await self._record(
                call,
                {},
                ToolResult(
                    call_id=call.id,
                    tool_name=call.name,
                    ok=False,
                    error=INVALID_ARGUMENTS,
                    text=str(exc),
                    dispatched=False,
                ),
            )

        decision = self.guardrails.before_call(call.name, arguments)
        if decision.verdict in {Verdict.BLOCK, Verdict.HALT}:
            error = BLOCKED_CALL if decision.verdict is Verdict.BLOCK else HALTED_TURN
            return await self._record(
                call,
                arguments,
                ToolResult(
                    call_id=call.id,
                    tool_name=call.name,
                    ok=False,
                    error=error,
                    text=decision.guidance or "",
                    guidance=decision.guidance,
                    dispatched=False,
                ),
            )

        started = time.perf_counter()

        # The handler's own exceptions are captured *inside* the awaited
        # coroutine, so the only ``TimeoutError`` that can escape ``wait_for``
        # is the one ``wait_for`` itself raises at the declared bound. Without
        # this seam the two are indistinguishable: a socket timeout is a
        # ``TimeoutError`` too (``socket.timeout`` is the same class), and a
        # wire that gave up after eight seconds would be reported as a call
        # that used up its whole declared allowance, with the wrong number in
        # the sentence the model acts on.
        async def _attempted() -> tuple[Any, Exception | None]:
            try:
                return await self._invoke(entry, arguments), None
            except Exception as exc:  # noqa: BLE001 - a tool failure is a result
                return None, exc

        failure: Exception | None = None
        try:
            payload, failure = await asyncio.wait_for(
                _attempted(), timeout=entry.timeout_seconds
            )
        except TimeoutError:
            logger.warning(
                "Tool %s passed its declared bound of %.1fs",
                call.name,
                entry.timeout_seconds,
            )
            payload, ok, error = None, False, TOOL_CALL_TIMEOUT
            text = (
                f"{call.name} was still running after the {entry.timeout_seconds:g} "
                "seconds its declaration allows one call, so it was given up on. "
                "Ask for something narrower, or use what the other calls returned."
            )
        else:
            if failure is None:
                ok, error, text = True, None, _normalize(payload)
            else:
                logger.warning("Tool %s failed: %s", call.name, failure)
                payload, ok, error = None, False, TOOL_FAILED
                text = f"{call.name} failed: {failure}"
        elapsed = int((time.perf_counter() - started) * 1000)

        # Scanned here, once, and deliberately not on the render path. What the
        # model reads is rebuilt on every LLM call of the Turn (``shown_result``),
        # so a scan living there would re-read a twenty-thousand-character page up
        # to five times for one answer and produce the same verdict each time.
        # This is where the result exists for the first time.
        scan = (
            scan_for_threats(text)
            if ok and self._reads_external(call.name)
            else None
        )

        after = self.guardrails.after_call(
            call.name, arguments, ok=ok, result_hash=result_signature(text)
        )
        return await self._record(
            call,
            arguments,
            ToolResult(
                call_id=call.id,
                tool_name=call.name,
                ok=ok,
                text=text,
                payload=payload,
                error=error,
                # A warning rides with the result rather than replacing it: the
                # model that lost the thread still needs the data to find it.
                guidance=after.guidance,
                duration_ms=elapsed,
                scan=scan,
            ),
        )

    async def _invoke(
        self, entry: ToolDeclaration, arguments: Mapping[str, Any]
    ) -> Any:
        """Run one handler the way its declaration says it has to be run.

        The caller bounds this with the declaration's own ``timeout_seconds``,
        and for an async handler that bound also cancels the work. For a
        declared-blocking one it does not: a thread cannot be cancelled from
        outside, so what the bound buys is the round getting its answer back on
        time while the thread keeps running until whatever internal limit the
        handler set — a socket timeout, a statement timeout — ends it. That is
        the honest trade, and it is why the bound belongs on the declaration
        beside those internal limits rather than being invented here.
        """
        if entry.is_async:
            outcome = entry.handler(self.context, arguments)
            if inspect.isawaitable(outcome):
                return await outcome
            return outcome
        # A declared-blocking handler is moved off the event loop, so one slow
        # database read cannot stall the other calls of the same round.
        return await asyncio.to_thread(entry.handler, self.context, arguments)

    async def _attempt(self, call: ToolCall) -> ToolResult:
        """One call from a sequential segment, under the parallel path's floor.

        ``gather(return_exceptions=True)`` catches whatever escapes
        :meth:`_dispatch` in a parallel segment. A sequential segment runs
        outside that gather, so the same floor is spelled out here — otherwise
        one raising barrier still takes the round, and a barrier is exactly the
        call most likely to be a write.
        """
        try:
            return await self._dispatch(call)
        except Exception as exc:  # noqa: BLE001 - our own failure is a result too
            return self._dispatch_failed(call, exc)

    def _dispatch_failed(self, call: ToolCall, error: BaseException) -> ToolResult:
        """This module failed, and the batch still owes the model a result.

        Logged at ``warning`` and counted under its own code, because a bug
        turned into a result is a bug that has to stay visible somewhere. No
        trace entry: the trace write is one of the things that can land here.
        """
        logger.warning("Could not dispatch %s: %r", call.name, error)
        return ToolResult(
            call_id=call.id,
            tool_name=call.name,
            ok=False,
            error=DISPATCH_FAILED,
            text=f"{call.name} could not be run: {error}",
            dispatched=False,
        )

    async def _over_ceiling(self, call: ToolCall, issued: int) -> ToolResult:
        """A call past the round's ceiling, told what happened and what to do.

        Traced, and warned about, because a ceiling nobody can see firing is a
        ceiling nobody can tune. The number to raise or lower it by is the rate
        it turns away batches on healthy traffic, and that rate is a count of
        these rows. Unlike :meth:`_dispatch_failed` there is no risk of writing
        a trace about a failed trace write here: nothing has been dispatched and
        nothing has failed except the model asking for too much at once.
        """
        external = self._reads_external(call.name)
        ceiling = (
            MAX_EXTERNAL_CALLS_PER_ROUND if external else MAX_STORE_CALLS_PER_ROUND
        )
        kind = "calls that leave this deployment" if external else "store reads"
        logger.warning(
            "A round issued %d tool calls; %s was past the ceiling of %d %s",
            issued,
            call.name,
            ceiling,
            kind,
        )
        return await self._record(
            call,
            {},
            ToolResult(
                call_id=call.id,
                tool_name=call.name,
                ok=False,
                error=ROUND_FANOUT_EXCEEDED,
                text=(
                    f"This round issued {issued} tool calls, and only the first "
                    f"{ceiling} {kind} were run, so this one was not dispatched. "
                    "Ask for fewer of that kind at a time, and reissue what still "
                    "matters."
                ),
                dispatched=False,
            ),
        )

    def _skipped(self, call: ToolCall) -> ToolResult:
        return ToolResult(
            call_id=call.id,
            tool_name=call.name,
            ok=False,
            error=HALTED_TURN,
            text="This turn stopped calling tools before this call ran.",
            dispatched=False,
        )

    async def _record(
        self, call: ToolCall, arguments: Mapping[str, Any], result: ToolResult
    ) -> ToolResult:
        """Write one trace entry for one call, dispatched or not.

        Two paths deliberately do not come here. :meth:`_dispatch_failed` cannot,
        because the trace write is one of the things that can land there.
        :meth:`_skipped` does not, because the call the halt was declared on
        already wrote its own row and the ones behind it were never attempted.
        """
        if self.trace is None:
            return result
        entry = {
            "call_id": result.call_id,
            "tool": result.tool_name,
            "arguments": dict(arguments),
            "ok": result.ok,
            "error": result.error,
            "guidance": result.guidance,
            "dispatched": result.dispatched,
            "duration_ms": result.duration_ms,
            # The body as well as its size, because the Tool Call Trace is the
            # audit record of what an answer rested on. What is stored is
            # trimmed by whoever writes the row, which is the only layer that
            # knows the Turn's budget.
            "result_text": result.text,
            "result_chars": len(result.text),
        }
        try:
            written = self.trace(entry)
            if inspect.isawaitable(written):
                await written
        except Exception as exc:  # noqa: BLE001 - a lost trace is not a lost answer
            logger.warning("Could not record the trace for %s: %s", call.name, exc)
        return result


def _permission_refusal(
    name: str, permission: registry.ToolPermission | None
) -> str | None:
    """Why this call may not be made, or ``None`` when it may.

    Three answers rather than one sentence reused three times, because the model
    can do something different with each: a denied tool is closed here for good,
    a tool waiting on approval may open later, and a declaration carrying no
    permission at all is this deployment's own bug.

    That last case is refused rather than allowed. A registered tool cannot
    reach it — :func:`registry.register` refuses an unset permission — so it can
    only arrive from a declaration assembled outside the registry, which is the
    kind of declaration least entitled to the benefit of the doubt.
    """
    if permission is registry.ToolPermission.ALLOW:
        return None
    if permission is registry.ToolPermission.DENY:
        return f"{name} is not permitted in this deployment."
    if permission is registry.ToolPermission.ASK:
        return (
            f"{name} may only run once a person has agreed to it, and there is "
            "no way to ask for that agreement here yet, so the call was refused "
            "rather than made on nobody's authority."
        )
    return (
        f"{name} was declared without saying whether it may run, so it was "
        "not run."
    )


def _parse_arguments(raw: str | Mapping[str, Any] | None) -> Mapping[str, Any]:
    """The model's arguments as a mapping, or a message saying why they are not."""
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"the arguments are not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, Mapping):
        raise ValueError("the arguments must be a JSON object")
    return dict(parsed)


def _normalize(payload: Any) -> str:
    """One textual form for whatever a handler returned.

    Structured payloads become compact JSON because that is what the model reads
    best and what the budget can measure; a handler that already returns prose is
    passed through untouched.
    """
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(payload)


__all__ = [
    "BLOCKED_CALL",
    "CANCELLED_CALL",
    "DISPATCH_FAILED",
    "HALTED_TURN",
    "INVALID_ARGUMENTS",
    "MAX_EXTERNAL_CALLS_PER_ROUND",
    "MAX_STORE_CALLS_PER_ROUND",
    "PERMISSION_DENIED",
    "ROUND_FANOUT_EXCEEDED",
    "TOOL_CALL_TIMEOUT",
    "TOOL_FAILED",
    "TOOL_UNAVAILABLE",
    "UNKNOWN_TOOL",
    "ExecutionOutcome",
    "Segment",
    "ToolCall",
    "ToolExecutor",
    "ToolResult",
    "plan_segments",
]
