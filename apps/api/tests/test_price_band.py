"""Which band a session traded under, and whether it was locked at it.

The arithmetic is three lines. Everything else here is about the cases where
those three lines must not run, because each of them has a different honest
answer and every one of them produces a plausible number if it is allowed to:

*The exchange is not a property of the symbol, it is a property of the bar.*
HNX listings are moving to HOSE through 31/12/2026, so reading today's board off
the listing register and applying it to a 2025 bar silently swaps ±10 for ±7.

*The anchor the band is measured from is not the anchor the store holds.* On
HOSE and HNX the exchange's reference is the previous session's close, which is
reconstructible; on UPCOM it is the previous day's volume-weighted average of
round-lot continuous trades, which is not stored anywhere. Anchoring UPCOM to the
previous close would answer with the same confident shape and the wrong number.

*A move larger than the band means the anchor is wrong, not that the market
broke.* MBB's real 2025-08-13 session moves −20.37% against a ±7% band, because
that session is an ex-date and the exchange's reference was adjusted while the
previous close was not.

The three locked and gapped sessions pinned below are real rows out of this
system's own store, not invented ones: a fabricated ceiling would agree with
whatever rounding rule this file happened to implement, which is the one thing
these tests exist to check.
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import BarDaily, CorporateAction, ListingRoster
from src.stocks.providers import Exchange, PriceBasis, ProviderSource
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.issues import SignalIssue
from src.stocks.trading_day import CALENDAR_SERIES
from src.stocks.signals.price_band import (
    MIGRATION_PROGRAMME_END,
    BandAnchorBasis,
    ExchangeAsOf,
    ExchangeMigration,
    LimitLock,
    band_limits,
    detect_limit_lock,
    resolve_band_regime,
    tick_size,
)

from .conftest import basis_of

NOW = datetime(2026, 8, 13, 11, 0, tzinfo=timezone.utc)

#: The one symbol whose sessions define the calendar.
CALENDAR_SYMBOL = "VNINDEX"


def open_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        BarDaily.__table__,
        ListingRoster.__table__,
        # The stored action series: what tells an ex-date gap from a wrong
        # anchor, and what says whether the provider has rescaled a session
        # since it printed.
        CorporateAction.__table__,
    ):
        table.create(engine)
    return Session(engine)


def _stamp(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


def write_session(
    session: Session,
    symbol: str,
    day: date,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
    open_price: float | None = None,
    volume: int = 1_000_000,
    source: ProviderSource = ProviderSource.VNSTOCK,
    basis: PriceBasis = PriceBasis.RAW,
    series: str = "equity",
) -> None:
    """Store one session in the daily spine, defaulting the range to the close.

    ``high``/``low`` default to the close rather than to nothing, because an
    anchor session only ever needs its close and spelling out a range on every
    one of them would bury the ranges that are the point of the test.

    ``basis`` is stated rather than derived from ``source``, because in this
    table it is not derivable: ``bar_daily`` has one writer and the basis is a
    column. It defaults to ``raw`` because that is still the only basis the band
    machine can measure — a band is a percentage of a *published* reference
    price, and a rebased close is not one. Teaching it to read the spine's own
    adjusted rows is Phase 06 of the price-basis plan; until then this default is
    what keeps these tests about the band arithmetic instead of about the
    refusal in front of it.
    """
    resolved = basis
    if series == "equity":
        # The Trading Day calendar is the index series, so a market that held a
        # session has to say so there too. In production VNINDEX is filled by
        # its own backfill scope; a fixture writing only the equity row would be
        # describing a day the market never opened, and every anchor would go
        # missing.
        _mark_session_on_the_calendar(session, day)
    session.merge(
        BarDaily(
            symbol=symbol,
            trading_day=day,
            series=series,
            open=_decimal(open_price if open_price is not None else close),
            high=_decimal(high if high is not None else close),
            low=_decimal(low if low is not None else close),
            close=_decimal(close),
            volume=volume,
            price_basis=resolved.value,
            source=source.value,
            # When a run that waited for the close would have read it. Derived
            # from the session rather than pinned, because a row read before the
            # session it describes is one the store cannot hold.
            observed_at=datetime.combine(day, time(16, 30), tzinfo=VN_TZ),
        )
    )
    session.flush()


def _mark_session_on_the_calendar(session: Session, day: date) -> None:
    """One VNINDEX row, which is what makes ``day`` a Trading Day."""
    session.merge(
        BarDaily(
            symbol=CALENDAR_SYMBOL,
            trading_day=day,
            series=CALENDAR_SERIES,
            open=_decimal(1_800),
            high=_decimal(1_800),
            low=_decimal(1_800),
            close=_decimal(1_800),
            volume=1,
            price_basis=PriceBasis.ADJUSTED_AT_SOURCE.value,
            source=ProviderSource.VNSTOCK.value,
            observed_at=datetime.combine(day, time(16, 30), tzinfo=VN_TZ),
        )
    )


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def list_on(session: Session, symbol: str, exchange: Exchange) -> None:
    session.add(
        ListingRoster(
            symbol=symbol,
            exchange=exchange.value,
            is_listed=True,
            company_name=None,
            source=ProviderSource.VNSTOCK.value,
            observed_at=NOW,
        )
    )
    session.flush()


# One real HNX→HOSE move, shaped the way a register entry has to be shaped. The
# shipped register is empty until entries with dated primary sources exist, so
# the mechanism is exercised with a fixture rather than with production data.
MIGRATED = ExchangeMigration(
    symbol="ZZZ",
    from_exchange=Exchange.HNX,
    to_exchange=Exchange.HOSE,
    first_session=date(2026, 3, 2),
    citation="fixture",
)


class TestWhichBandAppliedToThisBar:
    def test_each_board_carries_its_own_band(self):
        """±7 / ±10 / ±15, keyed off the board and nothing else."""
        with open_session() as session:
            for symbol, exchange in (
                ("AAA", Exchange.HOSE),
                ("BBB", Exchange.HNX),
                ("CCC", Exchange.UPCOM),
            ):
                list_on(session, symbol, exchange)

            bands = {
                symbol: resolve_band_regime(session, symbol, date(2026, 8, 13))
                for symbol in ("AAA", "BBB", "CCC")
            }

        assert bands["AAA"].limit_ratio == Decimal("0.07")
        assert bands["BBB"].limit_ratio == Decimal("0.10")
        assert bands["CCC"].limit_ratio == Decimal("0.15")
        assert bands["AAA"].exchange is Exchange.HOSE

    def test_a_symbol_the_register_has_never_carried_has_no_band(self):
        """No board means no band, and never a default one.

        Defaulting to HOSE would be the most likely guess and the least
        detectable error: a symbol whose band is quietly narrowed to ±7 reports
        limit locks on ordinary HNX sessions.
        """
        with open_session() as session:
            regime = resolve_band_regime(session, "AAA", date(2026, 8, 13))

        assert regime.exchange is None
        assert regime.limit_ratio is None
        assert regime.exchange_as_of is ExchangeAsOf.UNKNOWN

    def test_a_dated_migration_beats_the_board_the_symbol_sits_on_today(self):
        """The bar decides, not the register's one current row.

        Both bars belong to a symbol whose register row says HOSE, because that
        is the only row the register will ever hold for it. Only the date
        separates the ±10 session from the ±7 one.
        """
        with open_session() as session:
            list_on(session, "ZZZ", Exchange.HOSE)

            before = resolve_band_regime(
                session, "ZZZ", date(2026, 2, 27), migrations=(MIGRATED,)
            )
            after = resolve_band_regime(
                session, "ZZZ", date(2026, 3, 2), migrations=(MIGRATED,)
            )

        assert (before.exchange, before.limit_ratio) == (
            Exchange.HNX,
            Decimal("0.10"),
        )
        assert (after.exchange, after.limit_ratio) == (
            Exchange.HOSE,
            Decimal("0.07"),
        )
        assert before.exchange_as_of is ExchangeAsOf.DATED_MIGRATION
        assert after.exchange_as_of is ExchangeAsOf.DATED_MIGRATION

    def test_the_first_session_on_the_new_board_is_the_boundary(self):
        """``first_session`` is the first bar under the new band, not the last
        under the old one."""
        with open_session() as session:
            list_on(session, "ZZZ", Exchange.HOSE)
            eve = resolve_band_regime(
                session, "ZZZ", date(2026, 3, 1), migrations=(MIGRATED,)
            )

        assert eve.exchange is Exchange.HNX

    def test_an_unmigrated_hose_bar_inside_the_programme_says_it_is_assuming(self):
        """The limitation is on the answer, not only in a comment.

        The register holds one current row per symbol by design, so a symbol
        that moved before this system first saw it leaves no trace at all. Every
        HOSE bar dated inside the migration programme is therefore an assumption
        about a board, and it is named as one — on the provenance field rather
        than as a degradation, because a warning attached to every HOSE bar in
        the store is a warning nobody reads.
        """
        with open_session() as session:
            list_on(session, "AAA", Exchange.HOSE)
            inside = resolve_band_regime(session, "AAA", MIGRATION_PROGRAMME_END)
            outside = resolve_band_regime(session, "AAA", date(2027, 1, 4))

        assert inside.exchange_as_of is ExchangeAsOf.CURRENT_LISTING_ASSUMED
        assert outside.exchange_as_of is ExchangeAsOf.CURRENT_LISTING
        assert inside.limit_ratio == Decimal("0.07")

    def test_a_board_the_programme_cannot_move_a_symbol_onto_is_not_assumed(self):
        """HNX→HOSE moves one way, so an HNX bar carries no such doubt."""
        with open_session() as session:
            list_on(session, "BBB", Exchange.HNX)
            regime = resolve_band_regime(session, "BBB", date(2026, 6, 1))

        assert regime.exchange_as_of is ExchangeAsOf.CURRENT_LISTING

    def test_the_anchor_each_board_measures_from_travels_with_the_band(self):
        """A band is a percentage of something, and the something differs."""
        with open_session() as session:
            list_on(session, "AAA", Exchange.HOSE)
            list_on(session, "CCC", Exchange.UPCOM)
            hose = resolve_band_regime(session, "AAA", date(2026, 8, 13))
            upcom = resolve_band_regime(session, "CCC", date(2026, 8, 13))

        assert hose.anchor_basis is BandAnchorBasis.PREVIOUS_CLOSE
        assert upcom.anchor_basis is BandAnchorBasis.PRIOR_DAY_VWAP


class TestTheTickGridTheLimitsLandOn:
    @pytest.mark.parametrize(
        ("price", "expected"),
        [(9_990, 10), (10_000, 50), (49_950, 50), (50_000, 100), (112_600, 100)],
    )
    def test_hose_quotes_in_three_steps(self, price: int, expected: int):
        assert tick_size(Exchange.HOSE, Decimal(price)) == Decimal(expected)

    @pytest.mark.parametrize("exchange", [Exchange.HNX, Exchange.UPCOM])
    def test_the_other_two_boards_quote_in_one_step(self, exchange: Exchange):
        assert tick_size(exchange, Decimal(9_990)) == Decimal(100)
        assert tick_size(exchange, Decimal(112_600)) == Decimal(100)

    def test_the_ceiling_rounds_down_and_the_floor_rounds_up(self):
        """Both toward the reference, which is what keeps them quotable.

        Pinned on MBB's real 2025-08-14 anchor of 25,800: ±7% is 27,606 and
        23,994, and neither is a price the exchange would accept.
        """
        limits = band_limits(Exchange.HOSE, Decimal(25_800))

        assert limits.ceiling == Decimal(27_600)
        assert limits.floor == Decimal(24_000)

    def test_a_limit_crossing_a_tick_boundary_lands_on_its_own_step(self):
        """49,000 × 1.07 is 52,430, and 52,400 is quotable while 52,350 is not.

        The step is chosen by the limit price rather than by the reference,
        because the number has to be a legal order price at the level it sits
        at. No stored session in this system's universe straddles the 50,000
        boundary, so this case is reasoned rather than observed.
        """
        limits = band_limits(Exchange.HOSE, Decimal(49_000))

        assert limits.ceiling == Decimal(52_400)

    def test_a_band_that_rounds_away_to_nothing_is_widened_to_one_step(self):
        """A penny name on UPCOM: 400 ± 15% is 460 and 340, both rounding to 400.

        A ceiling equal to the reference would say the session may not move,
        which no band does, so the exchange widens it to a single step. Live on
        UPCOM, where the step is 100 VND and companies trade in the hundreds;
        unreachable on HOSE, whose step under 10,000 is 10.
        """
        limits = band_limits(Exchange.UPCOM, Decimal(400))

        assert limits.ceiling == Decimal(500)
        assert limits.floor == Decimal(300)


class TestSessionsThatWereRealLockedAtTheirBand:
    """Rows lifted from this system's own store, with their real numbers.

    Each was collected from the Main Source and is `raw`, which is the only
    basis these questions can be asked on.
    """

    def test_mbb_on_2025_08_14_closed_locked_at_its_ceiling(self):
        """25,800 → 27,606 → 27,600, and the session never left it."""
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                open_price=27_600,
                high=27_600,
                low=27_600,
                close=27_600,
                volume=40_356_994,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.lock is LimitLock.CEILING
        assert reading.limits.ceiling == Decimal(27_600)
        assert reading.anchor == Decimal(25_800)
        assert reading.anchor_date == date(2025, 8, 13)
        assert reading.degraded_reason is None

    def test_mwg_on_2026_03_09_closed_locked_at_its_floor(self):
        """82,700 → 76,911 → 77,000, on the other rounding direction."""
        with open_session() as session:
            list_on(session, "MWG", Exchange.HOSE)
            write_session(session, "MWG", date(2026, 3, 6), close=82_700)
            write_session(
                session,
                "MWG",
                date(2026, 3, 9),
                open_price=77_000,
                high=77_000,
                low=77_000,
                close=77_000,
                volume=5_008_352,
            )

            reading = detect_limit_lock(session, "MWG", date(2026, 3, 9))

        assert reading.lock is LimitLock.FLOOR
        assert reading.limits.floor == Decimal(77_000)
        assert reading.degraded_reason is None

    def test_mwg_the_session_after_moved_inside_its_band(self):
        """A −7% day followed by a +5.2% one that touched neither limit."""
        with open_session() as session:
            list_on(session, "MWG", Exchange.HOSE)
            write_session(session, "MWG", date(2026, 3, 9), close=77_000)
            write_session(
                session,
                "MWG",
                date(2026, 3, 10),
                open_price=79_000,
                high=81_800,
                low=77_400,
                close=81_000,
            )

            reading = detect_limit_lock(session, "MWG", date(2026, 3, 10))

        assert reading.lock is LimitLock.NONE
        assert reading.degraded_reason is None

    def test_a_session_pinned_all_day_by_one_trade_is_not_a_lock(self):
        """H=L=O=C is the shape of a lock, not the fact of one.

        A thin session that matched once has the same flat bar as a locked one,
        and on UPCOM that is an ordinary day. What makes it a lock is where the
        flat bar sits.
        """
        with open_session() as session:
            list_on(session, "MWG", Exchange.HOSE)
            write_session(session, "MWG", date(2026, 3, 9), close=77_000)
            write_session(
                session,
                "MWG",
                date(2026, 3, 10),
                open_price=78_000,
                high=78_000,
                low=78_000,
                close=78_000,
                volume=300,
            )

            reading = detect_limit_lock(session, "MWG", date(2026, 3, 10))

        assert reading.lock is LimitLock.NONE

    def test_a_session_that_closed_at_its_ceiling_after_trading_below_is_not_locked(
        self,
    ):
        """Closing at the limit and never leaving it are different sessions.

        The first is buying pressure and belongs to a band-pressure reading; the
        second is an order book that could not clear, which is what deflates a
        range estimator and has to be excluded from one.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                open_price=26_000,
                high=27_600,
                low=25_900,
                close=27_600,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.lock is LimitLock.NONE


class TestWhatTheDetectorRefusesToDecide:
    def test_upcom_is_degraded_rather_than_anchored_to_the_previous_close(self):
        """The band is known; the number it is a percentage of is not.

        UPCOM's reference is the previous day's volume-weighted average of
        round-lot continuous trades. Nothing in the store is that average — the
        stored turnover covers put-through and odd lots too — so an answer here
        would be a confident wrong one.
        """
        with open_session() as session:
            list_on(session, "CCC", Exchange.UPCOM)
            write_session(session, "CCC", date(2026, 3, 6), close=10_000)
            write_session(
                session,
                "CCC",
                date(2026, 3, 9),
                open_price=11_500,
                high=11_500,
                low=11_500,
                close=11_500,
            )

            reading = detect_limit_lock(session, "CCC", date(2026, 3, 9))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.ANCHOR_NOT_STORED
        assert reading.limits is None
        # The regime still answers: which band applied is a separate question
        # from whether this session can be measured against it.
        assert reading.regime.limit_ratio == Decimal("0.15")
        assert reading.regime.exchange is Exchange.UPCOM

    def test_a_move_larger_than_the_band_says_the_anchor_is_wrong(self):
        """MBB's real 2025-08-13: −20.37% against ±7%, because it is an ex-date.

        The exchange adjusted its reference for the entitlement that morning and
        the previous close did not move with it. Reporting this as a session
        below its floor would be arithmetic run on a stale anchor; once the
        Corporate Action series exists this is the same measurement that
        separates an accounted ex-date from an unexplained gap.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 12), close=32_400)
            write_session(
                session,
                "MBB",
                date(2025, 8, 13),
                open_price=25_400,
                high=25_800,
                low=24_700,
                close=25_800,
                volume=79_742_535,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 13))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.PRICE_MOVE_EXCEEDS_BAND

    def test_a_session_the_store_does_not_hold_is_not_a_session_that_did_not_move(
        self,
    ):
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.MISSING_TARGET_SESSION

    def test_an_adjusted_session_still_on_the_grid_is_judged(self):
        """The label stopped deciding this; the prices decide it.

        Every row ``bar_daily`` holds is ``adjusted_at_source``, so refusing that
        label refused every session of every symbol — and silently, because the
        withheld verdict reads as *no lock* rather than as an error. What is asked
        instead is whether these prices are still the ones the board printed, and
        a symbol with no entitlement behind it carries published prices under the
        adjusted label. 25,800 anchors a ceiling of 27,600 after rounding to the
        grid, and the session traded its whole range there.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(
                session,
                "MBB",
                date(2019, 3, 1),
                close=25_800,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )
            write_session(
                session,
                "MBB",
                date(2019, 3, 4),
                high=27_600,
                low=27_600,
                close=27_600,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )

            reading = detect_limit_lock(session, "MBB", date(2019, 3, 4))

        assert reading.degraded_reason is None
        assert reading.lock is LimitLock.CEILING

    def test_a_price_off_the_quoting_grid_is_refused_by_name(self):
        """A rebased price cannot be compared with a limit that sits on a tick.

        The anchor is multiplied by a factor that takes it off the grid, which is
        what a provider's rescaling does. The verdict is withheld under its own
        code rather than becoming a false *no lock*, which is the whole difference
        between this and the label test it replaced.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(
                session,
                "MBB",
                date(2019, 3, 1),
                close=25_837,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )
            write_session(
                session,
                "MBB",
                date(2019, 3, 4),
                high=26_000,
                low=25_900,
                close=25_950,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )

            reading = detect_limit_lock(session, "MBB", date(2019, 3, 4))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.PRICE_OFF_TICK_GRID
        assert reading.limits is None

    def test_a_session_and_an_anchor_on_two_bases_is_still_a_seam(self):
        """One of each is a symbol's own seam falling between two days.

        Untouched by the narrowing above: the ratio between a raw close and an
        adjusted one is not a price move, whatever grid either sits on.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(
                session,
                "MBB",
                date(2019, 3, 1),
                close=25_800,
                basis=PriceBasis.RAW,
            )
            write_session(
                session,
                "MBB",
                date(2019, 3, 4),
                high=27_600,
                low=27_600,
                close=27_600,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )

            reading = detect_limit_lock(session, "MBB", date(2019, 3, 4))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.MIXED_PRICE_BASIS

    def test_an_adjusted_anchor_cannot_supply_a_reference_either(self):
        """The seam runs between two sessions, so a raw bar can have an adjusted
        one behind it — which is exactly what a symbol's crossover day looks
        like."""
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(
                session,
                "MBB",
                date(2021, 8, 4),
                close=25_800,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )
            write_session(
                session,
                "MBB",
                date(2021, 8, 5),
                high=27_600,
                low=27_600,
                close=27_600,
            )

            reading = detect_limit_lock(session, "MBB", date(2021, 8, 5))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.MIXED_PRICE_BASIS

    def test_a_symbol_that_did_not_trade_the_session_before_has_no_reference(self):
        """A suspension is also where the band widens, and by how much depends
        on how long it ran — which the store cannot tell from a collector gap."""
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            list_on(session, "MWG", Exchange.HOSE)
            # The market traded on the 13th; MBB did not.
            write_session(session, "MWG", date(2025, 8, 13), close=70_900)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                high=27_600,
                low=27_600,
                close=27_600,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.ANCHOR_MISSING

    def test_the_first_session_the_store_holds_has_nothing_behind_it(self):
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                high=27_600,
                low=27_600,
                close=27_600,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.degraded_reason is SignalIssue.ANCHOR_MISSING

    def test_a_session_without_a_usable_range_withholds_the_verdict(self):
        """A close at the ceiling is not a lock, so a bar with no high and low
        withholds the answer rather than falling back to the close.

        ``bar_daily`` types high and low NOT NULL, so the only way a stored
        session has no range is a value that is not a price. The reader maps a
        non-positive price to absent for exactly this reason: the session
        contract bounds every price above zero, so a zero left as a number would
        fail validation and take the whole window with it.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                high=0,
                low=0,
                close=27_600,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.SESSION_PRICES_INCOMPLETE

    def test_a_symbol_off_the_register_gets_no_band_to_be_judged_against(self):
        with open_session() as session:
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                high=27_600,
                low=27_600,
                close=27_600,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.EXCHANGE_UNKNOWN


class TestWhichStoredSessionIsRead:
    """One session is one row, and the band never comes off it.

    Both facts used to need defending against a store that held two copies of a
    session on two price bases, written by two sources. ``bar_daily`` is keyed
    ``(symbol, trading_day)`` and ingest upserts on it, so the first is now a
    property of the schema; the second is still a rule, because a stored ceiling
    would be today's band applied to an old session.
    """

    def test_a_session_restated_by_the_provider_replaces_the_row_it_had(self):
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                high=99_000,
                low=99_000,
                close=99_000,
            )
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                high=27_600,
                low=27_600,
                close=27_600,
            )

            held = (
                session.execute(
                    select(BarDaily).where(
                        BarDaily.symbol == "MBB",
                        BarDaily.trading_day == date(2025, 8, 14),
                    )
                )
                .scalars()
                .all()
            )
            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert len(held) == 1
        assert reading.lock is LimitLock.CEILING

    def test_the_band_is_taken_from_the_regime_and_never_from_the_stored_row(self):
        """The spine carries no reference, ceiling or floor at all — by design.

        A stored band would be whatever the provider's board rule was on the day
        it answered, applied to a session years earlier. The regime resolves the
        board as of the session instead, and the limits come out of that.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                open_price=27_600,
                high=27_600,
                low=27_600,
                close=27_600,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert not hasattr(BarDaily, "ceiling")
        assert reading.lock is LimitLock.CEILING
        assert reading.limits.ceiling == Decimal(27_600)
