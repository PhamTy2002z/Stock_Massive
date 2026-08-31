"""The one composition root Alpha Desk's transport is served from.

Everything a Turn needs — the client, the tools, the execution slots, the
lifecycle and the admission check — is built **once per process** and shared.
That is not a performance choice.

**The tools are registered here, once.** ``tools.register_all()`` has no import
side effect by design (``tools/__init__.py``), so something has to call it, and
the composition root is the only place that knows the process is starting rather
than a test importing a module. Registering inside the loop would make the tool
list a function of how many Turns had run.

**The semaphore only means anything if it is shared.** :class:`SessionSlots`
defaults to a fresh instance per :class:`AgentLoop`, which would give every Turn
its own permits and enforce nothing. One instance here is what makes "three
concurrent Turns" true, and it is the same instance admission reads before it
opens a stream.

**The ledger only means anything if it is one ledger.** Admission at the route
asks the same ``SpendAdmission`` the client reserves against, rather than a
second one built beside it that could read a different configuration.
"""

from __future__ import annotations

import logging
from typing import Any

from src.agent import tools
from src.agent.limits import SubscriptionLimiter
from src.agent.loop import AgentLoop, SessionSlots, TurnAdmission
from src.agent.persistence import AgentPersistence
from src.agent.turns import TurnService
from src.alpha.refusals import AlphaRefusal
from src.core.config import get_settings
from src.core.llm import LLMConfig, build_client, llm_config_from_settings

logger = logging.getLogger(__name__)


class AlphaDeskDisabled(AlphaRefusal):
    """The operator switched the interactive surface off.

    Nothing disables itself automatically, so this is only ever a deliberate
    act — and it must read as a temporary service condition
    rather than as a fault or as a rule about this user.
    """

    def __init__(self) -> None:
        super().__init__(
            reason="alpha_desk_disabled",
            message="Alpha Desk is currently unavailable.",
            status_code=503,
        )


class AlphaDeskService:
    """The process-wide handle the transport endpoints are served from."""

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
) -> AlphaDeskService:
    """Assemble the whole surface. Called once, at first use."""
    settings = get_settings()
    resolved = config or llm_config_from_settings(settings)
    persistence = store or AgentPersistence()
    client = build_client(resolved)
    # Idempotent, so a reload path and a startup path may both reach it. The
    # registered set is what ``definitions.get_tool_definitions`` builds the
    # schema list from, and nothing else installs a tool.
    installed = tools.register_all()
    logger.info(
        "Alpha Desk registered %d tool(s): %s",
        len(installed),
        ", ".join(entry.name for entry in installed),
    )
    # The semaphore and the ledger enforce one configured ceiling from opposite
    # sides (``core/llm/admission.py``); ``None`` is unlimited in both.
    slots = SessionSlots(limit=resolved.ceilings.active_turns_system)

    def loop_factory(*, checkpoint, publisher) -> AgentLoop:
        return AgentLoop(
            client=client,
            config=resolved,
            slots=slots,
            checkpoint=checkpoint,
            publisher=publisher,
            # Wired the same way the checkpoint is: one short transaction per
            # write, and a Turn never holds a session.
            trace=persistence.record_tool_call,
        )

    return AlphaDeskService(
        turns=TurnService(
            store=persistence,
            loop_factory=loop_factory,
            config=resolved,
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

    Lazily rather than at import, because building it opens an HTTP client,
    reads configuration and registers tools — work that must not happen merely
    because a test imported a module.
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
