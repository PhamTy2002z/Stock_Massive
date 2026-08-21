"""The LLM boundary: one protocol, one transport, one error taxonomy.

``docs/adr/0008`` keeps the agent loop hand-rolled over this package rather than
inside a framework, for a reason this package is the whole of: the failures on
this channel class are silent. A measured gateway keyed streamed tool calls on a
local counter instead of the upstream index and concatenated two calls'
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
from .admission import (
    BUDGET_REFUSAL_REASONS,
    BudgetLane,
    BudgetRefusal,
    CallOwner,
    OwnerType,
    Reservation,
    SpendAdmission,
    SpendRequest,
    TurnState,
    check_candidate_shape,
)
from .client import MissingSpendReservation, ReservedLLMClient, build_client
from .config import (
    BudgetLanes,
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
    Workload,
    llm_config_from_settings,
)
from .errors import (
    AuthUnavailable,
    ContentPolicyBlocked,
    ContextOverflow,
    GatewayTimeout,
    RouteAttempt,
    RouteRateLimited,
    LLMError,
    LLMMetrics,
    MalformedArguments,
    ModelRefusal,
    ModelUnavailable,
    OutputCapExceeded,
    SchemaRejected,
    ToolAttempts,
    ToolError,
    llm_metrics,
    redact,
    tool_error_result,
)
from .protocol import (
    Completion,
    CompletionRequest,
    JsonSchemaFormat,
    LLMClient,
    Message,
    Role,
    ToolCall,
    ToolSchema,
    Usage,
)
from .probe import (
    CapabilityProbe,
    CapabilityProbeError,
    ProbeCheck,
    ProbeResult,
    clear_capability_probe_cache,
    enforce_capability_probe,
)

__all__ = [
    "BUDGET_REFUSAL_REASONS",
    "AuthUnavailable",
    "BudgetLane",
    "BudgetRefusal",
    "BudgetLanes",
    "BudgetValidation",
    "BudgetValidationError",
    "Completion",
    "CompletionRequest",
    "CallOwner",
    "CapabilityProbe",
    "CapabilityProbeError",
    "ContentPolicyBlocked",
    "ContextOverflow",
    "GatewayTimeout",
    "ModelUnavailable",
    "OutputCapExceeded",
    "RouteAttempt",
    "RouteRateLimited",
    "SchemaRejected",
    "JsonSchemaFormat",
    "LLMClient",
    "LLMConfig",
    "LLMError",
    "LLMMetrics",
    "LLMRoute",
    "MalformedArguments",
    "MissingSpendReservation",
    "Message",
    "ModelRefusal",
    "OwnerType",
    "PricingTable",
    "ProbeCheck",
    "ProbeResult",
    "Role",
    "Reservation",
    "SpendAdmission",
    "ReservedLLMClient",
    "TokenPrices",
    "ToolAttempts",
    "ToolCall",
    "ToolError",
    "ToolSchema",
    "SpendRequest",
    "check_candidate_shape",
    "TurnState",
    "Usage",
    "Workload",
    "build_client",
    "clear_capability_probe_cache",
    "enforce_budget_validation",
    "enforce_capability_probe",
    "llm_config_from_settings",
    "llm_metrics",
    "redact",
    "tool_error_result",
    "validate_budget",
]
