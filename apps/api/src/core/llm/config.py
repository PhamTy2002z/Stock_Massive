"""What route the application talks to, and what that route charges.

Every value here is environment configuration, and that is the whole point of
the boundary: a route change is an env-var flip (``docs/adr/0014``,
``docs/specs/0003`` §3). A model id compiled into a module would survive the
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


class Workload(str, Enum):
    """The two lanes a model is chosen for, never inside a loop.

    ``docs/adr/0008``: an in-loop split adds a decision point whose quality
    cannot be measured until the Eval Battery exists.
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

        Admission reserves the worst case before dispatch (``docs/adr/0014``),
        and writing the cacheable prefix is usually dearer than reading it
        fresh. Validating against the cheaper of the two would approve a
        configuration whose first cache-writing call already breaks the ceiling.
        """
        return max(self.input, self.cache_write)


@dataclass(frozen=True)
class PricingTable:
    """One dated, versioned set of prices per workload.

    The version and the effective date are carried rather than derived: a cost
    row records which prices produced it (``docs/adr/0014``), and a table that
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

    def __repr__(self) -> str:
        marker = "set" if self.api_key else "missing"
        return (
            f"LLMRoute(base_url={self.base_url!r}, api_key=<{marker}>, "
            f"streaming={self.streaming})"
        )

    __str__ = __repr__


@dataclass(frozen=True)
class BudgetLanes:
    """The monthly envelope and the four lanes that share it."""

    monthly_envelope_usd: float
    analysis_usd: float
    turn_usd: float
    emergency_usd: float
    eval_usd: float

    @property
    def allocated_usd(self) -> float:
        return self.analysis_usd + self.turn_usd + self.emergency_usd + self.eval_usd


@dataclass(frozen=True)
class LLMConfig:
    """Everything the boundary reads, resolved once from settings."""

    enabled: bool
    route: LLMRoute
    models: Mapping[Workload, str]
    pricing: PricingTable
    lanes: BudgetLanes
    request_timeout_seconds: float = 120.0
    eval_run_cost_ceiling_usd: float | None = 2.5

    def model_for(self, workload: Workload) -> str:
        return self.models[workload]

    def prices_for(self, workload: Workload) -> TokenPrices:
        return self.pricing.for_workload(workload)


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

    eval_ceiling = float(settings.llm_eval_run_cost_ceiling_usd)
    return LLMConfig(
        enabled=bool(settings.alpha_desk_enabled),
        route=LLMRoute(
            base_url=settings.llm_base_url.strip(),
            api_key=settings.llm_api_key.strip(),
            streaming=bool(settings.llm_streaming_enabled),
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
            eval_usd=settings.llm_budget_eval_usd,
        ),
        request_timeout_seconds=settings.llm_request_timeout_seconds,
        eval_run_cost_ceiling_usd=eval_ceiling if eval_ceiling > 0 else None,
    )


__all__ = [
    "BudgetLanes",
    "LLMConfig",
    "LLMRoute",
    "PricingTable",
    "TokenPrices",
    "Workload",
    "llm_config_from_settings",
]
