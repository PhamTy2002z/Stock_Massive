"""The one tool that lets a model write numbers, and the checks that make it safe.

Every other frame is built by the engine out of the store, and the reason this
one exists is that some questions have no number in the store. The reason it is
*allowed* to exist is that every row is checked against the page — and the check
is against the Tool Call Trace rather than against a fresh fetch, because the
trace holds what the model actually saw and a second fetch could return
something else.

Against a live database, like the other tool tests here: the whole mechanism is
a join from the Turn to the trace, and a stubbed store would let a broken join
pass.
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
from src.agent.tools import evidence as evidence_tools
from src.alpha.models import (
    TOOL_CALL_OK,
    AgentArtifact,
    AgentMessage,
    AgentThread,
    AgentToolCall,
    AgentTurn,
)
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine
from src.studies import frames_buffer

PAGE_URL = "https://www.example.com/bao-cao-quy-2/"
PAGE_TEXT = (
    "Lợi nhuận quý II đạt 3,2 nghìn tỷ đồng, tăng 12,5% so với cùng kỳ. "
    "Ngân hàng mở thêm 5 chi nhánh và giữ nợ xấu ở 1,02%."
)


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def turn():
    email = f"evidence-{uuid.uuid4().hex[:12]}@example.com"
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
            status="running",
        )
        session.add(row)
        session.commit()
        made = (row.id, thread.id, user.id, message.id)

    yield made

    with get_sync_db() as session:
        session.execute(
            delete(AgentToolCall).where(AgentToolCall.thread_id == made[1])
        )
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


def a_fetch(
    turn,
    *,
    url: str = PAGE_URL,
    text: str = PAGE_TEXT,
    status: str = TOOL_CALL_OK,
    reason: str | None = None,
    started_at: datetime | None = None,
) -> None:
    """One ``fetch_url`` row, written exactly the way the loop writes them.

    Exactly the way, and it matters: the loop stores the result as one JSON
    string under ``text`` — what the model read — rather than as the mapping the
    handler returned. A fixture that stored the mapping would be testing a
    reading path that does not exist.
    """
    _turn_id, thread_id, _user_id, request_message_id = turn
    payload = {
        "url": url,
        "title": "Báo cáo quý II",
        "content": text,
        "reason": reason,
        "retrieved_at": "2026-08-29T10:15:00+00:00",
    }
    with get_sync_db() as session:
        session.add(
            AgentToolCall(
                thread_id=thread_id,
                request_message_id=request_message_id,
                tool_name="fetch_url",
                tool_call_id=uuid.uuid4().hex[:16],
                arguments={"url": url},
                result={"text": json.dumps(payload, ensure_ascii=False)},
                status=status,
                started_at=started_at or datetime(2026, 8, 29, 10, 15, tzinfo=timezone.utc),
            )
        )
        session.commit()


ROWS = [
    {"label": "Lợi nhuận quý II", "value": 3.2, "unit": "nghìn tỷ"},
    {"label": "Tăng trưởng", "value": 12.5, "unit": "%"},
]


# -- the page has to be one this Turn read -------------------------------------


def test_a_url_this_turn_never_fetched_is_refused_and_writes_no_frame(turn):
    turn_id, thread_id, _user_id, _message_id = turn

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id), {"url": PAGE_URL, "rows": ROWS}
    )

    assert answer["error"] == evidence_tools.PAGE_NOT_FETCHED
    with get_sync_db() as session:
        assert (
            session.query(AgentArtifact)
            .filter(AgentArtifact.thread_id == thread_id)
            .count()
            == 0
        )


def test_a_page_another_turn_read_is_not_evidence_for_this_one(turn):
    """A URL fetched in some other conversation is not this answer's evidence."""
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(uuid.uuid4(), thread_id), {"url": PAGE_URL, "rows": ROWS}
    )

    assert answer["error"] == evidence_tools.PAGE_NOT_FETCHED


def test_a_fetch_that_failed_is_not_a_page(turn):
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn, status="error")

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id), {"url": PAGE_URL, "rows": ROWS}
    )

    assert answer["error"] == evidence_tools.PAGE_NOT_FETCHED


def test_a_fetch_that_came_back_unavailable_is_not_a_page_either(turn):
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn, text="", reason="web_unavailable")

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id), {"url": PAGE_URL, "rows": ROWS}
    )

    assert answer["error"] == evidence_tools.PAGE_NOT_FETCHED


def test_the_url_is_matched_the_way_the_source_rail_matches_one(turn):
    """A link retyped without ``www.`` still finds the page it was read from.

    Comparison only: what the frame records is the URL the fetch returned, so a
    reader clicking it gets the page rather than a normalised guess at it.
    """
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id),
        {"url": "http://example.com/bao-cao-quy-2", "rows": ROWS},
    )

    assert answer["matched"] == 2
    assert answer["url"] == PAGE_URL


def test_the_page_read_last_is_the_one_checked_against(turn):
    """A page fetched twice in one Turn is the same page, later read winning."""
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(
        turn,
        text="Không có con số nào ở đây.",
        started_at=datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc),
    )
    a_fetch(turn, started_at=datetime(2026, 8, 29, 11, 0, tzinfo=timezone.utc))

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id), {"url": PAGE_URL, "rows": ROWS}
    )

    assert answer["matched"] == 2


# -- every row has to be on it -------------------------------------------------


def test_a_row_whose_number_is_on_the_page_is_kept(turn):
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id),
        {"url": PAGE_URL, "rows": ROWS, "caption": "Kết quả quý II"},
    )

    assert answer["matched"] == 2
    assert answer["refusedCount"] == 0
    assert answer["health"] == "normal"
    with get_sync_db() as session:
        row = session.get(AgentArtifact, uuid.UUID(answer["frameId"]))
    assert row.frames["frame"]["columns"] == ["label", "value"]
    assert row.frames["frame"]["rows"] == [
        ["Lợi nhuận quý II", 3.2],
        ["Tăng trưởng", 12.5],
    ]
    assert row.params["caption"] == "Kết quả quý II"


def test_a_row_whose_number_is_not_on_the_page_is_dropped_and_named(turn):
    """The whole point: a figure the model invented does not become a picture."""
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id),
        {
            "url": PAGE_URL,
            "rows": [
                {"label": "Tăng trưởng", "value": 12.5, "unit": "%"},
                {"label": "Biên lãi ròng", "value": 13, "unit": "%"},
            ],
        },
    )

    assert answer["matched"] == 1
    assert answer["refused"] == [
        {"label": "Biên lãi ròng", "reason": evidence_tools.NOT_ON_PAGE}
    ]
    # A frame that dropped a row is thinner than one that did not, and the strip
    # a reader sees has to say so.
    assert answer["health"] == "degraded"


def test_a_round_number_with_no_unit_is_dropped_under_its_own_name(turn):
    """Absent and indistinguishable are different facts and get different names."""
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id),
        {
            "url": PAGE_URL,
            "rows": [
                {"label": "Tăng trưởng", "value": 12.5, "unit": "%"},
                {"label": "Chi nhánh mới", "value": 5},
            ],
        },
    )

    assert answer["refused"] == [
        {"label": "Chi nhánh mới", "reason": evidence_tools.AMBIGUOUS}
    ]


def test_a_frame_where_nothing_matched_is_no_frame_at_all(turn):
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id),
        {"url": PAGE_URL, "rows": [{"label": "Bịa", "value": 987.65, "unit": "%"}]},
    )

    assert answer["error"] == evidence_tools.NOTHING_MATCHED
    with get_sync_db() as session:
        assert (
            session.query(AgentArtifact)
            .filter(AgentArtifact.thread_id == thread_id)
            .count()
            == 0
        )


def test_more_rows_than_a_reader_can_check_by_eye_is_refused_at_the_boundary(turn):
    turn_id, thread_id, _user_id, _message_id = turn

    with pytest.raises(ValueError, match="at most"):
        evidence_tools.EvidenceTool().frame_from_evidence(
            a_context(turn_id, thread_id),
            {
                "url": PAGE_URL,
                "rows": [{"label": "x", "value": 1.0}]
                * (evidence_tools.MAX_EVIDENCE_ROWS + 1),
            },
        )


# -- what the frame says about itself ------------------------------------------


def test_the_frame_says_it_is_web_and_never_says_it_is_the_store(turn):
    """A number this deployment measured and one it copied are different claims.

    ``source`` is a closed vocabulary precisely so the badge beside a figure is
    a decision the engine took rather than a string the browser guesses at.
    """
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id), {"url": PAGE_URL, "rows": ROWS}
    )

    with get_sync_db() as session:
        row = session.get(AgentArtifact, uuid.UUID(answer["frameId"]))

    assert row.provenance["source"] == "web"
    assert row.provenance["query"]["url"] == PAGE_URL
    assert row.study_name == frames_buffer.EVIDENCE_KIND


def test_the_frame_is_frozen_at_the_day_the_page_was_read(turn):
    """A figure published on a page is a fact about that day, not that minute."""
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id), {"url": PAGE_URL, "rows": ROWS}
    )

    assert answer["asOf"] == "2026-08-29"


def test_rows_in_one_unit_give_the_frame_that_unit_and_mixed_rows_give_none(turn):
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)
    tool = evidence_tools.EvidenceTool()
    context = a_context(turn_id, thread_id)

    same = tool.frame_from_evidence(
        context,
        {
            "url": PAGE_URL,
            "rows": [
                {"label": "Tăng trưởng", "value": 12.5, "unit": "%"},
                {"label": "Nợ xấu", "value": 1.02, "unit": "%"},
            ],
        },
    )
    mixed = tool.frame_from_evidence(context, {"url": PAGE_URL, "rows": ROWS})

    assert same["unit"] == "%"
    assert mixed["unit"] is None


# -- the calculation axis reads it ---------------------------------------------


def test_a_calculation_may_take_an_evidence_frame_and_says_that_it_did(turn):
    """A derived number is no better than the page it rests on, and says so."""
    from src.agent.tools import compute as compute_tools

    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn)
    context = a_context(turn_id, thread_id)

    evidence = evidence_tools.EvidenceTool().frame_from_evidence(
        context,
        {
            "url": PAGE_URL,
            "rows": [
                {"label": "Tăng trưởng", "value": 12.5, "unit": "%"},
                {"label": "Nợ xấu", "value": 1.02, "unit": "%"},
            ],
        },
    )
    derived = compute_tools.ComputeTool().compute(
        context,
        {
            "code": "result = (f0['value'] / 100).to_frame(name='ratio')",
            "inputs": [evidence["frameId"]],
        },
    )

    with get_sync_db() as session:
        row = session.get(AgentArtifact, uuid.UUID(derived["frameId"]))

    assert row.provenance["source"] == "derived"
    assert any("trang đã đọc" in note for note in row.provenance["methodNotes"])


# -- the transcript ------------------------------------------------------------


def test_the_frame_does_not_reach_a_message(turn):
    turn_id, thread_id, _user_id, _message_id = turn
    a_fetch(turn, text="Tổng tài sản 987654321 đồng trong kỳ.")

    answer = evidence_tools.EvidenceTool().frame_from_evidence(
        a_context(turn_id, thread_id),
        {
            "url": PAGE_URL,
            "rows": [{"label": "Tổng tài sản", "value": 987654321, "unit": "đồng"}],
        },
    )

    call = TurnToolCall(
        id="call-1",
        name="frame_from_evidence",
        arguments={"url": PAGE_URL, "rows": []},
        status=ToolCallStatus.OK,
        result_text=json.dumps(answer, ensure_ascii=False),
        summary="Lấy 1 số từ example.com",
    )
    built = build_messages(
        Transcript(
            system_prompt="hệ thống",
            turns=(TranscriptTurn(user_text="Tổng tài sản?", tool_calls=(call,)),),
        ),
        ContextBudget(),
    )

    whole = "\n".join(str(message.content or "") for message in built.messages)
    assert "987654321" not in whole
    assert answer["frameId"] in whole


def test_the_tool_is_offered_to_a_conversation():
    from src.agent.toolsets import CHAT_TOOLSETS, resolve_toolset

    assert "frame_from_evidence" in resolve_toolset(CHAT_TOOLSETS)
