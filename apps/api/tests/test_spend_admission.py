"""The committed reservation is the only route to the provider boundary."""

import asyncio
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from types import MappingProxyType
from dataclasses import replace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.llm import (
    BudgetLane,
    CallOwner,
    Completion,
    CompletionRequest,
    MissingSpendReservation,
    ModelRefusal,
    GatewayTimeout,
    OwnerType,
    Reservation,
    ReservedLLMClient,
    Role,
    SpendRequest,
    SpendAdmission,
    BudgetLanes,
    BudgetRefusal,
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
    TurnState,
    Message,
    Usage,
    Workload,
)
from src.alpha.models import LlmCallUsage


def request() -> CompletionRequest:
    return CompletionRequest(
        model="session-model",
        messages=(Message(role=Role.USER, content="VCB?"),),
        max_output_tokens=200,
    )


def spend() -> SpendRequest:
    return SpendRequest(
        owner=CallOwner(OwnerType.TURN_REQUEST_MESSAGE, "42", user_id=7),
        lane=BudgetLane.TURN,
        workload=Workload.SESSION,
        input_tokens=1_000,
        output_tokens=200,
    )


def analysis_spend(
    *,
    owner_id: str = "run-1",
    input_tokens: int = 1_000,
    output_tokens: int = 200,
) -> SpendRequest:
    return SpendRequest(
        owner=CallOwner(OwnerType.ANALYSIS_RUN, owner_id),
        lane=BudgetLane.ANALYSIS,
        workload=Workload.BATCH,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


class RecordingAdmission:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.reconciled: Usage | None = None
        self.candidates: list[SpendRequest] = []

    def reserve(self, candidate: SpendRequest, model: str) -> Reservation:
        self.candidates.append(candidate)
        self.events.append("reservation_committed")
        return Reservation(
            id=91,
            owner=candidate.owner,
            lane=candidate.lane,
            model=model,
            reserved_micro_usd=400,
            provider_called_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        )

    def reconcile(self, reservation: Reservation, usage: Usage) -> None:
        self.events.append("reconciled")
        self.reconciled = usage


class RecordingTransport:
    def __init__(self, admission: RecordingAdmission) -> None:
        self.admission = admission
        self.calls = 0

    async def dispatch(self, completion_request: CompletionRequest) -> Completion:
        assert self.admission.events == ["reservation_committed"]
        self.admission.events.append("provider_dispatched")
        self.calls += 1
        return Completion(
            model=completion_request.model,
            text="flat",
            usage=Usage(input_tokens=800, output_tokens=120, reasoning_tokens=20),
        )


class TestReservedLLMClient:
    pytestmark = pytest.mark.asyncio

    async def test_a_committed_reservation_precedes_dispatch_and_usage_is_reconciled(
        self,
    ):
        admission = RecordingAdmission()
        transport = RecordingTransport(admission)
        client = ReservedLLMClient(transport, admission)

        result = await client.complete(request(), spend())

        assert result.text == "flat"
        assert admission.events == [
            "reservation_committed",
            "provider_dispatched",
            "reconciled",
        ]
        assert admission.reconciled == Usage(
            input_tokens=800,
            output_tokens=120,
            reasoning_tokens=20,
        )

    async def test_a_call_without_spend_identity_fails_before_dispatch(self):
        admission = RecordingAdmission()
        transport = RecordingTransport(admission)
        client = ReservedLLMClient(transport, admission)

        with pytest.raises(MissingSpendReservation):
            await client.complete(request())

        assert transport.calls == 0

    async def test_each_gateway_attempt_gets_its_own_reservation_and_retry_lane(self):
        admission = RecordingAdmission()

        class FlakyTransport:
            def __init__(self):
                self.calls = 0

            async def dispatch(self, completion_request):
                self.calls += 1
                if self.calls == 1:
                    raise GatewayTimeout("accepted but timed out")
                return Completion(model=completion_request.model, text="done")

        transport = FlakyTransport()
        client = ReservedLLMClient(transport, admission)

        result = await client.complete(request(), spend())

        assert result.text == "done"
        assert transport.calls == 2
        assert [candidate.lane for candidate in admission.candidates] == [
            BudgetLane.TURN,
            BudgetLane.EMERGENCY,
        ]


def llm_config() -> LLMConfig:
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://llm.example/v1", api_key="secret"),
        models=MappingProxyType(
            {Workload.BATCH: "batch-model", Workload.SESSION: "session-model"}
        ),
        pricing=PricingTable(
            version="2026-08",
            effective_from=date(2026, 8, 1),
            batch=TokenPrices(
                input=0.5, cached_input=0.1, cache_write=0.5, output=1.0
            ),
            session=TokenPrices(
                input=2.0, cached_input=0.2, cache_write=2.0, output=5.0
            ),
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=50,
            analysis_usd=10,
            turn_usd=30,
            emergency_usd=5,
            eval_usd=5,
        ),
    )


@pytest.fixture
def ledger():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LlmCallUsage.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    admission = SpendAdmission(
        llm_config(),
        session_factory=sessions,
        clock=lambda: datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc),
        turn_state_reader=lambda *_: TurnState(0, 1, 1),
    )
    return admission, sessions


class TestCommittedUsageLedger:
    def test_reservation_copies_prices_and_keeps_the_worst_case_charged(self, ledger):
        admission, sessions = ledger

        reservation = admission.reserve(spend(), model="session-model")

        with sessions() as session:
            row = session.scalar(
                select(LlmCallUsage).where(LlmCallUsage.id == reservation.id)
            )
            assert row is not None
            assert row.status == "usage_unknown"
            assert row.lane == "turn"
            assert row.user_id == 7
            assert row.reserved_input_tokens == 1_000
            assert row.reserved_output_tokens == 200
            assert row.pricing_version == "2026-08"
            assert float(row.input_token_price_usd) == 2.0
            assert float(row.output_token_price_usd) == 5.0
            assert row.reserved_micro_usd == 3_000

    def test_actual_usage_reconciles_without_double_counting_reasoning(self, ledger):
        admission, sessions = ledger
        reservation = admission.reserve(spend(), model="session-model")

        admission.reconcile(
            reservation,
            Usage(
                input_tokens=100,
                cached_input_tokens=50,
                cache_write_tokens=20,
                output_tokens=30,
                reasoning_tokens=10,
            ),
        )

        with sessions() as session:
            row = session.get(LlmCallUsage, reservation.id)
            assert row.status == "reconciled"
            assert row.input_tokens == 100
            assert row.cached_read_tokens == 50
            assert row.cache_write_tokens == 20
            assert row.output_tokens == 30
            assert row.reasoning_tokens == 10
            assert row.actual_micro_usd == 450

    def test_reservation_prices_input_at_the_cache_write_worst_case(self):
        config = replace(
            llm_config(),
            pricing=replace(
                llm_config().pricing,
                session=TokenPrices(
                    input=2,
                    cached_input=0.2,
                    cache_write=4,
                    output=5,
                ),
            ),
        )
        admission, _ = admission_with(config)

        reservation = admission.reserve(
            replace(spend(), input_tokens=1_000, output_tokens=0),
            "session-model",
        )

        assert reservation.reserved_micro_usd == 4_000


class TestAnalysisCeilings:
    def test_generation_input_ceiling_refuses_without_writing_a_reservation(
        self, ledger
    ):
        admission, sessions = ledger

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                analysis_spend(input_tokens=6_001), model="batch-model"
            )

        assert refused.value.reason == "analysis_input_per_call"
        assert refused.value.public()["state"] == "budget_exhausted"
        assert "usd" not in str(refused.value.public()).lower()
        with sessions() as session:
            assert session.scalar(select(LlmCallUsage)) is None

    def test_generation_output_ceiling_is_independent(self, ledger):
        admission, _ = ledger

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                analysis_spend(output_tokens=1_501), model="batch-model"
            )

        assert refused.value.reason == "analysis_output_per_call"

    def test_analysis_cost_ceiling_holds_across_attempts_for_one_owner(self, ledger):
        admission, sessions = ledger
        first = admission.reserve(
            analysis_spend(input_tokens=6_000, output_tokens=1_500),
            model="batch-model",
        )
        admission.reconcile(
            first,
            Usage(input_tokens=6_000, output_tokens=1_500),
        )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                analysis_spend(input_tokens=1), model="batch-model"
            )

        assert refused.value.reason == "analysis_cost"
        with sessions() as session:
            assert len(session.scalars(select(LlmCallUsage)).all()) == 1

    def test_another_analysis_owner_has_its_own_ceiling(self, ledger):
        admission, _ = ledger
        first = admission.reserve(
            analysis_spend(input_tokens=6_000, output_tokens=1_500),
            model="batch-model",
        )
        admission.reconcile(first, Usage(input_tokens=6_000, output_tokens=1_500))

        reservation = admission.reserve(
            analysis_spend(owner_id="run-2", input_tokens=1),
            model="batch-model",
        )

        assert reservation.owner.id == "run-2"


def reconcile_call(admission, candidate, usage):
    reservation = admission.reserve(candidate, model="session-model")
    admission.reconcile(reservation, usage)


class TestTurnCeilings:
    def test_constructed_context_is_capped_per_call(self, ledger):
        admission, _ = ledger

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(replace(spend(), input_tokens=32_001), "session-model")

        assert refused.value.reason == "turn_context_per_call"

    def test_aggregate_input_holds_across_calls_for_the_turn(self, ledger):
        admission, _ = ledger
        for _ in range(3):
            reconcile_call(
                admission,
                replace(spend(), input_tokens=32_000, output_tokens=0),
                Usage(input_tokens=32_000),
            )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                replace(spend(), input_tokens=4_001, output_tokens=0),
                "session-model",
            )

        assert refused.value.reason == "turn_input_total"

    def test_aggregate_output_includes_hidden_reasoning(self, ledger):
        admission, _ = ledger
        reconcile_call(
            admission,
            replace(spend(), input_tokens=0, output_tokens=20_000),
            Usage(output_tokens=15_000, reasoning_tokens=5_000),
        )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                replace(spend(), input_tokens=0, output_tokens=1),
                "session-model",
            )

        assert refused.value.reason == "turn_output_total"

    def test_monetary_ceiling_can_bind_before_either_token_total(self):
        expensive = llm_config()
        expensive = replace(
            expensive,
            pricing=replace(
                expensive.pricing,
                session=TokenPrices(
                    input=10,
                    cached_input=10,
                    cache_write=10,
                    output=10,
                ),
            ),
        )
        engine = create_engine("sqlite://")
        LlmCallUsage.__table__.create(engine)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        admission = SpendAdmission(
            expensive,
            sessions,
            lambda: datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc),
            lambda *_: TurnState(0, 1, 1),
        )
        reconcile_call(
            admission,
            replace(spend(), input_tokens=30_000, output_tokens=19_000),
            Usage(input_tokens=30_000, output_tokens=19_000),
        )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                replace(spend(), input_tokens=1_001, output_tokens=0),
                "session-model",
            )

        assert refused.value.reason == "turn_cost"


def admission_with(
    config,
    *,
    now=datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc),
    turn_state_reader=lambda *_: TurnState(0, 1, 1),
):
    engine = create_engine("sqlite://")
    LlmCallUsage.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    clock = now if callable(now) else lambda: now
    return SpendAdmission(config, sessions, clock, turn_state_reader), sessions


class TestBudgetLanes:
    def test_exhausting_analysis_does_not_block_the_turn_lane(self):
        config = replace(
            llm_config(),
            lanes=BudgetLanes(
                monthly_envelope_usd=40.001,
                analysis_usd=0.001,
                turn_usd=30,
                emergency_usd=5,
                eval_usd=5,
            ),
        )
        admission, _ = admission_with(config)
        admission.reserve(
            analysis_spend(input_tokens=1_000, output_tokens=200), "batch-model"
        )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                analysis_spend(owner_id="run-2", input_tokens=1_000),
                "batch-model",
            )
        turn_reservation = admission.reserve(spend(), "session-model")

        assert refused.value.reason == "lane_budget_exhausted"
        assert turn_reservation.lane is BudgetLane.TURN

    def test_eval_never_borrows_from_another_lane(self):
        config = replace(
            llm_config(),
            lanes=BudgetLanes(
                monthly_envelope_usd=45.000001,
                analysis_usd=10,
                turn_usd=30,
                emergency_usd=5,
                eval_usd=0.000001,
            ),
        )
        admission, _ = admission_with(config)
        candidate = SpendRequest(
            owner=CallOwner(OwnerType.EVAL_RUN, "eval-1"),
            lane=BudgetLane.EVAL,
            workload=Workload.SESSION,
            input_tokens=1,
            output_tokens=0,
        )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(candidate, "session-model")

        assert refused.value.reason == "lane_budget_exhausted"

    def test_seventy_percent_emits_an_operational_alert(self, caplog):
        config = replace(
            llm_config(),
            lanes=BudgetLanes(
                monthly_envelope_usd=40.001,
                analysis_usd=0.001,
                turn_usd=30,
                emergency_usd=5,
                eval_usd=5,
            ),
        )
        admission, _ = admission_with(config)

        admission.reserve(
            analysis_spend(input_tokens=1_000, output_tokens=200), "batch-model"
        )

        assert "analysis lane reached 70%" in caplog.text

    def test_cost_uses_the_ict_month_of_the_provider_call(self):
        config = replace(
            llm_config(),
            lanes=BudgetLanes(
                monthly_envelope_usd=40.001,
                analysis_usd=0.001,
                turn_usd=30,
                emergency_usd=5,
                eval_usd=5,
            ),
        )
        moments = [datetime(2026, 8, 31, 16, 59, tzinfo=timezone.utc)]
        admission, sessions = admission_with(config, now=lambda: moments[0])

        before = admission.reserve(
            analysis_spend(owner_id="aug", input_tokens=1_000, output_tokens=200),
            "batch-model",
        )
        moments[0] = datetime(2026, 8, 31, 17, 1, tzinfo=timezone.utc)
        after = admission.reserve(
            analysis_spend(owner_id="sep", input_tokens=1_000, output_tokens=200),
            "batch-model",
        )

        assert before.provider_called_at.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).month == 8
        assert after.provider_called_at.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).month == 9
        with sessions() as session:
            assert len(session.scalars(select(LlmCallUsage)).all()) == 2

    def test_timestamp_is_sampled_after_scope_locking_when_midnight_crosses(self):
        moments = iter(
            [
                datetime(2026, 8, 31, 16, 59, tzinfo=timezone.utc),
                datetime(2026, 8, 31, 17, 1, tzinfo=timezone.utc),
                datetime(2026, 8, 31, 17, 1, tzinfo=timezone.utc),
            ]
        )
        admission, _ = admission_with(llm_config(), now=lambda: next(moments))

        reservation = admission.reserve(
            analysis_spend(owner_id="crossing", input_tokens=1),
            "batch-model",
        )

        assert reservation.provider_called_at == datetime(
            2026, 8, 31, 17, 1, tzinfo=timezone.utc
        )

    def test_capability_probe_has_a_hard_daily_emergency_ceiling(self):
        expensive = replace(
            llm_config(),
            pricing=replace(
                llm_config().pricing,
                session=TokenPrices(10, 10, 10, 10),
            ),
        )
        admission, _ = admission_with(expensive)
        first = SpendRequest(
            owner=CallOwner(OwnerType.CAPABILITY_PROBE, "boot-1"),
            lane=BudgetLane.EMERGENCY,
            workload=Workload.SESSION,
            input_tokens=25_000,
            output_tokens=0,
        )
        admission.reserve(first, "session-model")

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                replace(
                    first,
                    owner=CallOwner(OwnerType.CAPABILITY_PROBE, "boot-2"),
                    input_tokens=1,
                ),
                "session-model",
            )

        assert refused.value.reason == "probe_budget_exhausted"


class TestPerUserCeilings:
    def test_twenty_first_turn_start_is_refused_until_the_next_ict_day(self):
        now = [datetime(2026, 8, 15, 16, 59, tzinfo=timezone.utc)]

        def turn_state(_session, _user_id, moment, _owner_id):
            starts = 21 if moment.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).day == 15 else 1
            return TurnState(starts_today=starts, active_for_user=1, active_system=1)

        admission, _ = admission_with(
            llm_config(), now=lambda: now[0], turn_state_reader=turn_state
        )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(spend(), "session-model")
        now[0] = datetime(2026, 8, 15, 17, 1, tzinfo=timezone.utc)
        reservation = admission.reserve(spend(), "session-model")

        assert refused.value.reason == "user_turn_starts_daily"
        assert refused.value.reset_at == datetime(
            2026, 8, 15, 17, 0, tzinfo=timezone.utc
        )
        assert reservation.id == 1

    @pytest.mark.parametrize(
        ("state", "reason"),
        [
            (TurnState(1, 2, 2), "user_active_turn"),
            (TurnState(1, 1, 4), "system_active_turns"),
        ],
    )
    def test_active_turn_limits_are_stable_refusals(self, state, reason):
        admission, _ = admission_with(
            llm_config(), turn_state_reader=lambda *_: state
        )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(spend(), "session-model")

        assert refused.value.reason == reason
        assert refused.value.public()["state"] == "capacity_exhausted"

    def test_daily_spend_resets_at_ict_midnight(self):
        expensive = replace(
            llm_config(),
            pricing=replace(
                llm_config().pricing,
                session=TokenPrices(10, 10, 10, 10),
            ),
        )
        now = [datetime(2026, 8, 15, 16, 59, tzinfo=timezone.utc)]
        admission, _ = admission_with(expensive, now=lambda: now[0])
        for owner in range(6):
            admission.reserve(
                replace(
                    spend(),
                    owner=CallOwner(
                        OwnerType.TURN_REQUEST_MESSAGE, str(owner), user_id=7
                    ),
                    input_tokens=30_000,
                    output_tokens=19_000,
                ),
                "session-model",
            )

        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                replace(
                    spend(),
                    owner=CallOwner(OwnerType.TURN_REQUEST_MESSAGE, "last", user_id=7),
                    input_tokens=7_000,
                    output_tokens=0,
                ),
                "session-model",
            )
        now[0] = datetime(2026, 8, 15, 17, 1, tzinfo=timezone.utc)
        next_day = admission.reserve(
            replace(
                spend(),
                owner=CallOwner(OwnerType.TURN_REQUEST_MESSAGE, "next", user_id=7),
                input_tokens=7_000,
                output_tokens=0,
            ),
            "session-model",
        )

        assert refused.value.reason == "user_spend_daily"
        assert next_day.owner.id == "next"

    def test_thirty_day_spend_rolls_instead_of_resetting_by_month(self):
        expensive = replace(
            llm_config(),
            pricing=replace(
                llm_config().pricing,
                session=TokenPrices(10, 10, 10, 10),
            ),
        )
        base = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)
        now = [base]
        admission, _ = admission_with(expensive, now=lambda: now[0])
        for index in range(30):
            now[0] = base + timedelta(days=index // 6)
            admission.reserve(
                replace(
                    spend(),
                    owner=CallOwner(
                        OwnerType.TURN_REQUEST_MESSAGE, str(index), user_id=7
                    ),
                    input_tokens=30_000,
                    output_tokens=19_000,
                ),
                "session-model",
            )

        now[0] = base + timedelta(days=5)
        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                replace(
                    spend(),
                    owner=CallOwner(OwnerType.TURN_REQUEST_MESSAGE, "30", user_id=7),
                    input_tokens=30_000,
                    output_tokens=19_000,
                ),
                "session-model",
            )

        now[0] = base + timedelta(days=35)
        after_window = admission.reserve(
            replace(
                spend(),
                owner=CallOwner(OwnerType.TURN_REQUEST_MESSAGE, "31", user_id=7),
                input_tokens=30_000,
                output_tokens=19_000,
            ),
            "session-model",
        )

        assert refused.value.reason == "user_spend_rolling_30d"
        assert refused.value.reset_at == base + timedelta(days=30)
        assert after_window.owner.id == "31"

    def test_rolling_reset_waits_until_enough_old_spend_has_expired(self):
        expensive = replace(
            llm_config(),
            pricing=replace(
                llm_config().pricing,
                session=TokenPrices(10, 10, 10, 10),
            ),
        )
        base = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)
        now = [base]
        admission, _ = admission_with(expensive, now=lambda: now[0])
        admission.reserve(
            replace(
                spend(),
                owner=CallOwner(OwnerType.TURN_REQUEST_MESSAGE, "small", user_id=7),
                input_tokens=10_000,
                output_tokens=0,
            ),
            "session-model",
        )
        for index in range(30):
            now[0] = base + timedelta(days=1 + index // 6)
            admission.reserve(
                replace(
                    spend(),
                    owner=CallOwner(
                        OwnerType.TURN_REQUEST_MESSAGE, f"large-{index}", user_id=7
                    ),
                    input_tokens=30_000,
                    output_tokens=19_000,
                ),
                "session-model",
            )

        now[0] = base + timedelta(days=6)
        with pytest.raises(BudgetRefusal) as refused:
            admission.reserve(
                replace(
                    spend(),
                    owner=CallOwner(
                        OwnerType.TURN_REQUEST_MESSAGE, "refused", user_id=7
                    ),
                    input_tokens=30_000,
                    output_tokens=19_000,
                ),
                "session-model",
            )

        assert refused.value.reason == "user_spend_rolling_30d"
        assert refused.value.reset_at == base + timedelta(days=31)


class FailingTransport:
    def __init__(self, failure: Exception) -> None:
        self.failure = failure

    async def dispatch(self, completion_request: CompletionRequest) -> Completion:
        raise self.failure


class TestFailedCalls:
    pytestmark = pytest.mark.asyncio

    async def test_provider_reported_usage_is_reconciled_even_when_the_call_fails(
        self, ledger
    ):
        admission, sessions = ledger
        client = ReservedLLMClient(
            FailingTransport(
                ModelRefusal(
                    "cannot answer",
                    usage=Usage(input_tokens=90, output_tokens=12, reasoning_tokens=8),
                )
            ),
            admission,
        )

        with pytest.raises(ModelRefusal):
            await client.complete(request(), spend())

        with sessions() as session:
            row = session.scalar(select(LlmCallUsage))
            assert row.status == "reconciled"
            assert row.actual_micro_usd == 280

    async def test_a_failure_without_usage_keeps_the_full_reservation_charged(
        self, ledger
    ):
        admission, sessions = ledger
        client = ReservedLLMClient(FailingTransport(GatewayTimeout("late")), admission)

        with pytest.raises(GatewayTimeout):
            await client.complete(request(), spend())

        with sessions() as session:
            row = session.scalar(select(LlmCallUsage))
            assert row.status == "usage_unknown"
            assert row.actual_micro_usd is None
            assert row.reserved_micro_usd == 3_000

    async def test_process_death_after_dispatch_leaves_usage_unknown(self, ledger):
        admission, sessions = ledger

        class ProcessDiesAfterDispatch:
            async def dispatch(self, completion_request):
                raise asyncio.CancelledError

        client = ReservedLLMClient(ProcessDiesAfterDispatch(), admission)

        with pytest.raises(asyncio.CancelledError):
            await client.complete(request(), spend())

        with sessions() as session:
            rows = session.scalars(select(LlmCallUsage)).all()
            assert len(rows) == 1
            assert rows[0].status == "usage_unknown"
            assert rows[0].reserved_micro_usd == 3_000

    async def test_success_without_provider_usage_keeps_the_reservation(self, ledger):
        admission, sessions = ledger

        class RouteOmitsUsage:
            async def dispatch(self, completion_request):
                return Completion(model=completion_request.model, text="done")

        client = ReservedLLMClient(RouteOmitsUsage(), admission)

        await client.complete(request(), spend())

        with sessions() as session:
            row = session.scalar(select(LlmCallUsage))
            assert row.status == "usage_unknown"
            assert row.actual_micro_usd is None
