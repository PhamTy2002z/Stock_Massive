"""The calculation tool, and the four promises it is the enforcement of.

**No number the model typed reaches a frame.** The validator is where that is
decided and ``tests/studies/test_compute_validator.py`` is where it is proven;
what is proven here is that the tool actually runs it, and answers a rejection
in a shape the model can rewrite from rather than as a failure.

**A frame is owned by the Turn that made it.** A calculation reading a frame id
from another conversation would be a route into somebody else's numbers, so the
ownership check is the same one ``read_frame`` already holds and it is asserted
against a real database rather than a stub.

**Numbers do not come back.** The answer is a shape and a range, and the
transcript a Turn would send carries neither the cells nor anything derived from
them — asserted on the transcript, because a clean payload and a clean
transcript are two different claims.

**The same inputs give the same frame.** Re-opening a thread renders the stored
artifact; the ``params`` carry the code so the frame can be rebuilt and checked,
and a calculation that was not deterministic would make that check meaningless.

Against a live database on ``tests/test_agent_query_tools.py``'s reasoning: the
tool writes a row through an ownership join, and a fake store would let a broken
one pass.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

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
from src.agent.tools import compute as compute_tools
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
    """A real Thread and Turn, because ``agent_artifact`` points at both."""
    email = f"compute-{uuid.uuid4().hex[:12]}@example.com"
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
        now=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc),
    )


QUARTERS = Frame(
    kind="table",
    columns=("period", "symbol", "net_profit", "equity"),
    rows=(
        ("2025-Q1", "VIC", 1_000.0, 20_000.0),
        ("2025-Q2", "VIC", 1_200.0, 20_500.0),
        ("2025-Q1", "VCB", 8_000.0, 90_000.0),
        ("2025-Q2", "VCB", 8_400.0, 92_000.0),
    ),
    unit="vnd",
    labels={
        "period": "Quý",
        "symbol": "Mã",
        "net_profit": "Lợi nhuận sau thuế",
        "equity": "Vốn chủ sở hữu",
    },
)


def a_frame(context, frame=QUARTERS, *, as_of=None, source="store", health="normal"):
    """One stored frame this Turn owns, and the id that addresses it."""
    with get_sync_db() as session:
        frame_id = frames_buffer.store_frame(
            session,
            kind=frames_buffer.QUERY_KIND,
            frame=frame,
            provenance=Provenance(
                source=source,
                as_of=as_of or datetime(2026, 8, 30, tzinfo=timezone.utc),
                sessions_used=len(frame.rows),
                health=health,
                reason=None if health == "normal" else "hai ô không có số",
            ),
            params={"source": "statement"},
            title="Báo cáo tài chính",
            turn_id=context.turn_id,
            thread_id=context.thread_id,
        )
        session.commit()
    return str(frame_id)


# -- the invariant -------------------------------------------------------------


def test_a_figure_typed_into_the_code_is_refused_with_every_reason_at_once(turn):
    """Refused, and refused as something to rewrite rather than as a failure.

    The loop counts a tool failure towards halting the Turn. A calculation the
    model can fix on the next round is not one of those, so the refusal comes
    back as a result.
    """
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    answer = compute_tools.ComputeTool().compute(
        context,
        {"code": "result = f0['net_profit'] * 0.07", "inputs": [frame_id]},
    )

    assert answer["error"] == "compute_literal_number"
    assert answer["rejected"] == compute_tools.REJECTED
    assert answer["violations"][0]["line"] == 1
    assert "frameId" not in answer


def test_a_declared_constant_lets_the_same_figure_through_and_is_recorded(turn):
    """The door, and the reason it is not a hole.

    A constant differs from a literal by exactly one thing: somebody said why.
    So the reason is stored on the artifact and the summary says the picture
    rests on an assumption.
    """
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    answer = compute_tools.ComputeTool().compute(
        context,
        {
            "code": "result = (f0['net_profit'] * tax).to_frame(name='after_tax')",
            "inputs": [frame_id],
            "constants": {"tax": {"value": 0.8, "reason": "thuế suất giả định 20%"}},
        },
    )

    assert answer["hasConstants"] is True
    with get_sync_db() as session:
        row = session.get(AgentArtifact, uuid.UUID(answer["frameId"]))
        assert row.params["constants"]["tax"] == {
            "value": 0.8,
            "reason": "thuế suất giả định 20%",
        }


def test_a_constant_with_no_reason_is_a_literal_that_found_a_way_in(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    with pytest.raises(ValueError, match="needs a reason"):
        compute_tools.ComputeTool().compute(
            context,
            {
                "code": "result = f0 * tax",
                "inputs": [frame_id],
                "constants": {"tax": {"value": 0.8}},
            },
        )


# -- ownership -----------------------------------------------------------------


def test_a_frame_from_another_turn_is_refused_as_though_it_were_not_there(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    answer = compute_tools.ComputeTool().compute(
        a_context(uuid.uuid4(), thread_id),
        {"code": "result = f0", "inputs": [frame_id]},
    )

    assert answer["error"] == compute_tools.INPUT_NOT_AVAILABLE


def test_a_frame_id_nobody_ever_wrote_is_refused_the_same_way(turn):
    turn_id, thread_id, _ = turn

    answer = compute_tools.ComputeTool().compute(
        a_context(turn_id, thread_id),
        {"code": "result = f0", "inputs": [str(uuid.uuid4())]},
    )

    assert answer["error"] == compute_tools.INPUT_NOT_AVAILABLE


# -- what comes back -----------------------------------------------------------


def test_the_answer_is_a_shape_and_a_range_rather_than_the_numbers(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    answer = compute_tools.ComputeTool().compute(
        context,
        {
            "code": (
                "roe = f0['net_profit'] / f0['equity'] * 100\n"
                "result = f0[['period', 'symbol']].assign(roe=roe)"
            ),
            "inputs": [frame_id],
        },
    )

    assert answer["rows"] == 4
    assert answer["columnCount"] == 3
    assert answer["computesLeft"] == compute_tools.MAX_COMPUTE_PER_TURN - 1
    ranges = {entry["column"]: entry for entry in answer["columnRanges"]}
    assert ranges["roe"]["answered"] == 4
    assert ranges["roe"]["min"] == pytest.approx(5.0)


def test_a_column_the_calculation_kept_keeps_its_vietnamese_heading(turn):
    """A table of ratios should not lose its labels by being divided by another."""
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    answer = compute_tools.ComputeTool().compute(
        context,
        {"code": "result = f0[['symbol', 'net_profit']]", "inputs": [frame_id]},
    )

    labels = {entry["name"]: entry["label"] for entry in answer["columnSample"]}
    assert labels["net_profit"] == "Lợi nhuận sau thuế"


def test_a_comparison_marks_the_winner_and_it_reaches_the_stored_frame(turn):
    """The acceptance shape of this phase: VIC against VCB on a derived figure.

    The role is set by the calculation, because only the layer that computed the
    number knows which way is better — and a role invented at the far end of the
    wire would be the browser interpreting a number.
    """
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    answer = compute_tools.ComputeTool().compute(
        context,
        {
            "code": (
                "roe = (f0['net_profit'] / f0['equity'] * 100)\n"
                "table = f0[['symbol']].assign(roe=roe)\n"
                "table = table.groupby('symbol', as_index=False)['roe'].mean()\n"
                "best = table['roe'].idxmax()\n"
                "worst = table['roe'].idxmin()\n"
                "table.attrs['cell_roles'] = [\n"
                "    (int(best), 'roe', 'winner'),\n"
                "    (int(worst), 'roe', 'loser'),\n"
                "]\n"
                "result = table"
            ),
            "inputs": [frame_id],
        },
    )

    with get_sync_db() as session:
        row = session.get(AgentArtifact, uuid.UUID(answer["frameId"]))
        roles = row.frames["frame"]["cellRoles"]

    assert {entry["role"] for entry in roles} == {"winner", "loser"}
    assert all(entry["column"] == "roe" for entry in roles)


def test_a_role_naming_a_row_that_is_not_there_is_a_named_answer(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    answer = compute_tools.ComputeTool().compute(
        context,
        {
            "code": (
                "result = f0[['symbol']]\n"
                "result.attrs['cell_roles'] = [(12, 'symbol', 'winner')]"
            ),
            "inputs": [frame_id],
        },
    )

    assert answer["error"] == "compute_invalid_result"


# -- provenance ----------------------------------------------------------------


def test_a_derived_frame_is_as_old_as_its_oldest_input(turn):
    """A number computed from last Tuesday's frame is a number from last Tuesday."""
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    old = a_frame(context, as_of=datetime(2026, 8, 20, tzinfo=timezone.utc))
    fresh = a_frame(context, as_of=datetime(2026, 8, 30, tzinfo=timezone.utc))

    answer = compute_tools.ComputeTool().compute(
        context,
        {"code": "result = pd.concat([f0, f1])[['symbol']]", "inputs": [fresh, old]},
    )

    assert answer["asOf"].startswith("2026-08-20")


def test_a_derived_frame_is_no_healthier_than_the_thinnest_thing_it_used(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    thin = a_frame(context, health="degraded")

    answer = compute_tools.ComputeTool().compute(
        context, {"code": "result = f0[['symbol']]", "inputs": [thin]}
    )

    assert answer["health"] == "degraded"


def test_a_derived_frame_says_it_is_derived_and_never_says_it_is_the_store(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)

    answer = compute_tools.ComputeTool().compute(
        context, {"code": "result = f0[['symbol']]", "inputs": [frame_id]}
    )

    with get_sync_db() as session:
        row = session.get(AgentArtifact, uuid.UUID(answer["frameId"]))

    assert row.provenance["source"] == "derived"
    assert row.study_name == frames_buffer.COMPUTE_KIND


# -- the ceilings --------------------------------------------------------------


def test_a_turn_runs_out_of_calculations_before_it_runs_out_of_rounds(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)
    tool = compute_tools.ComputeTool()

    for _ in range(compute_tools.MAX_COMPUTE_PER_TURN):
        assert "frameId" in tool.compute(
            context, {"code": "result = f0[['symbol']]", "inputs": [frame_id]}
        )

    refused = tool.compute(
        context, {"code": "result = f0[['symbol']]", "inputs": [frame_id]}
    )

    assert refused["error"] == compute_tools.TOO_MANY


def test_more_inputs_than_a_calculation_may_read_is_refused_at_the_boundary(turn):
    turn_id, thread_id, _ = turn

    with pytest.raises(ValueError, match="at most"):
        compute_tools.ComputeTool().compute(
            a_context(turn_id, thread_id),
            {
                "code": "result = f0",
                "inputs": [str(uuid.uuid4())] * (compute_tools.MAX_INPUTS + 1),
            },
        )


# -- replay --------------------------------------------------------------------


def test_the_same_calculation_twice_stores_frames_that_match_byte_for_byte(turn):
    """The artifact's promise: re-opening a thread renders rather than recomputes.

    The stored ``params`` carry the code so the frame can be rebuilt and checked
    against what was served — which is only worth anything if rebuilding it gives
    the same bytes.
    """
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)
    tool = compute_tools.ComputeTool()
    code = "result = (f0['net_profit'] / f0['equity']).to_frame(name='roe')"

    first = tool.compute(context, {"code": code, "inputs": [frame_id]})
    second = tool.compute(context, {"code": code, "inputs": [frame_id]})

    with get_sync_db() as session:
        one = session.get(AgentArtifact, uuid.UUID(first["frameId"]))
        two = session.get(AgentArtifact, uuid.UUID(second["frameId"]))
        assert one.frames == two.frames
        assert one.params["code_digest"] == two.params["code_digest"]


def test_changing_one_declared_constant_changes_the_frame_and_the_record(turn):
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(context)
    tool = compute_tools.ComputeTool()
    code = "result = (f0['net_profit'] * rate).to_frame(name='scaled')"

    first = tool.compute(
        context,
        {
            "code": code,
            "inputs": [frame_id],
            "constants": {"rate": {"value": 0.8, "reason": "giả định thứ nhất"}},
        },
    )
    second = tool.compute(
        context,
        {
            "code": code,
            "inputs": [frame_id],
            "constants": {"rate": {"value": 0.9, "reason": "giả định thứ hai"}},
        },
    )

    with get_sync_db() as session:
        one = session.get(AgentArtifact, uuid.UUID(first["frameId"]))
        two = session.get(AgentArtifact, uuid.UUID(second["frameId"]))
        assert one.frames != two.frames
        assert one.params["constants"] != two.params["constants"]


# -- the transcript ------------------------------------------------------------


def test_the_cells_a_calculation_produced_do_not_reach_a_message(turn):
    """Asserted on the transcript, because that is where the promise is made.

    What the summary *does* carry is the range of each numeric column — the same
    thing ``get_series`` has always returned, and the reason the model can tell
    an arithmetic mistake from an answer. So the assertion is not "no number
    reaches a message"; it is that the summary is a fixed size whatever the
    frame's height, and that the cells between the extremes are not in it.
    """
    turn_id, thread_id, _ = turn
    context = a_context(turn_id, thread_id)
    frame_id = a_frame(
        context,
        Frame(
            kind="table",
            columns=("symbol", "value"),
            rows=tuple(
                (f"S{index:02d}", float(313_131_000 + index * 1_000))
                for index in range(30)
            ),
            unit="vnd",
            labels={"symbol": "Mã", "value": "Giá trị"},
        ),
    )

    answer = compute_tools.ComputeTool().compute(
        context,
        {"code": "result = f0[['symbol', 'value']]", "inputs": [frame_id]},
    )

    call = TurnToolCall(
        id="call-1",
        name="compute",
        arguments={"code": "result = f0", "inputs": [frame_id]},
        status=ToolCallStatus.OK,
        result_text=json.dumps(answer, ensure_ascii=False),
        summary="Tính trên 1 bảng số",
    )
    built = build_messages(
        Transcript(
            system_prompt="hệ thống",
            turns=(TranscriptTurn(user_text="Mã nào lớn nhất?", tool_calls=(call,)),),
        ),
        ContextBudget(),
    )

    whole = "\n".join(str(message.content or "") for message in built.messages)
    # The fifteenth row is neither the smallest nor the largest, so nothing in a
    # summary has any reason to hold it.
    assert "313146000" not in whole
    assert "S15" not in whole
    # The extremes are there, deliberately, and so is the only thing that draws.
    assert "313131000" in whole
    assert answer["frameId"] in whole


def test_the_tool_is_offered_to_a_conversation():
    from src.agent.toolsets import CHAT_TOOLSETS, resolve_toolset

    assert "compute" in resolve_toolset(CHAT_TOOLSETS)
