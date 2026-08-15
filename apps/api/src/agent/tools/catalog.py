"""Registration and dispatch for the model-visible Tool Catalog.

One registration produces both the schemas sent to the LLM and the catalog
version used by the cacheable prompt prefix.  The dispatcher owns the rules
that must hold for every tool: bounded JSON, structured unknown-tool results,
and a trace for every attempted call.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from src.core.llm import ToolSchema
from src.core.provider_access import store_only_execution

from .fields import (
    REGISTERED_FIELD_VALUES_KEY,
    SHARED_WINDOW_HEALTH_KEY,
    RefusedRegisteredField,
    registered_field_schema,
    serialize_refused_field,
    serialize_field_value,
    serialize_window_health,
)

MAX_TOOL_RESULT_BYTES = 4 * 1024

ToolCallable = Callable[["ToolContext", Mapping[str, Any]], Awaitable[Mapping[str, Any]]]
TraceWriter = Callable[[dict[str, Any]], Any]


class ToolDataAccess(str, Enum):
    """The data authority a registration receives during dispatch."""

    STORE_ONLY = "store_only"
    NEWS_PROVIDER = "news_provider"


@dataclass(frozen=True)
class ToolContext:
    """Trusted Turn facts injected out of band, never into a tool schema."""

    user_id: int
    trading_day: date
    active_symbol: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    """One registration: model schema and the callable it dispatches to."""

    name: str
    description: str
    parameters: Mapping[str, Any]
    callable: ToolCallable
    data_access: ToolDataAccess = ToolDataAccess.STORE_ONLY
    registered_fields: tuple[str, ...] = ()
    shared_window_health: bool = False

    def schema(self) -> ToolSchema:
        field_descriptions = [
            f"{name}: {registered_field_schema(name)['description']}"
            for name in self.registered_fields
        ]
        description = self.description
        if field_descriptions:
            description = f"{description} Registered fields: {' '.join(field_descriptions)}"
        return ToolSchema(
            name=self.name,
            description=description,
            parameters=self.parameters,
        )


class ToolResultTooLarge(ValueError):
    """A tool broke the catalog-wide context budget."""

    def __init__(self, tool_name: str, size: int) -> None:
        super().__init__(
            f"tool {tool_name} returned {size} bytes; "
            f"the limit is {MAX_TOOL_RESULT_BYTES} bytes"
        )
        self.tool_name = tool_name
        self.size = size


def refusal_reason(result: Mapping[str, Any]) -> str | None:
    """The Structured Refusal a result carries, or ``None`` if it carries data.

    Owned here because the envelope is this layer's, and a caller re-deriving
    it gets one case wrong: ``search_news`` answers a successful call with
    ``reason: None``, so the *presence* of the key is not a refusal. Anything
    reading the shape from outside would count "nothing found" as evidence.
    """

    reason = result.get("reason")
    if reason:
        return str(reason)
    error = result.get("error")
    if isinstance(error, Mapping):
        return str(error.get("code") or "tool_error")
    if error:
        return "tool_error"
    return None


def serialized_size(value: Mapping[str, Any]) -> int:
    """The exact compact UTF-8 size charged against the response budget."""

    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    )


class ToolCatalog:
    """Immutable catalog whose registration is the only dispatch authority."""

    def __init__(
        self,
        registrations: Sequence[ToolSpec],
        *,
        trace_writer: TraceWriter,
    ) -> None:
        indexed: dict[str, ToolSpec] = {}
        for registration in registrations:
            if registration.name in indexed:
                raise ValueError(f"tool {registration.name} is registered twice")
            if (
                registration.data_access is ToolDataAccess.NEWS_PROVIDER
                and registration.name != "search_news"
            ):
                raise ValueError("search_news is the only Provider Source exception")
            indexed[registration.name] = registration
        self._registrations = indexed
        self._trace_writer = trace_writer
        self.tool_schemas = tuple(item.schema() for item in registrations)
        stable_surface = [schema.as_wire() for schema in self.tool_schemas]
        encoded = json.dumps(
            stable_surface,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.tool_catalog_version = hashlib.sha256(encoded).hexdigest()[:16]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._registrations)

    async def dispatch(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        context: ToolContext,
        *,
        thread_id: Any | None = None,
        request_message_id: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> Mapping[str, Any]:
        """Run one registered tool, or return an actionable unknown-tool result."""

        started = time.perf_counter()
        registration = self._registrations.get(tool_name)
        if registration is None:
            result: Mapping[str, Any] = {
                "error": {
                    "code": "unknown_tool",
                    "tool_name": tool_name,
                    "available_tools": list(self.names),
                }
            }
            await self._trace(
                thread_id=thread_id,
                request_message_id=request_message_id,
                tool_name=tool_name,
                arguments=dict(arguments),
                result=dict(result),
                status="unknown_tool",
                error=None,
                latency_ms=self._latency_ms(started),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return result

        try:
            if registration.data_access is ToolDataAccess.STORE_ONLY:
                with store_only_execution():
                    result = await registration.callable(context, arguments)
            else:
                result = await registration.callable(context, arguments)
            result = self._project_registered_fields(registration, result)
            size = serialized_size(result)
            if size > MAX_TOOL_RESULT_BYTES:
                raise ToolResultTooLarge(tool_name, size)
        except Exception as exc:
            await self._trace(
                thread_id=thread_id,
                request_message_id=request_message_id,
                tool_name=tool_name,
                arguments=dict(arguments),
                result=None,
                status="tool_error",
                error=str(exc),
                latency_ms=self._latency_ms(started),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            raise

        await self._trace(
            thread_id=thread_id,
            request_message_id=request_message_id,
            tool_name=tool_name,
            arguments=dict(arguments),
            result=dict(result),
            status="ok",
            error=None,
            latency_ms=self._latency_ms(started),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return result

    @staticmethod
    def _project_registered_fields(
        registration: ToolSpec,
        result: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Make the Signal Registry the only route for computed field values."""

        payload = dict(result)
        if "registered_fields" in payload:
            raise ValueError(
                "tool callables cannot serialize registered_fields themselves"
            )
        answers = payload.pop(REGISTERED_FIELD_VALUES_KEY, {})
        if not isinstance(answers, Mapping):
            raise TypeError("registered field answers must be a mapping")
        undeclared = set(answers).difference(registration.registered_fields)
        if undeclared:
            raise ValueError(
                f"tool {registration.name} returned undeclared registered fields: "
                f"{', '.join(sorted(undeclared))}"
            )
        shared_health = payload.pop(SHARED_WINDOW_HEALTH_KEY, None)
        if registration.shared_window_health:
            if shared_health is None:
                if payload.get("reason") == "not_in_universe":
                    return payload
                raise ValueError(
                    f"tool {registration.name} must return shared Window Health"
                )
            payload["window_health"] = serialize_window_health(shared_health)
        elif shared_health is not None:
            raise ValueError(
                f"tool {registration.name} did not declare shared Window Health"
            )
        if answers:
            payload["registered_fields"] = {
                name: (
                    serialize_refused_field(answer)
                    if isinstance(answer, RefusedRegisteredField)
                    else serialize_field_value(
                        answer,
                        include_window_health=not registration.shared_window_health,
                    )
                )
                for name, answer in answers.items()
            }
        return payload

    @staticmethod
    def _latency_ms(started: float) -> int:
        return max(0, round((time.perf_counter() - started) * 1000))

    async def _trace(self, **trace: Any) -> None:
        written = self._trace_writer(trace)
        if inspect.isawaitable(written):
            await written
