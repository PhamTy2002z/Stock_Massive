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
    REGISTERED_FIELDS_KEY,
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
    EXTERNAL = "external"


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
    # What this tool's own result may occupy in the constructed context before
    # it is replaced by a preview (``tools/spillover.py``). Declared at
    # registration because that is the *registry* rung of the resolution order
    # a spillover budget uses, and because the number is a property of the
    # shape a tool returns: a screen of twenty rows and a single close are both
    # inside the catalog's 4 KB cap and only one of them is worth spilling.
    #
    # ``None`` means "the budget's default", never "unlimited": the ceiling
    # above still applies, and a tool that wants more room has to say so here
    # where a reviewer can see it.
    result_budget_bytes: int | None = None
    # MCP discovery is deployment state, recorded separately. Including those
    # schemas here would make the core fixture pin move when a server blinked.
    versioned: bool = True

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


#: The key a recovery hint travels under, beside the refusal it belongs to.
HINT_KEY = "hint"

#: One next action per refusal, and the whole of what a hint may say.
#:
#: A refused tool hands the model a code and a shape. The code is honest and it
#: is also inert: nothing in it says what to do instead, so the measured
#: behaviour is a Turn that calls the same tool again with the same arguments and
#: refuses a second time on the same code. These sentences are what turns the
#: refusal into a next move.
#:
#: Four rules hold for every entry, and they are what keeps this from becoming a
#: second prompt: it appears **only** on a refusal, there is at most **one** of
#: them, it names an **action** rather than diagnosing the cause, and it is
#: written here rather than assembled per call so that two Turns refused the same
#: way read the same. Nothing here is enforcement — the model is free to ignore
#: it, and the Structured Refusal it sits beside is unchanged.
RECOVERY_HINTS: Mapping[str, str] = {
    # The refusal already carries same-industry alternatives, and the loop
    # measured Turns that never looked at them.
    "not_in_universe": (
        "this symbol is outside the covered Universe; ask about one of the "
        "alternatives this refusal lists, or tell the reader it is not covered"
    ),
    "news_unavailable": (
        "the news channel is unreachable in this Turn; answer from stored data "
        "and say the news source was unavailable rather than calling it again"
    ),
    "web_unavailable": (
        "the open web is unreachable in this Turn; answer from stored data and "
        "say so rather than calling it again"
    ),
    "no_cleared_news_in_window": (
        "nothing cleared in that window; widen the window once, or say there was "
        "no cleared news for this symbol"
    ),
    "no_web_results": (
        "that sentence found nothing; ask it once in the words the reader used, "
        "or say the open web had nothing on it"
    ),
    "no_remembered_facts": (
        "nothing has been remembered for this; get it from a lookup instead"
    ),
    "unknown_tool": "call one of the tools this result lists as available",
    "tool_error": (
        "this call failed rather than answered; take a different approach or say "
        "what is missing — an identical retry reaches the same failure"
    ),
}

#: The same, for a window that could not carry the field that was asked for.
#:
#: These arrive on ``window_health`` rather than as an envelope refusal, so the
#: result is not a refusal as a whole: the tool answered, and one field inside it
#: did not. The action is the same shape — what to ask for instead — and it never
#: promises a figure, because a shorter window is a different measurement rather
#: than a cheaper route to the same one.
WINDOW_HINTS: Mapping[str, str] = {
    "insufficient_history": (
        "the stored window is shorter than this field needs; ask for a field "
        "computed from a short window, such as the indicator pack, or say the "
        "history is too short to compute this one"
    ),
    "cohort_warming": (
        "the cross-sectional cohort is still warming up, so no ranking exists "
        "yet; answer from the symbol's own figures instead of its rank"
    ),
    "ranking_unavailable": (
        "no ranking exists for this day; answer from the symbol's own figures "
        "instead of its rank"
    ),
    "missing_target_session": (
        "the store holds no session for this symbol on that day; ask for the "
        "latest session it does hold and name the day you answered from"
    ),
    "recently_inactive": (
        "the symbol has not traded recently enough for this field; say so and "
        "answer from the last session that is held"
    ),
    "mixed_price_basis": (
        "the window crosses a price-basis seam and cannot be compared across; "
        "ask for a window inside one basis, or say the series is not comparable"
    ),
    "stale_market_data": (
        "the data behind this field is older than it may be for this reading; "
        "name the session it is dated to rather than calling again"
    ),
}


def recovery_hint(result: Mapping[str, Any]) -> str | None:
    """The one next action a refused result suggests, or nothing.

    Pure, and first match wins: the envelope's own refusal outranks a refused
    window inside it, because a result that refused as a whole has no field for
    the second hint to be about. A result that answered gets no hint at all —
    a suggestion attached to a successful call is a prompt, and prompts belong
    in the Contract where a version records them.
    """
    reason = refusal_reason(result)
    if reason is not None:
        return RECOVERY_HINTS.get(reason)
    health = result.get("window_health")
    if isinstance(health, Mapping):
        refused = health.get("refusal")
        if refused:
            return WINDOW_HINTS.get(str(refused))
    return None


def omit_nulls(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Read an explicit null as the absence it stands for.

    Strict mode cannot express an absent key, so an optional parameter reaches
    the loop as one whose value is null (``core.llm.protocol.strict_parameters``).
    Every tool here was written against the omission that predates it — a
    default applies when the key is not there — so the two spellings are
    reconciled once, at the boundary, rather than in each tool's argument
    handling. The trace records what the tool actually ran on, which is this.
    """

    cleaned: dict[str, Any] = {}
    for key, value in arguments.items():
        if value is None:
            continue
        cleaned[key] = omit_nulls(value) if isinstance(value, Mapping) else value
    return cleaned


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
        mcp_servers_version: str = "disabled",
    ) -> None:
        indexed: dict[str, ToolSpec] = {}
        for registration in registrations:
            if registration.name in indexed:
                raise ValueError(f"tool {registration.name} is registered twice")
            if registration.data_access is ToolDataAccess.NEWS_PROVIDER and (
                registration.name != "search_news"
            ):
                raise ValueError("search_news is the only Provider Source exception")
            indexed[registration.name] = registration
        self._registrations = indexed
        self._trace_writer = trace_writer
        self.tool_schemas = tuple(item.schema() for item in registrations)
        stable_surface = [
            registration.schema().as_wire()
            for registration in registrations
            if registration.versioned
        ]
        encoded = json.dumps(
            stable_surface,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.tool_catalog_version = hashlib.sha256(encoded).hexdigest()[:16]
        self.mcp_servers_version = mcp_servers_version

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._registrations)

    def is_external(self, tool_name: str) -> bool:
        """Whether one call spends the Turn's optional external-tool budget."""
        registration = self._registrations.get(tool_name)
        return bool(
            registration is not None
            and registration.data_access is ToolDataAccess.EXTERNAL
        )

    @property
    def result_budgets(self) -> Mapping[str, int]:
        """Every declared per-tool result budget, as a spillover budget's table.

        The registry rung of ``pinned > config > registry > default``, read off
        the registrations rather than kept as a second table: the declaration
        lives beside the schema where a reviewer meets it, and the resolution
        order that consults it lives in ``tools/spillover.py``. A tool that
        declared nothing is absent, which is how it inherits the default —
        including every MCP tool, whose shape nothing here has seen.
        """
        return {
            name: registration.result_budget_bytes
            for name, registration in self._registrations.items()
            if registration.result_budget_bytes is not None
        }

    async def dispatch(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        context: ToolContext,
        *,
        call_id: str | None = None,
        thread_id: Any | None = None,
        request_message_id: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> Mapping[str, Any]:
        """Run one registered tool, or return an actionable unknown-tool result.

        ``call_id`` is the route's own id for this call, recorded on the trace
        and never read by a tool. It is what makes a stored trace addressable by
        the same identifier the model cites in an evidence reference — without
        it, a citation and the row holding the result it names can only be joined
        by guessing from the tool name and the arguments.
        """

        arguments = omit_nulls(arguments)
        started = time.perf_counter()
        registration = self._registrations.get(tool_name)
        if registration is None:
            result: Mapping[str, Any] = self._with_hint(
                {
                    "error": {
                        "code": "unknown_tool",
                        "tool_name": tool_name,
                        "available_tools": list(self.names),
                    }
                }
            )
            await self._trace(
                call_id=call_id,
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
            result = self._with_hint(result)
            size = serialized_size(result)
            if size > MAX_TOOL_RESULT_BYTES:
                raise ToolResultTooLarge(tool_name, size)
        except Exception as exc:
            await self._trace(
                call_id=call_id,
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
            call_id=call_id,
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
    def _with_hint(result: Mapping[str, Any]) -> Mapping[str, Any]:
        """Attach the one recovery hint a refusal earns, if it fits.

        Dropped rather than kept when adding it would break the result budget: a
        refusal that no longer fits its own envelope has cost the Turn the
        refusal, and the hint is the garnish. Nothing is overwritten either — a
        tool that wrote its own hint knows more about its refusal than this
        table does.
        """
        if HINT_KEY in result:
            return result
        hint = recovery_hint(result)
        if hint is None:
            return result
        hinted = {**result, HINT_KEY: hint}
        return hinted if serialized_size(hinted) <= MAX_TOOL_RESULT_BYTES else result

    @staticmethod
    def _project_registered_fields(
        registration: ToolSpec,
        result: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Make the Signal Registry the only route for computed field values."""

        payload = dict(result)
        if REGISTERED_FIELDS_KEY in payload:
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
            payload[REGISTERED_FIELDS_KEY] = {
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

    async def _trace(self, *, call_id: str | None = None, **trace: Any) -> None:
        written = self._trace_writer({"tool_call_id": call_id, **trace})
        if inspect.isawaitable(written):
            await written
