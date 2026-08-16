"""The one fixed ops query (#100), over a database nothing else is writing to.

Every assertion here is about a *count*, and a count is the one thing a shared
test database cannot give: another module's leftover Turn would move the
`grounding_failed` rate and nobody would know which test was wrong. So this file
creates its own throwaway Postgres beside the dev store, the same way the Eval
Fixture tests do, and drops it afterwards.

Four properties are what the file is for.

*The window is half-open and it is real.* A row outside `[since, until)` is not
counted, in every one of the five signals — the whole value of the query is that
"over 7 days" means the same thing to all of them.

*The denominator is Turns.* ADR-0016 states the threshold as `grounding_failed`
above 5% **of Turns**, so the rate is over `agent_turn` rows and never over
messages, incomplete Turns, or anything else that happens to be smaller.

*A key at zero is not a missing key.* Every flag reason, every `AnswerKind` and
every tool-call status the query names is present even when nothing produced it.
Absent and zero read the same to a careless eye and mean opposite things.

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

from src.agent.ops import (
    GROUNDING_FAILED_RATE_THRESHOLD,
    OPS_WINDOW_DAYS,
    NO_ANSWER_KIND,
    OpsSnapshot,
    read_ops_snapshot,
)
from src.agent.prompt import AnswerKind
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
from src.core.config import Settings
from src.core.database import Base

from .eval_store import create_database, drop_database

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
        answer_kind: str | None = AnswerKind.ANALYSIS.value,
        created_at: datetime = INSIDE,
        flagged_reason: str | None = None,
        flagged_at: datetime | None = None,
    ) -> int:
        self._seq += 1
        content: dict = {"text": "x"}
        if answer_kind is not None:
            content["answer_kind"] = answer_kind
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
        answer_kind: str | None = AnswerKind.ANALYSIS.value,
        with_message: bool = True,
    ) -> None:
        request_id = self.message(role="user", answer_kind=None, created_at=started_at)
        response_id = (
            self.message(answer_kind=answer_kind, created_at=started_at)
            if with_message
            else None
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
        tool_name: str = "get_price_zone",
        status: str = "ok",
        started_at: datetime = INSIDE,
    ) -> None:
        request_id = self.message(role="user", answer_kind=None, created_at=started_at)
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
    world.turn(status=TURN_INCOMPLETE, terminal_reason="grounding_failed")
    world.turn(
        status=TURN_INCOMPLETE,
        terminal_reason="grounding_failed",
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
    assert reading.grounding_failed == 1
    assert reading.incomplete_reasons == {"grounding_failed": 1}
    assert reading.unknown_tool_calls == {"run_python": 1}
    assert reading.flags[FLAG_OVERREACH] == 1


def test_the_window_is_configurable(world):
    world.turn(started_at=OUTSIDE)

    assert snapshot(world).turns == 0
    assert snapshot(world, window_days=OPS_WINDOW_DAYS + 3).turns == 1


def test_the_configured_default_is_the_window_the_threshold_is_stated_over():
    """``eval_ops_window_days`` cannot be imported from here, so it is pinned.

    ``src/core/config.py`` cannot import :mod:`src.agent.ops` — the import graph
    runs the other way — so the ADR's seven days is written down twice. This is
    the assertion that keeps the two copies equal, because a settings default
    that drifted would silently change what "5% over 7 days" is measured over.

    Read off the field rather than off a constructed ``Settings``: this is a
    claim about the two code constants agreeing, and a developer who exported
    ``EVAL_OPS_WINDOW_DAYS`` has configured their window rather than broken it.
    """
    assert (
        Settings.model_fields["eval_ops_window_days"].default == OPS_WINDOW_DAYS
    )


def test_the_grounding_rate_is_over_turns_not_over_incomplete_turns(world):
    """ADR-0016 states the threshold as a share of Turns. The denominator matters.

    Nineteen healthy Turns and one blocked one is 5% exactly, which is not
    *above* the threshold — the rule reopens category B above 5%, and a boundary
    read as a breach would reopen it on the first ordinary week.
    """
    for _ in range(19):
        world.turn()
    world.turn(status=TURN_INCOMPLETE, terminal_reason="grounding_failed")

    reading = snapshot(world)

    assert reading.turns == 20
    assert reading.grounding_failed == 1
    assert reading.grounding_failed_rate == pytest.approx(0.05)
    assert reading.grounding_failed_rate == GROUNDING_FAILED_RATE_THRESHOLD
    assert not reading.reopens_category_b


def test_above_five_percent_of_turns_reopens_category_b(world):
    for _ in range(18):
        world.turn()
    world.turn(status=TURN_INCOMPLETE, terminal_reason="grounding_failed")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="grounding_failed")

    reading = snapshot(world)

    assert reading.grounding_failed_rate == pytest.approx(0.10)
    assert reading.reopens_category_b


def test_a_widened_window_reads_the_rate_and_never_the_threshold(world):
    """*5% over 7 days* is one sentence, and the span is half of it.

    A month smooths the burst that separates fabrication from over-blocking, so
    a wider reading is useful and is not the quantity the rule decides on.
    """
    for _ in range(4):
        world.turn(started_at=OUTSIDE)
    world.turn(
        status=TURN_INCOMPLETE,
        terminal_reason="grounding_failed",
        started_at=OUTSIDE,
    )

    wide = snapshot(world, window_days=OPS_WINDOW_DAYS + 30)

    assert wide.grounding_failed_rate == pytest.approx(0.20)
    assert not wide.threshold_applies
    assert not wide.reopens_category_b


def test_an_empty_window_is_not_a_breach(world):
    """Zero Turns is zero percent, not a division by zero and not an alarm."""
    reading = snapshot(world)

    assert reading.turns == 0
    assert reading.grounding_failed_rate == 0.0
    assert not reading.reopens_category_b


def test_every_flag_reason_is_a_key_even_at_zero(world):
    world.message(flagged_reason=FLAG_WRONG_FIGURE, flagged_at=INSIDE)

    reading = snapshot(world)

    assert set(reading.flags) == set(FLAG_REASONS)
    assert reading.flags[FLAG_WRONG_FIGURE] == 1
    assert reading.flags[FLAG_OVERREACH] == 0
    assert reading.flags_total == 1


def test_every_answer_kind_is_a_key_and_a_released_nothing_is_its_own_bucket(world):
    """The distribution is over Turns, so a Turn that released no message shows.

    A Turn that ended before any block was released has no assistant message and
    therefore no ``answer_kind`` at all. Dropping those would make the
    distribution silently smaller than the Turn count it sits beside — and the
    Turns most likely to be missing are exactly the ones that failed.
    """
    world.turn(answer_kind=AnswerKind.ANALYSIS.value)
    world.turn(answer_kind=AnswerKind.REFUSAL.value)
    world.turn(
        status=TURN_INCOMPLETE, terminal_reason="turn_deadline", with_message=False
    )

    reading = snapshot(world)

    assert set(reading.answer_kinds) == {
        AnswerKind.ANALYSIS.value,
        AnswerKind.EDUCATION.value,
        AnswerKind.REFUSAL.value,
        NO_ANSWER_KIND,
    }
    assert reading.answer_kinds[AnswerKind.ANALYSIS.value] == 1
    assert reading.answer_kinds[AnswerKind.REFUSAL.value] == 1
    assert reading.answer_kinds[AnswerKind.EDUCATION.value] == 0
    assert reading.answer_kinds[NO_ANSWER_KIND] == 1
    # The distribution and the denominator are the same population.
    assert sum(reading.answer_kinds.values()) == reading.turns


def test_incomplete_reasons_are_counted_by_reason_and_only_for_incomplete_turns(world):
    """A cancelled Turn carries a reason too, and it is not an incomplete one."""
    world.turn(status=TURN_INCOMPLETE, terminal_reason="llm_call_timeout")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="llm_call_timeout")
    world.turn(status=TURN_INCOMPLETE, terminal_reason="grounding_failed")
    world.turn(status="cancelled", terminal_reason="cancelled_by_user")
    world.turn()

    reading = snapshot(world)

    assert reading.incomplete_reasons == {
        "llm_call_timeout": 2,
        "grounding_failed": 1,
    }
    assert reading.incomplete_total == 3


def test_unknown_tool_is_counted_by_the_name_that_was_asked_for(world):
    """ADR-0011's demand trigger is *which* tool, not how many."""
    world.tool_call(status=TOOL_CALL_UNKNOWN_TOOL, tool_name="run_python")
    world.tool_call(status=TOOL_CALL_UNKNOWN_TOOL, tool_name="run_python")
    world.tool_call(status=TOOL_CALL_UNKNOWN_TOOL, tool_name="backtest")
    world.tool_call(status="ok", tool_name="get_price_zone")

    reading = snapshot(world)

    assert reading.unknown_tool_calls == {"run_python": 2, "backtest": 1}
    assert reading.unknown_tool_total == 3
    assert reading.tool_calls == 4


def test_the_query_writes_nothing(world):
    """It runs against the database the API serves from. That is the promise."""
    world.turn(status=TURN_INCOMPLETE, terminal_reason="grounding_failed")
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

