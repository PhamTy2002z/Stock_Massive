"""Admission decided before a Turn exists, and before any stream opens (#85).

``docs/adr/0013`` is explicit that a refusal is an ordinary HTTP response taken
*before* the ``EventSource`` connects.  That is the whole reason this check is
separate from :meth:`SpendAdmission.reserve`: the reservation is written
immediately before a network call and its existence *is* the fact that a Turn
dispatched, so using it to answer a ``POST`` would charge a start to a Turn the
same call is about to refuse.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from types import MappingProxyType

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.agent.admission import (
    ADMISSION_STATUS,
    TurnAdmission,
    TurnRefused,
)
from src.agent.loop import SessionSlots
from src.alpha.models import LlmCallUsage
from src.core.llm import (
    BudgetLanes,
    BudgetRefusal,
    LLMConfig,
    LLMRoute,
    PricingTable,
    SpendAdmission,
    TokenPrices,
    TurnState,
    Workload,
)

NOW = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)


def llm_config(**overrides) -> LLMConfig:
    base = LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://llm.example/v1", api_key="secret"),
        models=MappingProxyType(
            {Workload.BATCH: "batch-model", Workload.SESSION: "session-model"}
        ),
        pricing=PricingTable(
            version="2026-08",
            effective_from=date(2026, 8, 1),
            batch=TokenPrices(input=0.5, cached_input=0.1, cache_write=0.5, output=1.0),
            session=TokenPrices(input=2.0, cached_input=0.2, cache_write=2.0, output=5.0),
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=50,
            analysis_usd=10,
            turn_usd=30,
            emergency_usd=5,
            eval_usd=5,
        ),
    )
    return replace(base, **overrides) if overrides else base


def spend_admission(config: LLMConfig, state: TurnState) -> SpendAdmission:
    engine = create_engine("sqlite://")
    LlmCallUsage.__table__.create(engine)
    return SpendAdmission(
        config,
        sessionmaker(bind=engine, expire_on_commit=False),
        lambda: NOW,
        lambda *_: state,
    )


def admission(
    *,
    state: TurnState = TurnState(starts_today=1, active_for_user=0, active_system=0),
    config: LLMConfig | None = None,
    slots: SessionSlots | None = None,
) -> TurnAdmission:
    return TurnAdmission(
        spend_admission(config or llm_config(), state),
        slots=slots or SessionSlots(),
    )


class TestTheUserCeilings:
    def test_an_idle_user_inside_every_allowance_is_admitted(self):
        admission().admit(user_id=7)

    def test_a_user_already_holding_an_active_turn_is_refused(self):
        # The row for *this* Turn does not exist yet, so the ceiling is met at
        # the limit rather than past it. Comparing the way `reserve` does would
        # admit a second concurrent Turn for every user.
        with pytest.raises(TurnRefused) as refused:
            admission(
                state=TurnState(starts_today=1, active_for_user=1, active_system=1)
            ).admit(user_id=7)

        assert refused.value.reason == "user_active_turn"
        assert refused.value.status_code == 429

    def test_an_exhausted_daily_start_allowance_is_refused(self):
        with pytest.raises(TurnRefused) as refused:
            admission(
                state=TurnState(starts_today=21, active_for_user=0, active_system=0)
            ).admit(user_id=7)

        assert refused.value.reason == "user_turn_starts_daily"
        assert refused.value.status_code == 429
        # A user allowance resets; saying when is the difference between a rule
        # and an outage.
        assert refused.value.reset_at is not None


class TestTheServiceCeilings:
    def test_a_full_system_is_a_503_under_the_reason_admission_already_uses(self):
        with pytest.raises(TurnRefused) as refused:
            admission(
                state=TurnState(starts_today=1, active_for_user=0, active_system=3)
            ).admit(user_id=7)

        assert refused.value.reason == "system_active_turns"
        assert refused.value.status_code == 503

    def test_a_full_semaphore_is_refused_without_reading_the_ledger_at_all(self):
        # The in-process semaphore and the database count answer the same
        # question from two sides, and the route must not open a stream on a
        # Turn that would immediately meet a closed door.
        slots = SessionSlots(limit=1)

        async def occupy():
            async with slots.occupy():
                with pytest.raises(TurnRefused) as refused:
                    admission(slots=slots).admit(user_id=7)
                return refused.value

        import asyncio

        failure = asyncio.run(occupy())
        assert failure.reason == "system_active_turns"
        assert failure.status_code == 503

    def test_an_exhausted_lane_is_a_service_failure_rather_than_a_user_one(self):
        starved = llm_config(
            lanes=BudgetLanes(
                monthly_envelope_usd=50,
                analysis_usd=10,
                turn_usd=0.000001,
                emergency_usd=5,
                eval_usd=5,
            )
        )
        with pytest.raises(TurnRefused) as refused:
            admission(config=starved).admit(user_id=7)

        assert refused.value.reason == "lane_budget_exhausted"
        assert refused.value.status_code == 503


class TestTheStatusMapping:
    def test_every_reason_admission_can_raise_has_a_status(self):
        # A reason with no entry would fall through to a 500, which turns a
        # rule the user could act on into an outage they cannot.
        raised = {
            "user_turn_starts_daily",
            "user_active_turn",
            "user_spend_daily",
            "user_spend_rolling_30d",
            "system_active_turns",
            "lane_budget_exhausted",
        }
        assert raised <= set(ADMISSION_STATUS)

    def test_a_refusal_carries_the_ledgers_own_reason_unchanged(self):
        refusal = BudgetRefusal(
            "user_spend_daily",
            "Your daily generation allowance has been exhausted.",
            reset_at=NOW,
        )

        translated = TurnRefused.of(refusal)

        assert translated.reason == "user_spend_daily"
        assert translated.status_code == 429
        assert translated.message == refusal.message
        assert translated.reset_at == NOW
