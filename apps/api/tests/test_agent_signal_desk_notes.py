"""Which pipeline notes a Turn gets, and why the surface decides it.

The notes are prompt text, so there is not much to assert about their prose. The
two things worth holding are structural: the market variant is chosen from the
tools a Turn was actually offered rather than from the mode it was asked in, and
it states the three rules that Phase 3 proved the ledger enforces — because a
model that breaks any of them produces claims no evidence can support.
"""

from __future__ import annotations

from src.agent.evidence import pipeline


def test_a_surface_without_the_market_read_gets_the_notes_it_always_got():
    assert pipeline.planner_note(market=False) is pipeline.PLANNER_NOTE
    assert pipeline.research_note(market=False) is pipeline.RESEARCH_NOTE


def test_a_surface_with_the_market_read_is_told_to_use_it():
    planning = pipeline.planner_note(market=True)
    research = pipeline.research_note(market=True)

    assert pipeline.MARKET_TOOL in planning
    assert pipeline.MARKET_TOOL in research
    # A snippet has no unit, no timezone and no session boundary, so it can
    # never satisfy a price. The note has to say so or the model will try.
    assert "snippet" in planning.casefold()


def test_the_market_note_states_the_three_rules_the_ledger_enforces():
    """Each rule maps to a test in ``test_agent_market_data.py``.

    Kept as one test rather than three because they are one contract: a claim
    that breaks any of them is refused, and a note that states two of the three
    teaches the model a rule it will still be caught by.
    """
    research = pipeline.research_note(market=True).casefold()

    # 1. Whole dong, not the provider's thousands.
    assert "whole dong" in research
    # 2. Figures digit for digit: a rounded one is printed in no source, so the
    #    numeric check refuses the claim that states it.
    assert "10.196.800" in research
    # 3. A market-only material claim is single_source; labelling it verified
    #    invalidates the whole ledger, not just the claim.
    assert "single_source" in research
    assert "invalidates the whole ledger" in research


def test_the_market_surface_buys_no_extra_capacity():
    """A third tool does not widen the ceilings, and this is where that is said.

    The bounds live on the lane and the lane is chosen by mode, so a Signal Desk
    Turn runs on exactly the numbers a keyword-routed deep Turn has always run
    on. Written as a test because the tempting bug is the opposite: giving the
    new capability its own allowance so it "has room", which is a second budget
    that can disagree with the first.
    """
    from src.agent.lanes import DEEP
    from src.agent import toolsets

    assert (DEEP.max_tool_rounds, DEEP.max_external_calls, DEEP.deadline_seconds) == (
        25,
        80,
        3_600.0,
    )
    # And the selection is a tuple of names, holding no numbers of its own.
    assert toolsets.SIGNAL_DESK_TOOLSETS == (*toolsets.CORE_TOOLSETS, "market_data")
