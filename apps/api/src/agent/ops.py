"""The one fixed ops query: what the field is doing, read on demand.

Production observability for a product with **one developer and no on-call
rotation** is settled here by a refusal: *no new tables and no automatic
alerting.* Alerts nobody is rostered to answer
are noise, and a metrics table is a second store to keep true. Every signal that
would justify one already exists on rows the product writes anyway:

- how many Turns ran at all (``agent_turn``), the denominator for the rest;
- why the ones that did not finish stopped (``agent_turn.terminal_reason`` where
  the Turn ended ``incomplete``), which is where a route failure, an expired
  deadline and a halted tool loop all surface under their own names;
- ``unknown_tool`` in ``agent_tool_call``, showing expected but unavailable
  capabilities;
- flagged-message counts, the nullable pair on ``agent_message``.

So the queries here are read-only, they return values, and nothing pages. They
are read when somebody asks what the field is doing, which is the only occasion
on which any of these numbers means anything.

There are two readings and they answer different questions. The first is the
field snapshot above. The second counts how often a Turn that quoted a price had
checked it (:func:`read_price_check_compliance`), which exists because the rule
it measures lives in the system prompt and a prompt is not an enforcement — the
number is there so the decision about building a backstop is made on a measured
rate rather than on a guess about one.

There is no threshold on any of these numbers, and that is a change of substance
rather than of wording. The rule this query used to carry — a sustained
``grounding_failed`` rate reopening a category — was a rule about the
Recommendation Gate, and the Gate is gone. A threshold kept over a mechanism
that no longer exists would be read as a live rule by the next person who read
these numbers.

## Two things this module does not do

**It adds no index.** ``agent_turn`` carries only ``(thread_id, started_at)``,
so a service-wide seven-day scan is a sequential one. That is the right trade
for a query run twice a month against a store one developer's users write: an
index is a cost on every Turn ever written, paid forever, to speed up a reading.
Revisit it when the scan is slow enough to notice, which is a fact about row
counts rather than a prediction.

**It reads the application store and never writes to it.** It looks at the
database the API serves from, and it looks with ``SELECT`` only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from src.alpha.models import (
    TOOL_CALL_UNKNOWN_TOOL,
    TURN_INCOMPLETE,
    AgentMessage,
    AgentToolCall,
    AgentTurn,
)

from . import registry
from .persistence import flag_counts_between

#: The tool the contract asks for before a price read elsewhere is stated. Named
#: here because this module counts calls to it and nothing else about it.
PRICE_CHECK_TOOL = "check_price_claim"

#: The window the numbers are stated over. Configurable per call, because a
#: wider window is a useful reading — there is no rule attached to any
#: particular span.
OPS_WINDOW_DAYS = 7


@dataclass(frozen=True)
class OpsSnapshot:
    """The field signals over one window, and nothing derived stored.

    Rates are properties rather than fields for the reason counts are stored
    and percentages are not: a stored rate is a number two later readers
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


def _external_tool_names() -> frozenset[str]:
    """Tools whose results are somebody else's writing.

    Asked of the registry rather than named here, so a web-reading tool added
    later counts without this module being edited — the same reason
    ``untrusted.py`` stopped keeping a list.
    """
    return frozenset(
        entry.name for entry in registry.entries() if entry.reads_external
    )


#: A number written the way a Vietnamese price is written: groups of three
#: digits separated by dots. Deliberately loose, because the alternative is
#: parsing prose.
_GROUPED_NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+")

#: What immediately after a number means it was not a price. A revenue in
#: billions and a percentage both arrive in the same shape as a price and are
#: not one, and the real Turn this reading exists for quoted all three.
_NOT_A_PRICE_AFTER = re.compile(r"^\s*(?:%|tỷ|ty|triệu|trieu|nghìn|nghin|tr\b|bn\b)")

#: The range a share price in VND falls in. Outside it the grouped number was a
#: volume, a market capitalisation or an index level.
_MIN_PRICE = 1_000
_MAX_PRICE = 5_000_000


def names_a_price(text: str) -> bool:
    """Whether this answer states something shaped like a share price in VND.

    A heuristic, and it is used for exactly one thing: counting how often the
    model checked a price it quoted. It is **not** wired into the message layer
    and nothing is flagged, blocked or rewritten on the strength of it — a free
    text scan that gated answers would flag revenues and percentages too, and
    the noise would cost the reader's trust in the mechanism. Measure first; the
    plan behind this says build the backstop only if the measurement says the
    contract is being ignored.
    """
    for match in _GROUPED_NUMBER.finditer(text or ""):
        if _NOT_A_PRICE_AFTER.match(text[match.end() : match.end() + 12]):
            continue
        try:
            value = int(match.group(0).replace(".", ""))
        except ValueError:  # pragma: no cover - the pattern is all digits and dots
            continue
        if _MIN_PRICE <= value <= _MAX_PRICE:
            return True
    return False


@dataclass(frozen=True)
class PriceCheckCompliance:
    """How often a quoted price was checked before it was stated.

    The contract asks the model to call ``check_price_claim`` before it states a
    price it read somewhere else. A contract is not an enforcement, so this
    counts rather than assuming — the whole reason the tool landed without a
    text-scanning backstop in the message layer.

    ``eligible`` is the denominator and it is narrow on purpose: a Turn counts
    only when it both read outside content and stated something shaped like a
    price. A Turn that answered from the store, or that quoted no number, is not
    a Turn that owed a check.
    """

    since: datetime
    until: datetime
    window_days: int
    #: Every Turn that finished with an answer in the window.
    turns_with_answers: int
    #: Turns that read outside content *and* stated a price-shaped number.
    eligible: int
    #: Of those, the ones that called ``check_price_claim`` at least once.
    checked: int

    @property
    def rate(self) -> float | None:
        """The share of eligible Turns that checked, or None with none to judge.

        ``None`` rather than zero, because zero out of zero is a compliance
        failure that never had the chance to happen, and reading it as one is
        how a quiet week becomes an alarm.
        """
        return None if self.eligible == 0 else self.checked / self.eligible

    def as_wire(self) -> dict[str, Any]:
        return {
            "since": self.since.isoformat(),
            "until": self.until.isoformat(),
            "window_days": self.window_days,
            "turns_with_answers": self.turns_with_answers,
            "eligible": self.eligible,
            "checked": self.checked,
            "rate": self.rate,
        }


def read_price_check_compliance(
    session: Session,
    *,
    now: datetime,
    window_days: int = OPS_WINDOW_DAYS,
) -> PriceCheckCompliance:
    """How often a Turn that quoted a price had checked it. Reads only.

    Two queries and a scan in Python rather than one clever query: deciding
    whether prose names a price is not something to express in SQL, and the
    window holds one developer's users' Turns.
    """
    window = _Window(now=now, window_days=window_days)
    external = _external_tool_names()

    answered = session.execute(
        window.bound(
            select(
                AgentTurn.request_message_id,
                AgentMessage.content,
            ).join(AgentMessage, AgentMessage.id == AgentTurn.response_message_id),
            AgentTurn.started_at,
        )
    ).all()
    if not answered:
        return PriceCheckCompliance(
            since=window.since,
            until=window.until,
            window_days=window.window_days,
            turns_with_answers=0,
            eligible=0,
            checked=0,
        )

    request_ids = {row[0] for row in answered if row[0] is not None}
    tools_by_request: dict[int, set[str]] = {}
    if request_ids:
        for request_id, tool_name in session.execute(
            select(AgentToolCall.request_message_id, AgentToolCall.tool_name)
            .where(AgentToolCall.request_message_id.in_(request_ids))
            .distinct()
        ).all():
            tools_by_request.setdefault(request_id, set()).add(tool_name)

    eligible = 0
    checked = 0
    for request_id, content in answered:
        used = tools_by_request.get(request_id, set())
        if not used & external:
            continue
        text = str((content or {}).get("text") or "")
        if not names_a_price(text):
            continue
        eligible += 1
        if PRICE_CHECK_TOOL in used:
            checked += 1

    return PriceCheckCompliance(
        since=window.since,
        until=window.until,
        window_days=window.window_days,
        turns_with_answers=len(answered),
        eligible=eligible,
        checked=checked,
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
    "PRICE_CHECK_TOOL",
    "OpsSnapshot",
    "PriceCheckCompliance",
    "names_a_price",
    "read_ops_snapshot",
    "read_price_check_compliance",
]
