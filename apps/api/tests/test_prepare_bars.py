"""What the one gateway to bars serves, and what it refuses to serve.

``prepare_bars()`` exists so the Vietnamese-market hazard list is enforced once
rather than remembered fourteen times, so almost every test here is about a
window that must not be handed to a computation:

*Two price conventions in one window is not a weaker window.* A raw close and an
``adjusted_at_source`` close are not two measurements of the same thing, so the
window is refused rather than measured and flagged.

*A session that broke its band is a wrong anchor, not a wild market.* The stored
action series is the only thing that tells an ex-date apart from a price move
nothing explains, and without one on that date the window is refused.

*An action changes prices and sometimes share counts, and never the same way.*
ACB's 2025 ex-date multiplies past prices by 0.8355 and the share count by 1.15.
A window that rescaled quantities by the price factor would be wrong by exactly
the cash dividend.

The prices around ACB's 2025-05-23 ex-date and MBB's 2025-08-14 ceiling lock are
real rows out of this system's own store, reached through the same helpers the
band-regime tests use. The sessions padding a window out to its length are flat
and invented, and are marked as such where they matter: they are calendar, not
evidence.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import Exchange, PriceBasis, ProviderSource
from src.stocks.signals.bars import prepare_bars
from src.stocks.signals.fields import (
    PERCENTILE_ABSOLUTE_FLOOR,
    min_sample_for,
)
from src.stocks.signals.corporate_actions import CorporateActionStore
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.price_band import LimitLock

from .test_corporate_actions import ACB_CASH_2025, ACB_STOCK_2025, save
from .test_price_band import list_on, write_session

# ACB's real ex-date, and the two sessions the store holds around it.
ACB_EX_DATE = date(2025, 5, 23)
ACB_BLEND_FACTOR = Decimal("0.8355314")


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


def weekdays(first: date, last: date) -> tuple[date, ...]:
    """Every weekday in a closed range, oldest first.

    The store's own definition of a Trading Day is a day it holds a session for,
    so writing weekdays is what gives these tests a calendar at all. Weekends are
    skipped so a window of eight sessions stretches wider than eight days —
    the only way a test can tell the two apart.
    """
    days: list[date] = []
    cursor = first
    while cursor <= last:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return tuple(days)


def store_acb_window(session: Session) -> tuple[date, ...]:
    """ACB across its 2025 ex-date, padded to a window's worth of sessions.

    The three sessions around 2025-05-23 are the real ones. The rest are flat at
    the closest real close, which keeps every one of them inside its band and
    leaves the ex-date as the only thing in the window that moves.
    """
    list_on(session, "ACB", Exchange.HOSE)
    days = weekdays(date(2025, 5, 15), date(2025, 5, 28))
    for day in days:
        if day == date(2025, 5, 21):
            write_session(session, "ACB", day, close=25_650.0, high=25_900.0, low=25_600.0)
        elif day == date(2025, 5, 22):
            write_session(session, "ACB", day, close=25_550.0, high=25_750.0, low=25_500.0)
        elif day == ACB_EX_DATE:
            write_session(session, "ACB", day, close=21_600.0, high=21_600.0, low=21_450.0)
        elif day < ACB_EX_DATE:
            write_session(session, "ACB", day, close=25_650.0)
        else:
            write_session(session, "ACB", day, close=21_600.0)
    return days


def store_mbb_window(session: Session) -> tuple[date, ...]:
    """MBB across its real 2025-08-14 ceiling lock, padded either side.

    25,800 → 27,606 → 27,600 is the rounding this system's store actually holds,
    and the sessions around it are flat so that the lock is the only session in
    the window with anywhere to be.
    """
    list_on(session, "MBB", Exchange.HOSE)
    days = weekdays(date(2025, 8, 8), date(2025, 8, 18))
    for day in days:
        if day == date(2025, 8, 14):
            write_session(
                session,
                "MBB",
                day,
                open_price=27_600.0,
                high=27_600.0,
                low=27_600.0,
                close=27_600.0,
                volume=40_356_994,
            )
        elif day > date(2025, 8, 14):
            write_session(session, "MBB", day, close=27_600.0)
        else:
            write_session(session, "MBB", day, close=25_800.0)
    return days


class TestAWindowTheGatewayServes:
    def test_a_clean_window_comes_back_whole_and_says_what_it_is_made_of(self):
        with open_session() as session:
            days = store_mbb_window(session)
            frame, health = prepare_bars(session, "MBB", 5, end=days[-1])

        assert frame is not None
        assert health.refusal is None
        assert health.sessions_used == 5
        assert len(frame) == 5
        assert frame.sessions == days[-5:]
        assert health.first_session == days[-5]
        assert health.last_session == days[-1]

    def test_the_newest_trading_day_is_the_default_end(self):
        """A window asked for without an end is the trailing one, always."""
        with open_session() as session:
            days = store_mbb_window(session)
            frame, _ = prepare_bars(session, "MBB", 3)

        assert frame is not None
        assert frame.sessions[-1] == days[-1]

    def test_the_band_the_window_was_judged_against_travels_with_it(self):
        with open_session() as session:
            days = store_mbb_window(session)
            _, health = prepare_bars(session, "MBB", 5, end=days[-1])

        assert health.band_regime is not None
        assert health.band_regime.exchange is Exchange.HOSE
        assert health.band_regime.limit_ratio == Decimal("0.07")
        assert health.band_regime.uniform is True


class TestTooLittleHistoryIsRefusedRatherThanShortened:
    def test_a_window_shorter_than_the_floor_refuses(self):
        """Never a silently shortened window — that is a different baseline."""
        with open_session() as session:
            days = store_mbb_window(session)
            frame, health = prepare_bars(session, "MBB", 60, end=days[-1])

        assert frame is None
        assert health.refusal is SignalIssue.INSUFFICIENT_HISTORY

    def test_the_refusal_still_reports_how_far_it_got(self):
        """Forty of sixty sessions and none of sixty are different situations.

        A caller deciding whether a Warm-up would fix this has to be able to tell
        them apart, so the count that was reached survives the refusal.
        """
        with open_session() as session:
            days = store_mbb_window(session)
            _, health = prepare_bars(session, "MBB", 60, end=days[-1])

        assert health.sessions_used == len(days)
        assert health.min_sessions == 60

    def test_a_field_may_set_a_floor_below_the_window_it_asks_for(self):
        """``min_sessions`` is the field's bar, and the window is what it wants."""
        with open_session() as session:
            days = store_mbb_window(session)
            frame, health = prepare_bars(
                session, "MBB", 60, min_sessions=5, end=days[-1]
            )

        assert frame is not None
        assert health.refusal is None
        assert health.sessions_used == len(days)

    def test_a_store_holding_no_session_at_all_refuses(self):
        with open_session() as session:
            frame, health = prepare_bars(session, "ACB", 20)

        assert frame is None
        assert health.refusal is SignalIssue.INSUFFICIENT_HISTORY


class TestTheTwoPriceBasisRefusals:
    def test_a_window_crossing_the_seam_is_refused_as_meaningless(self):
        """One adjusted session among raw ones is not a weaker window.

        The seam is where a symbol's Backfill happened to run, so it falls in a
        different place for every symbol and cannot be a date. A window holding
        both sides of it is refused rather than stamped and measured.
        """
        with open_session() as session:
            days = store_mbb_window(session)
            write_session(
                session,
                "MBB",
                days[-2],
                close=27_600.0,
                source=ProviderSource.VNSTOCK,
            )
            # The Main Source row for that session is removed, so the Cover
            # Source's adjusted one is the session rather than losing to it.
            _drop_main_row(session, "MBB", days[-2])

            frame, health = prepare_bars(session, "MBB", 5, end=days[-1])

        assert frame is None
        assert health.refusal is SignalIssue.MIXED_PRICE_BASIS

    def test_a_window_wholly_in_the_adjusted_era_is_refused(self):
        """Not for being mixed: that basis was fixed at somebody's ``observed_at``.

        It has decayed with every action since and cannot be recomputed from
        anything stored, so there is nothing to serve.
        """
        with open_session() as session:
            list_on(session, "ACB", Exchange.HOSE)
            days = weekdays(date(2025, 5, 15), date(2025, 5, 28))
            for day in days:
                write_session(
                    session, "ACB", day, close=25_650.0, source=ProviderSource.VNSTOCK
                )

            frame, health = prepare_bars(session, "ACB", 5, end=days[-1])

        assert frame is None
        assert health.refusal is SignalIssue.UNADJUSTABLE_PRICE_BASIS

    def test_the_basis_is_read_off_the_row_and_not_off_its_source(self):
        """The whole reason the field is on the Snapshot rather than in a flag.

        A Main Source row stamped ``adjusted_at_source`` is refused exactly like
        a Cover Source one. Nothing here consults which provider wrote it, so a
        provider that changes its flag tomorrow does not change what an
        already-stored window reports.
        """
        with open_session() as session:
            list_on(session, "ACB", Exchange.HOSE)
            days = weekdays(date(2025, 5, 15), date(2025, 5, 28))
            for day in days:
                write_session(
                    session,
                    "ACB",
                    day,
                    close=25_650.0,
                    source=ProviderSource.FIINQUANT,
                    basis=PriceBasis.ADJUSTED_AT_SOURCE,
                )

            frame, health = prepare_bars(session, "ACB", 5, end=days[-1])

        assert frame is None
        assert health.refusal is SignalIssue.UNADJUSTABLE_PRICE_BASIS


class TestAPriceMoveNothingExplains:
    def test_a_gap_with_no_stored_action_on_that_date_refuses(self):
        """ACB fell 15.5% on a board that permits 7%, and nothing says why.

        Until an action is stored for that date the honest answer is that the
        window contains a move this system cannot account for — the anchor is
        wrong, and every price on one side of it is incomparable with every price
        on the other.
        """
        with open_session() as session:
            days = store_acb_window(session)
            frame, health = prepare_bars(session, "ACB", 8, end=days[-1])

        assert frame is None
        assert health.refusal is SignalIssue.UNEXPLAINED_PRICE_GAP

    def test_a_window_that_stops_short_of_the_gap_is_served(self):
        """The refusal is about the window, not about the symbol."""
        with open_session() as session:
            store_acb_window(session)
            frame, health = prepare_bars(
                session, "ACB", 3, end=date(2025, 5, 22)
            )

        assert frame is not None
        assert health.refusal is None

    def test_a_break_upward_is_refused_even_with_an_action_on_the_date(self):
        """No entitlement is ever added to a share, so no action produces one.

        Taking an action as the explanation for an upward break would let a rally
        excuse a wrong anchor of some entirely different kind.
        """
        with open_session() as session:
            list_on(session, "ACB", Exchange.HOSE)
            days = weekdays(date(2025, 5, 15), date(2025, 5, 28))
            for day in days:
                if day == ACB_EX_DATE:
                    write_session(
                        session,
                        "ACB",
                        day,
                        close=30_000.0,
                        high=30_000.0,
                        low=29_500.0,
                    )
                else:
                    write_session(session, "ACB", day, close=25_650.0)
            save(session, ACB_CASH_2025, ACB_STOCK_2025)

            frame, health = prepare_bars(session, "ACB", 8, end=days[-1])

        assert frame is None
        assert health.refusal is SignalIssue.UNEXPLAINED_PRICE_GAP


class TestTheReadTimeAdjustment:
    def test_a_confirmed_action_is_applied_and_the_window_says_so(self):
        """ACB 2025-05-23: (25,550 − 1,000) ÷ 1.15 is 0.8355 of the close before.

        The blend is the point. The stock dividend alone implies 0.8696, which is
        4% away, on every price before that date, in the direction that looks
        entirely reasonable.
        """
        with open_session() as session:
            days = store_acb_window(session)
            save(session, ACB_CASH_2025, ACB_STOCK_2025)
            CorporateActionStore(session).confirm_pending("ACB")

            frame, health = prepare_bars(session, "ACB", 8, end=days[-1])

        assert frame is not None
        assert health.refusal is None
        assert health.adjustment.applied is True
        assert health.adjustment.actions_applied == 2
        assert health.adjustment.ex_dates_applied == (ACB_EX_DATE,)

        before = {bar.session_date: bar for bar in frame.bars}[date(2025, 5, 22)]
        after = {bar.session_date: bar for bar in frame.bars}[ACB_EX_DATE]
        assert before.adjustment_factor == pytest.approx(ACB_BLEND_FACTOR, abs=1e-7)
        assert before.close == pytest.approx(25_550.0 * float(ACB_BLEND_FACTOR), abs=1e-2)
        assert after.adjustment_factor == Decimal(1)
        assert after.close == 21_600.0

    def test_the_windows_newest_prices_are_the_ones_the_exchange_published(self):
        """Adjustment rebases the past onto the present, never the other way."""
        with open_session() as session:
            days = store_acb_window(session)
            save(session, ACB_CASH_2025, ACB_STOCK_2025)
            CorporateActionStore(session).confirm_pending("ACB")
            frame, _ = prepare_bars(session, "ACB", 8, end=days[-1])

        assert frame is not None
        assert frame.bars[-1].adjustment_factor == Decimal(1)
        assert frame.bars[-1].close == 21_600.0

    def test_a_quantity_is_never_rescaled_by_the_price_factor(self):
        """The share count goes up by 1.15 while prices go down by 0.8355.

        Rescaling a quantity by the price factor would be wrong by exactly the
        cash dividend, and it would break the ``close × volume`` reconciliation
        that makes a stored row checkable at all.
        """
        with open_session() as session:
            days = store_acb_window(session)
            save(session, ACB_CASH_2025, ACB_STOCK_2025)
            CorporateActionStore(session).confirm_pending("ACB")
            frame, _ = prepare_bars(session, "ACB", 8, end=days[-1])

        assert frame is not None
        assert all(bar.volume == 1_000_000 for bar in frame.bars)

    def test_a_window_with_no_action_in_it_reports_no_adjustment(self):
        with open_session() as session:
            days = store_mbb_window(session)
            frame, health = prepare_bars(session, "MBB", 5, end=days[-1])

        assert frame is not None
        assert health.adjustment.applied is False
        assert health.adjustment.actions_in_window == 0
        assert all(bar.adjustment_factor == Decimal(1) for bar in frame.bars)


class TestTheTwoDegradations:
    def test_an_action_nothing_corroborates_degrades_rather_than_adjusts(self):
        """Stored, dated, and never confirmed — so it may not drive arithmetic.

        The window is still served: the gap is accounted for by an action this
        system holds. What it may not do is quietly rebase prices off a row
        nothing has checked.
        """
        with open_session() as session:
            days = store_acb_window(session)
            save(session, ACB_CASH_2025, ACB_STOCK_2025)

            frame, health = prepare_bars(session, "ACB", 8, end=days[-1])

        assert frame is not None
        assert SignalIssue.UNCONFIRMED_CORPORATE_ACTION in health.degradations
        assert health.adjustment.applied is False

    def test_a_share_count_change_breaks_the_quantities_and_not_the_prices(self):
        with open_session() as session:
            days = store_acb_window(session)
            save(session, ACB_CASH_2025, ACB_STOCK_2025)
            CorporateActionStore(session).confirm_pending("ACB")

            frame, health = prepare_bars(session, "ACB", 8, end=days[-1])

        assert frame is not None
        assert SignalIssue.VOLUME_BASIS_BREAK in health.degradations
        assert health.quantities_comparable is False
        assert health.adjustment.applied is True

    def test_a_cash_dividend_alone_leaves_the_quantities_comparable(self):
        """The distinction the exercise ratio carries and a dividend record does not.

        Money out of the company moves the reference price and leaves every share
        outstanding exactly where it was, so a traded quantity either side of it
        is the same measurement.
        """
        with open_session() as session:
            days = store_acb_window(session)
            save(session, ACB_CASH_2025)
            CorporateActionStore(session).confirm_pending("ACB")

            frame, health = prepare_bars(session, "ACB", 8, end=days[-1])

        assert frame is not None
        assert SignalIssue.VOLUME_BASIS_BREAK not in health.degradations
        assert health.quantities_comparable is True


class TestLimitLockDaysAreCountedAndExcludableRatherThanDropped:
    def test_a_locked_session_is_counted_and_named(self):
        """MBB on 2025-08-14: 25,800 → 27,600, and it never left the ceiling."""
        with open_session() as session:
            days = store_mbb_window(session)
            frame, health = prepare_bars(session, "MBB", 5, end=days[-1])

        assert frame is not None
        assert health.limit_lock_days == 1
        assert health.limit_lock_dates == (date(2025, 8, 14),)
        locked = {bar.session_date: bar.limit_lock for bar in frame.bars}
        assert locked[date(2025, 8, 14)] is LimitLock.CEILING

    def test_the_locked_sessions_can_be_taken_out_of_a_robust_baseline(self):
        """A run of zero range deflates a MAD baseline and manufactures z elsewhere.

        The exclusion is a seam on the frame rather than something each field
        remembers, and what was excluded stays on the health report — so a
        baseline that dropped them still says they were there.
        """
        with open_session() as session:
            days = store_mbb_window(session)
            frame, health = prepare_bars(session, "MBB", 5, end=days[-1])

        assert frame is not None
        trimmed = frame.without_limit_locks()
        assert len(trimmed) == len(frame) - 1
        assert date(2025, 8, 14) not in trimmed.sessions
        assert health.limit_lock_days == 1

    def test_a_session_that_stayed_inside_its_band_is_not_a_lock(self):
        with open_session() as session:
            days = store_mbb_window(session)
            frame, _ = prepare_bars(session, "MBB", 5, end=days[-1])

        assert frame is not None
        locked = {bar.session_date: bar.limit_lock for bar in frame.bars}
        assert locked[date(2025, 8, 13)] is LimitLock.NONE


class TestNothingIsComputedFromTheWholeSample:
    def test_one_session_reads_the_same_from_two_different_window_ends(self):
        """The measured lookahead bias, designed out.

        The same event once scored z = +151.5 on a short run and z = +135.6 on a
        longer one, because its baseline had quietly read the whole sample. Every
        per-session verdict this gateway makes depends on that session and the
        one before it and on nothing else, so a longer window cannot change what
        a session already said.
        """
        with open_session() as session:
            days = store_mbb_window(session)
            short_frame, _ = prepare_bars(session, "MBB", 4, end=date(2025, 8, 14))
            long_frame, _ = prepare_bars(session, "MBB", 6, end=days[-1])

        assert short_frame is not None and long_frame is not None
        short = {bar.session_date: bar for bar in short_frame.bars}
        long = {bar.session_date: bar for bar in long_frame.bars}
        shared = set(short) & set(long)
        assert len(shared) >= 4
        for day in shared:
            assert short[day] == long[day]

    def test_across_an_action_the_facts_hold_and_only_the_rebasing_moves(self):
        """The one number that is window-relative, and why that is not the bias.

        Adjustment expresses a window's prices in the share terms of that
        window's last session, so a longer window that reaches past an ex-date
        rebases a bar the shorter one did not. That is a rebasing rather than a
        statistic — extending it to actions *after* the window would make a
        historical window depend on its own future, which is the bias by another
        road — and every per-session verdict underneath it is unchanged.
        """
        with open_session() as session:
            days = store_acb_window(session)
            save(session, ACB_CASH_2025, ACB_STOCK_2025)
            CorporateActionStore(session).confirm_pending("ACB")

            before_action, _ = prepare_bars(
                session, "ACB", 3, end=date(2025, 5, 22)
            )
            across_action, _ = prepare_bars(session, "ACB", 8, end=days[-1])

        assert before_action is not None and across_action is not None
        shared = date(2025, 5, 22)
        short = {bar.session_date: bar for bar in before_action.bars}[shared]
        long = {bar.session_date: bar for bar in across_action.bars}[shared]

        # The facts about the session are the same in both.
        assert short.limit_lock == long.limit_lock
        assert short.volume == long.volume
        assert short.close is not None and long.close is not None

        # The rebasing is not, and the raw price it was taken from is.
        assert short.adjustment_factor == Decimal(1)
        assert long.adjustment_factor == pytest.approx(ACB_BLEND_FACTOR, abs=1e-7)
        raw_short = Decimal(str(short.close)) / short.adjustment_factor
        raw_long = Decimal(str(long.close)) / long.adjustment_factor
        assert raw_short == pytest.approx(raw_long, abs=1e-6)


class TestHowThinTheSymbolIs:
    def test_the_window_is_ranked_against_its_peers_by_traded_money(self):
        """Money rather than shares: a corporate action leaves the first alone.

        An ADTV in shares crosses an ex-date and changes unit; an ADTV in dong
        does not, so it is the one that can be compared across a window at all.
        """
        with open_session() as session:
            days = _store_flat_cross_section(session, peers=32, sessions=20)
            peers = [f"P{index:02d}" for index in range(32)]

            _, health = prepare_bars(
                session, "AAA", 20, end=days[-1], peers=[*peers, "AAA"]
            )

        # AAA trades 16 billion a session; seventeen of the thirty-two peers
        # (P00 through P16) trade that or less.
        assert health.adtv is not None
        assert health.adtv.percentile == pytest.approx(17 / 32)
        assert health.adtv.average_value_vnd == pytest.approx(16e9)

    def test_the_standing_carries_the_sample_it_was_ranked_in(self):
        """A percentile with no ``n`` and no cutoff date is one nobody can read.

        Both travel because ADR-0010 admits a percentile on no other terms: the
        number alone cannot say whether it was taken over the Universe or over
        the eleven names that happened to have traded.
        """
        with open_session() as session:
            days = _store_flat_cross_section(session, peers=32, sessions=20)
            peers = [f"P{index:02d}" for index in range(32)]

            _, health = prepare_bars(
                session, "AAA", 20, end=days[-1], peers=[*peers, "AAA"]
            )

        assert health.adtv is not None
        assert health.adtv.n == 32
        assert health.adtv.as_of == days[-1]

    def test_too_few_peers_to_rank_against_reports_nothing(self):
        """A percentile over eleven names is a rank dressed up as a distribution."""
        with open_session() as session:
            days = _store_flat_cross_section(session, peers=11, sessions=20)
            peers = [f"P{index:02d}" for index in range(11)]

            _, health = prepare_bars(
                session, "AAA", 20, end=days[-1], peers=[*peers, "AAA"]
            )

        assert health.adtv is None
        # Eleven names is under the absolute floor, so no share of the sample
        # rescues it.
        assert min_sample_for(11) == PERCENTILE_ABSOLUTE_FLOOR


def _store_flat_cross_section(
    session: Session,
    *,
    peers: int,
    sessions: int,
) -> tuple[date, ...]:
    """A flat market: one symbol under test and ``peers`` others beside it.

    Every price is the same so that nothing in the window moves; the only thing
    that differs between symbols is the money that changed hands, which is the
    question being asked.
    """
    days = weekdays(date(2025, 3, 3), date(2025, 3, 3) + timedelta(days=60))[
        : sessions + 1
    ]
    list_on(session, "AAA", Exchange.HOSE)
    for day in days:
        write_session(
            session, "AAA", day, close=20_000.0, total_value_vnd=16e9
        )
    for index in range(peers):
        symbol = f"P{index:02d}"
        list_on(session, symbol, Exchange.HOSE)
        for day in days:
            write_session(
                session,
                symbol,
                day,
                close=20_000.0,
                total_value_vnd=float(index) * 1e9,
            )
    return days


def _drop_main_row(session: Session, symbol: str, day: date) -> None:
    """Remove the Main Source copy of one session, leaving the Cover Source's.

    Written as a deletion rather than by never storing the row, because the seam
    this test is about is a real one: the Cover Source loaded the deep years and
    the Main Source has written every session since, so a session held by only
    one of them is what the store actually looks like on either side of it.
    """
    from src.stocks.providers import Capability

    from .test_price_band import _stamp

    session.query(ProviderSnapshot).filter(
        ProviderSnapshot.capability == Capability.MARKET.value,
        ProviderSnapshot.symbol == symbol,
        ProviderSnapshot.source == ProviderSource.FIINQUANT.value,
        ProviderSnapshot.effective_at == _stamp(day),
    ).delete()
    session.flush()
