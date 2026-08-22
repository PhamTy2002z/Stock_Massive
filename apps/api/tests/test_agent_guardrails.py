"""Each rung of the repetition ladder, at the thresholds the harness ships."""

from __future__ import annotations

from src.agent.guardrails import (
    NO_PROGRESS,
    REPEATED_FAILURE,
    REPEATED_TOOL_FAILURE,
    GuardrailThresholds,
    TurnGuardrails,
    Verdict,
    call_signature,
    result_signature,
)

ARGUMENTS = {"query": "lãi suất", "limit": 3}


def test_a_reordered_argument_object_is_the_same_call():
    assert call_signature("web_search", {"a": 1, "b": 2}) == call_signature(
        "web_search", {"b": 2, "a": 1}
    )
    assert call_signature("web_search", {"a": 1}) != call_signature("fetch_url", {"a": 1})


def test_one_failure_is_not_yet_a_pattern():
    guardrails = TurnGuardrails()

    decision = guardrails.after_call("web_search", ARGUMENTS, ok=False)

    assert decision.verdict is Verdict.ALLOW


def test_the_second_identical_failure_warns():
    guardrails = TurnGuardrails()
    guardrails.after_call("web_search", ARGUMENTS, ok=False)

    decision = guardrails.after_call("web_search", ARGUMENTS, ok=False)

    assert decision.verdict is Verdict.WARN
    assert decision.reason == REPEATED_FAILURE
    assert "web_search" in decision.guidance


def test_the_third_failure_of_one_tool_warns_even_with_new_arguments():
    guardrails = TurnGuardrails()
    first = guardrails.after_call("fetch_url", {"url": "https://a.example"}, ok=False)
    second = guardrails.after_call("fetch_url", {"url": "https://b.example"}, ok=False)

    third = guardrails.after_call("fetch_url", {"url": "https://c.example"}, ok=False)

    assert (first.verdict, second.verdict) == (Verdict.ALLOW, Verdict.ALLOW)
    assert third.verdict is Verdict.WARN
    assert third.reason == REPEATED_TOOL_FAILURE


def test_the_sixth_identical_call_is_blocked_before_it_is_dispatched():
    guardrails = TurnGuardrails()
    for _ in range(5):
        guardrails.after_call("web_search", ARGUMENTS, ok=False)

    decision = guardrails.before_call("web_search", ARGUMENTS)

    assert decision.verdict is Verdict.BLOCK
    assert decision.reason == REPEATED_FAILURE
    assert guardrails.halted is False


def test_a_call_that_has_not_failed_is_never_blocked():
    guardrails = TurnGuardrails()
    for _ in range(5):
        guardrails.after_call("web_search", ARGUMENTS, ok=False)

    assert guardrails.before_call("web_search", {"query": "something else"}).verdict is (
        Verdict.ALLOW
    )


def test_the_eighth_failure_of_one_tool_halts_the_turn():
    guardrails = TurnGuardrails()
    verdicts = [
        guardrails.after_call("fetch_url", {"url": f"https://{index}.example"}, ok=False)
        for index in range(8)
    ]

    assert verdicts[-1].verdict is Verdict.HALT
    assert verdicts[-1].reason == REPEATED_TOOL_FAILURE
    assert guardrails.halted is True
    # Once halted, nothing else is dispatched in this Turn.
    assert guardrails.before_call("web_search", ARGUMENTS).verdict is Verdict.HALT


def test_blocked_calls_still_count_towards_the_halt():
    thresholds = GuardrailThresholds(
        exact_failure_block_after=2, same_tool_failure_halt_after=4
    )
    guardrails = TurnGuardrails(thresholds)
    for _ in range(2):
        guardrails.after_call("web_search", ARGUMENTS, ok=False)

    verdicts = [guardrails.before_call("web_search", ARGUMENTS).verdict for _ in range(2)]

    assert verdicts == [Verdict.BLOCK, Verdict.HALT]


def test_repeating_a_successful_call_for_the_same_answer_warns():
    guardrails = TurnGuardrails()
    unchanged = result_signature('{"results": []}')

    first = guardrails.after_call("web_search", ARGUMENTS, ok=True, result_hash=unchanged)
    second = guardrails.after_call("web_search", ARGUMENTS, ok=True, result_hash=unchanged)
    third = guardrails.after_call("web_search", ARGUMENTS, ok=True, result_hash=unchanged)

    assert (first.verdict, second.verdict) == (Verdict.ALLOW, Verdict.ALLOW)
    assert third.verdict is Verdict.WARN
    assert third.reason == NO_PROGRESS


def test_a_new_answer_clears_the_no_progress_streak():
    guardrails = TurnGuardrails()
    for _ in range(3):
        guardrails.after_call(
            "web_search", ARGUMENTS, ok=True, result_hash=result_signature("same")
        )

    fresh = guardrails.after_call(
        "web_search", ARGUMENTS, ok=True, result_hash=result_signature("different")
    )
    repeated = guardrails.after_call(
        "web_search", ARGUMENTS, ok=True, result_hash=result_signature("different")
    )

    assert fresh.verdict is Verdict.ALLOW
    assert repeated.verdict is Verdict.ALLOW


def test_a_turn_that_resets_starts_from_the_first_rung_again():
    guardrails = TurnGuardrails()
    for _ in range(8):
        guardrails.after_call("fetch_url", {"url": "https://a.example"}, ok=False)
    assert guardrails.halted is True

    guardrails.reset()

    assert guardrails.halted is False
    assert guardrails.before_call("fetch_url", {"url": "https://a.example"}).verdict is (
        Verdict.ALLOW
    )


def test_the_ladder_ranks_so_a_batch_can_take_its_strongest_verdict():
    assert Verdict.ALLOW.rank < Verdict.WARN.rank < Verdict.BLOCK.rank < Verdict.HALT.rank
