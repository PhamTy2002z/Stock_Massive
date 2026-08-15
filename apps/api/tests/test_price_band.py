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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import ListingRoster, ProviderSnapshot
from src.stocks.providers import Capability, Exchange, PriceBasis, ProviderSource
from src.stocks.providers.contracts import (
    MARKET_SCHEMA_VERSION,
    MarketSnapshot,
    SnapshotMetadata,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.issues import SignalIssue
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


def open_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (ProviderSnapshot.__table__, ListingRoster.__table__):
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
    total_value_vnd: float | None = None,
    market_cap_vnd: float | None = None,
    source: ProviderSource = ProviderSource.FIINQUANT,
    basis: PriceBasis | None = None,
) -> None:
    """Store one session, defaulting the intraday range to the close.

    ``high``/``low`` default to the close rather than to nothing, because an
    anchor session only ever needs its close and spelling out a range on every
    one of them would bury the ranges that are the point of the test.

    ``basis`` defaults to the one that source has always written, which is the
    only pairing the store has ever held. It is overridable so that a test can
    prove the code reads the basis off the row rather than deriving it from the
    source — the separation the field exists for.
    """
    snapshot = MarketSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=source,
            effective_at=_stamp(day),
            observed_at=NOW,
            schema_version=MARKET_SCHEMA_VERSION,
        ),
        price_basis=basis if basis is not None else basis_of(source),
        total_value_vnd=total_value_vnd,
        open_price=open_price if open_price is not None else close,
        high_price=high if high is not None else close,
        low_price=low if low is not None else close,
        last_price=close,
        volume=volume,
        market_cap_vnd=market_cap_vnd,
    )
    session.add(
        ProviderSnapshot(
            capability=Capability.MARKET.value,
            symbol=symbol,
            source=source.value,
            effective_at=_stamp(day),
            observed_at=NOW,
            schema_version=MARKET_SCHEMA_VERSION,
            payload=snapshot.model_dump(mode="json"),
        )
    )
    session.flush()


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

    def test_an_adjusted_session_cannot_be_judged_against_a_band(self):
        """Rescaled closes sit off the tick grid the band is defined on.

        The Cover Source's era is `adjusted_at_source` for every row it wrote,
        so this is most of the history before each symbol's own seam, not an
        edge case.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(
                session,
                "MBB",
                date(2019, 3, 1),
                close=25_800,
                source=ProviderSource.VNSTOCK,
            )
            write_session(
                session,
                "MBB",
                date(2019, 3, 4),
                high=27_600,
                low=27_600,
                close=27_600,
                source=ProviderSource.VNSTOCK,
            )

            reading = detect_limit_lock(session, "MBB", date(2019, 3, 4))

        assert reading.lock is LimitLock.INDETERMINATE
        assert reading.degraded_reason is SignalIssue.UNADJUSTABLE_PRICE_BASIS

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
                source=ProviderSource.VNSTOCK,
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

    def test_a_session_without_a_range_cannot_be_shown_to_have_been_locked(self):
        """A close at the ceiling is not a lock, so a bar with no high and low
        withholds the answer rather than falling back to the close."""
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            snapshot = MarketSnapshot(
                symbol="MBB",
                metadata=SnapshotMetadata(
                    source=ProviderSource.FIINQUANT,
                    effective_at=_stamp(date(2025, 8, 14)),
                    observed_at=NOW,
                    schema_version=MARKET_SCHEMA_VERSION,
                ),
                price_basis=basis_of(ProviderSource.FIINQUANT),
                last_price=27_600,
                volume=40_356_994,
            )
            session.add(
                ProviderSnapshot(
                    capability=Capability.MARKET.value,
                    symbol="MBB",
                    source=ProviderSource.FIINQUANT.value,
                    effective_at=_stamp(date(2025, 8, 14)),
                    observed_at=NOW,
                    schema_version=MARKET_SCHEMA_VERSION,
                    payload=snapshot.model_dump(mode="json"),
                )
            )
            session.flush()

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
    def test_the_main_source_wins_where_both_sources_hold_one_session(self):
        """The Cover Source's copy of a session is a quote history bar, and it
        is on the other price basis — so which of the two is read decides
        whether the question can be asked at all."""
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                high=27_600,
                low=27_600,
                close=27_600,
                source=ProviderSource.VNSTOCK,
            )
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                high=27_600,
                low=27_600,
                close=27_600,
            )

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.lock is LimitLock.CEILING

    def test_the_band_is_taken_from_the_regime_and_not_from_the_stored_pair(self):
        """``ceiling_price`` and ``floor_price`` are absent on every history bar
        by design, and a stored one would be today's band on an old session.

        This row carries a deliberately wrong stored pair; the detector's answer
        has to come out the same as the row without one.
        """
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            snapshot = MarketSnapshot(
                symbol="MBB",
                metadata=SnapshotMetadata(
                    source=ProviderSource.FIINQUANT,
                    effective_at=_stamp(date(2025, 8, 14)),
                    observed_at=NOW,
                    schema_version=MARKET_SCHEMA_VERSION,
                ),
                price_basis=basis_of(ProviderSource.FIINQUANT),
                open_price=27_600,
                high_price=27_600,
                low_price=27_600,
                last_price=27_600,
                reference_price=99_000,
                ceiling_price=105_900,
                floor_price=92_100,
                volume=40_356_994,
            )
            session.add(
                ProviderSnapshot(
                    capability=Capability.MARKET.value,
                    symbol="MBB",
                    source=ProviderSource.FIINQUANT.value,
                    effective_at=_stamp(date(2025, 8, 14)),
                    observed_at=NOW,
                    schema_version=MARKET_SCHEMA_VERSION,
                    payload=snapshot.model_dump(mode="json"),
                )
            )
            session.flush()

            reading = detect_limit_lock(session, "MBB", date(2025, 8, 14))

        assert reading.lock is LimitLock.CEILING
        assert reading.limits.ceiling == Decimal(27_600)
