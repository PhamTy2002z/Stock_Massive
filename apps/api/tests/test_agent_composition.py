"""Gathering numbers and then drawing them, for a question no Study answers.

Three claims, and the middle one is the reason this path can exist at all.

*A series is summarised, never sent.* ``get_series`` reads sixty sessions and
answers with five statistics and an id. Everything the reducer of a Signal Desk
needs is in the row it names.

*A frame belongs to the Turn that made it.* The id is a UUID a model has seen,
and a model that has seen one could name it later — or invent a plausible one.
So a frame from any other Turn is refused as though it were not there, and the
scheme rests on the check rather than on the id being unguessable.

*A bad block costs one block.* A model that named the wrong widget for one frame
has still gathered good ones, and throwing the Signal Desk away over a mistake it
could fix next round is the wrong trade.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select

from src.agent.registry import ToolContext
from src.agent.tools import signals as signal_tools, studies as study_tools
from src.alpha.envelope import EvidenceFigure
from src.alpha.models import AgentArtifact, AgentMessage, AgentThread, AgentTurn
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine
from src.studies import frames_buffer, grammar
from src.studies.contracts import Frame, Provenance

FIELD = "risk_adjusted.sharpe_annualized"
SYMBOL = "STB"
DAYS = tuple(date(2026, 8, day) for day in range(10, 20))


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def turn():
    """A real Thread and Turn, because ``agent_artifact`` points at both.

    The foreign keys are the reason: a test writing an artifact under an
    invented Turn would be a test the database refuses, and inventing one is
    exactly the mistake the ownership rule exists to catch.
    """
    email = f"composition-{uuid.uuid4().hex[:12]}@example.com"
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


@pytest.fixture
def other_turn(turn):
    """A second Turn, for the frame that must not be reachable from the first."""
    del turn
    email = f"stranger-{uuid.uuid4().hex[:12]}@example.com"
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

    yield made[0]

    with get_sync_db() as session:
        session.execute(delete(AgentArtifact).where(AgentArtifact.thread_id == made[1]))
        session.execute(delete(AgentTurn).where(AgentTurn.thread_id == made[1]))
        session.execute(delete(AgentMessage).where(AgentMessage.thread_id == made[1]))
        session.execute(delete(AgentThread).where(AgentThread.id == made[1]))
        session.execute(delete(User).where(User.id == made[2]))


def a_figure(value: float | None, *, reason: str | None = None) -> EvidenceFigure:
    return EvidenceFigure(
        field_id=FIELD,
        label="Sharpe (năm hoá)",
        value=value,
        unit="ratio",
        kind="signal",
        source="store",
        interpretation="Đọc theo mức.",
        health=_health(value),
        reason_code=reason,
        reason=None if reason is None else "không đủ lịch sử",
        as_of=DAYS[-1],
        sessions_used=250,
        window_days=250,
        extras={},
    )


def _health(value: float | None):
    from src.alpha.envelope import Health

    return Health.OK if value is not None else Health.REFUSED


@pytest.fixture
def store(monkeypatch):
    """A store holding ten sessions of one symbol, and nothing else.

    The field itself is stubbed: what this file is about is the series, the
    ownership rule and the composition, and a real ten-session window of a
    250-session field would be ten refusals.
    """
    monkeypatch.setattr(
        signal_tools, "trading_days_before", lambda _s, day, count: DAYS[-count - 1 : -1]
    )
    monkeypatch.setattr(signal_tools, "latest_trading_day", lambda _s: DAYS[-1])
    monkeypatch.setattr(
        signal_tools,
        "build_universe",
        lambda _s: type("U", (), {"contains": staticmethod(lambda _x: True)})(),
    )


def series(arguments: dict, *, turn_id=None, thread_id=None) -> dict:
    return dict(
        signal_tools.SignalTools().get_series(
            ToolContext(
                user_id=1,
                turn_id=turn_id,
                thread_id=thread_id,
                now=datetime(2026, 8, 20, tzinfo=timezone.utc),
            ),
            arguments,
        )
    )


def render(arguments: dict, *, turn_id=None, thread_id=None) -> dict:
    return dict(
        study_tools.StudyTools().render_signal_desk(
            ToolContext(user_id=1, turn_id=turn_id, thread_id=thread_id), arguments
        )
    )


# -- gathering -------------------------------------------------------------


def test_a_series_answers_with_statistics_and_an_id_and_never_the_points(
    store, turn, monkeypatch
):
    values = iter([1.0, 2.0, 3.0, 4.0, 5.0])
    monkeypatch.setattr(
        signal_tools,
        "figure_for_field",
        lambda *_args, **_kwargs: a_figure(next(values)),
    )
    turn_id = turn[0]

    answered = series({"field_id": FIELD, "symbol": SYMBOL, "sessions": 5}, turn_id=turn_id)

    assert answered["summary"] == {
        "first": 1.0,
        "last": 5.0,
        "min": 1.0,
        "max": 5.0,
        "median": 3.0,
    }
    assert answered["sessionsUsed"] == 5
    assert answered["health"] == "normal"
    # The points are in the row this names, and there is no key here holding
    # them: a model that could read the series would read the wrong one.
    assert "rows" not in answered
    assert "series" not in answered

    with get_sync_db() as session:
        row = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(answered["frameId"])
            )
        ).scalar_one()
        assert row.turn_id == turn_id
        assert [point[1] for point in row.frames["series"]["rows"]] == [1, 2, 3, 4, 5]


def test_a_session_the_store_refused_is_a_hole_with_its_reason_counted(
    store, turn, monkeypatch
):
    values = iter([1.0, None, 3.0])
    monkeypatch.setattr(
        signal_tools,
        "figure_for_field",
        lambda *_args, **_kwargs: (
            lambda value: a_figure(value, reason=None if value else "insufficient_history")
        )(next(values)),
    )

    answered = series(
        {"field_id": FIELD, "symbol": SYMBOL, "sessions": 3}, turn_id=turn[0]
    )

    assert answered["sessionsRead"] == 3
    assert answered["sessionsUsed"] == 2
    assert answered["health"] == "degraded"
    assert answered["refusals"] == {"insufficient_history": 1}

    with get_sync_db() as session:
        row = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(answered["frameId"])
            )
        ).scalar_one()
        # Null and not zero: a session the store refused is not a session in
        # which the number was nought.
        assert [point[1] for point in row.frames["series"]["rows"]] == [1.0, None, 3.0]


def test_a_window_the_store_refuses_entirely_is_a_refusal_and_not_an_empty_chart(
    store, turn, monkeypatch
):
    monkeypatch.setattr(
        signal_tools,
        "figure_for_field",
        lambda *_args, **_kwargs: a_figure(None, reason="insufficient_history"),
    )

    answered = series(
        {"field_id": FIELD, "symbol": SYMBOL, "sessions": 3}, turn_id=turn[0]
    )

    assert answered["error"] == "cannot_read"
    assert "insufficient_history" in answered["detail"]
    assert "frameId" not in answered


def test_a_field_nothing_registers_says_where_the_real_names_are():
    with pytest.raises(ValueError, match="list_fields"):
        series({"field_id": "made.up", "symbol": SYMBOL})


def test_the_cost_of_a_series_is_bounded_by_the_field_it_reads():
    """Points × window is the real cost, and the clamp lands on the points.

    A field over a year of sessions cannot afford a hundred and twenty of them;
    one over twenty sessions can. Stated here rather than only through a handler
    because it is arithmetic, and arithmetic should be assertable without a store.
    """
    # A cheap field is bounded by the picture rather than by the work.
    assert signal_tools.points_affordable(20, 500) == signal_tools.MAX_SERIES_SESSIONS
    # An expensive one is bounded by the work.
    assert signal_tools.points_affordable(250, 120) == 48
    # And a request smaller than either ceiling is answered as asked.
    assert signal_tools.points_affordable(250, 20) == 20


# -- drawing ---------------------------------------------------------------


def a_frame_for(turn_id) -> str:
    with get_sync_db() as session:
        frame_id = frames_buffer.store_series(
            session,
            frame=Frame(
                kind="series",
                columns=("session", "value"),
                rows=(("2026-08-19", 1.0), ("2026-08-20", 2.0)),
                unit="ratio",
                labels={"session": "Phiên", "value": "Sharpe"},
            ),
            provenance=Provenance(
                source="store",
                as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
                sessions_used=2,
                health="normal",
                reason=None,
            ),
            params={"field_id": FIELD, "symbol": SYMBOL, "sessions": 2},
            turn_id=turn_id,
            thread_id=None,
        )
        session.commit()
    return str(frame_id)


def a_table_for(turn_id) -> str:
    """A one-row table: what a KPI strip is read out of."""
    with get_sync_db() as session:
        frame_id = frames_buffer.store_frame(
            session,
            kind=frames_buffer.QUERY_KIND,
            frame=Frame(
                kind="table",
                columns=("symbol", "roe", "roa", "margin"),
                rows=(("STB", 18.5, 1.4, 22.0),),
                unit="%",
                labels={
                    "symbol": "Mã",
                    "roe": "ROE",
                    "roa": "ROA",
                    "margin": "Biên lợi nhuận",
                },
            ),
            provenance=Provenance(
                source="store",
                as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
                sessions_used=1,
                health="normal",
                reason=None,
            ),
            params={"source": "ratio"},
            title="Chỉ số STB",
            turn_id=turn_id,
            thread_id=None,
        )
        session.commit()
    return str(frame_id)


def a_board(series_id: str, table_id: str) -> dict:
    """The smallest board that satisfies every rule, for the tests about one rule."""
    return {
        "title": "Sharpe của STB",
        "archetype": "profile",
        "kpis": [
            {"label": "ROE", "value": {"frame_id": table_id, "column": "roe"}},
            {"label": "ROA", "value": {"frame_id": table_id, "column": "roa"}},
            {"label": "Biên", "value": {"frame_id": table_id, "column": "margin"}},
        ],
        "sections": [
            {
                "heading": "Diễn biến",
                "blocks": [
                    {"kind": "visual", "frame_id": series_id},
                    {"kind": "visual", "frame_id": table_id},
                ],
            }
        ],
    }


def test_a_board_is_compiled_from_the_frames_this_turn_gathered(turn):
    turn_id = turn[0]
    series_id = a_frame_for(turn_id)
    table_id = a_table_for(turn_id)

    answered = render(a_board(series_id, table_id), turn_id=turn_id)

    assert answered["autoComposed"] is False
    assert answered["kpiCount"] == 3

    with get_sync_db() as session:
        row = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(answered["artifactId"])
            )
        ).scalar_one()
        spec = row.signal_desk_spec

    assert spec["specVersion"] == 2
    assert spec["archetype"] == "profile"
    # The figure is stored resolved and formatted: re-opening the board a month
    # later draws the string that was written, not one derived again.
    first = spec["kpis"][0]
    assert first["value"]["text"] == "18,5%"
    assert first["value"]["raw"] == 18.5
    assert first["value"]["row"] == 0
    # The widget is the shape's, not the model's — it named none.
    blocks = spec["sections"][0]["blocks"]
    assert [block["widget"] for block in blocks] == ["line_series", "stat_tiles"]
    assert blocks[0]["options"] == {"x": "session", "y": "value"}
    # Every row of the grid adds to twelve.
    assert sum(block["span"] for block in blocks) == 12
    assert row.frames[blocks[0]["frame"]]["rows"][0] == ["2026-08-19", 1.0]


def test_a_caption_is_stored_resolved_and_a_typed_digit_is_refused(turn):
    turn_id = turn[0]
    series_id = a_frame_for(turn_id)
    table_id = a_table_for(turn_id)

    # Three pictures and one sentence, because the lint floor is seven tenths
    # of the blocks: a board of two charts cannot carry a caption at all, which
    # is a consequence of the threshold rather than of this test.
    second_series = a_frame_for(turn_id)
    board = a_board(series_id, table_id)
    board["sections"] = [
        {
            "heading": "Diễn biến",
            "blocks": [
                {"kind": "visual", "frame_id": series_id},
                {"kind": "visual", "frame_id": second_series},
            ],
        },
        {
            "heading": "Chỉ số",
            "blocks": [
                {"kind": "visual", "frame_id": table_id},
                {
                    "kind": "caption",
                    "template": "ROE đang ở {a}.",
                    "refs": {"a": {"frame_id": table_id, "column": "roe"}},
                },
            ],
        },
    ]
    answered = render(board, turn_id=turn_id)

    with get_sync_db() as session:
        spec = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(answered["artifactId"])
            )
        ).scalar_one().signal_desk_spec
    caption = spec["sections"][1]["blocks"][1]
    assert caption["kind"] == "caption"
    assert caption["text"] == "ROE đang ở 18,5%."
    assert caption["refs"]["a"]["column"] == "roe"

    # The same caption with a year typed into it is the one thing this whole
    # arrangement exists to refuse.
    board["title"] = "Có chữ số"
    board["sections"][1]["blocks"][1]["template"] = "Quý 3 năm 2026: ROE {a}."
    refused = render(board, turn_id=turn_id)

    assert refused["error"] == "board_rejected"
    assert "caption_has_digit" in {
        violation["code"] for violation in refused["violations"]
    }


def test_a_frame_from_another_turn_is_a_named_violation(turn, other_turn):
    turn_id = turn[0]
    table_id = a_table_for(turn_id)
    stranger = a_frame_for(other_turn)

    board = a_board(stranger, table_id)
    answered = render(board, turn_id=turn_id)

    assert answered["error"] == "board_rejected"
    assert "frame_not_available" in {
        violation["code"] for violation in answered["violations"]
    }
    assert answered["unavailableFrames"][0]["frame_id"] == stranger


def test_a_board_that_breaks_a_rule_twice_is_drawn_by_the_server(turn):
    """One round to fix it, and then a board rather than a paragraph.

    One ``StudyTools`` for both calls, because the memory of "this Turn has had
    its round" is on the instance. In the process this runs in there is exactly
    one, built by ``register_study_tools``; a test that built two would be
    testing a deployment that does not exist.
    """
    turn_id = turn[0]
    a_frame_for(turn_id)
    a_table_for(turn_id)
    tools = study_tools.StudyTools()
    context = ToolContext(user_id=1, turn_id=turn_id, thread_id=None)
    # A board with no sections is malformed; one with one KPI is merely wrong,
    # which is the case that gets a round to fix itself.
    wrong = {
        "title": "Thiếu KPI",
        "kpis": [],
        "sections": [{"blocks": [{"kind": "caption", "template": "Không có gì."}]}],
    }

    first = dict(tools.render_signal_desk(context, wrong))
    assert first["error"] == "board_rejected"
    assert "board_missing_kpi_strip" in {
        violation["code"] for violation in first["violations"]
    }

    second = dict(tools.render_signal_desk(context, wrong))
    assert second["autoComposed"] is True
    assert "error" not in second

    with get_sync_db() as session:
        spec = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(second["artifactId"])
            )
        ).scalar_one().signal_desk_spec
    assert spec["autoComposed"] is True
    # The server draws; it never writes a sentence.
    assert all(
        block["kind"] == "visual"
        for section in spec["sections"]
        for block in section["blocks"]
    )


def test_a_turn_may_not_keep_drawing(turn):
    turn_id = turn[0]
    series_id = a_frame_for(turn_id)
    table_id = a_table_for(turn_id)

    for index in range(frames_buffer.MAX_SIGNAL_DESKS_PER_TURN):
        board = a_board(series_id, table_id)
        board["title"] = f"Lần {index}"
        assert render(board, turn_id=turn_id)["kpiCount"] == 3

    board = a_board(series_id, table_id)
    board["title"] = "Lần thừa"
    refused = render(board, turn_id=turn_id)

    assert refused["error"] == "cannot_read"
    assert "already drawn" in refused["detail"]


def test_a_board_may_not_be_longer_than_a_reader_will_read(turn):
    turn_id = turn[0]
    series_id = a_frame_for(turn_id)
    table_id = a_table_for(turn_id)

    board = a_board(series_id, table_id)
    board["sections"] = [
        {"blocks": [{"kind": "visual", "frame_id": series_id}]}
    ] * (grammar.MAX_SECTIONS + 1)
    answered = render(board, turn_id=turn_id)

    assert answered["error"] == "board_rejected"
    codes = {violation["code"] for violation in answered["violations"]}
    assert "sections_over_limit" in codes
    # And the same frame drawn five times is its own violation, so the model is
    # told both things rather than fixing one and meeting the other.
    assert "visual_frame_reused" in codes


def test_a_study_frame_is_addressed_by_name_because_a_study_has_several(turn):
    turn_id = turn[0]
    table_id = a_table_for(turn_id)
    with get_sync_db() as session:
        row = AgentArtifact(
            id=uuid.uuid4(),
            turn_id=turn_id,
            thread_id=None,
            study_name="intraday_liquidity_profile",
            study_version=1,
            params={},
            frames={
                "profile": {
                    "kind": "series",
                    "columns": ["bucket", "share"],
                    "rows": [["09:15", 0.1]],
                    "unit": None,
                    "labels": {"bucket": "Khung giờ", "share": "Tỷ trọng"},
                },
                "ranking": {
                    "kind": "table",
                    "columns": ["bucket", "share"],
                    "rows": [["09:15", 0.1]],
                    "unit": None,
                    "labels": {"bucket": "Khung giờ", "share": "Tỷ trọng"},
                },
            },
            signal_desk_spec={"title": "x", "blocks": []},
            provenance={"source": "store", "asOf": "", "sessionsUsed": 30,
                        "health": "normal", "reason": None},
        )
        session.add(row)
        session.commit()
        artifact_id = str(row.id)

    unnamed = render(a_board(artifact_id, table_id), turn_id=turn_id)
    named = render(a_board(f"{artifact_id}#profile", table_id), turn_id=turn_id)

    assert unnamed["error"] == "board_rejected"
    assert "has to be named" in unnamed["unavailableFrames"][0]["reason"]
    assert named["kpiCount"] == 3

    with get_sync_db() as session:
        session.execute(
            delete(AgentArtifact).where(AgentArtifact.id == uuid.UUID(artifact_id))
        )


# -- the question the whole track exists for -------------------------------


def a_comparison_for(turn_id) -> str:
    """VIC against VCB on four ratios, shaped exactly as ``compare_fields`` files one."""
    with get_sync_db() as session:
        frame_id = frames_buffer.store_frame(
            session,
            kind=frames_buffer.COMPARE_KIND,
            frame=Frame(
                kind="table",
                columns=("symbol", "roe", "roa", "gross_margin", "debt_to_equity"),
                rows=(
                    ("VIC", 4.2, 0.6, 18.4, 2.9),
                    ("VCB", 18.9, 1.8, 42.1, 0.4),
                ),
                unit="%",
                labels={
                    "symbol": "Mã",
                    "roe": "ROE",
                    "roa": "ROA",
                    "gross_margin": "Biên gộp",
                    "debt_to_equity": "Nợ trên vốn",
                },
                cell_roles={
                    (0, "roe"): "loser",
                    (1, "roe"): "winner",
                    (0, "roa"): "loser",
                    (1, "roa"): "winner",
                },
            ),
            provenance=Provenance(
                source="store",
                as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
                sessions_used=2,
                health="normal",
                reason=None,
            ),
            params={"field_ids": ["roe", "roa"], "symbols": ["VIC", "VCB"]},
            title="VIC và VCB",
            turn_id=turn_id,
            thread_id=None,
        )
        session.commit()
    return str(frame_id)


def a_quarter_series_for(turn_id) -> str:
    with get_sync_db() as session:
        frame_id = frames_buffer.store_frame(
            session,
            kind=frames_buffer.QUERY_KIND,
            frame=Frame(
                kind="series",
                columns=("quarter", "vic_profit", "vcb_profit"),
                rows=tuple(
                    (f"2025Q{quarter}", 1.0e12 * quarter, 8.0e12 + 1.0e11 * quarter)
                    for quarter in range(1, 5)
                ),
                unit="VND",
                labels={
                    "quarter": "Quý",
                    "vic_profit": "LNST VIC",
                    "vcb_profit": "LNST VCB",
                },
            ),
            provenance=Provenance(
                source="store",
                as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
                sessions_used=4,
                health="normal",
                reason=None,
            ),
            params={"source": "statement", "symbols": ["VIC", "VCB"]},
            title="LNST theo quý",
            turn_id=turn_id,
            thread_id=None,
        )
        session.commit()
    return str(frame_id)


def test_vic_against_vcb_compiles_into_the_board_the_plan_describes(turn):
    """The example the whole plan was written around, end to end.

    A comparison table with winner and loser cells, the bars beside it, a KPI
    strip of four, one caption — and not one market number typed by the model:
    every figure on this board is a cell reference the server looked up.
    """
    turn_id = turn[0]
    ratios = a_comparison_for(turn_id)
    quarters = a_quarter_series_for(turn_id)

    answered = render(
        {
            "title": "VIC và VCB: nền tảng nào chắc hơn",
            "archetype": "compare",
            "kpis": [
                {
                    "label": "ROE VCB",
                    "value": {"frame_id": ratios, "column": "roe", "row_where": "symbol=VCB"},
                    "role": "winner",
                },
                {
                    "label": "ROE VIC",
                    "value": {"frame_id": ratios, "column": "roe", "row_where": "symbol=VIC"},
                    "role": "loser",
                },
                {
                    "label": "Nợ trên vốn VCB",
                    "value": {
                        "frame_id": ratios,
                        "column": "debt_to_equity",
                        "row_where": "symbol=VCB",
                    },
                },
                {
                    "label": "LNST VCB quý gần nhất",
                    "value": {"frame_id": quarters, "column": "vcb_profit", "row": 3},
                },
            ],
            "sections": [
                {
                    "heading": "Đối chiếu chỉ số",
                    "blocks": [{"kind": "visual", "frame_id": ratios}],
                },
                {
                    "heading": "Lợi nhuận theo quý",
                    "blocks": [
                        {"kind": "visual", "frame_id": quarters},
                        {
                            "kind": "caption",
                            "template": "ROE của VCB là {a} so với {b} của VIC.",
                            "refs": {
                                "a": {
                                    "frame_id": ratios,
                                    "column": "roe",
                                    "row_where": "symbol=VCB",
                                },
                                "b": {
                                    "frame_id": ratios,
                                    "column": "roe",
                                    "row_where": "symbol=VIC",
                                },
                            },
                        },
                    ],
                },
            ],
            "appendix_frame_id": ratios,
        },
        turn_id=turn_id,
    )

    assert "error" not in answered
    assert answered["kpiCount"] == 4
    assert answered["autoComposed"] is False
    assert answered["lint"]["violations"] == []

    with get_sync_db() as session:
        spec = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(answered["artifactId"])
            )
        ).scalar_one().signal_desk_spec

    assert spec["specVersion"] == 2
    assert spec["archetype"] == "compare"

    # A comparison, drawn as one, at the full width of the grid — and the bars
    # beside it, which the model did not ask for. The server adds them because a
    # table is where a reader checks a number and bars are where they see the
    # gap, and neither one does the other's job.
    comparison, companion = spec["sections"][0]["blocks"]
    assert comparison["widget"] == "comparison_table"
    assert comparison["span"] == 12
    assert comparison["options"] == {
        "entity": "symbol",
        "metrics": ["roe", "roa", "gross_margin", "debt_to_equity"],
    }
    assert companion["widget"] == "grouped_bar"
    assert companion["frame"] == comparison["frame"]

    # Four quarters against two measures is two lines: the plan's rule sends a
    # time axis of one or two measures to a line, and a third measure to bars.
    quarterly = spec["sections"][1]["blocks"][0]
    assert quarterly["widget"] == "line_series"

    # Every figure is resolved, formatted, and traceable back to its cell.
    strip = spec["kpis"]
    assert [kpi["value"]["text"] for kpi in strip] == [
        "18,9%",
        "4,2%",
        "0,4%",
        "8,40 nghìn tỷ",
    ]
    assert [kpi["role"] for kpi in strip[:2]] == ["winner", "loser"]
    # Every figure names a frame the row actually carries, so a replay resolves
    # without reaching for anything that is not in front of it.
    assert sum(kpi["span"] for kpi in strip) == 12

    caption = spec["sections"][1]["blocks"][1]
    assert caption["text"] == "ROE của VCB là 18,9% so với 4,2% của VIC."
    # The template keeps its holes, so the panel can mark each figure and say
    # which cell it came from.
    assert "{a}" in caption["template"]
    assert caption["refs"]["a"]["column"] == "roe"

    # The one table on the board is the appendix, at full width.
    assert spec["appendix"]["widget"] == "data_table"
    assert spec["appendix"]["span"] == 12

    # And the cell roles the comparison declared survive into the row the panel
    # draws from: the winner mark is the engine's claim, not the browser's.
    with get_sync_db() as session:
        frames = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(answered["artifactId"])
            )
        ).scalar_one().frames
    drawn = frames[comparison["frame"]]
    assert {"row": 1, "column": "roe", "role": "winner"} in drawn["cellRoles"]
    assert {kpi["value"]["frame"] for kpi in strip} <= set(frames)
