"""What route the application talks to, and what that route charges.

Every value here is environment configuration, and that is the whole point of
the boundary: a route change is an env-var flip. A model id compiled into a
module would survive the
flip and quietly keep the old route alive, so the only place a model id may
have a default is ``Settings`` — the configuration layer itself.

Prices are declared **per workload** rather than once. Batch and interactive
lanes are different models by design, and one price block shared between them
would either overstate the cheap lane or underfund the expensive one — and the
ceilings that Budget Validation checks are denominated in money, so a wrong
price is a wrong ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

# Prices are published per million tokens; costs are in USD.
TOKENS_PER_PRICE_UNIT = 1_000_000

# Every deadline is clamped where it is configured rather than where it is used,
# and the reason is a real crash rather than tidiness: a timeout large enough to
# overflow ``time_t`` raises inside ``Lock.acquire(timeout=)`` on macOS and takes
# the whole batch down with it (cpython #83220). One day is far past any answer
# worth waiting for, and one second is the floor below which a configuration
# value is a typo rather than an impatient operator.
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 86_400.0


def clamp_timeout(seconds: float) -> float:
    """One deadline, inside the range every waiter can express."""
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return MIN_TIMEOUT_SECONDS
    if value != value:  # NaN, which compares false against every bound
        return MIN_TIMEOUT_SECONDS
    return max(MIN_TIMEOUT_SECONDS, min(MAX_TIMEOUT_SECONDS, value))


class Workload(str, Enum):
    """The two lanes a model is chosen for, never inside a loop.

    The split is made once, before the loop runs: an in-loop split adds a
    decision point whose quality nothing here can measure.
    """

    BATCH = "batch"
    SESSION = "session"


@dataclass(frozen=True)
class TokenPrices:
    """The four prices a route charges, in USD per million tokens.

    Five counters meet these four prices: reasoning tokens are billed at the
    output price, because that is what the provider charges for them and
    inventing a fifth price would put a number nobody publishes into the ledger.
    """

    input: float
    cached_input: float
    cache_write: float
    output: float

    def cost_usd(
        self,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        cache_write_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> float:
        """Price one call's token counts.

        ``input_tokens`` counts the fresh input only. Cached reads and cache
        writes are counted separately by the provider and must not be added
        back in here, which is exactly the double-count ``llm_call_usage``
        exists to keep out of the ledger.
        """
        units = (
            input_tokens * self.input
            + cached_input_tokens * self.cached_input
            + cache_write_tokens * self.cache_write
            + (output_tokens + reasoning_tokens) * self.output
        )
        return units / TOKENS_PER_PRICE_UNIT

    @property
    def worst_case_input(self) -> float:
        """What an input token costs when every one of them is charged dearest.

        Admission reserves the worst case before dispatch, and writing the cacheable prefix is usually dearer than reading it
        fresh. Validating against the cheaper of the two would approve a
        configuration whose first cache-writing call already breaks the ceiling.
        """
        return max(self.input, self.cache_write)


@dataclass(frozen=True)
class PricingTable:
    """One dated, versioned set of prices per workload.

    The version and the effective date are carried rather than derived: a cost
    row records which prices produced it, and a table that
    cannot say which prices it holds cannot be reconciled against later.
    """

    version: str
    effective_from: date | None
    batch: TokenPrices
    session: TokenPrices

    def for_workload(self, workload: Workload) -> TokenPrices:
        return self.batch if workload is Workload.BATCH else self.session


@dataclass(frozen=True)
class LLMRoute:
    """Where the calls go, and with what credential.

    The credential is redacted from every representation. A route ends up in
    logs and tracebacks by accident all the time; a key that ends up there once
    has to be rotated.
    """

    base_url: str
    api_key: str = field(repr=False, default="")
    #: Whether this route may be called with ``stream: true``. A route that
    #: streams tool calls without the upstream index cannot be assembled safely,
    #: and that is a fact about the route rather than about any one call — so it
    #: is answered here, once, instead of at every call site.
    streaming: bool = True
    #: Whether this route requires a thinking model's own reasoning history to
    #: come back with the tool-call history. Answered per route for the same
    #: reason ``streaming`` is: it is a property of what is on the other end.
    reasoning_history: bool = False
    #: Whether this route accepts ``cache_control`` breakpoints on message
    #: content. Off until the Capability Probe's ``prompt_cache_control`` check
    #: says otherwise, because the field is Anthropic's spelling and an
    #: OpenAI-compatible route is free to refuse the request that carries it —
    #: and a breakpoint in the wrong place voids a cache rather than filling one.
    prompt_cache_control: bool = False
    #: Whether this route reads image blocks. Answered here for the reason
    #: ``streaming`` is: it is a fact about what is on the other end, not about
    #: any one call — and ``loop.py`` reads no settings at all, so every edge
    #: fact reaches it through this object or not at all.
    vision: bool = False

    def __repr__(self) -> str:
        marker = "set" if self.api_key else "missing"
        return (
            f"LLMRoute(base_url={self.base_url!r}, api_key=<{marker}>, "
            f"streaming={self.streaming}, "
            f"reasoning_history={self.reasoning_history}, "
            f"prompt_cache_control={self.prompt_cache_control}, "
            f"vision={self.vision})"
        )

    __str__ = __repr__


@dataclass(frozen=True)
class BudgetLanes:
    """The monthly envelope and the three lanes that share it."""

    monthly_envelope_usd: float
    analysis_usd: float
    turn_usd: float
    emergency_usd: float

    @property
    def allocated_usd(self) -> float:
        return self.analysis_usd + self.turn_usd + self.emergency_usd

    @property
    def unmetered(self) -> bool:
        """Whether this deployment declares no monthly envelope at all.

        ``0`` is unlimited here, widened to the whole envelope for a route
        billed by subscription rather than per call. It has to be all four
        values or none: a single zero among three funded lanes is a variable
        somebody forgot to fill in, and Budget Validation keeps failing that,
        because an unfunded lane refuses every call rather than admitting it.
        """
        return (
            self.monthly_envelope_usd <= 0
            and self.analysis_usd <= 0
            and self.turn_usd <= 0
            and self.emergency_usd <= 0
        )


@dataclass(frozen=True)
class UserCeilings:
    """The five per-user spend ceilings; ``None`` is unlimited.

    Configuration for the same reason the lanes are: what one account may spend
    in a day is a spend decision rather than a promise the product makes, and a
    deployment used internally over a subscription route answers it differently
    from one serving strangers over a metered API. The ADR's numbers are the
    defaults, so the contract still has one written home and one env var
    restores it.

    ``None`` drops only the refusal. Every call is still reserved and
    reconciled into ``llm_call_usage``, so the ledger keeps answering what an
    account has spent — which is what makes turning a ceiling off recoverable.
    """

    turn_starts_per_day: int | None = 20
    active_turns_per_user: int | None = 1
    active_turns_system: int | None = 3
    daily_usd: float | None = 3.0
    rolling_30d_usd: float | None = 15.0


@dataclass(frozen=True)
class LLMConfig:
    """Everything the boundary reads, resolved once from settings."""

    enabled: bool
    route: LLMRoute
    models: Mapping[Workload, str]
    pricing: PricingTable
    lanes: BudgetLanes
    #: How long *this process* waits for one HTTP attempt. Enforced by ``httpx``
    #: on the socket, and distinct from the deadline the route keeps for itself:
    #: an expiry here is a ``DeadlineExpired``, while a 504 from the route is a
    #: ``GatewayTimeout``, and the two have different remedies.
    request_timeout_seconds: float = 120.0
    #: The five per-user ceilings, each of which may be unlimited.
    ceilings: UserCeilings = UserCeilings()
    #: The shared Redis rate-limit breaker (``core/llm/breaker.py``). A kill
    #: switch rather than a tuning knob: the breaker fails open, so turning it
    #: off returns the deployment to discovering each rate limit per caller.
    route_breaker_enabled: bool = True

    def model_for(self, workload: Workload) -> str:
        return self.models[workload]

    def alternate_model(self, workload: Workload) -> tuple[str, Workload] | None:
        """The other model of the configured pair, with the workload it is priced under.

        Returned as a pair because a failover that changed the model without
        changing the workload would be reserved against the wrong prices, and
        ``SpendAdmission.reserve`` refuses that combination outright — which is
        the check that makes this failover legitimate rather than the silent
        transport-level fallback ``transport.py`` refuses to do.
        """
        other = Workload.BATCH if workload is Workload.SESSION else Workload.SESSION
        candidate = self.models.get(other, "").strip()
        if not candidate or candidate == self.models.get(workload, "").strip():
            return None
        return candidate, other

    def prices_for(self, workload: Workload) -> TokenPrices:
        return self.pricing.for_workload(workload)


def _user_ceilings_from_settings(settings: Any) -> UserCeilings:
    """Read the five per-user ceilings, mapping a non-positive value to unlimited.

    One reader for all five rather than five inline conditionals: the
    ``0``-means-unlimited convention is the part a later ceiling would get
    wrong, and a ceiling accidentally read as ``0`` *enforced* would refuse
    every Turn instead of admitting them.
    """

    def limit(name: str, cast):
        value = cast(getattr(settings, name))
        return value if value > 0 else None

    return UserCeilings(
        turn_starts_per_day=limit("llm_user_turn_starts_per_day", int),
        active_turns_per_user=limit("llm_user_active_turns", int),
        active_turns_system=limit("llm_system_active_turns", int),
        daily_usd=limit("llm_user_daily_usd", float),
        rolling_30d_usd=limit("llm_user_rolling_30d_usd", float),
    )


def _prices_for(settings: Any, workload: Workload) -> TokenPrices:
    """Read one workload's four prices off the settings that name it.

    One reader rather than two mirrored blocks: the mirror is where a copied
    line keeps the wrong workload's name, and a price read from the wrong lane
    is a ceiling enforced against the wrong model.
    """
    prefix = f"llm_price_{workload.value}"
    return TokenPrices(
        input=getattr(settings, f"{prefix}_input_usd_per_mtok"),
        cached_input=getattr(settings, f"{prefix}_cached_input_usd_per_mtok"),
        cache_write=getattr(settings, f"{prefix}_cache_write_usd_per_mtok"),
        output=getattr(settings, f"{prefix}_output_usd_per_mtok"),
    )


def llm_config_from_settings(settings: Any | None = None) -> LLMConfig:
    """Build the configuration the whole boundary shares."""
    if settings is None:
        from src.core.config import get_settings

        settings = get_settings()

    return LLMConfig(
        enabled=bool(settings.alpha_desk_enabled),
        route=LLMRoute(
            base_url=settings.llm_base_url.strip(),
            api_key=settings.llm_api_key.strip(),
            streaming=bool(settings.llm_streaming_enabled),
            reasoning_history=bool(settings.llm_reasoning_history_required),
            prompt_cache_control=bool(
                getattr(settings, "llm_prompt_cache_control_enabled", False)
            ),
            vision=bool(getattr(settings, "llm_vision_enabled", False)),
        ),
        models=MappingProxyType(
            {
                Workload.BATCH: settings.llm_model_batch.strip(),
                Workload.SESSION: settings.llm_model_session.strip(),
            }
        ),
        pricing=PricingTable(
            version=settings.llm_pricing_version.strip(),
            effective_from=settings.llm_pricing_effective_date,
            batch=_prices_for(settings, Workload.BATCH),
            session=_prices_for(settings, Workload.SESSION),
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=settings.llm_budget_monthly_usd,
            analysis_usd=settings.llm_budget_analysis_usd,
            turn_usd=settings.llm_budget_turn_usd,
            emergency_usd=settings.llm_budget_emergency_usd,
        ),
        request_timeout_seconds=clamp_timeout(settings.llm_request_timeout_seconds),
        ceilings=_user_ceilings_from_settings(settings),
        route_breaker_enabled=bool(getattr(settings, "llm_route_breaker_enabled", True)),
    )


__all__ = [
    "MAX_TIMEOUT_SECONDS",
    "MIN_TIMEOUT_SECONDS",
    "BudgetLanes",
    "LLMConfig",
    "LLMRoute",
    "PricingTable",
    "TokenPrices",
    "UserCeilings",
    "Workload",
    "clamp_timeout",
    "llm_config_from_settings",
]
