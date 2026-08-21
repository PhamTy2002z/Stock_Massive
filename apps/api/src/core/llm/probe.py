"""Boot-time proof that the configured route honours the LLM contract."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping

from .admission import (
    BudgetLane,
    BudgetRefusal,
    CallOwner,
    OwnerType,
    SpendRequest,
)
from .config import Workload
from .protocol import (
    Completion,
    CompletionRequest,
    ContentSegment,
    JsonSchemaFormat,
    LLMClient,
    Message,
    Role,
    ToolSchema,
)

logger = logging.getLogger(__name__)

PROBE_INPUT_TOKENS = 1_000
PROBE_OUTPUT_TOKENS = 256

ECHO_TOOL = ToolSchema(
    name="probe_echo",
    description="Echo the supplied value exactly.",
    parameters={
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
        "additionalProperties": False,
    },
)
LEFT_TOOL = ToolSchema(
    name="probe_left",
    description="Return the left probe value.",
    parameters={
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
        "additionalProperties": False,
    },
)
RIGHT_TOOL = ToolSchema(
    name="probe_right",
    description="Return the right probe value.",
    parameters=LEFT_TOOL.parameters,
)
LOOP_TOOL = ToolSchema(
    name="probe_loop",
    description="Open the capability probe loop once.",
    parameters=ECHO_TOOL.parameters,
)
STRICT_FORMAT = JsonSchemaFormat(
    name="capability_probe",
    schema={
        "type": "object",
        "properties": {"ok": {"type": "boolean", "const": True}},
        "required": ["ok"],
        "additionalProperties": False,
    },
)


@dataclass(frozen=True)
class ProbeCheck:
    passed: bool
    response: str


@dataclass(frozen=True)
class ProbeResult:
    checks: Mapping[str, ProbeCheck]

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks.values())


class CapabilityProbeError(RuntimeError):
    def __init__(self, result: ProbeResult) -> None:
        failures = [
            f"{name}: received {check.response}"
            for name, check in result.checks.items()
            if not check.passed
        ]
        super().__init__("Capability Probe failed — " + "; ".join(failures))
        self.result = result


_cached_result: ProbeResult | None = None


class CapabilityProbe:
    """Run the independent route checks, once per process."""

    def __init__(
        self,
        client: LLMClient,
        model: str,
        prompt_cache_control: bool = False,
    ) -> None:
        self._client = client
        self._model = model
        # Whether the route is *configured* to send ``cache_control``. The check
        # below is what says whether it should be: caching is off by default, and
        # the only way to learn that a route accepts the field is to send it one.
        self._prompt_cache_control = prompt_cache_control
        self._run_id = uuid.uuid4().hex
        self._call_index = 0

    async def run(self) -> ProbeResult:
        global _cached_result
        if _cached_result is not None:
            return _cached_result

        checks: dict[str, ProbeCheck] = {}
        checks["forced_tool_choice"] = await self._check(
            "forced_tool_choice", self._forced_tool_choice
        )
        checks["parallel_tool_calls"] = await self._check(
            "parallel_tool_calls", self._parallel_tool_calls
        )
        checks["strict_json_schema"] = await self._check(
            "strict_json_schema", self._strict_json_schema
        )
        checks["closed_tool_loop"] = await self._check(
            "closed_tool_loop", self._closed_tool_loop
        )
        checks["prompt_cache_control"] = await self._check(
            "prompt_cache_control", self._prompt_cache_breakpoint
        )
        _cached_result = ProbeResult(checks=checks)
        return _cached_result

    async def _check(
        self,
        name: str,
        check: Callable[[], Awaitable[tuple[bool, str]]],
    ) -> ProbeCheck:
        try:
            passed, response = await check()
            return ProbeCheck(passed=passed, response=response)
        except BudgetRefusal as exc:
            if exc.reason == "probe_budget_exhausted":
                raise
            return ProbeCheck(False, f"{exc.reason}: {exc}")
        except Exception as exc:
            return ProbeCheck(False, f"{type(exc).__name__}: {exc}")

    async def _complete(self, request: CompletionRequest) -> Completion:
        self._call_index += 1
        spend = SpendRequest(
            owner=CallOwner(
                OwnerType.CAPABILITY_PROBE,
                f"{self._run_id}:{self._call_index}",
            ),
            lane=BudgetLane.EMERGENCY,
            workload=Workload.SESSION,
            input_tokens=PROBE_INPUT_TOKENS,
            output_tokens=PROBE_OUTPUT_TOKENS,
        )
        return await self._client.complete(request, spend)

    async def _forced_tool_choice(self) -> tuple[bool, str]:
        completion = await self._complete(
            CompletionRequest(
                model=self._model,
                messages=(
                    Message(role=Role.USER, content="Call probe_echo with forced."),
                ),
                tools=(ECHO_TOOL,),
                tool_choice=ECHO_TOOL.name,
                metadata={"probe_check": "forced_tool_choice"},
            )
        )
        passed = (
            len(completion.tool_calls) == 1
            and completion.tool_calls[0].name == ECHO_TOOL.name
            and completion.tool_calls[0].arguments == {"value": "forced"}
        )
        return passed, _render(completion)

    async def _parallel_tool_calls(self) -> tuple[bool, str]:
        completion = await self._complete(
            CompletionRequest(
                model=self._model,
                messages=(
                    Message(
                        role=Role.USER,
                        content="Call probe_left with 1 and probe_right with 2 in parallel.",
                    ),
                ),
                tools=(LEFT_TOOL, RIGHT_TOOL),
                tool_choice="required",
                parallel_tool_calls=True,
                metadata={"probe_check": "parallel_tool_calls"},
            )
        )
        calls = {call.name: call.arguments for call in completion.tool_calls}
        passed = calls == {"probe_left": {"value": 1}, "probe_right": {"value": 2}}
        return passed, _render(completion)

    async def _strict_json_schema(self) -> tuple[bool, str]:
        completion = await self._complete(
            CompletionRequest(
                model=self._model,
                messages=(Message(role=Role.USER, content="Return the strict probe object."),),
                response_format=STRICT_FORMAT,
                metadata={"probe_check": "strict_json_schema"},
            )
        )
        try:
            payload = json.loads(completion.text or "")
        except (TypeError, ValueError):
            payload = None
        return payload == {"ok": True}, _render(completion)

    async def _closed_tool_loop(self) -> tuple[bool, str]:
        first = await self._complete(
            CompletionRequest(
                model=self._model,
                messages=(Message(role=Role.USER, content="Open one probe tool loop."),),
                tools=(LOOP_TOOL,),
                tool_choice=LOOP_TOOL.name,
                metadata={"probe_check": "closed_tool_loop", "probe_step": 1},
            )
        )
        if len(first.tool_calls) != 1 or first.tool_calls[0].name != LOOP_TOOL.name:
            return False, _render(first)
        call = first.tool_calls[0]
        second = await self._complete(
            CompletionRequest(
                model=self._model,
                messages=(
                    Message(role=Role.USER, content="Open one probe tool loop."),
                    Message(role=Role.ASSISTANT, tool_calls=(call,)),
                    Message(
                        role=Role.TOOL,
                        content='{"closed": true}',
                        tool_call_id=call.id,
                        name=call.name,
                    ),
                ),
                tools=(LOOP_TOOL,),
                tool_choice="none",
                metadata={"probe_check": "closed_tool_loop", "probe_step": 2},
            )
        )
        passed = bool(second.text) and not second.tool_calls
        return passed, _render(second)


    async def _prompt_cache_breakpoint(self) -> tuple[bool, str]:
        """Whether this route answers a request carrying a cache breakpoint.

        The one check that can pass without a call. ``cache_control`` is
        Anthropic's spelling, an OpenAI-compatible route is free to refuse the
        request that carries it, and refusing arrives as a 400 that
        ``classify_status`` reads as a schema or an unclassified failure — so a
        deployment that has not enabled the field has nothing to prove and is not
        charged for proving it.

        With the field enabled, what is checked is acceptance rather than
        effectiveness: whether the route *served* the prefix from cache is
        visible in ``Usage.cached_input_tokens`` on real traffic, and a single
        probe call has no earlier call to have cached anything for. The response
        line records the counter anyway, because an operator reading a green
        check wants to know which of the two they are looking at.
        """
        if not self._prompt_cache_control:
            return True, "cache_control disabled by configuration"

        stable = "You are a capability probe. Answer with the word ready."
        completion = await self._complete(
            CompletionRequest(
                model=self._model,
                messages=(
                    Message(
                        role=Role.SYSTEM,
                        content=stable + " Nothing else.",
                        segments=(
                            ContentSegment(stable, cache_breakpoint=True),
                            ContentSegment(" Nothing else."),
                        ),
                    ),
                    Message(role=Role.USER, content="Say ready."),
                ),
                metadata={"probe_check": "prompt_cache_control"},
            )
        )
        cached = completion.usage.cached_input_tokens if completion.usage else 0
        return bool(completion.text), f"cached_input_tokens={cached} {_render(completion)}"


def _render(completion: Completion) -> str:
    return repr(
        {
            "text": completion.text,
            "tool_calls": [
                {"name": call.name, "arguments": dict(call.arguments)}
                for call in completion.tool_calls
            ],
            "finish_reason": completion.finish_reason,
        }
    )


def enforce_capability_probe(
    result: ProbeResult,
    *,
    alpha_desk_enabled: bool,
) -> ProbeResult:
    if result.ok:
        logger.info(
            "Capability Probe passed all %d route checks", len(result.checks)
        )
        return result
    error = CapabilityProbeError(result)
    if alpha_desk_enabled:
        raise error
    logger.warning("%s (Alpha Desk is disabled, so startup continues)", error)
    return result


def clear_capability_probe_cache() -> None:
    """Explicit test seam; production never clears a process result."""
    global _cached_result
    _cached_result = None


__all__ = [
    "CapabilityProbe",
    "CapabilityProbeError",
    "ProbeCheck",
    "ProbeResult",
    "clear_capability_probe_cache",
    "enforce_capability_probe",
]
