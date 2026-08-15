"""What the risk cluster says, and the well-known wrong answers it does not give.

Each of these four numbers has a textbook form that is wrong in a way nobody
notices, so most of this file pins the correction rather than the formula:

*Garman-Klass with ln(Cᵢ/Cᵢ₋₁) in place of ln(C/O)* is a literature error that
"sometimes produces negative estimates" (Molnár 2012). With the right term the
estimator is non-negative for every bar there is.

*√252 on a Sharpe* is a special case people apply as a general rule. Lo (2002)
shows the factor is q/√(q + 2Σ(q−k)ρ_k) and reduces to √q only under zero
autocorrelation; ignoring that overstated hedge-fund ratios by as much as 65%.

*Downside deviation divided by the count below the benchmark* understates
downside risk exactly when most returns are positive, which is most of the time.
The divisor is the total.

*A drawdown without its benchmark* is drama. E[MDD] ≈ 1.2533σ√T is what turns
"−18% over a year" into "about what a coin would have done".

The estimators are exercised against series built to have a known answer, so a
test that passes is a test that pinned the arithmetic rather than the shape.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import Exchange
from src.stocks.signals.bars import Bar, BarFrame
from src.stocks.signals.fields import Claim, FieldKind, Sign, Unit
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.nulls import (
    MATCHED_DAILY_VOLATILITIES,
    frames_from,
    gbm_shapes,
)
from src.stocks.signals.price_band import LimitLock
from src.stocks.signals.registry import (
    CURRENT_DRAWDOWN,
    DAYS_UNDERWATER,
    DRAWDOWN_VERSUS_BENCHMARK,
    MAX_DRAWDOWN,
    NULL_DERIVATION_SEED,
    PRICE_ZONE,
    REALIZED_VOLATILITY,
    SHARPE,
    SORTINO,
)
from src.stocks.signals.risk import (
    CURRENT_DRAWDOWN_NULL_SCATTER,
    DAYS_UNDERWATER_NULL_SCATTER,
    EXPECTED_MDD_CONSTANT,
    MAX_DRAWDOWN_NULL_SCATTER,
    MIN_DOWNSIDE_OBSERVATIONS,
    PRICE_ZONE_MIN_SESSIONS,
    TRADING_SESSIONS_PER_YEAR,
    annualization_of,
    close_to_close_variance,
    current_drawdown_reading,
    days_underwater_reading,
    drawdown_of,
    drawdown_ratio,
    drawdown_versus_benchmark_reading,
    expected_max_drawdown,
    garman_klass_mean_variance,
    max_drawdown_reading,
    parkinson_variance,
    price_zone_reading,
    realized_volatility_reading,
    rogers_satchell_variance,
    serve,
    sharpe_reading,
    sortino_reading,
    yang_zhang_variance,
)

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
    ):
        table.create(engine)
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
    open_price: float,
    high: float,
    low: float,
    close: float,
    *,
    lock: LimitLock = LimitLock.NONE,
) -> Bar:
    return Bar(
        session_date=day,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1_000_000,
        total_value_vnd=None,
        adjustment_factor=Decimal(1),
        limit_lock=lock,
    )


def frame_of(closes: list[float], *, spread: float = 0.01) -> BarFrame:
    """A window whose closes are exactly as given, with a fixed relative range.

    The open is the previous close, so the overnight term of Yang-Zhang is zero
    and every number below is reproducible by hand from the closes alone.
    """
    days = weekdays(len(closes))
    bars = []
    previous = closes[0]
    for day, close in zip(days, closes):
        high = max(previous, close) * (1.0 + spread)
        low = min(previous, close) * (1.0 - spread)
        bars.append(bar(day, previous, high, low, close))
        previous = close
    return BarFrame(symbol="AAA", bars=tuple(bars))


def store_history(
    session: Session,
    sessions: int,
    *,
    symbol: str = "AAA",
    seed: int = 5,
    drift: float = 0.0,
) -> list[date]:
    """A stored window long enough for the cluster's longest field.

    Moves stay well inside the ±7% band, so the gateway serves the window rather
    than refusing a gap it cannot explain.
    """
    rng = random.Random(seed)
    list_on(session, symbol, Exchange.HOSE)
    days = weekdays(sessions)
    close = 20_000.0
    for day in days:
        step = drift + rng.uniform(-0.02, 0.02)
        open_price = close * (1.0 + rng.uniform(-0.004, 0.004))
        next_close = close * (1.0 + step)
        spread = rng.uniform(0.003, 0.02)
        write_session(
            session,
            symbol,
            day,
            open_price=round(open_price, 1),
            high=round(max(open_price, next_close) * (1.0 + spread), 1),
            low=round(min(open_price, next_close) * (1.0 - spread), 1),
            close=round(next_close, 1),
        )
        close = round(next_close, 1)
    return days


class TestRealizedVolatility:
    def test_yang_zhang_is_the_headline_and_the_components_come_with_it(self):
        """They disagree, and the disagreement is what a reader is owed.

        Parkinson and Garman-Klass ignore the opening jump; Rogers-Satchell is
        the only one unbiased under drift. Printing one number would hide which
        of those assumptions the answer is resting on.
        """
        reading = realized_volatility_reading(frame_of([20_000.0 * (1.01**i) for i in range(60)]))

        assert reading.value is not None
        assert reading.value >= 0
        components = reading.extras["components_annualized_pct"]
        assert set(components) == {
            "parkinson",
            "garman_klass",
            "rogers_satchell",
            "close_to_close",
        }
        assert all(value is not None for value in components.values())

    def test_it_is_annualized_by_the_square_root_of_252_on_the_variance(self):
        """Legitimate here, and not the Sharpe annualization argued with below:
        variance over independent periods adds, and the root falls out of it."""
        frame = frame_of([20_000.0 * (1.005 ** (i % 7)) for i in range(60)])
        bars = list(frame.bars)
        variance = yang_zhang_variance(bars)
        reading = realized_volatility_reading(frame)

        assert variance is not None
        assert reading.value == pytest.approx(
            100.0 * math.sqrt(variance * TRADING_SESSIONS_PER_YEAR)
        )

    def test_it_is_never_negative(self):
        frame = frame_of([20_000.0 + 500.0 * math.sin(i) for i in range(60)])
        reading = realized_volatility_reading(frame)

        assert reading.value is not None
        assert reading.value >= 0

    def test_the_limit_locked_and_zero_range_counts_travel_with_it(self):
        """Both bias a range estimate downward, and neither is correctable from
        stored data — so both are counted rather than adjusted for."""
        days = weekdays(30)
        bars = []
        price = 20_000.0
        for index, day in enumerate(days):
            if index in (10, 11):
                bars.append(bar(day, price, price, price, price, lock=LimitLock.CEILING))
            else:
                bars.append(bar(day, price, price * 1.01, price * 0.99, price * 1.002))
                price *= 1.002
        reading = realized_volatility_reading(BarFrame(symbol="AAA", bars=tuple(bars)))

        assert reading.extras["limit_lock_days"] == 2
        assert reading.extras["zero_range_days"] == 2

    def test_the_estimator_ships_its_uncertainty(self):
        reading = realized_volatility_reading(frame_of([20_000.0 * (1.003**i) for i in range(60)]))

        assert reading.extras["standard_error"] > 0

    def test_the_component_formulae_are_the_published_ones(self):
        """Pinned by hand on one bar, so a transcription error has somewhere to fail."""
        one = [bar(date(2024, 1, 2), 20_000.0, 20_600.0, 19_800.0, 20_400.0)]
        hl = math.log(20_600.0 / 19_800.0)
        co = math.log(20_400.0 / 20_000.0)

        assert parkinson_variance(one) == pytest.approx(hl * hl / (4.0 * math.log(2.0)))
        assert garman_klass_mean_variance(one) == pytest.approx(
            0.5 * hl * hl - (2.0 * math.log(2.0) - 1.0) * co * co
        )
        assert rogers_satchell_variance(one) == pytest.approx(
            math.log(20_600.0 / 20_400.0) * math.log(20_600.0 / 20_000.0)
            + math.log(19_800.0 / 20_400.0) * math.log(19_800.0 / 20_000.0)
        )

    def test_garman_klass_is_non_negative_wherever_close_to_close_would_not_be(self):
        """The literature error Molnár flags, and the reason the C/O term is used.

        The C/C variant can go negative on a bar whose close-to-close move is
        large against its own range — precisely a gap day, which this market has
        rather a lot of.
        """
        gap = [bar(date(2024, 1, 2), 20_000.0, 20_050.0, 19_950.0, 20_040.0)]
        naive = 0.5 * math.log(20_050.0 / 19_950.0) ** 2 - (
            2.0 * math.log(2.0) - 1.0
        ) * math.log(20_040.0 / 18_000.0) ** 2

        assert naive < 0
        assert garman_klass_mean_variance(gap) >= 0


class TestDrawdownStatistics:
    def test_the_sign_convention_is_negative_and_is_pinned_here(self):
        """A drawdown is ≤ 0, always, so "worse" is unambiguously "more
        negative" and two of them can be compared without asking which way round
        the field is written."""
        fall = drawdown_of(frame_of([100.0, 120.0, 90.0, 110.0]).bars)

        assert fall is not None
        assert fall.max_drawdown_pct == pytest.approx(100.0 * (90.0 / 120.0 - 1.0))
        assert fall.max_drawdown_pct < 0
        assert fall.current_drawdown_pct == pytest.approx(
            100.0 * (110.0 / 120.0 - 1.0)
        )
        assert fall.current_drawdown_pct < 0

    def test_a_series_at_a_new_high_is_not_underwater(self):
        fall = drawdown_of(frame_of([100.0, 90.0, 110.0]).bars)

        assert fall is not None
        assert fall.current_drawdown_pct == pytest.approx(0.0)
        assert fall.days_underwater == 0

    def test_days_underwater_counts_from_the_last_high(self):
        fall = drawdown_of(frame_of([100.0, 130.0, 120.0, 110.0, 115.0]).bars)

        assert fall is not None
        assert fall.days_underwater == 3

    def test_the_peak_and_the_trough_of_the_worst_fall_are_named(self):
        frame = frame_of([100.0, 130.0, 80.0, 120.0, 118.0])
        fall = drawdown_of(frame.bars)

        assert fall is not None
        assert fall.peak_session == frame.bars[1].session_date
        assert fall.trough_session == frame.bars[2].session_date

    def test_the_brownian_benchmark_is_the_one_magdon_ismail_published(self):
        """E[MDD] = σ√(πT/2) ≈ 1.2533·σ√T for driftless Brownian motion."""
        assert EXPECTED_MDD_CONSTANT == pytest.approx(1.2533, abs=1e-4)
        assert expected_max_drawdown(0.02, 250) == pytest.approx(
            1.2533 * 0.02 * math.sqrt(250), abs=1e-4
        )

    def test_the_ratio_reads_the_fall_against_that_benchmark(self):
        frame = frame_of([20_000.0 * (0.995**i) for i in range(120)])
        ratio = drawdown_ratio(frame)
        fall = drawdown_of(frame.bars)
        variance = yang_zhang_variance(list(frame.bars))

        assert ratio is not None and fall is not None and variance is not None
        assert ratio == pytest.approx(
            fall.max_drawdown_log
            / expected_max_drawdown(math.sqrt(variance), len(frame.bars) - 1)
        )

    def test_each_drawdown_number_ships_the_spread_measured_under_the_null(self):
        """The estimator's bar, met with a real sampling spread rather than with
        the benchmark wearing a standard error's name."""
        frame = frame_of([20_000.0 * (1.0 + 0.01 * math.sin(i / 3)) for i in range(120)])
        variance = yang_zhang_variance(list(frame.bars))
        assert variance is not None
        sigma_root_t = math.sqrt(variance) * math.sqrt(len(frame.bars) - 1)

        assert max_drawdown_reading(frame).extras["standard_error"] == pytest.approx(
            100.0 * MAX_DRAWDOWN_NULL_SCATTER * sigma_root_t
        )
        assert current_drawdown_reading(frame).extras[
            "standard_error"
        ] == pytest.approx(100.0 * CURRENT_DRAWDOWN_NULL_SCATTER * sigma_root_t)
        assert days_underwater_reading(frame).extras[
            "standard_error"
        ] == pytest.approx(DAYS_UNDERWATER_NULL_SCATTER * (len(frame.bars) - 1))

    def test_the_frozen_scatters_are_what_the_null_actually_produces(self):
        """Re-measured at a fraction of the derivation's paths, wide bounds.

        Enough to catch a constant written for a different statistic; nowhere
        near enough to re-derive one, which is deliberate — nothing in the suite
        may move a shipped constant.
        """
        rng = np.random.default_rng(NULL_DERIVATION_SEED)
        shapes = gbm_shapes(
            rng,
            paths=400,
            sessions=250,
            daily_volatility=MATCHED_DAILY_VOLATILITIES[1],
            truncated=False,
        )
        maxima, currents, underwater = [], [], []
        for frame in frames_from(shapes):
            fall = drawdown_of(frame.bars)
            variance = yang_zhang_variance(list(frame.bars))
            if fall is None or variance is None or variance <= 0:
                continue
            scale = math.sqrt(variance) * math.sqrt(len(frame.bars) - 1)
            maxima.append(abs(fall.max_drawdown_pct) / 100.0 / scale)
            currents.append(abs(fall.current_drawdown_pct) / 100.0 / scale)
            underwater.append(fall.days_underwater / (len(frame.bars) - 1))

        assert float(np.std(maxima)) == pytest.approx(
            MAX_DRAWDOWN_NULL_SCATTER, rel=0.35
        )
        assert float(np.std(currents)) == pytest.approx(
            CURRENT_DRAWDOWN_NULL_SCATTER, rel=0.35
        )
        assert float(np.std(underwater)) == pytest.approx(
            DAYS_UNDERWATER_NULL_SCATTER, rel=0.35
        )

    def test_the_expected_fall_travels_beside_the_observed_one(self):
        frame = frame_of([20_000.0 * (0.998**i) for i in range(120)])
        reading = max_drawdown_reading(frame)

        assert reading.extras["expected_max_drawdown_pct"] < 0
        assert reading.extras["max_drawdown_pct"] < 0
        assert reading.extras["days_underwater"] > 0


class TestRiskAdjustedReturn:
    def test_sharpe_ships_the_lo_standard_error_and_its_interval(self):
        reading = sharpe_reading(frame_of([20_000.0 * (1.0005**i) for i in range(250)]))

        assert reading.value is not None
        assert reading.extras["standard_error"] > 0
        low, high = reading.extras["confidence_interval"]
        assert low < reading.value < high
        assert high - low == pytest.approx(2 * 1.96 * reading.extras["standard_error"])

    def test_a_short_sample_says_it_cannot_tell_the_ratio_from_zero(self):
        """The honest headline on the samples this system holds."""
        rng = random.Random(3)
        closes = [20_000.0]
        for _ in range(120):
            closes.append(closes[-1] * (1.0 + rng.gauss(0.0002, 0.02)))
        reading = sharpe_reading(frame_of(closes))

        assert reading.extras["indistinguishable_from_zero"] is True

    def test_the_sqrt_252_shortcut_is_refused_when_the_returns_are_autocorrelated(
        self,
    ):
        """A contract rule inside the field, not a convention applied anyway.

        Lo measured hedge-fund Sharpes overstated by as much as 65% by taking
        √q on a series whose autocorrelation forbids it.
        """
        # Returns that carry over from one session to the next — an AR(1) with a
        # positive coefficient — which is the case Lo's correction exists for and
        # the one √252 overstates.
        rng = random.Random(23)
        closes = [20_000.0]
        step = 0.0
        for _ in range(250):
            step = 0.6 * step + rng.gauss(0.0004, 0.01)
            closes.append(closes[-1] * (1.0 + step))
        reading = sharpe_reading(frame_of(closes))

        assert reading.extras["annualization"] == "lo_corrected"
        assert reading.extras["first_autocorrelation"] > 1.96 / math.sqrt(250)
        assert reading.value is not None

    def test_returns_too_negatively_autocorrelated_to_annualize_are_refused(self):
        """√252 is the number the correction exists to refuse, so it is not what
        the field falls back to when the correction has no root to take."""
        closes = [20_000.0 * (1.0 + 0.03 * (index % 2)) for index in range(250)]
        reading = sharpe_reading(frame_of(closes))

        assert reading.value is None
        assert reading.refusal is SignalIssue.AUTOCORRELATION_UNUSABLE

    def test_an_uncorrelated_series_keeps_the_ordinary_factor(self):
        rng = random.Random(11)
        closes = [20_000.0]
        for _ in range(250):
            closes.append(closes[-1] * (1.0 + rng.gauss(0.0, 0.015)))
        reading = sharpe_reading(frame_of(closes))

        assert reading.extras["annualization"] == "sqrt_252"

    def test_lo_s_factor_is_the_root_of_q_exactly_where_it_is_entitled_to_be(self):
        """The formula reduces to √q under zero autocorrelation, and is smaller
        under positive autocorrelation — the direction that matters."""
        rng = random.Random(7)
        independent = [rng.gauss(0.0, 0.01) for _ in range(400)]
        trending = []
        previous = 0.0
        for _ in range(400):
            previous = 0.6 * previous + rng.gauss(0.0, 0.01)
            trending.append(previous)

        assert annualization_of(independent).factor == pytest.approx(
            math.sqrt(TRADING_SESSIONS_PER_YEAR)
        )
        corrected = annualization_of(trending)
        assert corrected.method == "lo_corrected"
        assert corrected.factor < math.sqrt(TRADING_SESSIONS_PER_YEAR)

    def test_sortino_divides_by_every_observation_and_not_only_the_losses(self):
        """The common implementation divides by the count below the benchmark and
        understates downside risk exactly when most returns are positive."""
        rng = random.Random(19)
        closes = [20_000.0]
        for _ in range(250):
            closes.append(closes[-1] * (1.0 + rng.gauss(0.0005, 0.012)))
        frame = frame_of(closes)
        reading = sortino_reading(frame)

        returns = [
            math.log(later.close / earlier.close)
            for earlier, later in zip(frame.bars, frame.bars[1:])
        ]
        below = [item for item in returns if item < 0]
        expected = math.sqrt(sum(item * item for item in below) / len(returns))

        assert reading.extras["downside_deviation_pct"] == pytest.approx(
            100.0 * expected
        )
        assert reading.extras["downside_obs_count"] == len(below)

    def test_sortino_is_withheld_below_the_downside_observation_floor(self):
        """Sortino's discrete downside deviation is documented as unstable on a
        handful of observations, so it is not printed with a caveat."""
        reading = sortino_reading(frame_of([20_000.0 * (1.002**i) for i in range(60)]))

        assert reading.value is None
        assert reading.refusal is SignalIssue.INSUFFICIENT_DOWNSIDE_OBSERVATIONS
        assert MIN_DOWNSIDE_OBSERVATIONS == 10

    def test_a_flat_series_has_no_ratio_to_report(self):
        reading = sharpe_reading(frame_of([20_000.0] * 60))

        assert reading.value is None
        assert reading.refusal is SignalIssue.BASELINE_DISPERSION_ZERO


class TestThePriceZone:
    def test_it_is_one_realized_sigma_either_side_of_the_reference_price(self):
        frame = frame_of([20_000.0 * (1.0 + 0.004 * math.sin(i)) for i in range(21)])
        reading = price_zone_reading(frame)
        variance = yang_zhang_variance(list(frame.bars))

        assert variance is not None and reading.value is not None
        sigma = math.sqrt(variance)
        reference = frame.bars[-1].close
        assert reading.value == pytest.approx(100.0 * sigma)
        assert reading.extras["reference_price"] == reference
        assert reading.extras["lower_price"] == pytest.approx(
            reference * (1.0 - sigma)
        )
        assert reading.extras["upper_price"] == pytest.approx(
            reference * (1.0 + sigma)
        )

    def test_it_reads_twenty_sessions_plus_the_close_before_them(self):
        assert PRICE_ZONE.min_sessions == PRICE_ZONE_MIN_SESSIONS == 21

    def test_its_sanctioned_reading_is_a_range_and_never_a_direction(self):
        """The resolution of the product's price-zone commitment against
        ADR-0010's ban on direction: the zone is a number, the judgement is the
        model's, and the artifact carries the fields it rested on."""
        assert PRICE_ZONE.claim is Claim.DESCRIPTIVE
        assert "ordinary daily range" in PRICE_ZONE.interpretation
        for word in ("buy", "sell", "target", "recommend", "should"):
            assert word not in PRICE_ZONE.interpretation.lower()

    def test_it_is_registered_and_named_where_the_profile_will_read_it(self):
        assert PRICE_ZONE.name == "price_zone.ordinary_range_pct"

    def test_it_never_reports_a_negative_range(self):
        reading = price_zone_reading(frame_of([20_000.0] * 21, spread=0.005))

        assert reading.value is not None
        assert reading.value >= 0


class TestEveryFieldReachesBarsThroughTheGatewayAlone:
    @pytest.mark.parametrize(
        ("field", "compute"),
        [
            (REALIZED_VOLATILITY, realized_volatility_reading),
            (PRICE_ZONE, price_zone_reading),
            (MAX_DRAWDOWN, max_drawdown_reading),
            (CURRENT_DRAWDOWN, current_drawdown_reading),
            (DAYS_UNDERWATER, days_underwater_reading),
            (DRAWDOWN_VERSUS_BENCHMARK, drawdown_versus_benchmark_reading),
            (SHARPE, sharpe_reading),
            (SORTINO, sortino_reading),
        ],
    )
    def test_it_echoes_window_health(self, field, compute):
        with open_session() as session:
            days = store_history(session, 260)
            value = serve(session, "AAA", field, compute, end=days[-1])

        assert value.refusal is None, f"{field.name} refused a clean window"
        assert value.value is not None
        assert value.health.refusal is None
        assert value.health.sessions_used == field.min_sessions
        assert value.health.last_session == days[-1]

    @pytest.mark.parametrize(
        ("field", "compute"),
        [
            (REALIZED_VOLATILITY, realized_volatility_reading),
            (PRICE_ZONE, price_zone_reading),
            (MAX_DRAWDOWN, max_drawdown_reading),
            (SHARPE, sharpe_reading),
        ],
    )
    def test_a_window_the_gateway_refuses_refuses_the_field(self, field, compute):
        """There is no second path to a bar, so a refused window is a refused
        field under the gateway's own name."""
        with open_session() as session:
            days = store_history(session, 15)
            value = serve(session, "AAA", field, compute, end=days[-1])

        assert value.value is None
        assert value.refusal is SignalIssue.INSUFFICIENT_HISTORY
        assert value.health.refusal is SignalIssue.INSUFFICIENT_HISTORY


class TestWhatTheClusterDeclares:
    def test_the_signs_are_declared_the_way_the_numbers_come_out(self):
        assert REALIZED_VOLATILITY.sign is Sign.NON_NEGATIVE
        assert PRICE_ZONE.sign is Sign.NON_NEGATIVE
        assert MAX_DRAWDOWN.sign is Sign.NON_POSITIVE
        assert CURRENT_DRAWDOWN.sign is Sign.NON_POSITIVE
        assert DAYS_UNDERWATER.sign is Sign.NON_NEGATIVE
        assert SHARPE.sign is Sign.SIGNED
        assert SORTINO.sign is Sign.SIGNED

    def test_the_units_say_what_each_number_is_measured_in(self):
        assert REALIZED_VOLATILITY.unit is Unit.PERCENT_ANNUALIZED
        assert MAX_DRAWDOWN.unit is Unit.PERCENT
        assert DAYS_UNDERWATER.unit is Unit.SESSIONS
        assert SHARPE.unit is Unit.RATIO
        assert DRAWDOWN_VERSUS_BENCHMARK.unit is Unit.RATIO

    def test_only_the_benchmark_comparison_can_fire(self):
        """Estimators have no threshold and therefore no null: the rule is that a
        threshold requires a null, whatever the number's origin."""
        assert DRAWDOWN_VERSUS_BENCHMARK.kind is FieldKind.SIGNAL
        for field in (
            REALIZED_VOLATILITY,
            PRICE_ZONE,
            MAX_DRAWDOWN,
            CURRENT_DRAWDOWN,
            DAYS_UNDERWATER,
            SHARPE,
            SORTINO,
        ):
            assert field.kind is FieldKind.ESTIMATOR
            assert field.threshold is None
            assert field.null_fpr is None

    def test_the_benchmark_field_records_that_the_derived_threshold_won(self):
        threshold = DRAWDOWN_VERSUS_BENCHMARK.threshold
        assert threshold is not None
        assert threshold.convention == 1.0
        assert threshold.value == threshold.derived > threshold.convention

    def test_close_to_close_stays_available_as_the_baseline(self):
        """Every efficiency claim in the module is relative to it, so it is
        reported rather than replaced."""
        frame = frame_of([20_000.0 * (1.004**i) for i in range(30)])
        assert close_to_close_variance(list(frame.bars)) is not None
