"""The two-way check that keeps the Study catalog honest at import."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from src.studies import registry, widgets
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


def a_definition(**overrides) -> StudyDefinition:
    fields = {
        "name": "a_study",
        "version": 1,
        "question": "Câu hỏi study này trả lời?",
        "display_name": "Một study",
        "params_model": Params,
        "requires": ("intraday_bar_15m",),
        "frames": ("profile",),
        "widgets": (("bar_series", 1),),
        "compute": lambda context: None,
        "view": lambda result: None,
    }
    fields.update(overrides)
    return StudyDefinition(**fields)


@pytest.fixture(autouse=True)
def empty_registry():
    """Every test registers into its own catalog, so order cannot matter."""
    saved = dict(registry.REGISTRY)
    registry.REGISTRY.clear()
    yield
    registry.REGISTRY.clear()
    registry.REGISTRY.update(saved)


def test_a_name_registered_twice_is_refused_rather_than_overwritten():
    registry.register(a_definition())

    with pytest.raises(ImportError, match="registered twice"):
        registry.register(a_definition())


@pytest.mark.parametrize("field", ["question", "display_name"])
def test_a_blank_catalog_entry_is_refused(field):
    with pytest.raises(ImportError, match=field):
        registry.register(a_definition(**{field: "  "}))


def test_a_widget_no_viewer_has_is_refused():
    with pytest.raises(ImportError, match="candlestick v1"):
        registry.register(a_definition(widgets=(("candlestick", 1),)))


def test_a_widget_version_no_viewer_has_is_refused():
    assert widgets.known("bar_series", 1)

    with pytest.raises(ImportError, match="bar_series v9"):
        registry.register(a_definition(widgets=(("bar_series", 9),)))


def test_params_declared_as_anything_but_a_pydantic_model_are_refused():
    class NotAModel:
        pass

    with pytest.raises(ImportError, match="pydantic model"):
        registry.register(a_definition(params_model=NotAModel))


def test_a_study_that_declares_no_frames_is_refused():
    with pytest.raises(ImportError, match="no frames"):
        registry.register(a_definition(frames=()))


def test_the_catalog_hands_the_model_the_question_and_the_schema():
    registry.register(a_definition(name="second_study"))
    registry.register(a_definition(name="first_study"))

    entries = registry.catalog()

    assert [entry["name"] for entry in entries] == ["first_study", "second_study"]
    schema = entries[0]["params"]
    assert schema["properties"]["sessions"]["maximum"] == 60
    assert "symbol" in schema["required"]


def test_asking_for_an_unregistered_study_names_what_is_registered():
    registry.register(a_definition(name="the_only_one"))

    with pytest.raises(KeyError, match="the_only_one"):
        registry.study("missing_study")


def test_the_declaration_has_no_defaults_to_forget():
    with pytest.raises(TypeError):
        StudyDefinition(name="incomplete", version=1)  # type: ignore[call-arg]


def a_result() -> StudyResult:
    from datetime import datetime, timezone

    return StudyResult(
        headline={"symbol": "STB"},
        frames={
            "profile": Frame(
                kind="series",
                columns=("bucket",),
                rows=(("09:15",),),
                unit=None,
                labels={"bucket": "Khung giờ"},
            )
        },
        provenance=Provenance(
            source="vnstock",
            as_of=datetime.now(timezone.utc),
            sessions_used=30,
            health="normal",
            reason=None,
        ),
    )


def test_a_view_may_only_draw_declared_widgets_over_declared_frames():
    """The pairing the runner enforces, stated once where a reader will look."""
    definition = registry.register(a_definition())
    spec = CanvasSpec(
        title="Một study",
        blocks=(
            CanvasBlock(
                widget="bar_series", widget_version=1, frame="profile", options={}
            ),
        ),
    )

    assert spec.blocks[0].frame in definition.frames
    assert (spec.blocks[0].widget, spec.blocks[0].widget_version) in definition.widgets
    assert widgets.accepts("bar_series", 1, a_result().frames["profile"].kind)
