"""What one account has consumed against its own ceilings.

The ceilings themselves are enforced in :mod:`src.core.llm.admission`, which
refuses a Turn and names the reason. This module answers the same question one
step earlier, for the account holder rather than the operator: a refusal that
arrives with no way to have seen it coming reads as a fault in the product.

Three allowances rather than five. ``active_turns_per_user`` and
``active_turns_system`` are momentary concurrency — they say "not right now",
never "not again today" — so they belong to the refusal that mentions them and
not to a panel about consumption. The two that remain unread here are read by
admission at the moment they bind.

**Counted the way admission counts, or not at all.** The daily window comes from
:func:`~src.core.llm.admission.ict_day` and the charge from the same
reserved-or-actual case expression, because a panel that measured either
differently would contradict the refusal it exists to explain. The one
deliberate difference is the candidate Turn: ``_read_turn_state`` adds the
prospective Turn to today's count because it is deciding whether to admit one,
and a reader that is not admitting anything must not.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.agent.persistence import SessionFactory
from src.alpha.models import LlmCallUsage
from src.core.database import sync_session_factory
from src.core.llm import OwnerType, UserCeilings, ict_day
from src.core.llm.config import llm_config_from_settings


@dataclass(frozen=True)
class Allowance:
    """One ceiling, what has gone against it, and when it next frees.

    ``limit is None`` is unlimited, which is a configured state rather than a
    missing value: a deployment on a subscription route sets every ceiling to
    zero, and the reader has to be able to say "no limit" instead of drawing a
    meter against nothing.

    ``resets_at is None`` means nothing is waiting to be released — an empty
    window, not an unknown one.
    """

    used: int
    limit: int | None
    resets_at: datetime | None

    @property
    def unlimited(self) -> bool:
        return self.limit is None


@dataclass(frozen=True)
class UsageSnapshot:
    """One account's consumption, as of ``as_of``.

    ``as_of`` is carried rather than left implicit because the daily figures are
    only true inside the Vietnamese day they were read in, and a client that
    cached this across midnight would otherwise have no way to notice.
    """

    as_of: datetime
    turns_today: Allowance
    spend_today_micro_usd: Allowance
    spend_rolling_30d_micro_usd: Allowance


def _charged() -> object:
    """Reserved until reconciled, actual afterwards — admission's own rule."""
    return case(
        (LlmCallUsage.status == "reconciled", LlmCallUsage.actual_micro_usd),
        else_=LlmCallUsage.reserved_micro_usd,
    )


def _micro_usd_ceiling(amount: float | None) -> int | None:
    """A configured USD ceiling in the ledger's integer unit, or unlimited.

    Rounded down, matching ``admission._micro_usd_ceiling``: the panel must not
    report headroom the enforcement will not fund.
    """
    if amount is None:
        return None
    return int(
        (Decimal(str(amount)) * Decimal(1_000_000)).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )


def _turn_window(session: Session, user_id: int, start: datetime, end: datetime) -> int:
    """Distinct Turns this account dispatched inside a window.

    Distinct owners rather than rows: one Turn makes several provider calls, and
    the allowance is spent per Turn. Over ``llm_call_usage`` rather than
    ``agent_turn`` for the reason ``_read_turn_state`` gives — a reservation row
    exists only once a Turn actually dispatched.
    """
    value = session.scalar(
        select(func.count(func.distinct(LlmCallUsage.owner_id))).where(
            LlmCallUsage.owner_type == OwnerType.TURN_REQUEST_MESSAGE.value,
            LlmCallUsage.user_id == user_id,
            LlmCallUsage.provider_called_at >= start,
            LlmCallUsage.provider_called_at < end,
        )
    )
    return int(value or 0)


def _spend_window(
    session: Session,
    user_id: int,
    start: datetime,
    end: datetime,
    *,
    start_exclusive: bool = False,
) -> int:
    lower = (
        LlmCallUsage.provider_called_at > start
        if start_exclusive
        else LlmCallUsage.provider_called_at >= start
    )
    value = session.scalar(
        select(func.coalesce(func.sum(_charged()), 0)).where(
            LlmCallUsage.owner_type == OwnerType.TURN_REQUEST_MESSAGE.value,
            LlmCallUsage.user_id == user_id,
            lower,
            LlmCallUsage.provider_called_at <= end,
        )
    )
    return int(value or 0)


def _oldest_charge_at(
    session: Session, user_id: int, start: datetime, end: datetime
) -> datetime | None:
    """When the rolling window's earliest charge landed.

    That charge plus thirty days is the first moment the window gives anything
    back, which is the only honest answer to "when does this free up" for a
    window that releases continuously rather than resetting.
    """
    value = session.scalar(
        select(func.min(LlmCallUsage.provider_called_at)).where(
            LlmCallUsage.owner_type == OwnerType.TURN_REQUEST_MESSAGE.value,
            LlmCallUsage.user_id == user_id,
            LlmCallUsage.provider_called_at > start,
            LlmCallUsage.provider_called_at <= end,
        )
    )
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _read(
    session_factory: SessionFactory,
    user_id: int,
    now: datetime,
    ceilings: UserCeilings,
) -> UsageSnapshot:
    day_start, day_reset = ict_day(now)
    rolling_start = now - timedelta(days=30)

    with session_factory() as session:
        turns = _turn_window(session, user_id, day_start, day_reset)
        spent_today = _spend_window(session, user_id, day_start, day_reset)
        spent_rolling = _spend_window(
            session, user_id, rolling_start, now, start_exclusive=True
        )
        oldest = _oldest_charge_at(session, user_id, rolling_start, now)

    return UsageSnapshot(
        as_of=now,
        turns_today=Allowance(
            used=turns,
            limit=ceilings.turn_starts_per_day,
            # A day always resets, whether or not anything was spent in it.
            resets_at=day_reset,
        ),
        spend_today_micro_usd=Allowance(
            used=spent_today,
            limit=_micro_usd_ceiling(ceilings.daily_usd),
            resets_at=day_reset,
        ),
        spend_rolling_30d_micro_usd=Allowance(
            used=spent_rolling,
            limit=_micro_usd_ceiling(ceilings.rolling_30d_usd),
            resets_at=None if oldest is None else oldest + timedelta(days=30),
        ),
    )


async def read_usage(
    user_id: int,
    *,
    now: datetime | None = None,
    ceilings: UserCeilings | None = None,
    session_factory: SessionFactory = sync_session_factory,
) -> UsageSnapshot:
    """This account's consumption against its ceilings.

    Off the event loop through ``asyncio.to_thread``, like every other read in
    this package: the ledger is reached over the synchronous engine, and the
    async pool is fifteen connections that the streaming endpoints need.
    """
    moment = now or datetime.now(timezone.utc)
    limits = ceilings if ceilings is not None else llm_config_from_settings().ceilings
    return await asyncio.to_thread(_read, session_factory, user_id, moment, limits)


__all__ = ["Allowance", "UsageSnapshot", "read_usage"]
