"""The run path: validate, read, calculate, draw, persist — each exactly once.

Driven with a template built here rather than with one of the four real ones, so
what is under test is the executor and not a domain. Its plan is the smallest
that exercises every kind of step: a read the query layer has no source for, a
calculation over it, and a board written against both.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from src.alpha.models import AgentArtifact
from src.core.database import Base, get_sync_db, sync_engine
from src.studies import frames_buffer, registry, runner
from src.studies.contracts import (
    ComputeStep,
    Frame,
    Provenance,
    ReadStep,
    StudyDefinition,
)


class Params(BaseModel):
    symbol: str
    sessions: int = Field(default=30, ge=10, le=60)


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def only_this_studys_catalog():
    saved = dict(registry.REGISTRY)
    registry.REGISTRY.clear()
    yield
    registry.REGISTRY.clear()
    registry.REGISTRY.update(saved)


@pytest.fixture(autouse=True)
def no_leftover_rows():
    yield
    with get_sync_db() as session:
        session.execute(
            delete(AgentArtifact).where(
                AgentArtifact.study_name.in_(
                    (
                        frames_buffer.QUERY_KIND,
                        frames_buffer.COMPUTE_KIND,
                        frames_buffer.COMPOSITION_KIND,
                    )
                )
            )
        )
        session.commit()


class _AUniverseOf:
    def __init__(self, symbols: tuple[str, ...]) -> None:
        self.symbols = symbols


@pytest.fixture(autouse=True)
def a_declared_universe(monkeypatch):
    monkeypatch.setattr(
        runner, "build_universe", lambda session: _AUniverseOf(("STB",))
    )


def a_profile_frame() -> Frame:
    return Frame(
        kind="series",
        columns=("bucket", "avg_volume"),
        rows=(("09:15", 1_000), ("14:45", 4_000)),
        unit="shares",
        labels={"bucket": "Khung giờ", "avg_volume": "KL trung bình"},
    )


def a_provenance(context) -> Provenance:
    return Provenance(
        source="store",
        as_of=context.as_of,
        sessions_used=context.params.sessions,
        health="normal",
        reason=None,
    )


def a_read_step(**overrides) -> ReadStep:
    fields = {
        "name": "profile",
        "title": "Khung giờ",
        "read": lambda context: (a_profile_frame(), a_provenance(context)),
    }
    fields.update(overrides)
    return ReadStep(**fields)


#: Twice the window's total, on one row. Two is structural, so the validator
#: admits it and the assertion below can be about a number that moved rather than
#: about a number that was copied. One row rather than two because a board of two
#: identically shaped frames draws the same picture twice, and the grammar refuses
#: that — which is itself the rule worth having under a runner test.
_DOUBLE = """
result = pd.DataFrame({"total": [f0["avg_volume"].sum() * 2]})
result.attrs["labels"] = {"total": "Tổng gấp đôi"}
result.attrs["unit"] = "shares"
"""


def a_board(**overrides) -> dict:
    board = {
        "title": "Runner — {symbol}",
        "archetype": "profile",
        # Three figures over a two-row frame: the strip's floor is three, and
        # what it is a floor on is *answering*, not on how tall a frame is.
        "kpis": [
            {
                "label": f"Số {index}",
                "value": {
                    "frame_id": "profile",
                    "column": "avg_volume",
                    "row": index % 2,
                },
            }
            for index in range(3)
        ],
        "sections": [
            {
                "heading": "Tổng quan",
                "blocks": [
                    {"kind": "visual", "frame_id": "profile"},
                    {"kind": "visual", "frame_id": "doubled"},
                ],
            }
        ],
    }
    board.update(overrides)
    return board


def a_template(**overrides) -> StudyDefinition:
    fields = {
        "name": "runner_study",
        "version": 1,
        "question": "Câu hỏi?",
        "display_name": "Runner",
        "params_model": Params,
        "requires": (),
        "archetype": "profile",
        "plan": (
            a_read_step(),
            ComputeStep(
                name="doubled",
                title="Gấp đôi",
                code=_DOUBLE,
                inputs=("profile",),
                output_kind="table",
            ),
        ),
        "board": a_board(),
        "headline": lambda params, frames: {
            "symbol": params.symbol,
            "sessionsUsed": params.sessions,
            "peak": frames["profile"]["rows"][-1][0],
        },
    }
    fields.update(overrides)
    return StudyDefinition(**fields)


def run(params: dict | None = None, **overrides):
    """Register the template, run it, and hand back the artifact and the rows."""
    registry.register(a_template(**overrides))
    with get_sync_db() as session:
        artifact = runner.run(
            "runner_study",
            params or {"symbol": "STB"},
            session=session,
            read=_never_read,
        )
        rows = list(
            session.execute(select(AgentArtifact)).scalars()
        )
        session.commit()
    return artifact, rows


def _never_read(*args, **kwargs):
    raise AssertionError("this template's plan has no query step")


def test_a_run_persists_a_frame_per_step_and_a_board_over_them():
    artifact, rows = run()

    steps = {
        row.params.get("step"): row
        for row in rows
        if row.study_name in (frames_buffer.QUERY_KIND, frames_buffer.COMPUTE_KIND)
    }
    compositions = [
        row for row in rows if row.study_name == frames_buffer.COMPOSITION_KIND
    ]

    assert set(steps) == {"profile", "doubled"}
    assert len(compositions) == 1
    # The calculation ran in the sandbox and its answer is what was filed.
    assert steps["doubled"].frames["doubled"]["rows"][0][0] == 10_000
    assert artifact.signal_desk_spec.title == "Runner — STB"


def test_the_model_is_handed_a_headline_and_never_the_frames():
    artifact, _rows = run()

    assert artifact.headline == {
        "symbol": "STB",
        "sessionsUsed": 30,
        "peak": "14:45",
    }
    assert "frames" not in artifact.headline
    # Every step is addressable, which is what lets a model re-mix one.
    assert set(artifact.steps) == {"profile", "doubled"}
    assert all("#" in reference for reference in artifact.steps.values())


def test_the_as_of_written_to_the_row_is_the_one_the_run_froze():
    frozen = datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc)
    registry.register(a_template())
    with get_sync_db() as session:
        artifact = runner.run(
            "runner_study",
            {"symbol": "STB"},
            session=session,
            read=_never_read,
            as_of=frozen,
        )
        row = session.execute(
            select(AgentArtifact).where(AgentArtifact.id == artifact.id)
        ).scalar_one()
        stamp = row.provenance["asOf"]
        session.commit()

    assert stamp == frozen.isoformat()


def test_parameters_the_model_filled_wrongly_come_back_saying_how():
    registry.register(a_template())

    with get_sync_db() as session:
        with pytest.raises(runner.StudyParamsInvalid) as invalid:
            runner.run(
                "runner_study",
                {"symbol": "STB", "sessions": 900},
                session=session,
                read=_never_read,
            )

    assert "sessions" in str(invalid.value)


def test_a_board_that_breaks_its_own_rules_fails_on_the_run_that_wrote_it():
    """A model's board gets a round to fix itself; a template's is a bug here.

    The distinction is the whole reason this raises rather than composing
    something. A board the model wrote is an attempt, and the answer to a bad one
    is a named violation and a retry. A board a template declares was written by
    hand, reviewed and shipped, so a violation is a fact about this repository
    and the run that finds it should be a test run.
    """
    board = a_board(kpis=[])

    registry.register(a_template(board=board))
    with get_sync_db() as session:
        with pytest.raises(RuntimeError, match="breaks its own rules"):
            runner.run(
                "runner_study", {"symbol": "STB"}, session=session, read=_never_read
            )


def test_a_calculation_that_will_not_run_names_the_step_and_the_sandbox_reason():
    """A template whose code fails is a bug, not an answer for a reader."""
    plan = (
        a_read_step(),
        ComputeStep(
            name="doubled",
            title="Gấp đôi",
            code="result = f0['nothing_here']",
            inputs=("profile",),
        ),
    )

    registry.register(a_template(plan=plan))
    with get_sync_db() as session:
        with pytest.raises(RuntimeError, match="doubled did not compute"):
            runner.run(
                "runner_study", {"symbol": "STB"}, session=session, read=_never_read
            )


def test_a_step_declaring_a_note_about_method_leads_the_strip():
    """Declared notes come first, so a cap drops the engine's lines and not these."""
    plan = (
        a_read_step(method_notes=("Cửa sổ đọc là ba mươi phiên gần nhất.",)),
        ComputeStep(
            name="doubled",
            title="Gấp đôi",
            code=_DOUBLE,
            inputs=("profile",),
            output_kind="table",
        ),
    )

    registry.register(a_template(plan=plan))
    with get_sync_db() as session:
        artifact = runner.run(
            "runner_study", {"symbol": "STB"}, session=session, read=_never_read
        )
        row = session.execute(
            select(AgentArtifact).where(AgentArtifact.id == artifact.id)
        ).scalar_one()
        notes = list(row.provenance["methodNotes"])
        session.commit()

    assert notes[0] == "Cửa sổ đọc là ba mươi phiên gần nhất."


def test_the_session_count_comes_from_the_reads_and_not_from_a_row_count():
    """A derived frame's ``sessionsUsed`` is its own height, which is not sessions.

    Maxed across every frame it made a two-row ladder claim two sessions and a
    thirty-session profile claim four hundred and eighty — a figure on the strip
    that reads as a claim about how much history the picture rests on.
    """
    registry.register(a_template())
    with get_sync_db() as session:
        artifact = runner.run(
            "runner_study",
            {"symbol": "STB", "sessions": 45},
            session=session,
            read=_never_read,
        )
        session.commit()

    assert artifact.provenance.sessions_used == 45


def test_a_run_outside_a_turn_is_reachable_by_id_alone():
    artifact, rows = run()

    composition = next(
        row for row in rows if row.study_name == frames_buffer.COMPOSITION_KIND
    )
    assert composition.id == artifact.id
    assert composition.turn_id is None
    assert composition.thread_id is None


def test_a_symbol_the_template_refuses_never_reaches_a_read():
    """The precheck runs before the plan, which is what makes it worth having."""
    from src.stocks.signals.issues import SignalIssue
    from src.studies.contracts import StudyRefused

    def _refuse(context):
        raise StudyRefused(SignalIssue.MISSING_TARGET_SESSION, "not covered")

    def _explode(context):
        raise AssertionError("the precheck should have stopped this")

    registry.register(
        a_template(
            precheck=_refuse,
            plan=(a_read_step(read=_explode),),
            board=a_board(
                sections=[
                    {
                        "heading": "Tổng quan",
                        "blocks": [{"kind": "visual", "frame_id": "profile"}],
                    }
                ]
            ),
        )
    )
    with get_sync_db() as session:
        with pytest.raises(StudyRefused) as refusal:
            runner.run(
                "runner_study", {"symbol": "STB"}, session=session, read=_never_read
            )

    assert refusal.value.issue is SignalIssue.MISSING_TARGET_SESSION
