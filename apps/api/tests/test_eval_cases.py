"""The Eval Case shape and the registry the battery is read from.

Two properties that would be invisible until they cost something:

*A failure has to name exactly one case.* Two cases under one id makes an
attributed failure unattributable, so the registry refuses the second.

*A case names a fixture seat, not a ticker.* A re-freeze moves the symbol below
``min_sessions``; a case that had hard-coded the old one would go on passing
while silently asking about a healthy symbol.
"""

from __future__ import annotations

import pytest

from src.eval import cases as registry
from src.eval.cases import (
    DuplicateEvalCase,
    EvalCase,
    EvalCategory,
    EvalSurface,
    battery,
    register,
)
from src.eval.roles import FixtureRole


@pytest.fixture(autouse=True)
def empty_registry():
    """The battery is global; a test that seats cases must not leak them."""
    saved = dict(registry._REGISTRY)
    registry._REGISTRY.clear()
    yield
    registry._REGISTRY.clear()
    registry._REGISTRY.update(saved)


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
    def test_the_shipped_registry_is_empty_until_the_category_tickets_seed_it(self):
        """An empty battery reports nothing rather than a clean sheet."""
        registry._REGISTRY.update({})
        assert battery() == ()

    def test_registered_cases_come_back_in_registration_order(self):
        register(turn_case("b-1"), turn_case("b-2"))
        assert [case.id for case in battery()] == ["b-1", "b-2"]

    def test_a_duplicate_id_is_refused(self):
        register(turn_case("dup"))
        with pytest.raises(DuplicateEvalCase):
            register(turn_case("dup"))

    def test_the_battery_narrows_by_category_and_by_surface(self):
        register(
            turn_case("q-1", category=EvalCategory.DATA_GAP),
            turn_case("q-2", category=EvalCategory.SCOPE),
            EvalCase(
                id="a-1",
                category=EvalCategory.DATA_GAP,
                surface=EvalSurface.ANALYSIS,
                prompt="",
                role=FixtureRole.LIMIT_LOCK_DENSE,
            ),
        )
        assert [c.id for c in battery(categories=[EvalCategory.DATA_GAP])] == [
            "q-1",
            "a-1",
        ]
        assert [c.id for c in battery(surfaces=[EvalSurface.ANALYSIS])] == ["a-1"]


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

    def test_a_case_without_an_id_has_nothing_to_fail_under(self):
        with pytest.raises(ValueError):
            turn_case("   ")


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
