"""The one fixed ops query (#100), over a database nothing else is writing to.

Every assertion here is about a *count*, and a count is the one thing a shared
test database cannot give: another module's leftover Turn would move every rate
and nobody would know which test was wrong. So this file creates its own
throwaway Postgres beside the dev store, the way an exact-count suite must,
and drops it afterwards.

Four properties are what the file is for.

*The window is half-open and it is real.* A row outside `[since, until)` is not
counted, in any signal — the whole value of the query is that "over 7 days"
means the same thing to all of them.

*The denominator is Turns.* Every rate is over `agent_turn` rows and never over
messages, incomplete Turns, or anything else that happens to be smaller.

*A key at zero is not a missing key.* Every flag reason is present even when
nothing produced it. Absent and zero read the same to a careless eye and mean
opposite things.

*It writes nothing.* Asserted by counting rows before and after, because the
query runs against the database the API serves from and that is the one promise
it owes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from src.agent.ops import OPS_WINDOW_DAYS, OpsSnapshot, read_ops_snapshot
from src.alpha.models import (
    FLAG_OTHER,
    FLAG_OVERREACH,
    FLAG_REASONS,
    FLAG_WRONG_FIGURE,
    TOOL_CALL_UNKNOWN_TOOL,
    TURN_COMPLETE,
    TURN_INCOMPLETE,
    AgentMessage,
    AgentThread,
    AgentToolCall,
    AgentTurn,
)
from src.auth.models import User
from src.core.database import Base

from .throwaway_db import create_database, drop_database

OPS_DB = "stockmassive_ops_test"

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=OPS_WINDOW_DAYS)
INSIDE = NOW - timedelta(days=1)
OUTSIDE = NOW - timedelta(days=OPS_WINDOW_DAYS + 1)


@pytest.fixture(scope="module")
def session_factory():
    url = create_database(OPS_DB)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False, future=True)
    engine.dispose()
    drop_database(OPS_DB)


@pytest.fixture
def world(session_factory):
    """One empty store per test, so a count is a count."""
    with session_factory() as session:
        for model in (AgentToolCall, AgentTurn, AgentMessage, AgentThread, User):
            session.query(model).delete()
        session.commit()
    return _World(session_factory)


class _World:
    """The smallest amount of store a Turn needs to exist in."""

    def __init__(self, session_factory) -> None:
        self._factory = session_factory
        with session_factory() as session:
            user = User(
                email=f"ops-{uuid.uuid4().hex}@example.com", hashed_password="x"
            )
            session.add(user)
            session.flush()
            self.user_id = user.id
            self.thread_id = uuid.uuid4()
            session.add(AgentThread(id=self.thread_id, user_id=user.id, title="ops"))
            session.commit()
        self._seq = 0

    def session(self):
        return self._factory()

    def message(
        self,
        *,
        role: str = "assistant",
        created_at: datetime = INSIDE,
        flagged_reason: str | None = None,
        flagged_at: datetime | None = None,
    ) -> int:
        self._seq += 1
        content: dict = {"text": "x", "tool_calls": [], "status": "complete"}
        with self.session() as session:
            row = AgentMessage(
                thread_id=self.thread_id,
                seq=self._seq,
                role=role,
                content=content,
                created_at=created_at,
                flagged_reason=flagged_reason,
                flagged_at=flagged_at,
            )
            session.add(row)
            session.commit()
            return row.id

    def turn(
        self,
        *,
        status: str = TURN_COMPLETE,
        terminal_reason: str | None = None,
        started_at: datetime = INSIDE,
        with_message: bool = True,
    ) -> None:
        request_id = self.message(role="user", created_at=started_at)
        response_id = (
            self.message(created_at=started_at) if with_message else None
        )
        with self.session() as session:
            session.add(
                AgentTurn(
                    id=uuid.uuid4(),
                    thread_id=self.thread_id,
                    request_message_id=request_id,
                    response_message_id=response_id,
                    status=status,
                    terminal_reason=terminal_reason,
                    started_at=started_at,
                )
            )
            session.commit()

    def tool_call(
        self,
        *,
        tool_name: str = "web_search",
        status: str = "ok",
        started_at: datetime = INSIDE,
    ) -> None:
        request_id = self.message(role="user", created_at=started_at)
        with self.session() as session:
            session.add(
                AgentToolCall(
                    thread_id=self.thread_id,
                    request_message_id=request_id,
                    tool_name=tool_name,
                    arguments={},
                    result={},
                    status=status,
                    started_at=started_at,
                )
            )
            session.commit()


def snapshot(world: _World, *, window_days: int = OPS_WINDOW_DAYS) -> OpsSnapshot:
    with world.session() as session:
        return read_ops_snapshot(session, now=NOW, window_days=window_days)


def test_the_window_is_half_open_and_binds_every_signal(world):
    """One row of each kind inside the window, one outside. Only the first counts."""
    world.turn(status=TURN_INCOMPLETE, terminal_reason="turn_deadline")
    world.turn(
        status=TURN_INCOMPLETE,
        terminal_reason="turn_deadline",
        started_at=OUTSIDE,
    )
    world.tool_call(status=TOOL_CALL_UNKNOWN_TOOL, tool_name="run_python")
    world.tool_call(
        status=TOOL_CALL_UNKNOWN_TOOL, tool_name="run_python", started_at=OUTSIDE
    )
    world.message(flagged_reason=FLAG_OVERREACH, flagged_at=INSIDE)
    world.message(flagged_reason=FLAG_OVERREACH, flagged_at=OUTSIDE)

    reading = snapshot(world)

    assert reading.since == SINCE
    assert reading.until == NOW
    assert reading.turns == 1
    assert reading.incomplete_reasons == {"turn_deadline": 1}
    assert reading.unknown_tool_calls == {"run_python": 1}
    assert reading.flags[FLAG_OVERREACH] == 1


def test_the_window_is_configurable(world):
    world.turn(started_at=OUTSIDE)

    assert snapshot(world).turns == 0
    assert snapshot(world, window_days=OPS_WINDOW_DAYS + 3).turns == 1


def test_the_incomplete_rate_is_over_turns_not_over_incomplete_turns(world):
    """The denominator is every Turn that ran, not every Turn that failed.

    A rate over the failures would be 100% on every window that had any, which
    is the shape of a number nobody can read.
    """
    for _ in range(19):
        world.turn()
    world.turn(status=TURN_INCOMPLETE, terminal_reason="turn_deadline")

    reading = snapshot(world)

    assert reading.turns == 20
    assert reading.incomplete_total == 1
    assert reading.incomplete_rate == pytest.approx(0.05)


def test_an_empty_window_is_zero_rather_than_a_division_by_zero(world):
    reading = snapshot(world)

    assert reading.turns == 0
    assert reading.incomplete_rate == 0.0
    assert reading.incomplete_total == 0


def test_every_flag_reason_is_a_key_even_at_zero(world):
    world.message(flagged_reason=FLAG_WRONG_FIGURE, flagged_at=INSIDE)

    reading = snapshot(world)

    assert set(reading.flags) == set(FLAG_REASONS)
    assert reading.flags[FLAG_WRONG_FIGURE] == 1
    assert reading.flags[FLAG_OVERREACH] == 0
    assert reading.flags_total == 1


def test_incomplete_reasons_are_counted_by_reason_and_only_for_incomplete_turns(world):
    """A cancelled Turn carries a reason too, and it is not an incomplete one."""
    world.turn(status=TURN_INCOMPLETE, terminal_reason="llm_call_timeout")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="llm_call_timeout")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="tool_timeout")
    world.turn(status="cancelled", terminal_reason="cancelled_by_user")
    world.turn()

    reading = snapshot(world)

    assert reading.incomplete_reasons == {
        "llm_call_timeout": 2,
        "tool_timeout": 1,
    }
    assert reading.incomplete_total == 3


def test_the_named_route_conditions_are_counted_apart_from_route_error(world):
    """The reason for not changing `ops.py` at all, held as a test.

    `incomplete_reasons` is a group-by over whatever the loop writes, so the five
    conditions that used to arrive as `route_error` split the moment they got
    their own reasons — no allowlist here to extend, and none to forget to
    extend next time. What is left under `route_error` is the residue: a 400
    whose body this repository has never seen.
    """
    world.turn(status=TURN_INCOMPLETE, terminal_reason="context_overflow")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="context_overflow")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="output_cap_exceeded")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="content_policy_blocked")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="model_unavailable")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="schema_rejected")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="route_error")

    reading = snapshot(world)

    assert reading.incomplete_reasons == {
        "context_overflow": 2,
        "output_cap_exceeded": 1,
        "content_policy_blocked": 1,
        "model_unavailable": 1,
        "schema_rejected": 1,
        "route_error": 1,
    }


def test_unknown_tool_is_counted_by_the_name_that_was_asked_for(world):
    """Capability gaps retain both the requested name and its frequency."""
    world.tool_call(status=TOOL_CALL_UNKNOWN_TOOL, tool_name="run_python")
    world.tool_call(status=TOOL_CALL_UNKNOWN_TOOL, tool_name="run_python")
    world.tool_call(status=TOOL_CALL_UNKNOWN_TOOL, tool_name="backtest")
    world.tool_call(status="ok", tool_name="web_search")

    reading = snapshot(world)

    assert reading.unknown_tool_calls == {"run_python": 2, "backtest": 1}
    assert reading.unknown_tool_total == 3
    assert reading.tool_calls == 4


def test_the_query_writes_nothing(world):
    """It runs against the database the API serves from. That is the promise."""
    world.turn(status=TURN_INCOMPLETE, terminal_reason="turn_deadline")
    world.message(flagged_reason=FLAG_OTHER, flagged_at=INSIDE)

    def totals() -> tuple[int, ...]:
        with world.session() as session:
            return tuple(
                int(session.execute(select(func.count()).select_from(model)).scalar())
                for model in (AgentTurn, AgentMessage, AgentToolCall, AgentThread)
            )

    before = totals()
    snapshot(world)
    assert totals() == before
