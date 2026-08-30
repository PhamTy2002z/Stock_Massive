"""The two tools that read the store as a table, and the laws they hold.

Three laws, and they are not the same law said three ways.

**Frames never reach a message.** The numbers a table holds are exactly what a
Signal Desk draws and exactly what a model must not read, so the assertion is
made against the transcript a Turn would send rather than against the payload —
a clean payload and a clean transcript are two different claims, and only the
second one is the promise.

**A refusal is counted, never filled.** A line a company does not report becomes
``null`` with its reason named, because absent and zero are different answers and
a screener cannot tell them apart after the fact.

**A winner is a claim about a cell.** Not a row and not a column: the sentence a
comparison makes is *this symbol wins on this figure*, and a role on the row
would say the symbol wins outright.

Against a live database where the read is the point, on
``tests/test_agent_study_tools.py``'s reasoning: the tools write a row through an
ownership join and a fake store would let a broken one pass.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete

from src.agent.messages import (
    ContextBudget,
    ToolCallStatus,
    Transcript,
    TranscriptTurn,
    TurnToolCall,
    build_messages,
)
from src.agent.registry import ToolContext
from src.agent.tools import query as query_tools
from src.alpha.models import AgentArtifact, AgentMessage, AgentThread, AgentTurn
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine
from src.studies import frames_buffer
from src.studies.contracts import Frame, Provenance


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def turn():
    """A real Thread and Turn, because ``agent_artifact`` points at both.

    The foreign keys are the reason, and it is the same reason
    ``test_agent_composition.py`` builds one: a test writing an artifact under an
    invented Turn is a test the database refuses, and inventing one is exactly
    the mistake the ownership rule exists to catch.
    """
    email = f"query-{uuid.uuid4().hex[:12]}@example.com"
    with get_sync_db() as session:
        user = User(email=email, hashed_password="x", is_active=True)
        session.add(user)
        session.flush()
        thread = AgentThread(id=uuid.uuid4(), user_id=user.id, title=None, symbols=[])
        session.add(thread)
        session.flush()
        message = AgentMessage(
            thread_id=thread.id, seq=1, role="user", content={"text": "?"}
        )
        session.add(message)
        session.flush()
        row = AgentTurn(
            id=uuid.uuid4(),
            thread_id=thread.id,
            request_message_id=message.id,
            status="complete",
        )
        session.add(row)
        session.commit()
        made = (row.id, thread.id, user.id)

    yield made

    with get_sync_db() as session:
        session.execute(delete(AgentArtifact).where(AgentArtifact.thread_id == made[1]))
        session.execute(delete(AgentTurn).where(AgentTurn.thread_id == made[1]))
        session.execute(delete(AgentMessage).where(AgentMessage.thread_id == made[1]))
        session.execute(delete(AgentThread).where(AgentThread.id == made[1]))
        session.execute(delete(User).where(User.id == made[2]))


def a_context(turn_id=None, thread_id=None) -> ToolContext:
    return ToolContext(
        turn_id=turn_id,
        thread_id=thread_id,
        now=datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc),
    )


# -- the roles ---------------------------------------------------------------


def test_a_column_marks_one_winner_and_one_loser_by_the_declared_direction():
    roles = query_tools._comparison_roles(
        ("liquidity_profile.adtv_vnd",),
        {"liquidity_profile.adtv_vnd": [10.0, 30.0, 20.0]},
    )
    assert roles == {
        (1, "liquidity_profile.adtv_vnd"): "winner",
        (0, "liquidity_profile.adtv_vnd"): "loser",
    }


def test_a_lower_is_better_field_inverts_the_pair():
    """Amihud illiquidity: the smallest number is the best one.

    The case the whole ``better`` declaration exists for. ``Sign`` says both this
    and ``roe_percentile`` are non-negative, so nothing derivable from the unit
    or the convention separates them — only the field's own statement does.
    """
    roles = query_tools._comparison_roles(
        ("liquidity_profile.amihud_illiq",),
        {"liquidity_profile.amihud_illiq": [0.4, 0.1, 0.9]},
    )
    assert roles[(1, "liquidity_profile.amihud_illiq")] == "winner"
    assert roles[(2, "liquidity_profile.amihud_illiq")] == "loser"


def test_a_field_with_no_direction_is_left_unmarked():
    """A beta of 1.2 is not worse than 0.8; it is a different exposure."""
    assert (
        query_tools._comparison_roles(
            ("relative_strength.beta_vs_market_index",),
            {"relative_strength.beta_vs_market_index": [0.8, 1.2]},
        )
        == {}
    )


def test_one_answered_cell_is_not_a_winner():
    """With one number there is nothing to be better than.

    A lone survivor dressed as a victor is the exact failure a comparison of two
    companies where one refused would produce, and it would read as a finding.
    """
    assert (
        query_tools._comparison_roles(
            ("risk_adjusted.sharpe_annualized",),
            {"risk_adjusted.sharpe_annualized": [1.4, None]},
        )
        == {}
    )


def test_a_tie_has_no_winner():
    assert (
        query_tools._comparison_roles(
            ("risk_adjusted.sharpe_annualized",),
            {"risk_adjusted.sharpe_annualized": [1.4, 1.4]},
        )
        == {}
    )


def test_a_cell_role_naming_a_row_that_is_not_there_fails_where_it_is_written():
    with pytest.raises(ValueError, match="names row 3"):
        Frame(
            kind="table",
            columns=("symbol", "roe"),
            rows=(("VCB", 1.0),),
            unit=None,
            labels={"symbol": "Mã", "roe": "ROE"},
            cell_roles={(3, "roe"): "winner"},
        )


def test_a_cell_role_naming_a_column_that_is_not_there_fails_too():
    with pytest.raises(ValueError, match="does not have"):
        Frame(
            kind="table",
            columns=("symbol", "roe"),
            rows=(("VCB", 1.0),),
            unit=None,
            labels={"symbol": "Mã", "roe": "ROE"},
            cell_roles={(0, "roa"): "winner"},
        )


def test_cell_roles_reach_the_browser_as_triples():
    """A JSON key can only be a string, so the pair is a field rather than a key.

    Spelled ``"0|roe"`` it would have to be parsed back at the far end, which is
    a second encoding for the browser to agree with.
    """
    payload = Frame(
        kind="table",
        columns=("symbol", "roe"),
        rows=(("VCB", 1.0), ("VIC", 2.0)),
        unit=None,
        labels={"symbol": "Mã", "roe": "ROE"},
        cell_roles={(1, "roe"): "winner"},
    ).to_payload()
    assert payload["cellRoles"] == [{"row": 1, "column": "roe", "role": "winner"}]


# -- the provenance vocabulary -----------------------------------------------


def test_a_provenance_naming_a_provider_is_refused():
    """``source`` answers where the numbers came from, not who supplied them.

    It was a free string and every caller wrote a provider name into it, which
    is why the browser's badge could never be more than a guess.
    """
    with pytest.raises(ValueError, match="is not where numbers come from"):
        Provenance(
            source="vnstock",
            as_of=datetime(2026, 8, 27, tzinfo=timezone.utc),
            sessions_used=1,
            health="normal",
            reason=None,
        )


def test_the_query_a_frame_was_built_from_survives_to_the_payload():
    payload = Provenance(
        source="store",
        as_of=datetime(2026, 8, 27, tzinfo=timezone.utc),
        sessions_used=8,
        health="normal",
        reason=None,
        query={"source": "statement", "symbols": ["VIC", "VCB"]},
    ).to_payload()
    assert payload["query"]["symbols"] == ["VIC", "VCB"]


# -- the ceilings ------------------------------------------------------------


def test_a_frame_taller_than_the_row_ceiling_is_refused_by_size():
    frame = Frame(
        kind="table",
        columns=("symbol", "close"),
        rows=tuple(("VCB", float(index)) for index in range(query_tools.MAX_QUERY_ROWS + 1)),
        unit=None,
        labels={"symbol": "Mã", "close": "Giá đóng cửa"},
    )
    reason = query_tools._too_big(frame)
    assert reason is not None and str(query_tools.MAX_QUERY_ROWS) in reason


def test_a_frame_under_both_ceilings_is_not_refused():
    frame = Frame(
        kind="table",
        columns=("symbol", "close"),
        rows=(("VCB", 1.0),),
        unit=None,
        labels={"symbol": "Mã", "close": "Giá đóng cửa"},
    )
    assert query_tools._too_big(frame) is None


# -- the frame store ---------------------------------------------------------


def test_a_frame_kind_nobody_registered_is_refused_at_the_write():
    """The kind is what an operator reads ``agent_artifact`` by.

    A typo would file a row under a name nothing queries for, which is the one
    failure that leaves the row present and unreachable at once.
    """
    with get_sync_db() as session:
        with pytest.raises(ValueError, match="is not a frame kind"):
            frames_buffer.store_frame(
                session,
                kind="whatever",
                frame=Frame(
                    kind="table",
                    columns=("symbol",),
                    rows=(("VCB",),),
                    unit=None,
                    labels={"symbol": "Mã"},
                ),
                provenance=Provenance(
                    source="store",
                    as_of=datetime(2026, 8, 27, tzinfo=timezone.utc),
                    sessions_used=1,
                    health="normal",
                    reason=None,
                ),
                params={},
                title="Bảng",
                turn_id=None,
                thread_id=None,
            )


def test_a_stored_frame_is_read_back_by_the_turn_that_made_it_and_by_nobody_else(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    with get_sync_db() as session:
        frame_id = frames_buffer.store_frame(
            session,
            kind=frames_buffer.QUERY_KIND,
            frame=Frame(
                kind="table",
                columns=("symbol", "close"),
                rows=(("VCB", 61_500.0),),
                unit="vnd",
                labels={"symbol": "Mã", "close": "Giá đóng cửa"},
            ),
            provenance=Provenance(
                source="store",
                as_of=datetime(2026, 8, 27, tzinfo=timezone.utc),
                sessions_used=1,
                health="normal",
                reason=None,
            ),
            params={"source": "bar_daily", "symbols": ["VCB"]},
            title="giá theo phiên: VCB",
            turn_id=context.turn_id,
            thread_id=context.thread_id,
        )
        session.commit()

        frame, provenance = frames_buffer.read_frame(
            session, str(frame_id), turn_id=context.turn_id
        )
        assert frame["rows"] == [["VCB", 61500.0]]
        assert provenance["source"] == "store"

        with pytest.raises(frames_buffer.FrameNotAvailable):
            frames_buffer.read_frame(
                session, str(frame_id), turn_id=uuid.uuid4()
            )


# -- the law -----------------------------------------------------------------


# -- the handlers, against the real store -------------------------------------
#
# Every test below calls a handler. The first version of this file asserted the
# three laws against payloads it wrote by hand, which proved that a literal
# written in a test contains what the test wrote in it. What follows reads the
# store this deployment actually holds — the same reasoning
# ``tests/studies/test_runner.py`` gives for not faking it.


#: Two symbols this file owns. Not tickers of real companies: the tests below
#: seed their own sessions, and borrowing a real ticker would make a green run
#: depend on whether somebody's backfill had reached it.
SYMBOLS = ("QRYA", "QRYB")

#: Enough sessions for the one field these tests compare on. ``adtv_vnd``
#: averages over twenty and refuses below twenty-one (``market_behavior.py``);
#: thirty leaves room for the anchor session the band gateway reads before the
#: window's oldest bar.
SEEDED_SESSIONS = 30

#: The symbol the Trading Day calendar is defined by.
CALENDAR_SYMBOL = "QRYIDX"


@pytest.fixture
def universe_symbols(monkeypatch):
    """Two symbols with a real window of sessions behind them, in the store.

    Seeded rather than borrowed, and this is the difference between a test that
    proves something and a test that skips. The earlier version of this file read
    whichever symbols the environment happened to declare and skipped when there
    were none — so on any machine without a backfill, every assertion about the
    handlers silently did not run.

    The Universe is patched where ``query.py`` binds it, because that is the gate
    the handler actually consults; patching the module it came from would leave
    the bound name pointing at the real one.
    """
    from src.stocks.models import BarDaily
    from src.stocks.providers.contracts import PriceBasis

    day = date(2026, 8, 3)
    rows: list[BarDaily] = []
    for index in range(SEEDED_SESSIONS):
        session_day = day + timedelta(days=index)
        # The Trading Day calendar is read off ``series = 'index'`` alone
        # (``trading_day.py``), so an equity-only seed gives a store with bars
        # and no sessions — which is what the first version of this fixture did,
        # and every handler answered "no closed session yet".
        rows.append(
            BarDaily(
                symbol=CALENDAR_SYMBOL,
                trading_day=session_day,
                series="index",
                open=1_800.0,
                high=1_820.0,
                low=1_790.0,
                close=1_810.0 + index,
                volume=500_000_000,
                price_basis=PriceBasis.ADJUSTED_AT_SOURCE.value,
                source="vnstock",
                observed_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            )
        )
        for offset, symbol in enumerate(SYMBOLS):
            close = 20_000.0 + index * 100 + offset * 5_000
            rows.append(
                BarDaily(
                    symbol=symbol,
                    trading_day=session_day,
                    series="equity",
                    open=close - 100,
                    high=close + 200,
                    low=close - 200,
                    close=close,
                    # Different by symbol so the comparison has a winner that is
                    # a fact rather than a coin toss.
                    volume=1_000_000 + offset * 500_000,
                    price_basis=PriceBasis.ADJUSTED_AT_SOURCE.value,
                    source="vnstock",
                    observed_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
                )
            )

    with get_sync_db() as session:
        session.add_all(rows)
        session.commit()

    monkeypatch.setattr(query_tools, "build_universe", lambda _session: _Universe())

    yield SYMBOLS

    with get_sync_db() as session:
        session.execute(
            delete(BarDaily).where(
                BarDaily.symbol.in_((*SYMBOLS, CALENDAR_SYMBOL))
            )
        )


class _Universe:
    """Only what ``query.py`` asks a Universe for."""

    symbols = SYMBOLS

    def contains(self, symbol: str) -> bool:
        return symbol in SYMBOLS


def test_a_query_answer_carries_no_number_out_of_the_frame(turn, universe_symbols):
    """The payload names the shape and never a cell.

    Read off the handler's own answer rather than off the transcript, which is
    the other half of the assertion further down: this is what fails if a later
    change puts "just the first row" in the summary. The key set is asserted
    whole, so an added key is a red test rather than a silent widening.
    """
    turn_id, thread_id, _ = turn
    answered = query_tools.QueryTools().query(
        a_context(turn_id, thread_id),
        {"source": "bar_daily", "symbols": list(universe_symbols[:2]), "window": 5},
    )

    assert "error" not in answered, answered
    assert set(answered) == {
        "frameId",
        "source",
        "symbols",
        "rows",
        "columnCount",
        "columnSample",
        "asOf",
        "unit",
        "missing",
        "notCovered",
        "detail",
    }
    # The summary is sizes, names, dates and refusal counts. Not one number that
    # is a measurement of a company — and a close is the easiest one to leak.
    text = json.dumps(answered, ensure_ascii=False)
    frame, _ = _stored_frame(answered["frameId"], turn_id)
    for row in frame["rows"]:
        for cell in row[2:]:
            if isinstance(cell, (int, float)):
                assert str(cell) not in text, cell


def test_the_frame_id_is_the_first_key_a_long_answer_would_keep(
    turn, universe_symbols
):
    """A result over its size is replaced by a preview of its *head*.

    So the id — the only part of the answer that can be drawn — has to be
    written before anything that can grow. It was written last, and a wide
    statement read would have cut it off after the row was already committed.
    """
    turn_id, thread_id, _ = turn
    answered = query_tools.QueryTools().query(
        a_context(turn_id, thread_id),
        {"source": "bar_daily", "symbols": [universe_symbols[0]], "window": 3},
    )
    assert next(iter(answered)) == "frameId"


def test_a_symbol_outside_the_universe_is_refused_by_name(turn):
    """The gate ``get_field`` keeps, kept here: a promise, not a schema."""
    turn_id, thread_id, _ = turn
    answered = query_tools.QueryTools().query(
        a_context(turn_id, thread_id),
        {"source": "bar_daily", "symbols": ["ZZZZ"]},
    )
    assert answered["error"] == "cannot_read"
    assert "ZZZZ" in answered["detail"]


def test_a_wide_statement_read_is_refused_before_it_runs():
    """The ceiling that has to bite before the query, not after the grid.

    Without ``items`` a statement read asks for every line every named symbol
    filed — measured at 574 columns for ten symbols. Checked only on the built
    frame, it would pull tens of thousands of rows into memory and refuse
    afterwards, which is a ceiling protecting the model's context and not the
    process.

    Asserted on the estimate rather than through the handler, because the handler
    has to reach a store holding filed quarters to get that far and seeding a
    hundred thousand statement lines to prove a subtraction is not a test anybody
    would keep.
    """
    # Ten symbols across every quarter the store holds — the shape that pulls
    # tens of thousands of rows into one dict before anything is built.
    deep = 10 * 34 * query_tools.WIDEST_STATEMENT_LINES
    assert deep > query_tools.MAX_QUERY_CELLS

    # And the ordinary ask still runs: ten symbols across eight quarters is
    # measured at 0,12 s on the real store, so a guard that refused it would be
    # refusing the question this tool exists for.
    ordinary = 10 * 8 * query_tools.WIDEST_STATEMENT_LINES
    assert ordinary <= query_tools.MAX_QUERY_CELLS


def test_a_window_wider_than_the_ceiling_is_clamped_rather_than_obeyed():
    assert query_tools._window({"window": 10_000}, 60) == query_tools.MAX_WINDOW
    # ``isinstance(True, int)`` is true in Python, so a model answering
    # ``window: true`` would otherwise get a silent one-session read.
    assert query_tools._window({"window": True}, 60) == 60


def test_corporate_actions_answers_the_columns_the_table_actually_has(
    turn, universe_symbols
):
    """The two columns that were dead: named wrong, defaulted to ``None``.

    ``getattr(action, "ratio", None)`` on a table whose column is
    ``exercise_ratio`` gave every row a null and a summary saying nothing was
    missing. This asserts on the *shape the store offers*, so renaming a column
    out from under the reader goes red here instead of shipping blank.
    """
    from src.stocks.models import CorporateAction

    # Every column this reader offers has to be a column the table has. The
    # failure this catches is not a rename: it is a reader asking for a name that
    # was never there, which ``getattr(row, name, None)`` turns into a null on
    # every row and a summary saying nothing was missing.
    for name in query_tools.ACTION_COLUMNS:
        assert hasattr(CorporateAction, name), name

    with get_sync_db() as session:
        session.add(
            CorporateAction(
                symbol=SYMBOLS[0],
                ex_date=date(2026, 8, 12),
                event_code="DIV",
                title="Trả cổ tức bằng tiền",
                kind="cash_dividend",
                exercise_ratio=Decimal("0.10"),
                value_per_share=Decimal("1000.00"),
                changes_share_count=False,
                confirmation="confirmed",
                source="vnstock",
                observed_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            )
        )
        session.commit()

    try:
        turn_id, thread_id, _ = turn
        answered = query_tools.QueryTools().query(
            a_context(turn_id, thread_id),
            {"source": "corporate_actions", "symbols": list(universe_symbols)},
        )
        assert "error" not in answered, answered

        frame, _ = _stored_frame(answered["frameId"], turn_id)
        assert "exercise_ratio" in frame["columns"]
        assert "ratio" not in frame["columns"]

        # The values reach the frame. This is the whole point: before the fix
        # both of these were ``None`` on every row.
        cells = dict(zip(frame["columns"], frame["rows"][0]))
        assert cells["exercise_ratio"] == 0.10
        assert cells["value_per_share"] == 1000.0
        assert cells["kind"] == "cash_dividend"

        # And the symbol with no dated action says so under a name that is true:
        # ``for_symbols`` excludes undated ones by construction.
        assert answered["missing"] == {f"{SYMBOLS[1]}:no_dated_corporate_action": 1}
    finally:
        with get_sync_db() as session:
            session.execute(
                delete(CorporateAction).where(CorporateAction.symbol.in_(SYMBOLS))
            )


def test_compare_fields_reads_the_store_and_marks_a_winner(turn, universe_symbols):
    """The whole tool, end to end, on figures this deployment computes.

    ``adtv_vnd`` is the field chosen because it needs no cross-section and no
    quarterly statement: every symbol with a window of bars has one, so a green
    test here means the store answered rather than that the assertion was weak.
    """
    turn_id, thread_id, _ = turn
    answered = query_tools.QueryTools().compare_fields(
        a_context(turn_id, thread_id),
        {
            "symbols": list(universe_symbols[:2]),
            "field_ids": ["liquidity_profile.adtv_vnd"],
        },
    )
    if "error" in answered:
        pytest.skip("the store answered no figure for either symbol")

    assert next(iter(answered)) == "frameId"
    assert answered["cellsAsked"] == 2
    assert answered["fields"][0]["better"] == "higher"

    frame, provenance = _stored_frame(answered["frameId"], turn_id)
    assert provenance["source"] == "store"
    if answered["cellsAnswered"] == 2:
        roles = {
            (entry["row"], entry["column"]): entry["role"]
            for entry in frame["cellRoles"]
        }
        assert sorted(roles.values()) == ["loser", "winner"]

    # And the numbers stay behind: the payload names counts, not values.
    text = json.dumps(answered, ensure_ascii=False)
    for row in frame["rows"]:
        for cell in row[1:]:
            if isinstance(cell, (int, float)):
                assert str(cell) not in text, cell


def test_compare_fields_refuses_a_field_nobody_registered(turn, universe_symbols):
    turn_id, thread_id, _ = turn
    with pytest.raises(ValueError, match="is not a registered Signal Field"):
        query_tools.QueryTools().compare_fields(
            a_context(turn_id, thread_id),
            {"symbols": list(universe_symbols[:2]), "field_ids": ["not.a.field"]},
        )


def _stored_frame(frame_id: str, turn_id):
    with get_sync_db() as session:
        return frames_buffer.read_frame(session, frame_id, turn_id=turn_id)


def test_the_frames_are_absent_from_the_messages_a_query_turn_would_send(turn):
    """The law itself, read off the transcript rather than off the payload.

    ``result_text`` is what the executor normalises a handler's answer into and
    what the model actually reads, so this is the assertion that would fail if a
    later change put a cell in the payload "just for the model to check".
    """
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    with get_sync_db() as session:
        frame_id = frames_buffer.store_frame(
            session,
            kind=frames_buffer.COMPARE_KIND,
            frame=Frame(
                kind="table",
                columns=("symbol", "liquidity_profile.adtv_vnd"),
                rows=(("VIC", 424_242_424.0), ("VCB", 313_131_313.0)),
                unit=None,
                labels={
                    "symbol": "Mã",
                    "liquidity_profile.adtv_vnd": "Giá trị giao dịch bình quân",
                },
                cell_roles={(0, "liquidity_profile.adtv_vnd"): "winner"},
            ),
            provenance=Provenance(
                source="store",
                as_of=datetime(2026, 8, 27, tzinfo=timezone.utc),
                sessions_used=1,
                health="normal",
                reason=None,
            ),
            params={"symbols": ["VIC", "VCB"]},
            title="So sánh VIC, VCB",
            turn_id=context.turn_id,
            thread_id=context.thread_id,
        )
        session.commit()

    answered = {
        "symbols": ["VIC", "VCB"],
        "fields": [
            {
                "fieldId": "liquidity_profile.adtv_vnd",
                "label": "Giá trị giao dịch bình quân",
                "unit": "vnd",
                "better": "higher",
                "answered": 2,
            }
        ],
        "asOf": "2026-08-27",
        "cellsAnswered": 2,
        "cellsAsked": 2,
        "missing": {},
        "frameId": str(frame_id),
    }
    call = TurnToolCall(
        id="call-1",
        name="compare_fields",
        arguments={
            "symbols": ["VIC", "VCB"],
            "field_ids": ["liquidity_profile.adtv_vnd"],
        },
        status=ToolCallStatus.OK,
        result_text=json.dumps(answered, ensure_ascii=False),
        summary="So sánh 2 mã trên 1 chỉ báo",
    )
    built = build_messages(
        Transcript(
            system_prompt="hệ thống",
            turns=(
                TranscriptTurn(
                    user_text="VIC hay VCB thanh khoản hơn?", tool_calls=(call,)
                ),
            ),
        ),
        ContextBudget(),
    )

    whole = "\n".join(str(message.content or "") for message in built.messages)
    assert "424242424" not in whole.replace(".0", "")
    assert "313131313" not in whole.replace(".0", "")
    assert str(frame_id) in whole


# -- the arguments -----------------------------------------------------------


def test_a_source_this_system_does_not_hold_is_refused_by_name():
    with pytest.raises(ValueError, match="is not a source"):
        query_tools.QueryTools().query(a_context(), {"source": "orderbook", "symbols": ["VCB"]})


def test_a_column_this_source_does_not_offer_is_refused_by_name():
    refusal = query_tools._columns(
        {"columns": ["close", "vwap"]}, query_tools.BAR_COLUMNS
    )
    assert refusal["error"] == "cannot_read"
    assert "vwap" in refusal["detail"]


def test_columns_come_back_in_the_sources_order_and_not_the_callers():
    """open/high/low/close read in that order for a reason a caller may not know."""
    assert query_tools._columns(
        {"columns": ["close", "open"]}, query_tools.BAR_COLUMNS
    ) == ("open", "close")


def test_omitting_columns_asks_for_all_of_them():
    assert query_tools._columns({}, query_tools.REFERENCE_COLUMNS) == tuple(
        query_tools.REFERENCE_COLUMNS
    )


def test_a_quarter_label_freezes_at_the_last_day_of_the_quarter():
    """A quarter is a range and ``as_of`` is an instant."""
    assert query_tools._period_end("2026-Q2") == date(2026, 6, 30)
    assert query_tools._period_end("2025-Q4") == date(2025, 12, 31)
    assert query_tools._period_end("2026-Q1") == date(2026, 3, 31)


def test_the_two_tools_are_offered_to_a_conversation():
    from src.agent.toolsets import CHAT_TOOLSETS, resolve_toolset

    offered = resolve_toolset(CHAT_TOOLSETS)
    assert "query" in offered
    assert "compare_fields" in offered
