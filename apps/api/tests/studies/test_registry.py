"""The checks that keep the Study catalog honest at import.

A Study is a plan and a board written against the plan's step names, so every
way a declaration can rot is now knowable without running it: a board that draws
a frame no step produces, a calculation fed by a step that runs after it, a
figure typed into a template's code. All of them are refused here, where the
module that declared them is imported, rather than on a live question.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from src.studies import grammar, registry
from src.studies.contracts import (
    ComputeStep,
    QueryStep,
    ReadStep,
    StudyDefinition,
)


class Params(BaseModel):
    symbol: str
    sessions: int = Field(default=30, ge=10, le=60)


def a_query(**overrides) -> QueryStep:
    fields = {
        "name": "bars",
        "title": "Phiên đã đóng",
        "source": "bar_daily",
        "symbols": lambda context: [context.params.symbol],
        "arguments": lambda context: {"window": context.params.sessions},
    }
    fields.update(overrides)
    return QueryStep(**fields)


def a_board(**overrides) -> dict:
    board = {
        "title": "Một study — {symbol}",
        "archetype": "profile",
        "kpis": [
            {
                "label": f"Số {index}",
                "value": {"frame_id": "bars", "column": "close", "row": 0},
            }
            for index in range(3)
        ],
        "sections": [
            {
                "heading": "Tổng quan",
                "blocks": [{"kind": "visual", "frame_id": "bars"}],
            }
        ],
    }
    board.update(overrides)
    return board


def a_definition(**overrides) -> StudyDefinition:
    fields = {
        "name": "a_study",
        "version": 1,
        "question": "Câu hỏi study này trả lời?",
        "display_name": "Một study",
        "params_model": Params,
        "requires": ("intraday_bar_15m",),
        "archetype": "profile",
        "plan": (a_query(),),
        "board": a_board(),
        "headline": lambda params, frames: {"symbol": params.symbol},
    }
    fields.update(overrides)
    return StudyDefinition(**fields)


@pytest.fixture(autouse=True)
def empty_registry():
    """Every test registers into its own catalog, so order cannot matter."""
    saved = dict(registry.REGISTRY)
    registry.REGISTRY.clear()
    yield saved
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


def test_params_declared_as_anything_but_a_pydantic_model_are_refused():
    class NotAModel:
        pass

    with pytest.raises(ImportError, match="pydantic model"):
        registry.register(a_definition(params_model=NotAModel))


def test_a_study_that_declares_no_steps_is_refused():
    with pytest.raises(ImportError, match="no steps"):
        registry.register(a_definition(plan=()))


def test_a_step_name_used_twice_is_refused():
    """The second frame would hide the first from every board that named it."""
    with pytest.raises(ImportError, match="twice"):
        registry.register(a_definition(plan=(a_query(), a_query())))


def test_a_calculation_fed_by_a_step_that_runs_after_it_is_refused():
    """Order is the whole of a plan's meaning, so it is checked and not trusted."""
    plan = (
        ComputeStep(
            name="derived",
            title="Tính",
            code="result = f0",
            inputs=("bars",),
        ),
        a_query(),
    )

    with pytest.raises(ImportError, match="has not produced yet"):
        registry.register(a_definition(plan=plan))


def test_a_calculation_over_more_frames_than_the_sandbox_binds_is_refused():
    plan = (a_query(),) + tuple(
        ComputeStep(name=f"c{index}", title="Tính", code="result = f0", inputs=("bars",))
        for index in range(registry.MAX_COMPUTE_INPUTS)
    )
    too_many = plan + (
        ComputeStep(
            name="last",
            title="Tính",
            code="result = f0",
            inputs=("bars",) + tuple(f"c{index}" for index in range(registry.MAX_COMPUTE_INPUTS)),
        ),
    )

    with pytest.raises(ImportError, match="the sandbox binds"):
        registry.register(a_definition(plan=too_many))


def test_a_source_the_store_does_not_hold_is_refused():
    with pytest.raises(ImportError, match="not\n?.*one of the store's sources"):
        registry.register(a_definition(plan=(a_query(source="order_book"),)))


def test_a_template_that_types_a_figure_is_refused_at_import():
    """The invariant of the whole plane, checked where a template is written.

    A template has no privilege over a model here. The model's calculation is
    read by the validator before a subprocess is spawned for it; a template's is
    read before the module that declared it finishes importing, which is a
    stricter moment for the same rule.
    """
    plan = (
        a_query(),
        ComputeStep(
            name="derived",
            title="Tính",
            code="result = f0[f0['close'] > 41500]",
            inputs=("bars",),
        ),
    )

    with pytest.raises(ImportError, match="compute_literal_number"):
        registry.register(a_definition(plan=plan))


def test_a_figure_declared_as_an_assumption_passes():
    """The same number, through the door it is supposed to come through."""
    plan = (
        a_query(),
        ComputeStep(
            name="derived",
            title="Tính",
            code="result = f0[f0['close'] > floor]",
            inputs=("bars",),
            constants=lambda context: {"floor": 41500},
        ),
    )

    assert registry.register(a_definition(plan=plan)).name == "a_study"


def test_a_board_that_draws_a_frame_the_plan_never_produces_is_refused():
    board = a_board(
        sections=[
            {"heading": None, "blocks": [{"kind": "visual", "frame_id": "nowhere"}]}
        ]
    )

    with pytest.raises(ImportError, match="nowhere"):
        registry.register(a_definition(board=board))


def test_a_board_that_is_not_a_board_is_refused_by_its_own_message():
    with pytest.raises(ImportError, match="not one"):
        registry.register(a_definition(board={"sections": []}))


def test_a_widget_no_viewer_has_is_refused():
    board = a_board(
        sections=[
            {
                "heading": None,
                "blocks": [
                    {"kind": "visual", "frame_id": "bars", "widget": "candlestick"}
                ],
            }
        ]
    )

    with pytest.raises(ImportError, match="candlestick"):
        registry.register(a_definition(board=board))


def test_an_archetype_nobody_defines_is_refused():
    with pytest.raises(ImportError, match="the five are"):
        registry.register(a_definition(archetype="dashboard"))


def test_the_catalog_hands_the_model_the_question_the_schema_and_the_shape():
    registry.register(a_definition(name="second_study"))
    registry.register(a_definition(name="first_study", archetype="screen"))

    entries = registry.catalog()

    assert [entry["name"] for entry in entries] == ["first_study", "second_study"]
    schema = entries[0]["params"]
    assert schema["properties"]["sessions"]["maximum"] == 60
    assert "symbol" in schema["required"]
    # What the template's answer *looks* like, which is what a model is choosing
    # between when it weighs a template against composing a board itself.
    assert entries[0]["archetype"] == "screen"
    assert entries[1]["archetype"] == "profile"


def test_asking_for_an_unregistered_study_names_what_is_registered():
    registry.register(a_definition(name="the_only_one"))

    with pytest.raises(KeyError, match="the_only_one"):
        registry.study("missing_study")


def test_the_declaration_has_no_defaults_to_forget():
    with pytest.raises(TypeError):
        StudyDefinition(name="incomplete", version=1)  # type: ignore[call-arg]


def test_a_read_step_is_admitted_without_naming_a_source():
    """The narrow privilege, and it is narrow on purpose.

    A ``ReadStep`` answers to no source name because it exists for the reads the
    query layer has none for. What it does not get is a calculation of its own:
    every figure a template derives still goes through ``ComputeStep`` and the
    validator, which is what the literal test above is protecting.
    """
    step = ReadStep(name="bars", title="Đọc riêng", read=lambda context: None)

    assert registry.register(a_definition(plan=(step,))).plan[0].kind == "read"


def test_every_registered_template_declares_a_board_over_its_own_steps(
    empty_registry,
):
    """The real catalog, checked the way the fakes above are.

    A loop rather than four tests, because what is asserted is a property of the
    registry as a whole: whatever is registered when the suite runs has been
    through the same door. The catalog comes from the fixture, which holds what
    importing ``src.studies`` produced — a reload here would find every template
    module already in ``sys.modules`` and register nothing.
    """
    assert set(empty_registry) == {
        "earnings_dislocation_screener",
        "entry_condition_review",
        "intraday_liquidity_profile",
        "volume_at_price",
    }
    for definition in empty_registry.values():
        assert definition.step_names, definition.name
        assert definition.archetype in {
            "compare",
            "profile",
            "screen",
            "timeline",
            "decompose",
        }
        # Registration checked this when the module imported; asserted again
        # here because the door being shut is worth stating where a reader of
        # the catalog will look.
        drawn = set(grammar.frame_references(grammar.parse(definition.board)))
        assert drawn <= set(definition.step_names), definition.name
