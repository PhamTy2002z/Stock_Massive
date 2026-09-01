"""The ceilings a Turn runs under, and the routing that picks them.

Two properties are worth a test each, and neither is visible at runtime.

The first is that the light lane *is* what this system has always done. Its
numbers are the constants the loop, the service and the ledger were written
around, so the two are compared here rather than described in a comment: a Turn
that nothing routed anywhere has to behave exactly as it did before lanes
existed, and the only way that claim stays true is if a build that edits one side
fails.

The second is that routing is a decision and not a guess. It reads no store,
makes no call and returns the same lane and the same reason for the same
question every time, which is what makes a misroute a cheap mistake instead of a
mystery.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.agent.lanes import (
    DEEP,
    DEEP_KEYWORDS,
    DEEP_MIN_CHARS,
    DEFAULT_REASON,
    LIGHT,
    LaneProfile,
    route_intent,
    route_reason,
)
from src.agent import loop as agent_loop
from src.agent import turns as agent_turns
from src.core.llm.admission import (
    TURN_INPUT_TOTAL,
    TURN_INPUT_TOTAL_MAX,
    TURN_OUTPUT_TOTAL,
    TURN_OUTPUT_TOTAL_MAX,
)


# -- the arithmetic ----------------------------------------------------------


@pytest.mark.parametrize("lane", [LIGHT, DEEP], ids=lambda lane: lane.name)
def test_a_lanes_output_total_funds_exactly_the_calls_it_allows(
    lane: LaneProfile,
) -> None:
    # The one piece of arithmetic: a Turn makes at most one call per round plus
    # the answering one, each at the per-call ceiling, and is admitted against
    # the total.
    assert lane.owner_output_total == (lane.max_tool_rounds + 1) * lane.max_output_tokens


def test_a_profile_whose_total_does_not_fund_its_rounds_cannot_be_built() -> None:
    with pytest.raises(ValueError) as refused:
        replace(LIGHT, max_tool_rounds=LIGHT.max_tool_rounds + 1)

    # And it says which number to change, because the fix is arithmetic.
    assert "aggregate output" in str(refused.value)


@pytest.mark.parametrize(
    "field",
    [
        "max_tool_rounds",
        "max_external_calls",
        "max_output_tokens",
        "owner_output_total",
        "owner_input_total",
    ],
)
def test_a_ceiling_of_zero_is_not_a_lane(field: str) -> None:
    with pytest.raises(ValueError):
        replace(LIGHT, **{field: 0})


def test_a_lane_with_no_wall_clock_is_not_a_lane() -> None:
    with pytest.raises(ValueError):
        replace(LIGHT, deadline_seconds=0.0)


# -- the light lane is today -------------------------------------------------


def test_the_light_lane_is_the_ceilings_this_build_already_ran() -> None:
    assert LIGHT.max_tool_rounds == agent_loop.MAX_TOOL_ROUNDS
    assert LIGHT.max_external_calls == agent_loop.MAX_EXTERNAL_TOOL_CALLS
    assert LIGHT.max_output_tokens == agent_loop.DEFAULT_MAX_OUTPUT_TOKENS
    assert LIGHT.deadline_seconds == agent_loop.TURN_DEADLINE_SECONDS
    # The service's own hard ``wait_for`` and the loop's between-round check are
    # the same wall clock seen from two sides, so they are one number.
    assert LIGHT.deadline_seconds == agent_turns.TURN_DEADLINE_SECONDS
    assert LIGHT.owner_output_total == TURN_OUTPUT_TOTAL
    assert LIGHT.owner_input_total == TURN_INPUT_TOTAL


def test_the_note_on_the_ceiling_names_the_lanes_own_rounds() -> None:
    assert agent_loop.rounds_exhausted_note(LIGHT.max_tool_rounds) == (
        agent_loop.ROUNDS_EXHAUSTED_NOTE
    )
    assert str(DEEP.max_tool_rounds) in agent_loop.rounds_exhausted_note(
        DEEP.max_tool_rounds
    )


def test_the_deep_lane_stays_inside_what_the_ledger_will_grant() -> None:
    # A lane above these would be clamped by admission, which would make the
    # profile's arithmetic a claim the ledger quietly declines to honour.
    assert DEEP.owner_output_total <= TURN_OUTPUT_TOTAL_MAX
    assert DEEP.owner_input_total <= TURN_INPUT_TOTAL_MAX
    # Deep buys rounds of evidence, not a longer reply.
    assert DEEP.max_output_tokens == LIGHT.max_output_tokens
    assert DEEP.max_tool_rounds > LIGHT.max_tool_rounds


# -- routing -----------------------------------------------------------------


def test_an_ordinary_question_gets_the_light_lane() -> None:
    lane, reason = route_reason("Giá VCB hôm nay bao nhiêu?")

    assert lane is LIGHT
    assert reason == DEFAULT_REASON


def test_nothing_asked_is_still_a_lane() -> None:
    assert route_intent("") is LIGHT


@pytest.mark.parametrize("keyword", DEEP_KEYWORDS)
def test_a_question_that_asks_for_verification_gets_the_deep_lane(
    keyword: str,
) -> None:
    lane, reason = route_reason(f"Giúp tôi {keyword} chuyện này với.")

    assert lane is DEEP
    # The reason names the keyword, so an operator reading a Turn that spent ten
    # rounds can see what bought them.
    assert reason == f"keyword:{keyword}"


def test_the_keyword_is_read_however_it_was_typed() -> None:
    lane, reason = route_reason("  Viết một   MEMO về FPT  ")

    assert lane is DEEP
    assert reason == "keyword:memo"


def test_a_question_long_enough_to_be_a_brief_gets_the_deep_lane() -> None:
    # No keyword anywhere in it: the length alone is the memo shape spelled out.
    asked = (
        "Tôi đang cân nhắc tăng tỷ trọng cổ phiếu ngân hàng trong nửa cuối năm "
        "và muốn hiểu vì sao NIM của nhóm này vẫn giảm dù tín dụng tăng, nợ xấu "
        "nhóm hai đang đi đâu, và điều gì sẽ xảy ra với thu nhập ngoài lãi nếu "
        "lãi suất huy động tiếp tục nhích lên trong vài quý tới."
    )
    assert len(asked) >= DEEP_MIN_CHARS
    assert not any(keyword in asked.casefold() for keyword in DEEP_KEYWORDS)

    lane, reason = route_reason(asked)

    assert lane is DEEP
    assert reason == f"length:{len(asked)}"


def test_blank_space_is_not_length() -> None:
    # A pasted block of line breaks is not a reader who wrote four paragraphs.
    padded = "Giá VCB?" + "\n" * (DEEP_MIN_CHARS * 2)

    lane, reason = route_reason(padded)

    assert lane is LIGHT
    assert reason == DEFAULT_REASON


def test_the_same_question_always_gets_the_same_lane_and_reason() -> None:
    asked = "Hãy kiểm chứng luận điểm rằng biên lãi ròng đã tạo đáy."

    first = route_reason(asked)
    second = route_reason(asked)

    assert first == second
    # First match wins, and the order of the keyword list is what decides it.
    assert first[1] == "keyword:kiểm chứng"


def test_the_short_form_answers_the_same_question_as_the_long_one() -> None:
    for asked in ("Giá VCB?", "Viết memo về FPT", "kiểm chứng số này"):
        assert route_intent(asked) is route_reason(asked)[0]
