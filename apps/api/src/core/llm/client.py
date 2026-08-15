"""The public LLM boundary, guarded by committed worst-case spend."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable, Protocol

import httpx
from sqlalchemy.orm import Session
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .admission import AdmissionLedger, BudgetLane, SpendAdmission, SpendRequest
from .config import LLMConfig
from .errors import GatewayTimeout, LLMError, MAX_GATEWAY_ATTEMPTS
from .protocol import Completion, CompletionRequest


class MissingSpendReservation(RuntimeError):
    """A caller tried to reach the provider without an accounting owner."""


class ProviderTransport(Protocol):
    """The network implementation hidden behind :class:`ReservedLLMClient`."""

    async def dispatch(self, request: CompletionRequest) -> Completion: ...


class ReservedLLMClient:
    """Reserve each attempt, dispatch without a transaction, then reconcile."""

    def __init__(self, transport: ProviderTransport, admission: AdmissionLedger) -> None:
        self._transport = transport
        self._admission = admission

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

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(MAX_GATEWAY_ATTEMPTS),
            wait=wait_exponential(multiplier=0.5, max=4),
            retry=retry_if_exception_type(GatewayTimeout),
            reraise=True,
        ):
            with attempt:
                candidate = (
                    spend
                    if attempt.retry_state.attempt_number == 1
                    else replace(spend, lane=BudgetLane.EMERGENCY)
                )
                reservation = await asyncio.to_thread(
                    self._admission.reserve,
                    candidate,
                    request.model,
                )
                try:
                    result = await self._transport.dispatch(request)
                except LLMError as exc:
                    if exc.usage is not None:
                        await asyncio.to_thread(
                            self._admission.reconcile,
                            reservation,
                            exc.usage,
                        )
                    raise
                await asyncio.to_thread(
                    self._admission.reconcile,
                    reservation,
                    result.usage,
                )
                return result

        raise RuntimeError("the retry loop ended without a result")  # pragma: no cover


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
    )


__all__ = [
    "MissingSpendReservation",
    "ProviderTransport",
    "ReservedLLMClient",
    "build_client",
]
