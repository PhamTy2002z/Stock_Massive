"""Offline model scripting and redacted observable trajectory capture.

The evaluation lane records protocol facts, never prompt bodies, response prose,
headers, private memory, or hidden reasoning.  The wrapped client remains the
owner of retries and typed failures; this module observes and re-raises.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from src.core.llm import (
    Completion,
    CompletionRequest,
    LLMClient,
    LLMConfig,
    ReservedLLMClient,
    SpendAdmission,
    Usage,
)
from src.core.llm.errors import redact

from .contracts import TrajectoryEvent, content_digest, find_secret_shapes

Clock = Callable[[], datetime]
Monotonic = Callable[[], float]
TraceWriter = Callable[[Mapping[str, Any]], Awaitable[Any] | Any]

_SAFE_METADATA = frozenset({"case_id", "trial_index", "workload"})
_EVIDENCE_KEYS = (
    "evidence_references",
    "evidenceReferences",
    "evidence_refs",
    "source_ids",
    "field_ids",
)
_SECRET_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "secret",
        "password",
        "passwd",
        "authorization",
        "headers",
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    """Project a value onto JSON scalars/containers, redacting secret shapes."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return "[REDACTED]" if find_secret_shapes(value) else value
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            lowered = name.lower()
            if lowered in _SECRET_FIELD_NAMES:
                projected[name] = "[REDACTED]"
            else:
                projected[name] = _json_safe(item)
        return projected
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    return str(value)


def _request_projection(request: CompletionRequest) -> dict[str, Any]:
    response_format = request.response_format
    return {
        "model": request.model,
        "message_roles": [message.role.value for message in request.messages],
        "message_chars": [len(message.content or "") for message in request.messages],
        "tools": [tool.name for tool in request.tools],
        "tool_choice": request.tool_choice,
        "parallel_tool_calls": request.parallel_tool_calls,
        "response_format": None if response_format is None else response_format.name,
        "max_output_tokens": request.max_output_tokens,
        "temperature": request.temperature,
        "stream": request.stream,
        "metadata": {
            key: _json_safe(value)
            for key, value in request.metadata.items()
            if key in _SAFE_METADATA
        },
    }


def _tool_call_projection(call: Any) -> dict[str, Any]:
    return {
        "id": str(call.id),
        "name": str(call.name),
        "arguments": _json_safe(dict(call.arguments)),
    }


def _usage_tokens(usage: Usage | None) -> int:
    return 0 if usage is None else usage.total_tokens


class TrajectoryRecorder:
    """One thread-safe sequence shared by model, tool, and terminal observers."""

    def __init__(self, *, clock: Clock = _utcnow) -> None:
        self._clock = clock
        self._events: list[TrajectoryEvent] = []
        self._lock = threading.Lock()

    def emit(
        self,
        kind: str,
        payload: Mapping[str, Any],
        *,
        at: datetime | None = None,
    ) -> TrajectoryEvent:
        with self._lock:
            event = TrajectoryEvent(
                schema="eval.trajectory-event@1",
                seq=len(self._events),
                kind=kind,
                at=at or self._clock(),
                payload=dict(_json_safe(payload)),
            )
            self._events.append(event)
            return event

    @property
    def events(self) -> tuple[TrajectoryEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def interleave_tool_events(
        self,
        tools: Sequence[tuple[str | None, Mapping[str, Any], datetime]],
    ) -> None:
        """Place persisted tool settlements after the attempt that issued them."""
        with self._lock:
            pending = list(tools)
            ordered: list[tuple[str, Mapping[str, Any], datetime]] = []
            for event in self._events:
                ordered.append((event.kind, event.payload, event.at))
                if event.kind != "model_attempt":
                    continue
                calls = event.payload.get("tool_calls") or []
                for call in calls:
                    call_id = str(call.get("id")) if call.get("id") is not None else None
                    for index, (candidate_id, payload, at) in enumerate(pending):
                        if candidate_id == call_id:
                            ordered.append(("tool_call", payload, at))
                            pending.pop(index)
                            break
            ordered.extend(("tool_call", payload, at) for _id, payload, at in pending)
            self._events = [
                TrajectoryEvent(
                    schema="eval.trajectory-event@1",
                    seq=index,
                    kind=kind,
                    at=at,
                    payload=dict(_json_safe(payload)),
                )
                for index, (kind, payload, at) in enumerate(ordered)
            ]

    def order_existing_tool_events(self) -> None:
        """Reorder concurrently persisted tool events by issued call order."""
        with self._lock:
            tools = [
                (
                    None
                    if event.payload.get("call_id") is None
                    else str(event.payload.get("call_id")),
                    event.payload,
                    event.at,
                )
                for event in self._events
                if event.kind == "tool_call"
            ]
            base = [event for event in self._events if event.kind != "tool_call"]
            self._events = base
        self.interleave_tool_events(tools)


class ScriptedLLMClient:
    """An offline client returning exactly the supplied typed script."""

    offline = True

    def __init__(self, script: Sequence[Any]) -> None:
        self._script = list(script)
        self.requests: list[CompletionRequest] = []
        self.spends: list[Any] = []
        self._reserved: ReservedLLMClient | None = None

    def with_admission(
        self,
        *,
        config: LLMConfig,
        session_factory: Callable[[], Any],
        clock: Clock,
    ) -> "ScriptedLLMClient":
        """Install the production reservation/reconciliation boundary once."""
        if self._reserved is None:
            self._reserved = ReservedLLMClient(
                _ScriptedTransport(self),
                SpendAdmission(config, session_factory=session_factory, clock=clock),
                config=config,
            )
        return self

    async def complete(self, request: CompletionRequest, spend: Any = None) -> Completion:
        self.requests.append(request)
        self.spends.append(spend)
        if self._reserved is not None:
            return await self._reserved.complete(request, spend)
        return await self._next(request, spend)

    async def _next(self, request: CompletionRequest, spend: Any = None) -> Completion:
        if not self._script:
            raise AssertionError("the scripted eval client has no completion left")
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            item = item(request, spend)
            if inspect.isawaitable(item):
                item = await item
        if not isinstance(item, Completion):
            raise TypeError("a scripted eval item must produce Completion or raise")
        return item

    @property
    def remaining(self) -> int:
        return len(self._script)


class LiveEvalLLMClient:
    """A paid client whose route and admission ledger are owned by one eval case."""

    offline = False

    def __init__(
        self,
        transport: Any,
        *,
        config: LLMConfig,
        session_factory: Callable[[], Any],
        clock: Clock,
    ) -> None:
        self.route = config.route.base_url
        self._config = config
        self._session_factory = session_factory
        self._reserved = ReservedLLMClient(
            transport,
            SpendAdmission(config, session_factory=session_factory, clock=clock),
            config=config,
        )

    async def complete(self, request: CompletionRequest, spend: Any = None) -> Completion:
        return await self._reserved.complete(request, spend)

    async def aclose(self) -> None:
        await self._reserved.aclose()

    def belongs_to(
        self, *, config: LLMConfig, session_factory: Callable[[], Any]
    ) -> bool:
        """Whether route pricing and ledger ownership match one runner exactly."""
        return self._config == config and self._session_factory is session_factory


class SingleAttemptEvalLLMClient:
    """One admitted provider dispatch for auxiliary rubric measurement.

    Rubric failure is recorded as unavailable, so retrying would add spend and
    variance without repairing a candidate outcome. Keeping this client to one
    reservation and one dispatch makes its run-ceiling proof exact.
    """

    offline = False

    def __init__(self, transport: Any, admission: Any) -> None:
        self._transport = transport
        self._admission = admission

    async def complete(self, request: CompletionRequest, spend: Any = None) -> Completion:
        if spend is None:
            raise ValueError("a rubric call requires an explicit spend reservation")
        reservation = await asyncio.to_thread(
            self._admission.reserve, spend, request.model
        )
        try:
            completion = await self._transport.dispatch(request)
        except BaseException as exc:
            usage = getattr(exc, "usage", None)
            if usage is not None:
                await asyncio.to_thread(
                    self._admission.reconcile, reservation, usage
                )
            raise
        if completion.usage is not None:
            await asyncio.to_thread(
                self._admission.reconcile, reservation, completion.usage
            )
        return completion

    async def aclose(self) -> None:
        close = getattr(self._transport, "aclose", None)
        if close is not None:
            await close()


class _ScriptedTransport:
    """Adapt a script to the transport side of ``ReservedLLMClient``."""

    def __init__(self, scripted: ScriptedLLMClient) -> None:
        self._scripted = scripted

    async def dispatch(self, request: CompletionRequest) -> Completion:
        return await self._scripted._next(request)


class RecordingLLMClient:
    """Decorate ``LLMClient.complete`` without changing its behavior."""

    def __init__(
        self,
        client: LLMClient,
        *,
        recorder: TrajectoryRecorder,
        monotonic: Monotonic = time.monotonic,
    ) -> None:
        self._client = client
        self._recorder = recorder
        self._monotonic = monotonic
        self.usage = Usage()
        self.usage_known = True

    @property
    def offline(self) -> bool:
        return bool(getattr(self._client, "offline", False))

    async def complete(self, request: CompletionRequest, spend: Any = None) -> Completion:
        started = self._monotonic()
        projected = _request_projection(request)
        try:
            completion = await self._client.complete(request, spend)
        except BaseException as exc:
            elapsed = max(0, round((self._monotonic() - started) * 1_000))
            usage = getattr(exc, "usage", None)
            if usage is not None:
                self.usage = self.usage + usage
            else:
                self.usage_known = False
            detail = redact(str(exc))
            self._recorder.emit(
                "model_attempt",
                {
                    "status": "failed",
                    "request": projected,
                    "latency_ms": elapsed,
                    "error_type": type(exc).__name__,
                    # Exception text can contain a provider body or private
                    # prompt excerpt even when it is not credential-shaped.
                    "error": "[REDACTED]" if detail else "",
                    "usage_tokens": _usage_tokens(usage),
                },
            )
            raise

        elapsed = max(0, round((self._monotonic() - started) * 1_000))
        if completion.usage is not None:
            self.usage = self.usage + completion.usage
        else:
            self.usage_known = False
        self._recorder.emit(
            "model_attempt",
            {
                "status": "completed",
                "request": projected,
                "latency_ms": elapsed,
                "completion_model": completion.model,
                "text_chars": len(completion.text or ""),
                "text_digest": content_digest(completion.text or ""),
                "tool_calls": [
                    _tool_call_projection(call) for call in completion.tool_calls
                ],
                "usage_tokens": _usage_tokens(completion.usage),
                "finish_reason": completion.finish_reason,
                "request_id": completion.request_id,
            },
        )
        return completion


class RecordingTraceWriter:
    """Persist a production tool trace and record its redacted eval projection."""

    def __init__(
        self,
        writer: TraceWriter,
        *,
        recorder: TrajectoryRecorder,
        argument_allowlists: Mapping[str, frozenset[str]] | None = None,
    ) -> None:
        self._writer = writer
        self._recorder = recorder
        self._argument_allowlists = dict(argument_allowlists or {})

    async def __call__(self, trace: Mapping[str, Any]) -> Any:
        written = self._writer(trace)
        if inspect.isawaitable(written):
            written = await written

        tool_name = str(trace.get("tool_name") or "")
        self._recorder.emit(
            "tool_call",
            tool_trace_projection(
                trace,
                argument_allowlist=self._argument_allowlists.get(
                    tool_name, frozenset()
                ),
            ),
        )
        return written


def tool_trace_projection(
    trace: Mapping[str, Any],
    *,
    argument_allowlist: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """The allowlisted eval projection of one persisted tool settlement."""
    arguments = dict(trace.get("arguments") or {})
    result = trace.get("result")
    evidence: list[Any] = []
    if isinstance(result, Mapping):
        candidates: list[Mapping[str, Any]] = [result]
        body = result.get("text")
        if isinstance(body, str):
            try:
                decoded = json.loads(body)
            except (TypeError, ValueError):
                decoded = None
            if isinstance(decoded, Mapping):
                candidates.append(decoded)
        for candidate in candidates:
            for key in _EVIDENCE_KEYS:
                value = candidate.get(key)
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    evidence.extend(value)
    return {
        "call_id": trace.get("tool_call_id"),
        "tool_name": str(trace.get("tool_name") or ""),
        "arguments": {
            key: _json_safe(value)
            for key, value in arguments.items()
            if key in argument_allowlist
        },
        "status": trace.get("status"),
        "outcome": trace.get("outcome"),
        "duration_ms": int(trace.get("latency_ms") or 0),
        "error": _json_safe(trace.get("error")),
        "evidence_references": _json_safe(evidence),
    }


def sanitize_artifact(value: Any) -> Any:
    """Remove credential-shaped values before normalized eval artifacts persist."""
    return _json_safe(value)


__all__ = [
    "LiveEvalLLMClient",
    "RecordingLLMClient",
    "RecordingTraceWriter",
    "ScriptedLLMClient",
    "TrajectoryRecorder",
    "sanitize_artifact",
    "tool_trace_projection",
]
