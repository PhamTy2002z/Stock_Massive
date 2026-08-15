"""Corporate Actions: what they declare, and what may be believed of it.

The arithmetic is one line. Everything here is about the ways a corporate action
arrives incomplete, because each of them produces a plausible wrong number if it
is allowed to:

*A ratio is not a ratio everywhere.* The feed puts a cash dividend's payment into
``exercise_ratio`` as a fraction of par — 700 VND arrives as 0.07 — beside share
issues where the same column is shares per share. Read by name, TCB's dividend
becomes a 7% bonus issue.

*The factor is not the gap.* An ex-date's price gap is the entitlement and that
session's own move together, so the terms supply the factor and the prices supply
only the date.

*A blend is not its largest part.* ACB's 2025-05-23 ex-date is a 15% stock
dividend and a 1,000 VND cash dividend, and the stock dividend alone implies a
factor 4% away from the right one — in the direction that looks reasonable.

Every action and every price below is real: the actions come from
``Company(source='VCI').events()`` as it answered in August 2026, and the prices
are rows out of this system's own store. A fabricated pair would agree with
whatever this file happened to implement, which is the one thing these tests
exist to check.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.corporate_action_collector import CorporateActionCollector
from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import CorporateActionEvent, Exchange, ProviderSource
from src.stocks.signals.corporate_actions import (
    ActionKind,
    Confirmation,
    ConfirmationReason,
    CorporateActionStore,
    adjustment_factor,
    classify,
    confirm_ex_date,
    previous_close,
    terms_of,
)
from src.stocks.signals.issues import SignalIssue

from .test_price_band import list_on, write_session

# The store these tests build is the one the band regime reads, so the sessions
# are written through the same helper. A second way of writing a session would be
# a second store, and the point of every price below is that it is the one the
# system actually holds.

NOW = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)


def open_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        ProviderSnapshot.__table__,
        ListingRoster.__table__,
        CorporateAction.__table__,
    ):
        table.create(engine)
    return Session(engine)


# --- The real rows -------------------------------------------------------
# ACB's 2025 ex-date, both halves of it. The 0.10 on the cash row is the trap:
# it is 1,000 VND expressed against the 10,000 VND par, not a share ratio.
ACB_CASH_2025 = CorporateActionEvent(
    symbol="ACB",
    event_code="DIV",
    title="Cash Dividend - Year 2024 - 1,000 VND",
    ex_date=date(2025, 5, 23),
    record_date=date(2025, 5, 26),
    public_date=date(2025, 5, 16),
    exercise_ratio=0.10,
    value_per_share=1000.0,
)
ACB_STOCK_2025 = CorporateActionEvent(
    symbol="ACB",
    event_code="ISS",
    title="Share Issue - Stock dividend ratio 15.0%",
    ex_date=date(2025, 5, 23),
    record_date=date(2025, 5, 26),
    public_date=date(2025, 5, 16),
    exercise_ratio=0.15,
    value_per_share=None,
)

# TCB's 2026 bonus issue: announced, ratio declared, and no ex-date at all.
TCB_BONUS_UNDATED = CorporateActionEvent(
    symbol="TCB",
    event_code="ISS",
    title="Share Issue - Bonus Issue ratio 60.0%",
    ex_date=None,
    record_date=None,
    public_date=date(2026, 5, 14),
    exercise_ratio=0.6,
    value_per_share=None,
)

# MBB's 2026 ex-date: two share issues on one date, one of them priced at a
# subscription the feed does not carry.
MBB_STOCK_2026 = CorporateActionEvent(
    symbol="MBB",
    event_code="ISS",
    title="Share Issue - Stock dividend ratio 15.0%",
    ex_date=date(2026, 8, 11),
    record_date=date(2026, 8, 12),
    public_date=date(2026, 8, 6),
    exercise_ratio=0.15,
    value_per_share=None,
)
MBB_RIGHTS_2026 = CorporateActionEvent(
    symbol="MBB",
    event_code="ISS",
    title="Share Issue - Rights issue ratio 10.0%",
    ex_date=date(2026, 8, 11),
    record_date=date(2026, 8, 12),
    public_date=date(2026, 8, 6),
    exercise_ratio=0.10,
    value_per_share=None,
)


def store_acb_sessions(session: Session) -> None:
    """ACB's real sessions across its 2025 ex-date."""
    list_on(session, "ACB", Exchange.HOSE)
    write_session(session, "ACB", date(2025, 5, 21), close=25650.0, high=25900.0, low=25600.0)
    write_session(session, "ACB", date(2025, 5, 22), close=25550.0, high=25750.0, low=25500.0)
    write_session(session, "ACB", date(2025, 5, 23), close=21600.0, high=21600.0, low=21450.0)


def store_mbb_sessions(session: Session) -> None:
    """MBB's real sessions across its 2026 ex-date."""
    list_on(session, "MBB", Exchange.HOSE)
    write_session(session, "MBB", date(2026, 8, 10), close=24250.0, high=24450.0, low=23950.0)
    write_session(session, "MBB", date(2026, 8, 11), close=20350.0, high=20550.0, low=20350.0)


def save(session: Session, *events: CorporateActionEvent) -> tuple[CorporateAction, ...]:
    store = CorporateActionStore(session)
    return tuple(
        store.save(event, ProviderSource.VNSTOCK, NOW) for event in events
    )


class TestWhatKindOfActionThisIs:
    def test_a_share_issue_is_told_apart_by_its_title_alone(self):
        """One event code covers five different things, and only the text says which."""
        assert classify("ISS", "Share Issue - Stock dividend ratio 15.0%") is (
            ActionKind.STOCK_DIVIDEND
        )
        assert classify("ISS", "Share Issue - Bonus Issue ratio 60.0%") is (
            ActionKind.BONUS_ISSUE
        )
        assert classify("ISS", "Share Issue - Rights issue ratio 10.0%") is (
            ActionKind.RIGHTS_ISSUE
        )
        assert classify("ISS", "Share Issue - ESOP ratio 0.3%") is ActionKind.ESOP
        assert classify("ISS", "Share Issue - Private Placements ratio 1.0%") is (
            ActionKind.PRIVATE_PLACEMENT
        )

    def test_wording_this_system_has_not_seen_is_not_guessed_at(self):
        """An unrecognised share issue stays unknown rather than becoming the commonest kind.

        A share issue read as a cash dividend rescales nothing; a cash dividend
        read as a bonus rescales everything. Neither error announces itself, so
        the only safe answer to unfamiliar wording is that it is unfamiliar.
        """
        assert classify("ISS", "Share Issue - Convertible bond exercise") is (
            ActionKind.UNKNOWN
        )

    def test_a_payment_row_titled_like_a_share_issue_is_refused(self):
        """The code and the title disagreeing is not a case to resolve by preference."""
        assert classify("DIV", "Share Issue - Stock dividend ratio 15.0%") is (
            ActionKind.UNKNOWN
        )


class TestWhatAStoredRowDeclares:
    def test_a_cash_dividends_ratio_column_is_never_read_as_a_share_ratio(self):
        """1,000 VND arrives as 0.10, and 0.10 is not a 10% bonus issue.

        This is the single most damaging misreading available in this feed: it
        turns every dividend into a share-count change, and the resulting factor
        looks entirely reasonable.
        """
        with open_session() as session:
            cash, = save(session, ACB_CASH_2025)
            terms = terms_of(cash)

        assert terms.kind is ActionKind.CASH_DIVIDEND
        assert terms.cash_per_share == Decimal("1000.00")
        assert terms.ratio is None
        assert terms.changes_share_count is False

    def test_a_share_issue_declares_its_ratio_and_no_payment(self):
        with open_session() as session:
            stock, = save(session, ACB_STOCK_2025)
            terms = terms_of(stock)

        assert terms.kind is ActionKind.STOCK_DIVIDEND
        assert terms.ratio == Decimal("0.15")
        assert terms.cash_per_share is None
        assert terms.changes_share_count is True

    def test_whether_the_share_count_moves_is_answerable_from_the_row(self):
        """ADR-0006 makes a downstream field depend on this, so it is stored.

        A share-count change breaks every ``*_volume`` field and leaves every
        ``*_value_vnd`` field alone. A reader that had to re-parse the title to
        find that out would be re-deriving the one column the distinction turns
        on, once per window.
        """
        with open_session() as session:
            cash, stock = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            assert cash.changes_share_count is False
            assert stock.changes_share_count is True


class TestTheAdjustmentFactor:
    def test_a_blend_is_not_the_ratio_its_bonus_alone_implies(self):
        """ACB 2025-05-23: a 15% stock dividend and a 1,000 VND dividend, together.

        The real reference the exchange set that morning is
        (25,550 − 1,000) ÷ 1.15 = 21,347.8, which is 0.8355 of the previous
        close. The stock dividend alone gives 0.8696 — a 4% error applied to
        every price before that date, in the plausible direction.
        """
        with open_session() as session:
            store_acb_sessions(session)
            actions = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            CorporateActionStore(session).confirm_pending("ACB")
            anchor = previous_close(session, "ACB", date(2025, 5, 23))
            reading = adjustment_factor(actions, anchor)

        assert anchor == Decimal("25550.0")
        assert reading.factor == pytest.approx(Decimal("0.8355314"), abs=1e-7)
        assert reading.factor != pytest.approx(Decimal(1) / Decimal("1.15"), abs=1e-4)

    def test_the_share_count_ratio_is_not_the_price_factor(self):
        """One multiplies quantities by 1.15 while the other multiplies prices by 0.8355.

        Rescaling a traded quantity by the price factor would be wrong by exactly
        the cash dividend, which is why the two travel as separate numbers rather
        than one being derived from the other.
        """
        with open_session() as session:
            store_acb_sessions(session)
            actions = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            CorporateActionStore(session).confirm_pending("ACB")
            reading = adjustment_factor(
                actions, previous_close(session, "ACB", date(2025, 5, 23))
            )

        assert reading.share_count_ratio == Decimal("1.15")

    def test_an_unconfirmed_action_cannot_drive_arithmetic(self):
        """The gate, stated as arithmetic rather than as a convention.

        An action nobody has corroborated is exactly the case where a factor
        would be applied to a series that never moved, so the refusal is the
        answer rather than a caveat attached to a number.
        """
        with open_session() as session:
            store_acb_sessions(session)
            actions = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            # deliberately not confirmed
            reading = adjustment_factor(actions, Decimal("25550.0"))

        assert reading.factor is None
        assert reading.refusal is SignalIssue.UNCONFIRMED_CORPORATE_ACTION

    def test_a_rights_issue_is_confirmed_and_still_refuses_a_factor(self):
        """MBB 2026-08-11 gapped, so the date is certain and the size is not.

        The reference that morning was (24,250 + 0.10 × 10,000) ÷ 1.25 = 20,200,
        and that 10,000 is the subscription price — knowledge from outside the
        feed, which carries no such column. Guessing par would put a confident
        number on the one term that decides the answer.
        """
        with open_session() as session:
            store_mbb_sessions(session)
            actions = save(session, MBB_STOCK_2026, MBB_RIGHTS_2026)
            CorporateActionStore(session).confirm_pending("MBB")
            confirmations = {action.confirmation for action in actions}
            reading = adjustment_factor(
                actions, previous_close(session, "MBB", date(2026, 8, 11))
            )

        assert confirmations == {Confirmation.CONFIRMED.value}
        assert reading.factor is None
        assert reading.refusal is SignalIssue.CORPORATE_ACTION_TERMS_INCOMPLETE

    def test_one_date_is_one_calculation(self):
        """Actions on two dates cannot be blended, and saying so is not optional.

        Multiplying two dates' factors together is the shape of the right answer
        for a window, but it is not this function's answer, and quietly accepting
        the input would make the two indistinguishable at the call site.
        """
        with open_session() as session:
            store_acb_sessions(session)
            cash, stock = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            stock.ex_date = date(2025, 5, 26)
            with pytest.raises(ValueError, match="one ex-date"):
                adjustment_factor((cash, stock), Decimal("25550.0"))


class TestConfirmingAnExDate:
    def test_a_gap_beyond_the_bands_floor_confirms_the_date(self):
        """ACB fell 15.5% on a board that permits 7%, so the session is not ordinary."""
        with open_session() as session:
            store_acb_sessions(session)
            actions = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            verdict = confirm_ex_date(session, "ACB", date(2025, 5, 23), actions)

        assert verdict.confirmation is Confirmation.CONFIRMED
        assert verdict.reason is None

    def test_a_move_inside_the_band_is_not_read_as_a_gap(self):
        """The band regime is what makes the test mean anything.

        Without it, "the price fell" is the whole test, and an ordinary −3%
        session would confirm an action that never happened — which is precisely
        how a wrong ex-date gets to rescale a year of prices.
        """
        with open_session() as session:
            list_on(session, "ACB", Exchange.HOSE)
            write_session(session, "ACB", date(2025, 5, 22), close=25550.0)
            write_session(
                session, "ACB", date(2025, 5, 23), close=24800.0, high=25000.0, low=24750.0
            )
            actions = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            verdict = confirm_ex_date(session, "ACB", date(2025, 5, 23), actions)

        assert verdict.confirmation is Confirmation.UNCONFIRMED
        assert verdict.reason is ConfirmationReason.NO_CORROBORATING_GAP

    def test_an_effect_too_small_to_show_is_not_a_contradiction(self):
        """A 700 VND dividend on a 25,000 VND share is 2.8% against a ±7% band.

        No gap could ever corroborate it, so the row is not wrong — the
        instrument does not reach. Reported as its own reason, because "waiting
        for evidence that cannot exist" and "the prices say otherwise" ask for
        different things from whoever reads them.
        """
        with open_session() as session:
            list_on(session, "ACB", Exchange.HOSE)
            write_session(session, "ACB", date(2026, 6, 12), close=25000.0)
            write_session(
                session, "ACB", date(2026, 6, 15), close=24300.0, high=24400.0, low=24250.0
            )
            small = CorporateActionEvent(
                symbol="ACB",
                event_code="DIV",
                title="Cash Dividend - Year 2025 - 700 VND",
                ex_date=date(2026, 6, 15),
                public_date=date(2026, 6, 5),
                exercise_ratio=0.07,
                value_per_share=700.0,
            )
            actions = save(session, small)
            verdict = confirm_ex_date(session, "ACB", date(2026, 6, 15), actions)

        assert verdict.confirmation is Confirmation.UNCONFIRMED
        assert verdict.reason is ConfirmationReason.EFFECT_WITHIN_BAND

    def test_a_session_the_store_cannot_measure_leaves_the_verdict_open(self):
        """No anchor session means no band, and no band means no test.

        Distinct from a contradiction: this action may well be real, and a later
        run with the prices loaded will say so.
        """
        with open_session() as session:
            list_on(session, "ACB", Exchange.HOSE)
            write_session(session, "ACB", date(2025, 5, 23), close=21600.0)
            actions = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            verdict = confirm_ex_date(session, "ACB", date(2025, 5, 23), actions)

        assert verdict.confirmation is Confirmation.UNCONFIRMED
        assert verdict.reason is ConfirmationReason.SESSION_UNDECIDED

    def test_confirmation_reads_raw_prices_only(self):
        """An ``adjusted_at_source`` session has this very action folded into it.

        Anchoring to one would compare a series against itself after the fact,
        find no gap, and refuse the action that produced the adjustment.
        """
        with open_session() as session:
            list_on(session, "ACB", Exchange.HOSE)
            write_session(
                session,
                "ACB",
                date(2025, 5, 22),
                close=25550.0,
                source=ProviderSource.VNSTOCK,
            )
            write_session(
                session,
                "ACB",
                date(2025, 5, 23),
                close=21600.0,
                high=21600.0,
                low=21450.0,
                source=ProviderSource.VNSTOCK,
            )
            actions = save(session, ACB_CASH_2025, ACB_STOCK_2025)
            verdict = confirm_ex_date(session, "ACB", date(2025, 5, 23), actions)

        assert verdict.confirmation is Confirmation.UNCONFIRMED
        assert verdict.reason is ConfirmationReason.SESSION_UNDECIDED


class TestAnActionWithNoExDate:
    def test_it_is_stored_rather_than_dropped(self):
        """TCB's 2026 bonus issue is announced with a ratio and no date.

        Dropping it would be the tidier table and the worse answer: an action
        nobody knows the date of is exactly what makes a window unadjustable, and
        a window cannot be degraded for a row that was never written.
        """
        with open_session() as session:
            saved, = save(session, TCB_BONUS_UNDATED)
            undated = CorporateActionStore(session).undated("TCB")

        assert saved.ex_date is None
        assert saved.exercise_ratio == 0.6
        assert [row.title for row in undated] == [TCB_BONUS_UNDATED.title]

    def test_it_is_unconfirmed_and_says_why(self):
        with open_session() as session:
            saved, = save(session, TCB_BONUS_UNDATED)

        assert saved.confirmation == Confirmation.UNCONFIRMED.value
        assert saved.confirmation_reason == ConfirmationReason.NO_EX_DATE.value

    def test_it_cannot_drive_arithmetic(self):
        """Not by being refused, but by not being addressable at all.

        A factor is computed for an ex-date. An action without one belongs to no
        date, so there is no calculation for it to be part of.
        """
        with open_session() as session:
            saved, = save(session, TCB_BONUS_UNDATED)
            with pytest.raises(ValueError, match="one ex-date"):
                adjustment_factor((saved,), Decimal("30000.0"))

    def test_it_is_not_in_any_window(self):
        """``for_symbol`` answers with dated actions, because a window is dates."""
        with open_session() as session:
            save(session, TCB_BONUS_UNDATED)
            windowed = CorporateActionStore(session).for_symbol(
                "TCB", start=date(2026, 1, 1), end=date(2026, 12, 31)
            )

        assert windowed == ()

    def test_the_date_arriving_later_updates_the_row_it_was_announced_as(self):
        """The feed fills an ex-date in eventually, and that is not a new action.

        Two rows for one bonus issue would double-count it: the window would be
        adjusted twice and the share count multiplied twice.
        """
        dated = TCB_BONUS_UNDATED.model_copy(update={"ex_date": date(2026, 6, 2)})
        with open_session() as session:
            save(session, TCB_BONUS_UNDATED)
            save(session, dated)
            store = CorporateActionStore(session)
            held = store.for_symbol("TCB")

        assert len(held) == 1
        assert held[0].ex_date == date(2026, 6, 2)
        assert held[0].confirmation_reason is None


class FakeActionProvider:
    """A feed that answers from a script and counts what it was asked."""

    source = ProviderSource.VNSTOCK

    def __init__(self, by_symbol: dict[str, tuple[CorporateActionEvent, ...]]) -> None:
        self._by_symbol = by_symbol
        self.calls: list[str] = []

    def fetch_corporate_actions(self, symbol: str):
        self.calls.append(symbol)
        if symbol == "BOOM":
            raise RuntimeError("the feed refused this symbol")
        return self._by_symbol.get(symbol, ())


class TestTheCollector:
    def test_a_second_run_stores_no_second_copy(self):
        """Idempotent on the identity the table enforces.

        The load re-reads a company's whole event history every run, so without
        this a year of weekly runs is fifty-two copies of one bonus issue — and
        the series would read as fifty-two corporate actions.
        """
        provider = FakeActionProvider(
            {"ACB": (ACB_CASH_2025, ACB_STOCK_2025), "TCB": (TCB_BONUS_UNDATED,)}
        )
        with open_session() as session:
            store_acb_sessions(session)
            collector = CorporateActionCollector(session, provider, now=lambda: NOW)
            collector.run(("ACB", "TCB"))
            collector.run(("ACB", "TCB"))
            store = CorporateActionStore(session)
            acb = store.for_symbol("ACB")
            tcb = store.undated("TCB")

        assert len(acb) == 2
        assert len(tcb) == 1

    def test_two_share_issues_on_one_date_are_both_kept(self):
        """MBB's 2026-08-11 carries a stock dividend and a rights issue, both ``ISS``.

        Keyed on symbol, date and event code alone, the second would overwrite
        the first — and half of an adjustment that has to be computed from both
        at once would simply be gone.
        """
        provider = FakeActionProvider({"MBB": (MBB_STOCK_2026, MBB_RIGHTS_2026)})
        with open_session() as session:
            store_mbb_sessions(session)
            CorporateActionCollector(session, provider, now=lambda: NOW).run(("MBB",))
            held = CorporateActionStore(session).for_symbol("MBB")

        assert {ActionKind(row.kind) for row in held} == {
            ActionKind.STOCK_DIVIDEND,
            ActionKind.RIGHTS_ISSUE,
        }

    def test_one_request_per_symbol_and_no_more(self):
        """The allowance is the binding constraint, so the shape of the run is the guard.

        vnstock answers an exhausted quota by exiting the process, and the pacer
        can only space out calls that were made. A run that asked twice per
        symbol would double a five-minute Universe pass with nothing to show.
        """
        provider = FakeActionProvider({"ACB": (ACB_CASH_2025,)})
        with open_session() as session:
            store_acb_sessions(session)
            CorporateActionCollector(session, provider, now=lambda: NOW).run(
                ("ACB", "TCB", "MBB")
            )

        assert provider.calls == ["ACB", "TCB", "MBB"]

    def test_a_symbol_the_feed_refuses_costs_only_itself(self):
        provider = FakeActionProvider({"ACB": (ACB_CASH_2025, ACB_STOCK_2025)})
        with open_session() as session:
            store_acb_sessions(session)
            summary = CorporateActionCollector(session, provider, now=lambda: NOW).run(
                ("BOOM", "ACB")
            )

        assert [item.symbol for item in summary.failed] == ["BOOM"]
        assert summary.completed == ("ACB",)
        assert summary.actions_stored == 2

    def test_the_run_confirms_what_the_prices_now_support(self):
        """Announcement and corroboration are separated by weeks of sessions.

        An action is written by the run that first sees it announced and
        confirmed by a later one, once the ex-date's prices have been collected —
        which is why this is a recurring job rather than a one-off import.
        """
        provider = FakeActionProvider({"ACB": (ACB_CASH_2025, ACB_STOCK_2025)})
        with open_session() as session:
            collector = CorporateActionCollector(session, provider, now=lambda: NOW)
            before = collector.run(("ACB",))
            unconfirmed = {
                row.confirmation for row in CorporateActionStore(session).for_symbol("ACB")
            }

            store_acb_sessions(session)
            after = collector.run(("ACB",))
            confirmed = {
                row.confirmation for row in CorporateActionStore(session).for_symbol("ACB")
            }

        assert before.actions_confirmed == 0
        assert unconfirmed == {Confirmation.UNCONFIRMED.value}
        assert after.actions_confirmed == 2
        assert confirmed == {Confirmation.CONFIRMED.value}

    def test_a_confirmed_action_is_not_rejudged(self):
        """The verdict was made against raw prices of a session that will not change.

        Re-judging would also make the verdict depend on what else is in the
        store at the time, so an action confirmed in May could quietly
        un-confirm in June.
        """
        provider = FakeActionProvider({"ACB": (ACB_CASH_2025, ACB_STOCK_2025)})
        with open_session() as session:
            store_acb_sessions(session)
            collector = CorporateActionCollector(session, provider, now=lambda: NOW)
            collector.run(("ACB",))
            again = collector.run(("ACB",))

        assert again.actions_confirmed == 0
