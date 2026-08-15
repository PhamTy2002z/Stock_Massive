"""The LLM boundary: one protocol, one transport, one error taxonomy.

``docs/adr/0008`` keeps the agent loop hand-rolled over this package rather than
inside a framework, for a reason this package is the whole of: the failures on
this channel class are silent. A measured gateway keyed streamed tool calls on
a local counter instead of the upstream index and concatenated two calls'
arguments into invalid JSON under the wrong id — while returning 200. Nothing
downstream can notice that; it only makes the answers wrong.

So the boundary is where the assertions live: the JSON-parse invariant on tool
arguments, ``auth_unavailable`` as a first-class class, and Budget Validation
before anything reaches the network at all.
"""

from .budget import (
    BudgetValidation,
    BudgetValidationError,
    enforce_budget_validation,
    validate_budget,
)
from .config import (
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
    Workload,
    llm_config_from_settings,
)

__all__ = [
    "BudgetValidation",
    "BudgetValidationError",
    "LLMConfig",
    "LLMRoute",
    "PricingTable",
    "TokenPrices",
    "Workload",
    "enforce_budget_validation",
    "llm_config_from_settings",
    "validate_budget",
]
