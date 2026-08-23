"""The constraints every later Alpha Desk milestone rests on.

Not schema documentation. Each of these is an invariant some future code will
depend on without checking, so the check has to live in the database:

*One Analysis per ``(symbol, trading_day)``, and the template version is not
part of that key.* Deliberately unlike ``provider_snapshots``, where the schema
version *is* in the key. There is one author here, at most one Analysis per
pair, and every reader reads by exactly that pair — two rows differing only by
template version would force every reader to choose, and no choice rule is
correct.

*One run per pair too.* That is what makes two users retrying the same symbol
one run rather than two, and it is what the retry ceiling counts against.

*Transcript order is a column, not a clock.* Two streamed messages can share a
millisecond, and a timestamp cannot express inserting between two rows.

*A trace cannot exist without the message that caused it.* Anchored to the
user's message, which already exists before the first tool call — so the column
can be NOT NULL and a Turn that dies mid-flight still leaves a readable chain.

*An Analysis trace is anchored to the run and ordered by a pair of columns.* The
run exists before the ``analysis`` row does, and two calls dispatched together in
one round share a millisecond — so the order is ``(round_index, seq)``, and the
trace dies with the run that owns it.

Run against a live Postgres rather than SQLite, because what is being tested is
what the database refuses.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from src.alpha.models import (
    AgentMessage,
    AgentThread,
    AgentToolCall,
    Analysis,
    AnalysisRun,
    AnalysisToolCall,
)
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory

SYMBOL = "CONSTR"
TRADING_DAY = date(2026, 8, 14)


@pytest.fixture(scope="module", autouse=True)
def alpha_schema():
    """The Alpha Desk tables, whatever shaped this database."""
    Base.metadata.create_all(
        sync_engine,
        tables=[
            AgentThread.__table__,
            AgentMessage.__table__,
            AgentToolCall.__table__,
            Analysis.__table__,
            AnalysisRun.__table__,
            AnalysisToolCall.__table__,
        ],
        checkfirst=True,
    )


@pytest.fixture
def analysis_rows():
    """Anything written under the test symbol, removed afterwards.

    Traces go with the run they belong to, by cascade rather than by a second
    delete — which is also one of the things under test.
    """
    yield
    with get_sync_db() as session:
        session.execute(delete(Analysis).where(Analysis.symbol == SYMBOL))
        session.execute(delete(AnalysisRun).where(AnalysisRun.symbol == SYMBOL))


@pytest.fixture
def thread():
    """A Thread with one user message in it, and its owner, all cleaned up."""
    thread_id = uuid.uuid4()
    email = f"alpha-{uuid.uuid4().hex[:12]}@example.com"

    with get_sync_db() as session:
        user = User(email=email, hashed_password="x")
        session.add(user)
        session.flush()
        session.add(AgentThread(id=thread_id, user_id=user.id, symbols=[SYMBOL]))
        session.flush()
        message = AgentMessage(
            thread_id=thread_id, seq=1, role="user", content={"text": "hỏi gì đó"}
        )
        session.add(message)
        session.flush()
        message_id = message.id
        user_id = user.id

    yield thread_id, message_id

    with get_sync_db() as session:
        session.execute(delete(AgentToolCall).where(AgentToolCall.thread_id == thread_id))
        session.execute(delete(AgentMessage).where(AgentMessage.thread_id == thread_id))
        session.execute(delete(AgentThread).where(AgentThread.id == thread_id))
        session.execute(delete(User).where(User.id == user_id))


def _refuses(*rows) -> None:
    """Assert the database refuses these rows, and leave nothing behind."""
    session = sync_session_factory()
    try:
        for row in rows:
            session.add(row)
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def _analysis(**overrides) -> Analysis:
    return Analysis(
        **{
            "symbol": SYMBOL,
            "trading_day": TRADING_DAY,
            "verdict": "hold",
            "payload": {},
            "schema_version": 1,
            **overrides,
        }
    )


def _run(**overrides) -> AnalysisRun:
    return AnalysisRun(
        **{
            "symbol": SYMBOL,
            "trading_day": TRADING_DAY,
            "status": "pending",
            "origin": "nightly",
            **overrides,
        }
    )


class TestAnalysisIdentity:
    """`analysis` is unique on `(symbol, trading_day)`."""

    def test_a_second_analysis_for_the_same_pair_is_refused(self, analysis_rows):
        with get_sync_db() as session:
            session.add(_analysis())

        _refuses(_analysis(verdict="reduce"))

    def test_a_different_schema_version_does_not_buy_a_second_row(self, analysis_rows):
        """The key excludes `schema_version` on purpose. Readers handle several
        values; they never choose between two rows for one pair."""
        with get_sync_db() as session:
            session.add(_analysis(schema_version=1))

        _refuses(_analysis(schema_version=2))

    def test_the_same_symbol_on_another_trading_day_is_a_new_row(self, analysis_rows):
        with get_sync_db() as session:
            session.add(_analysis())
            session.add(_analysis(trading_day=date(2026, 8, 13)))

        with get_sync_db() as session:
            days = session.execute(
                select(Analysis.trading_day)
                .where(Analysis.symbol == SYMBOL)
                .order_by(Analysis.trading_day.desc())
            ).scalars().all()
        assert days == [TRADING_DAY, date(2026, 8, 13)]


class TestAnalysisRunIdentity:
    """One run per pair, so two people retrying is one run."""

    def test_a_second_run_for_the_same_pair_is_refused(self, analysis_rows):
        with get_sync_db() as session:
            session.add(_run())

        _refuses(_run(origin="on_demand"))


class TestTranscriptOrder:
    """Order is held by `seq`, never by a timestamp."""

    def test_two_messages_cannot_share_a_seq(self, thread):
        thread_id, _ = thread

        _refuses(
            AgentMessage(thread_id=thread_id, seq=1, role="assistant", content={})
        )

    def test_messages_written_in_the_same_millisecond_still_have_an_order(self, thread):
        """The case a timestamp cannot serve: two streamed rows sharing a clock
        reading, which `seq` orders anyway."""
        thread_id, _ = thread
        stamp = datetime(2026, 8, 14, 12, 0, 0, 500, tzinfo=timezone.utc)

        with get_sync_db() as session:
            session.add(
                AgentMessage(
                    thread_id=thread_id,
                    seq=2,
                    role="assistant",
                    content={"text": "b"},
                    created_at=stamp,
                )
            )
            session.add(
                AgentMessage(
                    thread_id=thread_id,
                    seq=3,
                    role="assistant",
                    content={"text": "c"},
                    created_at=stamp,
                )
            )

        with get_sync_db() as session:
            rows = session.execute(
                select(AgentMessage.seq, AgentMessage.created_at)
                .where(AgentMessage.thread_id == thread_id, AgentMessage.seq > 1)
                .order_by(AgentMessage.seq)
            ).all()

        assert [row.seq for row in rows] == [2, 3]
        assert rows[0].created_at == rows[1].created_at


class TestTraceAnchor:
    """A trace anchors to the request message, and the anchor is not optional."""

    def test_a_trace_without_a_request_message_is_refused(self, thread):
        thread_id, _ = thread

        _refuses(
            AgentToolCall(
                thread_id=thread_id,
                request_message_id=None,
                tool_name="get_analysis",
                arguments={},
                status="ok",
            )
        )

    def test_a_trace_anchored_to_the_user_message_is_accepted(self, thread):
        thread_id, message_id = thread

        with get_sync_db() as session:
            session.add(
                AgentToolCall(
                    thread_id=thread_id,
                    request_message_id=message_id,
                    tool_name="get_analysis",
                    arguments={"symbol": SYMBOL},
                    result={"verdict": "hold"},
                    status="ok",
                    latency_ms=12,
                )
            )

        with get_sync_db() as session:
            anchored = session.execute(
                select(AgentToolCall).where(AgentToolCall.thread_id == thread_id)
            ).scalar_one()
        assert anchored.request_message_id == message_id


def _trace(run_id: int, **overrides) -> AnalysisToolCall:
    return AnalysisToolCall(
        **{
            "run_id": run_id,
            "round_index": 1,
            "seq": 1,
            "tool_name": "read_signal_field",
            "arguments": {"symbol": SYMBOL},
            "status": "ok",
            **overrides,
        }
    )


@pytest.fixture
def run_id(analysis_rows):
    """A run to hang a trace off, cleaned up with its trace."""
    with get_sync_db() as session:
        run = _run(status="producing")
        session.add(run)
        session.flush()
        return run.id


class TestAnalysisTraceOrder:
    """`(round_index, seq)` is the order, and it is unique per run."""

    def test_two_calls_cannot_share_a_place_in_a_round(self, run_id):
        with get_sync_db() as session:
            session.add(_trace(run_id))

        _refuses(_trace(run_id, tool_name="read_price_zone"))

    def test_two_calls_in_one_round_are_ordered_by_seq_not_by_the_clock(self, run_id):
        """The case a timestamp cannot serve: a round that dispatches two calls
        together, both stamped the same millisecond."""
        stamp = datetime(2026, 8, 22, 21, 0, 0, 500, tzinfo=timezone.utc)

        with get_sync_db() as session:
            session.add(_trace(run_id, seq=1, started_at=stamp))
            session.add(_trace(run_id, seq=2, started_at=stamp))

        with get_sync_db() as session:
            rows = session.execute(
                select(AnalysisToolCall.seq, AnalysisToolCall.started_at)
                .where(AnalysisToolCall.run_id == run_id)
                .order_by(AnalysisToolCall.round_index, AnalysisToolCall.seq)
            ).all()

        assert [row.seq for row in rows] == [1, 2]
        assert rows[0].started_at == rows[1].started_at

    def test_a_later_round_reuses_seq_one(self, run_id):
        with get_sync_db() as session:
            session.add(_trace(run_id, round_index=1, seq=1))
            session.add(_trace(run_id, round_index=2, seq=1))

        with get_sync_db() as session:
            rounds = session.execute(
                select(AnalysisToolCall.round_index)
                .where(AnalysisToolCall.run_id == run_id)
                .order_by(AnalysisToolCall.round_index)
            ).scalars().all()
        assert rounds == [1, 2]


class TestAnalysisTraceAnchor:
    """The trace is owned by the run, not by the published Analysis."""

    def test_a_trace_without_a_run_is_refused(self):
        _refuses(_trace(run_id=None))

    def test_a_trace_pointing_at_no_run_is_refused(self):
        """The anchor is a foreign key, so an id nobody issued is refused rather
        than stored as a dangling number."""
        _refuses(_trace(run_id=-1))

    def test_deleting_the_run_deletes_its_trace(self, analysis_rows):
        with get_sync_db() as session:
            run = _run(status="producing")
            session.add(run)
            session.flush()
            run_id = run.id
            session.add(_trace(run_id, seq=1))
            session.add(_trace(run_id, seq=2))

        with get_sync_db() as session:
            session.execute(delete(AnalysisRun).where(AnalysisRun.id == run_id))

        with get_sync_db() as session:
            left = session.execute(
                select(AnalysisToolCall).where(AnalysisToolCall.run_id == run_id)
            ).scalars().all()
        assert left == []

    def test_a_run_that_never_published_still_keeps_its_trace(self, run_id):
        """The reason the anchor is the run: a run that dies mid-flight writes no
        `analysis` row, and that is exactly when the trace is worth the most."""
        with get_sync_db() as session:
            session.add(
                _trace(
                    run_id,
                    status="tool_error",
                    error="the store had nothing for that field",
                    latency_ms=41,
                )
            )
            session.execute(
                delete(Analysis).where(Analysis.symbol == SYMBOL)
            )

        with get_sync_db() as session:
            published = session.execute(
                select(Analysis).where(Analysis.symbol == SYMBOL)
            ).scalars().all()
            trace = session.execute(
                select(AnalysisToolCall).where(AnalysisToolCall.run_id == run_id)
            ).scalar_one()

        assert published == []
        assert trace.status == "tool_error"
        assert trace.error == "the store had nothing for that field"
