"""Assembling a streamed answer, keyed on the upstream's own index.

This module exists because of one measured failure. A gateway keyed streamed
tool calls on a **local counter** instead of the index the upstream sent, so
when two calls streamed interleaved it concatenated their arguments into
invalid JSON under the wrong id — and returned 200. Nothing downstream can
notice that. It does not fail; it makes answers wrong.

So two rules are enforced here and nowhere else:

1. **Fragments are grouped by the upstream ``output_index``.** A chunk that
   carries no index is refused rather than guessed at, because guessing is
   precisely the bug.
2. **Every assembled ``arguments`` must parse.** On failure the assembly raises
   immediately; no caller is ever handed a string that was never JSON for the
   model to guess at.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .errors import LLMError, MalformedArguments, llm_metrics
from .protocol import (
    SIGNATURE_CONTAINER_KEY,
    SIGNATURE_KEY,
    SIGNATURE_VENDOR_KEY,
    ToolCall,
)

# The delta keys an OpenAI-compatible route may use for the upstream index.
# ``output_index`` is the Responses API's name and ``index`` the Chat
# Completions one; both are the upstream's, which is the only property that
# matters here.
INDEX_KEYS = ("output_index", "index")


def _signature_of(fragment: dict[str, Any]) -> str | None:
    """The route's reasoning token for this call, if it sent one.

    Read defensively rather than trusted: the container is a vendor extension,
    so a route may send it empty, send something that is not a mapping, or not
    send it at all. Anything but a non-empty string reads as absent, which is
    the state a route that has no such token is already in.
    """
    container = fragment.get(SIGNATURE_CONTAINER_KEY)
    if not isinstance(container, dict):
        return None
    vendor = container.get(SIGNATURE_VENDOR_KEY)
    if not isinstance(vendor, dict):
        return None
    signature = vendor.get(SIGNATURE_KEY)
    return signature if isinstance(signature, str) and signature else None


@dataclass
class _PartialToolCall:
    output_index: int
    id: str = ""
    name: str = ""
    arguments: str = ""
    signature: str | None = None

    def append(
        self,
        id: str | None,
        name: str | None,
        arguments: str | None,
        signature: str | None = None,
    ) -> None:
        # First writer wins for id and name: a route that repeats them on every
        # fragment is common, and concatenating them would corrupt both. The
        # signature is one opaque token rather than text, so it is kept whole for
        # the same reason and never appended to.
        if id and not self.id:
            self.id = id
        if name and not self.name:
            self.name = name
        if signature and self.signature is None:
            self.signature = signature
        if arguments:
            self.arguments += arguments


@dataclass
class StreamAssembler:
    """Collect streamed fragments into one answer.

    Holds no opinion about transport: it is fed already-decoded chunks, which is
    what lets the interleaving test drive it directly.
    """

    text_parts: list[str] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = ""
    # The route's id for this call, first writer wins for the same reason the
    # tool-call id does: a route that repeats it on every chunk must not be able
    # to change it midway.
    request_id: str | None = None
    refusal: str | None = None
    usage_payload: dict[str, Any] | None = None
    _calls: dict[int, _PartialToolCall] = field(default_factory=dict)

    def add_chunk(self, chunk: dict[str, Any]) -> None:
        if not isinstance(chunk, dict):
            raise LLMError(f"the route streamed something that is not an object: {chunk!r}")

        if chunk.get("model"):
            self.model = str(chunk["model"])
        if chunk.get("id") and self.request_id is None:
            self.request_id = str(chunk["id"])
        if chunk.get("usage"):
            self.usage_payload = chunk["usage"]

        for choice in chunk.get("choices") or ():
            self._add_choice(choice)

    def _add_choice(self, choice: dict[str, Any]) -> None:
        if choice.get("finish_reason"):
            self.finish_reason = str(choice["finish_reason"])

        delta = choice.get("delta") or {}
        content = delta.get("content")
        if content:
            self.text_parts.append(str(content))
        if delta.get("refusal"):
            self.refusal = str(delta["refusal"])

        for fragment in delta.get("tool_calls") or ():
            self.add_tool_call_fragment(fragment)

    def add_tool_call_fragment(self, fragment: dict[str, Any]) -> None:
        """File one fragment under the index the upstream gave it."""
        index = self._index_of(fragment)
        function = fragment.get("function") or {}
        partial = self._calls.setdefault(index, _PartialToolCall(output_index=index))
        partial.append(
            id=fragment.get("id"),
            name=function.get("name"),
            arguments=function.get("arguments"),
            signature=_signature_of(fragment),
        )

    @staticmethod
    def _index_of(fragment: dict[str, Any]) -> int:
        for key in INDEX_KEYS:
            value = fragment.get(key)
            if value is not None:
                return int(value)
        # Deliberately fatal. A local counter here is the measured bug, and a
        # route that streams tool calls without an index cannot be assembled
        # safely by anyone.
        raise LLMError(
            "the route streamed a tool-call fragment with no upstream index, so "
            "there is no safe way to tell which call it belongs to"
        )

    @property
    def text(self) -> str | None:
        return "".join(self.text_parts) if self.text_parts else None

    def tool_calls(self) -> tuple[ToolCall, ...]:
        """Finish every call, in upstream index order, or raise.

        Sorted by index rather than by arrival: fragments interleave, so arrival
        order is not call order, and a caller matching results to calls by
        position needs the order the upstream meant.
        """
        return tuple(
            _finish(partial) for _, partial in sorted(self._calls.items())
        )


def _finish(partial: _PartialToolCall) -> ToolCall:
    raw = partial.arguments.strip()
    # A tool with no parameters streams nothing, or an empty object. Both mean
    # the same thing, and neither is a parse failure.
    if not raw:
        arguments: Any = {}
    else:
        try:
            arguments = json.loads(raw)
        except (TypeError, ValueError) as exc:
            llm_metrics().record_malformed_arguments(
                f"{partial.name or '<unnamed>'} (id {partial.id or '<none>'}, "
                f"index {partial.output_index}): {raw[:200]}"
            )
            raise MalformedArguments(
                f"the route returned unparseable arguments for tool "
                f"{partial.name or '<unnamed>'} (id {partial.id or '<none>'}): {exc}"
            ) from exc

    if not isinstance(arguments, dict):
        llm_metrics().record_malformed_arguments(
            f"{partial.name or '<unnamed>'}: arguments were a "
            f"{type(arguments).__name__}, not an object"
        )
        raise MalformedArguments(
            f"the route returned {type(arguments).__name__} arguments for tool "
            f"{partial.name or '<unnamed>'}, and a tool call takes an object"
        )

    return ToolCall(
        id=partial.id,
        name=partial.name,
        arguments=arguments,
        output_index=partial.output_index,
        signature=partial.signature,
    )


def parse_tool_calls(payload: list[dict[str, Any]] | None) -> tuple[ToolCall, ...]:
    """Read tool calls off a non-streamed response, under the same invariant.

    The same assembler is used rather than a second parser: one JSON-parse rule
    that two code paths share cannot drift apart, and this one is the whole
    reason the boundary is hand-rolled.

    Position stands in for the index only where the route omitted one, and only
    here: in a complete response every element already carries its own id, name
    and whole ``arguments``, so position is the upstream's own ordering rather
    than a counter that could file a fragment under the wrong call. The
    streaming path has no such guarantee, which is why it refuses instead.
    """
    assembler = StreamAssembler()
    for position, call in enumerate(payload or ()):
        fragment = dict(call)
        fragment.setdefault("index", position)
        assembler.add_tool_call_fragment(fragment)
    return assembler.tool_calls()


__all__ = ["INDEX_KEYS", "StreamAssembler", "parse_tool_calls"]
