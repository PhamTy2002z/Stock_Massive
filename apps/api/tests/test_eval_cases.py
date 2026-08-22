"""The Eval Case shape and the registry the battery is read from.

Two properties that would be invisible until they cost something:

*A failure has to name exactly one case.* Two cases under one id makes an
attributed failure unattributable, so the registry refuses the second.

*A case names a fixture seat, not a ticker.* A re-freeze moves the symbol below
``min_sessions``; a case that had hard-coded the old one would go on passing
while silently asking about a healthy symbol.

And one about the battery as shipped: the Analysis lane's ten cases are read off
the **registry** rather than off the module that writes them, because the
registry is what a run reads. A case module nobody imported is a case that left
the exam, and the report would show that category shrink without a word.
"""

from __future__ import annotations

import pytest

# Imported at module scope so that the shipped battery is always already seated
# when ``empty_registry`` sets it aside. Deferred to a test body it would be
# seated *into the cleared registry* on a run of this file alone, and put back
# as nothing afterwards.
from src.eval import cases as registry
from src.eval.cases import (
    AnalysisExpectation,
    DuplicateEvalCase,
    EvalCase,
    EvalCategory,
    EvalSurface,
    Expectation,
    battery,
    register,
)
from src.eval.roles import FixtureRole


_SAVED: dict = {}


def saved_battery() -> dict:
    """The shipped registry, set aside so a test can put it back deliberately."""
    return dict(_SAVED)


@pytest.fixture(autouse=True)
def empty_registry():
    """The battery is global; a test that seats cases must not leak them.

    Yields what was there, so a test about the **shipped** battery can read it
    without the ones this file seats — see :func:`shipped`.
    """
    _SAVED.clear()
    _SAVED.update(registry._REGISTRY)
    registry._REGISTRY.clear()
    yield tuple(_SAVED.values())
    registry._REGISTRY.clear()
    registry._REGISTRY.update(_SAVED)


@pytest.fixture
def shipped(empty_registry):
    """Every case the package seats when it is imported."""
    return empty_registry


def turn_case(identifier: str, **overrides) -> EvalCase:
    defaults = dict(
        id=identifier,
        category=EvalCategory.FALSE_REFUSAL,
        surface=EvalSurface.TURN,
        prompt="Cổ phiếu này đang ở vùng giá nào?",
        role=FixtureRole.BANK,
    )
    defaults.update(overrides)
    return EvalCase(**defaults)


class TestTheRegistry:
    def test_an_unseeded_registry_reports_nothing_rather_than_a_clean_sheet(self):
        """The registry is empty until the case modules are imported."""
        assert battery() == ()

    def test_registered_cases_come_back_in_registration_order(self):
        register(turn_case("b-1"), turn_case("b-2"))
        assert [case.id for case in battery()] == ["b-1", "b-2"]

    def test_a_duplicate_id_is_refused(self):
        register(turn_case("dup"))
        with pytest.raises(DuplicateEvalCase):
            register(turn_case("dup"))

    def test_the_battery_is_unfiltered(self):
        """All D/E cases are re-scored on every gate run, not only the changed.

        So there is no selector: the one that felt convenient is the one reached
        for on a run that felt slow.
        """
        register(
            turn_case("q-1", category=EvalCategory.DATA_GAP),
            turn_case("q-2", category=EvalCategory.SCOPE),
        )
        assert [c.id for c in battery()] == ["q-1", "q-2"]


class TestTheCaseShape:
    def test_a_turn_case_without_a_prompt_is_refused(self):
        with pytest.raises(ValueError):
            turn_case("no-prompt", prompt="  ")

    def test_an_analysis_case_without_a_fixture_seat_is_refused(self):
        """Its input is a symbol, so a case with no seat has no subject."""
        with pytest.raises(ValueError):
            EvalCase(
                id="a-2",
                category=EvalCategory.INTERPRETATION,
                surface=EvalSurface.ANALYSIS,
                prompt="",
                role=None,
            )

    def test_an_analysis_case_with_no_analysis_expectation_asserts_nothing(self):
        """A case is a question, and this one has lost it.

        With only the surface set it still runs the three lane checks, so it
        would sit in the battery reporting passes while asserting nothing about
        what the pipeline was supposed to do with that seat.
        """
        with pytest.raises(ValueError):
            EvalCase(
                id="a-3",
                category=EvalCategory.DATA_GAP,
                surface=EvalSurface.ANALYSIS,
                prompt="",
                role=FixtureRole.BANK,
            )

    def test_a_turn_case_carrying_an_analysis_expectation_is_refused(self):
        """Nothing a Turn produces could satisfy or fail it."""
        with pytest.raises(ValueError):
            turn_case(
                "a-4",
                expectation=Expectation(
                    analysis=AnalysisExpectation(publishes=True)
                ),
            )

    def test_a_case_without_an_id_has_nothing_to_fail_under(self):
        with pytest.raises(ValueError):
            turn_case("   ")


class TestTheAnalysisLaneIsSeated:
    """The ten cases ``docs/adr/0016`` gives the Analysis surface.

    Read off the registry rather than off the module, because what the battery
    runs is the registry: a case module nobody imported is a case that left the
    exam, and the report would show its category total shrink without a word.

    They are the whole shipped battery since ``docs/adr/0026``: the Turn lane's
    cases went with the harness that answered them.
    """

    def test_the_shipped_battery_is_the_analysis_lane_and_nothing_else(self, shipped):
        assert shipped
        assert {item.surface for item in shipped} == {EvalSurface.ANALYSIS}

    def test_the_shipped_battery_seats_the_analysis_lane(self, shipped):
        analysis = [
            item for item in shipped if item.surface is EvalSurface.ANALYSIS
        ]
        assert len(analysis) == 10

    def test_every_analysis_case_is_scored_by_d_or_e(self, shipped):
        """The nightly artifact fails at interpretation and at data gaps.

        The safety categories are the Turn lane's: there is no prompt to be
        off-topic about and no system prompt to extract.
        """
        categories = {
            item.category
            for item in shipped
            if item.surface is EvalSurface.ANALYSIS
        }
        assert categories == {EvalCategory.INTERPRETATION, EvalCategory.DATA_GAP}

    def test_interpretation_runs_across_the_four_field_profiles(self, shipped):
        """Emphasis and field membership differ by industry."""
        seats = {
            item.role
            for item in shipped
            if item.surface is EvalSurface.ANALYSIS
            and item.category is EvalCategory.INTERPRETATION
        }
        assert seats == {
            FixtureRole.BANK,
            FixtureRole.REAL_ESTATE,
            FixtureRole.RETAIL,
            FixtureRole.ORDINARY,
        }

    def test_the_data_gap_cases_cover_all_three_deliberate_bad_seats(self, shipped):
        seats = {
            item.role
            for item in shipped
            if item.surface is EvalSurface.ANALYSIS
            and item.category is EvalCategory.DATA_GAP
        }
        assert {
            FixtureRole.BELOW_MIN_SESSIONS,
            FixtureRole.PRICE_BASIS_SEAM,
            FixtureRole.LIMIT_LOCK_DENSE,
        } <= seats

    def test_every_analysis_case_says_what_it_is_for(self, shipped):
        """A failure a reader cannot attribute is a failure nobody acts on."""
        assert all(
            item.intent.strip()
            for item in shipped
            if item.surface is EvalSurface.ANALYSIS
        )


class TestTheSafetyCategories:
    def test_a_rate_is_not_an_acceptable_answer_for_a_c_and_f(self):
        """One leak is a leak; the letters that mean that are fixed here."""
        safety = {
            category.value for category in EvalCategory if category.is_safety
        }
        assert safety == {"A", "C", "F"}

    def test_the_quality_categories_are_the_other_three(self):
        quality = {
            category.value for category in EvalCategory if not category.is_safety
        }
        assert quality == {"B", "D", "E"}
