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
handler that raised, a call skipped because the Turn halted — each returns a
result carrying the reason. A tool call with no result is a conversation the
provider will reject, so there is no path here that drops one.

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
from .guardrails import HALT_GUIDANCE, TurnGuardrails, Verdict, result_signature

logger = logging.getLogger(__name__)

#: The tools that answer a question and change nothing, so a round may run them
#: at once. Listed by name rather than derived from a toolset, because "reads the
#: open web" and "changes nothing" are different properties: ``fetch_url`` is
#: external and idempotent, ``remember_fact`` is local and not.
#:
#: ``remember_fact`` is the one tool in the current surface that is absent here,
#: and that is the whole point of the allowlist.
PARALLEL_SAFE_TOOLS = frozenset(
    {
        "web_search",
        "fetch_url",
        "session_search",
        "recall_facts",
    }
)

UNKNOWN_TOOL = "unknown_tool"
TOOL_UNAVAILABLE = "tool_unavailable"
INVALID_ARGUMENTS = "invalid_arguments"
BLOCKED_CALL = "blocked_call"
HALTED_TURN = "halted_turn"
TOOL_FAILED = "tool_failed"

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


@dataclass(frozen=True)
class ExecutionOutcome:
    """One batch, executed. ``halted`` ends the Turn after this batch."""

    results: tuple[ToolResult, ...]
    halted: bool = False
    halt_reason: str | None = None
    guidance: str | None = None


def plan_segments(calls: Sequence[ToolCall]) -> tuple[Segment, ...]:
    """Group a batch into what may overlap and what must not, order intact."""
    segments: list[Segment] = []
    run: list[ToolCall] = []
    for call in calls:
        if call.name in PARALLEL_SAFE_TOOLS:
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
    #: Injectable so a test can register tools without touching the process-wide
    #: registry, and so a future per-user surface can narrow what is visible.
    lookup: Callable[[str], registry.ToolEntry | None] = registry.get
    availability: Callable[[str], bool] = registry.is_available

    async def run(self, calls: Sequence[ToolCall]) -> ExecutionOutcome:
        """Execute one batch and return its results in the issued order."""
        results: dict[str, ToolResult] = {}
        halt_reason: str | None = None
        guidance: str | None = None
        for mode, segment in plan_segments(calls):
            if self.guardrails.halted:
                for call in segment:
                    results[call.id] = self._skipped(call)
                continue
            if mode == "parallel" and len(segment) > 1:
                completed = await asyncio.gather(
                    *(self._dispatch(call) for call in segment)
                )
            else:
                completed = [await self._dispatch(call) for call in segment]
            for result in completed:
                results[result.call_id] = result
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

    async def _dispatch(self, call: ToolCall) -> ToolResult:
        entry = self.lookup(call.name)
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
        if not self.availability(call.name):
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
        try:
            payload = await self._invoke(entry, arguments)
            ok, error, text = True, None, _normalize(payload)
        except Exception as exc:  # noqa: BLE001 - a tool failure is a result
            logger.warning("Tool %s failed: %s", call.name, exc)
            payload, ok, error = None, False, TOOL_FAILED
            text = f"{call.name} failed: {exc}"
        elapsed = int((time.perf_counter() - started) * 1000)

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
            ),
        )

    async def _invoke(
        self, entry: registry.ToolEntry, arguments: Mapping[str, Any]
    ) -> Any:
        if entry.is_async:
            outcome = entry.handler(self.context, arguments)
            if inspect.isawaitable(outcome):
                return await outcome
            return outcome
        # A declared-blocking handler is moved off the event loop, so one slow
        # database read cannot stall the other calls of the same round.
        return await asyncio.to_thread(entry.handler, self.context, arguments)

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
        """Write one trace entry. Every attempted call gets one, dispatched or not."""
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
    "HALTED_TURN",
    "INVALID_ARGUMENTS",
    "PARALLEL_SAFE_TOOLS",
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
