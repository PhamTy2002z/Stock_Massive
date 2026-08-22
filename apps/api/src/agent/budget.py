"""Three rungs of defence against a Turn overflowing the model's context.

**Rung one — per tool.** A tool bounds its own output before returning it, and
declares that bound at registration (``ToolEntry.max_result_size_chars``). This
module does not enforce rung one; it *reads* the declaration, because the size a
tool's shape justifies is a property of the tool and belongs beside its schema.

**Rung two — per result.** A result over its limit is replaced by a preview: the
head of the text, cut at a line boundary so the model never reads half a row,
followed by a cursor saying exactly how much was hidden and where it starts.
Deliberately *not* an error. The harness this replaces raised on an oversized
result, which turned a large answer into no answer at all — a page that happened
to be long could fail a Turn. A preview keeps the Turn moving and tells the
model what it is missing.

**Rung three — per Turn.** Every result gathered so far, added up. Four results
each honestly under their own limit are four times that much context, and the
overflow lands on a later round where it reads as the model losing the thread
rather than as the harness overspending. So when the aggregate is over budget the
largest result gives ground first, and only as far as the Turn needs.

Both budgets scale with the model's context window rather than being constants:
a window is measured in tokens, characters are what we can count cheaply, and
:data:`CHARS_PER_TOKEN` is the conversion. Fifteen percent of the window for one
result and thirty for the whole Turn, each clamped — the floors keep a small
window usable, the ceilings stop a very large window from letting one tool spend
everything.

Pure: no session, no clock, no Settings. Every threshold arrives as an argument,
including the registry's own declarations, so a test can ask what the ladder does
at any window size.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

#: One token is about four characters of the mixed Vietnamese and English this
#: agent handles. Used only to turn a window in tokens into a budget in
#: characters, which is the unit both rungs measure.
CHARS_PER_TOKEN = 4

PER_RESULT_FRACTION = 0.15
PER_RESULT_MIN_CHARS = 8_000
PER_RESULT_MAX_CHARS = 100_000

PER_TURN_FRACTION = 0.30
PER_TURN_MIN_CHARS = 16_000
PER_TURN_MAX_CHARS = 200_000

#: Room kept inside a result's limit for the cursor sentence, so a preview plus
#: its explanation still fits the budget that produced it.
CURSOR_RESERVE_CHARS = 240

#: How far from the requested cut point a line boundary is still worth taking.
#: Beyond this the text is cut mid-line: a preview that hunted for a newline
#: across half the document would not be a preview of the head any more.
NEWLINE_SLACK_CHARS = 400

#: No result is reduced below this by rung three. A preview too small to carry a
#: shape is worse than no preview: the model cannot plan its next move from it,
#: and it still costs a round to discover that.
SPILL_FLOOR_CHARS = 512


def _clamp(value: float, low: int, high: int) -> int:
    return int(max(low, min(high, value)))


@dataclass(frozen=True)
class BudgetThresholds:
    """What one result and one whole Turn may weigh, in characters."""

    per_result_chars: int
    per_turn_chars: int

    @classmethod
    def for_context(cls, context_length: int) -> BudgetThresholds:
        """Scale both budgets to a model's context window, measured in tokens."""
        window_chars = max(0, int(context_length)) * CHARS_PER_TOKEN
        return cls(
            per_result_chars=_clamp(
                window_chars * PER_RESULT_FRACTION,
                PER_RESULT_MIN_CHARS,
                PER_RESULT_MAX_CHARS,
            ),
            per_turn_chars=_clamp(
                window_chars * PER_TURN_FRACTION,
                PER_TURN_MIN_CHARS,
                PER_TURN_MAX_CHARS,
            ),
        )


def thresholds_for_context(context_length: int) -> BudgetThresholds:
    """Module-level spelling of :meth:`BudgetThresholds.for_context`."""
    return BudgetThresholds.for_context(context_length)


@dataclass(frozen=True)
class ResultCursor:
    """Where a preview stopped and how much it left behind.

    Descriptive, not a retrieval handle: nothing in this harness fetches a
    hidden tail back, and a cursor that implied otherwise would send the model
    looking for a tool that does not exist. It says where the text was cut so a
    narrower call — or a tool that happens to take an offset — can pick it up.
    """

    offset: int
    hidden_chars: int
    total_chars: int

    def sentence(self) -> str:
        return (
            f"[truncated: {self.offset} of {self.total_chars} characters shown; "
            f"{self.hidden_chars} hidden from offset {self.offset}. Narrow the "
            "request, or continue from that offset if this tool accepts one.]"
        )


@dataclass(frozen=True)
class BudgetedResult:
    """One tool result as the message layer will see it."""

    call_id: str
    tool_name: str
    text: str
    original_chars: int
    cursor: ResultCursor | None = None

    @property
    def truncated(self) -> bool:
        return self.cursor is not None

    @property
    def chars(self) -> int:
        return len(self.text)


def resolve_limit(
    tool_name: str,
    *,
    default_chars: int,
    pinned: Mapping[str, int] | None = None,
    config: Mapping[str, int] | None = None,
    registry: Mapping[str, int] | None = None,
) -> int:
    """The limit for one tool's result: pinned > config > registry > default.

    Four rungs because each answers a different question. **Pinned** is one
    call's override, which a caller with more context than this module may set.
    **Config** is a deployment saying a tool needs more or less room than it
    declared. **Registry** is the tool's own declaration, made where a reviewer
    meets its schema. **Default** is the window-scaled budget above.
    """
    for source in (pinned, config, registry):
        if source is None:
            continue
        declared = source.get(tool_name)
        if declared is not None:
            return max(SPILL_FLOOR_CHARS, int(declared))
    return max(SPILL_FLOOR_CHARS, int(default_chars))


def trim_text(text: str, limit: int) -> tuple[str, ResultCursor | None]:
    """Cut ``text`` to ``limit`` characters at a line boundary, with a cursor.

    The cut point is the requested one moved to the nearest newline within
    :data:`NEWLINE_SLACK_CHARS`, preferring backwards so the preview stays inside
    its budget. Text with no newline anywhere near is cut where it was asked to
    be — a single very long line has no boundary to respect.
    """
    total = len(text)
    if total <= limit:
        return text, None
    preview_size = max(SPILL_FLOOR_CHARS // 2, limit - CURSOR_RESERVE_CHARS)
    cut = _line_boundary(text, preview_size)
    preview = text[:cut].rstrip()
    cursor = ResultCursor(offset=cut, hidden_chars=total - cut, total_chars=total)
    return f"{preview}\n{cursor.sentence()}", cursor


def _line_boundary(text: str, preview_size: int) -> int:
    backwards = text.rfind("\n", max(0, preview_size - NEWLINE_SLACK_CHARS), preview_size)
    if backwards > 0:
        return backwards
    forwards = text.find("\n", preview_size, preview_size + NEWLINE_SLACK_CHARS)
    if forwards > 0:
        return forwards
    return preview_size


class TurnBudget:
    """Rungs two and three over the results of one Turn.

    Stateful because rung three is a fact about the Turn, not about a round: the
    message list is rebuilt from stored results on every round, so a result
    gathered three rounds ago can still be asked to give ground now.
    """

    def __init__(
        self,
        thresholds: BudgetThresholds,
        *,
        per_tool_config: Mapping[str, int] | None = None,
        registry_limits: Mapping[str, int] | None = None,
    ) -> None:
        self._thresholds = thresholds
        self._config = dict(per_tool_config or {})
        self._registry = dict(registry_limits or {})
        self._originals: list[tuple[str, str, str]] = []
        self._results: dict[str, BudgetedResult] = {}

    @property
    def thresholds(self) -> BudgetThresholds:
        return self._thresholds

    @property
    def total_chars(self) -> int:
        return sum(result.chars for result in self._results.values())

    def limit_for(self, tool_name: str, *, pinned: int | None = None) -> int:
        pins = {tool_name: pinned} if pinned is not None else None
        return resolve_limit(
            tool_name,
            default_chars=self._thresholds.per_result_chars,
            pinned=pins,
            config=self._config,
            registry=self._registry,
        )

    def add(
        self, call_id: str, tool_name: str, text: str, *, pinned: int | None = None
    ) -> BudgetedResult:
        """Apply rung two to one result and remember it for rung three."""
        original = text if isinstance(text, str) else str(text)
        self._originals.append((call_id, tool_name, original))
        trimmed, cursor = trim_text(original, self.limit_for(tool_name, pinned=pinned))
        result = BudgetedResult(
            call_id=call_id,
            tool_name=tool_name,
            text=trimmed,
            original_chars=len(original),
            cursor=cursor,
        )
        self._results[call_id] = result
        return result

    def results(self) -> tuple[BudgetedResult, ...]:
        """Every result in the order it arrived, rung two applied."""
        return tuple(self._results[call_id] for call_id, _, _ in self._originals)

    def rebalance(self) -> tuple[BudgetedResult, ...]:
        """Apply rung three: shrink the largest results until the Turn fits.

        Halving rather than trimming to an exact share, because an exact share
        would reduce every large result to the same size — and one of the two is
        usually the answer while the other is background. Halving asks the
        biggest to give the most and stops as soon as the Turn is inside budget.
        """
        limits: dict[str, int] = {
            call_id: self.limit_for(tool_name)
            for call_id, tool_name, _ in self._originals
        }
        while self.total_chars > self._thresholds.per_turn_chars:
            candidate = self._largest_reducible(limits)
            if candidate is None:
                # Every result is at the floor. The remainder is a fact about
                # the budget rather than about any one result, and the caller
                # keeps the smallest set of previews there is.
                break
            call_id, tool_name, original = candidate
            limits[call_id] = max(SPILL_FLOOR_CHARS, len(self._results[call_id].text) // 2)
            trimmed, cursor = trim_text(original, limits[call_id])
            self._results[call_id] = BudgetedResult(
                call_id=call_id,
                tool_name=tool_name,
                text=trimmed,
                original_chars=len(original),
                cursor=cursor,
            )
        return self.results()

    def _largest_reducible(
        self, limits: Mapping[str, int]
    ) -> tuple[str, str, str] | None:
        reducible = [
            entry
            for entry in self._originals
            if self._results[entry[0]].chars > SPILL_FLOOR_CHARS
            and limits[entry[0]] > SPILL_FLOOR_CHARS
        ]
        if not reducible:
            return None
        return max(reducible, key=lambda entry: self._results[entry[0]].chars)


__all__ = [
    "CHARS_PER_TOKEN",
    "CURSOR_RESERVE_CHARS",
    "NEWLINE_SLACK_CHARS",
    "PER_RESULT_FRACTION",
    "PER_RESULT_MAX_CHARS",
    "PER_RESULT_MIN_CHARS",
    "PER_TURN_FRACTION",
    "PER_TURN_MAX_CHARS",
    "PER_TURN_MIN_CHARS",
    "SPILL_FLOOR_CHARS",
    "BudgetThresholds",
    "BudgetedResult",
    "ResultCursor",
    "TurnBudget",
    "resolve_limit",
    "thresholds_for_context",
    "trim_text",
]
