"""What the foreign-flow cluster says, and the two things it will not say.

The distinctive dataset, and the one where the contract does most of the work:

*It does not claim to predict.* No verified published result shows HOSE foreign
net buying forecasts returns, so the field is descriptive — a schema constraint,
not a disclaimer — and the sentence saying so is in the field's own contract
rather than in whatever a model happens to narrate.

*It does not swap a unit to fill a slot.* The Main Source writes foreign buy,
sell and net **value**; no adapter writes foreign **volume**. So the
money-denominated ratio is served and the share-denominated one is registered
refused with its missing input named. Filling the second from the first is the
one substitution the money/quantity naming split exists to make impossible, and
it is asserted here rather than trusted.

*It does not present a room-capped flow as an ordinary one.* A statutory ceiling
stops buying mechanically, and a field that cannot tell that apart from a change
of view says which of the two the room permits.

The persistence threshold is frozen from a block permutation of the daily flows,
because a run length is exactly the statistic that looks impressive on serially
dependent noise. The derivation is re-measured in ``test_null_harness``; what is
pinned here is that the shipped constant is the one the field fires at.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import numpy as np
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
from src.stocks.providers import Exchange, ProviderSource
from src.stocks.providers.contracts import (
    Capability,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SnapshotMetadata,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.bars import Bar, BarFrame
from src.stocks.signals.fields import Claim, FieldKind, FieldWindow, Sign, Unit
from src.stocks.signals.foreign_flow import (
    FOREIGN_FLOW_SESSIONS,
    FOREIGN_PERSISTENCE_SESSIONS,
    PERSISTENCE_RUN_THRESHOLD,
    net_value_over_adtv_reading,
    net_volume_over_adtv_reading,
    persistence_run_days,
    persistence_run_days_reading,
)
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.nulls import (
    MATCHED_DAILY_VOLATILITIES,
    REFERENCE_HISTORIES,
    block_bootstrap_shapes,
    false_positive_rate,
    frames_from,
    gbm_shapes,
    reference_bar_history,
)
from src.stocks.signals.price_band import LimitLock
from src.stocks.signals.reference import (
    FOREIGN_ROOM_EXHAUSTED_SHARE,
    ForeignRoomStanding,
    foreign_room_on_or_before,
)
from src.stocks.signals.registry import (
    FOREIGN_FLOW_FIELDS,
    FOREIGN_FLOW_PERSISTENCE,
    FOREIGN_FLOW_PRESSURE,
    FOREIGN_FLOW_SHARE_PRESSURE,
    FOREIGN_ROOM_PCT,
    NULL_DERIVATION_SEED,
)
from src.stocks.signals.serving import serve_field
from src.stocks.universe import forget_cohort_cache

from .signal_windows import health_of, window_of
from .test_market_behavior import weekdays
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
        CohortVersion.__table__,
        CohortMember.__table__,
    ):
        table.create(engine)
    forget_cohort_cache()
    return Session(engine)


def bar_with_flow(day: date, flow: float | None, *, value: float = 10e9) -> Bar:
    return Bar(
        session_date=day,
        open=20_000.0,
        high=20_100.0,
        low=19_900.0,
        close=20_000.0,
        volume=800_000,
        total_value_vnd=value,
        adjustment_factor=Decimal(1),
        limit_lock=LimitLock.NONE,
        foreign_net_value_vnd=flow,
    )


def frame_of_flows(flows: list[float | None], *, value: float = 10e9) -> BarFrame:
    days = weekdays(len(flows))
    return BarFrame(
        symbol="AAA",
        bars=tuple(
            bar_with_flow(day, flow, value=value) for day, flow in zip(days, flows)
        ),
    )


def window_with_room(frame: BarFrame, room: ForeignRoomStanding | None) -> FieldWindow:
    return FieldWindow(frame=frame, health=health_of(frame), foreign_room=room)


def store_history(
    session: Session,
    sessions: int,
    *,
    symbol: str = "AAA",
    flow: float = 1e9,
) -> list[date]:
    list_on(session, symbol, Exchange.HOSE)
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
            total_value_vnd=10e9,
            foreign_net_value_vnd=flow,
        )
    return days


def store_room(
    session: Session,
    symbol: str,
    day: date,
    *,
    current: int | None,
    total: int | None,
) -> None:
    stamp = datetime.combine(day, time.min, tzinfo=VN_TZ)
    snapshot = ReferenceSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=stamp,
            observed_at=stamp,
        ),
        shares=(ShareCount(share_type=ShareType.LISTED, value=1_000_000),),
        current_foreign_room=current,
        total_foreign_room=total,
    )
    session.add(
        ProviderSnapshot(
            capability=Capability.REFERENCE.value,
            symbol=symbol,
            source=ProviderSource.VNSTOCK.value,
            schema_version=1,
            effective_at=stamp,
            observed_at=stamp,
            payload=snapshot.model_dump(mode="json"),
        )
    )
    session.flush()


class TestThePressureRatio:
    def test_it_is_money_over_money_and_says_so_on_both_sides(self):
        """A ratio whose two halves are in different units is not a ratio."""
        frame = frame_of_flows([1e9] * FOREIGN_FLOW_SESSIONS, value=10e9)

        reading = net_value_over_adtv_reading(window_of(frame))

        # Twenty sessions of one billion net, over ten billion of daily turnover.
        assert reading.value == pytest.approx(2.0)
        assert reading.extras["numerator_basis"] == "money"
        assert reading.extras["denominator_basis"] == "money"

    def test_positive_is_net_foreign_buying_and_the_sign_is_pinned(self):
        buying = net_value_over_adtv_reading(
            window_of(frame_of_flows([1e9] * FOREIGN_FLOW_SESSIONS))
        )
        selling = net_value_over_adtv_reading(
            window_of(frame_of_flows([-1e9] * FOREIGN_FLOW_SESSIONS))
        )

        assert buying.value > 0
        assert selling.value == pytest.approx(-buying.value)
        assert FOREIGN_FLOW_PRESSURE.sign is Sign.SIGNED

    def test_a_session_without_a_stored_flow_refuses_rather_than_summing_the_rest(self):
        flows: list[float | None] = [1e9] * FOREIGN_FLOW_SESSIONS
        flows[4] = None

        reading = net_value_over_adtv_reading(window_of(frame_of_flows(flows)))

        assert reading.value is None
        # Its own code: a window with a hole in its foreign split is a different
        # collection gap from a window that is simply too short.
        assert reading.refusal is SignalIssue.FOREIGN_FLOW_NOT_STORED

    def test_the_standard_error_corrects_for_the_persistence_it_measures(self):
        """An independent-observation error would understate a persistent flow.

        The same flows in the same order carry serial dependence the Newey-West
        estimate picks up; shuffled apart they do not. The corrected error is
        the larger of the two, which is the direction that matters.
        """
        persistent = [1e9 if index < 10 else -1e9 for index in range(FOREIGN_FLOW_SESSIONS)]
        alternating = [1e9 if index % 2 else -1e9 for index in range(FOREIGN_FLOW_SESSIONS)]

        run = net_value_over_adtv_reading(window_of(frame_of_flows(persistent)))
        flip = net_value_over_adtv_reading(window_of(frame_of_flows(alternating)))

        assert run.extras["standard_error_basis"] == "newey_west_bartlett"
        assert run.extras["standard_error"] > flip.extras["standard_error"]


class TestPersistenceRunLength:
    def test_it_counts_the_unbroken_run_ending_at_the_newest_session(self):
        flows = [-1e9] * (FOREIGN_PERSISTENCE_SESSIONS - 5) + [1e9] * 5

        assert persistence_run_days(frame_of_flows(flows)) == 5

    def test_a_session_of_exactly_no_net_flow_ends_a_run(self):
        """No foreign money moved is neither buying nor selling."""
        flows = [1e9] * (FOREIGN_PERSISTENCE_SESSIONS - 4) + [0.0, 1e9, 1e9, 1e9]

        assert persistence_run_days(frame_of_flows(flows)) == 3

    def test_a_newest_session_of_no_flow_is_a_run_of_none(self):
        flows = [1e9] * (FOREIGN_PERSISTENCE_SESSIONS - 1) + [0.0]

        assert persistence_run_days(frame_of_flows(flows)) == 0

    def test_the_direction_of_the_streak_travels_beside_its_length(self):
        """Fifteen sessions of selling and fifteen of buying are not one fact."""
        selling = persistence_run_days_reading(
            window_of(frame_of_flows([-1e9] * FOREIGN_PERSISTENCE_SESSIONS))
        )
        buying = persistence_run_days_reading(
            window_of(frame_of_flows([1e9] * FOREIGN_PERSISTENCE_SESSIONS))
        )

        assert selling.value == buying.value
        assert selling.extras["run_sign"] == -1
        assert buying.extras["run_sign"] == 1

    def test_it_fires_at_the_frozen_threshold_and_not_before(self):
        below = [-1e9] * 46 + [1e9] * 14
        at = [-1e9] * 45 + [1e9] * 15

        assert persistence_run_days(frame_of_flows(below)) < PERSISTENCE_RUN_THRESHOLD
        assert persistence_run_days(frame_of_flows(at)) >= PERSISTENCE_RUN_THRESHOLD
        assert FOREIGN_FLOW_PERSISTENCE.threshold is not None
        assert FOREIGN_FLOW_PERSISTENCE.threshold.value == PERSISTENCE_RUN_THRESHOLD


class TestTheBlockPermutationNull:
    def test_an_independent_flow_null_would_have_calibrated_this_wrongly(self):
        """Which is the whole argument for permuting blocks of a real flow.

        Under independently drawn flows a run is a coin landing the same way
        several times, and a threshold set from that null fires constantly once
        the flows have the persistence foreign flows actually have. Both rates
        are measured here at a fraction of the derivation's paths, so this
        checks the shape the frozen constant rests on rather than the constant.
        """
        rng = np.random.default_rng(NULL_DERIVATION_SEED)
        independent = frames_from(
            gbm_shapes(
                rng,
                paths=1200,
                sessions=FOREIGN_PERSISTENCE_SESSIONS,
                daily_volatility=MATCHED_DAILY_VOLATILITIES[1],
                truncated=True,
            )
        )
        history = reference_bar_history(rng)
        persistent = frames_from(
            block_bootstrap_shapes(
                rng, history, paths=1200, sessions=FOREIGN_PERSISTENCE_SESSIONS
            )
        )

        independent_runs = np.array(
            [persistence_run_days(frame) for frame in independent]
        )
        persistent_runs = np.array(
            [persistence_run_days(frame) for frame in persistent]
        )

        # The persistent null demands far more of the statistic than the
        # independent one does; a naive calibration would have shipped the
        # smaller number.
        assert np.quantile(persistent_runs, 0.99) > np.quantile(
            independent_runs, 0.99
        )

    def test_the_shipped_threshold_clears_the_ceiling_on_the_harder_null(self):
        rng = np.random.default_rng(NULL_DERIVATION_SEED)
        history = reference_bar_history(rng)
        frames = frames_from(
            block_bootstrap_shapes(
                rng,
                history,
                paths=REFERENCE_HISTORIES * 375,
                sessions=FOREIGN_PERSISTENCE_SESSIONS,
            )
        )

        rate = false_positive_rate(FOREIGN_FLOW_PERSISTENCE, frames)

        assert rate <= 0.01


class TestTheForeignRoom:
    def test_an_exhausted_room_degrades_the_reading_under_a_named_reason(self):
        """A flow that stopped because there was nothing left to buy.

        The number is real, so it is served; what changes is that it may not be
        read as a change of view.
        """
        frame = frame_of_flows([1e9] * FOREIGN_FLOW_SESSIONS)
        room = ForeignRoomStanding(
            symbol="AAA", current_room=0, total_room=1_000_000, as_of=date(2024, 2, 1)
        )

        reading = net_value_over_adtv_reading(window_with_room(frame, room))

        assert reading.value is not None
        assert reading.degraded_reason is SignalIssue.FOREIGN_ROOM_EXHAUSTED
        assert reading.extras["foreign_room_state"] == "exhausted"

    def test_a_room_down_to_its_last_fraction_counts_as_exhausted(self):
        """It stops buying as mechanically as a room at zero does."""
        nearly = ForeignRoomStanding(
            symbol="AAA",
            current_room=int(1_000_000 * FOREIGN_ROOM_EXHAUSTED_SHARE),
            total_room=1_000_000,
            as_of=date(2024, 2, 1),
        )
        open_room = ForeignRoomStanding(
            symbol="AAA", current_room=200_000, total_room=1_000_000, as_of=date(2024, 2, 1)
        )

        assert nearly.exhausted
        assert nearly.state == "exhausted"
        assert not open_room.exhausted
        assert open_room.state == "open"

    def test_an_uncollected_room_is_unknown_and_not_open(self):
        """Two different facts, and asserting the second from the first is wrong."""
        frame = frame_of_flows([1e9] * FOREIGN_FLOW_SESSIONS)

        reading = net_value_over_adtv_reading(window_with_room(frame, None))

        assert reading.extras["foreign_room_state"] == "unknown"
        assert reading.degraded_reason is None

    def test_the_room_is_read_as_it_stood_at_the_windows_own_cutoff(self):
        """A window answered for an old date must not acquire today's room."""
        with open_session() as session:
            days = store_history(session, 30)
            store_room(session, "AAA", days[5], current=500_000, total=1_000_000)
            store_room(session, "AAA", days[-1], current=0, total=1_000_000)

            early = foreign_room_on_or_before(session, "AAA", days[10])
            late = foreign_room_on_or_before(session, "AAA", days[-1])

        assert early is not None and early.current_room == 500_000
        assert late is not None and late.current_room == 0

    def test_a_symbol_with_no_stored_room_reads_as_none(self):
        with open_session() as session:
            days = store_history(session, 30)

            assert foreign_room_on_or_before(session, "AAA", days[-1]) is None


class TestTheForeignRoomPercentage:
    def test_it_is_served_because_its_inputs_are_stored(self):
        """The prerequisite list assumed it had none; the reference feed has them.

        Registering a refusal over data this system does collect would be the
        same dishonesty as substituting a live read for data it does not — the
        spec forbids fictionalising availability in either direction.
        """
        with open_session() as session:
            days = store_history(session, 30)
            store_room(session, "AAA", days[-1], current=250_000, total=1_000_000)

            value = serve_field(session, "AAA", FOREIGN_ROOM_PCT, end=days[-1])

        assert value.value == pytest.approx(25.0)
        assert value.extras["current_room_shares"] == 250_000
        assert value.extras["foreign_room_state"] == "open"
        assert value.degraded_reason is None

    def test_a_full_room_is_served_and_degraded(self):
        with open_session() as session:
            days = store_history(session, 30)
            store_room(session, "AAA", days[-1], current=0, total=1_000_000)

            value = serve_field(session, "AAA", FOREIGN_ROOM_PCT, end=days[-1])

        assert value.value == pytest.approx(0.0)
        assert value.degraded_reason is SignalIssue.FOREIGN_ROOM_EXHAUSTED

    def test_an_uncollected_room_refuses_rather_than_reporting_a_full_one(self):
        """Reporting 100% would assert the thing nobody looked at."""
        with open_session() as session:
            days = store_history(session, 30)

            value = serve_field(session, "AAA", FOREIGN_ROOM_PCT, end=days[-1])

        assert value.value is None
        assert value.refusal is SignalIssue.FOREIGN_ROOM_NOT_STORED
        assert value.extras["foreign_room_state"] == "unknown"


class TestTheShareDenominatedRatioIsRefused:
    def test_it_refuses_and_names_the_input_it_is_short_of(self):
        reading = net_volume_over_adtv_reading(
            window_of(frame_of_flows([1e9] * FOREIGN_FLOW_SESSIONS))
        )

        assert reading.value is None
        assert reading.refusal is SignalIssue.UNAVAILABLE
        assert "foreign traded volume" in reading.extras["missing_input"]

    def test_it_never_answers_with_the_money_ratio_instead(self):
        """The one substitution the money/quantity naming split exists to stop."""
        frame = frame_of_flows([1e9] * FOREIGN_FLOW_SESSIONS)

        money = net_value_over_adtv_reading(window_of(frame))
        shares = net_volume_over_adtv_reading(window_of(frame))

        assert money.value is not None
        assert shares.value is None
        assert shares.extras["available_instead"] == (
            "foreign_flow_pressure.net_value_over_adtv"
        )

    def test_no_adapter_in_this_system_writes_a_foreign_share_count(self):
        """The premise of the refusal, asserted rather than assumed.

        The snapshot contract declares the two fields; nothing populates them.
        The day something does, this test fails and the refusal above is the
        thing to revisit.
        """
        from src.stocks.providers import fiinquant, vnstock_provider

        for module in (fiinquant, vnstock_provider):
            with open(module.__file__, encoding="utf-8") as handle:
                text = handle.read()
            assert "foreign_buy_volume=" not in text
            assert "foreign_sell_volume=" not in text


class TestTheClusterContract:
    def test_every_field_is_descriptive_and_points_nowhere(self):
        for field in FOREIGN_FLOW_FIELDS:
            assert field.claim is Claim.DESCRIPTIVE

    def test_the_unverified_vietnamese_claim_is_in_the_contract(self):
        """The model reads the contract before it decides to call at all."""
        text = FOREIGN_FLOW_PRESSURE.interpretation.lower()

        assert "no verified published result" in text
        assert "positive means net foreign buying" in text

    def test_only_the_run_length_fires_and_it_carries_a_measured_null(self):
        firing = [field for field in FOREIGN_FLOW_FIELDS if field.fires]

        assert firing == [FOREIGN_FLOW_PERSISTENCE]
        assert FOREIGN_FLOW_PERSISTENCE.kind is FieldKind.SIGNAL
        assert FOREIGN_FLOW_PERSISTENCE.null_fpr is not None
        assert FOREIGN_FLOW_PERSISTENCE.null_fpr.paths >= 1000
        assert FOREIGN_FLOW_PERSISTENCE.unit is Unit.SESSIONS


class TestEveryFieldReachesBarsThroughTheGatewayAlone:
    def test_a_served_window_carries_its_health_and_its_room(self):
        with open_session() as session:
            days = store_history(session, 80)
            store_room(session, "AAA", days[-1], current=0, total=1_000_000)

            pressure = serve_field(session, "AAA", FOREIGN_FLOW_PRESSURE, end=days[-1])
            run = serve_field(session, "AAA", FOREIGN_FLOW_PERSISTENCE, end=days[-1])

        assert pressure.value == pytest.approx(2.0)
        assert pressure.health.sessions_used == FOREIGN_FLOW_SESSIONS
        assert pressure.degraded_reason is SignalIssue.FOREIGN_ROOM_EXHAUSTED
        assert run.value == FOREIGN_PERSISTENCE_SESSIONS
        assert run.fired

    def test_a_window_the_gateway_refuses_is_a_field_that_refuses(self):
        with open_session() as session:
            days = store_history(session, 10)

            value = serve_field(session, "AAA", FOREIGN_FLOW_PRESSURE, end=days[-1])

        assert value.value is None
        assert value.refusal is SignalIssue.INSUFFICIENT_HISTORY

    def test_the_refused_share_ratio_keeps_its_reason_through_serving(self):
        with open_session() as session:
            days = store_history(session, 30)

            value = serve_field(
                session, "AAA", FOREIGN_FLOW_SHARE_PRESSURE, end=days[-1]
            )

        assert value.value is None
        assert value.refusal is SignalIssue.UNAVAILABLE
        assert "foreign traded volume" in value.extras["missing_input"]
