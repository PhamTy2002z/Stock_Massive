"""Rungs two and three of the defence against a Turn overflowing its context.

Rung one is already in place and is deliberately not here: every tool bounds its
own output before returning it, and :data:`catalog.MAX_TOOL_RESULT_BYTES` refuses
the ones that do not.  What a per-tool bound cannot see is the *round*.  Four
parallel calls, each honestly under 4 KB, are 16 KB of context that arrives at
once — and the overflow then lands on the following call, where it reads as the
model losing the thread rather than as the harness overspending.

So this module answers two questions, both as functions of bytes:

2. **One result is too big for the tool that produced it.**  Replace it with a
   preview that keeps the envelope, keeps the first few entries of whatever was
   large, and says — in :data:`SPILL_REF_KEY` — exactly what was left out and how
   much of it there was.
3. **A whole round is too big even though every result was fine.**  Spill the
   largest result first, and only as far as the round needs, until the round fits
   or nothing will give ground.

Three things about the preview are decisions rather than details.

**It is not the collapse in ``agent.context``.**  That one replaces an *old* tool
result with the line *called X with arguments Y*, which is right for a result the
model has already reasoned over and wrong for one it has not seen yet.  A
spilled result belongs to the round now finishing, so the preview has to carry
enough shape for the model to plan its next move — the counts, the first rows,
the keys those rows have.  The plan's own risk register names the failure this
avoids: a spill that leaves the model guessing produces a worse answer than the
overflow would have.

**The reference is descriptive, not a retrieval handle.**  Nothing in the Tool
Catalog fetches a spilled result back; the full result is kept in the record
(``agent_tool_call.result``) for audit, and the model's route to the truncated
part is a narrower call, not a fetch.  So the reference says what is missing and
how much, and never promises a way to ask for it.

**The key is not ``data_ref``.**  That name is taken: ``get_price_series``
returns a Data Reference under it and the Widget Validator resolves that
descriptor (``widgets.py``, ``resolve_data_ref``).  Writing a spill descriptor
into the same key would turn every widget bound to a spilled series into a
``wrong_binding`` rejection, so ``data_ref`` is in :data:`PRESERVED_KEYS`
instead — kept whole, never truncated — alongside ``registered_fields``, whose
truncation would cost the Turn a citation the Grounding Gate then refuses
(``grounding.py``, ``unknown_field_path``).

Pure throughout: no session, no clock, no Settings.  Every threshold arrives as
a parameter, including the round ceiling, which the loop owns because the loop
is what knows how much of the constructed-context budget one round may take.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .catalog import MAX_TOOL_RESULT_BYTES, serialized_size

#: Where a preview says what it left behind. Named for what it describes — a
#: result that spilled — and kept out of ``data_ref``'s way for the reason the
#: module docstring gives.
SPILL_REF_KEY = "spilled_ref"

#: Three quarters of what a single tool may return at all, and the number is
#: measured rather than chosen. Across sixty days of stored traces the largest
#: result any tool produced was 2,267 bytes and the mean was about 1,200, against
#: rung one's 4,096 — so a threshold at half the cap would have previewed
#: perfectly ordinary results whose bulk is the registered fields a preview must
#: preserve anyway, spending a spill record to save nothing. Sitting above every
#: measured result, this fires on the two cases that are not in that history:
#: a tool whose payload grew (twelve periods of statement figures is a shape W1
#: only just made possible), and an MCP tool, whose shape nothing here has ever
#: seen and which declares no budget of its own.
DEFAULT_SPILL_THRESHOLD_BYTES = MAX_TOOL_RESULT_BYTES * 3 // 4

#: What one round of tool results may add to the context, as a default the loop
#: is free to override. Four full-sized results, derived rather than chosen:
#: ``MAX_TOOL_ROUNDS`` (4) rounds of this ceiling is 64 KB, which at
#: ``context.CHARS_PER_TOKEN`` is roughly 21,000 of the 32,000 tokens
#: ``TURN_CONTEXT_PER_CALL`` allows one call — leaving about a third of the
#: window for the Contract, the user's Turns and the answer itself. Raising it
#: spends that third.
DEFAULT_ROUND_CEILING_BYTES = 4 * MAX_TOOL_RESULT_BYTES

#: Never truncated, whatever it costs. Three groups, and each is a failure the
#: preview would otherwise cause somewhere else: the refusal envelope every
#: caller branches on (``reason``, ``error``, ``available``,
#: ``unavailable_reason``), the two bindings other modules resolve out of a tool
#: result (``registered_fields`` for the Grounding Gate, ``data_ref`` for the
#: Widget Validator), and the identity a figure is cited by (``symbol``,
#: ``as_of``, ``tool_call_id``, ``tool``). ``window_health`` is here for the same
#: reason as ``as_of``: a figure whose window nobody can read is a figure the
#: Validator will not stamp.
PRESERVED_KEYS = frozenset(
    {
        "as_of",
        "available",
        "data_ref",
        "error",
        "reason",
        "registered_fields",
        "symbol",
        "tool",
        "tool_call_id",
        "unavailable",
        "unavailable_reason",
        "window_health",
    }
)

_LIST = "list"
_OBJECT = "object"
_TEXT = "text"

#: The ladder, one rung per pass: how many entries of a truncated container, and
#: how many characters of a long string, a preview keeps. It ends at nothing kept
#: so that the ladder has a floor — a preview of the envelope alone is small, and
#: a ladder without a floor is a loop.
_ITEM_RUNGS = (3, 1, 0)
_TEXT_RUNGS = (400, 120, 0)

#: How many of a truncated list's element keys the reference names. Enough for
#: the model to know what a row looks like once the rows themselves are gone,
#: bounded so the description cannot become the payload.
_MAX_ITEM_KEYS = 12

_COUNT_KEYS = {_LIST: "items", _OBJECT: "keys", _TEXT: "chars"}


@dataclass(frozen=True)
class SpilloverBudget:
    """The thresholds rungs two and three are measured against.

    Resolution order is the ``pinned > config > registry > default`` shape the
    plan borrows, spelled out for this module: **pinned** is the ``threshold``
    argument a caller hands :func:`spill_result` for one specific call,
    **config** and **registry** both arrive as ``per_tool`` — the caller builds
    it, and the caller that matters builds it from the Tool Catalog's own
    ``ToolSpec.result_budget_bytes`` declarations — and **default** is
    :attr:`default_bytes`.

    The registry rung is deliberately *not* a table in this module. A tool's
    budget is a property of the shape it returns, so it belongs beside the
    schema where a reviewer meets it, and a second table here would be a second
    place for the two to disagree. There is no Settings read either: a pure
    function that reaches for global configuration is only pure until somebody
    changes the environment.
    """

    default_bytes: int = DEFAULT_SPILL_THRESHOLD_BYTES
    per_tool: Mapping[str, int] = field(default_factory=dict)
    round_bytes: int = DEFAULT_ROUND_CEILING_BYTES

    def threshold_for(self, tool_name: str, *, pinned: int | None = None) -> int:
        """What one tool's result may weigh before rung two replaces it."""
        if pinned is not None:
            return max(0, int(pinned))
        return max(0, int(self.per_tool.get(tool_name, self.default_bytes)))

    def declared_for(self, tool_name: str) -> int | None:
        """What this tool *declared*, or ``None`` if it inherited the default.

        The two are different answers to different questions, which is why this
        is not :meth:`threshold_for`. A declaration is a statement that the
        payload is the answer, and rung three honours it as a floor. The default
        is the absence of such a statement, so rung three may reduce past it —
        otherwise every result would already sit at its own floor after rung two
        and the round-level rung could never give ground at all.
        """
        declared = self.per_tool.get(tool_name)
        return None if declared is None else max(0, int(declared))


@dataclass(frozen=True)
class SpilledResult:
    """One result reduced to a preview, and what that cost.

    ``full_bytes`` is the size of the *original* result even when the preview
    was built from an earlier preview — a caller logging a spill wants the size
    the round actually produced, not the size of the last thing it shrank.
    """

    preview: Mapping[str, Any]
    full_bytes: int
    preview_bytes: int
    #: The ladder ran out of rungs and the preview is still over the threshold.
    #: Not an error: it means the preserved envelope alone is bigger than the
    #: threshold allows, which is a fact about the threshold rather than about
    #: the result, and the caller keeps the smallest preview there is.
    at_floor: bool = False


@dataclass(frozen=True)
class RoundResult:
    """One completed call of a round, as rung three receives it."""

    call_id: str
    tool_name: str
    result: Mapping[str, Any]


@dataclass(frozen=True)
class SpillRecord:
    """One spill, in the shape a caller writes to the trace or the store."""

    call_id: str
    tool_name: str
    full_bytes: int
    preview_bytes: int


@dataclass(frozen=True)
class RoundSpillover:
    """What a round looks like after it has been made to fit.

    ``results`` holds every call the round was given, spilled or untouched, so a
    caller substitutes the whole mapping rather than deciding per call which
    version it holds — the mistake that puts a full result in the transcript and
    a preview in the trace.
    """

    results: Mapping[str, Mapping[str, Any]]
    spilled: tuple[SpillRecord, ...]
    total_bytes: int
    #: The round is still over its ceiling and nothing left will give ground.
    #: Reported rather than raised: a round that cannot be made to fit is still
    #: better handed over with what reduction was possible than dropped, and the
    #: caller is the layer that can decide to end the Turn over it.
    over_ceiling: bool = False


def _kind(value: Any) -> str | None:
    """What sort of thing this value is, or ``None`` if it cannot be reduced.

    A short string is not reducible: clipping it saves nothing and costs the
    model a fact it could have read whole.
    """
    if isinstance(value, Mapping):
        return _OBJECT
    if isinstance(value, str):
        return _TEXT if len(value) > _TEXT_RUNGS[0] else None
    if isinstance(value, (bytes, bytearray)):
        return None
    if isinstance(value, Sequence):
        return _LIST
    return None


def _count(value: Any, kind: str) -> int:
    if kind == _TEXT:
        return len(str(value))
    return len(value)


def _rung(kind: str, index: int) -> int:
    return _TEXT_RUNGS[index] if kind == _TEXT else _ITEM_RUNGS[index]


def _reduce(value: Any, kind: str, keep: int) -> Any:
    """This value, cut to ``keep``, in the same shape it arrived in."""
    if kind == _TEXT:
        text = str(value)[:keep]
        # The ellipsis is the point of this branch: a clipped sentence that
        # looks finished is one the model will quote as if it were.
        return f"{text}…" if keep else ""
    if kind == _LIST:
        return list(value)[:keep]
    return dict(list(value.items())[:keep])


def _item_keys(value: Any, kind: str) -> list[str] | None:
    """The keys one element of a list has, when its elements are objects."""
    if kind != _LIST:
        return None
    rows = list(value)
    if not rows or not isinstance(rows[0], Mapping):
        return None
    return sorted(str(key) for key in rows[0])[:_MAX_ITEM_KEYS]


def _prior(result: Mapping[str, Any]) -> tuple[int, dict[str, dict[str, Any]]]:
    """What an earlier spill of this same result already recorded.

    Rung three can be handed a preview rung two already built, and when it is,
    the counts in that preview's reference are the *original* counts. Rebuilding
    them from the preview would report 3 rows out of 3.
    """
    reference = result.get(SPILL_REF_KEY)
    if not isinstance(reference, Mapping):
        return 0, {}
    records: dict[str, dict[str, Any]] = {}
    for record in reference.get("truncated") or ():
        if isinstance(record, Mapping) and record.get("key"):
            records[str(record["key"])] = dict(record)
    full = reference.get("full_bytes")
    return (int(full) if isinstance(full, int) else 0), records


def _reference(
    *,
    call_id: str,
    tool_name: str,
    full_bytes: int,
    records: Mapping[str, Mapping[str, Any]],
    at_floor: bool,
) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "tool_call_id": call_id,
        "tool": tool_name,
        "full_bytes": full_bytes,
        "truncated": [dict(record) for record in records.values()],
    }
    if at_floor:
        reference["at_floor"] = True
    return reference


def spill_result(
    tool_name: str,
    call_id: str,
    result: Mapping[str, Any],
    *,
    threshold: int,
) -> SpilledResult | None:
    """Rung two: one result, previewed if it is over its own threshold.

    ``None`` means the result fits and must be passed through untouched — the
    common case, and the reason this returns an option rather than always
    handing back a copy: a caller that cannot tell a spill from a pass-through
    logs every result as spilled.

    Reduction is greedy and largest-first, one rung at a time, and stops at the
    first preview that fits. A result whose single big list was enough keeps the
    rest of itself whole, which is what makes the preview worth reading.
    """
    full_bytes = serialized_size(result)
    if full_bytes <= threshold:
        return None

    original_bytes, prior = _prior(result)
    original_bytes = original_bytes or full_bytes
    working = {key: value for key, value in result.items() if key != SPILL_REF_KEY}
    records: dict[str, dict[str, Any]] = {}

    reducible: list[tuple[str, str]] = []
    for key, value in working.items():
        if key in PRESERVED_KEYS:
            continue
        kind = _kind(value)
        if kind is not None:
            reducible.append((key, kind))
    reducible.sort(
        key=lambda pair: (-serialized_size({pair[0]: working[pair[0]]}), pair[0])
    )

    def candidate(*, at_floor: bool = False) -> dict[str, Any]:
        return {
            **working,
            SPILL_REF_KEY: _reference(
                call_id=call_id,
                tool_name=tool_name,
                full_bytes=original_bytes,
                records=records,
                at_floor=at_floor,
            ),
        }

    for rung in range(len(_ITEM_RUNGS)):
        for key, kind in reducible:
            preview = candidate()
            size = serialized_size(preview)
            if size <= threshold:
                return SpilledResult(preview, original_bytes, size)
            keep = _rung(kind, rung)
            before = working[key]
            reduced = _reduce(before, kind, keep)
            count_key = _COUNT_KEYS[kind]
            earlier = records.get(key) or prior.get(key) or {}
            record: dict[str, Any] = {
                "key": key,
                "kind": kind,
                count_key: int(earlier.get(count_key, _count(before, kind))),
                "kept": min(keep, _count(before, kind)),
            }
            item_keys = earlier.get("item_keys") or _item_keys(before, kind)
            if item_keys:
                record["item_keys"] = list(item_keys)
            records[key] = record
            working[key] = reduced

    preview = candidate()
    size = serialized_size(preview)
    if size <= threshold:
        return SpilledResult(preview, original_bytes, size)
    preview = candidate(at_floor=True)
    return SpilledResult(preview, original_bytes, serialized_size(preview), at_floor=True)


def spill_round(
    results: Sequence[RoundResult],
    *,
    budget: SpilloverBudget | None = None,
) -> RoundSpillover:
    """Rungs two and three over one round's results, in that order.

    Rung two runs here as well as at dispatch, and running it twice is safe: a
    preview is under the threshold that produced it, so a result already spilled
    is passed through untouched and reported once. Rung three then spills the
    largest remaining result first, asking it for exactly the bytes the round is
    over by, and repeats until the round fits or nothing gives ground. Largest
    first because the alternative — every result trimmed a little — pays the
    cost of a spill on results that were never the problem.

    **A tool's *declared* budget holds at this rung too**, and only a declared
    one: rung three asks for the bytes the round is over by, but never for fewer
    than the tool was declared to be worth. A declaration says *this payload is
    the answer*, and that is no less true because a sibling call was large.
    Without the floor the rung reached exactly the wrong results first — it sorts
    largest-first, and the tools that declare the full cap are the large ones — so
    a Turn that asked for eight quarters of statements would have been answered
    with three, and the Widget bound to those quarters pinned to three forever.
    A round that still does not fit is reported as ``over_ceiling`` rather than
    shrunk past what its results are for.

    The floor is the declaration and not :meth:`SpilloverBudget.threshold_for`,
    because after rung two every result already sits at or under its threshold —
    flooring at that would leave this rung nothing to give.
    """
    budget = budget or SpilloverBudget()
    current: dict[str, Mapping[str, Any]] = {}
    names: dict[str, str] = {}
    records: dict[str, SpillRecord] = {}

    for item in results:
        current[item.call_id] = item.result
        names[item.call_id] = item.tool_name
        spilled = spill_result(
            item.tool_name,
            item.call_id,
            item.result,
            threshold=budget.threshold_for(item.tool_name),
        )
        if spilled is not None:
            current[item.call_id] = spilled.preview
            records[item.call_id] = SpillRecord(
                call_id=item.call_id,
                tool_name=item.tool_name,
                full_bytes=spilled.full_bytes,
                preview_bytes=spilled.preview_bytes,
            )

    ceiling = max(0, int(budget.round_bytes))
    total = sum(serialized_size(result) for result in current.values())
    # One pass per call per rung is every reduction there is to make: past that
    # every result is at its floor, and a loop that kept going would be waiting
    # for a byte nothing can give.
    for _ in range(max(1, len(current)) * len(_ITEM_RUNGS)):
        if total <= ceiling:
            break
        overshoot = total - ceiling
        order = sorted(
            current,
            key=lambda call_id: (-serialized_size(current[call_id]), call_id),
        )
        progressed = False
        for call_id in order:
            size = serialized_size(current[call_id])
            spilled = spill_result(
                names[call_id],
                call_id,
                current[call_id],
                threshold=max(
                    size - overshoot, budget.declared_for(names[call_id]) or 0
                ),
            )
            if spilled is None or spilled.preview_bytes >= size:
                continue
            current[call_id] = spilled.preview
            records[call_id] = SpillRecord(
                call_id=call_id,
                tool_name=names[call_id],
                full_bytes=spilled.full_bytes,
                preview_bytes=spilled.preview_bytes,
            )
            total = total - size + spilled.preview_bytes
            progressed = True
            break
        if not progressed:
            break

    return RoundSpillover(
        results=MappingProxyType(dict(current)),
        spilled=tuple(records.values()),
        total_bytes=total,
        over_ceiling=total > ceiling,
    )


__all__ = [
    "DEFAULT_ROUND_CEILING_BYTES",
    "DEFAULT_SPILL_THRESHOLD_BYTES",
    "PRESERVED_KEYS",
    "SPILL_REF_KEY",
    "RoundResult",
    "RoundSpillover",
    "SpillRecord",
    "SpilledResult",
    "SpilloverBudget",
    "spill_result",
    "spill_round",
]
