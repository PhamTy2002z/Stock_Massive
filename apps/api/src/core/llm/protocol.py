"""The one protocol the rest of the system may depend on.

``docs/adr/0008`` keeps the agent loop hand-rolled over this, and the reason is
in the shape of these types rather than in the transport behind them: a
``ToolCall`` here carries *parsed* arguments, never a string, so no caller can
be handed text that was never valid JSON. The transport is what makes that
promise; the protocol is what states it.

No provider SDK appears in these types. Every framework marries one client
abstraction, and this abstraction is the seam a route change has to be free
across.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .admission import SpendRequest


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


def _nullable(prop: Mapping[str, Any]) -> dict[str, Any]:
    """Widen one property so that omitting it is expressible under strict mode.

    Strict mode has no notion of an absent key, so an optional parameter is
    spelled as one whose value may be null. An enum has to admit null too, or
    the widened type and the enumerated values contradict each other.
    """

    widened = dict(prop)
    declared = widened.get("type")
    if isinstance(declared, str):
        if declared == "null":
            return widened
        widened["type"] = [declared, "null"]
    elif isinstance(declared, list):
        if "null" in declared:
            return widened
        widened["type"] = [*declared, "null"]
    else:
        return widened

    enum = widened.get("enum")
    if isinstance(enum, Sequence) and not isinstance(enum, (str, bytes)):
        if None not in enum:
            widened["enum"] = [*enum, None]
    return widened


def strict_parameters(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Restate a parameter schema in the form strict mode actually accepts.

    A route that honours ``strict`` refuses any object whose ``required`` omits
    a declared property — the whole point of the mode is that the arguments
    which arrive are the arguments that were described. Writing the tools the
    other way round (``required`` naming only the mandatory keys) describes the
    same intent but is rejected before a single token is generated, so the
    translation happens here, at the one place a schema crosses onto the wire,
    rather than in twelve tool definitions that would each have to remember it.
    """

    if not isinstance(schema, Mapping):
        return schema

    restated = dict(schema)
    declared = restated.get("type")
    kinds = declared if isinstance(declared, list) else [declared]

    if "object" in kinds:
        properties = {
            name: strict_parameters(value)
            for name, value in (restated.get("properties") or {}).items()
        }
        required = list(restated.get("required") or [])
        for name in properties:
            if name not in required:
                properties[name] = _nullable(properties[name])
        restated["properties"] = properties
        restated["required"] = list(properties)
        restated["additionalProperties"] = False
    elif "array" in kinds and "items" in restated:
        restated["items"] = strict_parameters(restated["items"])

    return restated


@dataclass(frozen=True)
class ToolSchema:
    """One tool as the model sees it.

    ``strict`` defaults on: a schema the route is free to ignore is a schema
    that describes what was hoped for rather than what arrives.
    """

    name: str
    description: str
    parameters: Mapping[str, Any]
    strict: bool = True

    def as_wire(self) -> dict[str, Any]:
        parameters = dict(self.parameters)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": (
                    strict_parameters(parameters) if self.strict else parameters
                ),
                "strict": self.strict,
            },
        }


@dataclass(frozen=True)
class ToolCall:
    """One tool call the model asked for, with its arguments already parsed.

    ``output_index`` is the upstream's own index for this call, carried through
    rather than discarded: it is the key streamed fragments were assembled by,
    and keeping it is what lets a caller prove which call a fragment belonged to.
    """

    id: str
    name: str
    arguments: Mapping[str, Any]
    output_index: int = 0
    #: The route's own opaque token for the reasoning behind this call, kept
    #: exactly as it arrived. Gemini 3.x refuses a round whose function calls
    #: come back without it, and only the route that issued one can read it —
    #: so it is carried, never inspected, and never synthesised.
    signature: str | None = None


#: Where an OpenAI-compatible route carries vendor fields on a tool call. Read
#: and written under the same two keys, because a token that comes back under a
#: different name than it left is not the token the route asked for.
SIGNATURE_CONTAINER_KEY = "extra_content"
SIGNATURE_VENDOR_KEY = "google"
SIGNATURE_KEY = "thought_signature"


def _tool_call_wire(call: ToolCall) -> dict[str, Any]:
    """One tool call on the wire, with the route's own token if it gave one.

    A signature is only ever present because this route issued it, so handing it
    back needs no per-route switch: a route that never sends one never sees one.
    """
    payload: dict[str, Any] = {
        "id": call.id,
        "type": "function",
        "function": {
            "name": call.name,
            "arguments": json.dumps(call.arguments),
        },
    }
    if call.signature is not None:
        payload[SIGNATURE_CONTAINER_KEY] = {
            SIGNATURE_VENDOR_KEY: {SIGNATURE_KEY: call.signature}
        }
    return payload


@dataclass(frozen=True)
class Message:
    """One turn of the conversation, in the shape the route expects."""

    role: Role
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None

    def as_wire(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            payload["content"] = self.content
        if self.tool_calls:
            payload["tool_calls"] = [
                _tool_call_wire(call) for call in self.tool_calls
            ]
        if self.tool_call_id is not None:
            payload["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            payload["name"] = self.name
        return payload


@dataclass(frozen=True)
class JsonSchemaFormat:
    """A strict structured-output request.

    ``strict`` is not optional in practice: a gateway was measured silently
    dropping ``response_format``, and a schema that is merely encouraged cannot
    tell that outcome from a model that wandered.
    """

    name: str
    schema: Mapping[str, Any]
    strict: bool = True

    def as_wire(self) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": self.name,
                "schema": dict(self.schema),
                "strict": self.strict,
            },
        }


@dataclass(frozen=True)
class Usage:
    """Five counters, matching the four prices of ``config.TokenPrices``.

    ``output_tokens`` excludes ``reasoning_tokens`` so nothing is counted twice,
    and reasoning is billed at the output price — which is why it is carried
    separately rather than folded in (``docs/adr/0014``).
    """

    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cached_input_tokens
            + self.cache_write_tokens
            + self.output_tokens
            + self.reasoning_tokens
        )

    def __add__(self, other: "Usage") -> "Usage":
        """Sum two calls' counters, for a caller totalling one Turn.

        Here rather than in the caller: a second five-field type that had to be
        kept in step with this one is a fifth counter waiting to be forgotten.
        """
        if not isinstance(other, Usage):
            return NotImplemented
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
        )


@dataclass(frozen=True)
class CompletionRequest:
    """One call to the route, described without naming the route."""

    model: str
    messages: Sequence[Message]
    tools: Sequence[ToolSchema] = ()
    # "auto" | "none" | "required" | a tool name to force
    tool_choice: str = "auto"
    parallel_tool_calls: bool = True
    response_format: JsonSchemaFormat | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    stream: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Completion:
    """What came back, with every tool call already proven parseable."""

    model: str
    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    # None means the provider supplied no evidence. It is intentionally not an
    # all-zero Usage: absence may not refund a committed reservation.
    usage: Usage | None = None
    finish_reason: str = "stop"
    # The route's own id for this call, recorded in the Evidence Manifest so a
    # disputed answer can be traced back at the provider. ``None`` when the
    # route supplied none: the entire value of the field is that somebody can
    # look it up, so a synthesized id would be worse than an absent one.
    request_id: str | None = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMClient(Protocol):
    """The whole boundary. Everything else is an implementation detail."""

    async def complete(
        self,
        request: CompletionRequest,
        spend: "SpendRequest | None" = None,
    ) -> Completion:
        """Make one call and return a typed result or raise a typed failure."""
        ...


__all__ = [
    "Completion",
    "CompletionRequest",
    "JsonSchemaFormat",
    "LLMClient",
    "Message",
    "Role",
    "ToolCall",
    "ToolSchema",
    "Usage",
    "strict_parameters",
]
