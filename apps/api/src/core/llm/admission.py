"""Spend identities and the reservation handed to one provider dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from enum import Enum
import hashlib
import logging
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.alpha.models import (
    ACTIVE_TURN_STATUSES,
    AgentThread,
    AgentTurn,
    LlmCallUsage,
)

from .config import LLMConfig, TokenPrices, UserCeilings, Workload
from .protocol import Usage

logger = logging.getLogger(__name__)

# The historical ``analysis`` owner and lane names are reserved for offline
# batch/evaluation work. They remain stable ledger vocabulary until a dedicated
# compatibility change renames them; current chat execution uses the Turn lane.
#
# They are not unbounded, and that matters: an envelope that grew past what one
# generation can carry still arrives here reserved at its real size and is
# refused under ``analysis_input_per_call``, which is the only way that defect
# ever surfaces.
#
# The cost ceilings below are lifted on a deployment that declares no monthly
# lane (``_owner_cost_ceiling``), because what they protect is the lane. The two
# token bounds are not, for the reason in the paragraph above: on an unmetered
# route the loop is bounded by rounds and by these, and an oversized envelope
# still has to be caught by something.
ANALYSIS_INPUT_PER_CALL = 24_000
ANALYSIS_OUTPUT_PER_CALL = 3_000
# ``budget.ANALYSIS_COST_CEILING_USD`` in the ledger's own unit. One number in
# two places, and the test suite compares them rather than trusting the comment.
ANALYSIS_COST_MICRO_USD = 15_000
TURN_CONTEXT_PER_CALL = 32_000
TURN_INPUT_TOTAL = 100_000
TURN_OUTPUT_TOTAL = 20_000
TURN_COST_MICRO_USD = 500_000
# The five per-user ceilings live in ``UserCeilings`` (``config.py``) rather
# than here. They are the one group of ceilings a deployment legitimately
# changes without changing what the product promises, and each of them may be
# unlimited; the per-Turn and per-Analysis ceilings above are the contract and
# stay constants.
PROBE_DAILY_MICRO_USD = 250_000
ICT = ZoneInfo("Asia/Ho_Chi_Minh")


class BudgetLane(str, Enum):
    ANALYSIS = "analysis"
    TURN = "turn"
    EMERGENCY = "emergency"


class OwnerType(str, Enum):
    ANALYSIS_RUN = "analysis_run"
    TURN_REQUEST_MESSAGE = "turn_request_message"
    CAPABILITY_PROBE = "capability_probe"
    #: The golden harness's rubric pass. Out-of-band measurement of answers that
    #: have already been written, so it owns neither a Turn nor a probe.
    #:
    #: It has an owner of its own rather than borrowing one, and each of the two
    #: it could have borrowed says why. ``CAPABILITY_PROBE`` carries a hard
    #: $0.25 daily allowance shared with the boot probe: a judge pass over a
    #: forty-case corpus would exhaust it in a few calls *and* leave production
    #: unable to probe its own route on the next restart. ``TURN_REQUEST_MESSAGE``
    #: would put measurement spend inside the per-Turn ceilings and inside the
    #: rows a Turn's cost is read from, so measuring the system would change the
    #: number being measured.
    #:
    #: No ceiling branch below claims it: the harness enforces its own
    #: ``--judge-ceiling-usd`` per pass, and the lane envelope is the backstop.
    #: It rides the analysis lane, which the Phase 0 teardown left unused —
    #: out-of-band batch work belongs there rather than in the lane serving
    #: readers or the one held back for provider recovery.
    GOLDEN_JUDGE = "golden_judge"


@dataclass(frozen=True)
class CallOwner:
    """The durable artifact that owns exactly one provider call row."""

    type: OwnerType
    id: str
    user_id: int | None = None


@dataclass(frozen=True)
class SpendRequest:
    """The worst case a caller asks admission to fund."""

    owner: CallOwner
    lane: BudgetLane
    workload: Workload
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Reservation:
    """Proof that the worst case was committed before dispatch."""

    id: int
    owner: CallOwner
    lane: BudgetLane
    model: str
    reserved_micro_usd: int
    provider_called_at: datetime


@dataclass(frozen=True)
class TurnState:
    """Counts admission needs from the Turn lifecycle table."""

    starts_today: int
    active_for_user: int
    active_system: int


class BudgetRefusal(RuntimeError):
    """Stable branchable refusal, with a USD-free user representation."""

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        state: str = "budget_exhausted",
        reset_at: datetime | None = None,
        operator_detail: str = "",
    ) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason
        # Kept beside the joined ``args[0]`` rather than only inside it: the
        # transport answers a refusal with ``{reason, message}``, and a caller
        # forced to split the exception's text back into halves would be parsing
        # the one part that is allowed to change.
        self.message = message
        self.state = state
        self.reset_at = reset_at
        self.operator_detail = operator_detail

    def public(self) -> dict[str, str | None]:
        return {
            "reason": self.reason,
            "state": self.state,
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
        }


#: Every reason a :class:`BudgetRefusal` can carry, as one closed set.
#:
#: The agent loop turns a refusal into a Turn's ``terminal_reason`` and ends the
#: Turn where it is, so a caller holding only the finished Turn has a *string*
#: and no exception to catch. Matching that string against a literal it chose
#: itself is how a caller comes to recognise one refusal and sail past the rest,
#: which is how a caller comes to treat an exhausted lane as a result rather
#: than a stop.
#:
#: Kept beside the refusals rather than at the reading end, and pinned by a test
#: that scans this module for every reason actually raised — a set maintained by
#: hand at a distance is the same failure one indirection later.
BUDGET_REFUSAL_REASONS: frozenset[str] = frozenset(
    {
        "analysis_cost",
        "analysis_input_per_call",
        "analysis_output_per_call",
        "lane_budget_exhausted",
        "probe_budget_exhausted",
        "system_active_turns",
        "turn_context_per_call",
        "turn_cost",
        "turn_input_total",
        "turn_output_total",
        "user_active_turn",
        "user_spend_daily",
        "user_spend_rolling_30d",
        "user_turn_starts_daily",
    }
)


class AdmissionLedger(Protocol):
    """The transaction owner used by the guarded client."""

    def reserve(self, candidate: SpendRequest, model: str) -> Reservation: ...

    def reconcile(self, reservation: Reservation, usage: Usage) -> None: ...


class SpendAdmission:
    """Own the short reservation and reconciliation transactions."""

    def __init__(
        self,
        config: LLMConfig,
        session_factory: Callable[[], Session],
        clock: Callable[[], datetime],
        turn_state_reader: Callable[[Session, int, datetime, str], TurnState]
        | None = None,
    ) -> None:
        self._config = config
        self._session_factory = session_factory
        self._clock = clock
        self._turn_state_reader = turn_state_reader or _read_turn_state

    def reserve(self, candidate: SpendRequest, model: str) -> Reservation:
        expected_model = self._config.model_for(candidate.workload)
        if model != expected_model:
            raise ValueError(
                f"model {model!r} is not the configured {candidate.workload.value} model"
            )
        if candidate.input_tokens < 0 or candidate.output_tokens < 0:
            raise ValueError("a worst-case token count cannot be negative")

        check_candidate_shape(candidate)

        called_at = self._clock()
        prices = self._config.prices_for(candidate.workload)
        reserved = _micro_usd(
            TokenPrices(
                input=prices.worst_case_input,
                cached_input=prices.cached_input,
                cache_write=prices.cache_write,
                output=prices.output,
            ),
            input_tokens=candidate.input_tokens,
            output_tokens=candidate.output_tokens,
        )

        session = self._session_factory()
        try:
            with session.begin():
                while True:
                    month_start, month_reset = _ict_month(called_at)
                    day_start, day_reset = ict_day(called_at)
                    scopes = [
                        f"lane:{candidate.lane.value}:{month_start.isoformat()}",
                        f"owner:{candidate.owner.type.value}:{candidate.owner.id}",
                    ]
                    if candidate.owner.user_id is not None:
                        scopes.extend(
                            [
                                f"user-day:{candidate.owner.user_id}:{day_start.isoformat()}",
                                f"user-rolling:{candidate.owner.user_id}",
                                f"turn-active-user:{candidate.owner.user_id}",
                                "turn-active-system",
                            ]
                        )
                    if candidate.owner.type is OwnerType.CAPABILITY_PROBE:
                        scopes.append(f"probe-day:{day_start.isoformat()}")
                    _lock_scopes(session, scopes)

                    # The timestamp is sampled after any lock wait, immediately
                    # before the row is written and committed for dispatch. If
                    # that wait crossed an ICT boundary, lock the new scopes as
                    # well and evaluate only against the real call period.
                    dispatch_at = self._clock()
                    if (
                        _ict_month(dispatch_at)[0] == month_start
                        and ict_day(dispatch_at)[0] == day_start
                    ):
                        called_at = dispatch_at
                        break
                    called_at = dispatch_at
                lane_spent, lane_limit = _assert_lane_headroom(
                    session,
                    config=self._config,
                    lane=candidate.lane,
                    reserved=reserved,
                    month_start=month_start,
                    month_reset=month_reset,
                )
                if candidate.owner.type is OwnerType.CAPABILITY_PROBE:
                    probe_spent = _charged_cost(
                        session,
                        LlmCallUsage.owner_type == OwnerType.CAPABILITY_PROBE.value,
                        LlmCallUsage.provider_called_at >= day_start,
                        LlmCallUsage.provider_called_at < day_reset,
                    )
                    if probe_spent + reserved > PROBE_DAILY_MICRO_USD:
                        raise BudgetRefusal(
                            "probe_budget_exhausted",
                            "The Capability Probe allowance is exhausted.",
                            reset_at=day_reset,
                            operator_detail=(
                                f"Capability Probe has {probe_spent} micro-USD "
                                f"charged today and requested {reserved} more"
                            ),
                        )
                if candidate.owner.type is OwnerType.ANALYSIS_RUN:
                    owner_cost = _owner_cost(session, candidate.owner)
                    ceiling = _owner_cost_ceiling(
                        self._config, ANALYSIS_COST_MICRO_USD
                    )
                    if owner_cost + reserved > ceiling:
                        raise BudgetRefusal(
                            "analysis_cost",
                            "This Analysis has exhausted its generation allowance.",
                            operator_detail=(
                                f"owner {candidate.owner.id} has {owner_cost} micro-USD "
                                f"charged and requested {reserved} more"
                            ),
                        )
                elif candidate.owner.type is OwnerType.TURN_REQUEST_MESSAGE:
                    owner_cost, owner_input, owner_output = _owner_totals(
                        session,
                        candidate.owner,
                    )
                    if owner_input + candidate.input_tokens > TURN_INPUT_TOTAL:
                        raise BudgetRefusal(
                            "turn_input_total",
                            "This Turn has exhausted its aggregate input allowance.",
                        )
                    if owner_output + candidate.output_tokens > TURN_OUTPUT_TOTAL:
                        raise BudgetRefusal(
                            "turn_output_total",
                            "This Turn has exhausted its aggregate output allowance.",
                        )
                    ceiling = _owner_cost_ceiling(self._config, TURN_COST_MICRO_USD)
                    if owner_cost + reserved > ceiling:
                        raise BudgetRefusal(
                            "turn_cost",
                            "This Turn has exhausted its generation allowance.",
                            operator_detail=(
                                f"owner {candidate.owner.id} has {owner_cost} micro-USD "
                                f"charged and requested {reserved} more"
                            ),
                        )
                    if candidate.owner.user_id is None:
                        raise ValueError("a Turn spend owner requires user_id")
                    self._check_user(
                        session,
                        candidate,
                        reserved,
                        called_at,
                        day_start,
                        day_reset,
                    )
                row = LlmCallUsage(
                    owner_type=candidate.owner.type.value,
                    owner_id=candidate.owner.id,
                    user_id=candidate.owner.user_id,
                    lane=candidate.lane.value,
                    route=self._config.route.base_url,
                    model=model,
                    reserved_input_tokens=candidate.input_tokens,
                    reserved_output_tokens=candidate.output_tokens,
                    pricing_version=self._config.pricing.version,
                    input_token_price_usd=Decimal(str(prices.input)),
                    cached_read_token_price_usd=Decimal(str(prices.cached_input)),
                    cache_write_token_price_usd=Decimal(str(prices.cache_write)),
                    output_token_price_usd=Decimal(str(prices.output)),
                    reserved_micro_usd=reserved,
                    status="usage_unknown",
                    provider_called_at=called_at,
                )
                session.add(row)
                session.flush()
                utilization = (lane_spent + reserved) / lane_limit
                if utilization >= 0.70:
                    logger.warning(
                        "%s lane reached %.0f%% of its monthly budget",
                        candidate.lane.value,
                        utilization * 100,
                    )
                reservation = Reservation(
                    id=row.id,
                    owner=candidate.owner,
                    lane=candidate.lane,
                    model=model,
                    reserved_micro_usd=reserved,
                    provider_called_at=called_at,
                )
            return reservation
        finally:
            session.close()

    def preflight_turn(self, user_id: int, *, output_tokens: int) -> None:
        """Would this user's next Turn be able to fund its first call?

        Read-only, writes nothing, and takes no advisory lock. That is not an
        oversight — it is the difference between this and :meth:`reserve`. A
        reservation row is written immediately before the network call and its
        existence *is* the fact that a Turn dispatched, so answering
        a ``POST`` from one would charge a start to the very Turn it is about to
        refuse.

        :meth:`reserve` stays the authority. This is the same set of ceilings
        asked early enough to be an ordinary HTTP status, which is what the
        transport requires of admission: a refusal must be decided before any
        stream opens, never delivered as an in-band event.

        The headroom checked is one call at the Turn's own per-call ceiling —
        exactly what the loop's first :meth:`reserve` will ask for at worst.
        Admitting a Turn that cannot fund even that produces an ``incomplete``
        with nothing in it, which a reader cannot tell from a fault.
        """
        called_at = self._clock()
        day_start, day_reset = ict_day(called_at)
        month_start, month_reset = _ict_month(called_at)
        prices = self._config.prices_for(Workload.SESSION)
        reserved = _micro_usd(
            TokenPrices(
                input=prices.worst_case_input,
                cached_input=prices.cached_input,
                cache_write=prices.cache_write,
                output=prices.output,
            ),
            input_tokens=TURN_CONTEXT_PER_CALL,
            output_tokens=output_tokens,
        )

        session = self._session_factory()
        try:
            _assert_lane_headroom(
                session,
                config=self._config,
                lane=BudgetLane.TURN,
                reserved=reserved,
                month_start=month_start,
                month_reset=month_reset,
            )
            # The candidate's own owner id does not exist yet, so nothing is
            # excluded and nothing is added back: ``starts_today`` already
            # counts this prospective Turn, and the two active counts do not —
            # which is what ``pending=1`` says.
            _assert_user_ceilings(
                session,
                state=self._turn_state_reader(session, user_id, called_at, ""),
                ceilings=self._config.ceilings,
                user_id=user_id,
                reserved=reserved,
                called_at=called_at,
                day_start=day_start,
                day_reset=day_reset,
                pending=1,
            )
        finally:
            session.close()

    def _check_user(
        self,
        session: Session,
        candidate: SpendRequest,
        reserved: int,
        called_at: datetime,
        day_start: datetime,
        day_reset: datetime,
    ) -> None:
        user_id = candidate.owner.user_id
        assert user_id is not None
        # ``pending=0``: this Turn's ``agent_turn`` row was committed before
        # execution began, so the active counts already include it.
        _assert_user_ceilings(
            session,
            state=self._turn_state_reader(
                session,
                user_id,
                called_at,
                candidate.owner.id,
            ),
            ceilings=self._config.ceilings,
            user_id=user_id,
            reserved=reserved,
            called_at=called_at,
            day_start=day_start,
            day_reset=day_reset,
            pending=0,
        )

    def reconcile(self, reservation: Reservation, usage: Usage) -> None:
        session = self._session_factory()
        try:
            with session.begin():
                row = session.get(LlmCallUsage, reservation.id, with_for_update=True)
                if row is None:
                    raise LookupError(f"reservation {reservation.id} no longer exists")
                prices = TokenPrices(
                    input=float(row.input_token_price_usd),
                    cached_input=float(row.cached_read_token_price_usd),
                    cache_write=float(row.cache_write_token_price_usd),
                    output=float(row.output_token_price_usd),
                )
                row.input_tokens = usage.input_tokens
                row.cached_read_tokens = usage.cached_input_tokens
                row.cache_write_tokens = usage.cache_write_tokens
                row.output_tokens = usage.output_tokens
                row.reasoning_tokens = usage.reasoning_tokens
                row.actual_micro_usd = _micro_usd(
                    prices,
                    input_tokens=usage.input_tokens,
                    cached_input_tokens=usage.cached_input_tokens,
                    cache_write_tokens=usage.cache_write_tokens,
                    output_tokens=usage.output_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                )
                row.status = "reconciled"
                row.reconciled_at = self._clock()
        finally:
            session.close()


def _assert_lane_headroom(
    session: Session,
    *,
    config: LLMConfig,
    lane: BudgetLane,
    reserved: int,
    month_start: datetime,
    month_reset: datetime,
) -> tuple[int, int | float]:
    """The lane's monthly ceiling, asked once for both callers.

    :meth:`SpendAdmission.reserve` asks it under an advisory lock immediately
    before writing a row; :meth:`SpendAdmission.preflight_turn` asks it with no
    lock at all, because it writes nothing. The *question* is the same one, and
    two copies of it would be two places to edit a ceiling and one place to
    forget — which would make the ``POST`` admit exactly what dispatch refuses.
    """
    limit = _lane_limit_micro_usd(config, lane)
    spent = _charged_cost(
        session,
        LlmCallUsage.lane == lane.value,
        LlmCallUsage.provider_called_at >= month_start,
        LlmCallUsage.provider_called_at < month_reset,
    )
    if spent + reserved > limit:
        raise BudgetRefusal(
            "lane_budget_exhausted",
            "This service lane is unavailable until its allowance resets.",
            reset_at=month_reset,
            operator_detail=(
                f"{lane.value} lane has {spent} micro-USD charged against "
                f"{limit}; this request needs {reserved}"
            ),
        )
    return spent, limit


def _assert_user_ceilings(
    session: Session,
    *,
    state: TurnState,
    ceilings: UserCeilings,
    user_id: int,
    reserved: int,
    called_at: datetime,
    day_start: datetime,
    day_reset: datetime,
    pending: int,
) -> None:
    """The five per-user spend ceilings, in one place.

    Asked twice with one difference. At admission no ``agent_turn`` row exists
    yet, so the prospective Turn has to be added to the two active counts;
    at reservation the row was committed before execution began, so it is
    already in them. ``pending`` is that difference, and making it a parameter
    is what keeps the two paths from drifting into disagreeing about who may
    start a Turn — an admission that let through what dispatch then refused
    would produce an ``incomplete`` Turn with nothing in it.

    A ceiling left unlimited is not asked at all, and the two monetary ones do
    not even run their query. That is the point of asking here rather than
    inside ``_charged_cost``: an unlimited ceiling should cost nothing per call,
    not a scan whose answer is then discarded.
    """
    if (
        ceilings.turn_starts_per_day is not None
        and state.starts_today > ceilings.turn_starts_per_day
    ):
        raise BudgetRefusal(
            "user_turn_starts_daily",
            "Your daily Turn allowance has been exhausted.",
            reset_at=day_reset,
        )
    if (
        ceilings.active_turns_per_user is not None
        and state.active_for_user + pending > ceilings.active_turns_per_user
    ):
        raise BudgetRefusal(
            "user_active_turn",
            "Another Turn is already active for this account.",
            state="capacity_exhausted",
        )
    if (
        ceilings.active_turns_system is not None
        and state.active_system + pending > ceilings.active_turns_system
    ):
        raise BudgetRefusal(
            "system_active_turns",
            "The service is at its active Turn capacity.",
            state="capacity_exhausted",
        )

    daily_ceiling = _micro_usd_ceiling(ceilings.daily_usd)
    if daily_ceiling is not None:
        daily = _charged_cost(
            session,
            LlmCallUsage.user_id == user_id,
            LlmCallUsage.owner_type == OwnerType.TURN_REQUEST_MESSAGE.value,
            LlmCallUsage.provider_called_at >= day_start,
            LlmCallUsage.provider_called_at < day_reset,
        )
        if daily + reserved > daily_ceiling:
            raise BudgetRefusal(
                "user_spend_daily",
                "Your daily generation allowance has been exhausted.",
                reset_at=day_reset,
                operator_detail=(
                    f"user {user_id} has {daily} micro-USD charged today and "
                    f"this request needs {reserved}"
                ),
            )

    rolling_ceiling = _micro_usd_ceiling(ceilings.rolling_30d_usd)
    if rolling_ceiling is not None:
        rolling_start = called_at - timedelta(days=30)
        rolling = _charged_cost(
            session,
            LlmCallUsage.user_id == user_id,
            LlmCallUsage.owner_type == OwnerType.TURN_REQUEST_MESSAGE.value,
            LlmCallUsage.provider_called_at > rolling_start,
            LlmCallUsage.provider_called_at <= called_at,
        )
        if rolling + reserved > rolling_ceiling:
            raise BudgetRefusal(
                "user_spend_rolling_30d",
                "Your rolling generation allowance has been exhausted.",
                reset_at=_rolling_reset_at(
                    session,
                    user_id=user_id,
                    rolling_start=rolling_start,
                    called_at=called_at,
                    amount_to_release=rolling + reserved - rolling_ceiling,
                ),
                operator_detail=(
                    f"user {user_id} has {rolling} micro-USD charged in 30 days "
                    f"and this request needs {reserved}"
                ),
            )


def _micro_usd(
    prices: TokenPrices,
    *,
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> int:
    """Price in the ledger's integer unit, rounding upward conservatively."""
    amount = (
        Decimal(input_tokens) * Decimal(str(prices.input))
        + Decimal(cached_input_tokens) * Decimal(str(prices.cached_input))
        + Decimal(cache_write_tokens) * Decimal(str(prices.cache_write))
        + Decimal(output_tokens + reasoning_tokens) * Decimal(str(prices.output))
    )
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def check_candidate_shape(candidate: SpendRequest) -> None:
    """The per-call ceilings, which depend on what kind of artifact is paying.

    Public because a caller that redirects the owner of a call still owes the
    ceilings of the work that produced it: asked here, on the spend the
    production path built, the answer does not depend on whose name the row
    ends up carrying.
    """
    if candidate.owner.type is OwnerType.ANALYSIS_RUN:
        if candidate.input_tokens > ANALYSIS_INPUT_PER_CALL:
            raise BudgetRefusal(
                "analysis_input_per_call",
                "This Analysis generation has exhausted its input allowance.",
            )
        if candidate.output_tokens > ANALYSIS_OUTPUT_PER_CALL:
            raise BudgetRefusal(
                "analysis_output_per_call",
                "This Analysis generation has exhausted its output allowance.",
            )
    elif candidate.owner.type is OwnerType.TURN_REQUEST_MESSAGE:
        if candidate.input_tokens > TURN_CONTEXT_PER_CALL:
            raise BudgetRefusal(
                "turn_context_per_call",
                "This Turn call has exhausted its constructed-context allowance.",
            )


def _charged_cost(session: Session, *conditions: object) -> int:
    charged = _charged_cost_expression()
    value = session.scalar(select(func.coalesce(func.sum(charged), 0)).where(*conditions))
    return int(value or 0)


def _owner_cost(session: Session, owner: CallOwner) -> int:
    """What this one owner has already been charged, across every lane.

    Across every lane deliberately: a retried call is re-reserved against
    ``emergency`` (see ``client.py``), and an owner ceiling that counted only
    its own lane would let a retry storm walk past the ceiling it exists to be.
    """
    return _charged_cost(
        session,
        LlmCallUsage.owner_type == owner.type.value,
        LlmCallUsage.owner_id == owner.id,
    )


def _owner_totals(session: Session, owner: CallOwner) -> tuple[int, int, int]:
    charged_cost = _charged_cost_expression()
    charged_input = case(
        (
            LlmCallUsage.status == "reconciled",
            LlmCallUsage.input_tokens
            + LlmCallUsage.cached_read_tokens
            + LlmCallUsage.cache_write_tokens,
        ),
        else_=LlmCallUsage.reserved_input_tokens,
    )
    charged_output = case(
        (
            LlmCallUsage.status == "reconciled",
            LlmCallUsage.output_tokens + LlmCallUsage.reasoning_tokens,
        ),
        else_=LlmCallUsage.reserved_output_tokens,
    )
    row = session.execute(
        select(
            func.coalesce(func.sum(charged_cost), 0),
            func.coalesce(func.sum(charged_input), 0),
            func.coalesce(func.sum(charged_output), 0),
        ).where(
            LlmCallUsage.owner_type == owner.type.value,
            LlmCallUsage.owner_id == owner.id,
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)


def _charged_cost_expression():
    return case(
        (LlmCallUsage.status == "reconciled", LlmCallUsage.actual_micro_usd),
        else_=LlmCallUsage.reserved_micro_usd,
    )


def _rolling_reset_at(
    session: Session,
    *,
    user_id: int,
    rolling_start: datetime,
    called_at: datetime,
    amount_to_release: int,
) -> datetime | None:
    rows = session.execute(
        select(
            LlmCallUsage.provider_called_at,
            _charged_cost_expression(),
        )
        .where(
            LlmCallUsage.user_id == user_id,
            LlmCallUsage.owner_type == OwnerType.TURN_REQUEST_MESSAGE.value,
            LlmCallUsage.provider_called_at > rolling_start,
            LlmCallUsage.provider_called_at <= called_at,
        )
        .order_by(LlmCallUsage.provider_called_at, LlmCallUsage.id)
    ).all()
    released = 0
    for provider_called_at, charged in rows:
        released += int(charged or 0)
        if released >= amount_to_release:
            return _aware(provider_called_at) + timedelta(days=30)
    return None


def _lock_scopes(session: Session, scopes: list[str]) -> None:
    """Serialize every absent-or-present scope without a sentinel table."""
    if session.get_bind().dialect.name != "postgresql":
        return
    for scope in sorted(set(scopes)):
        key = int.from_bytes(
            hashlib.blake2b(scope.encode(), digest_size=8).digest(),
            byteorder="big",
            signed=True,
        )
        session.execute(select(func.pg_advisory_xact_lock(key)))


def _micro_usd_ceiling(amount: float | None) -> int | None:
    """A configured USD ceiling in the ledger's integer unit, or unlimited.

    Rounded *down* where a reservation is rounded up: a ceiling is the most that
    may be spent, so rounding it outward would fund a call the configuration
    did not.
    """
    if amount is None:
        return None
    return int(
        (Decimal(str(amount)) * Decimal(1_000_000)).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )


def _owner_cost_ceiling(config: LLMConfig, metered: int) -> int | float:
    """One owner's cost ceiling, or ``inf`` when the deployment is unmetered.

    The per-owner cost ceilings exist to protect the *monthly lane*: the $0.015
    Analysis figure was arrived at by pricing an internal cohort of thirty
    symbols at about $9.45 against the $10 lane. A deployment that declares no
    lane has nothing for them to protect, so they come off with it, exactly as
    :func:`_lane_limit_micro_usd` does.

    The **token** ceilings beside them do not, and the difference is the point.
    ``analysis_input_per_call`` is not a budget: it is the only way an envelope
    that grew past what one generation can carry ever surfaces. Money follows the
    money; a contract about what one call can hold stays a contract.
    """
    if config.lanes.unmetered:
        return float("inf")
    return metered


def _lane_limit_micro_usd(config: LLMConfig, lane: BudgetLane) -> int | float:
    """The lane's monthly ceiling in micro-USD, or ``inf`` when unmetered.

    ``BudgetLanes.unmetered`` is the deployment saying it has no monthly
    envelope, so the comparison in :func:`_assert_lane_headroom` is left to
    return the spend it measured and admit the call.
    """
    if config.lanes.unmetered:
        return float("inf")
    amount = {
        BudgetLane.ANALYSIS: config.lanes.analysis_usd,
        BudgetLane.TURN: config.lanes.turn_usd,
        BudgetLane.EMERGENCY: config.lanes.emergency_usd,
    }[lane]
    return int(
        (Decimal(str(amount)) * Decimal(1_000_000)).to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def _ict_month(moment: datetime) -> tuple[datetime, datetime]:
    local = moment.astimezone(ICT)
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        reset = start.replace(year=start.year + 1, month=1)
    else:
        reset = start.replace(month=start.month + 1)
    return start.astimezone(timezone.utc), reset.astimezone(timezone.utc)


def ict_day(moment: datetime) -> tuple[datetime, datetime]:
    """The UTC bounds of the Vietnamese day a moment falls in.

    Public because the daily ceilings are read in two places that must agree
    about where a day begins: here, where a Turn is refused for exceeding one,
    and the usage read that tells the account holder the same thing before they
    ask. A second copy of these four lines is a panel that disagrees with the
    refusal it exists to explain.
    """
    local = moment.astimezone(ICT)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    reset = start + timedelta(days=1)
    return start.astimezone(timezone.utc), reset.astimezone(timezone.utc)


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _read_turn_state(
    session: Session,
    user_id: int,
    called_at: datetime,
    owner_id: str,
) -> TurnState:
    """Read current Turn counts inside the same locked admission transaction.

    **The start allowance is consumed at dispatch, not at admission:**
    refusals, provider model refusals and incomplete Turns count because they
    consumed resources, while authentication, schema, origin, body-size and
    admission failures rejected *before* dispatch do not.

    That is why the count is over ``llm_call_usage`` rather than over
    ``agent_turn``. A reservation row is written immediately before the network
    call and only then, so its existence *is* the fact that a Turn dispatched —
    where an ``agent_turn`` row exists from the create transaction onwards and
    would charge a start to a Turn this very check is about to refuse.

    The current owner is excluded and then added back, so the candidate counts
    exactly once whether this is its first call or its eighth.
    """
    day_start, day_reset = ict_day(called_at)
    dispatched = session.scalar(
        select(func.count(func.distinct(LlmCallUsage.owner_id))).where(
            LlmCallUsage.owner_type == OwnerType.TURN_REQUEST_MESSAGE.value,
            LlmCallUsage.user_id == user_id,
            LlmCallUsage.owner_id != owner_id,
            LlmCallUsage.provider_called_at >= day_start,
            LlmCallUsage.provider_called_at < day_reset,
        )
    )
    starts = int(dispatched or 0) + 1
    active_for_user = session.scalar(
        select(func.count(AgentTurn.id))
        .join(AgentThread, AgentThread.id == AgentTurn.thread_id)
        .where(
            AgentThread.user_id == user_id,
            AgentTurn.status.in_(ACTIVE_TURN_STATUSES),
        )
    )
    active_system = session.scalar(
        select(func.count(AgentTurn.id)).where(
            AgentTurn.status.in_(ACTIVE_TURN_STATUSES)
        )
    )
    return TurnState(
        starts_today=int(starts or 0),
        active_for_user=int(active_for_user or 0),
        active_system=int(active_system or 0),
    )


__all__ = [
    "BUDGET_REFUSAL_REASONS",
    "check_candidate_shape",
    "AdmissionLedger",
    "BudgetLane",
    "BudgetRefusal",
    "CallOwner",
    "ict_day",
    "OwnerType",
    "Reservation",
    "SpendAdmission",
    "SpendRequest",
    "TurnState",
]
