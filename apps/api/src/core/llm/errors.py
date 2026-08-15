"""The five error classes, single-sourced for both lanes.

``docs/adr/0008`` and ``docs/specs/0003`` §3 fix the taxonomy and, more
importantly, fix what each class *does*. The classes only earn their keep
because their behaviours differ:

| Class | Behaviour |
| --- | --- |
| ``ToolError`` | structured error returned to the model, which may try another approach; at most 2 attempts on the same tool |
| ``MalformedArguments`` | raise immediately; the caller fails saying the route violated its contract |
| ``GatewayTimeout`` | retried through ``tenacity``, 2 attempts with backoff, then fail |
| ``AuthUnavailable`` | **never** retried; a 401 means the channel's credential died |
| ``ModelRefusal`` | surfaced verbatim; no re-prompting to work around it |

``AuthUnavailable`` is a class rather than a status code because it was measured:
the dev route's OAuth channel died mid-test and needed manual re-auth. Retrying
a dead credential turns one failure into a run of identical ones, one per symbol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ``docs/specs/0003`` §3: the model may try another approach, but not the same
# tool forever. Two attempts is enough for a transient failure and short enough
# that a broken tool cannot spend a Turn's budget rediscovering it.
MAX_TOOL_ATTEMPTS = 2

# ``gateway_timeout`` retries twice in total — one retry after the first
# failure — because a third attempt on a route that has already timed out twice
# spends more of a user's patience than it is likely to buy back.
MAX_GATEWAY_ATTEMPTS = 2


class LLMError(RuntimeError):
    """Any failure at the LLM boundary."""


class ToolError(LLMError):
    """A tool the model called did not do what it was asked.

    Not raised to the caller by default: it is handed back to the model as a
    structured result, because a model that is told a tool failed can pick a
    different one, and a Turn that dies on a failing tool cannot.
    """

    def __init__(self, message: str, tool_name: str = "", tool_call_id: str = "") -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id


class MalformedArguments(LLMError):
    """A tool call whose ``arguments`` are not JSON.

    Raised immediately and never handed back. A measured gateway keyed streamed
    tool calls on a local counter instead of the upstream index and concatenated
    two calls' arguments into invalid JSON under the wrong id, while returning
    200 — so garbage here is not a model mistake to be re-prompted around, it is
    the route violating its contract.
    """


class GatewayTimeout(LLMError):
    """The route did not answer in time, or answered that it could not."""


class AuthUnavailable(LLMError):
    """The channel's credential died. Never retried.

    Interactive Turns surface *re-auth needed*; the nightly lane marks the
    symbol failed-retryable and pauses the dispatcher rather than walking the
    rest of the cohort to record the same failure against every symbol.
    """


class ModelRefusal(LLMError):
    """The model declined, and its own words are the answer.

    Carried verbatim. Re-prompting to get around a refusal is how a system ends
    up arguing with its own model on a user's behalf.
    """

    def __init__(self, refusal: str) -> None:
        super().__init__(refusal)
        self.refusal = refusal


@dataclass
class LLMMetrics:
    """What the operator watches, and what nothing here acts on automatically.

    ``malformed_arguments`` is counted and logged loudly, and that is all: the
    operator flips ``alpha_desk_enabled`` by hand (``docs/adr/0008``). A cutoff
    that fires on two errors is a mechanism that can cause its own outage, and
    with a handful of internal users whoever notices is also whoever can fix it.
    """

    malformed_arguments: int = 0
    gateway_timeouts: int = 0
    auth_failures: int = 0
    refusals: int = 0

    def record_malformed_arguments(self, detail: str) -> None:
        self.malformed_arguments += 1
        logger.error(
            "The route returned tool-call arguments that are not JSON (%d so far "
            "this process): %s",
            self.malformed_arguments,
            detail,
        )

    def record_gateway_timeout(self, detail: str) -> None:
        self.gateway_timeouts += 1
        logger.warning("The LLM route timed out: %s", detail)

    def record_auth_failure(self, detail: str) -> None:
        self.auth_failures += 1
        logger.error("The LLM route rejected the credential: %s", detail)

    def record_refusal(self, detail: str) -> None:
        self.refusals += 1
        logger.info("The model refused: %s", detail)

    def reset(self) -> None:
        self.malformed_arguments = 0
        self.gateway_timeouts = 0
        self.auth_failures = 0
        self.refusals = 0


_metrics = LLMMetrics()


def llm_metrics() -> LLMMetrics:
    """The counters every client in this process shares."""
    return _metrics


class ToolAttempts:
    """How many times the model has been allowed to retry one tool.

    Counted per tool name rather than per call id: the point is to stop the
    model going round on a tool that does not work, and a fresh call id every
    round is exactly what that loop looks like.
    """

    def __init__(self, limit: int = MAX_TOOL_ATTEMPTS) -> None:
        self._limit = limit
        self._attempts: dict[str, int] = {}

    def record_failure(self, tool_name: str) -> int:
        self._attempts[tool_name] = self._attempts.get(tool_name, 0) + 1
        return self._attempts[tool_name]

    def may_attempt(self, tool_name: str) -> bool:
        return self._attempts.get(tool_name, 0) < self._limit

    def exhausted(self, tool_name: str) -> bool:
        return not self.may_attempt(tool_name)


def tool_error_result(tool_call_id: str, tool_name: str, message: str) -> dict[str, Any]:
    """The structured error a failed tool hands back to the model.

    A shape rather than prose, so the model can tell a tool that failed from a
    tool that answered "nothing found" — which are different facts about the
    world and lead to different next moves.
    """
    return {
        "tool_call_id": tool_call_id,
        "tool": tool_name,
        "error": message,
        "status": "tool_error",
    }


def classify_status(status_code: int, body: str) -> LLMError:
    """Turn one real upstream condition into its declared class.

    Single-sourced here so the nightly lane and the interactive lane cannot
    disagree about what a 401 means.
    """
    if status_code in (401, 403):
        return AuthUnavailable(
            f"the route rejected the configured credential ({status_code}): {body}"
        )
    if status_code in (408, 429, 502, 503, 504):
        return GatewayTimeout(f"the route did not answer ({status_code}): {body}")
    if 500 <= status_code < 600:
        return GatewayTimeout(f"the route failed ({status_code}): {body}")
    return LLMError(f"the route refused the request ({status_code}): {body}")


__all__ = [
    "MAX_GATEWAY_ATTEMPTS",
    "MAX_TOOL_ATTEMPTS",
    "AuthUnavailable",
    "GatewayTimeout",
    "LLMError",
    "LLMMetrics",
    "MalformedArguments",
    "ModelRefusal",
    "ToolAttempts",
    "ToolError",
    "classify_status",
    "llm_metrics",
    "tool_error_result",
]
