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
from src.studies import frames_buffer
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


def test_a_signal_desk_is_composed_from_the_frames_this_turn_gathered(turn):
    turn_id = turn[0]
    frame_id = a_frame_for(turn_id)

    answered = render(
        {
            "title": "Sharpe của STB",
            "blocks": [{"widget": "line_series", "frame_id": frame_id}],
        },
        turn_id=turn_id,
    )

    assert answered["blockCount"] == 1
    assert answered["dropped"] == []
    with get_sync_db() as session:
        row = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(answered["artifactId"])
            )
        ).scalar_one()
        block = row.signal_desk_spec["blocks"][0]
        # The version and the presentation are the server's, not the model's: a
        # version is how an old artifact keeps rendering, and which column is
        # the line is a claim about the numbers.
        assert block["widgetVersion"] == 1
        assert block["options"] == {"x": "session", "y": "value"}
        assert row.frames[block["frame"]]["rows"][0] == ["2026-08-19", 1.0]


def test_a_frame_from_another_turn_draws_nothing(turn, other_turn):
    frame_id = a_frame_for(other_turn)

    answered = render(
        {"title": "Của người khác", "blocks": [{"widget": "line_series", "frame_id": frame_id}]},
        turn_id=turn[0],
    )

    assert answered["error"] == "cannot_read"
    assert "not a frame id this turn produced" in answered["dropped"][0]["reason"]


def test_a_block_that_cannot_be_drawn_costs_one_block_and_not_the_signal_desk(
    turn, other_turn
):
    turn_id = turn[0]
    good = a_frame_for(turn_id)
    stranger = a_frame_for(other_turn)

    answered = render(
        {
            "title": "Một khối hỏng",
            "blocks": [
                {"widget": "line_series", "frame_id": good},
                {"widget": "session_heatmap", "frame_id": good},
                {"widget": "line_series", "frame_id": stranger},
            ],
        },
        turn_id=turn_id,
    )

    assert answered["blockCount"] == 1
    reasons = " ".join(entry["reason"] for entry in answered["dropped"])
    # Both refusals name what was wrong, so the model can fix them next round.
    assert "cannot draw a series frame" in reasons
    assert "not a frame id this turn produced" in reasons


def test_a_turn_may_not_keep_drawing(turn):
    turn_id = turn[0]
    frame_id = a_frame_for(turn_id)
    block = {"widget": "line_series", "frame_id": frame_id}

    for index in range(frames_buffer.MAX_SIGNAL_DESKS_PER_TURN):
        assert render({"title": f"Lần {index}", "blocks": [block]}, turn_id=turn_id)[
            "blockCount"
        ] == 1

    refused = render({"title": "Lần thừa", "blocks": [block]}, turn_id=turn_id)

    assert refused["error"] == "cannot_read"
    assert "already drawn" in refused["detail"]


def test_a_signal_desk_may_not_be_longer_than_a_reader_will_read(turn):
    turn_id = turn[0]
    frame_id = a_frame_for(turn_id)
    block = {"widget": "line_series", "frame_id": frame_id}

    with pytest.raises(ValueError, match="at most"):
        render(
            {
                "title": "Quá dài",
                "blocks": [block] * (frames_buffer.MAX_BLOCKS + 1),
            },
            turn_id=turn_id,
        )


def test_a_study_frame_is_addressed_by_name_because_a_study_has_several(turn):
    turn_id = turn[0]
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
            provenance={"source": "vnstock", "asOf": "", "sessionsUsed": 30,
                        "health": "normal", "reason": None},
        )
        session.add(row)
        session.commit()
        artifact_id = str(row.id)

    unnamed = render(
        {"title": "Không nêu tên", "blocks": [{"widget": "line_series", "frame_id": artifact_id}]},
        turn_id=turn_id,
    )
    named = render(
        {
            "title": "Có nêu tên",
            "blocks": [{"widget": "line_series", "frame_id": f"{artifact_id}#profile"}],
        },
        turn_id=turn_id,
    )

    assert unnamed["error"] == "cannot_read"
    assert "has to be named" in unnamed["dropped"][0]["reason"]
    assert named["blockCount"] == 1

    with get_sync_db() as session:
        session.execute(
            delete(AgentArtifact).where(AgentArtifact.id == uuid.UUID(artifact_id))
        )
