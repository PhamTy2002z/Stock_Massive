"""The Recommendation Validator: an unprovable block is never displayed (#82)."""

from __future__ import annotations

import re
from datetime import date

import pytest

from src.agent.blocks import split_blocks
from src.agent.context import TranscriptToolCall
from src.agent.grounding import (
    GROUNDING_FAILED,
    BlockKind,
    EvidenceRef,
    EvidenceSource,
    GroundingFailure,
    RecommendationValidator,
    TraceIndex,
    display_text,
    figures_agree,
)
from src.agent.tools.fields import serialize_registered_field

TRADING_DAY = date(2026, 8, 14)
RSI = "indicator_pack.rsi_14"
ZONE = "price_zone.ordinary_range_pct"
DRAWDOWN = "drawdown_stats.current_drawdown_pct"


def registered(
    name: str,
    value: float | None,
    *,
    refusal: str | None = None,
    degraded: str | None = None,
    health_refusal: str | None = None,
) -> dict:
    """One registered field exactly as the Tool Catalog serializes it."""
    return {
        **serialize_registered_field(name, value=value, refusal=refusal),
        "degraded_reason": degraded,
        "window_health": {"refusal": health_refusal, "last_session": "2026-08-14"},
    }


def computation(symbol: str = "FPT", **fields) -> dict:
    return {
        "symbol": symbol,
        "as_of": TRADING_DAY.isoformat(),
        "registered_fields": dict(fields),
    }


def quote(symbol: str = "FPT", close: float = 95.4) -> dict:
    return {
        "symbol": symbol,
        "quote": {
            "close_price": close,
            "as_of": TRADING_DAY.isoformat(),
            "age_days": 0,
            "stale": False,
        },
    }


def news(symbol: str = "FPT", value: str = "tăng trưởng 30") -> dict:
    return {
        "symbol": symbol,
        "window_days": 7,
        "count": 1,
        "stale": False,
        "age_seconds": 10,
        "reason": None,
        "items": [
            {
                "untrusted_evidence": {
                    "source": "CafeF",
                    "published_at": "2026-08-13T09:00:00+00:00",
                    "claim_class": "source_claim",
                    "title": "FPT báo lãi",
                    "content": value,
                }
            }
        ],
    }


def traces(**results) -> TraceIndex:
    return TraceIndex(
        [
            TranscriptToolCall(
                call_id=call_id,
                name="indicator_pack" if call_id == "c1" else call_id,
                arguments={"symbol": "FPT"},
                result=result,
            )
            for call_id, result in results.items()
        ]
    )


def standard_traces() -> TraceIndex:
    return traces(
        c1=computation(
            **{
                RSI: registered(RSI, 61.2),
                ZONE: registered(ZONE, 4.5),
                DRAWDOWN: registered(DRAWDOWN, -12.5),
            }
        ),
        c2=quote(),
        c3=news(),
    )


def validator() -> RecommendationValidator:
    return RecommendationValidator(trading_day=TRADING_DAY)


RECOMMENDATION = (
    "[rec:FPT@2026-08-14] Giá tham chiếu 95.4 [ref-price:c2#quote.close_price]. "
    f"RSI 61.2 [ev:c1#registered_fields.{RSI}.value] cho thấy đà tăng còn nguyên. "
    f"Vùng dao động thường ngày 4.5 [zone:tich_luy@c1#registered_fields.{ZONE}.value]. "
    f"Chiều ngược lại, mức giảm -12.5 [against:c1#registered_fields.{DRAWDOWN}.value]."
)


# --- attribution -----------------------------------------------------------


def test_a_material_figure_with_no_reference_downgrades_prose():
    block = validator().validate("RSI hiện ở 61.2, khá cao.", standard_traces())

    assert block.kind is BlockKind.PROSE
    assert block.unverified_figures == ("61.2",)


def test_one_reference_cannot_attribute_two_figures():
    text = f"RSI 61.2 và ngưỡng 61.2 [ev:c1#registered_fields.{RSI}.value]."

    block = validator().validate(text, standard_traces())

    assert block.unverified_figures == ("61.2",)
    assert len(block.citations) == 1


def test_a_recommendation_with_an_unreferenced_figure_is_still_blocked():
    text = f"{RECOMMENDATION} Mục tiêu 110."

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "unreferenced_figure"
    assert raised.value.reason == GROUNDING_FAILED


def test_a_trading_day_and_a_list_number_are_not_material_figures():
    block = validator().validate(
        "1. Dữ liệu tới 2026-08-14 chưa có thay đổi đáng kể.", standard_traces()
    )

    assert block.kind is BlockKind.PROSE
    assert block.citations == ()


def test_a_session_named_the_way_its_reader_writes_it_is_not_a_figure():
    """`14/08` is a date, exactly as `2026-08-14` is.

    The Contract answers in Vietnamese and tells the model to name the session
    it answered from, so this is the most ordinary sentence the product writes.
    Read as the two numbers either side of a slash it is unattributable, and an
    unattributable block does not lose its citation — it ends the Turn.
    """
    block = validator().validate(
        "Phiên 14/08 chưa có thay đổi đáng kể so với 13/08/2026.", standard_traces()
    )

    assert block.kind is BlockKind.PROSE
    assert block.citations == ()


def test_a_price_written_with_thousands_dots_is_the_price_it_says():
    """`71.800` is seventy-one thousand eight hundred, not seventy-one point eight.

    A dot groups thousands and a comma is the decimal separator in the language
    this product answers in. Parsed the other way round, a correctly written
    share price disagrees with its own trace by a factor of a thousand and the
    block is blocked for a mismatch its writer cannot see.
    """
    index = traces(c2=quote(close=71_800))

    block = validator().validate(
        "Giá đóng cửa 71.800 đồng [ev:c2#quote.close_price].", index
    )

    assert block.citations[0].value == 71_800
    assert not figures_agree("71.8", 71_800, unit=None)


def test_a_figure_that_disagrees_with_its_trace_is_blocked():
    text = f"RSI đang là 71.2 [ev:c1#registered_fields.{RSI}.value]."

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "figure_mismatch"


def test_a_figure_is_compared_at_the_precision_it_was_written_to():
    index = traces(c1=computation(**{RSI: registered(RSI, 61.2487)}))

    block = validator().validate(
        f"RSI 61.2 [ev:c1#registered_fields.{RSI}.value].", index
    )

    assert block.citations[0].value == pytest.approx(61.2487)


def test_money_matches_at_a_scale_and_a_z_score_does_not():
    assert figures_agree("3.4", 3_400_000_000, unit="vnd")
    assert not figures_agree("3.4", 3_400_000_000, unit="z_score")
    # Both separator conventions, and a scale is not what carries either of
    # them: a stored figure cites no unit at all, so the parse has to be right
    # on its own.
    assert figures_agree("71.800", 71_800, unit=None)
    assert figures_agree("71,800", 71_800, unit=None)
    assert figures_agree("2,3", 2.3, unit="percent")


# --- reference resolution --------------------------------------------------


def test_a_reference_to_a_call_this_turn_did_not_make_fails():
    with pytest.raises(GroundingFailure) as raised:
        standard_traces().resolve(EvidenceRef(call_id="c9", field_path="a.b"))

    assert raised.value.code == "unknown_tool_call"


def test_a_reference_into_a_refused_tool_result_fails():
    index = traces(c1={"reason": "not_in_universe", "suggestions": []})

    with pytest.raises(GroundingFailure) as raised:
        index.resolve(EvidenceRef(call_id="c1", field_path="anything"))

    assert raised.value.code == "refused_tool_call"


def test_a_dotted_registered_field_name_resolves_as_one_key():
    citation = standard_traces().resolve(
        EvidenceRef(call_id="c1", field_path=f"registered_fields.{RSI}.value")
    )

    assert citation.value == 61.2
    assert citation.unit == "index_0_100"
    assert citation.interpretation
    assert citation.claim == "descriptive"
    assert citation.as_of == "2026-08-14"
    assert citation.source is EvidenceSource.REGISTERED_FIELD


@pytest.mark.parametrize(
    "key, replacement, code",
    [
        ("unit", "percent", "unit_mismatch"),
        ("claim", "predictive", "claim_mismatch"),
        ("interpretation", "Đi lên là tốt.", "interpretation_mismatch"),
        ("source", "stored", "source_mismatch"),
    ],
)
def test_a_serialization_that_disagrees_with_the_registry_is_refused(
    key, replacement, code
):
    field = registered(RSI, 61.2)
    field[key] = replacement
    index = traces(c1=computation(**{RSI: field}))

    with pytest.raises(GroundingFailure) as raised:
        index.resolve(EvidenceRef(call_id="c1", field_path=f"registered_fields.{RSI}.value"))

    assert raised.value.code == code


def test_a_registered_field_without_a_date_carries_no_staleness():
    result = computation(**{RSI: registered(RSI, 61.2)})
    result.pop("as_of")
    result["registered_fields"][RSI]["window_health"] = {"refusal": None}
    index = traces(c1=result)

    with pytest.raises(GroundingFailure) as raised:
        index.resolve(EvidenceRef(call_id="c1", field_path=f"registered_fields.{RSI}.value"))

    assert raised.value.code == "missing_as_of"


def test_a_news_figure_is_marked_as_an_unverified_source_claim():
    citation = standard_traces().resolve(
        EvidenceRef(call_id="c3", field_path="items.0.untrusted_evidence.content")
    )

    assert citation.source is EvidenceSource.SOURCE_CLAIM
    assert citation.provenance == "CafeF"


def test_an_open_web_figure_remains_an_external_claim():
    index = traces(
        web={
            "results": [
                {
                    "title": "Leadership",
                    "value": 2026,
                    "source": "Example Exchange",
                    "retrieved_at": "2026-08-17T00:00:00+00:00",
                    "claim_class": "external_claim",
                }
            ]
        }
    )

    citation = index.resolve(EvidenceRef("web", "results.0.value"))

    assert citation.source is EvidenceSource.EXTERNAL_CLAIM
    assert citation.provenance == "Example Exchange"
    assert citation.as_of == "2026-08-17T00:00:00+00:00"


def test_a_user_supplied_number_is_marked_user_input_and_needs_no_trace():
    block = validator().validate(
        "Với giả định vốn 100 [user:von_gia_dinh] triệu đồng.", standard_traces()
    )

    assert block.citations[0].source is EvidenceSource.USER_INPUT
    assert block.citations[0].provenance == "user_input"


# --- the seven Gate conditions, each failing alone -------------------------


def test_a_complete_recommendation_is_released():
    block = validator().validate(RECOMMENDATION, standard_traces())

    assert block.kind is BlockKind.RECOMMENDATION
    assert block.symbol == "FPT"
    assert block.trading_day == "2026-08-14"
    assert "[ev:" not in block.text and "[rec:" not in block.text
    assert any(citation.contradictory for citation in block.citations)
    assert any(citation.zone_label == "tich_luy" for citation in block.citations)


def test_one_a_symbol_the_tool_layer_never_served_fails_the_gate():
    index = traces(
        c1=computation(symbol="VNM", **{RSI: registered(RSI, 61.2), ZONE: registered(ZONE, 4.5), DRAWDOWN: registered(DRAWDOWN, -12.5)}),
        c2=quote(symbol="VNM"),
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(RECOMMENDATION, index)

    assert raised.value.code == "symbol_not_in_universe"


def test_two_a_trading_day_that_is_not_this_turns_fails_the_gate():
    with pytest.raises(GroundingFailure) as raised:
        validator().validate(
            RECOMMENDATION.replace("2026-08-14]", "2026-08-13]"), standard_traces()
        )

    assert raised.value.code == "trading_day_mismatch"


def test_two_a_recommendation_without_a_reference_price_fails_the_gate():
    text = RECOMMENDATION.replace(
        "Giá tham chiếu 95.4 [ref-price:c2#quote.close_price]. ", ""
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "missing_reference_price"


def test_three_a_price_zone_that_is_not_a_registered_field_fails_the_gate():
    text = RECOMMENDATION.replace(
        f"[zone:tich_luy@c1#registered_fields.{ZONE}.value]",
        "[zone:tich_luy@c2#quote.close_price]",
    ).replace("Vùng dao động thường ngày 4.5", "Vùng dao động thường ngày 95.4")

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "unregistered_price_zone"


def test_three_a_recommendation_with_no_price_zone_at_all_fails_the_gate():
    text = RECOMMENDATION.replace(
        f"Vùng dao động thường ngày 4.5 [zone:tich_luy@c1#registered_fields.{ZONE}.value]. ",
        "",
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "missing_price_zone"


def test_four_a_refusal_level_window_health_blocks_the_recommendation():
    index = traces(
        c1=computation(
            **{
                RSI: registered(RSI, 61.2, health_refusal="insufficient_sessions"),
                ZONE: registered(ZONE, 4.5),
                DRAWDOWN: registered(DRAWDOWN, -12.5),
            }
        ),
        c2=quote(),
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(RECOMMENDATION, index)

    assert raised.value.code == "window_health_refusal"


def test_five_a_verdict_that_only_names_levels_cites_nothing_for_itself():
    """Every other condition holds; only the supporting field is missing."""
    text = (
        "[rec:FPT@2026-08-14] Giá tham chiếu 95.4 [ref-price:c2#quote.close_price]. "
        f"Vùng dao động thường ngày 4.5 [zone:tich_luy@c1#registered_fields.{ZONE}.value]. "
        f"Chiều ngược lại, mức giảm -12.5 [against:c1#registered_fields.{DRAWDOWN}.value]."
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "no_supporting_field"


def test_five_a_verdict_with_no_contradictory_evidence_fails_the_gate():
    text = RECOMMENDATION.replace(
        f"Chiều ngược lại, mức giảm -12.5 [against:c1#registered_fields.{DRAWDOWN}.value].",
        "",
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "no_contradictory_evidence"


def test_six_a_cited_field_with_no_value_fails_the_gate():
    """The reference resolves; the Gate refuses it for what it does not carry."""
    index = traces(
        c1=computation(
            **{
                RSI: registered(RSI, None),
                ZONE: registered(ZONE, 4.5),
                DRAWDOWN: registered(DRAWDOWN, -12.5),
            }
        ),
        c2=quote(),
        c3=news(),
    )
    # Cited at the field rather than at its value, so resolution succeeds and
    # hands the Gate a citation whose value is None.
    text = RECOMMENDATION.replace(
        f"RSI 61.2 [ev:c1#registered_fields.{RSI}.value]",
        f"RSI chưa tính được [ev:c1#registered_fields.{RSI}]",
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, index)

    assert raised.value.code == "incomplete_citation"
    assert "value" in raised.value.detail


def test_seven_news_cannot_carry_a_price_zone_by_itself():
    text = RECOMMENDATION.replace(
        f"Vùng dao động thường ngày 4.5 [zone:tich_luy@c1#registered_fields.{ZONE}.value]",
        "Vùng theo tin [zone:tich_luy@c3#items.0.untrusted_evidence.title]",
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "news_only_basis"


def test_seven_news_cannot_carry_the_reference_price_either():
    text = RECOMMENDATION.replace(
        "Giá tham chiếu 95.4 [ref-price:c2#quote.close_price]",
        "Giá tham chiếu theo tin [ref-price:c3#items.0.untrusted_evidence.title]",
    )

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(text, standard_traces())

    assert raised.value.code == "news_only_basis"


# --- block splitting -------------------------------------------------------


def test_a_fenced_block_is_never_split_across_its_blank_lines():
    text = "Mở đầu.\n\n```\nmột\n\nhai\n```\n\nKết."

    assert split_blocks(text) == ("Mở đầu.", "```\nmột\n\nhai\n```", "Kết.")


def test_a_bullet_group_and_a_table_each_stay_one_block():
    text = "- một\n- hai\n\n| a | b |\n| - | - |\n| 1 | 2 |"

    blocks = split_blocks(text)

    assert len(blocks) == 2
    assert blocks[0].count("\n") == 1
    assert blocks[1].startswith("| a | b |")


def test_the_markers_never_reach_the_reader():
    rendered = display_text(
        f"RSI 61.2 [ev:c1#registered_fields.{RSI}.value] là trung tính."
    )

    assert rendered == "RSI 61.2 là trung tính."


def test_an_availability_failure_is_degradable_and_an_integrity_one_is_not():
    """The two classes of Gate failure, told apart by what the reader gets.

    Both keep the block off the screen. Only the availability class lets the
    Turn go on and say what was missing, because "no registered price zone
    could be computed" is an answer while a blank Turn is not — and the figure
    that contradicts its own citation stays in the class that ends the Turn.
    """
    missing_zone = RECOMMENDATION.replace(
        f"Vùng dao động thường ngày 4.5 [zone:tich_luy@c1#registered_fields.{ZONE}.value]. ",
        "",
    )

    with pytest.raises(GroundingFailure) as availability:
        validator().validate(missing_zone, standard_traces())

    assert availability.value.code == "missing_price_zone"
    assert availability.value.degradable is True
    notice = availability.value.notice()
    assert "vùng giá" in notice
    # The notice is the backend's own sentence, so it may not carry a figure:
    # nothing validates it, and a number in it would be a number nobody proved.
    assert not re.search(r"\d", notice.replace("{", "").replace("}", ""))

    mismatched = RECOMMENDATION.replace("Giá tham chiếu 95.4", "Giá tham chiếu 128.0")

    with pytest.raises(GroundingFailure) as integrity:
        validator().validate(mismatched, standard_traces())

    assert integrity.value.code == "figure_mismatch"
    assert integrity.value.degradable is False
    assert integrity.value.notice() == ""


def test_a_fullwidth_bracket_marker_attributes_and_never_reaches_the_reader():
    """A Vietnamese answer writes 【ev:…】, and it has to count as the citation.

    Measured on a real Turn: nine figures, every one attributed with fullwidth
    brackets, and the ASCII-only pattern matched none of them — so nine correct
    citations were reported as unattributed and the markers were displayed as
    part of the sentence.
    """
    text = (
        f"Vùng dao động thường ngày 4.5【ev:c1#registered_fields.{ZONE}.value】 "
        f"và mức giảm -12.5【ev:c1#registered_fields.{DRAWDOWN}.value】."
    )

    released = validator().validate(text, standard_traces())

    assert released.unverified_figures == ()
    assert len(released.citations) == 2
    assert "【" not in released.text and "ev:" not in released.text
    assert "4.5" in released.text and "-12.5" in released.text


def test_a_marker_written_without_its_kind_still_attributes_the_figure():
    """The model dropped the `ev:` prefix; the reference is still a reference.

    Inferred as plain evidence, which is the weakest kind: it attributes the
    figure in front of it and can never stand in for a zone, a reference price
    or the contradictory citation the Gate requires.
    """
    text = f"Vùng dao động thường ngày 4.5【c1#registered_fields.{ZONE}.value】."

    released = validator().validate(text, standard_traces())

    assert released.unverified_figures == ()
    assert len(released.citations) == 1
    assert released.citations[0].zone_label is None
    assert released.citations[0].reference_price is False
    assert "【" not in released.text


def test_an_inferred_marker_that_resolves_to_nothing_costs_only_its_figure():
    """A forgotten prefix must not end a Turn the model otherwise answered.

    An explicit `[ev:…]` naming a call that does not exist is the model
    breaking its own protocol and still fails. An inferred one was never a
    promise, so the figure falls back to unattributed — the same place it
    would be with no marker at all.
    """
    text = "Vùng dao động thường ngày 4.5【c9#registered_fields.nothing.here】."

    released = validator().validate(text, standard_traces())

    assert released.unverified_figures == ("4.5",)
    assert released.citations == ()
    assert "【" not in released.text

    explicit = "Vùng dao động thường ngày 4.5 [ev:c9#registered_fields.nothing.here]."

    with pytest.raises(GroundingFailure):
        validator().validate(explicit, standard_traces())


def test_ordinary_bracketed_prose_is_never_read_as_a_reference():
    """The inference is shaped to a reference, so prose keeps its brackets."""
    text = "Thị trường đóng cửa【ghi chú của người đọc】và không có số liệu nào."

    released = validator().validate(text, standard_traces())

    assert "ghi chú của người đọc" in released.text


def test_a_figure_that_disagrees_with_an_inferred_reference_is_labelled_not_fatal():
    """A guess that turns out wrong costs the figure its attribution, nothing more.

    The explicit form keeps the guarantee that matters: a figure contradicting
    a reference the model actually wrote still ends the Turn.
    """
    text = f"Vùng dao động thường ngày 99.9【c1#registered_fields.{ZONE}.value】."

    released = validator().validate(text, standard_traces())

    assert released.unverified_figures == ("99.9",)
    assert "【" not in released.text

    explicit = f"Vùng dao động thường ngày 99.9 [ev:c1#registered_fields.{ZONE}.value]."

    with pytest.raises(GroundingFailure) as raised:
        validator().validate(explicit, standard_traces())

    assert raised.value.code == "figure_mismatch"
