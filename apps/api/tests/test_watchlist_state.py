"""One state for two causes, proven where the state is decided.

A watched symbol leaves the **Universe** two ways: the company was delisted and
the Profit Leaders Cohort reseated without it, or an operator trimmed the
declared half. V1 cannot tell those apart and must not pretend to — a state
named for a cause it cannot establish is a lie the interface would repeat.

These are unit tests rather than requests because what is being tested is that
the decision has nowhere to learn a cause from. Driving it through HTTP would
prove the two paths agree today; reading the function proves they cannot
disagree.
"""

import inspect

import pytest

from src.alpha.watchlist import WatchlistState, entry_state
from src.stocks.universe import Universe

DECLARED = ("AAA", "BBB")
COHORT = ("CCC", "DDD")

FULL = Universe(explicit=DECLARED, cohort=COHORT)


@pytest.mark.parametrize("symbol", DECLARED + COHORT)
def test_a_symbol_the_universe_carries_is_active(symbol):
    assert entry_state(symbol, FULL) is WatchlistState.ACTIVE


def test_an_operator_trimming_the_declared_half_makes_it_unsupported():
    trimmed = Universe(explicit=("BBB",), cohort=COHORT)

    assert entry_state("AAA", trimmed) is WatchlistState.UNSUPPORTED


def test_a_delisting_reseating_the_cohort_makes_it_unsupported():
    """The cohort half is derived from the market, so a company that stops
    trading leaves it without anyone deciding to remove it."""
    reseated = Universe(explicit=DECLARED, cohort=("DDD",))

    assert entry_state("CCC", reseated) is WatchlistState.UNSUPPORTED


def test_both_causes_produce_the_very_same_state():
    trimmed = Universe(explicit=("BBB",), cohort=COHORT)
    reseated = Universe(explicit=DECLARED, cohort=("DDD",))

    assert entry_state("AAA", trimmed) == entry_state("CCC", reseated)


def test_the_decision_has_nowhere_to_learn_a_cause_from():
    """The signature is the guarantee. A symbol and the Universe are the whole
    input, so no caller can pass a cause in and no branch can read one out."""
    assert list(inspect.signature(entry_state).parameters) == ["symbol", "universe"]


def test_there_are_two_states_and_no_third():
    assert {state.value for state in WatchlistState} == {"active", "unsupported"}


def test_a_symbol_that_could_not_be_a_symbol_is_unsupported_rather_than_an_error():
    """The rail asks this about whatever is stored, so malformed text has to be
    a plain answer rather than an exception escaping into a response."""
    assert entry_state("not a symbol!", FULL) is WatchlistState.UNSUPPORTED
