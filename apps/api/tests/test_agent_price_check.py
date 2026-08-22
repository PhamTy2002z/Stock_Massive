"""The check step between reading a number and using it.

A real Turn quoted HPG's 52-week range as *20.100–27.542* out of a data site.
27.542 / 50 = 550,84, and HOSE quotes that price level in steps of 50, so it is
not a price that ever matched — and nothing in the loop could say so. These tests
are that sentence made mechanical.

Four properties, and three of them are about restraint rather than arithmetic:

*A step is a rule about which numbers exist.* Off the step is impossible, not
unlikely, and the check that proves it needs no session and no store row.

*The board belongs to the bar, not to the ticker.* HNX quotes in one flat step
and bands at ±10; reading HOSE onto an HNX symbol would pass an impossible price
and fail a legal one.

*"Could not check" is never "checked and fine".* Every branch that loses an
input answers ``unverified`` and says what was missing. Folding it into a pass is
how an absence of evidence becomes evidence.

*Nothing is removed and nothing is blocked.* A failed check rides back attached
to the number it is about, because a whited-out answer is worse than a wrong
number named as doubtful.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.agent import registry, untrusted
from src.agent.tools.price_check import (
    BAND,
    EXCEEDS_BAND,
    OFF_TICK,
    ON_TICK,
    STORE,
    STORE_AGREES,
    STORE_DISAGREES,
    TICK,
    UNVERIFIED,
    WITHIN_BAND,
    PriceCheckTool,
    summarise_check_price_claim,
)
from src.agent.toolsets import TOOLSETS, resolve_toolset
from src.stocks.providers import Exchange, PriceBasis

from .test_price_band import list_on, open_session, write_session

SYMBOL = "PCKSYM"

# Weekdays, because the store's own definition of a Trading Day is a day it
# holds a session for.
SESSION = date(2026, 8, 12)
BEFORE = date(2026, 8, 11)

# The number out of the real Turn, and the close of the session it was quoted
# beside. One is on the HOSE step of 50 and the other is not.
IMPOSSIBLE = 27_542
REAL_CLOSE = 21_700


def tool_over(session) -> PriceCheckTool:
    """The tool reading one open session, which the test owns and closes."""

    class _Opener:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    return PriceCheckTool(session_opener=_Opener)


def check(session, price: float, *, symbol: str = SYMBOL, day: date | None = SESSION):
    arguments: dict[str, object] = {"symbol": symbol, "price": price}
    if day is not None:
        arguments["session_date"] = day.isoformat()
    return tool_over(session).check_price_claim(registry.ToolContext(), arguments)


def verdict(result, check_name: str) -> str:
    return next(item["verdict"] for item in result["checks"] if item["check"] == check_name)


def detail(result, check_name: str) -> str:
    entry = next(item for item in result["checks"] if item["check"] == check_name)
    return str(entry.get("detail", ""))


@pytest.fixture
def store():
    """One HOSE symbol with two ordinary sessions behind it."""
    session = open_session()
    list_on(session, SYMBOL, Exchange.HOSE)
    write_session(session, SYMBOL, BEFORE, close=21_500.0)
    write_session(
        session, SYMBOL, SESSION, close=float(REAL_CLOSE), high=21_750.0, low=21_150.0
    )
    session.flush()
    yield session
    session.close()


class TestTheStep:
    def test_the_price_from_the_real_turn_is_off_the_step(self, store):
        result = check(store, IMPOSSIBLE)

        assert verdict(result, TICK) == OFF_TICK

    def test_the_explanation_names_the_step_it_failed(self, store):
        """The number is the whole argument; a verdict without it is an assertion."""
        assert "50" in detail(check(store, IMPOSSIBLE), TICK)

    def test_a_price_that_did_trade_is_on_the_step(self, store):
        assert verdict(check(store, REAL_CLOSE), TICK) == ON_TICK

    def test_the_step_changes_with_the_price_level(self, store):
        """Under 10,000 HOSE quotes in tens, so 9,995 is off and 9,990 is on."""
        assert verdict(check(store, 9_995), TICK) == OFF_TICK
        assert verdict(check(store, 9_990), TICK) == ON_TICK

    def test_an_omitted_date_falls_back_to_the_newest_session_held(self, store):
        """Not to today: today may not have closed, and a band still moving."""
        assert check(store, IMPOSSIBLE, day=None)["sessionDate"] == SESSION.isoformat()

    def test_the_step_answers_with_no_session_anywhere_in_the_store(self):
        """A step is a property of the board, so it does not wait for a date.

        Failing this check for want of a date the other two need would hide the
        one check that can prove a price impossible on its own.
        """
        session = open_session()
        list_on(session, SYMBOL, Exchange.HOSE)
        session.flush()

        result = check(session, IMPOSSIBLE, day=None)

        assert result["sessionDate"] is None
        assert verdict(result, TICK) == OFF_TICK
        assert verdict(result, BAND) == UNVERIFIED
        assert verdict(result, STORE) == UNVERIFIED
        session.close()

    def test_a_number_too_large_to_be_a_price_is_not_judged(self, store):
        """A market capitalisation in the price field is not an off-step price."""
        assert verdict(check(store, 900_000_000), TICK) == UNVERIFIED


class TestTheBoard:
    def test_the_board_comes_from_the_listing_register_and_not_from_hose(self):
        """HNX quotes every equity in one flat step of 100.

        21,750 is a legal HOSE price and an illegal HNX one, so a hardcoded HOSE
        would call this on-step and be wrong about a different market.
        """
        session = open_session()
        list_on(session, SYMBOL, Exchange.HNX)
        write_session(session, SYMBOL, BEFORE, close=21_500.0)
        write_session(session, SYMBOL, SESSION, close=21_700.0)
        session.flush()

        result = check(session, 21_750)

        assert result["exchange"] == Exchange.HNX.value
        assert verdict(result, TICK) == OFF_TICK
        session.close()

    def test_a_symbol_on_no_board_is_unverified_rather_than_assumed_hose(self):
        session = open_session()
        write_session(session, SYMBOL, SESSION, close=21_700.0)
        session.flush()

        result = check(session, IMPOSSIBLE)

        assert result["exchange"] is None
        assert verdict(result, TICK) == UNVERIFIED
        assert verdict(result, BAND) == UNVERIFIED
        session.close()

    def test_the_result_says_how_confidently_the_board_is_known(self, store):
        """Inside the HNX-to-HOSE window a HOSE board is an assumption.

        The band check rests entirely on it, so the reader is told which of the
        two it got rather than being left to assume a record.
        """
        assert check(store, REAL_CLOSE)["exchangeAsOf"] == "current_listing_assumed"


class TestTheBand:
    def test_a_price_the_session_could_not_have_reached_exceeds_the_band(self, store):
        """±7% of the 21,500 anchor is 20,000–23,000, rounded to the step."""
        result = check(store, 25_000)

        assert verdict(result, BAND) == EXCEEDS_BAND
        assert result["checks"][1]["anchor"] == 21_500.0
        assert result["checks"][1]["anchorDate"] == BEFORE.isoformat()

    def test_a_price_inside_the_permitted_move_is_within_the_band(self, store):
        assert verdict(check(store, REAL_CLOSE), BAND) == WITHIN_BAND

    def test_with_no_earlier_session_the_band_is_unverified(self):
        session = open_session()
        list_on(session, SYMBOL, Exchange.HOSE)
        write_session(session, SYMBOL, SESSION, close=float(REAL_CLOSE))
        session.flush()

        result = check(session, 25_000)

        assert verdict(result, BAND) == UNVERIFIED
        # The step still answers: it never needed the anchor.
        assert verdict(result, TICK) == ON_TICK
        session.close()

    def test_an_adjusted_anchor_is_refused_rather_than_used(self):
        """An adjusted close is not the reference price the exchange set.

        Using it would produce a band of the right shape around the wrong
        number, which is the failure mode this whole module exists to name.
        """
        session = open_session()
        list_on(session, SYMBOL, Exchange.HOSE)
        write_session(
            session,
            SYMBOL,
            BEFORE,
            close=21_500.0,
            basis=PriceBasis.ADJUSTED_AT_SOURCE,
        )
        write_session(session, SYMBOL, SESSION, close=float(REAL_CLOSE))
        session.flush()

        assert verdict(check(session, 25_000), BAND) == UNVERIFIED
        session.close()


class TestTheStoredSession:
    def test_a_price_outside_the_stored_range_disagrees_with_the_store(self, store):
        assert verdict(check(store, IMPOSSIBLE), STORE) == STORE_DISAGREES

    def test_a_disagreement_carries_both_numbers_and_the_date_it_is_as_of(self, store):
        """A disagreement the reader cannot see both sides of is an assertion."""
        entry = next(
            item for item in check(store, IMPOSSIBLE)["checks"] if item["check"] == STORE
        )

        assert entry["claimed"] == float(IMPOSSIBLE)
        assert entry["stored"]["low"] == 21_150.0
        assert entry["stored"]["high"] == 21_750.0
        assert entry["asOf"] == SESSION.isoformat()

    def test_a_price_the_session_traded_at_agrees(self, store):
        assert verdict(check(store, REAL_CLOSE), STORE) == STORE_AGREES

    def test_no_stored_session_is_unverified_and_not_a_pass(self, store):
        """The whole point of the fourth state: absent is not fine."""
        result = check(store, REAL_CLOSE, day=date(2026, 8, 10))

        assert verdict(result, STORE) == UNVERIFIED
        assert verdict(result, STORE) != STORE_AGREES
        assert UNVERIFIED in result["flags"]


class TestWhatItRefusesToDo:
    def test_it_never_removes_the_number_it_was_given(self, store):
        assert check(store, IMPOSSIBLE)["price"] == float(IMPOSSIBLE)

    def test_a_ticker_this_market_has_no_shape_for_is_an_answer_not_a_raise(self, store):
        result = check(store, REAL_CLOSE, symbol="not a ticker")

        assert result["checks"] == []
        assert result["flags"] == [UNVERIFIED]
        assert "ticker" in result["detail"]

    def test_a_price_that_is_not_a_number_is_an_answer_not_a_raise(self, store):
        result = tool_over(store).check_price_claim(
            registry.ToolContext(), {"symbol": SYMBOL, "price": "twenty thousand"}
        )

        assert result["flags"] == [UNVERIFIED]

    def test_it_does_not_consult_the_context_for_a_symbol(self, store):
        """The subject is a claim, not the row this caller was opened for.

        A price quoted mid-Analysis is usually about some other company, and
        binding the check to the symbol under analysis would leave exactly those
        claims unchecked.
        """
        result = tool_over(store).check_price_claim(
            registry.ToolContext(symbol="OTHER", trading_day=SESSION),
            {"symbol": SYMBOL, "price": IMPOSSIBLE, "session_date": SESSION.isoformat()},
        )

        assert result["symbol"] == SYMBOL
        assert verdict(result, TICK) == OFF_TICK


class TestWhereItIsOffered:
    def test_it_is_in_the_signals_bundle_so_both_lanes_have_it(self):
        assert "check_price_claim" in TOOLSETS["signals"]["tools"]
        assert "check_price_claim" in resolve_toolset("signals")

    def test_its_result_is_not_wrapped_as_outside_content(self):
        """It reads this store to judge somebody else's number.

        What comes back is this system's own verdict, so wrapping it would tell
        the model to weigh its own harness's answer as a stranger's claim.
        """
        registry.register(tool_over(None).entries()[0])
        try:
            assert untrusted.is_untrusted("check_price_claim") is False
        finally:
            registry.deregister("check_price_claim")


class TestProvenanceIsDeclaredRatherThanRemembered:
    """``untrusted.py`` used to decide from a frozenset of two names.

    The module's own docstring already claimed the property the frozenset does
    not have — that a tool added later is wrapped without anybody remembering to
    edit a list. It is the same gap Hermes has, where ``x_search`` is missing
    from its own set of untrusted names.
    """

    def test_a_registered_tool_is_read_off_its_own_registration(self):
        registry.register(
            registry.ToolEntry(
                name="pck_outside",
                toolset="pck_test",
                schema=registry.object_schema({}),
                handler=lambda context, arguments: {},
                description="reads outside content",
                display_name="Đọc ngoài",
                reads_external=True,
            )
        )
        registry.register(
            registry.ToolEntry(
                name="pck_inside",
                toolset="pck_test",
                schema=registry.object_schema({}),
                handler=lambda context, arguments: {},
                description="reads this store",
                display_name="Đọc store",
                reads_external=False,
            )
        )
        try:
            assert untrusted.is_untrusted("pck_outside") is True
            assert untrusted.is_untrusted("pck_inside") is False
        finally:
            registry.deregister("pck_outside")
            registry.deregister("pck_inside")

    def test_a_tool_that_declares_nothing_is_treated_as_outside(self):
        """The default is the safe answer, not the common one."""
        registry.register(
            registry.ToolEntry(
                name="pck_silent",
                toolset="pck_test",
                schema=registry.object_schema({}),
                handler=lambda context, arguments: {},
                description="says nothing about where its results come from",
                display_name="Không khai gì",
            )
        )
        try:
            assert untrusted.is_untrusted("pck_silent") is True
        finally:
            registry.deregister("pck_silent")

    def test_a_name_nobody_registered_is_treated_as_outside(self):
        assert untrusted.is_untrusted("a_tool_that_does_not_exist") is True


class TestWhatAReaderIsShown:
    def test_the_row_names_the_price_and_the_company(self):
        """The price is the subject.

        A reader scanning the rail after an answer that quoted an odd number
        wants to see whether that number was the one checked, and a row naming
        only the ticker cannot tell them.
        """
        assert (
            summarise_check_price_claim({"symbol": "hpg", "price": IMPOSSIBLE})
            == "Kiểm mức giá: 27.542 — HPG"
        )

    def test_the_price_is_grouped_the_way_this_market_writes_one(self):
        """Compared against a number the reader read on a Vietnamese site."""
        assert "21.700" in summarise_check_price_claim(
            {"symbol": "HPG", "price": REAL_CLOSE}
        )

    def test_a_price_that_is_not_a_number_still_draws_a_row(self):
        row = summarise_check_price_claim({"symbol": "HPG", "price": "twenty"})

        assert row.startswith("Kiểm mức giá:")
        assert "HPG" in row

    def test_the_registration_carries_both_names(self):
        entry = tool_over(None).entries()[0]

        assert entry.name == "check_price_claim"
        assert entry.display_name == "Kiểm mức giá"
        assert entry.summarise is summarise_check_price_claim
