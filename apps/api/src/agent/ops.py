"""The one fixed ops query: what the field is doing, read into the Eval Report.

``docs/adr/0016`` settles the shape of production observability for a product
with **one developer and no on-call rotation**, and the settlement is a refusal:
*no new tables and no automatic alerting.* Alerts nobody is rostered to answer
are noise, and a metrics table is a second store to keep true. Every signal that
would justify one already exists on rows the product writes anyway:

- ``grounding_failed`` in the Turn lifecycle (``agent_turn.terminal_reason``);
- ``unknown_tool`` in ``agent_tool_call``, which is also ``docs/adr/0011``'s
  demand trigger for sandboxed execution;
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

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.alpha.models import (
    FLAG_REASONS,
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

#: The bucket for a Turn that released no assistant message and therefore has no
#: ``answer_kind`` at all — a deadline before the first block, a bare failure.
#: Its own key rather than an omission, because the distribution sits beside the
#: Turn count and a silently smaller total would be read as a smaller problem.
#: Safe as a name: the three :class:`AnswerKind` values are ``analysis``,
#: ``education`` and ``refusal``.
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
    #: ``terminal_reason`` counts for Turns that ended ``incomplete``, busiest
    #: first. ``grounding_failed`` appears here too, and that is not double
    #: counting — it is the same fact seen from the reason side.
    incomplete_reasons: Mapping[str, int]
    #: Every tool call attempted in the window, so the unknown ones have a scale.
    tool_calls: int
    #: ``unknown_tool`` calls by the name the model reached for. ``docs/adr/0011``
    #: asks *which* tool, not how many: the names are the evidence for whether
    #: sandboxed execution is ever worth revisiting.
    unknown_tool_calls: Mapping[str, int]
    #: One key per :class:`AnswerKind`, plus :data:`NO_ANSWER_KIND`, summing to
    #: :attr:`turns`. A value the store holds and this build does not know is
    #: kept under its own key rather than dropped — unlike a flag reason, this
    #: is a distribution, and a dropped bucket would break the sum.
    answer_kinds: Mapping[str, int]
    #: One key per reason in :data:`FLAG_REASONS`, present even at zero.
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
    def grounding_failed_rate(self) -> float:
        """The share of Turns the Gate blocked. Zero over an empty window."""
        return self.grounding_failed / self.turns if self.turns else 0.0

    @property
    def reopens_category_b(self) -> bool:
        """Strictly above the threshold, which is what "above 5%" says."""
        return self.grounding_failed_rate > GROUNDING_FAILED_RATE_THRESHOLD

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
            "incomplete_reasons": dict(self.incomplete_reasons),
            "tool_calls": self.tool_calls,
            "unknown_tool_calls": dict(self.unknown_tool_calls),
            "answer_kinds": dict(self.answer_kinds),
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
            grounding_failed=int(payload.get("grounding_failed", 0)),
            incomplete_reasons=dict(payload.get("incomplete_reasons") or {}),
            tool_calls=int(payload.get("tool_calls", 0)),
            unknown_tool_calls=dict(payload.get("unknown_tool_calls") or {}),
            answer_kinds=dict(payload.get("answer_kinds") or {}),
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
            grounding_failed=0,
            incomplete_reasons={},
            tool_calls=0,
            unknown_tool_calls={},
            answer_kinds={},
            flags=dict.fromkeys(FLAG_REASONS, 0),
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
    signals uses the same bounds: a query where "over 7 days" meant something
    slightly different per signal would produce a report whose lines cannot be
    compared with each other.
    """
    since = now - timedelta(days=window_days)
    return OpsSnapshot(
        since=since,
        until=now,
        window_days=window_days,
        turns=_turns(session, since, now),
        grounding_failed=_grounding_failed(session, since, now),
        incomplete_reasons=_incomplete_reasons(session, since, now),
        tool_calls=_tool_calls(session, since, now),
        unknown_tool_calls=_unknown_tool_calls(session, since, now),
        answer_kinds=_answer_kinds(session, since, now),
        flags=flag_counts_between(session, since=since, until=now),
    )


def _in_window(query, column, since: datetime, until: datetime):
    return query.where(column >= since, column < until)


def _turns(session: Session, since: datetime, until: datetime) -> int:
    return int(
        session.execute(
            _in_window(
                select(func.count(AgentTurn.id)), AgentTurn.started_at, since, until
            )
        ).scalar()
        or 0
    )


def _grounding_failed(session: Session, since: datetime, until: datetime) -> int:
    """Counted off ``terminal_reason`` rather than off the status.

    The reason is the stable half. ``grounding_failed`` is only ever written
    alongside ``incomplete`` (``src/agent/loop.py``), so restating the status
    here would add a condition that can only ever be redundant or wrong.
    """
    return int(
        session.execute(
            _in_window(
                select(func.count(AgentTurn.id)).where(
                    AgentTurn.terminal_reason == GROUNDING_FAILED
                ),
                AgentTurn.started_at,
                since,
                until,
            )
        ).scalar()
        or 0
    )


def _incomplete_reasons(
    session: Session, since: datetime, until: datetime
) -> dict[str, int]:
    """Why Turns ended short, busiest first.

    Only ``incomplete``. A ``cancelled`` Turn also carries a reason and it is
    not a failure — the reader pressed stop — so folding the two would put
    ``cancelled_by_user`` at the top of a list of things to fix.
    """
    rows = session.execute(
        _in_window(
            select(AgentTurn.terminal_reason, func.count()).where(
                AgentTurn.status == TURN_INCOMPLETE,
                AgentTurn.terminal_reason.is_not(None),
            ),
            AgentTurn.started_at,
            since,
            until,
        ).group_by(AgentTurn.terminal_reason)
    )
    return _busiest_first(rows)


def _tool_calls(session: Session, since: datetime, until: datetime) -> int:
    return int(
        session.execute(
            _in_window(
                select(func.count(AgentToolCall.id)),
                AgentToolCall.started_at,
                since,
                until,
            )
        ).scalar()
        or 0
    )


def _unknown_tool_calls(
    session: Session, since: datetime, until: datetime
) -> dict[str, int]:
    rows = session.execute(
        _in_window(
            select(AgentToolCall.tool_name, func.count()).where(
                AgentToolCall.status == TOOL_CALL_UNKNOWN_TOOL
            ),
            AgentToolCall.started_at,
            since,
            until,
        ).group_by(AgentToolCall.tool_name)
    )
    return _busiest_first(rows)


def _answer_kinds(
    session: Session, since: datetime, until: datetime
) -> dict[str, int]:
    """The distribution over **Turns**, not over messages.

    Over Turns because that is the population every other line of this report
    is denominated in, and because a Turn is the thing a reader asked for. It
    costs an outer join — ``response_message_id`` is nullable, and a Turn that
    released no block never got a message — and buys a distribution that sums
    to the Turn count printed above it.
    """
    kind = AgentMessage.content["answer_kind"].astext
    rows = session.execute(
        _in_window(
            select(kind, func.count()).select_from(AgentTurn).outerjoin(
                AgentMessage, AgentMessage.id == AgentTurn.response_message_id
            ),
            AgentTurn.started_at,
            since,
            until,
        ).group_by(kind)
    )
    counts = {value.value: 0 for value in AnswerKind}
    counts[NO_ANSWER_KIND] = 0
    for name, total in rows:
        key = NO_ANSWER_KIND if name is None else str(name)
        counts[key] = counts.get(key, 0) + int(total)
    return counts


def _busiest_first(rows) -> dict[str, int]:
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
