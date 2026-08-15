"""build_messages() and the trimming ladder, with no LLM involved (#79)."""

from __future__ import annotations

import pytest

from src.agent.context import (
    SUMMARY_LABEL,
    ConstructedContextTooLarge,
    ContextBudget,
    Transcript,
    TranscriptToolCall,
    TranscriptTurn,
    build_messages,
)
from src.core.llm.admission import TURN_CONTEXT_PER_CALL
from src.core.llm.protocol import Role

SYSTEM_PROMPT = "## 1. Mission\n\nYou are Alpha Desk."


def call(index: int, *, size: int = 1200) -> TranscriptToolCall:
    return TranscriptToolCall(
        call_id=f"call_{index}",
        name="get_price_series",
        arguments={"symbol": "FPT", "window_days": 90},
        result={"summary": "x" * size},
    )


def turn(index: int, *, calls: int = 2, size: int = 1200) -> TranscriptTurn:
    return TranscriptTurn(
        user_text=f"Hỏi lần {index} về FPT",
        tool_calls=tuple(call(index * 10 + n, size=size) for n in range(calls)),
        assistant_text=f"Trả lời lần {index}",
    )


def transcript(count: int, **overrides) -> Transcript:
    base = dict(
        system_prompt=SYSTEM_PROMPT,
        turns=tuple(turn(index) for index in range(count)),
    )
    base.update(overrides)
    return Transcript(**base)


def roles(result) -> list[Role]:
    return [message.role for message in result.messages]


def test_it_is_pure_and_returns_the_same_list_for_the_same_inputs():
    once = build_messages(transcript(4))
    twice = build_messages(transcript(4))

    assert once == twice
    assert once.messages == twice.messages


def test_a_short_thread_survives_intact_with_nothing_collapsed():
    result = build_messages(transcript(2))

    assert result.turns_dropped == 0
    assert result.results_collapsed == 0
    assert result.summary_needed is False
    assert result.summary_used is False
    assert result.estimated_tokens <= TURN_CONTEXT_PER_CALL


def test_the_system_prompt_is_its_own_block_and_nothing_is_interpolated_into_it():
    result = build_messages(transcript(3))

    assert result.messages[0].role is Role.SYSTEM
    assert result.messages[0].content == SYSTEM_PROMPT
    assert "Hỏi lần" not in result.messages[0].content
    assert "get_price_series" not in result.messages[0].content


def test_user_content_and_tool_results_are_separate_role_blocks():
    result = build_messages(transcript(1))

    user = [m for m in result.messages if m.role is Role.USER]
    tools = [m for m in result.messages if m.role is Role.TOOL]

    assert [m.content for m in user] == ["Hỏi lần 0 về FPT"]
    assert len(tools) == 2
    for message in tools:
        assert message.content is not None
        assert "Hỏi lần" not in message.content


def test_no_tool_result_appears_without_its_call():
    result = build_messages(transcript(3))

    requested: set[str] = set()
    for message in result.messages:
        if message.role is Role.ASSISTANT and message.tool_calls:
            requested.update(item.id for item in message.tool_calls)
        if message.role is Role.TOOL:
            assert message.tool_call_id in requested

    answered = {m.tool_call_id for m in result.messages if m.role is Role.TOOL}
    assert answered == requested


def test_an_unanswered_call_is_left_out_of_both_halves():
    unanswered = TranscriptTurn(
        user_text="Cancelled mid-flight",
        tool_calls=(
            call(1),
            TranscriptToolCall(call_id="call_pending", name="get_analysis", result=None),
        ),
    )
    result = build_messages(Transcript(system_prompt=SYSTEM_PROMPT, turns=(unanswered,)))

    assert "call_pending" not in str(result.messages)


def test_rung_two_replaces_old_results_with_called_x_with_arguments_y():
    result = build_messages(
        transcript(6), ContextBudget(max_tokens=3_000, keep_intact_turns=2)
    )

    assert result.results_collapsed > 0
    assert result.turns_dropped == 0
    collapsed = [
        m
        for m in result.messages
        if m.role is Role.TOOL and m.content.startswith("called ")
    ]
    assert collapsed
    assert collapsed[0].content == (
        'called get_price_series with arguments {"symbol":"FPT","window_days":90}'
    )
    # The full results are still readable in agent_tool_call; the transcript is
    # a working context, not the record.
    assert collapsed[0].tool_call_id.startswith("call_")


def test_the_most_recent_turns_keep_their_results_while_older_ones_collapse():
    result = build_messages(
        transcript(6), ContextBudget(max_tokens=3_000, keep_intact_turns=2)
    )

    tools = [m for m in result.messages if m.role is Role.TOOL]
    newest = tools[-4:]
    assert all(not m.content.startswith("called ") for m in newest)
    assert any(m.content.startswith("called ") for m in tools[:-4])


def test_past_the_threshold_the_function_reports_that_a_summary_is_needed():
    result = build_messages(
        transcript(10), ContextBudget(max_tokens=TURN_CONTEXT_PER_CALL, summary_threshold_turns=8)
    )

    assert result.summary_needed is True
    assert result.summary_used is False
    assert result.turns_dropped == 0


def test_dropping_a_turn_reports_a_summary_is_needed_and_never_splits_one():
    result = build_messages(
        transcript(8), ContextBudget(max_tokens=1_200, keep_intact_turns=2)
    )

    assert result.turns_dropped > 0
    assert result.summary_needed is True
    assert result.summarise_from_turn == 0
    assert result.summarise_through_turn == result.turns_dropped
    users = [m.content for m in result.messages if m.role is Role.USER]
    assert users == [f"Hỏi lần {index} về FPT" for index in range(8 - len(users), 8)]


def test_a_new_summary_covers_only_the_turns_the_old_one_did_not():
    """The existing summary is carried forward, never fed back to a summariser."""
    result = build_messages(
        transcript(10, summary="Tóm tắt cũ.", summarised_turns=3),
        ContextBudget(max_tokens=1_200, keep_intact_turns=2),
    )

    assert result.summary_used is True
    assert result.summary_needed is True
    assert result.turns_dropped > 0
    # New material starts where the old summary stopped, so the caller
    # summarises turns[3:through] and keeps "Tóm tắt cũ." beside it.
    assert result.summarise_from_turn == 3
    assert result.summarise_through_turn == 3 + result.turns_dropped
    assert "Tóm tắt cũ." in result.messages[1].content


def test_an_existing_summary_is_consumed_and_never_re_summarised():
    result = build_messages(
        transcript(6, summary="Người dùng đã hỏi về FPT và VCB.", summarised_turns=4),
        ContextBudget(max_tokens=TURN_CONTEXT_PER_CALL),
    )

    assert result.summary_used is True
    assert result.messages[1].role is Role.SYSTEM
    assert result.messages[1].content.startswith(SUMMARY_LABEL)
    assert "Người dùng đã hỏi về FPT và VCB." in result.messages[1].content
    users = [m.content for m in result.messages if m.role is Role.USER]
    assert users == ["Hỏi lần 4 về FPT", "Hỏi lần 5 về FPT"]
    # The summary text itself is carried, not re-fed to a summariser.
    assert result.summary_needed is False
    assert result.summarise_from_turn == 4
    assert result.summarise_through_turn == 4


def test_a_summary_span_without_a_summary_is_ignored_rather_than_trusted():
    result = build_messages(transcript(3, summarised_turns=2))

    users = [m.content for m in result.messages if m.role is Role.USER]
    assert users == [f"Hỏi lần {index} về FPT" for index in range(3)]


def test_the_result_never_exceeds_the_ceiling_across_the_whole_ladder():
    long_thread = transcript(24)

    for ceiling in (1_000, 2_500, 5_000, 12_000, TURN_CONTEXT_PER_CALL):
        result = build_messages(long_thread, ContextBudget(max_tokens=ceiling))
        assert result.estimated_tokens <= ceiling


def test_one_turn_that_outgrows_the_ceiling_collapses_its_own_results():
    heavy = Transcript(
        system_prompt=SYSTEM_PROMPT,
        turns=(turn(0, calls=24, size=3_800),),
    )

    result = build_messages(heavy, ContextBudget(max_tokens=8_000))

    assert result.turns_dropped == 0
    assert 0 < result.results_collapsed <= 24
    assert result.estimated_tokens <= 8_000
    # Even inside one Turn the collapse runs oldest first, so the round the
    # model is about to answer from is the last evidence to be given up.
    tools = [m for m in result.messages if m.role is Role.TOOL]
    assert not tools[-1].content.startswith("called ")
    assert tools[0].content.startswith("called ")


def test_a_context_that_cannot_be_made_to_fit_fails_loudly():
    with pytest.raises(ConstructedContextTooLarge, match="ceiling of 10"):
        build_messages(transcript(3), ContextBudget(max_tokens=10))
