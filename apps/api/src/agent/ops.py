"""The one fixed ops query: what the field is doing, read into the Eval Report.

``docs/adr/0016`` settles the shape of production observability for a product
with **one developer and no on-call rotation**, and the settlement is a refusal:
*no new tables and no automatic alerting.* Alerts nobody is rostered to answer
are noise, and a metrics table is a second store to keep true. Every signal that
would justify one already exists on rows the product writes anyway:

- ``grounding_failed`` in the Turn lifecycle (``agent_turn.terminal_reason``);
- ``unknown_tool`` in ``agent_tool_call``, showing expected but unavailable
  capabilities;
- downgrade labels inside released assistant-message blocks;
- the ``answer_kind`` distribution, inside the assistant message's content;
- incomplete reasons (``agent_turn.terminal_reason`` where the Turn ended
  ``incomplete``);
- flagged-message counts, the nullable pair on ``agent_message``.

So there is exactly **one** query, it is read-only, it returns a value, and
nothing pages. What makes it more than a dashboard nobody opens is where its
output goes: **into the next Eval Report**, written there by the harness rather
than pasted in by hand. The battery measures a frozen fixture and the field
measures live traffic, and a number from each in one document is the only place
the two get reconciled.

## The one threshold, and what it means

**``grounding_failed`` above 5% of Turns over 7 days reopens category B.**

It is read by eye, on the report, by the person who ran the battery. It is not
an alert and it is not a gate.

The reasoning is worth stating because the number looks like it should mean the
opposite. The Recommendation Gate blocks any figure it cannot attribute to a
tool reference, and a blocked figure ends the Turn ``incomplete/grounding_failed``
rather than being displayed (``src/agent/grounding.py``). So a *rising*
``grounding_failed`` rate is ambiguous on its face — it could be the model
fabricating more, or the Gate blocking more of what the model got right. The
sustained-rate pattern resolves it: fabrication is bursty and correlates with a
prompt or model change, while a persistent one-in-twenty says the Gate is
refusing ordinary correct answers. That is **over-blocking**, and over-blocking
is precisely what category B — false refusal — measures. Hence: reopen B, add
cases from the flagged messages, and re-run. Nothing else changes.

Two boundaries are deliberate. The comparison is **strictly above** 5%: a rule
that fired at exactly the boundary would reopen a category on an ordinary week.
And an **empty window is not a breach** — zero Turns is zero percent, not a
division by zero and not an alarm about a service nobody used.

## Two things this module does not do

**It adds no index.** ``agent_turn`` carries only ``(thread_id, started_at)``,
so a service-wide seven-day scan is a sequential one. That is the right trade
for a query run twice a month against a store one developer's users write: an
index is a cost on every Turn ever written, paid forever, to speed up a report.
Revisit it when the scan is slow enough to notice, which is a fact about row
counts rather than a prediction.

**It reads the application store and never writes to it.** The battery runs
entirely inside ``EVAL_DATABASE_URL``; this query is the one part of a run that
looks at the database the API serves from, and it looks with ``SELECT`` only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import InstrumentedAttribute, Session

from src.alpha.models import (
    TOOL_CALL_UNKNOWN_TOOL,
    TURN_INCOMPLETE,
    AgentMessage,
    AgentToolCall,
    AgentTurn,
)

from .grounding import GROUNDING_FAILED
from .persistence import flag_counts_between
from .prompt import AnswerKind

#: The window ``docs/adr/0016`` states the threshold over. Configurable per run
#: — the threshold is not, because *5% over 7 days* is one sentence and a rate
#: measured over a different span is not the quantity the rule is about.
OPS_WINDOW_DAYS = 7

#: Above this share of Turns, category B is reopened. See the module docstring
#: for why an over-blocking Gate is what a sustained rate means.
GROUNDING_FAILED_RATE_THRESHOLD = 0.05

#: The bucket for a Turn carrying no ``answer_kind`` at all — usually one that
#: released no assistant message, after a deadline before the first block or a
#: bare failure. Its own key rather than an omission, because the distribution
#: sits beside the Turn count and a silently smaller total would be read as a
#: smaller problem. Safe as a name: the three :class:`AnswerKind` values are
#: ``analysis``, ``education`` and ``refusal``.
NO_ANSWER_KIND = "none"


@dataclass(frozen=True)
class OpsSnapshot:
    """The five field signals over one window, and nothing derived stored.

    Rates are properties rather than fields for the reason ``eval_run`` stores
    counts and not percentages: a stored rate is a number two later readers
    disagree about the denominator of.
    """

    since: datetime
    until: datetime
    window_days: int
    #: Every ``agent_turn`` row started inside the window. The denominator.
    turns: int
    grounding_failed: int
    #: Released content blocks, the denominator for downgrade telemetry.
    blocks: int
    #: Prose blocks carrying at least one unverified figure.
    downgraded_blocks: int
    #: ``terminal_reason`` counts for Turns that ended ``incomplete``, busiest
    #: first. ``grounding_failed`` appears here too, and that is not double
    #: counting — it is the same fact seen from the reason side.
    incomplete_reasons: Mapping[str, int]
    #: Every tool call attempted in the window, so the unknown ones have a scale.
    tool_calls: int
    #: ``unknown_tool`` calls by the name the model reached for, so capability
    #: gaps remain visible after the executor decision in ADR-0019.
    unknown_tool_calls: Mapping[str, int]
    #: One key per :class:`AnswerKind`, plus :data:`NO_ANSWER_KIND`, summing to
    #: :attr:`turns`. A value the store holds and this build does not know is
    #: kept under its own key rather than dropped — unlike a flag reason, this
    #: is a distribution, and a dropped bucket would break the sum.
    answer_kinds: Mapping[str, int]
    #: One key per reason in ``FLAG_REASONS``, present even at zero — except on
    #: an unread store, where the mapping is empty rather than zeroed.
    flags: Mapping[str, int]
    #: Prompt-injection pattern labels found in untrusted tool results, by label
    #: and busiest first. Only labels that actually fired appear: the scan
    #: (``agent/tools/threat_patterns.py``) fails open and attaches nothing when
    #: it recognises nothing, so a zeroed key would be a claim about pages this
    #: query never saw. Read as a *rate against* ``tool_calls`` above it — the
    #: scan accepts false positives because it never blocks, and a label firing
    #: on a large share of ordinary retrievals is the signal to tighten the
    #: pattern rather than to worry about the field.
    #:
    #: Defaulted so a report assembled by an older build still loads; every
    #: other field here is required because every other field predates this one.
    injection_labels: Mapping[str, int] = field(default_factory=dict)
    #: Why there are no numbers, where there are none. The battery must not fail
    #: because the application store was unreachable — a gate run measures the
    #: fixture, and this reading is a reconciliation beside it. But a report
    #: showing zeros for an unread store would be a lie in the other direction,
    #: so the reason is carried and rendered in place of the numbers.
    error: str | None = None

    @property
    def readable(self) -> bool:
        return self.error is None

    @property
    def grounding_failed_rate(self) -> float:
        """The share of Turns the Gate blocked. Zero over an empty window."""
        return self.grounding_failed / self.turns if self.turns else 0.0

    @property
    def downgraded_block_rate(self) -> float:
        """The share of released blocks shown with an unverified-figure label."""
        return self.downgraded_blocks / self.blocks if self.blocks else 0.0

    @property
    def threshold_applies(self) -> bool:
        """Whether the rule can be read against this window at all.

        *5% of Turns over 7 days* is one sentence, and the span is half of it.
        A month's traffic smooths the burst that distinguishes fabrication from
        over-blocking, and a single day is noise — so a widened window is a
        useful reading and **not** the quantity the rule decides on. Stated as a
        property rather than left to the caller, because the caller that
        forgot would print a verdict this module calls meaningless.
        """
        return self.window_days == OPS_WINDOW_DAYS

    @property
    def reopens_category_b(self) -> bool:
        """Strictly above the threshold, which is what "above 5%" says."""
        return (
            self.threshold_applies
            and self.grounding_failed_rate > GROUNDING_FAILED_RATE_THRESHOLD
        )

    @property
    def incomplete_total(self) -> int:
        return sum(self.incomplete_reasons.values())

    @property
    def unknown_tool_total(self) -> int:
        return sum(self.unknown_tool_calls.values())

    @property
    def flags_total(self) -> int:
        return sum(self.flags.values())

    def as_wire(self) -> dict[str, Any]:
        return {
            "since": self.since.isoformat(),
            "until": self.until.isoformat(),
            "window_days": self.window_days,
            "turns": self.turns,
            "grounding_failed": self.grounding_failed,
            "blocks": self.blocks,
            "downgraded_blocks": self.downgraded_blocks,
            "incomplete_reasons": dict(self.incomplete_reasons),
            "tool_calls": self.tool_calls,
            "unknown_tool_calls": dict(self.unknown_tool_calls),
            "answer_kinds": dict(self.answer_kinds),
            "flags": dict(self.flags),
            "injection_labels": dict(self.injection_labels),
            "error": self.error,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> OpsSnapshot:
        return cls(
            since=datetime.fromisoformat(payload["since"]),
            until=datetime.fromisoformat(payload["until"]),
            window_days=int(payload["window_days"]),
            turns=int(payload.get("turns", 0)),
            grounding_failed=int(payload.get("grounding_failed", 0)),
            blocks=int(payload.get("blocks", 0)),
            downgraded_blocks=int(payload.get("downgraded_blocks", 0)),
            incomplete_reasons=dict(payload.get("incomplete_reasons") or {}),
            tool_calls=int(payload.get("tool_calls", 0)),
            unknown_tool_calls=dict(payload.get("unknown_tool_calls") or {}),
            answer_kinds=dict(payload.get("answer_kinds") or {}),
            flags=dict(payload.get("flags") or {}),
            injection_labels=dict(payload.get("injection_labels") or {}),
            error=payload.get("error"),
        )

    @classmethod
    def unreadable(
        cls, reason: str, *, now: datetime, window_days: int = OPS_WINDOW_DAYS
    ) -> OpsSnapshot:
        """A window with no numbers in it, and the reason there are none."""
        return cls(
            since=now - timedelta(days=window_days),
            until=now,
            window_days=window_days,
            turns=0,
            grounding_failed=0,
            blocks=0,
            downgraded_blocks=0,
            incomplete_reasons={},
            tool_calls=0,
            unknown_tool_calls={},
            answer_kinds={},
            # Empty, not seeded with zeros. A zero here would say *nothing was
            # flagged*, which is the one thing an unread store cannot say.
            flags={},
            injection_labels={},
            error=reason,
        )


def read_ops_snapshot(
    session: Session,
    *,
    now: datetime,
    window_days: int = OPS_WINDOW_DAYS,
) -> OpsSnapshot:
    """The five signals over ``[now - window_days, now)``. Reads only.

    The session is the caller's — it opened it and it closes it, as everywhere
    else in this repository's read paths.

    The window is **half-open** so two consecutive readings partition time
    rather than overlap at their shared instant, and every one of the five
    signals is counted over the same span: a query where "over 7 days" meant
    something slightly different per signal would produce a report whose lines
    cannot be read against each other.

    Two decisions are visible in the queries below rather than stated anywhere
    else. ``grounding_failed`` is counted off ``terminal_reason`` and not off
    the status — the reason is only ever written alongside ``incomplete``
    (``src/agent/loop.py``), so restating the status would add a condition that
    can only be redundant or wrong. And incomplete reasons exclude ``cancelled``
    Turns, which carry a reason too and are not failures: the reader pressed
    stop, and folding the two would put ``cancelled_by_user`` at the top of a
    list of things to fix.
    """
    window = _Window(now=now, window_days=window_days)
    blocks, downgraded_blocks = _block_counts(session, window)
    return OpsSnapshot(
        since=window.since,
        until=window.until,
        window_days=window.window_days,
        turns=window.count(session, AgentTurn.started_at),
        grounding_failed=window.count(
            session,
            AgentTurn.started_at,
            AgentTurn.terminal_reason == GROUNDING_FAILED,
        ),
        blocks=blocks,
        downgraded_blocks=downgraded_blocks,
        incomplete_reasons=window.tally(
            session,
            AgentTurn.terminal_reason,
            AgentTurn.started_at,
            AgentTurn.status == TURN_INCOMPLETE,
            AgentTurn.terminal_reason.is_not(None),
        ),
        tool_calls=window.count(session, AgentToolCall.started_at),
        unknown_tool_calls=window.tally(
            session,
            AgentToolCall.tool_name,
            AgentToolCall.started_at,
            AgentToolCall.status == TOOL_CALL_UNKNOWN_TOOL,
        ),
        answer_kinds=_answer_kinds(session, window),
        # Bounded on ``flagged_at``: a flag is written long after the message it
        # is about, so placing it by the message's own timestamp would report it
        # in the week the answer was given rather than the week somebody
        # objected to it.
        flags=flag_counts_between(session, since=window.since, until=window.until),
        injection_labels=_injection_labels(session, window),
    )


def _block_counts(session: Session, window: _Window) -> tuple[int, int]:
    """Count released blocks and the subset carrying downgrade labels.

    Blocks live inside the canonical assistant-message JSON rather than in a
    second metrics table. PostgreSQL expands only messages belonging to Turns
    in the same half-open ops window; a message with no blocks contributes
    nothing, and a block without the additive key is an ordinary block.
    """
    row = session.execute(
        text(
            """
            SELECT
              count(*) AS blocks,
              count(*) FILTER (
                WHERE jsonb_array_length(
                  coalesce(block.value -> 'unverified_figures', '[]'::jsonb)
                ) > 0
              ) AS downgraded_blocks
            FROM agent_turn AS turn_row
            JOIN agent_message AS message
              ON message.id = turn_row.response_message_id
            CROSS JOIN LATERAL jsonb_array_elements(
              coalesce(message.content -> 'blocks', '[]'::jsonb)
            ) AS block(value)
            WHERE turn_row.started_at >= :since
              AND turn_row.started_at < :until
            """
        ),
        {"since": window.since, "until": window.until},
    ).one()
    return int(row.blocks or 0), int(row.downgraded_blocks or 0)


def _injection_labels(session: Session, window: _Window) -> dict[str, int]:
    """Count prompt-injection labels out of the stored tool results themselves.

    ``docs/adr/0016`` refuses a new table, and none is needed: the scan writes
    its labels into the tool result, and the whole result is already stored
    (``agent_tool_call.result``, capped at 4KB by the catalog). So the count is
    a read over rows the product writes anyway, exactly like every other signal
    in this snapshot.

    The path is the recursive ``$.**`` rather than the three concrete paths the
    tools write today — ``results[*]``, ``external_claim`` and
    ``items[*].untrusted_evidence``. A list of paths here would be a second
    place to remember when a fourth untrusted envelope is added, and the one
    guaranteed outcome of forgetting it is a signal that silently reads zero.

    ``strict`` with ``silent``, and both halves are load-bearing. Lax mode
    unwraps an array before applying a member accessor, so ``$.**`` visiting the
    ``results`` array *and* each of its elements would count every label under
    an array twice while counting labels under a plain object once — a
    distribution skewed by the shape of the envelope rather than by the field.
    Strict mode refuses the unwrapping and ``silent`` turns the resulting type
    mismatches back into "no match", which is what a tool result carrying no
    labels — that is, nearly all of them — has to mean here.

    One row per occurrence, so a page carrying two labels counts once under
    each — the question this answers is *how often is each pattern firing*, and
    a per-call distinct would answer a different one.
    """
    rows = session.execute(
        text(
            """
            SELECT label.value #>> '{}' AS label, count(*) AS hits
            FROM agent_tool_call AS call_row
            CROSS JOIN LATERAL jsonb_path_query(
              coalesce(call_row.result, '{}'::jsonb),
              'strict $.**.injection_labels[*]',
              '{}'::jsonb,
              true
            ) AS label(value)
            WHERE call_row.started_at >= :since
              AND call_row.started_at < :until
            GROUP BY 1
            """
        ),
        {"since": window.since, "until": window.until},
    )
    return _busiest_first(rows)


class _Window:
    """The half-open span every signal is counted over, and how to ask for it.

    A type rather than three arguments threaded through six helpers. The span is
    one idea — ``[since, until)`` and the number of days that made it — and the
    whole value of this query is that every signal is counted over the same one,
    which is easier to be sure of when there is one object to be sure about.

    The *column* it bounds differs by signal, and that is not an inconsistency:
    a Turn is placed in time by ``started_at`` and a flag by ``flagged_at``,
    because a flag is written long after the message it is about.
    """

    __slots__ = ("since", "until", "window_days")

    def __init__(self, *, now: datetime, window_days: int) -> None:
        self.window_days = window_days
        self.since = now - timedelta(days=window_days)
        self.until = now

    def bound(self, query: Select, column: InstrumentedAttribute) -> Select:
        return query.where(column >= self.since, column < self.until)

    def count(
        self, session: Session, column: InstrumentedAttribute, *criteria: Any
    ) -> int:
        """How many rows of one table fall in the window, under ``criteria``.

        The table comes from the column, so a caller cannot bound one table's
        window while counting another's rows.
        """
        query = select(func.count()).select_from(column.class_)
        if criteria:
            query = query.where(*criteria)
        return int(session.execute(self.bound(query, column)).scalar() or 0)

    def tally(
        self,
        session: Session,
        grouped: InstrumentedAttribute,
        column: InstrumentedAttribute,
        *criteria: Any,
    ) -> dict[str, int]:
        """One column's values and their counts in the window, busiest first."""
        query = select(grouped, func.count()).where(*criteria)
        rows = session.execute(self.bound(query, column).group_by(grouped))
        return _busiest_first(rows)


def _answer_kinds(session: Session, window: _Window) -> dict[str, int]:
    """The distribution over **Turns**, not over messages.

    Over Turns because that is the population every other line of this report is
    denominated in, and because a Turn is the thing a reader asked for. It costs
    an outer join — ``response_message_id`` is nullable, and a Turn that released
    no block never got a message — and buys a distribution that sums to the Turn
    count printed above it.

    Its own function rather than a :meth:`_Window.tally` call: the join is what
    makes it different, and a ``tally`` taking an optional join would be
    carrying a parameter for one caller.

    ``NO_ANSWER_KIND`` also collects an assistant message whose content somehow
    lacks the key. Both are Turns with no ``answer_kind`` on them, which is
    exactly what the bucket is named for.
    """
    kind = AgentMessage.content["answer_kind"].astext
    query = (
        select(kind, func.count())
        .select_from(AgentTurn)
        .outerjoin(AgentMessage, AgentMessage.id == AgentTurn.response_message_id)
    )
    rows = session.execute(
        window.bound(query, AgentTurn.started_at).group_by(kind)
    )
    counts = {value.value: 0 for value in AnswerKind}
    counts[NO_ANSWER_KIND] = 0
    for name, total in rows:
        key = NO_ANSWER_KIND if name is None else str(name)
        counts[key] = counts.get(key, 0) + int(total)
    return counts


def _busiest_first(rows: Iterable[tuple[Any, Any]]) -> dict[str, int]:
    """Ordered by count and then by name, so two readings sort the same way."""
    counted = {str(name): int(total) for name, total in rows}
    return dict(sorted(counted.items(), key=lambda item: (-item[1], item[0])))


__all__ = [
    "GROUNDING_FAILED_RATE_THRESHOLD",
    "NO_ANSWER_KIND",
    "OPS_WINDOW_DAYS",
    "OpsSnapshot",
    "read_ops_snapshot",
]
