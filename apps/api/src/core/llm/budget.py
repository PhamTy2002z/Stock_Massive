"""Budget Validation: arithmetic that has to hold before the first request.

``docs/adr/0014`` reserves a worst case *before* every call, so the ceilings it
enforces are only enforceable if the configured prices can fund them at all. A
route priced above the per-Analysis or per-Turn ceiling does not fail at
startup on its own — it fails on the first real Turn, halfway through an answer
somebody is watching, which is the one place the failure is most expensive and
least explicable.

The check is local. It reads the configured models and prices, multiplies them
by the token ceilings, and compares. No token is spent and no socket is opened,
which is why it can run inside ``lifespan`` before anything else starts.

**The dev lane still declares prices.** CLIProxyAPI on a personal subscription
publishes none, and dev traffic produces no cost figures at all — a ~300-token
CLI system prompt rides on every request and there is no cache control
(``docs/specs/0003`` §3). What is configured there is therefore the *production*
price table the dev route stands in for, which is the same table the budget is
computed from analytically. Accepting a zero price instead would let a route
boot whose every call costs nothing on paper, and the ceilings this file exists
to enforce would pass by arithmetic rather than by being affordable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .config import LLMConfig, TokenPrices, Workload

logger = logging.getLogger(__name__)

# The ceilings of ``docs/adr/0014``. These are the contract, not the route, so
# they are constants: a deployment that wants different ceilings is changing
# what the product promises, not which model it talks to.
ANALYSIS_INPUT_TOKENS = 6_000
ANALYSIS_OUTPUT_TOKENS = 1_500
ANALYSIS_COST_CEILING_USD = 0.0045

TURN_INPUT_TOKENS = 100_000
TURN_OUTPUT_TOKENS = 20_000
TURN_COST_CEILING_USD = 0.50

# Money compared in floating point needs a tolerance, and the unit the ledger
# is denominated in is the honest one: a micro-USD (``docs/adr/0014``).
MICRO_USD = 1e-6


@dataclass(frozen=True)
class BudgetFailure:
    """One ceiling that cannot hold, named so the operator can act on it."""

    ceiling: str
    message: str

    def __str__(self) -> str:
        return f"{self.ceiling}: {self.message}"


@dataclass(frozen=True)
class BudgetValidation:
    """What the arithmetic found, whether or not it is allowed to stop startup."""

    analysis_cost_usd: float
    turn_cost_usd: float
    failures: tuple[BudgetFailure, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return not self.failures

    def summary(self) -> str:
        if self.ok:
            return (
                "Budget Validation passed: one Analysis costs at most "
                f"${self.analysis_cost_usd:.6f} against ${ANALYSIS_COST_CEILING_USD:.4f}, "
                f"one Turn at most ${self.turn_cost_usd:.4f} against "
                f"${TURN_COST_CEILING_USD:.2f}"
            )
        return "Budget Validation failed — " + "; ".join(
            str(failure) for failure in self.failures
        )


class BudgetValidationError(RuntimeError):
    """The configured prices cannot fund what the ceilings promise."""

    def __init__(self, report: BudgetValidation) -> None:
        super().__init__(report.summary())
        self.report = report


def _price_failures(config: LLMConfig) -> list[BudgetFailure]:
    """Refuse a price table that is incomplete or self-contradictory.

    A zero price is not free service; it is a key nobody filled in. Left alone
    it would pass every ceiling below by costing nothing, which turns the whole
    admission mechanism into a no-op — the exact outcome these checks exist to
    prevent.
    """
    failures: list[BudgetFailure] = []
    pricing = config.pricing

    if not pricing.version or pricing.effective_from is None:
        failures.append(
            BudgetFailure(
                "pricing_version",
                "the pricing table carries no version or no effective date, so no "
                "cost row could say which prices produced it",
            )
        )

    for workload in Workload:
        prices = pricing.for_workload(workload)
        named = {
            "input": prices.input,
            "cached read": prices.cached_input,
            "cache write": prices.cache_write,
            "output": prices.output,
        }
        missing = [name for name, value in named.items() if value <= 0]
        if missing:
            failures.append(
                BudgetFailure(
                    "pricing_table",
                    f"the {workload.value} lane has no {', '.join(missing)} price, "
                    "and an unpriced token reads as a free one",
                )
            )
            continue
        if prices.cached_input > prices.input:
            failures.append(
                BudgetFailure(
                    "pricing_table",
                    f"the {workload.value} lane prices a cached read "
                    f"(${prices.cached_input}/Mtok) above a fresh one "
                    f"(${prices.input}/Mtok), which is what a transposed pair of "
                    "prices looks like",
                )
            )

    return failures


def _route_failures(config: LLMConfig) -> list[BudgetFailure]:
    missing = [
        name
        for name, value in (
            ("base URL", config.route.base_url),
            ("credential", config.route.api_key),
            ("batch model", config.model_for(Workload.BATCH)),
            ("session model", config.model_for(Workload.SESSION)),
        )
        if not value
    ]
    if not missing:
        return []
    return [
        BudgetFailure(
            "route",
            f"the configured route has no {', '.join(missing)}",
        )
    ]


def _lane_failures(config: LLMConfig, analysis: float, turn: float) -> list[BudgetFailure]:
    failures: list[BudgetFailure] = []
    lanes = config.lanes

    if abs(lanes.allocated_usd - lanes.monthly_envelope_usd) > MICRO_USD:
        failures.append(
            BudgetFailure(
                "monthly_envelope",
                f"the four lanes allocate ${lanes.allocated_usd:.2f} against a "
                f"${lanes.monthly_envelope_usd:.2f} envelope",
            )
        )

    if lanes.analysis_usd + MICRO_USD < analysis:
        failures.append(
            BudgetFailure(
                "analysis_lane",
                f"the ${lanes.analysis_usd:.4f} Analysis lane cannot fund one "
                f"Analysis at ${analysis:.6f}",
            )
        )

    if lanes.turn_usd + MICRO_USD < turn:
        failures.append(
            BudgetFailure(
                "turn_lane",
                f"the ${lanes.turn_usd:.2f} Turn lane cannot fund one Turn at "
                f"${turn:.4f}",
            )
        )

    return failures


def _worst_case_usd(prices: TokenPrices, input_tokens: int, output_tokens: int) -> float:
    """Price a whole allowance of tokens at the dearest each one can be.

    Input is charged at ``worst_case_input`` — writing the cacheable prefix is
    usually dearer than reading it fresh, and admission reserves that worst case
    before dispatch. Output is charged through the same ``cost_usd`` the ledger
    will use, so a validation that passes and a call that is then refused cannot
    disagree about arithmetic.
    """
    return TokenPrices(
        input=prices.worst_case_input,
        cached_input=prices.cached_input,
        cache_write=prices.cache_write,
        output=prices.output,
    ).cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)


def worst_case_analysis_cost_usd(config: LLMConfig) -> float:
    """What one Analysis generation costs when every token is charged dearest."""
    return _worst_case_usd(
        config.prices_for(Workload.BATCH),
        ANALYSIS_INPUT_TOKENS,
        ANALYSIS_OUTPUT_TOKENS,
    )


def worst_case_turn_cost_usd(config: LLMConfig) -> float:
    """What one Turn costs at its aggregate token ceilings.

    Output covers hidden reasoning, which bills at the output price — a Turn
    that reasons at length and answers briefly costs the same as one that does
    not, and the ceiling has to be the one that survives both.
    """
    return _worst_case_usd(
        config.prices_for(Workload.SESSION), TURN_INPUT_TOKENS, TURN_OUTPUT_TOKENS
    )


def validate_budget(config: LLMConfig) -> BudgetValidation:
    """Check the configured prices against every ceiling, and report all of them.

    Every failing ceiling is collected rather than the first one raised: an
    operator fixing a price table wants the whole list, not one more restart per
    mistake.
    """
    analysis = worst_case_analysis_cost_usd(config)
    turn = worst_case_turn_cost_usd(config)

    failures: list[BudgetFailure] = []
    failures.extend(_route_failures(config))
    failures.extend(_price_failures(config))

    if analysis > ANALYSIS_COST_CEILING_USD + MICRO_USD:
        failures.append(
            BudgetFailure(
                "analysis_cost",
                f"one Analysis at {ANALYSIS_INPUT_TOKENS:,} input and "
                f"{ANALYSIS_OUTPUT_TOKENS:,} output tokens costs "
                f"${analysis:.6f}, above the ${ANALYSIS_COST_CEILING_USD:.4f} "
                "ceiling for the whole (symbol, trading_day) pair",
            )
        )

    if turn > TURN_COST_CEILING_USD + MICRO_USD:
        failures.append(
            BudgetFailure(
                "turn_cost",
                f"one Turn at {TURN_INPUT_TOKENS:,} aggregate input and "
                f"{TURN_OUTPUT_TOKENS:,} aggregate output tokens costs "
                f"${turn:.4f}, above the ${TURN_COST_CEILING_USD:.2f} ceiling",
            )
        )

    failures.extend(_lane_failures(config, analysis, turn))

    return BudgetValidation(
        analysis_cost_usd=analysis,
        turn_cost_usd=turn,
        failures=tuple(failures),
    )


def enforce_budget_validation(config: LLMConfig) -> BudgetValidation:
    """Run the check at startup and act on it according to the feature flag.

    With Alpha Desk on, an impossible configuration refuses startup — the same
    fail-fast precedent the Universe check already sets, and for the same
    reason: the operator should meet the failure here rather than hours later
    inside a run nobody is watching. With Alpha Desk off there is nothing to
    protect, so the finding is logged and the app starts.
    """
    report = validate_budget(config)

    if report.ok:
        logger.info(report.summary())
        return report

    if config.enabled:
        raise BudgetValidationError(report)

    logger.warning("%s (Alpha Desk is disabled, so startup continues)", report.summary())
    return report


__all__ = [
    "ANALYSIS_COST_CEILING_USD",
    "ANALYSIS_INPUT_TOKENS",
    "ANALYSIS_OUTPUT_TOKENS",
    "TURN_COST_CEILING_USD",
    "TURN_INPUT_TOKENS",
    "TURN_OUTPUT_TOKENS",
    "BudgetFailure",
    "BudgetValidation",
    "BudgetValidationError",
    "enforce_budget_validation",
    "validate_budget",
    "worst_case_analysis_cost_usd",
    "worst_case_turn_cost_usd",
]
