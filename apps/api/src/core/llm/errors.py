"""The five error classes, single-sourced for both lanes.

``docs/adr/0008`` and ``docs/specs/0003`` §3 fix the taxonomy and, more
importantly, fix what each class *does*. The classes only earn their keep
because their behaviours differ:

| Class | Behaviour |
| --- | --- |
| ``ToolError`` | structured error returned to the model, which may try another approach; at most 2 attempts on the same tool |
| ``MalformedArguments`` | raise immediately; the caller fails saying the route violated its contract |
| ``GatewayTimeout`` | retried through ``tenacity``, 2 attempts with backoff, then fail |
| ``RouteRateLimited`` | **never** retried; the route answered, and its answer was "not now" |
| ``AuthUnavailable`` | **never** retried; a 401 means the channel's credential died |
| ``ModelRefusal`` | surfaced verbatim; no re-prompting to work around it |

``AuthUnavailable`` is a class rather than a status code because it was measured:
the dev route's OAuth channel died mid-test and needed manual re-auth. Retrying
a dead credential turns one failure into a run of identical ones, one per symbol.

``RouteRateLimited`` was measured the same way. A 429 used to be a
``GatewayTimeout``, which made the system say three wrong things at once: the log
read "the route timed out" when the route had answered precisely and in detail;
the reader was told the route did not respond, with no hint that the fix was
credits or a wait; and ``tenacity`` retried a daily quota that reset eight hours
later, spending two requests to be told the same thing twice. A rate limit is the
route working — it is the one failure class where the remedy belongs to the
operator rather than to a retry.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .protocol import Usage

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

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


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


@dataclass(frozen=True)
class RouteAttempt:
    """What the route managed before the call gave up on it.

    Three numbers, because they answer three different questions an operator
    asks about the same failure: ``attempts`` says whether the retry inside the
    client was spent, ``elapsed_seconds`` says whether the route was slow or
    absent, and ``bytes_received`` separates a route that never spoke from one
    that broke off mid-answer. A timeout with 0 bytes after 120 seconds and a
    timeout with 8,000 bytes after 4 seconds are different incidents with the
    same class, and before this they logged as the same line.
    """

    #: Cumulative across the client's retries. ``elapsed_seconds`` is not: it
    #: covers the last attempt only, so the pair understates real wall time by
    #: whatever the backoff between them cost.
    attempts: int = 1
    elapsed_seconds: float = 0.0
    bytes_received: int = 0

    @property
    def measured(self) -> bool:
        """Whether a transport actually timed this attempt.

        A ``GatewayTimeout`` built from a 5xx status carries no measurements —
        the route answered, and quickly. Without this the zeros read as "the
        route never spoke", which is the opposite of what happened.
        """
        return self.elapsed_seconds > 0.0


class GatewayTimeout(LLMError):
    """The route did not answer in time, or answered that it could not.

    ``attempt`` carries :class:`RouteAttempt` when the transport measured one.
    It is diagnostic only — nothing branches on it, exactly as nothing branches
    on ``RouteRateLimited.retry_after``.
    """

    def __init__(
        self,
        message: str,
        *,
        usage: Usage | None = None,
        attempt: RouteAttempt | None = None,
    ) -> None:
        super().__init__(message, usage=usage)
        self.attempt = attempt


class RouteRateLimited(LLMError):
    """The route refused this call because the caller has run out of allowance.

    Never retried, whatever the window is. A per-minute limit clears on its own
    and a per-day limit does not, but neither is helped by a second identical
    request half a second later — and the caller cannot tell the two apart from
    inside the retry loop, because the window a 429 refers to is not part of the
    status code.

    ``retry_after`` and ``reset_at`` carry whatever the response said, in
    standard HTTP headers only: ``Retry-After`` in seconds, and the unix-epoch
    ``X-RateLimit-Reset`` that rate-limited routes conventionally send beside it.
    Both are for the operator's log line. Nothing branches on them.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        reset_at: float | None = None,
        usage: Usage | None = None,
    ) -> None:
        super().__init__(message, usage=usage)
        self.retry_after = retry_after
        self.reset_at = reset_at


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

    def __init__(self, refusal: str, usage: Usage | None = None) -> None:
        super().__init__(refusal, usage=usage)
        self.refusal = refusal


# The classes below split what used to be one shape. Every 4xx that was not a
# 401, 403, 408 or 429 arrived as a bare ``LLMError``, which made a retired
# model, a prompt over the context window and a tool schema the route would not
# accept indistinguishable in the log and in the ops snapshot — three failures
# whose remedies have nothing in common.
#
# All five subclass ``LLMError``, so every ``except LLMError`` written before
# them still catches them: this is a pure addition, and a caller that does not
# know about them behaves exactly as it did.


class ContextOverflow(LLMError):
    """The messages sent do not fit the model's context window.

    Distinct from :class:`OutputCapExceeded` because the fix is the opposite
    one. Here the *input* is too large and the remedy is to compress the
    transcript; there the input fits and it is the reserved output ceiling that
    pushes the total over. Both routes word the two conditions similarly enough
    that classifying them together would send half the cases to the wrong fix.
    """


class OutputCapExceeded(LLMError):
    """The requested output ceiling does not fit beside the input.

    The transcript is fine. Trimming it is wasted work and loses evidence the
    Turn already paid for; what has to come down is ``max_completion_tokens``.
    """


class ContentPolicyBlocked(LLMError):
    """The route's own filter refused the request before the model saw it.

    Terminal and never retried: a filter that refused this text refuses it
    again, and this is the route talking rather than the model — so unlike
    :class:`ModelRefusal` there are no words of the model's to carry.
    """


class ModelUnavailable(LLMError):
    """The route does not serve the model that was asked for.

    A retired model, a typo in configuration and a route that dropped an
    endpoint all land here. Nothing in this class is transient, which is why it
    is not a :class:`GatewayTimeout`.
    """


class SchemaRejected(LLMError):
    """The route refused the tool schemas or the tool choice.

    Logged loudly because it is ours to fix: the Tool Catalog emits these
    schemas, so a route rejecting them is a defect in this repository rather
    than a condition of the world.
    """


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
    rate_limits: int = 0
    auth_failures: int = 0
    refusals: int = 0

    def record_malformed_arguments(self, detail: str) -> None:
        self.malformed_arguments += 1
        logger.error(
            "The route returned tool-call arguments that are not JSON (%d so far "
            "this process): %s",
            self.malformed_arguments,
            redact(detail),
        )

    def record_gateway_timeout(self, detail: str) -> None:
        self.gateway_timeouts += 1
        logger.warning("The LLM route timed out: %s", redact(detail))

    def record_rate_limit(self, detail: str) -> None:
        self.rate_limits += 1
        # Warning rather than error: nothing is broken, and the sentence says
        # what to do about it instead of what failed.
        logger.warning("The LLM route is out of allowance: %s", redact(detail))

    def record_auth_failure(self, detail: str) -> None:
        self.auth_failures += 1
        # Redacted with more reason than anywhere else in this file: a 401 body
        # is the single most likely place for a route to quote back the key it
        # just rejected, and the whole point of naming a dead credential in a log
        # is defeated if naming it means rotating it.
        logger.error("The LLM route rejected the credential: %s", redact(detail))

    def record_refusal(self, detail: str) -> None:
        self.refusals += 1
        logger.info("The model refused: %s", redact(detail))

    def reset(self) -> None:
        self.malformed_arguments = 0
        self.gateway_timeouts = 0
        self.rate_limits = 0
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

    def remaining(self, tool_name: str) -> int:
        """How many attempts are left, which a caller dispatching a round of
        parallel calls needs before any of them has failed yet."""
        return max(0, self._limit - self._attempts.get(tool_name, 0))

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


def _rate_limit_window(
    headers: Mapping[str, str],
) -> tuple[float | None, float | None]:
    """``Retry-After`` in seconds and the epoch a limit resets at, if sent.

    Header names are matched case-insensitively and a value that is not a number
    is dropped rather than raised on: this runs on the failure path, and a route
    with an unparseable header is still a route that rate-limited the call.
    ``X-RateLimit-Reset`` is sent in seconds by some routes and milliseconds by
    others, so a value far past the year-3000 mark is read as milliseconds.
    """

    lowered = {name.lower(): value for name, value in headers.items()}

    def number(name: str) -> float | None:
        raw = lowered.get(name)
        if raw is None:
            return None
        try:
            return float(str(raw).strip())
        except ValueError:
            return None

    reset_at = number("x-ratelimit-reset")
    if reset_at is not None and reset_at > 32_503_680_000:
        reset_at /= 1000
    return number("retry-after"), reset_at


# What a credential looks like in a body the route echoed back, and in a header
# name a route names in its complaint. An error body is the one string in this
# module that is copied verbatim into a log line, so it is the one string that
# has to be scrubbed first: a route that quotes the request it refused quotes
# the ``Authorization`` header with it.
#
# Matched on shape rather than on a list of known providers. A prefix list goes
# stale the day a route is added, and the cost of over-redacting an error body
# is a less specific log line, while the cost of under-redacting it once is a
# rotated key.
_SECRET_PATTERNS = (
    # ``Authorization: <scheme> <credential>``, however spaced, whatever the
    # scheme. The scheme has to be swallowed with the credential: matched as
    # ``authorization\s*[:=]\s*\S+`` the ``\S+`` stops at the first space, so
    # for ``Basic``, ``Token`` or ``ApiKey`` the *scheme word* was redacted and
    # the credential survived — a line that reads as though it had been scrubbed,
    # which is worse than one that plainly has not.
    re.compile(r"(?i)\b(authorization)\b[\"\']?\s*[:=]\s*[\"\']?[^\"\',}\]\n]+"),
    # ``Bearer <token>`` on its own, without the header name in front of it.
    re.compile(r"(?i)\b(bearer)\s+[\w\-.~+/=]{8,}"),
    # A JSON, form or query field whose *name* says it holds a credential.
    # ``key`` and ``token`` are included bare because that is how they arrive in
    # an echoed URL (``?key=AIza…``) and in a cookie (``session=eyJ…``).
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token"
        r"|client[_-]?secret|secret|password|passwd|key|token|session|auth)"
        r"\b[\"\']?\s*[:=]\s*[\"\']?[\w\-.~+/=]{4,}"
    ),
    # A bare provider-style key, which routes echo without naming the field.
    re.compile(r"\b(sk|pk|rk|AIza|ghp|gho|xox[bpsa])[-_]?[\w\-]{12,}"),
    # A JWT, which is recognisable by shape alone and is always a credential.
    re.compile(r"\b(eyJ)[\w\-]{8,}\.[\w\-]+\.?[\w\-]*"),
)

REDACTED = "<redacted>"


def redact(text: str) -> str:
    """Strip anything credential-shaped out of a string bound for a log.

    Called on the route's own words before they are logged, never on the words
    themselves as they travel to a caller: the point is that a key which reached
    a log file has to be rotated, and the log file is the only place these
    strings are durable.

    Over-redaction is the accepted failure mode. A field named ``secret`` whose
    value was harmless reads as ``secret=<redacted>``, which costs an operator
    one guess; the other direction costs a key rotation.
    """

    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(
            lambda match: f"{match.group(1)} {REDACTED}"
            if match.lastindex
            else REDACTED,
            text,
        )
    return text


# The 400 taxonomy, matched on the body because the status code carries none of
# it. Order is load bearing exactly once: an output-cap complaint names a token
# ceiling too, so it is tested before the context-window markers or every one of
# them would be read as an oversized transcript and answered by trimming a
# transcript that fits.
#
# **Naming a parameter is not complaining about its size.** Three real 400 bodies
# name ``max_tokens`` without the ceiling being the problem: *"Unsupported
# parameter: 'max_tokens' is not supported with this model"* (a request-builder
# defect), *"Invalid value for max_tokens"* (also ours), and any route that echoes
# the request it refused — which is the premise ``redact`` exists for, so it is
# the common case rather than the exotic one. Each needs a *size* word beside the
# parameter name, or the ops split Phase 1 exists to produce is wrong and the
# recovery built on it lowers a ceiling that was never too high.
#
# Every list is deliberately tight. A marker loose enough to catch one more
# phrasing is a marker loose enough to misfile an unrelated 400, and an
# unrecognised body falling through to ``LLMError`` is the safe outcome by
# construction — it is what happened before any of this existed.
_OUTPUT_CAP_NAMES = (
    "max_tokens",
    "max_completion_tokens",
    "max output tokens",
    "max_output_tokens",
)
#: A size complaint rather than a mention. Required beside a parameter name
#: above before the body counts as an output-cap failure.
_SIZE_COMPLAINTS = (
    "too large",
    "too long",
    "too big",
    "exceed",
    "greater than",
    "at most",
    "must be less",
)
_CONTEXT_OVERFLOW_MARKERS = (
    "prompt is too long",
    "prompt too long",
    "context_length_exceeded",
    "context length",
    "maximum context",
    "reduce the length of the messages",
    "input is too long",
)
_CONTENT_POLICY_MARKERS = (
    "content_policy",
    "content policy",
    "content_filter",
    "content filter",
    "prohibited_content",
)
_MODEL_UNAVAILABLE_MARKERS = (
    "model_not_found",
    "no such model",
    "unknown model",
    "is not a valid model",
    "does not exist or you do not have access",
    "no endpoints found",
    "model is not supported",
)
#: ``deprecated`` alone matches a complaint about a *parameter* being retired,
#: which is ours to fix and not a reason to change model. Nor is "the word
#: ``model`` appears somewhere" enough: *"The parameter temperature has been
#: deprecated for this model"* contains it and means the opposite. The model has
#: to be the **subject** of the sentence.
_MODEL_DEPRECATED = re.compile(
    r"(?i)\bmodel\b[^.]{0,60}?\b(?:has been|is|was)\s+deprecated"
)
_SCHEMA_REJECTED_MARKERS = (
    "invalid schema",
    "invalid_function_parameters",
    "tool_choice",
    "function.parameters",
    "invalid tool schema",
    "invalid tools",
    "tools is not supported",
)


def _classify_refused_request(status_code: int, body: str) -> LLMError:
    """Give a refused request a class, or leave it the shape it had.

    Split out from :func:`classify_status` so the ordering above can be read and
    tested on its own. The fallthrough is the pre-existing behaviour verbatim:
    nothing here can turn a body it does not recognise into a class, and so
    nothing here can send a recovery path after the wrong remedy.
    """

    lowered = body.lower()

    def says(markers: tuple[str, ...]) -> bool:
        return any(marker in lowered for marker in markers)

    if says(_OUTPUT_CAP_NAMES) and says(_SIZE_COMPLAINTS):
        return OutputCapExceeded(
            f"the requested output ceiling does not fit ({status_code}): {body}"
        )
    if says(_CONTEXT_OVERFLOW_MARKERS):
        return ContextOverflow(
            f"the transcript does not fit the context window ({status_code}): {body}"
        )
    if says(_CONTENT_POLICY_MARKERS):
        return ContentPolicyBlocked(
            f"the route's content filter refused the request ({status_code}): {body}"
        )
    if says(_MODEL_UNAVAILABLE_MARKERS) or _MODEL_DEPRECATED.search(body):
        return ModelUnavailable(
            f"the route does not serve this model ({status_code}): {body}"
        )
    if says(_SCHEMA_REJECTED_MARKERS):
        return SchemaRejected(
            f"the route refused the tool schemas ({status_code}): {body}"
        )
    return LLMError(f"the route refused the request ({status_code}): {body}")


def classify_status(
    status_code: int,
    body: str,
    headers: Mapping[str, str] | None = None,
) -> LLMError:
    """Turn one real upstream condition into its declared class.

    Single-sourced here so the nightly lane and the interactive lane cannot
    disagree about what a 401 means.
    """
    if status_code in (401, 403):
        return AuthUnavailable(
            f"the route rejected the configured credential ({status_code}): {body}"
        )
    if status_code == 429:
        retry_after, reset_at = _rate_limit_window(headers or {})
        return RouteRateLimited(
            f"the route is out of allowance ({status_code}): {body}",
            retry_after=retry_after,
            reset_at=reset_at,
        )
    if status_code in (408, 502, 503, 504):
        return GatewayTimeout(f"the route did not answer ({status_code}): {body}")
    if 500 <= status_code < 600:
        return GatewayTimeout(f"the route failed ({status_code}): {body}")
    if 400 <= status_code < 500:
        # 404 is in scope alongside 400: a route that does not serve a model
        # says so with either status, and the remedy is the same one.
        return _classify_refused_request(status_code, body)
    return LLMError(f"the route refused the request ({status_code}): {body}")


__all__ = [
    "MAX_GATEWAY_ATTEMPTS",
    "MAX_TOOL_ATTEMPTS",
    "REDACTED",
    "AuthUnavailable",
    "ContentPolicyBlocked",
    "ContextOverflow",
    "GatewayTimeout",
    "RouteRateLimited",
    "LLMError",
    "LLMMetrics",
    "MalformedArguments",
    "ModelRefusal",
    "ModelUnavailable",
    "OutputCapExceeded",
    "RouteAttempt",
    "SchemaRejected",
    "ToolAttempts",
    "ToolError",
    "classify_status",
    "llm_metrics",
    "redact",
    "tool_error_result",
]
