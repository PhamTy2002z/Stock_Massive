"""The run path: validate, compute, check what came back, persist it once."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from src.alpha.models import AgentArtifact
from src.core.database import Base, get_sync_db, sync_engine
from src.studies import registry, runner
from src.studies.contracts import (
    CanvasBlock,
    CanvasSpec,
    Frame,
    Provenance,
    StudyDefinition,
    StudyResult,
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
            delete(AgentArtifact).where(AgentArtifact.study_name.like("runner_%"))
        )


def a_profile_frame() -> Frame:
    return Frame(
        kind="series",
        columns=("bucket", "avg_volume"),
        rows=(("09:15", 1_000), ("14:45", 4_000)),
        unit="shares",
        labels={"bucket": "Khung giờ", "avg_volume": "KL trung bình"},
    )


def a_result(context) -> StudyResult:
    return StudyResult(
        headline={"symbol": context.params.symbol, "sessionsUsed": context.params.sessions},
        frames={"profile": a_profile_frame()},
        provenance=Provenance(
            source="vnstock",
            as_of=context.as_of,
            sessions_used=context.params.sessions,
            health="normal",
            reason=None,
        ),
    )


def a_canvas(result: StudyResult) -> CanvasSpec:
    return CanvasSpec(
        title="Thanh khoản trong phiên",
        blocks=(
            CanvasBlock(
                widget="bar_series",
                widget_version=1,
                frame="profile",
                options={"x": "bucket", "y": "avg_volume"},
            ),
        ),
    )


def register(name: str = "runner_study", **overrides) -> StudyDefinition:
    fields = {
        "name": name,
        "version": 1,
        "question": "Thanh khoản tập trung ở khung giờ nào?",
        "display_name": "Study thử",
        "params_model": Params,
        "requires": (),
        "frames": ("profile",),
        "widgets": (("bar_series", 1),),
        "compute": a_result,
        "view": a_canvas,
    }
    fields.update(overrides)
    return registry.register(StudyDefinition(**fields))


def test_a_run_persists_the_frames_and_hands_back_only_the_headline():
    register()

    with get_sync_db() as session:
        stored = runner.run("runner_study", {"symbol": "STB"}, session=session)
        session.commit()
        row = session.execute(
            select(AgentArtifact).where(AgentArtifact.id == stored.id)
        ).scalar_one()

        assert stored.headline == {"symbol": "STB", "sessionsUsed": 30}
        assert "frames" not in stored.headline
        assert row.frames["profile"]["rows"] == [["09:15", 1000], ["14:45", 4000]]
        assert row.canvas_spec["blocks"][0]["widgetVersion"] == 1
        assert row.params == {"symbol": "STB", "sessions": 30}
        assert row.provenance["sessionsUsed"] == 30


def test_the_as_of_written_to_the_row_is_the_one_the_run_froze():
    register()

    with get_sync_db() as session:
        before = datetime.now(timezone.utc)
        stored = runner.run("runner_study", {"symbol": "STB"}, session=session)
        session.commit()
        row = session.execute(
            select(AgentArtifact).where(AgentArtifact.id == stored.id)
        ).scalar_one()

    frozen = datetime.fromisoformat(row.provenance["asOf"])
    assert before <= frozen <= datetime.now(timezone.utc)
    assert row.provenance["asOf"] == stored.provenance.as_of.isoformat()


def test_parameters_the_model_filled_wrongly_come_back_saying_how():
    register()

    with get_sync_db() as session:
        with pytest.raises(runner.StudyParamsInvalid, match="sessions"):
            runner.run(
                "runner_study", {"symbol": "STB", "sessions": 900}, session=session
            )
        with pytest.raises(runner.StudyParamsInvalid, match="symbol"):
            runner.run("runner_study", {}, session=session)


def test_a_compute_that_skips_a_declared_frame_fails_on_that_run():
    def half_a_result(context) -> StudyResult:
        result = a_result(context)
        return StudyResult(
            headline=result.headline,
            frames={"other": a_profile_frame()},
            provenance=result.provenance,
        )

    register("runner_wrong_frames", compute=half_a_result)

    with get_sync_db() as session:
        with pytest.raises(RuntimeError, match="declared frames"):
            runner.run("runner_wrong_frames", {"symbol": "STB"}, session=session)


def test_a_view_naming_a_frame_that_is_not_there_fails_on_that_run():
    def canvas_over_nothing(result: StudyResult) -> CanvasSpec:
        return CanvasSpec(
            title="Sai frame",
            blocks=(
                CanvasBlock(
                    widget="bar_series",
                    widget_version=1,
                    frame="heatmap",
                    options={},
                ),
            ),
        )

    register("runner_wrong_view", view=canvas_over_nothing)

    with get_sync_db() as session:
        with pytest.raises(RuntimeError, match="did not produce"):
            runner.run("runner_wrong_view", {"symbol": "STB"}, session=session)


def test_a_widget_that_cannot_draw_the_frame_kind_is_refused_on_the_run():
    def heatmap_over_a_series(result: StudyResult) -> CanvasSpec:
        return CanvasSpec(
            title="Sai loại frame",
            blocks=(
                CanvasBlock(
                    widget="session_heatmap",
                    widget_version=1,
                    frame="profile",
                    options={},
                ),
            ),
        )

    register(
        "runner_wrong_kind",
        view=heatmap_over_a_series,
        widgets=(("session_heatmap", 1),),
    )

    with get_sync_db() as session:
        with pytest.raises(RuntimeError, match="cannot draw a series frame"):
            runner.run("runner_wrong_kind", {"symbol": "STB"}, session=session)


def test_a_run_outside_a_turn_is_reachable_by_id_alone():
    register()

    with get_sync_db() as session:
        stored = runner.run("runner_study", {"symbol": "STB"}, session=session)
        session.commit()
        row = session.execute(
            select(AgentArtifact).where(AgentArtifact.id == stored.id)
        ).scalar_one()

    assert row.turn_id is None
    assert row.thread_id is None
