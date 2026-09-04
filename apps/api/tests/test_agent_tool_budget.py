"""The three rungs that keep a Turn inside the model's context window."""

from __future__ import annotations

from src.agent import budget


def _lines(count: int, width: int = 99) -> str:
    return "\n".join("x" * width for _ in range(count))


def test_both_budgets_scale_with_the_context_window():
    thresholds = budget.thresholds_for_context(100_000)

    # 100k tokens is 400k characters; 15% and 30% of it, neither clamp reached.
    assert thresholds.per_result_chars == 60_000
    assert thresholds.per_turn_chars == 120_000


def test_a_small_window_is_lifted_to_the_floor():
    thresholds = budget.thresholds_for_context(8_000)

    assert thresholds.per_result_chars == budget.PER_RESULT_MIN_CHARS
    assert thresholds.per_turn_chars == budget.PER_TURN_MIN_CHARS


def test_a_very_large_window_is_held_at_the_ceiling():
    thresholds = budget.thresholds_for_context(1_000_000)

    assert thresholds.per_result_chars == budget.PER_RESULT_MAX_CHARS
    assert thresholds.per_turn_chars == budget.PER_TURN_MAX_CHARS


def test_a_result_under_its_limit_is_untouched():
    text = _lines(3)

    trimmed, cursor = budget.trim_text(text, 10_000)

    assert trimmed == text
    assert cursor is None


def test_an_oversized_result_becomes_a_preview_with_a_cursor():
    text = _lines(400)

    trimmed, cursor = budget.trim_text(text, 4_000)

    assert cursor is not None
    assert cursor.total_chars == len(text)
    assert cursor.hidden_chars == len(text) - cursor.offset
    assert cursor.offset < len(text)
    # The preview keeps whole lines and states what it left behind.
    assert trimmed.startswith("x" * 99)
    assert "truncated" in trimmed
    assert f"offset {cursor.offset}" in trimmed


def test_a_result_with_no_line_breaks_is_still_previewed_rather_than_refused():
    text = "y" * 50_000

    trimmed, cursor = budget.trim_text(text, 4_000)

    assert cursor is not None
    assert len(trimmed) < len(text)


def test_the_threshold_resolution_order_is_pinned_config_registry_default():
    common = {"default_chars": 1_000, "registry": {"tool": 2_000}}

    assert budget.resolve_limit("tool", **common) == 2_000
    assert budget.resolve_limit("tool", config={"tool": 3_000}, **common) == 3_000
    assert (
        budget.resolve_limit("tool", pinned={"tool": 4_000}, config={"tool": 3_000}, **common)
        == 4_000
    )
    assert budget.resolve_limit("other", **common) == 1_000


def test_a_declared_per_tool_cap_is_what_one_result_is_measured_against():
    turn = budget.TurnBudget(
        budget.BudgetThresholds(per_result_chars=50_000, per_turn_chars=200_000),
        registry_limits={"chatty": 2_000},
    )

    result = turn.add("call-1", "chatty", _lines(400))

    assert result.truncated is True
    assert result.chars <= 2_000
    assert result.original_chars == len(_lines(400))


def test_a_turn_over_its_aggregate_shrinks_its_largest_result_first():
    turn = budget.TurnBudget(
        budget.BudgetThresholds(per_result_chars=20_000, per_turn_chars=16_000)
    )
    turn.add("small", "web_search", _lines(20))
    turn.add("large", "fetch_url", _lines(150))

    rebalanced = turn.rebalance()
    by_id = {result.call_id: result for result in rebalanced}

    assert turn.total_chars <= 16_000
    assert by_id["large"].truncated is True
    assert by_id["small"].truncated is False
    # Order is the order the results arrived, whatever gave ground.
    assert [result.call_id for result in rebalanced] == ["small", "large"]


def test_rebalancing_stops_at_the_floor_instead_of_looping():
    turn = budget.TurnBudget(
        budget.BudgetThresholds(per_result_chars=4_000, per_turn_chars=1_000)
    )
    for index in range(4):
        turn.add(f"call-{index}", "web_search", _lines(30))

    rebalanced = turn.rebalance()

    assert len(rebalanced) == 4
    assert all(result.chars >= 1 for result in rebalanced)
    # Every result is at the floor and the aggregate is still over: that is a
    # fact about the budget, not a reason to keep cutting.
    assert turn.total_chars > 1_000
    assert all(result.chars <= budget.SPILL_FLOOR_CHARS * 2 for result in rebalanced)


def test_a_result_that_fits_is_left_alone_by_both_rungs():
    turn = budget.TurnBudget(
        budget.BudgetThresholds(per_result_chars=20_000, per_turn_chars=100_000)
    )
    text = _lines(10)

    turn.add("call-1", "session_search", text)
    rebalanced = turn.rebalance()

    assert rebalanced[0].text == text
    assert rebalanced[0].truncated is False


def test_a_tool_that_reshapes_keeps_its_own_selection_when_a_rung_shrinks_it():
    """Rung three asks the largest result to give ground, not to lose its point.

    The generic cut keeps the head, which for a page read is its navigation
    menu. A tool that declares how to narrow its result is asked instead, at
    both rungs, so the part the call went looking for survives the shrinking.
    """
    head = "menu " * 400
    body = f"{head}CLOSING PRICE 74,500 {'tail ' * 400}"

    def reshape(text: str, limit: int) -> str:
        assert text == body
        return "CLOSING PRICE 74,500"[:limit]

    turn = budget.TurnBudget(
        budget.BudgetThresholds(per_result_chars=1_500, per_turn_chars=1_000)
    )
    turn.add("page", "fetch_url", body, reshape=reshape)

    rebalanced = turn.rebalance()

    assert "74,500" in rebalanced[0].text
    assert rebalanced[0].original_chars == len(body)
    # A selection drawn from several places is not a preview that stopped
    # somewhere, so it carries no cursor.
    assert rebalanced[0].cursor is None


def test_a_reshaper_that_overruns_or_declines_falls_back_to_the_cut():
    text = _lines(60)
    turn = budget.TurnBudget(
        budget.BudgetThresholds(per_result_chars=1_000, per_turn_chars=100_000)
    )

    turn.add("declined", "fetch_url", text, reshape=lambda _text, _limit: "")
    turn.add("overran", "fetch_url", text, reshape=lambda text, _limit: text)

    by_id = {result.call_id: result for result in turn.results()}
    assert by_id["declined"].truncated is True
    assert by_id["overran"].truncated is True
    assert all(result.chars <= 1_000 for result in by_id.values())
