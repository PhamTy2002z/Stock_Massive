"""One OpenAI-compatible transport behind the reserved ``LLMClient``.

Built on ``httpx`` without a provider SDK or agent framework. Retry lives one
layer above this transport, where each attempt can receive its own committed
reservation; retrying here would silently make two paid requests against one
ledger row.

What the hand-rolling buys, concretely:

- streamed tool calls assembled by the **upstream index** (``streaming.py``),
- the **JSON-parse invariant** on every returned ``arguments``,
- ``auth_unavailable`` as a first-class class that is **never retried**.

There is no automatic model fallback. A fallback route may have different
capabilities and different prices, which invalidates the monetary ceiling that
was reserved against the original model (``docs/adr/0014``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

import httpx
from .config import LLMConfig
from .errors import (
    AuthUnavailable,
    GatewayTimeout,
    RouteRateLimited,
    LLMError,
    ModelRefusal,
    classify_status,
    llm_metrics,
)
from .protocol import Completion, CompletionRequest, Role, Usage
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


class OpenAICompatibleTransport:
    """The network transport used only behind the reserved public client."""

    def __init__(
        self,
        config: LLMConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(config.request_timeout_seconds)
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

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
        wire = [message.as_wire() for message in request.messages]
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

        try:
            async with self._http.stream(
                "POST",
                self._url(),
                json=self._body(request),
                headers=self._headers(),
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    raise self._classified(
                        response.status_code, body, response.headers
                    )
                async for line in response.aiter_lines():
                    chunk = _decode_sse_line(line)
                    if chunk is not None:
                        assembler.add_chunk(chunk)
        except httpx.RequestError as exc:
            # Covers TimeoutException, which subclasses it: a route that did not
            # answer and a route that could not be reached are the same fact
            # from here, and both are retryable.
            raise self._timeout(exc) from exc

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
        try:
            response = await self._http.post(
                self._url(),
                json=self._body(request),
                headers=self._headers(),
            )
        except httpx.RequestError as exc:
            # Covers TimeoutException, which subclasses it: a route that did not
            # answer and a route that could not be reached are the same fact
            # from here, and both are retryable.
            raise self._timeout(exc) from exc

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
        return error

    def _timeout(self, exc: Exception) -> GatewayTimeout:
        error = GatewayTimeout(f"the route did not answer: {exc}")
        llm_metrics().record_gateway_timeout(str(error))
        return error


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
    "CHAT_COMPLETIONS_PATH",
    "OpenAICompatibleTransport",
    "build_transport",
]
