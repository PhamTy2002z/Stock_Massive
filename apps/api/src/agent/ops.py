"""The one fixed ops query: what the field is doing, read into the Eval Report.

``docs/adr/0016`` settles the shape of production observability for a product
with **one developer and no on-call rotation**, and the settlement is a refusal:
*no new tables and no automatic alerting.* Alerts nobody is rostered to answer
are noise, and a metrics table is a second store to keep true. Every signal that
would justify one already exists on rows the product writes anyway:

- how many Turns ran at all (``agent_turn``), the denominator for the rest;
- why the ones that did not finish stopped (``agent_turn.terminal_reason`` where
  the Turn ended ``incomplete``), which is where a route failure, an expired
  deadline and a halted tool loop all surface under their own names;
- ``unknown_tool`` in ``agent_tool_call``, showing expected but unavailable
  capabilities;
- flagged-message counts, the nullable pair on ``agent_message``.

So there is exactly **one** query, it is read-only, it returns a value, and
nothing pages. What makes it more than a dashboard nobody opens is where its
output goes: **into the next Eval Report**, written there by the harness rather
than pasted in by hand. The battery measures a frozen fixture and the field
measures live traffic, and a number from each in one document is the only place
the two get reconciled.

There is no threshold on any of these numbers, and that is a change of substance
rather than of wording. The rule this query used to carry — a sustained
``grounding_failed`` rate reopening a category — was a rule about the
Recommendation Gate, and ``docs/adr/0026`` removed the Gate. A threshold kept
over a mechanism that no longer exists would be read as a live rule by the next
person who opened the report.

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
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from src.alpha.models import (
    TOOL_CALL_UNKNOWN_TOOL,
    TURN_INCOMPLETE,
    AgentToolCall,
    AgentTurn,
)

from .persistence import flag_counts_between

#: The window ``docs/adr/0016`` states its numbers over. Configurable per run,
#: because a wider window is a useful reading — there is no rule attached to any
#: particular span.
OPS_WINDOW_DAYS = 7


@dataclass(frozen=True)
class OpsSnapshot:
    """The field signals over one window, and nothing derived stored.

    Rates are properties rather than fields for the reason ``eval_run`` stores
    counts and not percentages: a stored rate is a number two later readers
    disagree about the denominator of.
    """

    since: datetime
    until: datetime
    window_days: int
    #: Every ``agent_turn`` row started inside the window. The denominator.
    turns: int
    #: ``terminal_reason`` counts for Turns that ended ``incomplete``, busiest
    #: first. Every way a Turn can stop short — a route error, an expired
    #: deadline, a tool that never answered — arrives here under its own name.
    incomplete_reasons: Mapping[str, int]
    #: Every tool call attempted in the window, so the unknown ones have a scale.
    tool_calls: int
    #: ``unknown_tool`` calls by the name the model reached for, so capability
    #: gaps stay visible: the model asking repeatedly for something that is not
    #: registered is the one signal that names a tool nobody has written.
    unknown_tool_calls: Mapping[str, int]
    #: One key per reason in ``FLAG_REASONS``, present even at zero — except on
    #: an unread store, where the mapping is empty rather than zeroed.
    flags: Mapping[str, int]
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
    def incomplete_total(self) -> int:
        return sum(self.incomplete_reasons.values())

    @property
    def incomplete_rate(self) -> float:
        """The share of Turns that stopped short. Zero over an empty window."""
        return self.incomplete_total / self.turns if self.turns else 0.0

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
            "incomplete_reasons": dict(self.incomplete_reasons),
            "tool_calls": self.tool_calls,
            "unknown_tool_calls": dict(self.unknown_tool_calls),
            "flags": dict(self.flags),
            "error": self.error,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> OpsSnapshot:
        return cls(
            since=datetime.fromisoformat(payload["since"]),
            until=datetime.fromisoformat(payload["until"]),
            window_days=int(payload["window_days"]),
            turns=int(payload.get("turns", 0)),
            incomplete_reasons=dict(payload.get("incomplete_reasons") or {}),
            tool_calls=int(payload.get("tool_calls", 0)),
            unknown_tool_calls=dict(payload.get("unknown_tool_calls") or {}),
            flags=dict(payload.get("flags") or {}),
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
            incomplete_reasons={},
            tool_calls=0,
            unknown_tool_calls={},
            # Empty, not seeded with zeros. A zero here would say *nothing was
            # flagged*, which is the one thing an unread store cannot say.
            flags={},
            error=reason,
        )


def read_ops_snapshot(
    session: Session,
    *,
    now: datetime,
    window_days: int = OPS_WINDOW_DAYS,
) -> OpsSnapshot:
    """The field signals over ``[now - window_days, now)``. Reads only.

    The session is the caller's — it opened it and it closes it, as everywhere
    else in this repository's read paths.

    The window is **half-open** so two consecutive readings partition time
    rather than overlap at their shared instant, and every signal is counted
    over the same span: a query where "over 7 days" meant something slightly
    different per signal would produce a report whose lines cannot be read
    against each other.

    One decision is visible in the queries below rather than stated anywhere
    else: incomplete reasons exclude ``cancelled`` Turns, which carry a reason
    too and are not failures. The reader pressed stop, and folding the two would
    put ``cancelled_by_user`` at the top of a list of things to fix.
    """
    window = _Window(now=now, window_days=window_days)
    return OpsSnapshot(
        since=window.since,
        until=window.until,
        window_days=window.window_days,
        turns=window.count(session, AgentTurn.started_at),
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
        # Bounded on ``flagged_at``: a flag is written long after the message it
        # is about, so placing it by the message's own timestamp would report it
        # in the week the answer was given rather than the week somebody
        # objected to it.
        flags=flag_counts_between(session, since=window.since, until=window.until),
    )


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


def _busiest_first(rows: Iterable[tuple[Any, Any]]) -> dict[str, int]:
    """Ordered by count and then by name, so two readings sort the same way."""
    counted = {str(name): int(total) for name, total in rows}
    return dict(sorted(counted.items(), key=lambda item: (-item[1], item[0])))


__all__ = [
    "OPS_WINDOW_DAYS",
    "OpsSnapshot",
    "read_ops_snapshot",
]
