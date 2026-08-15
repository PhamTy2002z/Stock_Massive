"""What the market-behaviour cluster says, and the three things it refuses to.

The cluster answers how tradeable a symbol is, how close it sits to its band,
and how stretched it is against its own recent history — and each of the three
has a shape the Vietnamese market makes wrong in a specific way, so most of this
file pins the refusal rather than the formula.

*A liquidity figure has to say what it is denominated in.* Money crosses an
ex-date and shares do not, so an ADTV in shares is degraded across a
share-count-changing action and an ADTV in dong is not. The two are registered
separately for exactly that reason.

*A band distance has to take its anchor from the exchange.* HOSE and HNX measure
from the previous close, which the store holds; UPCOM measures from the previous
day's round-lot VWAP, which it does not. So a UPCOM distance is withheld under a
stable reason rather than quietly anchored to the wrong number.

*A mean-reversion z has to know when it is measuring the window.* Where the
estimated half-life reaches the window length there is no reversion in the
sample at all, and a z over it describes the window's own mean rather than the
market — so the z is suppressed rather than printed with a caveat. Under three
sessions the gauge says plainly that T+2 settlement makes the round trip
impossible.

Nothing in the cluster fires. That is a decision rather than an omission and it
is pinned below: a "stretched" flag is one narration away from a reversion call,
and the research this cluster is built from rejects that claim for this market.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import (
    CohortMember,
    CohortVersion,
    CorporateAction,
    ListingRoster,
    ProviderSnapshot,
)
from src.stocks.providers import Exchange
from src.stocks.signals.bars import Bar, BarFrame, prepare_bars
from src.stocks.signals.fields import Claim, FieldKind, Sign, Unit
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.market_behavior import (
    BAND_PRESSURE_SESSIONS,
    LIQUIDITY_SESSIONS,
    MEAN_REVERSION_SESSIONS,
    SETTLEMENT_FLOOR_SESSIONS,
    adtv_money_reading,
    adtv_shares_reading,
    amihud_illiquidity_reading,
    band_pressure_reading,
    fit_ar1,
    half_life_of,
    mean_reversion_half_life_reading,
    mean_reversion_z_reading,
)
from src.stocks.signals.price_band import BandLimits, LimitLock, band_limits
from src.stocks.signals.registry import (
    ADTV_MONEY,
    ADTV_PERCENTILE,
    ADTV_SHARES,
    AMIHUD_ILLIQUIDITY,
    BAND_PRESSURE,
    MARKET_BEHAVIOR_FIELDS,
    MEAN_REVERSION_HALF_LIFE,
    MEAN_REVERSION_Z,
)
from src.stocks.signals.serving import serve_field
from src.stocks.universe import forget_cohort_cache

from .signal_windows import window_of
from .test_corporate_actions import CorporateActionEvent, save
from .test_price_band import list_on, write_session


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
        # The gateway ranks a window's traded money against the Universe, and the
        # Universe is the declared half plus the active Cohort Version. These
        # tests store real traded money, so unlike the risk cluster's they reach
        # that read and need somewhere for it to find no cohort.
        CohortVersion.__table__,
        CohortMember.__table__,
    ):
        table.create(engine)
    forget_cohort_cache()
    return Session(engine)


def weekdays(count: int, first: date = date(2024, 1, 1)) -> list[date]:
    days: list[date] = []
    cursor = first
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def bar(
    day: date,
    close: float,
    *,
    volume: int | None = 1_000_000,
    value: float | None = 1e9,
    lock: LimitLock = LimitLock.NONE,
    band: BandLimits | None = None,
    spread: float = 0.005,
) -> Bar:
    return Bar(
        session_date=day,
        open=close,
        high=close * (1.0 + spread),
        low=close * (1.0 - spread),
        close=close,
        volume=volume,
        total_value_vnd=value,
        adjustment_factor=Decimal(1),
        limit_lock=lock,
        band=band,
    )


def frame_of(closes: list[float], **kwargs: object) -> BarFrame:
    days = weekdays(len(closes))
    return BarFrame(
        symbol="AAA",
        bars=tuple(bar(day, close, **kwargs) for day, close in zip(days, closes)),  # type: ignore[arg-type]
    )


def banded_frame(closes: list[float], anchor: float = 20_000.0) -> BarFrame:
    """A HOSE window where every session carries the band it was judged against.

    The band of a session is measured from the close before it, which is what
    the gateway does, so the anchor of the first session is given rather than
    invented.
    """
    days = weekdays(len(closes))
    bars = []
    previous = anchor
    for day, close in zip(days, closes):
        limits = band_limits(Exchange.HOSE, Decimal(str(previous)))
        lock = (
            LimitLock.CEILING
            if Decimal(str(close)) == limits.ceiling
            else LimitLock.FLOOR
            if Decimal(str(close)) == limits.floor
            else LimitLock.NONE
        )
        bars.append(bar(day, close, band=limits, lock=lock, spread=0.0))
        previous = close
    return BarFrame(symbol="AAA", bars=tuple(bars))


def store_history(
    session: Session,
    sessions: int,
    *,
    symbol: str = "AAA",
    exchange: Exchange = Exchange.HOSE,
    value: float = 16e9,
) -> list[date]:
    """A flat stored window: every session inside its band and worth the same.

    Flat on purpose. These are the tests about serving rather than about
    arithmetic, and a window that moves would make the numbers below depend on a
    random seed instead of on the code under test.
    """
    list_on(session, symbol, exchange)
    days = weekdays(sessions)
    for day in days:
        write_session(
            session,
            symbol,
            day,
            close=20_000.0,
            high=20_100.0,
            low=19_900.0,
            open_price=20_000.0,
            volume=800_000,
            total_value_vnd=value,
        )
    return days


class TestTheLiquidityProfile:
    def test_the_money_adtv_is_the_mean_of_traded_value_and_says_so(self):
        """Traded money, named as money, because the alternative changes unit."""
        frame = frame_of([20_000.0] * (LIQUIDITY_SESSIONS + 1), value=2e9)

        reading = adtv_money_reading(window_of(frame))

        assert reading.value == pytest.approx(2e9)
        assert reading.extras["adtv_basis"] == "money"
        assert reading.extras["sessions"] == LIQUIDITY_SESSIONS

    def test_the_money_adtv_reads_only_the_newest_twenty_sessions(self):
        """ADTV means twenty sessions in this market's own vocabulary."""
        closes = [20_000.0] * (LIQUIDITY_SESSIONS + 1)
        days = weekdays(len(closes))
        bars = [
            bar(day, close, value=1e9 if index == 0 else 2e9)
            for index, (day, close) in enumerate(zip(days, closes))
        ]

        reading = adtv_money_reading(window_of(BarFrame(symbol="AAA", bars=tuple(bars))))

        # The oldest session is the one dropped, so the odd value never lands.
        assert reading.value == pytest.approx(2e9)

    def test_the_share_adtv_is_a_separate_field_denominated_in_shares(self):
        """The naming split exists so the two can never be swapped by accident."""
        frame = frame_of([20_000.0] * (LIQUIDITY_SESSIONS + 1), volume=500_000)

        reading = adtv_shares_reading(window_of(frame))

        assert reading.value == pytest.approx(500_000)
        assert reading.extras["adtv_basis"] == "shares"
        assert ADTV_SHARES.unit is Unit.SHARES
        assert ADTV_MONEY.unit is Unit.VND

    def test_a_session_with_no_traded_money_refuses_rather_than_averages_the_rest(self):
        """An average over a different stretch of market is not a shorter average."""
        closes = [20_000.0] * (LIQUIDITY_SESSIONS + 1)
        days = weekdays(len(closes))
        bars = [
            bar(day, close, value=None if index == 5 else 2e9)
            for index, (day, close) in enumerate(zip(days, closes))
        ]

        reading = adtv_money_reading(window_of(BarFrame(symbol="AAA", bars=tuple(bars))))

        assert reading.value is None
        assert reading.refusal is SignalIssue.INSUFFICIENT_HISTORY

    def test_amihud_is_percent_moved_per_billion_dong_traded(self):
        """Amihud (2002): |R| over traded money, in the units the shortlist names.

        Every session here moves exactly +1% on exactly two billion dong, so the
        answer is 0.5 percent per billion and can be checked by hand.
        """
        closes = [20_000.0 * (1.01**index) for index in range(LIQUIDITY_SESSIONS + 1)]
        frame = frame_of(closes, value=2e9)

        reading = amihud_illiquidity_reading(window_of(frame))

        assert reading.value == pytest.approx(0.5, rel=1e-6)
        assert AMIHUD_ILLIQUIDITY.unit is Unit.PERCENT_PER_BILLION_VND
        assert AMIHUD_ILLIQUIDITY.sign is Sign.NON_NEGATIVE

    def test_a_zero_volume_session_is_counted_and_left_out_of_the_average(self):
        """Dividing by no trading is not illiquidity, it is no observation.

        The count travels because a symbol that did not trade on a third of the
        window is the fact a reader most needs — it is not a detail behind the
        average.
        """
        closes = [20_000.0 * (1.01**index) for index in range(LIQUIDITY_SESSIONS + 1)]
        days = weekdays(len(closes))
        bars = [
            bar(
                day,
                close,
                value=0.0 if index in (3, 4) else 2e9,
                volume=0 if index in (3, 4) else 1_000_000,
            )
            for index, (day, close) in enumerate(zip(days, closes))
        ]

        reading = amihud_illiquidity_reading(
            window_of(BarFrame(symbol="AAA", bars=tuple(bars)))
        )

        assert reading.extras["zero_volume_days"] == 2
        assert reading.value == pytest.approx(0.5, rel=1e-6)

    def test_the_estimators_ship_their_uncertainty(self):
        """ADR-0010 admits no estimator without one."""
        frame = frame_of(
            [20_000.0 * (1.0 + 0.01 * (index % 3)) for index in range(21)],
            value=2e9,
        )

        for reading in (
            adtv_money_reading(window_of(frame)),
            adtv_shares_reading(window_of(frame)),
            amihud_illiquidity_reading(window_of(frame)),
        ):
            assert reading.extras["standard_error"] is not None


class TestBandPressure:
    def test_it_counts_limit_days_and_closes_at_the_band(self):
        """Two different facts, counted separately.

        A session locked at its ceiling never traded away from it; a session
        that closed there after trading below is buying pressure. Folding them
        together would make an order book that could not clear look the same as
        one that cleared upward all day.
        """
        anchor = 20_000.0
        ceiling = float(band_limits(Exchange.HOSE, Decimal(str(anchor))).ceiling)
        closes = [anchor] * (BAND_PRESSURE_SESSIONS - 2) + [ceiling, anchor]
        frame = banded_frame(closes, anchor=anchor)

        reading = band_pressure_reading(window_of(frame))

        assert reading.value == 1
        assert reading.extras["closes_at_ceiling"] == 1
        assert reading.extras["closes_at_floor"] == 0

    def test_the_distance_is_positive_above_the_close_and_negative_below_it(self):
        """One sign convention for both limits: positive means the limit is above."""
        frame = banded_frame([20_000.0] * BAND_PRESSURE_SESSIONS, anchor=20_000.0)

        reading = band_pressure_reading(window_of(frame))

        assert reading.extras["distance_to_ceiling_pct"] == pytest.approx(7.0)
        assert reading.extras["distance_to_floor_pct"] == pytest.approx(-7.0)

    def test_a_session_whose_band_nobody_could_decide_withholds_the_distance(self):
        """A UPCOM band anchors to a VWAP the store does not hold.

        The gateway leaves such a session with no band at all, and the field
        withholds the distance rather than measuring it off the previous close —
        which would answer with the right shape and the wrong number.
        """
        days = weekdays(BAND_PRESSURE_SESSIONS)
        bars = tuple(
            bar(day, 20_000.0, band=None, lock=LimitLock.INDETERMINATE)
            for day in days
        )

        reading = band_pressure_reading(
            window_of(
                BarFrame(symbol="AAA", bars=bars),
            )
        )

        assert reading.value is None
        assert reading.refusal is SignalIssue.ANCHOR_NOT_STORED

    def test_a_partly_undecided_window_is_degraded_rather_than_refused(self):
        """The sessions that were judged are real; the count rests on fewer of them."""
        anchor = 20_000.0
        frame = banded_frame([anchor] * BAND_PRESSURE_SESSIONS, anchor=anchor)
        bars = (bar(frame.bars[0].session_date, anchor, band=None),) + frame.bars[1:]

        reading = band_pressure_reading(window_of(BarFrame(symbol="AAA", bars=bars)))

        assert reading.value == 0
        assert reading.degraded_reason is SignalIssue.ANCHOR_NOT_STORED
        assert reading.extras["undecided_days"] == 1

    def test_the_base_rate_comes_from_the_symbols_own_window(self):
        """Never a full-sample norm: the #31 post-mortem is about exactly that."""
        anchor = 20_000.0
        ceiling = float(band_limits(Exchange.HOSE, Decimal(str(anchor))).ceiling)
        closes = [anchor] * (BAND_PRESSURE_SESSIONS - 1) + [ceiling]
        frame = banded_frame(closes, anchor=anchor)

        reading = band_pressure_reading(window_of(frame))

        assert reading.extras["decided_days"] == BAND_PRESSURE_SESSIONS
        assert reading.extras["base_rate_pct"] == pytest.approx(
            100.0 / BAND_PRESSURE_SESSIONS
        )
        assert reading.extras["standard_error"] is not None


class TestTheMeanReversionGauge:
    def test_the_ar1_fit_recovers_a_known_decay(self):
        """φ̂ from Δx on x with an intercept, which is the standard estimate."""
        series = [0.05 * (0.5**index) for index in range(40)]

        fit = fit_ar1(series)

        assert fit is not None
        assert fit.phi == pytest.approx(0.5, rel=1e-6)

    def test_the_half_life_is_the_exponential_decay_arithmetic(self):
        """−ln 2 / ln φ̂, and nothing else pretending to be a published result."""
        assert half_life_of(0.5) == pytest.approx(1.0)
        assert half_life_of(0.5 ** (1 / 5)) == pytest.approx(5.0)
        assert half_life_of(1.0) is None

    def test_the_z_says_which_side_of_its_own_trailing_mean_the_close_is_on(self):
        """Positive is above the symbol's own recent mean, and nothing more.

        The baseline oscillates so that it has a dispersion to measure the last
        close in; a flat one has none, which is a refusal of its own rather than
        a z of zero.
        """
        baseline = [
            20_000.0 * math.exp(0.02 * math.sin(index))
            for index in range(MEAN_REVERSION_SESSIONS)
        ]
        above = mean_reversion_z_reading(window_of(frame_of([*baseline, 22_000.0])))
        below = mean_reversion_z_reading(window_of(frame_of([*baseline, 18_000.0])))

        assert above.value is not None and above.value > 0
        assert below.value is not None and below.value < 0
        assert MEAN_REVERSION_Z.sign is Sign.SIGNED

    def test_a_baseline_that_never_moved_has_no_z_to_take(self):
        """Not a z of zero: nothing in the window says how big a move would be."""
        frame = frame_of([20_000.0] * (MEAN_REVERSION_SESSIONS + 1))

        reading = mean_reversion_z_reading(window_of(frame))

        assert reading.value is None
        assert reading.refusal is SignalIssue.BASELINE_DISPERSION_ZERO

    def test_the_z_is_suppressed_when_the_half_life_reaches_the_window(self):
        """Past that the statistic measures the window rather than the market.

        A series with a linear trend has no reversion in it at all: the fitted
        φ̂ is one, the half-life is unbounded, and a z against the window's own
        mean would be describing where the window happened to start.
        """
        closes = [20_000.0 * (1.0 + 0.001 * index) for index in range(61)]
        frame = frame_of(closes)

        reading = mean_reversion_z_reading(window_of(frame))

        assert reading.value is None
        assert reading.refusal is SignalIssue.HALF_LIFE_EXCEEDS_WINDOW

    def test_a_half_life_under_the_settlement_floor_is_stated_as_such(self):
        """T+2 makes the round trip impossible, and the tool says so itself."""
        base = math.log(20_000.0)
        closes = [
            math.exp(base + 0.05 * (0.1**index))
            for index in range(MEAN_REVERSION_SESSIONS + 1)
        ]
        frame = frame_of(closes)

        reading = mean_reversion_half_life_reading(window_of(frame))

        assert reading.value is not None
        assert reading.value < SETTLEMENT_FLOOR_SESSIONS
        assert reading.extras["half_life_under_settlement_floor"] is True
        assert reading.extras["settlement_floor_sessions"] == SETTLEMENT_FLOOR_SESSIONS

    def test_the_half_life_ships_a_bootstrap_interval(self):
        """Block-resampled, because a half-life estimated once is a point on noise."""
        closes = [
            20_000.0 * math.exp(0.02 * math.sin(index / 3.0))
            for index in range(MEAN_REVERSION_SESSIONS + 1)
        ]

        reading = mean_reversion_half_life_reading(window_of(frame_of(closes)))

        interval = reading.extras["confidence_interval"]
        assert interval is not None
        assert interval[0] <= interval[1]

    def test_the_same_window_gives_the_same_interval_twice(self):
        """A field whose uncertainty moves per call is one nobody can cite."""
        closes = [
            20_000.0 * math.exp(0.02 * math.sin(index / 3.0))
            for index in range(MEAN_REVERSION_SESSIONS + 1)
        ]
        frame = frame_of(closes)

        first = mean_reversion_half_life_reading(window_of(frame))
        second = mean_reversion_half_life_reading(window_of(frame))

        assert first.extras["confidence_interval"] == second.extras["confidence_interval"]


class TestTheClusterContract:
    def test_the_volatility_regime_z_is_the_only_field_here_that_fires(self):
        """Which is a decision on the record rather than a gap in the work.

        A "thin" or "stretched against its own history" flag is one narration
        away from a claim about what the price does next, and the research this
        cluster is built from could verify no such claim for this market. So the
        four questions this cluster adds ship descriptive numbers and no
        thresholds — and a later author who wants one has to derive it from the
        null harness, which is what this test makes them notice.
        """
        firing = [field for field in MARKET_BEHAVIOR_FIELDS if field.fires]

        assert [field.name for field in firing] == [
            "volatility_regime.gk_variance_robust_z"
        ]
        for field in MARKET_BEHAVIOR_FIELDS:
            if field.fires:
                continue
            assert field.threshold is None
            assert field.null_fpr is None
            assert field.kind is not FieldKind.SIGNAL

    def test_every_field_is_descriptive_and_points_nowhere(self):
        for field in MARKET_BEHAVIOR_FIELDS:
            assert field.claim is Claim.DESCRIPTIVE

    def test_every_field_declares_the_history_it_needs_as_window_plus_skip(self):
        """None of these skips, so each is its window and the session before it."""
        assert ADTV_MONEY.min_sessions == LIQUIDITY_SESSIONS + 1
        assert AMIHUD_ILLIQUIDITY.min_sessions == LIQUIDITY_SESSIONS + 1
        assert BAND_PRESSURE.min_sessions == BAND_PRESSURE_SESSIONS
        assert MEAN_REVERSION_Z.min_sessions == MEAN_REVERSION_SESSIONS + 1


class TestEveryFieldReachesBarsThroughTheGatewayAlone:
    def test_a_window_the_gateway_refuses_is_a_field_that_refuses(self):
        with open_session() as session:
            days = store_history(session, 10)

            value = serve_field(session, "AAA", ADTV_MONEY, end=days[-1])

        assert value.value is None
        assert value.refusal is SignalIssue.INSUFFICIENT_HISTORY

    def test_a_served_window_carries_its_health_beside_the_number(self):
        with open_session() as session:
            days = store_history(session, 40)

            value = serve_field(session, "AAA", ADTV_MONEY, end=days[-1])

        assert value.value == pytest.approx(16e9)
        assert value.health.sessions_used == ADTV_MONEY.min_sessions
        assert value.health.refusal is None

    def test_the_percentile_carries_the_sample_it_was_ranked_in(self):
        """A percentile with no ``n`` and no cutoff date is refused at construction."""
        with open_session() as session:
            days = store_history(session, 40)
            for index in range(32):
                store_history(session, 40, symbol=f"P{index:02d}", value=1e9 * index)
            peers = [f"P{index:02d}" for index in range(32)]

            value = serve_field(
                session,
                "AAA",
                ADTV_PERCENTILE,
                end=days[-1],
                peers=[*peers, "AAA"],
            )

        assert value.value is not None
        assert value.extras["n"] == 32
        assert value.extras["as_of"] == days[-1].isoformat()

    def test_a_upcom_window_refuses_the_distance_under_a_stable_reason(self):
        """The whole path, not a hand-made frame: the board decides the anchor.

        UPCOM measures its band from the previous day's round-lot continuous
        VWAP, which the store does not hold and cannot reconstruct — the stored
        turnover covers put-through and odd-lot trades too. So the gateway
        leaves every one of these sessions unjudged and the field refuses under
        the reason it recorded, rather than anchoring to the previous close and
        answering with the right shape and the wrong number.
        """
        with open_session() as session:
            days = store_history(session, 70, exchange=Exchange.UPCOM)

            upcom = serve_field(session, "AAA", BAND_PRESSURE, end=days[-1])

        assert upcom.value is None
        assert upcom.refusal is SignalIssue.ANCHOR_NOT_STORED

    def test_a_hose_window_measures_the_distance_from_the_previous_close(self):
        """The same window on the board whose anchor the store does hold."""
        with open_session() as session:
            days = store_history(session, 70)

            hose = serve_field(session, "AAA", BAND_PRESSURE, end=days[-1])

        assert hose.value == 0
        assert hose.extras["distance_to_ceiling_pct"] == pytest.approx(7.0)
        assert hose.extras["anchor_basis"] == "previous_close"

    def test_a_share_denominated_field_degrades_across_a_share_count_change(self):
        """The unit is what says so, so a field cannot forget to.

        Money crosses an ex-date unchanged and shares do not, which is why the
        two ADTVs are separate fields rather than one figure with a note.
        """
        with open_session() as session:
            days = store_history(session, 40)
            save(
                session,
                CorporateActionEvent(
                    symbol="AAA",
                    event_code="ISS",
                    title="Share Issue - Stock dividend ratio 10.0%",
                    ex_date=days[-5],
                    record_date=days[-4],
                    public_date=days[-10],
                    exercise_ratio=0.10,
                    value_per_share=None,
                ),
            )

            shares = serve_field(session, "AAA", ADTV_SHARES, end=days[-1])
            money = serve_field(session, "AAA", ADTV_MONEY, end=days[-1])

        assert shares.degraded_reason is SignalIssue.VOLUME_BASIS_BREAK
        assert money.degraded_reason is None
