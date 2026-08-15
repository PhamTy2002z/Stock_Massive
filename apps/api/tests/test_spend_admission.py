"""The committed reservation is the only route to the provider boundary."""

from datetime import date, datetime, timezone
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

    def reserve(self, candidate: SpendRequest, model: str) -> Reservation:
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
