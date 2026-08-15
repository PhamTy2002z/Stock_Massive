"""Spend identities and the reservation handed to one provider dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from enum import Enum
import hashlib
import logging
from typing import Callable, Protocol

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.alpha.models import LlmCallUsage

from .config import LLMConfig, TokenPrices, Workload
from .protocol import Usage

logger = logging.getLogger(__name__)

ANALYSIS_INPUT_PER_CALL = 6_000
ANALYSIS_OUTPUT_PER_CALL = 1_500
ANALYSIS_COST_MICRO_USD = 4_500
TURN_CONTEXT_PER_CALL = 32_000
TURN_INPUT_TOTAL = 100_000
TURN_OUTPUT_TOTAL = 20_000
TURN_COST_MICRO_USD = 500_000


class BudgetLane(str, Enum):
    ANALYSIS = "analysis"
    TURN = "turn"
    EMERGENCY = "emergency"
    EVAL = "eval"


class OwnerType(str, Enum):
    ANALYSIS_RUN = "analysis_run"
    TURN_REQUEST_MESSAGE = "turn_request_message"
    CAPABILITY_PROBE = "capability_probe"
    EVAL_RUN = "eval_run"


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
        super().__init__(message)
        self.reason = reason
        self.state = state
        self.reset_at = reset_at
        self.operator_detail = operator_detail

    def public(self) -> dict[str, str | None]:
        return {
            "reason": self.reason,
            "state": self.state,
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
        }


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
    ) -> None:
        self._config = config
        self._session_factory = session_factory
        self._clock = clock

    def reserve(self, candidate: SpendRequest, model: str) -> Reservation:
        expected_model = self._config.model_for(candidate.workload)
        if model != expected_model:
            raise ValueError(
                f"model {model!r} is not the configured {candidate.workload.value} model"
            )
        if candidate.input_tokens < 0 or candidate.output_tokens < 0:
            raise ValueError("a worst-case token count cannot be negative")

        _check_candidate_shape(candidate)

        called_at = self._clock()
        prices = self._config.prices_for(candidate.workload)
        reserved = _micro_usd(
            prices,
            input_tokens=candidate.input_tokens,
            output_tokens=candidate.output_tokens,
        )

        session = self._session_factory()
        try:
            with session.begin():
                _lock_scopes(
                    session,
                    [
                        f"lane:{candidate.lane.value}:{called_at:%Y-%m}",
                        f"owner:{candidate.owner.type.value}:{candidate.owner.id}",
                    ],
                )
                if candidate.owner.type is OwnerType.ANALYSIS_RUN:
                    owner_cost = _charged_cost(
                        session,
                        LlmCallUsage.owner_type == candidate.owner.type.value,
                        LlmCallUsage.owner_id == candidate.owner.id,
                    )
                    if owner_cost + reserved > ANALYSIS_COST_MICRO_USD:
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
                    if owner_cost + reserved > TURN_COST_MICRO_USD:
                        raise BudgetRefusal(
                            "turn_cost",
                            "This Turn has exhausted its generation allowance.",
                            operator_detail=(
                                f"owner {candidate.owner.id} has {owner_cost} micro-USD "
                                f"charged and requested {reserved} more"
                            ),
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


def _check_candidate_shape(candidate: SpendRequest) -> None:
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
    charged = case(
        (LlmCallUsage.status == "reconciled", LlmCallUsage.actual_micro_usd),
        else_=LlmCallUsage.reserved_micro_usd,
    )
    value = session.scalar(select(func.coalesce(func.sum(charged), 0)).where(*conditions))
    return int(value or 0)


def _owner_totals(session: Session, owner: CallOwner) -> tuple[int, int, int]:
    charged_cost = case(
        (LlmCallUsage.status == "reconciled", LlmCallUsage.actual_micro_usd),
        else_=LlmCallUsage.reserved_micro_usd,
    )
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


__all__ = [
    "AdmissionLedger",
    "BudgetLane",
    "BudgetRefusal",
    "CallOwner",
    "OwnerType",
    "Reservation",
    "SpendAdmission",
    "SpendRequest",
]
