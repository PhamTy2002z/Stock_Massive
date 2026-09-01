"""The public LLM boundary: committed spend, and one recovery per failure.

Two things live here and nowhere else.

**Every attempt is its own reservation.** The worst case is committed before
dispatch and reconciled after, so a retry is a second
reservation rather than a second call against the first one. That is also what
makes failover legitimate at this layer and illegitimate one layer down — the
transport cannot ask admission anything, so a model it swapped in would be spent
against a ceiling nobody checked.

**Every failure gets the action** ``recovery.py`` **names for it**, and the
actions that belong to the caller are handed up untouched. ``ContextOverflow``
and ``OutputCapExceeded`` are the caller's: the transcript and the output ceiling
are its to change, and a client that shrank either of them would be editing a
request it was asked to send.

The retry loop is hand-rolled rather than declarative. It has to reserve per
attempt, choose a lane per attempt, jitter its own backoff, rebuild the transport
between two of the branches, swap models in a third, and decide whether an empty
answer was deterministic — and expressing that in a retry decorator's predicates
would spread one decision across five callbacks that cannot see each other.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, Protocol

import httpx
from sqlalchemy.orm import Session

from .admission import AdmissionLedger, BudgetLane, SpendAdmission, SpendRequest
from .breaker import RouteBreaker, route_key
from .config import LLMConfig
from .errors import (
    GatewayTimeout,
    LLMError,
    MAX_GATEWAY_ATTEMPTS,
    RouteAttempt,
    RouteRateLimited,
)
from .protocol import Completion, CompletionRequest
from .recovery import RouteAction, recovery_for

logger = logging.getLogger(__name__)

# The ceiling on paid attempts for one ``complete`` call, whatever combination of
# recoveries fires. Four is the worst legitimate path — two attempts on a route
# that timed out, one failover to the other model, one retry of an answer that
# came back empty for no stated reason — and a fifth would mean two recoveries
# had chained into each other, which is a loop rather than a recovery.
MAX_ROUTE_ATTEMPTS = 4

# Backoff between attempts, jittered. Fixed backoff is what turns one
# rate-limited route into a thundering herd: every session that failed at the
# same moment comes back at the same moment. The jitter is full rather than
# partial because the point is decorrelation, not politeness.
BACKOFF_BASE_SECONDS = 0.5
BACKOFF_MAX_SECONDS = 4.0

# How many empty answers with the same signature it takes to call the emptiness
# deterministic. Two: one is a route having a bad second, and paying for a third
# to confirm what the second already said is the failure this guard exists to
# stop — an empty answer is charged for its input like any other.
EMPTY_RUN_FOR_DETERMINISM = 2

# How many dispatches to one model may come back empty before the call gives up
# on that model. Also two, and for the opposite reason to the constant above: an
# empty answer used to be returned on the first one, so every retry here is new
# money, and the run that justifies spending it is exactly one retry long.
MAX_EMPTY_ATTEMPTS = 2


class MissingSpendReservation(RuntimeError):
    """A caller tried to reach the provider without an accounting owner."""


class ProviderTransport(Protocol):
    """The network implementation hidden behind :class:`ReservedLLMClient`."""

    async def dispatch(self, request: CompletionRequest) -> Completion: ...


@dataclass(frozen=True)
class _EmptySignature:
    """What an empty answer looked like, tightly enough to compare two of them.

    Model, route and finish reason. Two empties from different models are two
    incidents; two from the same model with the same finish reason are one thing
    happening twice, which is the only case worth acting on.
    """

    model: str
    route: str
    finish_reason: str


class _EmptyRun:
    """The run of identical empty answers seen inside one ``complete`` call.

    Fails open in both of its judgements. An answer with no usage at all is not
    counted as deterministic, because the evidence that the route generated
    nothing is precisely the usage that is missing; and reasoning tokens count as
    generation, so a thinking model that spent its whole ceiling on hidden
    thinking is a truncation to be retried rather than an empty route to give up
    on.
    """

    def __init__(self) -> None:
        self._signature: _EmptySignature | None = None
        self._length = 0

    @staticmethod
    def is_empty(completion: Completion) -> bool:
        return not completion.tool_calls and not (completion.text or "").strip()

    @staticmethod
    def is_deterministic(completion: Completion) -> bool:
        usage = completion.usage
        if usage is None:
            return False
        return usage.output_tokens <= 0 and usage.reasoning_tokens <= 0

    def record(self, completion: Completion, route: str) -> bool:
        """Note one empty answer, and say whether the run is now conclusive."""
        if not self.is_deterministic(completion):
            self._signature = None
            self._length = 0
            return False
        signature = _EmptySignature(
            model=completion.model,
            route=route,
            finish_reason=completion.finish_reason,
        )
        if signature == self._signature:
            self._length += 1
        else:
            self._signature = signature
            self._length = 1
        return self._length >= EMPTY_RUN_FOR_DETERMINISM


class ReservedLLMClient:
    """Reserve each attempt, dispatch without a transaction, then reconcile."""

    def __init__(
        self,
        transport: ProviderTransport,
        admission: AdmissionLedger,
        config: LLMConfig | None = None,
        breaker: RouteBreaker | None = None,
        sleep: Callable[[float], object] | None = None,
    ) -> None:
        self._transport = transport
        self._admission = admission
        self._config = config
        # Built here rather than injected by every caller, and disabled outright
        # without a configuration to read: a breaker that cannot know which route
        # it is guarding would key every deployment's rate limits together.
        self._breaker = breaker or RouteBreaker(
            enabled=bool(config and config.route_breaker_enabled)
        )
        self._sleep = sleep or asyncio.sleep

    @property
    def admission(self) -> AdmissionLedger:
        """The ledger every call is reserved against.

        Exposed for one caller: the transport's ``POST`` has to ask the same
        ledger the same ceiling questions *before* a Turn exists, and a second
        ledger built beside this one could read a different configuration.
        """
        return self._admission

    async def aclose(self) -> None:
        close = getattr(self._transport, "aclose", None)
        if close is not None:
            await close()

    async def complete(
        self,
        request: CompletionRequest,
        spend: SpendRequest | None = None,
    ) -> Completion:
        if spend is None:
            raise MissingSpendReservation(
                "an LLM call requires a committed worst-case spend reservation"
            )

        empties = _EmptyRun()
        attempt = 0
        gateway_attempts = 0
        empty_attempts = 0
        switched = False

        while True:
            attempt += 1
            await self._refuse_while_rate_limited(request.model)
            # The first attempt is funded from the lane the caller named; every
            # attempt after it is a retry, and a retry is what the emergency lane
            # is for.
            candidate = spend if attempt == 1 else replace(spend, lane=BudgetLane.EMERGENCY)
            reservation = await asyncio.to_thread(
                self._admission.reserve, candidate, request.model
            )
            try:
                result = await self._transport.dispatch(request)
            except LLMError as exc:
                if exc.usage is not None:
                    await asyncio.to_thread(
                        self._admission.reconcile, reservation, exc.usage
                    )
                if isinstance(exc, GatewayTimeout):
                    gateway_attempts += 1
                    # The retry count is only knowable here: the transport makes
                    # one paid attempt and does not know it is the second.
                    # Stamped rather than logged, so the caller that ends the Turn
                    # is the one that says how much was spent trying.
                    #
                    # Every paid attempt of this call, not only the ones that
                    # timed out: the field says what was spent reaching the
                    # failure, and a failover before it was spent too.
                    exc.attempt = replace(
                        exc.attempt or RouteAttempt(), attempts=attempt
                    )
                action = recovery_for(exc).action
                if isinstance(exc, RouteRateLimited):
                    # Off the event loop: ``get_redis`` hands back a *synchronous*
                    # client, and on the Upstash dialect this is an HTTPS round
                    # trip. Blocking here would stall every other Turn, every SSE
                    # heartbeat, and — per cpython #84047 — every asyncio timer in
                    # the process, on the one path this module calls cheap.
                    await asyncio.to_thread(
                        self._record_rate_limit, request.model, exc
                    )
                    raise
                if action is RouteAction.REBUILD_AND_RETRY and self._may_retry(
                    attempt, gateway_attempts
                ):
                    await self._rebuild()
                    await self._backoff(attempt)
                    continue
                if (
                    action is RouteAction.SWITCH_MODEL
                    and not switched
                    and attempt < MAX_ROUTE_ATTEMPTS
                ):
                    swapped = self._switch_model(request, spend)
                    if swapped is not None:
                        # No backoff: the wait between attempts exists to
                        # decorrelate callers hammering one route, and this
                        # attempt is going somewhere else.
                        request, spend = swapped
                        switched = True
                        continue
                raise

            if result.usage is not None:
                await asyncio.to_thread(self._admission.reconcile, reservation, result.usage)

            if not _EmptyRun.is_empty(result):
                return result

            empty_attempts += 1
            conclusive = empties.record(result, self._route_url())
            if conclusive and not switched and attempt < MAX_ROUTE_ATTEMPTS:
                swapped = self._switch_model(request, spend)
                if swapped is not None:
                    logger.warning(
                        "The route answered empty %d times as %s with finish_reason "
                        "%r and no output tokens; asking %s instead",
                        EMPTY_RUN_FOR_DETERMINISM,
                        request.model,
                        result.finish_reason,
                        swapped[0].model,
                    )
                    request, spend = swapped
                    switched = True
                    # The other model gets its own allowance of empties: the run
                    # that was conclusive was conclusive about the model it was
                    # measured on.
                    empty_attempts = 0
                    continue
            if (
                conclusive
                or empty_attempts >= MAX_EMPTY_ATTEMPTS
                or attempt >= MAX_ROUTE_ATTEMPTS
            ):
                # Handed back rather than raised: an empty answer is what the
                # route returned, and a new exception class here would end Turns
                # that today survive on a partial answer and their traces.
                logger.warning(
                    "The route answered empty and nothing left to try: model=%s "
                    "finish_reason=%r deterministic=%s attempts=%d",
                    result.model,
                    result.finish_reason,
                    _EmptyRun.is_deterministic(result),
                    attempt,
                )
                return result
            await self._backoff(attempt)

    # -- the recoveries ---------------------------------------------------

    def _may_retry(self, attempt: int, gateway_attempts: int) -> bool:
        """Whether another paid attempt is allowed for a route that timed out.

        Two ceilings, and both are needed. ``MAX_GATEWAY_ATTEMPTS`` is the
        measured one — a third attempt on a route that has timed out twice spends
        more of a user's patience than it buys back — and ``MAX_ROUTE_ATTEMPTS``
        bounds the whole call, so a timeout after a failover cannot start the
        timeout budget again.
        """
        return (
            gateway_attempts < MAX_GATEWAY_ATTEMPTS and attempt < MAX_ROUTE_ATTEMPTS
        )

    async def _rebuild(self) -> None:
        """Ask the transport for fresh connections, if it owns any."""
        rebuild = getattr(self._transport, "rebuild", None)
        if rebuild is None:
            return
        try:
            await rebuild()
        except Exception as exc:  # noqa: BLE001 - a failed rebuild is not a failed Turn
            logger.debug("The LLM transport could not be rebuilt: %s", exc)

    async def _backoff(self, attempt: int) -> None:
        """Wait a jittered, exponentially-growing moment before asking again."""
        ceiling = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
        await self._sleep(random.uniform(0, ceiling))

    def _switch_model(
        self,
        request: CompletionRequest,
        spend: SpendRequest,
    ) -> tuple[CompletionRequest, SpendRequest] | None:
        """The same request against the other model of the configured pair.

        Returns the *pair* of request and spend, because the workload has to move
        with the model: admission prices a call by workload and refuses a model
        that is not the one configured for it, which is what keeps this from
        being the silent fallback ``transport.py`` refuses to do.
        """
        if self._config is None:
            return None
        alternate = self._config.alternate_model(spend.workload)
        if alternate is None:
            return None
        model, workload = alternate
        logger.info(
            "Failing the LLM call over from %s to %s under the %s workload",
            request.model,
            model,
            workload.value,
        )
        return replace(request, model=model), replace(spend, workload=workload)

    # -- the shared rate-limit breaker ------------------------------------

    def _route_url(self) -> str:
        return self._config.route.base_url if self._config else ""

    def _breaker_key(self, model: str) -> str | None:
        if self._config is None or not self._breaker.enabled:
            return None
        return route_key(self._config.route.base_url, model)

    async def _refuse_while_rate_limited(self, model: str) -> None:
        """Refuse before dispatch while another caller's 429 is still holding.

        Raised as the same ``RouteRateLimited`` the route itself raises, because
        it is the same condition: the allowance is spent, and the remedy belongs
        to the operator rather than to a retry. What is saved is the paid request
        that would have been refused.

        Fails open all the way down — an unreachable Redis answers zero — so this
        can only ever refuse a call the route was going to refuse anyway.
        """
        key = self._breaker_key(model)
        if key is None:
            return
        remaining = await asyncio.to_thread(self._breaker.open_for, key)
        if remaining <= 0:
            return
        # Logged rather than counted. ``llm_metrics().rate_limits`` answers "how
        # often did the route refuse us", and a refusal this process made on the
        # strength of an earlier one would count the same 429 twice.
        logger.info(
            "Refusing an LLM call before dispatch: a shared breaker is holding "
            "%s for another %.1fs",
            model,
            remaining,
        )
        raise RouteRateLimited(
            f"the route is out of allowance for {model}; a shared breaker is "
            f"holding it for another {remaining:.1f}s",
            retry_after=remaining,
        )

    def _record_rate_limit(self, model: str, exc: RouteRateLimited) -> None:
        """Write this 429 where the next caller will read it."""
        key = self._breaker_key(model)
        if key is None:
            return
        try:
            self._breaker.record_rate_limit(
                key, retry_after=exc.retry_after, reset_at=exc.reset_at
            )
        except Exception as error:  # noqa: BLE001 - fail open, whatever broke
            logger.debug("The LLM route breaker could not record a 429: %s", error)


def build_client(
    config: LLMConfig | None = None,
    http_client: httpx.AsyncClient | None = None,
    session_factory: Callable[[], Session] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ReservedLLMClient:
    """Compose the only application-facing client: transport behind admission."""
    if config is None:
        from .config import llm_config_from_settings

        config = llm_config_from_settings()
    if session_factory is None:
        from src.core.database import sync_session_factory

        session_factory = sync_session_factory
    if clock is None:
        clock = lambda: datetime.now(timezone.utc)

    from .transport import build_transport

    return ReservedLLMClient(
        build_transport(config=config, http_client=http_client),
        SpendAdmission(config, session_factory=session_factory, clock=clock),
        config=config,
    )


__all__ = [
    "BACKOFF_BASE_SECONDS",
    "BACKOFF_MAX_SECONDS",
    "EMPTY_RUN_FOR_DETERMINISM",
    "MAX_EMPTY_ATTEMPTS",
    "MAX_ROUTE_ATTEMPTS",
    "MissingSpendReservation",
    "ProviderTransport",
    "ReservedLLMClient",
    "build_client",
]
