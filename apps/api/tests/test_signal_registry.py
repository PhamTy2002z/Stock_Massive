"""What a number has to declare before a model may see it.

The registry is a gate rather than a catalogue, so almost every test here is
about a declaration being refused:

*Nine attributes, none optional.* A field that forgets to say what unit it is in
or how it is to be read fails at import. That is the difference between a bar and
a checklist — a checklist holds for five fields and fails at the sixth.

*``descriptive`` is a type, not a label.* In v1 every field is descriptive, and a
descriptive field may not return a direction-bearing key at all. The constraint
bites where the field is declared and again where its value is built, because a
prompt asking a model not to draw a conclusion is a behaviour measured after the
fact rather than a property of the system.

*Each kind carries its own bar.* An estimator without its uncertainty and a
percentile without the sample it was ranked in are both numbers that invite a
comparison they cannot support.

The one seeded signal field is exercised end to end against a stored window, so
the loop the registry exists for — declaration, gateway, null — is proven rather
than described.
"""

from __future__ import annotations

import dataclasses
import math
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import (
    BarDaily,
    CorporateAction,
    ListingRoster,
    ProviderSnapshot,
)
from src.stocks.providers import Exchange, PriceBasis
from src.stocks.providers.contracts import (
    Capability,
    ProviderSource,
    cover_source,
    main_source,
)
from src.stocks.signals.bars import BarSeries, prepare_bars
from src.stocks.signals.fields import BarProjection
from src.stocks.signals.fields import (
    CATALOG_NULL_FPR_CEILING,
    PERCENTILE_ABSOLUTE_FLOOR,
    Claim,
    FieldKind,
    FieldReading,
    FieldSource,
    FieldValue,
    NullCalibration,
    SignalField,
    Sign,
    Threshold,
    ThresholdOrigin,
    Unit,
    schema_description,
)
from src.stocks.signals.bars import Bar
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.price_band import LimitLock, band_limits, tick_size
from src.stocks.signals.registry import (
    REGISTRY,
    VOLATILITY_REGIME_Z,
    fields_of_kind,
    registered_field,
    registry_version,
    signal_fields,
)
from src.stocks.signals.serving import serve_field
from src.stocks.signals.volatility import (
    VOLATILITY_REGIME_BASELINE_DAYS,
    VOLATILITY_REGIME_MIN_SESSIONS,
    garman_klass_variance,
)

from .test_price_band import list_on, write_session

TEN_DECLARATIONS = (
    "unit",
    "sign",
    "interpretation",
    "kind",
    "claim",
    "source",
    "min_sessions",
    "threshold",
    "null_fpr",
    # The tenth, added when the daily spine became the source of sessions: which
    # stored measurement the field's arithmetic reads, and so which contract the
    # gateway enforces over its window.
    "projection",
)


def open_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        BarDaily.__table__,
        ListingRoster.__table__,
        CorporateAction.__table__,
        # Sessions moved to the daily spine; the reference, valuation and
        # fundamental Capabilities did not, and the foreign room a served field
        # carries is still read out of here.
        ProviderSnapshot.__table__,
    ):
        table.create(engine)
    return Session(engine)


def store_quiet_history(
    session: Session,
    symbol: str = "AAA",
    *,
    sessions: int = VOLATILITY_REGIME_MIN_SESSIONS + 2,
    seed: int = 11,
    locked_from_end: tuple[int, ...] = (),
    basis: PriceBasis = PriceBasis.RAW,
    scale: float = 1.0,
) -> tuple[date, ...]:
    """An ordinary stretch of sessions, with locked ones where asked for.

    Every move stays well inside the ±7% band, so the gateway serves the window
    rather than refusing a gap, and every session has a range of its own so that
    a robust baseline has something to be robust about. The sessions named in
    ``locked_from_end`` are written as ceiling locks — H=L=O=C at the limit — the
    way the store actually holds one.

    ``basis`` states what the stored prices mean; ``scale`` multiplies the whole
    window by one constant, which is what a provider does when it restates a
    series for a corporate action. The two together are how a test asks whether
    a field reads a ratio or a level.
    """
    rng = random.Random(seed)
    list_on(session, symbol, Exchange.HOSE)

    days: list[date] = []
    cursor = date(2025, 1, 6)
    while len(days) < sessions:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)

    close = 20_000.0
    locked_days = {days[-offset] for offset in locked_from_end}
    for day in days:
        if day in locked_days:
            ceiling = float(band_limits(Exchange.HOSE, _decimal(close)).ceiling)
            write_session(
                session,
                symbol,
                day,
                open_price=ceiling * scale,
                high=ceiling * scale,
                low=ceiling * scale,
                close=ceiling * scale,
                basis=basis,
            )
            close = ceiling
            continue

        drift = rng.uniform(-0.02, 0.02)
        spread = rng.uniform(0.004, 0.025)
        open_price = close * (1.0 + rng.uniform(-0.005, 0.005))
        next_close = close * (1.0 + drift)
        high = max(open_price, next_close) * (1.0 + spread)
        low = min(open_price, next_close) * (1.0 - spread)
        write_session(
            session,
            symbol,
            day,
            open_price=_on_tick(open_price) * scale,
            high=_on_tick(high) * scale,
            low=_on_tick(low) * scale,
            close=_on_tick(next_close) * scale,
            basis=basis,
        )
        close = _on_tick(next_close)
    return tuple(days)


def _on_tick(price: float) -> float:
    """The nearest price HOSE would accept an order at.

    The fixture used to round to a tenth of a dong, which is not a price this
    market quotes at any level — the step is 10, 50 or 100 depending on the band
    the price sits in. That was invisible while a band verdict was decided by the
    price basis column, and became visible the moment it was decided by whether
    the prices are the ones the board printed: a window of prices off the grid is
    a window the band machine correctly declines to judge, so the locked sessions
    a test planted stopped being counted.

    Snapping here rather than loosening the check, because the check is right and
    the fixture was wrong. Every session written by this helper is now a session
    that could have traded.
    """
    step = float(tick_size(Exchange.HOSE, _decimal(price)))
    return round(price / step) * step


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def a_reading(_frame) -> FieldReading:
    """A computation that answers the same thing for every window."""
    return FieldReading(value=1.0, extras={"standard_error": 0.1})


def a_field(**overrides) -> SignalField:
    """A minimal well-formed estimator, for tests that break one thing at a time."""
    declared = {
        "reading": a_reading,
        "name": "test.estimator",
        "unit": Unit.PERCENT,
        "sign": Sign.NON_NEGATIVE,
        "interpretation": "a number that means nothing outside this test",
        "kind": FieldKind.ESTIMATOR,
        "claim": Claim.DESCRIPTIVE,
        "source": FieldSource.COMPUTED,
        "min_sessions": 20,
        "threshold": None,
        "null_fpr": None,
        "projection": BarProjection.PRICE,
    }
    declared.update(overrides)
    return SignalField(**declared)


def a_health(session: Session, symbol: str, days: tuple[date, ...]):
    _, health = prepare_bars(session, symbol, 20, end=days[-1])
    return health


class TestTenDeclarationsOrItDoesNotShip:
    def test_every_registered_field_declares_all_ten(self):
        """Asserted against the type rather than against an instance.

        ``hasattr`` on a dataclass whose fields have no defaults can never fail,
        so it would pass a field renamed out from under the ADR. What has to hold
        is that the names ADR-0010 lists are the names the type declares — the
        nine it wrote down, and the projection added beside them.
        """
        declared = {entry.name for entry in dataclasses.fields(SignalField)}

        assert set(TEN_DECLARATIONS) <= declared

        for field in REGISTRY.values():
            for attribute in TEN_DECLARATIONS:
                # Present *and* answered for: `interpretation` and the two null
                # attributes are the ones a field can carry emptily.
                assert getattr(field, attribute) is not None or attribute in (
                    "threshold",
                    "null_fpr",
                ), f"{field.name} declares no {attribute}"

    def test_a_field_that_omits_one_fails_where_it_is_written(self):
        """At import, not in review. A declaration with a hole is a TypeError."""
        with pytest.raises(TypeError):
            SignalField(  # type: ignore[call-arg]
                name="test.incomplete",
                unit=Unit.PERCENT,
                sign=Sign.SIGNED,
                interpretation="incomplete on purpose",
                kind=FieldKind.ESTIMATOR,
                claim=Claim.DESCRIPTIVE,
                source=FieldSource.COMPUTED,
                min_sessions=20,
            )

    def test_a_field_that_does_not_say_how_to_read_it_is_refused(self):
        """``interpretation`` is the only sanctioned reading, so it cannot be blank."""
        with pytest.raises(ValueError, match="how it is to be read"):
            a_field(interpretation="   ")

    def test_the_registry_refuses_two_fields_under_one_name(self):
        """A duplicate does not conflict, it silently wins — and one surface then
        cites a field another surface believes it is citing."""
        from src.stocks.signals.registry import _index

        with pytest.raises(ValueError, match="declared twice"):
            _index(a_field(), a_field())

    def test_a_field_is_reached_by_name_and_a_missing_one_is_not_guessed_at(self):
        assert registered_field(VOLATILITY_REGIME_Z.name) is VOLATILITY_REGIME_Z
        with pytest.raises(KeyError):
            registered_field("volatility_regime.no_such_field")


class TestADescriptiveFieldMayNotPointAnywhere:
    def test_every_field_in_v1_is_descriptive(self):
        """``predictive`` unlocks only behind a measured forward-return harness."""
        assert all(field.claim is Claim.DESCRIPTIVE for field in REGISTRY.values())

    def test_a_descriptive_field_declaring_a_direction_is_rejected(self):
        """The constraint bites at the type, which is the whole point of ADR-0010.

        A field that returns a ``direction`` key is making a claim about the
        future whatever its documentation says, so it is refused where it is
        declared rather than caught in a payload review.
        """
        with pytest.raises(ValueError, match="descriptive and may not return"):
            a_field(output_keys=("standard_error", "direction"))

    @pytest.mark.parametrize(
        "key", ["direction", "signal", "expected_return", "recommendation"]
    )
    def test_the_refused_keys_are_the_ones_a_field_would_reach_for(self, key):
        with pytest.raises(ValueError, match="descriptive and may not return"):
            a_field(output_keys=(key,))

    def test_a_descriptive_field_returning_a_direction_is_rejected(self, tmp_path):
        """Declaration is not the only place it can happen, so it is not the only
        place it is checked."""
        with open_session() as session:
            days = store_quiet_history(session, sessions=25)
            health = a_health(session, "AAA", days)

        with pytest.raises(ValueError, match="descriptive and returned"):
            FieldValue(
                field=a_field(),
                value=1.0,
                health=health,
                extras={"standard_error": 0.1, "direction": "up"},
            )


class TestEachKindCarriesItsOwnBar:
    def test_an_estimator_ships_a_standard_error_or_an_interval(self):
        with open_session() as session:
            days = store_quiet_history(session, sessions=25)
            health = a_health(session, "AAA", days)

        with pytest.raises(ValueError, match="standard error"):
            FieldValue(field=a_field(), value=1.0, health=health, extras={})

        assert FieldValue(
            field=a_field(),
            value=1.0,
            health=health,
            extras={"confidence_interval": (0.5, 1.5)},
        ).value == 1.0

    def test_a_percentile_ships_its_n_and_its_cutoff_date(self):
        """A percentile over eleven names is a rank dressed up as a distribution."""
        percentile = a_field(
            name="test.percentile",
            kind=FieldKind.PERCENTILE,
            unit=Unit.PERCENTILE,
        )
        with open_session() as session:
            days = store_quiet_history(session, sessions=25)
            health = a_health(session, "AAA", days)

        with pytest.raises(ValueError, match="ranked among"):
            FieldValue(field=percentile, value=0.8, health=health, extras={"n": 40})

        assert FieldValue(
            field=percentile,
            value=0.8,
            health=health,
            extras={"n": 40, "as_of": "2026-08-14"},
        ).value == 0.8

    def test_a_signal_ships_a_threshold_a_null_and_a_statistic(self):
        with pytest.raises(ValueError, match="frozen threshold and a measured null"):
            a_field(name="test.signal", kind=FieldKind.SIGNAL)

    def test_a_field_that_cannot_fire_may_not_carry_a_threshold(self):
        """A threshold on an estimator describes nothing, and invites a null run
        on a number that never claims an event."""
        with pytest.raises(ValueError, match="cannot fire"):
            a_field(
                threshold=Threshold(
                    value=2.0,
                    origin=ThresholdOrigin.DERIVED,
                    convention=None,
                    derived=2.0,
                    note="nothing to fire",
                )
            )

    def test_an_estimator_shipping_a_null_standard_error_is_refused(self):
        """Presence is not the test, and a null under the key is how a field
        ships no uncertainty while looking as though it does."""
        with open_session() as session:
            days = store_quiet_history(session, sessions=25)
            health = a_health(session, "AAA", days)

        with pytest.raises(ValueError, match="neither may be null"):
            FieldValue(
                field=a_field(),
                value=1.0,
                health=health,
                extras={"standard_error": None, "confidence_interval": None},
            )

    def test_a_percentile_shipping_a_null_n_is_refused(self):
        percentile = a_field(
            name="test.percentile",
            kind=FieldKind.PERCENTILE,
            unit=Unit.PERCENTILE,
        )
        with open_session() as session:
            days = store_quiet_history(session, sessions=25)
            health = a_health(session, "AAA", days)

        with pytest.raises(ValueError, match="ranked among"):
            FieldValue(
                field=percentile,
                value=0.8,
                health=health,
                extras={"n": None, "as_of": "2026-08-14"},
            )

    def test_a_field_carries_the_computation_that_answers_for_it(self):
        """Passed beside the field instead, a caller could serve one field's
        declaration with another field's arithmetic and get a valid-looking
        answer."""
        with pytest.raises(ValueError, match="declares exactly one"):
            a_field(reading=None)

        assert all(
            entry.reading is not None or entry.ranked is not None
            for entry in REGISTRY.values()
        )

    def test_a_field_answers_for_one_symbol_or_across_a_sample_and_not_both(self):
        """Whether a number is a position within a sample is the field's to say.

        A field declaring both would let a caller pick, and the two answers are
        not the same number: one is this symbol's own figure and the other is
        where that figure sits among ninety-nine others.
        """
        with pytest.raises(ValueError, match="declares exactly one"):
            a_field(ranked=lambda window: None)

    def test_a_ranked_field_answers_with_a_percentile(self):
        with pytest.raises(ValueError, match="ranked across a cross-section"):
            a_field(reading=None, ranked=lambda window: None, kind=FieldKind.ESTIMATOR)

    def test_a_value_with_no_number_and_no_reason_is_refused(self):
        with open_session() as session:
            days = store_quiet_history(session, sessions=25)
            health = a_health(session, "AAA", days)

        with pytest.raises(ValueError, match="no value and no reason"):
            FieldValue(field=a_field(), value=None, health=health)

    def test_a_refusal_may_not_carry_a_number_beside_it(self):
        with open_session() as session:
            days = store_quiet_history(session, sessions=25)
            health = a_health(session, "AAA", days)

        with pytest.raises(ValueError, match="returned a number anyway"):
            FieldValue(
                field=a_field(),
                value=1.0,
                health=health,
                refusal=SignalIssue.INSUFFICIENT_HISTORY,
            )


class TestThresholdsAreFrozenAndTheStricterWins:
    def test_the_stricter_of_convention_and_derived_ships(self):
        threshold = VOLATILITY_REGIME_Z.threshold
        assert threshold is not None
        assert threshold.value == max(threshold.derived, threshold.convention or 0)

    def test_the_registry_records_which_of_the_two_won(self):
        """Precisely the line a reviewer will want to argue with, so it is on the
        record rather than reconstructible from a commit message."""
        threshold = VOLATILITY_REGIME_Z.threshold
        assert threshold is not None
        assert threshold.origin is ThresholdOrigin.DERIVED
        assert threshold.convention == 2.0
        assert "bootstrap" in threshold.note

    def test_a_threshold_looser_than_either_candidate_is_refused(self):
        with pytest.raises(ValueError, match="stricter of convention and derived"):
            Threshold(
                value=2.0,
                origin=ThresholdOrigin.CONVENTION,
                convention=2.0,
                derived=3.0,
                note="the derived value was ignored",
            )

    def test_a_threshold_that_misnames_where_it_came_from_is_refused(self):
        with pytest.raises(ValueError, match="came from derived"):
            Threshold(
                value=3.0,
                origin=ThresholdOrigin.CONVENTION,
                convention=2.0,
                derived=3.0,
                note="mislabelled",
            )


class TestTheNullIsMetadataAndNotAPayload:
    def test_the_published_rate_is_the_maximum_of_the_nulls(self):
        calibration = VOLATILITY_REGIME_Z.null_fpr
        assert calibration is not None
        assert calibration.published == max(
            calibration.gbm, calibration.gbm_truncated, calibration.block_bootstrap
        )

    def test_a_calibration_over_the_catalog_ceiling_cannot_be_declared(self):
        """A field that cannot reach 1% gets a stricter threshold or stays out."""
        with pytest.raises(ValueError, match="exceeds the catalog ceiling"):
            NullCalibration(
                gbm=0.002,
                gbm_truncated=0.002,
                block_bootstrap=0.05,
                paths=2000,
                seed=1,
            )

    def test_a_calibration_under_a_thousand_paths_cannot_be_declared(self):
        with pytest.raises(ValueError, match="at least 1000 paths"):
            NullCalibration(
                gbm=0.002,
                gbm_truncated=0.002,
                block_bootstrap=0.004,
                paths=500,
                seed=1,
            )

    def test_the_rate_rides_in_the_schema_description(self):
        """Read once before a call rather than repeated on every one of them."""
        described = schema_description(VOLATILITY_REGIME_Z)

        assert VOLATILITY_REGIME_Z.interpretation in described
        assert "0.47%" in described
        assert "1% ceiling" in described

    def test_a_field_that_never_fires_publishes_no_rate(self):
        """A zero would read as a perfect detector rather than as a field that
        makes no claim about an event at all."""
        assert "false-positive" not in schema_description(a_field())

    def test_the_rate_is_not_in_what_the_field_returns(self):
        """It rides in the tool schema description, read once before a call,
        rather than costing the response budget on every one."""
        with open_session() as session:
            days = store_quiet_history(session)
            value = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        assert value.refusal is None
        assert "null_fpr" not in value.extras
        assert VOLATILITY_REGIME_Z.null_fpr is not None
        assert VOLATILITY_REGIME_Z.null_fpr.published <= CATALOG_NULL_FPR_CEILING


class TestTheSeededVolatilityRegimeField:
    def test_it_is_registered_as_a_signal_and_so_the_harness_runs_it(self):
        assert VOLATILITY_REGIME_Z in signal_fields()
        assert VOLATILITY_REGIME_Z in fields_of_kind(FieldKind.SIGNAL)

    def test_it_reaches_bars_through_the_gateway_and_echoes_window_health(self):
        with open_session() as session:
            days = store_quiet_history(session)
            value = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        assert value.refusal is None
        assert value.value is not None
        assert value.health.sessions_used == VOLATILITY_REGIME_MIN_SESSIONS
        assert value.health.refusal is None
        assert value.health.last_session == days[-1]

    def test_a_window_the_gateway_refuses_refuses_the_field_by_the_same_name(self):
        """There is no second path to a bar, and a field that fell back to one
        would be the sixth tool the checklist fails at."""
        with open_session() as session:
            days = store_quiet_history(session, sessions=30)
            value = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        assert value.value is None
        assert value.refusal is SignalIssue.INSUFFICIENT_HISTORY
        assert value.health.refusal is SignalIssue.INSUFFICIENT_HISTORY

    def test_min_sessions_is_the_baseline_window_plus_the_session_being_judged(self):
        """``min_sessions`` covers window **plus skip**, and this field skips
        nothing — so it is sixty plus one, and never sixty."""
        assert (
            VOLATILITY_REGIME_MIN_SESSIONS == VOLATILITY_REGIME_BASELINE_DAYS + 1
        )
        assert VOLATILITY_REGIME_Z.min_sessions == VOLATILITY_REGIME_MIN_SESSIONS

    def test_limit_locked_sessions_are_out_of_the_baseline_and_still_reported(self):
        """A run of zero range deflates MAD and manufactures z on the sessions
        around it, so the locked ones leave the baseline — and stay on the
        report, because a baseline that dropped them still has to say they were
        there."""
        with open_session() as session:
            days = store_quiet_history(session, locked_from_end=(2, 3, 4))
            value = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        assert value.refusal is None
        assert value.health.limit_lock_days == 3
        assert value.extras["baseline_sessions"] == (
            VOLATILITY_REGIME_MIN_SESSIONS - 1 - 3
        )

    def test_a_window_mostly_locked_is_degraded_rather_than_called_ordinary(self):
        """Past a fifth of the window the estimate is measuring the band."""
        locked = tuple(range(2, 2 + VOLATILITY_REGIME_MIN_SESSIONS // 4))
        with open_session() as session:
            days = store_quiet_history(session, locked_from_end=locked)
            value = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        assert value.degraded_reason is SignalIssue.LIMIT_LOCKED_WINDOW

    def test_a_session_that_never_moved_has_no_range_to_read(self):
        """Not a variance of zero to be logged: a session with nothing to read."""
        with open_session() as session:
            days = store_quiet_history(session, locked_from_end=(1,))
            value = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        assert value.value is None
        assert value.refusal is SignalIssue.ZERO_RANGE_SESSION

    def test_the_garman_klass_second_term_is_close_over_open(self):
        """Molnár (2012) flags the close-to-close version as a literature error
        that "sometimes produces negative estimates". With C/O the estimator is
        non-negative for every bar that has one, which is what this pins."""
        bar = Bar(
            session_date=date(2025, 8, 14),
            open=25_000.0,
            high=25_500.0,
            low=24_800.0,
            close=25_400.0,
            volume=1,
            total_value_vnd=None,
            adjustment_factor=Decimal(1),
            limit_lock=LimitLock.NONE,
        )
        hl = math.log(25_500.0 / 24_800.0)
        co = math.log(25_400.0 / 25_000.0)
        expected = 0.5 * hl * hl - (2.0 * math.log(2.0) - 1.0) * co * co

        assert garman_klass_variance(bar) == pytest.approx(expected)
        assert garman_klass_variance(bar) >= 0


class TestWhatAWindowsPriceBasisDecides:
    """The rule that changed when the daily spine became the source.

    ``bar_daily`` is ``adjusted_at_source`` on every row there is. Under the old
    rule that window was refused outright, which after the source change would
    have refused every price field for every symbol — silently, since a refusal
    is a normal answer. The new rule serves it and turns the adjustment machine
    off instead.
    """

    def test_a_window_adjusted_throughout_is_served(self):
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.ADJUSTED_AT_SOURCE)
            value = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        assert value.refusal is None
        assert value.value is not None

    def test_a_window_raw_throughout_is_served_and_still_adjusts_from_actions(self):
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.RAW)
            frame, health = prepare_bars(session, "AAA", 20, end=days[-1])

        assert health.refusal is None
        assert frame is not None

    def test_a_window_holding_both_bases_is_refused_where_its_seam_falls(self):
        """Two bases in one window is a seam, not a weaker measurement."""
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.RAW)
            write_session(
                session,
                "AAA",
                days[-1],
                close=20_000,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )
            _, health = prepare_bars(session, "AAA", 20, end=days[-1])

        assert health.refusal is SignalIssue.MIXED_PRICE_BASIS

    def test_the_adjustment_machine_does_not_run_on_prices_already_rebased(self):
        """Running it would take every entitlement out a second time.

        The stored action is real and the window contains its ex-date, so the
        raw window below rebases and the adjusted one must not. Read off
        ``adjustment.applied``, which is what Window Health reports either way.
        """
        ex_date = None
        applied: dict[str, bool] = {}
        for label, basis in (
            ("raw", PriceBasis.RAW),
            ("adjusted", PriceBasis.ADJUSTED_AT_SOURCE),
        ):
            with open_session() as session:
                days = store_quiet_history(session, basis=basis)
                ex_date = days[-5]
                _store_stock_dividend(session, "AAA", ex_date)
                _, health = prepare_bars(session, "AAA", 20, end=days[-1])
            applied[label] = health.adjustment.applied

        assert applied["raw"] is True
        assert applied["adjusted"] is False

    def test_every_ratio_a_field_reads_survives_the_window_being_rescaled(self):
        """Why serving an adjusted window is sound, stated as an assertion.

        A provider that rebases the whole series multiplies every price in the
        window by one constant. This is the golden test for the seventeen
        OHLCV-only fields: their arithmetic is ratios, so the constant divides
        out. It is asserted over the gateway's own bars rather than over hand-made
        ones, so a future change that made a field read a price *level* would
        break it here.
        """
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.ADJUSTED_AT_SOURCE)
            plain = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        with open_session() as session:
            days = store_quiet_history(
                session, basis=PriceBasis.ADJUSTED_AT_SOURCE, scale=2.5
            )
            rescaled = serve_field(session, "AAA", VOLATILITY_REGIME_Z, end=days[-1])

        assert plain.value is not None
        assert rescaled.value == pytest.approx(plain.value)


def _store_stock_dividend(session: Session, symbol: str, ex_date: date) -> None:
    """One priceable entitlement on ``ex_date``: a 10% stock dividend."""
    session.add(
        CorporateAction(
            symbol=symbol,
            source="vnstock",
            event_code="ISS",
            title="Stock dividend",
            kind="stock_dividend",
            ex_date=ex_date,
            exercise_ratio=Decimal("0.1"),
            changes_share_count=True,
            confirmation="confirmed",
            observed_at=datetime(2026, 8, 13, 11, 0, tzinfo=timezone.utc),
        )
    )
    session.flush()


class TestWhichProjectionEachFieldIsServedUnder:
    """Which contract the gateway enforces, declared per field rather than
    inherited from the gateway's default.

    The default is the price projection, so before this was declared a field
    whose arithmetic never touched a price still inherited the price-basis and
    band refusals — which on the daily spine meant refusing outright. The
    assertions below are about the two that genuinely do not read a price, and
    about the three that look as though they might not and do.
    """

    def test_every_registered_field_names_one(self):
        for field in REGISTRY.values():
            assert isinstance(field.projection, BarProjection), field.name

    @pytest.mark.parametrize(
        "name",
        ["liquidity_profile.adtv_shares", "factor_percentiles.roe_percentile"],
    )
    def test_the_two_that_read_no_price_are_served_on_quantities(self, name):
        assert registered_field(name).projection is BarProjection.VOLUME

    @pytest.mark.parametrize(
        "name",
        [
            "liquidity_profile.adtv_vnd",
            "liquidity_profile.amihud_illiq",
            "liquidity_profile.adtv_percentile",
        ],
    )
    def test_the_liquidity_fields_that_do_arithmetic_on_close_stay_on_price(
        self, name
    ):
        """``adtv_percentile`` is the one that cannot be moved at all.

        Its peer standing is measured only when the projection is price
        (``bars._adtv_standing``), so serving it on quantities would lock it into
        ``ranking_unavailable`` permanently — a refusal produced by the
        declaration rather than by anything missing from the store.
        """
        assert registered_field(name).projection is BarProjection.PRICE

    def test_a_volume_field_is_served_where_a_price_field_is_refused(self):
        """The whole point, made mechanical, on the seam that still refuses."""
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.RAW)
            write_session(
                session,
                "AAA",
                days[-1],
                close=20_000,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )
            _, on_price = prepare_bars(
                session, "AAA", 20, end=days[-1], projection=BarProjection.PRICE
            )
            _, on_volume = prepare_bars(
                session, "AAA", 20, end=days[-1], projection=BarProjection.VOLUME
            )

        assert on_price.refusal is SignalIssue.MIXED_PRICE_BASIS
        assert on_volume.refusal is None

    def test_the_registry_digest_moves_when_a_projection_does(self, monkeypatch):
        """It decides whether a field answers at all, so two answers made under
        different projections must not carry the same registry identity.

        The Evidence Manifest carries this digest, and it is silent when wrong:
        a field moved between projections without it moving would let an answer
        produced under one rule be compared with one produced under the other.
        """
        import src.stocks.signals.registry as registry_module

        before = registry_version()
        name = "liquidity_profile.adtv_shares"
        moved = dict(REGISTRY)
        moved[name] = dataclasses.replace(
            REGISTRY[name], projection=BarProjection.PRICE
        )
        monkeypatch.setattr(registry_module, "REGISTRY", moved)

        assert registry_version() != before


class TestTradedMoneyIsDerivedRatherThanRefused:
    """The three liquidity fields, over a source that reports no traded value.

    ``bar_daily`` holds OHLCV and nothing else, and the daily Adapter's own
    docstring tells its caller to multiply close by volume. So the alternative to
    deriving that product is refusing three fields over one multiplication. It is
    derived once, at the ``SessionSnapshot`` seam, and the assertions here are
    about the two consequences of choosing that seam:

    **It has to reach two tiers, not one.** ``adtv_vnd`` and ``amihud_illiq``
    read ``Bar.total_value_vnd``; the gateway's own peer standing reads the
    snapshot directly, and ``adtv_percentile`` reads that standing. Deriving in
    the first place only would leave the third permanently
    ``ranking_unavailable`` — a refusal manufactured by where the arithmetic sat.

    **A session that did not trade is missing, not zero.** Close times a zero
    volume is a well-formed ``0.0``, and ``average_over_sessions`` refuses a
    window with a gap in it while averaging a zero straight in. Returning zero
    would have turned the refusal that guards this field into one that can no
    longer fire.
    """

    #: Enough peers for a percentile to be served over them: the floor is
    #: ``max(ceil(0.6 × asked), 15)``, so twenty-five answer it with room over.
    PEER_COUNT = 25

    def _with_peers(self, session: Session) -> tuple[tuple[date, ...], list[str]]:
        """``AAA`` plus enough peers for the standing to have a sample."""
        days = store_quiet_history(session, basis=PriceBasis.ADJUSTED_AT_SOURCE)
        peers = [f"P{index:02d}" for index in range(self.PEER_COUNT)]
        for index, peer in enumerate(peers):
            store_quiet_history(
                session,
                peer,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
                seed=100 + index,
            )
        return days, ["AAA", *peers]

    def test_the_money_is_the_close_times_the_shares(self):
        """The arithmetic, off the gateway's own bars.

        ``write_session`` defaults the volume, so this pins the product against
        the two numbers that produced it rather than against a recorded figure.
        """
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.ADJUSTED_AT_SOURCE)
            frame, _ = prepare_bars(session, "AAA", 20, end=days[-1])

        assert frame is not None
        for bar in frame.bars:
            assert bar.close is not None
            assert bar.volume is not None
            assert bar.total_value_vnd == pytest.approx(bar.close * bar.volume)

    def test_the_two_fields_that_read_a_bar_answer_with_a_number(self):
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.ADJUSTED_AT_SOURCE)
            money = serve_field(
                session,
                "AAA",
                registered_field("liquidity_profile.adtv_vnd"),
                end=days[-1],
            )
            amihud = serve_field(
                session,
                "AAA",
                registered_field("liquidity_profile.amihud_illiq"),
                end=days[-1],
            )

        assert money.refusal is None
        assert money.value is not None and money.value > 0
        assert amihud.refusal is None
        assert amihud.value is not None and amihud.value >= 0

    def test_the_derived_money_reaches_the_gateways_own_standing(self):
        """The claim that decided where the derivation goes.

        ``WindowHealth.adtv`` is measured off the snapshots, one tier below the
        bars. If it is ``None`` here the derivation never reached it, and
        ``adtv_percentile`` is refused for a reason that is not about the store.
        """
        with open_session() as session:
            days, names = self._with_peers(session)
            _, health = prepare_bars(
                session, "AAA", 20, end=days[-1], peers=names
            )

        assert health.adtv is not None
        assert health.adtv.average_value_vnd > 0
        assert health.adtv.n >= PERCENTILE_ABSOLUTE_FLOOR

    def test_the_percentile_answers_off_that_standing(self):
        with open_session() as session:
            days, names = self._with_peers(session)
            value = serve_field(
                session,
                "AAA",
                registered_field("liquidity_profile.adtv_percentile"),
                end=days[-1],
                peers=names,
            )

        assert value.refusal is None
        assert value.value is not None
        assert 0.0 <= value.value <= 100.0

    def test_a_session_that_did_not_trade_is_missing_rather_than_zero(self):
        """The refusal has to still fire, and the average must not sag.

        Written as one session at zero volume inside the averaged stretch. Were
        the product ``0.0``, the window would be complete, the field would answer,
        and the answer would be a twentieth lighter than the market it describes.
        """
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.ADJUSTED_AT_SOURCE)
            write_session(
                session,
                "AAA",
                days[-3],
                close=20_000,
                volume=0,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )
            frame, _ = prepare_bars(session, "AAA", 20, end=days[-1])
            money = serve_field(
                session,
                "AAA",
                registered_field("liquidity_profile.adtv_vnd"),
                end=days[-1],
            )

        assert frame is not None
        untraded = [bar for bar in frame.bars if bar.volume == 0]
        assert untraded, "the fixture has to plant a session that did not trade"
        assert all(bar.total_value_vnd is None for bar in untraded)
        assert money.value is None
        assert money.refusal is SignalIssue.TRADED_FIGURE_NOT_STORED

    def test_amihud_steps_over_that_session_instead_of_refusing(self):
        """It guards its own denominator, so it degrades where ADTV refuses.

        Asserted beside the test above rather than assumed: the two fields read
        the same derived figure and answer differently, and the count of skipped
        sessions is what says so out loud.
        """
        with open_session() as session:
            days = store_quiet_history(session, basis=PriceBasis.ADJUSTED_AT_SOURCE)
            write_session(
                session,
                "AAA",
                days[-3],
                close=20_000,
                volume=0,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )
            amihud = serve_field(
                session,
                "AAA",
                registered_field("liquidity_profile.amihud_illiq"),
                end=days[-1],
            )

        assert amihud.refusal is None
        assert amihud.value is not None
        assert amihud.extras["zero_volume_days"] >= 1


class TestTheIndexSeriesIsServedThroughTheSameGateway:
    """VNINDEX, read from the daily spine by the reader that serves equities.

    The index is not a second reading path. ``BarSeries`` decides everything the
    gateway does differently for one — the band, the read-time adjustment, the
    peer cross-section are each switched off by a predicate on that value — so
    what is asserted here is that the shared path serves the series correctly,
    not that a parallel one exists.

    The ownership of this capability moved to the daily spine's source on
    2026-08-28. The objection that had kept it out was that a second index series
    would put two price bases on one instrument that is adjusted for nothing; the
    reason that is now safe is that there is exactly one, which is the property
    the last test here pins.
    """

    INDEX_SESSIONS = 24

    def _store_index_history(self, session: Session) -> tuple[date, ...]:
        """A rising VNINDEX in points, on the days the calendar calls sessions.

        Written over the flat level ``write_session`` puts on the calendar, so
        the series has a range of its own and a test can tell a level apart from
        a scaled one.
        """
        days: list[date] = []
        cursor = date(2025, 1, 6)
        while len(days) < self.INDEX_SESSIONS:
            if cursor.weekday() < 5:
                days.append(cursor)
            cursor += timedelta(days=1)

        level = 1_200.0
        for day in days:
            level *= 1.004
            write_session(
                session,
                "VNINDEX",
                day,
                close=round(level, 2),
                high=round(level * 1.003, 2),
                low=round(level * 0.997, 2),
                open_price=round(level * 0.999, 2),
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
                series="index",
            )
            # The calendar is the index series itself, so the equity row is what
            # makes these days Trading Days without overwriting the levels above.
            write_session(
                session,
                "AAA",
                day,
                close=20_000,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
            )
        return tuple(days)

    def test_the_series_is_served_and_the_window_is_not_refused(self):
        with open_session() as session:
            days = self._store_index_history(session)
            frame, health = prepare_bars(
                session,
                "VNINDEX",
                20,
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert health.refusal is None
        assert frame is not None
        assert len(frame.bars) == 20

    def test_the_level_is_in_points_and_nothing_rescaled_it(self):
        """The unit trap: an index scaled like a share price reads as 1.8 million.

        The store decides the scale once, at ingest, from the series. A second
        scaling anywhere on the read path would show up here and nowhere else,
        because no equity assertion can tell 20.000 dong from 20.000 of anything.
        """
        with open_session() as session:
            days = self._store_index_history(session)
            frame, _ = prepare_bars(
                session,
                "VNINDEX",
                20,
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert frame is not None
        closes = [bar.close for bar in frame.bars]
        assert all(close is not None for close in closes)
        assert all(1_000.0 < close < 3_000.0 for close in closes)
        # Rising, which is what the fixture built: a flat series would pass the
        # bound above while saying nothing about whether the levels arrived.
        assert closes == sorted(closes)

    def test_the_gateway_asks_the_index_none_of_the_three_equity_questions(self):
        """Each one is a category error on a composite, not a missing input."""
        assert BarSeries.MARKET_INDEX.has_price_band is False
        assert BarSeries.MARKET_INDEX.has_corporate_actions is False
        assert BarSeries.MARKET_INDEX.has_peer_cross_section is False

        with open_session() as session:
            days = self._store_index_history(session)
            frame, health = prepare_bars(
                session,
                "VNINDEX",
                20,
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert frame is not None
        assert all(bar.band is None for bar in frame.bars)
        assert health.band_regime is None
        assert health.adjustment.applied is False
        # No peers to rank a composite among; ranking its turnover would rank it
        # against its own members.
        assert health.adtv is None

    def test_the_index_capability_has_one_owner_and_one_basis(self):
        """Why reading the basis as "no adjustment to make" is safe here.

        It is safe because it is unanimous. Asserted as two halves of one fact:
        the capability admits a single source, and the window that source serves
        carries a single basis — so no index window can hold a seam, and the
        refusal that would have caught one has nothing to catch.
        """
        assert cover_source(Capability.MARKET_INDEX) is None
        assert main_source(Capability.MARKET_INDEX) is ProviderSource.VNSTOCK

        with open_session() as session:
            days = self._store_index_history(session)
            _, health = prepare_bars(
                session,
                "VNINDEX",
                20,
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert health.refusal is not SignalIssue.MIXED_PRICE_BASIS
        assert health.refusal is None


class TestTheBandVerdictOnAnAdjustedWindow:
    """The second price-basis gate, and what it was silently switching off.

    ``measure_band`` asks the basis question of a session and its anchor, and it
    used to refuse a pair adjusted throughout. Every row in the daily spine is
    adjusted, so that refused every session of every symbol — and it did so
    without raising anything a test could see: a withheld verdict is
    ``INDETERMINATE``, ``Bar.limit_locked`` reads that as *not locked*,
    ``without_limit_locks()`` then drops nothing, and a baseline volatility whose
    own docstring says limit-locked sessions may not be in it was computed over
    windows that still held them.

    So the assertions here are deliberately about the consequence rather than
    about the gate: that a lock is counted, and that the frame really removes it.
    A test that only checked the refusal code would have passed throughout the
    period the behaviour was wrong.
    """

    def test_a_ceiling_lock_is_counted_on_an_adjusted_window(self):
        with open_session() as session:
            days = store_quiet_history(
                session,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
                locked_from_end=(2, 3, 4),
            )
            _, health = prepare_bars(session, "AAA", 20, end=days[-1])

        assert health.refusal is None
        assert health.limit_lock_days > 0
        assert len(health.limit_lock_dates) == health.limit_lock_days

    def test_the_frame_actually_drops_the_locked_sessions(self):
        """The half that matters to a number: counted *and* excluded.

        ``limit_lock_days`` moving off zero only proves the verdict arrived.
        This proves the verdict is acted on, which is the part a range estimator
        depends on — a run of ``H=L=O=C`` deflates a robust baseline and
        manufactures a z-score on the sessions either side of it.
        """
        with open_session() as session:
            days = store_quiet_history(
                session,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
                locked_from_end=(2, 3, 4),
            )
            frame, health = prepare_bars(session, "AAA", 20, end=days[-1])

        assert frame is not None
        kept = frame.without_limit_locks()
        assert len(kept.bars) == len(frame.bars) - health.limit_lock_days
        assert all(not bar.limit_locked for bar in kept.bars)
        assert any(bar.limit_locked for bar in frame.bars)

    def test_an_upcom_session_is_undecided_and_stays_that_way(self):
        """Not a thin window and not a missing backfill: no VWAP is stored.

        The board anchors its band on the prior session's round-lot continuous
        VWAP, and the daily spine holds OHLCV. The code names the absent input so
        that a reader is not sent looking for a fix in the window length.
        """
        with open_session() as session:
            days = store_quiet_history(
                session, basis=PriceBasis.ADJUSTED_AT_SOURCE
            )
            # Moved to the board rather than listed twice: the fixture already
            # put this symbol on HOSE, and the register holds one row per symbol.
            session.execute(
                ListingRoster.__table__.update()
                .where(ListingRoster.symbol == "AAA")
                .values(exchange=Exchange.UPCOM.value)
            )
            session.flush()
            frame, health = prepare_bars(session, "AAA", 20, end=days[-1])

        assert frame is not None
        assert health.limit_lock_days == 0
        assert all(bar.band is None for bar in frame.bars)
        assert all(
            bar.band_undecided_reason is SignalIssue.ANCHOR_NOT_STORED
            for bar in frame.bars
        )

    def test_a_rebased_window_says_so_rather_than_reporting_no_locks(self):
        """The failure this phase exists to make loud.

        ``scale`` is what a provider does when it restates a series: one constant
        over every price. It takes them off the quoting grid, so no session can
        be judged — and the point is that the window says which input it is short
        of instead of answering that this symbol never reached its band.
        """
        with open_session() as session:
            days = store_quiet_history(
                session,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
                locked_from_end=(2, 3, 4),
                scale=1.037,
            )
            frame, health = prepare_bars(session, "AAA", 20, end=days[-1])

        assert frame is not None
        assert health.limit_lock_days == 0
        assert SignalIssue.PRICE_OFF_TICK_GRID in health.band_undecided_reasons
        assert all(
            bar.band_undecided_reason is SignalIssue.PRICE_OFF_TICK_GRID
            for bar in frame.bars
        )

    def test_band_pressure_answers_on_an_adjusted_window(self):
        """The field the phase is named for, end to end through the gateway."""
        with open_session() as session:
            days = store_quiet_history(
                session,
                basis=PriceBasis.ADJUSTED_AT_SOURCE,
                locked_from_end=(2, 3, 4),
            )
            value = serve_field(
                session,
                "AAA",
                registered_field("band_pressure.limit_days_in_window"),
                end=days[-1],
            )

        assert value.refusal is None
        assert value.value is not None
        assert value.value > 0
