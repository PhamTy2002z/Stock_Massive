"""The one composition root Alpha Desk's transport is served from (#85).

Everything a Turn needs — the client, the Tool Catalog, the execution slots, the
lifecycle and the admission check — is built **once per process** and shared.
That is not a performance choice.

**The semaphore only means anything if it is shared.**  :class:`SessionSlots`
defaults to a fresh instance per :class:`AgentLoop`, which would give every Turn
its own three permits and enforce nothing at all.  One instance here is what
makes "three concurrent Turns" true, and it is the same instance admission reads
before it opens a stream.

**The ledger only means anything if it is one ledger.**  Admission at the route
asks the same :class:`SpendAdmission` the client reserves against, rather than a
second one built beside it that could read a different configuration.

**The Tool Catalog's version is part of every Evidence Manifest.**  Building the
catalog per request would recompute the same hash for every Turn; building it
once makes the version a property of the deployment, which is what the Manifest
records it as.
"""

from __future__ import annotations

import logging
from typing import Any

from src.agent.admission import TurnAdmission
from src.agent.limits import SubscriptionLimiter
from src.agent.loop import AgentLoop, SessionSlots
from src.agent.persistence import AgentPersistence
from src.agent.tools.suite import IntelligentQuantCatalog
from src.agent.turns import TurnService
from src.alpha.refusals import AlphaRefusal
from src.core.config import get_settings
from src.core.llm import LLMConfig, build_client, llm_config_from_settings

logger = logging.getLogger(__name__)


class AlphaDeskDisabled(AlphaRefusal):
    """The operator switched the interactive surface off.

    ``docs/adr/0008``: nothing disables itself automatically, so this is only
    ever a deliberate act — and it must read as a temporary service condition
    rather than as a fault or as a rule about this user.
    """

    def __init__(self) -> None:
        super().__init__(
            reason="alpha_desk_disabled",
            message="Alpha Desk is currently unavailable.",
            status_code=503,
        )


class AlphaDeskService:
    """The process-wide handle the three transport endpoints are served from."""

    def __init__(
        self,
        *,
        turns: TurnService,
        admission: TurnAdmission,
        subscriptions: SubscriptionLimiter,
        store: AgentPersistence,
        config: LLMConfig,
        client: Any,
    ) -> None:
        self.turns = turns
        self.admission = admission
        self.subscriptions = subscriptions
        self.store = store
        self.config = config
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    def assert_enabled(self) -> None:
        if not self.enabled:
            raise AlphaDeskDisabled()

    async def aclose(self) -> None:
        """Let active Turns reach a checkpoint, then release the connection.

        Order matters: a client closed first would fail the very call a Turn is
        trying to finish inside its shutdown window.
        """
        await self.turns.shutdown()
        close = getattr(self._client, "aclose", None)
        if close is not None:
            await close()


def build_alpha_desk(
    *,
    config: LLMConfig | None = None,
    store: AgentPersistence | None = None,
    redis: Any | None = None,
) -> AlphaDeskService:
    """Assemble the whole surface. Called once, at first use."""
    settings = get_settings()
    resolved = config or llm_config_from_settings(settings)
    persistence = store or AgentPersistence()
    client = build_client(resolved)
    catalog = IntelligentQuantCatalog(redis=redis).catalog(
        # The Trace is written by the same short transaction every other write
        # uses; a Turn never holds a session (``docs/specs/0003`` §10.5).
        trace_writer=persistence.record_tool_call,
    )
    slots = SessionSlots()

    def loop_factory(*, checkpoint, publisher) -> AgentLoop:
        return AgentLoop(
            client=client,
            catalog=catalog,
            config=resolved,
            slots=slots,
            checkpoint=checkpoint,
            publisher=publisher,
            # Read here rather than inside the loop: the deployment decides
            # whether an extra batch call per answered Turn is worth its cost,
            # and the loop should not have to know what a Settings object is.
            suggest=settings.alpha_desk_suggestions_enabled,
        )

    return AlphaDeskService(
        turns=TurnService(
            store=persistence,
            loop_factory=loop_factory,
            config=resolved,
            tool_catalog_version=catalog.tool_catalog_version,
            mcp_servers_version=catalog.mcp_servers_version,
        ),
        admission=TurnAdmission(client.admission, slots=slots),
        subscriptions=SubscriptionLimiter(),
        store=persistence,
        config=resolved,
        client=client,
    )


_service: AlphaDeskService | None = None


def alpha_desk() -> AlphaDeskService:
    """The process's one service, built on first use.

    Lazily rather than at import, because building it opens an HTTP client and
    reads configuration — work that must not happen merely because a test
    imported a module.
    """
    global _service
    if _service is None:
        _service = build_alpha_desk()
    return _service


def set_alpha_desk(service: AlphaDeskService | None) -> AlphaDeskService | None:
    """Install a service, or clear it. Returns whatever was there before.

    The seam the application's own lifespan and the transport tests both use, so
    neither has to reach into a module global by name.
    """
    global _service
    previous = _service
    _service = service
    return previous


async def close_alpha_desk() -> None:
    """Shut the service down if one was ever built."""
    service = set_alpha_desk(None)
    if service is not None:
        await service.aclose()


__all__ = [
    "AlphaDeskDisabled",
    "AlphaDeskService",
    "alpha_desk",
    "build_alpha_desk",
    "close_alpha_desk",
    "set_alpha_desk",
]
