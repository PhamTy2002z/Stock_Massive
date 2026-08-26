"""The two tools that reach a Study, and the one law they exist to keep.

The law is that ``frames`` — the matrix a picture is drawn from — never enters a
message. It is asserted twice here on purpose: once against what the handler
answers with, and once against the messages a Turn would actually send, because
a payload that is clean and a transcript that is clean are two different claims
and only the second one is the promise.

Against a live database, like ``tests/studies/test_runner.py`` and for the same
reason: the run writes a row and the endpoint that serves it reads through an
ownership join, and a fake store would let both pass while the real one refused.
"""

from __future__ import annotations

import json
import uuid

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from src.agent.messages import (
    ContextBudget,
    ToolCallStatus,
    Transcript,
    TranscriptTurn,
    TurnToolCall,
    build_messages,
    canvas_of,
    outcome_of,
)
from src.agent.registry import ToolContext
from src.agent.tools import studies as study_tools
from src.alpha.models import AgentArtifact
from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.signals.issues import SignalIssue
from src.studies import registry as study_registry, warmup
from src.studies.contracts import (
    CanvasBlock,
    CanvasSpec,
    Frame,
    Provenance,
    StudyDefinition,
    StudyRefused,
    StudyResult,
)

STUDY = "tools_liquidity"


class Params(BaseModel):
    symbol: str = Field(description="Mã chứng khoán")
    sessions: int = Field(default=30, ge=10, le=60, description="Số phiên")


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def only_this_files_catalog():
    """A Study catalog holding nothing but what this file registers.

    The catalog is process-wide, and the tool's own schema is built from it, so
    a test asserting on the enum of names has to own the whole list.
    """
    saved = dict(study_registry.REGISTRY)
    study_registry.REGISTRY.clear()
    yield
    study_registry.REGISTRY.clear()
    study_registry.REGISTRY.update(saved)


@pytest.fixture(autouse=True)
def no_leftover_rows():
    yield
    with get_sync_db() as session:
        session.execute(
            delete(AgentArtifact).where(AgentArtifact.study_name.like("tools_%"))
        )


def a_result(context) -> StudyResult:
    return StudyResult(
        headline={
            "symbol": context.params.symbol,
            "sessionsUsed": context.params.sessions,
            "peakWindow": "14:45",
        },
        frames={
            "profile": Frame(
                kind="series",
                columns=("bucket", "avg_volume"),
                rows=(("09:15", 1_000), ("14:45", 4_242_424)),
                unit="shares",
                labels={"bucket": "Khung giờ", "avg_volume": "KL trung bình"},
            )
        },
        provenance=Provenance(
            source="vnstock",
            as_of=context.as_of,
            sessions_used=context.params.sessions,
            health="normal",
            reason=None,
        ),
    )


def a_canvas(_result: StudyResult) -> CanvasSpec:
    return CanvasSpec(
        title="Thanh khoản trong phiên — STB",
        blocks=(
            CanvasBlock(
                widget="bar_series",
                widget_version=1,
                frame="profile",
                options={"x": "bucket", "y": "avg_volume"},
            ),
        ),
    )


def register(name: str = STUDY, **overrides) -> StudyDefinition:
    fields = {
        "name": name,
        "version": 1,
        "question": "Thanh khoản tập trung ở khung giờ nào?",
        "display_name": "Thanh khoản trong phiên",
        "params_model": Params,
        "requires": (),
        "frames": ("profile",),
        "widgets": (("bar_series", 1),),
        "compute": a_result,
        "view": a_canvas,
    }
    fields.update(overrides)
    return study_registry.register(StudyDefinition(**fields))


def run(arguments: dict, *, turn_id=None, thread_id=None) -> dict:
    tools = study_tools.StudyTools()
    return dict(
        tools.run_study(
            ToolContext(user_id=1, turn_id=turn_id, thread_id=thread_id),
            arguments,
        )
    )


# -- what the model is handed ---------------------------------------------


def test_the_model_is_handed_a_headline_and_an_id_and_never_the_frames():
    register()

    answered = run({"name": STUDY, "symbol": "STB"})

    assert set(answered) == {
        "studyName",
        "studyVersion",
        "artifactId",
        "title",
        "blockCount",
        "headline",
        "provenance",
    }
    assert answered["headline"]["peakWindow"] == "14:45"
    assert answered["blockCount"] == 1
    # Not "frames is absent" but "no cell of any frame is reachable": a payload
    # that carried them under another name would pass the first check.
    wire = json.dumps(answered, ensure_ascii=False)
    assert "4242424" not in wire.replace(".0", "")
    assert "profile" not in wire


def test_the_frames_are_absent_from_the_messages_a_turn_would_send():
    """The law itself, read off the transcript rather than off the payload.

    ``result_text`` is what the executor normalises the handler's answer into
    and what the model actually reads, so this is the assertion that would fail
    if a later change put a frame in the payload "just for the model to check".
    """
    register()
    answered = run({"name": STUDY, "symbol": "STB"})

    call = TurnToolCall(
        id="call-1",
        name="run_study",
        arguments={"name": STUDY, "symbol": "STB"},
        status=ToolCallStatus.OK,
        result_text=json.dumps(answered, ensure_ascii=False),
        summary="Thanh khoản trong phiên: STB",
    )
    context = build_messages(
        Transcript(
            system_prompt="hệ thống",
            turns=(TranscriptTurn(user_text="Thanh khoản STB?", tool_calls=(call,)),),
        ),
        ContextBudget(),
    )

    whole = "\n".join(str(message.content or "") for message in context.messages)
    assert "4242424" not in whole.replace(".0", "")
    assert "avg_volume" not in whole
    assert answered["artifactId"] in whole


def test_the_row_holds_the_numbers_the_message_does_not():
    register()

    answered = run({"name": STUDY, "symbol": "STB"})

    with get_sync_db() as session:
        row = session.execute(
            select(AgentArtifact).where(
                AgentArtifact.id == uuid.UUID(answered["artifactId"])
            )
        ).scalar_one()
        assert row.frames["profile"]["rows"] == [["09:15", 1000], ["14:45", 4242424]]
        assert row.canvas_spec["title"] == answered["title"]


def test_the_run_is_owned_by_the_context_and_never_by_an_argument(monkeypatch):
    """Ownership comes from the trusted context, never from an argument.

    The pair is what the transcript joins on and what the fetch endpoint
    authorises through, so a model able to name either could attach a picture to
    a conversation that is not its own. Recorded at the call rather than read
    off a row, because the assertion is about which *source* the ids came from.
    """
    register()
    turn_id, thread_id = uuid.uuid4(), uuid.uuid4()
    seen: dict = {}

    real_run = study_tools.studies.run

    def recording_run(name, params, **kwargs):
        seen.update(kwargs, name=name, params=dict(params))
        with get_sync_db() as session:
            stored = real_run(name, params, session=session)
            session.rollback()
            return stored

    monkeypatch.setattr(study_tools.studies, "run", recording_run, raising=False)
    run(
        {"name": STUDY, "symbol": "STB", "turn_id": str(uuid.uuid4())},
        turn_id=turn_id,
        thread_id=thread_id,
    )

    assert seen["turn_id"] == turn_id
    assert seen["thread_id"] == thread_id
    # The argument the model tried to smuggle in is not a parameter of this
    # Study, so it never reaches the run at all.
    assert seen["params"] == {"symbol": "STB"}


# -- refusals, and how they are classified --------------------------------


def test_a_refused_study_answers_with_the_input_that_was_short():
    def refuse(_context) -> StudyResult:
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_SESSIONS, "4 closed sessions stored, 10 needed"
        )

    register("tools_thin", compute=refuse)

    answered = run({"name": "tools_thin", "symbol": "STB"})

    assert answered["issue"] == "insufficient_sessions"
    assert "10 needed" in answered["detail"]
    assert "artifactId" not in answered
    # "Ran" and "returned numbers" are two different things: the call is ``ok``
    # and the outcome is what says there is nothing to draw.
    assert outcome_of("run_study", answered) == "no_value:insufficient_sessions"
    assert canvas_of("run_study", answered) is None


def test_a_run_that_produced_a_canvas_is_classified_as_a_value():
    register()

    answered = run({"name": STUDY, "symbol": "STB"})

    assert outcome_of("run_study", answered) == "value"
    projected = canvas_of("run_study", answered)
    assert projected == {
        "artifactId": answered["artifactId"],
        "studyName": STUDY,
        "title": answered["title"],
        "blockCount": 1,
    }


def test_a_name_nothing_registers_says_what_is_registered():
    register()

    with pytest.raises(ValueError, match=STUDY):
        run({"name": "not_a_study", "symbol": "STB"})


def test_parameters_the_model_filled_wrongly_come_back_saying_how():
    register()

    with pytest.raises(ValueError, match="sessions"):
        run({"name": STUDY, "symbol": "STB", "sessions": 900})


# -- the flat argument object ---------------------------------------------


def test_the_schema_offers_the_registered_names_and_every_studys_parameters():
    register()
    register("tools_other", params_model=Params)

    schema = study_tools.run_study_schema()

    assert schema["properties"]["name"]["enum"] == [STUDY, "tools_other"]
    assert schema["required"] == ["name"]
    # Only the name is mandatory: a parameter required by one Study is
    # meaningless for the next, and requiring it would refuse every other call.
    assert set(schema["properties"]) == {"name", "symbol", "sessions"}
    assert schema["properties"]["symbol"]["description"].startswith(
        f"[{STUDY}, tools_other]"
    )


def test_a_key_meant_for_another_study_is_not_quietly_read_as_a_default():
    """Filtering rather than passing the object whole.

    pydantic ignores a key it does not know, so a parameter aimed at the wrong
    Study would vanish and the model would read a default as its own value.
    """
    register()

    params = study_tools._params_for(
        study_registry.REGISTRY[STUDY],
        {"name": STUDY, "symbol": "STB", "sessions": None, "unrelated": 5},
    )

    assert params == {"symbol": "STB"}


def test_two_studies_disagreeing_about_one_parameter_fail_the_build():
    class OtherParams(BaseModel):
        symbol: int

    register()
    register("tools_conflicting", params_model=OtherParams, frames=("profile",))

    with pytest.raises(ValueError, match="symbol"):
        study_tools._check_the_parameters_agree()


def test_a_study_may_not_claim_the_argument_that_names_a_study():
    class Shadowing(BaseModel):
        name: str

    register("tools_shadow", params_model=Shadowing)

    with pytest.raises(ValueError, match="which is the argument"):
        study_tools._check_the_parameters_agree()


# -- warming the inputs ----------------------------------------------------


def test_the_declared_inputs_are_fetched_before_the_store_is_read(monkeypatch):
    register("tools_warmed", requires=("intraday_bar_15m",))
    asked: list[tuple[str, int]] = []

    def fake(session, params):
        assert session is not None
        asked.append((params.symbol, params.sessions))

    monkeypatch.setitem(warmup.WARMERS, "intraday_bar_15m", fake)

    run({"name": "tools_warmed", "symbol": "STB", "sessions": 20})

    assert asked == [("STB", 20)]


def test_a_study_requiring_an_input_nothing_fetches_cannot_be_registered():
    with pytest.raises(ImportError, match="nothing knows how to fetch"):
        register("tools_impossible", requires=("moon_phase",))


# -- the catalog -----------------------------------------------------------


@pytest.mark.asyncio
async def test_the_catalog_lists_the_question_and_whether_the_inputs_are_reachable():
    register()

    listed = await study_tools.StudyTools().list_studies(ToolContext(), {})

    assert listed["count"] == 1
    entry = listed["studies"][0]
    assert entry["name"] == STUDY
    assert entry["question"].startswith("Thanh khoản")
    assert entry["params"]["properties"]["symbol"]["description"] == "Mã chứng khoán"
    assert entry["inputsReachable"] is True


def test_the_rail_row_names_the_analysis_the_company_and_the_window():
    register()

    assert (
        study_tools.summarise_run_study({"name": STUDY, "symbol": "stb", "sessions": 30})
        == "Thanh khoản trong phiên: STB · 30 phiên"
    )
    # A call whose arguments say nothing recognisable still gets a readable row
    # rather than a raw tool name.
    assert study_tools.summarise_run_study({}) == "phân tích"
