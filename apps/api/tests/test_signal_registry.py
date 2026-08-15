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
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import Exchange
from src.stocks.signals.bars import prepare_bars
from src.stocks.signals.fields import (
    CATALOG_NULL_FPR_CEILING,
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
from src.stocks.signals.price_band import LimitLock, band_limits
from src.stocks.signals.registry import (
    REGISTRY,
    VOLATILITY_REGIME_Z,
    fields_of_kind,
    registered_field,
    signal_fields,
)
from src.stocks.signals.serving import serve_field
from src.stocks.signals.volatility import (
    VOLATILITY_REGIME_BASELINE_DAYS,
    VOLATILITY_REGIME_MIN_SESSIONS,
    garman_klass_variance,
)

from .test_price_band import list_on, write_session

NINE_DECLARATIONS = (
    "unit",
    "sign",
    "interpretation",
    "kind",
    "claim",
    "source",
    "min_sessions",
    "threshold",
    "null_fpr",
)


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


def store_quiet_history(
    session: Session,
    symbol: str = "AAA",
    *,
    sessions: int = VOLATILITY_REGIME_MIN_SESSIONS + 2,
    seed: int = 11,
    locked_from_end: tuple[int, ...] = (),
) -> tuple[date, ...]:
    """An ordinary stretch of sessions, with locked ones where asked for.

    Every move stays well inside the ±7% band, so the gateway serves the window
    rather than refusing a gap, and every session has a range of its own so that
    a robust baseline has something to be robust about. The sessions named in
    ``locked_from_end`` are written as ceiling locks — H=L=O=C at the limit — the
    way the store actually holds one.
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
                open_price=ceiling,
                high=ceiling,
                low=ceiling,
                close=ceiling,
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
            open_price=round(open_price, 1),
            high=round(high, 1),
            low=round(low, 1),
            close=round(next_close, 1),
        )
        close = round(next_close, 1)
    return tuple(days)


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
    }
    declared.update(overrides)
    return SignalField(**declared)


def a_health(session: Session, symbol: str, days: tuple[date, ...]):
    _, health = prepare_bars(session, symbol, 20, end=days[-1])
    return health


class TestNineDeclarationsOrItDoesNotShip:
    def test_every_registered_field_declares_all_nine(self):
        """Asserted against the type rather than against an instance.

        ``hasattr`` on a dataclass whose fields have no defaults can never fail,
        so it would pass a field renamed out from under the ADR. What has to hold
        is that the nine names ADR-0010 lists are the nine the type declares.
        """
        declared = {entry.name for entry in dataclasses.fields(SignalField)}

        assert set(NINE_DECLARATIONS) <= declared

        for field in REGISTRY.values():
            for attribute in NINE_DECLARATIONS:
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

    def test_a_computed_field_carries_the_computation_that_answers_for_it(self):
        """Passed beside the field instead, a caller could serve one field's
        declaration with another field's arithmetic and get a valid-looking
        answer."""
        with pytest.raises(ValueError, match="computed, so the computation"):
            a_field(reading=None)

        assert all(
            entry.reading is not None
            for entry in REGISTRY.values()
            if entry.source is FieldSource.COMPUTED
        )

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
