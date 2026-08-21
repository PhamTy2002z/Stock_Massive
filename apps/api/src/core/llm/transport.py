"""One OpenAI-compatible transport behind the reserved ``LLMClient``.

Built on ``httpx`` without a provider SDK or agent framework. Retry lives one
layer above this transport, where each attempt can receive its own committed
reservation; retrying here would silently make two paid requests against one
ledger row.

What the hand-rolling buys, concretely:

- streamed tool calls assembled by the **upstream index** (``streaming.py``),
- the **JSON-parse invariant** on every returned ``arguments``,
- ``auth_unavailable`` as a first-class class that is **never retried**.

**This transport never changes the model it was given.** A different model has
different prices, so swapping one in under a reservation made for another spends
against a ceiling that was never checked (``docs/adr/0014``). Failover exists one
layer up, in ``client.py``, precisely because a reservation can be made there:
the client asks admission again, for the other model and under the workload that
model is priced in, and ``SpendAdmission.reserve`` refuses the pair if they do
not match.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Mapping
from typing import Any

import httpx
from .config import LLMConfig, clamp_timeout
from .errors import (
    AuthUnavailable,
    ContentPolicyBlocked,
    ContextOverflow,
    DeadlineExpired,
    GatewayTimeout,
    RouteRateLimited,
    LLMError,
    ModelRefusal,
    ModelUnavailable,
    OutputCapExceeded,
    RouteAttempt,
    SchemaRejected,
    classify_status,
    llm_metrics,
    redact,
)
from .protocol import CACHE_CONTROL, Completion, CompletionRequest, Role, Usage
from .streaming import StreamAssembler, parse_tool_calls

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_PATH = "/chat/completions"

# The tool_choice values that travel as themselves. Anything else is read as a
# tool name and forced, which is what the Capability Probe checks is honoured.
PASSTHROUGH_TOOL_CHOICES = frozenset({"auto", "none", "required"})

# What a thinking route calls the field, and the smallest value it accepts. An
# empty string is refused; a space is not.
REASONING_HISTORY_KEY = "reasoning_content"
REASONING_HISTORY_PLACEHOLDER = " "

SSE_DATA_PREFIX = "data:"
SSE_DONE = "[DONE]"

# How much of a refused response's body is read, and for how long. Ported from
# ``openclaw#95108``: ``read()`` on a stream is unbounded in two directions at
# once — a body that never ends, and a server that opens one and then stops
# sending — and the second is the one that hurts, because the request already
# failed and this is the error path.
#
# 8 KiB is far more than the 500 characters classification looks at and far less
# than a body worth holding in memory on a failure. The deadline is enforced by
# ``asyncio.wait_for`` around the whole read: unlike the synchronous case, where
# ``iter_bytes`` blocks *inside* the socket read and a check between chunks never
# runs, an async read yields to the event loop, so the timer fires and the
# response is closed under it.
ERROR_BODY_MAX_BYTES = 8_192
ERROR_BODY_MAX_SECONDS = 5.0

# How many trailing non-system messages carry a cache breakpoint. Two, so the
# prefix that grew by one exchange is still readable from cache on the next call;
# a breakpoint on every message would spend the route's small allowance of them
# on content that changes before it is read back.
CACHE_TAIL_MESSAGES = 2


class OpenAICompatibleTransport:
    """The network transport used only behind the reserved public client."""

    def __init__(
        self,
        config: LLMConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._http = http_client or self._new_client()

    def _new_client(self) -> httpx.AsyncClient:
        """One HTTP client, with this process's own deadline on the socket.

        Clamped rather than passed through: ``clamp_timeout`` explains why a
        deadline nobody can express is a crash rather than a long wait.
        """
        return httpx.AsyncClient(
            timeout=httpx.Timeout(clamp_timeout(self._config.request_timeout_seconds))
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def rebuild(self) -> bool:
        """Throw this transport's connections away and build fresh ones.

        Called after our own deadline expired, which a connection wedged in the
        pool reproduces on the next call and on every call after it. The cost is
        one handshake; the alternative is a route that looks dead until the
        process restarts.

        Answers ``False`` when the client was injected: a caller that supplied
        its own ``AsyncClient`` owns its lifecycle, and closing it here would
        break the next user of it rather than this one.
        """
        if not self._owns_client:
            return False
        stale = self._http
        self._http = self._new_client()
        try:
            await stale.aclose()
        except Exception as exc:  # noqa: BLE001 - the point was to stop using it
            logger.debug("The stale LLM transport did not close cleanly: %s", exc)
        return True

    async def dispatch(self, request: CompletionRequest) -> Completion:
        """Make exactly one paid attempt, returning or raising a typed result.

        A caller asks for streaming; the route decides whether it can be given.
        Both shapes assemble tool calls through the same rule, and the whole
        response is the one that also works on a route which omits the upstream
        index — so a route declared non-streaming is downgraded here rather than
        failing later inside the assembler.
        """
        if self._streaming(request):
            return await self._streamed(request)
        return await self._whole(request)

    def _messages(self, request: CompletionRequest) -> list[dict[str, Any]]:
        """The transcript on the wire, with whatever this route insists on.

        A thinking route wants its own reasoning back beside the tool calls it
        made. This transcript does not keep that text — reasoning is not evidence,
        and nothing downstream may cite it — so what goes out is a placeholder
        that satisfies the requirement and asserts nothing. Measured on DeepSeek
        v4-pro through TokenRouter: a single space is accepted where an empty
        string is refused.

        Only assistant turns that actually carry tool calls are touched, so a
        route without the requirement sees exactly what it saw before.
        """
        cache_control = self._config.route.prompt_cache_control
        wire = [message.as_wire(cache_control=cache_control) for message in request.messages]
        if cache_control:
            _mark_tail_breakpoints(wire)
        if not self._config.route.reasoning_history:
            return wire
        for payload in wire:
            if payload.get("role") == Role.ASSISTANT.value and payload.get("tool_calls"):
                payload.setdefault(REASONING_HISTORY_KEY, REASONING_HISTORY_PLACEHOLDER)
        return wire

    def _streaming(self, request: CompletionRequest) -> bool:
        """Whether this call streams: the caller's wish and the route's answer."""
        return request.stream and self._config.route.streaming

    # -- the two response shapes ------------------------------------------

    async def _streamed(self, request: CompletionRequest) -> Completion:
        assembler = StreamAssembler(model=request.model)
        # Counted on the way past rather than reconstructed afterwards: on the
        # failure path there is no response object left to ask, and "how much
        # arrived before it stopped" is the one number that separates a route
        # that never spoke from a route that broke off mid-answer.
        started = time.monotonic()
        received = 0

        try:
            async with self._http.stream(
                "POST",
                self._url(),
                json=self._body(request),
                headers=self._headers(),
            ) as response:
                if response.status_code >= 400:
                    body = await _read_error_body(response)
                    raise self._classified(
                        response.status_code, body, response.headers
                    )
                async for line in response.aiter_lines():
                    # Encoded length, because the field is called bytes and a
                    # Vietnamese answer is two to three bytes per character —
                    # counting characters would understate a broken stream by
                    # the same factor and make the number unusable for the one
                    # thing it is for.
                    received += len(line.encode())
                    chunk = _decode_sse_line(line)
                    if chunk is not None:
                        assembler.add_chunk(chunk)
        except httpx.RequestError as exc:
            # A route that could not be reached and a route that stopped talking
            # are both retryable, but they are not the same fact: a
            # ``TimeoutException`` is *our* deadline expiring, which a wedged
            # connection reproduces on the next call, so it is classified as one
            # and the client rebuilds this transport before asking again.
            raise self._timeout(
                exc,
                attempt=RouteAttempt(
                    elapsed_seconds=time.monotonic() - started,
                    bytes_received=received,
                ),
            ) from exc

        if assembler.refusal:
            llm_metrics().record_refusal(assembler.refusal)
            raise ModelRefusal(
                assembler.refusal,
                usage=_usage(assembler.usage_payload),
            )

        usage = _usage(assembler.usage_payload)
        try:
            tool_calls = assembler.tool_calls()
        except LLMError as exc:
            exc.usage = usage
            raise
        return Completion(
            model=assembler.model or request.model,
            text=assembler.text,
            # Parsed here rather than as they arrive: a call is only complete
            # when the stream ends, and half a JSON object never parses.
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=assembler.finish_reason,
            request_id=assembler.request_id,
        )

    async def _whole(self, request: CompletionRequest) -> Completion:
        started = time.monotonic()
        try:
            response = await self._http.post(
                self._url(),
                json=self._body(request),
                headers=self._headers(),
            )
        except httpx.RequestError as exc:
            # Split the same way the streamed path splits it: our own expiry is
            # a ``DeadlineExpired``, an unreachable route is a ``GatewayTimeout``.
            #
            # No byte count: a non-streaming request either has its whole body
            # or has none of it, so the number would always be zero and would
            # read as information.
            raise self._timeout(
                exc,
                attempt=RouteAttempt(elapsed_seconds=time.monotonic() - started),
            ) from exc

        if response.status_code >= 400:
            raise self._classified(
                response.status_code, response.text, response.headers
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMError(f"the route answered with something that is not JSON: {exc}")

        choices = payload.get("choices") or []
        if not choices:
            raise LLMError("the route answered with no choices at all")

        message = choices[0].get("message") or {}
        refusal = message.get("refusal")
        if refusal:
            llm_metrics().record_refusal(str(refusal))
            raise ModelRefusal(str(refusal), usage=_usage(payload.get("usage")))

        usage = _usage(payload.get("usage"))
        try:
            tool_calls = parse_tool_calls(message.get("tool_calls"))
        except LLMError as exc:
            exc.usage = usage
            raise
        return Completion(
            model=str(payload.get("model") or request.model),
            text=message.get("content"),
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=str(choices[0].get("finish_reason") or "stop"),
            request_id=str(payload["id"]) if payload.get("id") else None,
        )

    # -- the request ------------------------------------------------------

    def _url(self) -> str:
        return f"{self._config.route.base_url.rstrip('/')}{CHAT_COMPLETIONS_PATH}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.route.api_key}",
            "Content-Type": "application/json",
        }

    def _body(self, request: CompletionRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": self._messages(request),
            "stream": self._streaming(request),
        }

        if self._streaming(request):
            # Without this a streamed response carries no usage at all, and a
            # call with no usage cannot be reconciled against its reservation.
            body["stream_options"] = {"include_usage": True}

        if request.tools:
            body["tools"] = [tool.as_wire() for tool in request.tools]
            body["tool_choice"] = _tool_choice(request.tool_choice)
            body["parallel_tool_calls"] = request.parallel_tool_calls

        if request.response_format is not None:
            body["response_format"] = request.response_format.as_wire()
        if request.max_output_tokens is not None:
            body["max_completion_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature

        return body

    # -- failures ---------------------------------------------------------

    def _classified(
        self,
        status_code: int,
        body: str,
        headers: Mapping[str, str] | None = None,
    ) -> LLMError:
        error = classify_status(status_code, body[:500], headers)
        if isinstance(error, AuthUnavailable):
            llm_metrics().record_auth_failure(str(error))
        elif isinstance(error, RouteRateLimited):
            llm_metrics().record_rate_limit(str(error))
        elif isinstance(error, GatewayTimeout):
            llm_metrics().record_gateway_timeout(str(error))
        elif isinstance(error, SchemaRejected):
            # Loud because it is ours: the Tool Catalog wrote the schemas this
            # route just refused, so this is a defect here rather than a
            # condition of the world.
            logger.error("The LLM route refused our tool schemas: %s", redact(str(error)))
        elif isinstance(
            error,
            (ContextOverflow, OutputCapExceeded, ContentPolicyBlocked, ModelUnavailable),
        ):
            # One line per class at the boundary, so the ops snapshot's counts
            # and the log agree about what a refused request actually was. The
            # body is redacted: a route that quotes the request it refused
            # quotes the credential with it.
            logger.warning(
                "The LLM route refused the request as %s: %s",
                type(error).__name__,
                redact(str(error)),
            )
        return error

    def _timeout(
        self, exc: Exception, *, attempt: RouteAttempt | None = None
    ) -> GatewayTimeout:
        """The transport's own failure, classified by whose deadline it was.

        Counted under one metric either way. The counter answers "how often does
        the route not answer", which both of these are; the class answers "what
        should be done about it", which they differ on.
        """
        if isinstance(exc, httpx.TimeoutException):
            error: GatewayTimeout = DeadlineExpired(
                f"this process stopped waiting for the route: {exc}", attempt=attempt
            )
        else:
            error = GatewayTimeout(f"the route could not be reached: {exc}", attempt=attempt)
        llm_metrics().record_gateway_timeout(str(error))
        return error


def _mark_tail_breakpoints(wire: list[dict[str, Any]]) -> None:
    """Put a cache breakpoint on the last two non-system messages.

    Done on the wire payload rather than on the ``Message`` objects: where the
    stable prefix ends is knowledge the *caller* has and states in segments,
    while where the conversation currently ends is knowledge only the request
    has — and it changes on every call, so it is not a property to freeze into
    the transcript.

    A message whose content is not a plain string is left alone. It either
    already carries blocks of its own, in which case its last block gets the
    marker, or it carries none, in which case there is nothing to mark.
    """
    marked = 0
    for index in range(len(wire) - 1, -1, -1):
        payload = wire[index]
        if payload.get("role") == Role.SYSTEM.value:
            continue
        content = payload.get("content")
        if isinstance(content, str):
            payload["content"] = [
                {"type": "text", "text": content, "cache_control": dict(CACHE_CONTROL)}
            ]
        elif isinstance(content, list) and content:
            block = dict(content[-1])
            block["cache_control"] = dict(CACHE_CONTROL)
            payload["content"] = [*content[:-1], block]
        else:
            continue
        marked += 1
        if marked >= CACHE_TAIL_MESSAGES:
            return


async def _read_error_body(response: httpx.Response) -> str:
    """As much of a refused body as classification needs, and no more.

    Bounded in bytes and in time, and the response is closed either way: a route
    that opens an error body and then stops sending would otherwise hold this
    call for the whole request deadline *after* it has already failed.

    Whatever arrived is returned. A partial body classifies as well as a whole
    one — the markers ``classify_status`` matches are at the start of a message,
    not the end — and an empty string falls through to the unclassified branch,
    which is the pre-existing behaviour.
    """

    chunks: list[bytes] = []
    received = 0

    async def collect() -> None:
        nonlocal received
        async for chunk in response.aiter_bytes():
            chunks.append(chunk)
            received += len(chunk)
            if received >= ERROR_BODY_MAX_BYTES:
                return

    try:
        await asyncio.wait_for(collect(), timeout=ERROR_BODY_MAX_SECONDS)
    except (TimeoutError, asyncio.TimeoutError):
        logger.warning(
            "The LLM route opened an error body and stopped sending; keeping the "
            "%d byte(s) that arrived",
            received,
        )
    except (httpx.RequestError, httpx.StreamError) as exc:
        logger.debug("The LLM route's error body could not be read: %s", exc)
    finally:
        try:
            await response.aclose()
        except Exception as exc:  # noqa: BLE001 - already on the failure path
            logger.debug("The refused response did not close cleanly: %s", exc)

    return b"".join(chunks)[:ERROR_BODY_MAX_BYTES].decode("utf-8", "replace")


def _decode_sse_line(line: str) -> dict[str, Any] | None:
    """Read one SSE line, ignoring the framing.

    Keep-alives, blank lines and comment lines are not events. ``[DONE]`` ends
    the stream and carries nothing, so it is dropped here rather than being
    handed to the assembler as an object it would refuse.
    """
    line = line.strip()
    if not line or not line.startswith(SSE_DATA_PREFIX):
        return None
    data = line[len(SSE_DATA_PREFIX) :].strip()
    if not data or data == SSE_DONE:
        return None
    try:
        return json.loads(data)
    except ValueError as exc:
        raise LLMError(f"the route streamed a chunk that is not JSON: {exc}") from exc


def _tool_choice(choice: str) -> Any:
    if choice in PASSTHROUGH_TOOL_CHOICES:
        return choice
    return {"type": "function", "function": {"name": choice}}


def _usage(payload: dict[str, Any] | None) -> Usage | None:
    """Split the provider's counters so nothing is charged twice.

    Providers report the cached and cache-written parts *inside* the prompt
    total and reasoning *inside* the completion total. Left as they arrive, the
    cheap cached tokens would be billed again at the full input price and the
    reasoning tokens twice at the output price.
    """
    if not payload:
        return None

    prompt = int(payload.get("prompt_tokens") or payload.get("input_tokens") or 0)
    completion = int(
        payload.get("completion_tokens") or payload.get("output_tokens") or 0
    )
    prompt_details = payload.get("prompt_tokens_details") or {}
    completion_details = payload.get("completion_tokens_details") or {}

    cached = int(prompt_details.get("cached_tokens") or 0)
    cache_write = int(
        prompt_details.get("cache_write_tokens")
        or payload.get("cache_creation_input_tokens")
        or 0
    )
    reasoning = int(completion_details.get("reasoning_tokens") or 0)

    return Usage(
        input_tokens=max(0, prompt - cached - cache_write),
        cached_input_tokens=cached,
        cache_write_tokens=cache_write,
        output_tokens=max(0, completion - reasoning),
        reasoning_tokens=reasoning,
    )


def build_transport(
    config: LLMConfig | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> OpenAICompatibleTransport:
    """Build the unguarded network implementation for composition."""
    if config is None:
        from .config import llm_config_from_settings

        config = llm_config_from_settings()
    return OpenAICompatibleTransport(config, http_client=http_client)


__all__ = [
    "CACHE_TAIL_MESSAGES",
    "CHAT_COMPLETIONS_PATH",
    "ERROR_BODY_MAX_BYTES",
    "ERROR_BODY_MAX_SECONDS",
    "OpenAICompatibleTransport",
    "build_transport",
]
