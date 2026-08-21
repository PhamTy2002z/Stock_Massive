"""The repetition ladder, judged with nothing but a history and a round budget.

The failure this file is written against is the guardrail that never fires: a
last rung placed past what the round budget can reach makes every test here pass
and every real Turn go round in circles anyway. So the halt rung is asserted
twice — once at the deployed budget of four rounds, and once at another — and
always by walking a Turn round by round rather than by handing the ladder a
history no loop could produce.
"""

from __future__ import annotations

import pytest

from src.agent.guardrails import (
    EFFECT_CAPABLE_TOOLS,
    FRUITLESS_REPEAT,
    IDEMPOTENT_TOOLS,
    REPEATED_CALL,
    REPEATED_WRITE,
    Decision,
    GuardrailLadder,
    GuardrailThresholds,
    ObservedCall,
    PlannedCall,
    Verdict,
    is_idempotent,
)
from src.agent.loop import MAX_TOOL_ROUNDS

ARGUMENTS = {"symbol": "FPT", "window_days": 90}


def ladder(max_rounds: int = MAX_TOOL_ROUNDS) -> GuardrailLadder:
    return GuardrailLadder(max_rounds=max_rounds)


def planned(tool: str = "get_price_series", **arguments) -> PlannedCall:
    return PlannedCall(
        call_id="call_1", tool_name=tool, arguments=arguments or dict(ARGUMENTS)
    )


def observed(
    tool: str = "get_price_series",
    *,
    progressed: bool = True,
    **arguments,
) -> ObservedCall:
    return ObservedCall(
        tool_name=tool,
        arguments=arguments or dict(ARGUMENTS),
        progressed=progressed,
    )


def walk(tool: str, *, rounds: int) -> list[Decision]:
    """The verdicts a Turn collects by asking for the same call every round.

    Written as a walk because that is the only way to prove a rung is reachable:
    each round judges the call, and the call joins the history whether it was
    dispatched or refused — a blocked call is still a thing the model asked for.
    """
    controller = ladder(rounds)
    history: list[ObservedCall] = []
    verdicts: list[Decision] = []
    for _ in range(rounds):
        decision = controller.judge_call(planned(tool), history)
        verdicts.append(decision)
        if decision.verdict is Verdict.HALT:
            break
        history.append(observed(tool))
    return verdicts


def test_a_call_the_turn_has_never_made_is_allowed_with_nothing_to_say():
    decision = ladder().judge_call(planned(), [])

    assert decision.verdict is Verdict.ALLOW
    assert decision.guidance == ""
    assert decision.reason == ""


def test_the_second_identical_read_is_warned_and_still_dispatched():
    decision = ladder().judge_call(planned(), [observed()])

    assert decision.verdict is Verdict.WARN
    assert decision.reason == REPEATED_CALL
    assert "get_price_series" in decision.guidance


def test_the_third_identical_read_is_blocked_before_dispatch():
    decision = ladder().judge_call(planned(), [observed(), observed()])

    assert decision.verdict is Verdict.BLOCK
    assert decision.reason == REPEATED_CALL


def test_a_repeated_write_is_blocked_where_a_repeated_read_would_be_warned():
    history = [observed("remember_fact", fact="FPT is a software firm")]

    write = ladder().judge_call(
        PlannedCall("call_1", "remember_fact", {"fact": "FPT is a software firm"}),
        history,
    )
    read = ladder().judge_call(planned(), [observed()])

    assert write.verdict is Verdict.BLOCK
    assert write.reason == REPEATED_WRITE
    assert read.verdict is Verdict.WARN


def test_the_halt_rung_is_reached_inside_the_deployed_round_budget():
    verdicts = [decision.verdict for decision in walk("get_price_series", rounds=4)]

    assert verdicts == [Verdict.ALLOW, Verdict.WARN, Verdict.BLOCK, Verdict.HALT]


def test_the_halt_rung_moves_with_the_round_budget_it_was_given():
    short = [decision.verdict for decision in walk("get_price_series", rounds=2)]
    long = [decision.verdict for decision in walk("get_price_series", rounds=8)]

    # Two rounds leave no room for a ladder: the one repetition a Turn that
    # short can show is also the last straw.
    assert short == [Verdict.ALLOW, Verdict.HALT]
    # Eight rounds place the halt at the seventh repetition, and the rungs below
    # it stay where they are — the model is refused long before it is stopped.
    assert long[:3] == [Verdict.ALLOW, Verdict.WARN, Verdict.BLOCK]
    assert long[-1] is Verdict.HALT
    assert Verdict.HALT not in long[:-1]


def test_a_write_halts_a_round_earlier_than_a_read_does():
    thresholds = GuardrailThresholds.for_rounds(MAX_TOOL_ROUNDS)

    assert thresholds.halt_at(effect_capable=True) < thresholds.halt_at(
        effect_capable=False
    )
    assert thresholds.block_at(effect_capable=True) < thresholds.block_at(
        effect_capable=False
    )


def test_the_halt_rung_stays_reachable_at_every_round_budget():
    for rounds in range(1, 13):
        thresholds = GuardrailThresholds.for_rounds(rounds)
        # A repetition is observable from the second round onwards, so a Turn of
        # ``rounds`` rounds can show ``rounds - 1`` of them — except at one
        # round, where the ladder cannot fire at all and must not pretend to.
        assert thresholds.halt_repeats <= max(1, rounds - 1)
        assert thresholds.halt_repeats >= 1


def test_a_tool_of_unknown_shape_is_treated_as_a_write():
    assert is_idempotent("mcp__memory__store") is False
    assert is_idempotent("some_plugin_tool") is False

    decision = ladder().judge_call(
        PlannedCall("call_1", "mcp__memory__store", {"key": "FPT"}),
        [ObservedCall("mcp__memory__store", {"key": "FPT"})],
    )

    assert decision.verdict is Verdict.BLOCK
    assert decision.reason == REPEATED_WRITE


def test_every_registered_read_is_classified_as_idempotent():
    for tool in IDEMPOTENT_TOOLS:
        assert is_idempotent(tool) is True
    for tool in EFFECT_CAPABLE_TOOLS:
        assert is_idempotent(tool) is False


def test_a_tool_listed_on_both_sides_resolves_to_the_stricter_reading():
    overlap = IDEMPOTENT_TOOLS & EFFECT_CAPABLE_TOOLS

    assert overlap == frozenset()
    # The precedence that makes the overlap safe rather than the absence of one:
    # a name in both sets is a write.
    assert is_idempotent(next(iter(EFFECT_CAPABLE_TOOLS))) is False


def test_the_same_call_written_two_ways_is_still_the_same_call():
    history = [observed(symbol="FPT", window_days=90)]

    decision = ladder().judge_call(
        PlannedCall(
            "call_1",
            "get_price_series",
            {"symbol": "FPT", "window_days": 90, "as_of": None},
        ),
        history,
    )

    assert decision.verdict is Verdict.WARN


def test_different_arguments_to_the_same_tool_are_not_a_repetition():
    decision = ladder().judge_call(
        planned(symbol="VNM", window_days=90),
        [observed(symbol="FPT", window_days=90)],
    )

    assert decision.verdict is Verdict.ALLOW


def test_a_read_that_keeps_returning_nothing_new_is_warned_not_blocked():
    history = [
        observed(symbol="FPT", progressed=False),
        observed(symbol="VNM", progressed=False),
    ]

    decision = ladder().judge_call(planned(symbol="HPG"), history)

    assert decision.verdict is Verdict.WARN
    assert decision.reason == FRUITLESS_REPEAT


def test_a_turn_whose_reads_never_add_anything_is_told_but_not_stopped():
    # Three refusals from one tool, then a fourth call with arguments nobody has
    # tried. It is warned and dispatched: a Structured Refusal is what "no
    # progress" is read from, and refusals arrive in ordinary bunches — three
    # symbols outside the Universe, three searches while the web is down. Halting
    # here would end the tool loop over a question the Turn had not yet asked.
    history = [
        observed(symbol=symbol, progressed=False) for symbol in ("FPT", "VNM", "HPG")
    ]

    decision = ladder().judge_call(planned(symbol="VIC"), history)

    assert decision.verdict is Verdict.WARN
    assert decision.reason == FRUITLESS_REPEAT


def test_no_number_of_empty_reads_ever_halts_a_call_never_made():
    # The rung the fruitless route may reach, at every round budget: a tool that
    # keeps coming back empty is worth a sentence, never the rest of the Turn's
    # evidence budget.
    for rounds in (2, 4, 8):
        history = [
            observed(symbol=f"SYM{index}", progressed=False) for index in range(rounds * 2)
        ]

        decision = ladder(rounds).judge_call(planned(symbol="NEW"), history)

        assert decision.verdict is Verdict.WARN


def test_one_halted_call_does_not_refuse_the_round_it_arrived_in():
    # A halt takes the loop, not the round: the sibling call may be the first
    # time this Turn asked for what it asks for.
    history = [observed() for _ in range(3)]
    calls = [
        PlannedCall("call_1", "get_price_series", dict(ARGUMENTS)),
        PlannedCall("call_2", "get_analysis", {"symbol": "VNM"}),
    ]

    judgement = ladder().judge_round(calls, history)

    assert judgement.verdict is Verdict.HALT
    assert judgement.refused == ("call_1",)
    assert judgement.decisions["call_2"].verdict is Verdict.ALLOW


def test_a_fruitless_read_of_one_tool_says_nothing_about_another():
    history = [
        observed("get_analysis", symbol="FPT", progressed=False),
        observed("get_analysis", symbol="VNM", progressed=False),
    ]

    decision = ladder().judge_call(planned("get_financials", symbol="HPG"), history)

    assert decision.verdict is Verdict.ALLOW


def test_a_duplicate_inside_one_round_is_refused_rather_than_mentioned():
    # The rungs tolerate a repetition the model made *after* reading an answer.
    # Inside one round nobody has read anything, so the copy is pure waste and
    # the first call answers it.
    calls = [
        PlannedCall("call_1", "get_price_series", dict(ARGUMENTS)),
        PlannedCall("call_2", "get_price_series", dict(ARGUMENTS)),
    ]

    judgement = ladder().judge_round(calls, [])

    assert judgement.decisions["call_1"].verdict is Verdict.ALLOW
    assert judgement.blocked == ("call_2",)
    assert judgement.verdict is Verdict.BLOCK
    assert "one answer covers all of them" in judgement.guidance[0]


def test_a_duplicate_the_turn_already_halts_on_still_halts():
    # The exception to the rule above: a halt that the Turn's own history
    # produces is not the round's doing.
    calls = [
        PlannedCall("call_1", "get_price_series", dict(ARGUMENTS)),
        PlannedCall("call_2", "get_price_series", dict(ARGUMENTS)),
    ]
    history = [
        ObservedCall("get_price_series", dict(ARGUMENTS)),
        ObservedCall("get_price_series", dict(ARGUMENTS)),
        ObservedCall("get_price_series", dict(ARGUMENTS)),
    ]

    judgement = ladder().judge_round(calls, history)

    assert judgement.verdict is Verdict.HALT


def test_a_duplicated_write_inside_one_round_is_refused_not_mentioned():
    fact = {"fact": "FPT is a software firm"}
    calls = [
        PlannedCall("call_1", "remember_fact", dict(fact)),
        PlannedCall("call_2", "remember_fact", dict(fact)),
    ]

    judgement = ladder().judge_round(calls, [])

    assert judgement.blocked == ("call_2",)
    assert judgement.verdict is Verdict.BLOCK


def test_a_round_reports_the_strongest_verdict_and_every_call_it_judged():
    calls = [
        PlannedCall("call_1", "get_analysis", {"symbol": "VNM"}),
        PlannedCall("call_2", "get_price_series", dict(ARGUMENTS)),
    ]

    judgement = ladder().judge_round(calls, [observed(), observed()])

    assert set(judgement.decisions) == {"call_1", "call_2"}
    assert judgement.decisions["call_1"].verdict is Verdict.ALLOW
    assert judgement.verdict is Verdict.BLOCK
    assert judgement.blocked == ("call_2",)


def test_a_round_of_healthy_fan_out_is_allowed_with_no_guidance_at_all():
    calls = [
        PlannedCall(f"call_{index}", "get_analysis", {"symbol": symbol})
        for index, symbol in enumerate(("FPT", "VNM", "HPG"))
    ]

    judgement = ladder().judge_round(calls, [])

    assert judgement.verdict is Verdict.ALLOW
    assert judgement.guidance == ()


def test_one_sentence_of_guidance_is_all_a_verdict_ever_carries():
    decisions = [
        ladder().judge_call(planned(), [observed()]),
        ladder().judge_call(planned(), [observed(), observed()]),
        ladder().judge_call(planned(), [observed(), observed(), observed()]),
    ]

    for decision in decisions:
        assert decision.guidance
        assert decision.guidance.count(".") == 1
        assert decision.guidance.endswith(".")


def test_an_empty_round_is_a_decision_about_nothing():
    judgement = ladder().judge_round([], [observed(), observed()])

    assert judgement.verdict is Verdict.ALLOW
    assert judgement.decisions == {}
    assert judgement.blocked == ()


def test_the_controller_has_no_side_effects_across_a_hundred_questions():
    controller = ladder()
    history = [observed(), observed()]
    before = dict(vars(controller))

    answers = {
        controller.judge_call(planned(), history) for _ in range(100)
    }
    rounds = [
        controller.judge_round([planned()], history).verdict for _ in range(100)
    ]

    assert len(answers) == 1
    assert next(iter(answers)).verdict is Verdict.BLOCK
    assert set(rounds) == {Verdict.BLOCK}
    assert vars(controller) == before
    assert history == [observed(), observed()]


def test_a_judgement_cannot_be_edited_by_the_runtime_that_reads_it():
    judgement = ladder().judge_round([planned()], [observed()])

    with pytest.raises(TypeError):
        judgement.decisions["call_1"] = Decision(Verdict.ALLOW)
