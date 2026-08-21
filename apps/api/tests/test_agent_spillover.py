"""Rungs two and three of the context-overflow defence, with no loop involved.

Two claims run through the file and pull against each other. A preview has to be
**smaller than the threshold** — otherwise the rung bought nothing — and it has
to **still say what the full result held**, because a model that cannot tell
what it lost asks the wrong next question. Every test here holds one of the two.
"""

from __future__ import annotations

from src.agent.tools.catalog import MAX_TOOL_RESULT_BYTES, serialized_size
from src.agent.tools.spillover import (
    DEFAULT_ROUND_CEILING_BYTES,
    DEFAULT_SPILL_THRESHOLD_BYTES,
    SPILL_REF_KEY,
    RoundResult,
    SpilloverBudget,
    spill_result,
    spill_round,
)

THRESHOLD = 1_024


def rows(count: int, *, width: int = 40) -> list[dict[str, object]]:
    return [
        {
            "date": f"2026-02-{(index % 28) + 1:02d}",
            "close_price": 20_000 + index,
            "note": "x" * width,
        }
        for index in range(count)
    ]


def big_result(count: int = 200) -> dict[str, object]:
    """A price-series-shaped result whose ``sample`` is what makes it big."""
    return {
        "symbol": "FPT",
        "as_of": "2026-02-20",
        "summary": {"sessions": count, "last_close_vnd": 20_000 + count},
        "sample": rows(count),
        "data_ref": {
            "id": "a3de5f",
            "symbol": "FPT",
            "start": "2025-08-20",
            "end": "2026-02-20",
            "field": "ohlcv",
        },
        "registered_fields": {
            "adtv_money": {"value": 1_234.5, "unit": "vnd", "as_of": "2026-02-20"}
        },
    }


def reference(preview) -> dict:
    return dict(preview[SPILL_REF_KEY])


def truncated_keys(preview) -> set[str]:
    return {record["key"] for record in reference(preview)["truncated"]}


def test_a_result_under_its_threshold_is_not_touched_at_all():
    result = {"symbol": "FPT", "as_of": "2026-02-20", "sample": rows(2)}

    assert spill_result("get_analysis", "call_1", result, threshold=THRESHOLD) is None


def test_a_spilled_preview_is_smaller_than_the_threshold_that_spilled_it():
    spilled = spill_result("get_price_series", "call_1", big_result(), threshold=THRESHOLD)

    assert spilled is not None
    assert spilled.preview_bytes <= THRESHOLD
    assert spilled.preview_bytes == serialized_size(spilled.preview)
    assert spilled.full_bytes == serialized_size(big_result())
    assert spilled.at_floor is False


def test_the_preview_keeps_the_shape_of_what_it_dropped():
    spilled = spill_result(
        "get_price_series", "call_1", big_result(200), threshold=THRESHOLD
    )

    assert spilled is not None
    record = next(
        item for item in reference(spilled.preview)["truncated"] if item["key"] == "sample"
    )
    assert record["kind"] == "list"
    # The count is the original one, not the length of what survived, and the
    # element keys survive the rows themselves.
    assert record["items"] == 200
    assert record["kept"] < 200
    assert set(record["item_keys"]) == {"close_price", "date", "note"}


def test_the_reference_names_the_call_the_full_result_belongs_to():
    spilled = spill_result(
        "get_price_series", "call_a3de", big_result(), threshold=THRESHOLD
    )

    assert spilled is not None
    assert reference(spilled.preview)["tool_call_id"] == "call_a3de"
    assert reference(spilled.preview)["tool"] == "get_price_series"
    assert reference(spilled.preview)["full_bytes"] == spilled.full_bytes


def test_the_grounding_and_widget_bindings_survive_a_spill_whole():
    spilled = spill_result("get_price_series", "call_1", big_result(), threshold=THRESHOLD)

    assert spilled is not None
    assert spilled.preview["registered_fields"] == big_result()["registered_fields"]
    assert spilled.preview["data_ref"] == big_result()["data_ref"]
    assert spilled.preview["symbol"] == "FPT"
    assert spilled.preview["as_of"] == "2026-02-20"


def test_a_refusal_envelope_is_never_the_thing_that_gets_truncated():
    result = {
        "symbol": "FPT",
        "reason": "not_in_universe",
        "window_health": {"status": "short", "sessions": 12},
        "candidates": rows(200),
    }

    spilled = spill_result("get_analysis", "call_1", result, threshold=THRESHOLD)

    assert spilled is not None
    assert spilled.preview["reason"] == "not_in_universe"
    assert spilled.preview["window_health"] == result["window_health"]
    assert truncated_keys(spilled.preview) == {"candidates"}


def test_the_largest_key_gives_ground_first_and_a_small_one_is_left_alone():
    result = {
        "symbol": "FPT",
        "headlines": rows(3, width=10),
        "sample": rows(200),
    }

    spilled = spill_result("get_analysis", "call_1", result, threshold=THRESHOLD)

    assert spilled is not None
    assert truncated_keys(spilled.preview) == {"sample"}
    assert spilled.preview["headlines"] == result["headlines"]


def test_a_long_string_is_clipped_and_says_so_in_characters():
    result = {"symbol": "FPT", "text": "y" * 5_000}

    spilled = spill_result("fetch_url", "call_1", result, threshold=THRESHOLD)

    assert spilled is not None
    record = next(item for item in reference(spilled.preview)["truncated"])
    assert record["kind"] == "text"
    assert record["chars"] == 5_000
    assert len(spilled.preview["text"]) <= record["kept"] + 1
    # A clipped sentence that looks finished is one the model will quote whole.
    assert spilled.preview["text"].endswith("…")


def test_a_threshold_the_envelope_alone_cannot_meet_reports_its_floor():
    result = {
        "symbol": "FPT",
        "registered_fields": {
            f"field_{index}": {"value": index, "unit": "ratio"} for index in range(40)
        },
        "sample": rows(50),
    }

    spilled = spill_result("risk_metrics", "call_1", result, threshold=200)

    assert spilled is not None
    assert spilled.at_floor is True
    assert reference(spilled.preview)["at_floor"] is True
    assert spilled.preview["registered_fields"] == result["registered_fields"]
    assert spilled.preview_bytes < spilled.full_bytes


def test_spilling_a_preview_again_still_reports_the_original_size_and_counts():
    once = spill_result("get_price_series", "call_1", big_result(200), threshold=THRESHOLD)

    assert once is not None
    twice = spill_result("get_price_series", "call_1", once.preview, threshold=400)

    assert twice is not None
    assert twice.full_bytes == once.full_bytes
    record = next(
        item for item in reference(twice.preview)["truncated"] if item["key"] == "sample"
    )
    assert record["items"] == 200
    assert record["kept"] < next(
        item for item in reference(once.preview)["truncated"] if item["key"] == "sample"
    )["kept"]


def test_it_is_pure_and_the_same_result_spills_the_same_way_every_time():
    result = big_result()

    once = spill_result("get_price_series", "call_1", result, threshold=THRESHOLD)
    twice = spill_result("get_price_series", "call_1", result, threshold=THRESHOLD)

    assert once == twice
    assert result == big_result()


def test_the_threshold_ladder_prefers_pinned_then_registry_then_default():
    # The registry rung arrives as ``per_tool``, built by the caller from the
    # Tool Catalog's own declarations — there is no table in this module for the
    # catalog to disagree with.
    budget = SpilloverBudget(per_tool={"fetch_url": 4096})

    assert budget.threshold_for("get_analysis") == DEFAULT_SPILL_THRESHOLD_BYTES
    assert budget.threshold_for("fetch_url") == 4096
    assert budget.threshold_for("fetch_url", pinned=512) == 512


def test_a_tool_that_declared_nothing_falls_back_to_the_default():
    budget = SpilloverBudget(per_tool={"get_analysis": 128})

    assert budget.threshold_for("get_analysis") == 128
    assert budget.threshold_for("fetch_url") == DEFAULT_SPILL_THRESHOLD_BYTES


def test_a_round_of_small_results_is_returned_untouched():
    results = [
        RoundResult("call_1", "get_analysis", {"symbol": "FPT", "sample": rows(2)}),
        RoundResult("call_2", "get_analysis", {"symbol": "VNM", "sample": rows(2)}),
    ]

    round_spill = spill_round(results)

    assert round_spill.spilled == ()
    assert round_spill.over_ceiling is False
    assert round_spill.results["call_1"] == results[0].result
    assert round_spill.results["call_2"] == results[1].result


def test_every_call_of_a_round_comes_back_whether_it_spilled_or_not():
    results = [
        RoundResult("call_1", "get_price_series", big_result(300)),
        RoundResult("call_2", "get_analysis", {"symbol": "VNM", "sample": rows(2)}),
    ]

    round_spill = spill_round(results)

    assert set(round_spill.results) == {"call_1", "call_2"}
    assert [record.call_id for record in round_spill.spilled] == ["call_1"]
    assert round_spill.results["call_2"] == results[1].result


def test_a_result_over_its_own_threshold_spills_before_the_round_is_measured():
    results = [RoundResult("call_1", "get_price_series", big_result(300))]

    round_spill = spill_round(results)

    assert serialized_size(round_spill.results["call_1"]) <= DEFAULT_SPILL_THRESHOLD_BYTES
    assert round_spill.spilled[0].full_bytes > DEFAULT_SPILL_THRESHOLD_BYTES
    assert round_spill.total_bytes <= DEFAULT_ROUND_CEILING_BYTES


def test_a_round_over_its_ceiling_spills_the_largest_result_first():
    budget = SpilloverBudget(
        default_bytes=MAX_TOOL_RESULT_BYTES,
        per_tool={},
        round_bytes=3_000,
    )
    results = [
        RoundResult("call_small", "get_analysis", {"symbol": "FPT", "sample": rows(8)}),
        RoundResult("call_large", "screen_universe", {"symbol": "VNM", "sample": rows(60)}),
    ]

    round_spill = spill_round(results, budget=budget)

    assert round_spill.total_bytes <= 3_000
    assert [record.call_id for record in round_spill.spilled] == ["call_large"]
    assert round_spill.results["call_small"] == results[0].result
    assert round_spill.over_ceiling is False


def test_a_round_keeps_spilling_until_it_is_under_the_ceiling():
    budget = SpilloverBudget(
        default_bytes=MAX_TOOL_RESULT_BYTES,
        per_tool={},
        round_bytes=1_500,
    )
    results = [
        RoundResult(f"call_{index}", "get_analysis", {"symbol": "FPT", "sample": rows(30)})
        for index in range(4)
    ]

    round_spill = spill_round(results, budget=budget)

    assert round_spill.total_bytes <= 1_500
    assert len(round_spill.spilled) > 1
    assert round_spill.over_ceiling is False


def test_a_round_that_cannot_be_made_to_fit_says_so_instead_of_looping():
    budget = SpilloverBudget(round_bytes=10)
    results = [
        RoundResult(
            "call_1",
            "risk_metrics",
            {
                "symbol": "FPT",
                "registered_fields": {
                    f"field_{index}": {"value": index} for index in range(20)
                },
            },
        )
    ]

    round_spill = spill_round(results, budget=budget)

    assert round_spill.over_ceiling is True
    assert round_spill.total_bytes > 10
    assert round_spill.results["call_1"]["registered_fields"] == (
        results[0].result["registered_fields"]
    )


def test_running_a_round_twice_over_its_own_output_changes_nothing_further():
    budget = SpilloverBudget(round_bytes=3_000)
    results = [
        RoundResult(f"call_{index}", "get_price_series", big_result(120))
        for index in range(3)
    ]

    once = spill_round(results, budget=budget)
    twice = spill_round(
        [
            RoundResult(call_id, "get_price_series", result)
            for call_id, result in once.results.items()
        ],
        budget=budget,
    )

    assert twice.spilled == ()
    assert dict(twice.results) == dict(once.results)


def test_a_declared_tool_is_not_shrunk_past_its_declaration_by_the_round():
    # The failure this pins: rung three sorts largest-first, so the tools that
    # declare the full cap are the first ones it reaches for. ``get_financials``
    # declares it because its periods list is both the answer and a Widget
    # binding — a round that previewed it would answer eight quarters with three.
    budget = SpilloverBudget(
        default_bytes=600,
        per_tool={"get_financials": MAX_TOOL_RESULT_BYTES},
        round_bytes=1_000,
    )
    periods = [
        {"period_end": f"2026-{month:02d}-30", "figures": {"revenue_vnd": 1_000.0 * month}}
        for month in range(1, 9)
    ]
    results = [
        RoundResult("call_1", "get_financials", {"symbol": "MSN", "periods": periods}),
        RoundResult("call_2", "get_analysis", {"symbol": "FPT", "sample": rows(20)}),
    ]

    round_spill = spill_round(results, budget=budget)

    # Every quarter survives, and the undeclared sibling is what gave ground.
    assert round_spill.results["call_1"]["periods"] == periods
    assert [record.call_id for record in round_spill.spilled] == ["call_2"]
    assert round_spill.total_bytes <= 1_000


def test_an_undeclared_tool_is_still_reduced_by_the_round_ceiling():
    # The other half of the same rule: the default is the *absence* of a
    # declaration, so rung three may reduce past it.
    budget = SpilloverBudget(default_bytes=MAX_TOOL_RESULT_BYTES, per_tool={}, round_bytes=900)
    results = [
        RoundResult(f"call_{index}", "get_analysis", {"symbol": "FPT", "sample": rows(20)})
        for index in range(3)
    ]

    round_spill = spill_round(results, budget=budget)

    assert round_spill.total_bytes <= 900
    assert round_spill.over_ceiling is False
