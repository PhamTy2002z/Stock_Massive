"""The allowance an account reads is the allowance that refuses its next Turn.

Every test here exists to hold one property: the panel and the enforcement
measure the same thing. A reader that counted a different day, charged a
reservation differently, or added the prospective Turn would produce a number
that contradicts the refusal it exists to explain — and would do it silently,
because both numbers look plausible on their own.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.agent.usage import read_usage
from src.alpha.models import LlmCallUsage
from src.core.llm import OwnerType, UserCeilings, ict_day

# Mid-afternoon in Vietnam, which is the same calendar day in UTC. The tests
# that care about the day boundary choose their own moment.
NOW = datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def sessions():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LlmCallUsage.__table__.create(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def charge(
    sessions,
    *,
    user_id: int = 7,
    owner_id: str = "1",
    called_at: datetime = NOW,
    reserved: int = 1_000,
    actual: int | None = None,
    status: str | None = None,
    owner_type: str = OwnerType.TURN_REQUEST_MESSAGE.value,
) -> None:
    """One provider call in the ledger, priced the way admission prices one.

    ``status`` follows ``actual`` unless a test names it, because the ledger
    cannot hold the combination a free default would produce:
    ``admission.reconcile`` writes ``reconciled`` and ``actual_micro_usd`` in
    the same statement, so a reconciled row with no actual is a row no
    deployment has. Fixtures that invent one test the reader against data it
    will never see.
    """
    if status is None:
        status = "reserved" if actual is None else "reconciled"
    with sessions() as session:
        session.add(
            LlmCallUsage(
                owner_type=owner_type,
                owner_id=owner_id,
                user_id=user_id,
                lane="turn",
                route="test",
                model="session-model",
                pricing_version="v1",
                input_token_price_usd=0,
                cached_read_token_price_usd=0,
                cache_write_token_price_usd=0,
                output_token_price_usd=0,
                reserved_micro_usd=reserved,
                actual_micro_usd=actual,
                status=status,
                provider_called_at=called_at,
            )
        )
        session.commit()


def usage(sessions, *, now=NOW, ceilings=None, user_id=7):
    return asyncio.run(
        read_usage(
            user_id,
            now=now,
            ceilings=ceilings or UserCeilings(),
            session_factory=sessions,
        )
    )


class TestTurnCount:
    def test_counts_turns_not_provider_calls(self, sessions):
        """One Turn making four calls has spent one start, not four."""
        for index in range(4):
            charge(sessions, owner_id="turn-a", reserved=10)
        charge(sessions, owner_id="turn-b", reserved=10)

        assert usage(sessions).turns_today.used == 2

    def test_does_not_add_a_prospective_turn(self, sessions):
        """``_read_turn_state`` adds one because it is admitting one. This is not."""
        assert usage(sessions).turns_today.used == 0

        charge(sessions, owner_id="turn-a")
        assert usage(sessions).turns_today.used == 1

    def test_ignores_another_account(self, sessions):
        charge(sessions, user_id=99, owner_id="theirs")
        assert usage(sessions).turns_today.used == 0

    def test_ignores_owners_that_are_not_turns(self, sessions):
        """A capability probe is charged to the deployment, not to the reader."""
        charge(
            sessions,
            owner_id="probe-1",
            owner_type=OwnerType.CAPABILITY_PROBE.value,
        )
        assert usage(sessions).turns_today.used == 0


class TestTheDayBoundary:
    def test_uses_the_vietnamese_day_admission_uses(self, sessions):
        """23:30 UTC is already tomorrow in Vietnam, and must not count today."""
        now = datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc)
        day_start, _ = ict_day(now)

        charge(sessions, owner_id="before", called_at=day_start - timedelta(minutes=1))
        charge(sessions, owner_id="inside", called_at=day_start + timedelta(minutes=1))

        assert usage(sessions, now=now).turns_today.used == 1

    def test_resets_at_the_next_vietnamese_midnight(self, sessions):
        now = datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc)
        _, day_reset = ict_day(now)

        snapshot = usage(sessions, now=now)

        assert snapshot.turns_today.resets_at == day_reset
        assert snapshot.spend_today_micro_usd.resets_at == day_reset

    def test_a_day_resets_even_when_nothing_was_spent(self, sessions):
        """The reset is a property of the window, not of what went into it."""
        assert usage(sessions).turns_today.resets_at is not None


class TestSpend:
    def test_an_open_reservation_charges_its_worst_case(self, sessions):
        """Admission charges reserved until reconciled, so this must too."""
        charge(
            sessions,
            owner_id="open",
            reserved=5_000,
            actual=None,
            status="reserved",
        )
        assert usage(sessions).spend_today_micro_usd.used == 5_000

    def test_a_reconciled_call_charges_what_it_actually_cost(self, sessions):
        charge(
            sessions,
            owner_id="settled",
            reserved=5_000,
            actual=1_200,
            status="reconciled",
        )
        assert usage(sessions).spend_today_micro_usd.used == 1_200

    def test_the_configured_ceiling_arrives_in_the_ledgers_unit(self, sessions):
        snapshot = usage(sessions, ceilings=UserCeilings(daily_usd=3.0))
        assert snapshot.spend_today_micro_usd.limit == 3_000_000

    def test_a_ceiling_rounds_down_so_the_panel_promises_no_headroom(self, sessions):
        """Matching ``admission._micro_usd_ceiling``, which rounds down too."""
        snapshot = usage(sessions, ceilings=UserCeilings(daily_usd=0.0000015))
        assert snapshot.spend_today_micro_usd.limit == 1


class TestTheRollingWindow:
    def test_counts_thirty_days_back_and_no_further(self, sessions):
        charge(sessions, owner_id="old", called_at=NOW - timedelta(days=31), reserved=900)
        charge(sessions, owner_id="recent", called_at=NOW - timedelta(days=2), reserved=100)

        assert usage(sessions).spend_rolling_30d_micro_usd.used == 100

    def test_frees_when_the_oldest_charge_ages_out(self, sessions):
        oldest = NOW - timedelta(days=20)
        charge(sessions, owner_id="oldest", called_at=oldest)
        charge(sessions, owner_id="newer", called_at=NOW - timedelta(days=1))

        resets_at = usage(sessions).spend_rolling_30d_micro_usd.resets_at

        assert resets_at == oldest + timedelta(days=30)

    def test_an_empty_window_has_nothing_waiting_to_be_released(self, sessions):
        assert usage(sessions).spend_rolling_30d_micro_usd.resets_at is None


class TestAnUnlimitedCeiling:
    def test_is_carried_as_none_rather_than_zero(self, sessions):
        """Zero is a ceiling that refuses everything; unlimited refuses nothing."""
        snapshot = usage(
            sessions,
            ceilings=UserCeilings(
                turn_starts_per_day=None,
                daily_usd=None,
                rolling_30d_usd=None,
            ),
        )

        assert snapshot.turns_today.unlimited
        assert snapshot.spend_today_micro_usd.limit is None
        assert snapshot.spend_rolling_30d_micro_usd.limit is None

    def test_still_reports_what_was_consumed(self, sessions):
        """Turning a ceiling off drops the refusal, not the ledger."""
        charge(sessions, owner_id="turn-a", reserved=2_500)

        snapshot = usage(sessions, ceilings=UserCeilings(daily_usd=None))

        assert snapshot.spend_today_micro_usd.used == 2_500
        assert snapshot.spend_today_micro_usd.limit is None
