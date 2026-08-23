"""Planning a batch of tool calls, running it, and recording what happened."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from src.agent import executor, registry
from src.agent.guardrails import GuardrailThresholds, TurnGuardrails

CONTEXT = registry.ToolContext(user_id=7)


class Surface:
    """A handful of tools that record how they were run."""

    def __init__(self) -> None:
        self.entries: dict[str, registry.ToolEntry] = {}
        self.order: list[str] = []
        self.running = 0
        self.peak = 0

    def add(
        self,
        name: str,
        *,
        delay: float = 0.0,
        fails: bool = False,
        is_async: bool = True,
    ) -> None:
        async def handler(_context: registry.ToolContext, arguments: Mapping[str, Any]) -> Any:
            self.running += 1
            self.peak = max(self.peak, self.running)
            try:
                if delay:
                    await asyncio.sleep(delay)
                self.order.append(name)
                if fails:
                    raise RuntimeError(f"{name} is broken")
                return {"tool": name, "arguments": dict(arguments)}
            finally:
                self.running -= 1

        def blocking(_context: registry.ToolContext, arguments: Mapping[str, Any]) -> Any:
            self.order.append(name)
            return {"tool": name, "arguments": dict(arguments)}

        self.entries[name] = registry.ToolEntry(
            name=name,
            toolset="stub",
            schema=registry.object_schema({"value": {"type": "string"}}),
            handler=handler if is_async else blocking,
            description=f"stub {name}",
            display_name=f"Stub {name}",
            is_async=is_async,
        )

    def executor(self, **kwargs: Any) -> executor.ToolExecutor:
        return executor.ToolExecutor(
            context=CONTEXT,
            lookup=self.entries.get,
            availability=lambda name: name in self.entries,
            **kwargs,
        )


def call(name: str, call_id: str | None = None, arguments: Any = None) -> executor.ToolCall:
    return executor.ToolCall(id=call_id or f"call-{name}", name=name, arguments=arguments)


def test_a_batch_of_read_only_calls_is_one_parallel_segment():
    calls = [call("web_search", "a"), call("fetch_url", "b"), call("recall_facts", "c")]

    segments = executor.plan_segments(calls)

    assert len(segments) == 1
    assert segments[0][0] == "parallel"
    assert [item.id for item in segments[0][1]] == ["a", "b", "c"]


def test_a_write_becomes_its_own_barrier_without_reordering_the_batch():
    calls = [
        call("web_search", "a"),
        call("fetch_url", "b"),
        call("remember_fact", "c"),
        call("session_search", "d"),
    ]

    segments = executor.plan_segments(calls)

    assert [(mode, [item.id for item in group]) for mode, group in segments] == [
        ("parallel", ["a", "b"]),
        ("sequential", ["c"]),
        ("parallel", ["d"]),
    ]


def test_an_unknown_tool_is_treated_as_unsafe_to_overlap():
    calls = [call("web_search", "a"), call("mcp__server__do_thing", "b")]

    segments = executor.plan_segments(calls)

    assert [mode for mode, _ in segments] == ["parallel", "sequential"]
    assert "remember_fact" not in executor.PARALLEL_SAFE_TOOLS


@pytest.mark.asyncio
async def test_parallel_safe_calls_overlap_and_results_keep_the_issued_order():
    surface = Surface()
    surface.add("web_search", delay=0.05)
    surface.add("fetch_url", delay=0.01)
    surface.add("session_search", delay=0.03)
    calls = [call("web_search"), call("fetch_url"), call("session_search")]

    outcome = await surface.executor().run(calls)

    assert [result.call_id for result in outcome.results] == [
        "call-web_search",
        "call-fetch_url",
        "call-session_search",
    ]
    # They finished out of order, which is the proof they ran together.
    assert surface.order == ["fetch_url", "session_search", "web_search"]
    assert surface.peak == 3


@pytest.mark.asyncio
async def test_a_write_never_overlaps_the_reads_around_it():
    surface = Surface()
    surface.add("web_search", delay=0.02)
    surface.add("fetch_url", delay=0.02)
    surface.add("remember_fact", delay=0.02)
    calls = [call("web_search"), call("fetch_url"), call("remember_fact")]

    await surface.executor().run(calls)

    assert surface.peak == 2
    assert surface.order[-1] == "remember_fact"


@pytest.mark.asyncio
async def test_a_blocking_handler_still_returns_its_result():
    surface = Surface()
    surface.add("session_search", is_async=False)

    outcome = await surface.executor().run([call("session_search")])

    assert outcome.results[0].ok is True
    assert '"tool": "session_search"' in outcome.results[0].text


@pytest.mark.asyncio
async def test_a_tool_nobody_registered_answers_with_a_reason():
    surface = Surface()

    outcome = await surface.executor().run([call("nonexistent")])

    result = outcome.results[0]
    assert (result.ok, result.error, result.dispatched) == (
        False,
        executor.UNKNOWN_TOOL,
        False,
    )


@pytest.mark.asyncio
async def test_arguments_that_are_not_json_answer_with_a_reason():
    surface = Surface()
    surface.add("web_search")

    outcome = await surface.executor().run(
        [call("web_search", arguments="{not json")]
    )

    assert outcome.results[0].error == executor.INVALID_ARGUMENTS
    assert surface.order == []


@pytest.mark.asyncio
async def test_a_json_string_of_arguments_reaches_the_handler_parsed():
    surface = Surface()
    surface.add("web_search")

    outcome = await surface.executor().run(
        [call("web_search", arguments='{"value": "rates"}')]
    )

    assert outcome.results[0].ok is True
    assert '"value": "rates"' in outcome.results[0].text


@pytest.mark.asyncio
async def test_a_handler_that_raises_becomes_a_failed_result_not_an_exception():
    surface = Surface()
    surface.add("fetch_url", fails=True)

    outcome = await surface.executor().run([call("fetch_url")])

    assert outcome.results[0].error == executor.TOOL_FAILED
    assert "is broken" in outcome.results[0].text
    assert outcome.halted is False


@pytest.mark.asyncio
async def test_a_call_the_harness_cannot_dispatch_keeps_its_siblings_alive():
    # The registry lookup, the availability check and the trace write all sit
    # outside ``_dispatch``'s own try blocks. An exception there used to cancel
    # every sibling in the gather and throw away results already paid for.
    surface = Surface()
    surface.add("web_search")
    surface.add("fetch_url")
    surface.add("session_search")

    def lookup(name: str) -> registry.ToolEntry | None:
        if name == "fetch_url":
            raise RuntimeError("the registry is mid-reload")
        return surface.entries.get(name)

    broken = executor.ToolExecutor(
        context=CONTEXT,
        lookup=lookup,
        availability=lambda name: name in surface.entries,
    )

    outcome = await broken.run(
        [call("web_search"), call("fetch_url"), call("session_search")]
    )

    assert [result.ok for result in outcome.results] == [True, False, True]
    failed = outcome.results[1]
    assert (failed.error, failed.dispatched) == (executor.DISPATCH_FAILED, False)
    assert "fetch_url" in failed.text
    assert sorted(surface.order) == ["session_search", "web_search"]


@pytest.mark.asyncio
async def test_a_sequential_barrier_that_cannot_be_dispatched_answers_too():
    # A sequential segment runs outside the gather, so it needs the floor spelled
    # out — and a barrier is the call most likely to be a write.
    surface = Surface()
    surface.add("remember_fact")
    surface.add("forget_fact")

    def lookup(name: str) -> registry.ToolEntry | None:
        if name == "forget_fact":
            raise RuntimeError("the registry is mid-reload")
        return surface.entries.get(name)

    broken = executor.ToolExecutor(
        context=CONTEXT,
        lookup=lookup,
        availability=lambda name: name in surface.entries,
    )

    outcome = await broken.run(
        [
            call("remember_fact", "a"),
            call("forget_fact", "b"),
            call("remember_fact", "c"),
        ]
    )

    assert [result.call_id for result in outcome.results] == ["a", "b", "c"]
    assert [result.error for result in outcome.results] == [
        None,
        executor.DISPATCH_FAILED,
        None,
    ]
    # The barrier after the failure still ran: one dead call is not a dead round.
    assert surface.order == ["remember_fact", "remember_fact"]


@pytest.mark.asyncio
async def test_a_batch_past_the_round_ceiling_runs_its_head_and_answers_its_tail():
    surface = Surface()
    surface.add("session_search")
    issued = executor.MAX_CALLS_PER_ROUND + 4
    calls = [call("session_search", f"c{index}") for index in range(issued)]

    # Planning is unchanged: the ceiling is a limit on what is dispatched, not on
    # how a batch is grouped.
    segments = executor.plan_segments(calls)
    assert [(mode, len(group)) for mode, group in segments] == [("parallel", issued)]

    outcome = await surface.executor().run(calls)

    assert [result.call_id for result in outcome.results] == [
        f"c{index}" for index in range(issued)
    ]
    assert len(surface.order) == executor.MAX_CALLS_PER_ROUND
    refused = outcome.results[executor.MAX_CALLS_PER_ROUND :]
    assert all(result.error == executor.ROUND_FANOUT_EXCEEDED for result in refused)
    assert all(result.dispatched is False for result in refused)
    assert all(result.ok for result in outcome.results[: executor.MAX_CALLS_PER_ROUND])
    # The refusal says what happened, in numbers the model can act on.
    assert f"{issued} tool calls" in refused[0].text


@pytest.mark.asyncio
async def test_a_batch_at_the_round_ceiling_is_dispatched_whole():
    surface = Surface()
    surface.add("session_search")
    calls = [
        call("session_search", f"c{index}")
        for index in range(executor.MAX_CALLS_PER_ROUND)
    ]

    outcome = await surface.executor().run(calls)

    assert all(result.ok for result in outcome.results)
    assert len(surface.order) == executor.MAX_CALLS_PER_ROUND


@pytest.mark.asyncio
async def test_a_blocked_repeat_is_not_dispatched_and_carries_its_guidance():
    surface = Surface()
    surface.add("fetch_url")
    guardrails = TurnGuardrails(GuardrailThresholds(exact_failure_block_after=1))
    guardrails.after_call("fetch_url", {"value": "x"}, ok=False)

    outcome = await surface.executor(guardrails=guardrails).run(
        [call("fetch_url", arguments={"value": "x"})]
    )

    result = outcome.results[0]
    assert (result.error, result.dispatched) == (executor.BLOCKED_CALL, False)
    assert "Do not repeat it" in result.guidance
    assert surface.order == []


@pytest.mark.asyncio
async def test_a_halt_stops_the_rest_of_the_batch_but_answers_every_call():
    surface = Surface()
    surface.add("fetch_url", fails=True)
    surface.add("remember_fact")
    surface.add("session_search")
    guardrails = TurnGuardrails(GuardrailThresholds(same_tool_failure_halt_after=1))

    outcome = await surface.executor(guardrails=guardrails).run(
        [call("fetch_url"), call("remember_fact"), call("session_search")]
    )

    assert outcome.halted is True
    assert outcome.halt_reason == executor.HALTED_TURN
    assert [result.error for result in outcome.results] == [
        executor.TOOL_FAILED,
        executor.HALTED_TURN,
        executor.HALTED_TURN,
    ]
    assert surface.order == ["fetch_url"]


@pytest.mark.asyncio
async def test_a_warning_rides_with_the_result_rather_than_replacing_it():
    surface = Surface()
    surface.add("web_search")
    guardrails = TurnGuardrails()

    first = await surface.executor(guardrails=guardrails).run(
        [call("web_search", arguments={"value": "x"})]
    )
    second = await surface.executor(guardrails=guardrails).run(
        [call("web_search", arguments={"value": "x"})]
    )
    third = await surface.executor(guardrails=guardrails).run(
        [call("web_search", arguments={"value": "x"})]
    )

    assert first.results[0].guidance is None
    assert second.results[0].guidance is None
    assert "returned exactly what you already had" in third.results[0].guidance
    assert third.results[0].ok is True
    assert third.results[0].text == first.results[0].text


@pytest.mark.asyncio
async def test_every_attempted_call_leaves_a_trace_entry():
    surface = Surface()
    surface.add("web_search")
    written: list[dict[str, Any]] = []

    async def trace(entry: dict[str, Any]) -> None:
        written.append(entry)

    await surface.executor(trace=trace).run(
        [call("web_search", arguments={"value": "x"}), call("nonexistent")]
    )

    assert [entry["tool"] for entry in written] == ["web_search", "nonexistent"]
    assert written[0]["ok"] is True
    assert written[0]["arguments"] == {"value": "x"}
    assert written[1]["error"] == executor.UNKNOWN_TOOL


@pytest.mark.asyncio
async def test_a_failing_trace_writer_does_not_cost_the_answer():
    surface = Surface()
    surface.add("web_search")

    def trace(_entry: dict[str, Any]) -> None:
        raise RuntimeError("the trace store is down")

    outcome = await surface.executor(trace=trace).run([call("web_search")])

    assert outcome.results[0].ok is True


@pytest.mark.asyncio
async def test_a_tool_that_exists_but_is_switched_off_says_so():
    surface = Surface()
    surface.add("web_search")

    unavailable = executor.ToolExecutor(
        context=CONTEXT,
        lookup=surface.entries.get,
        availability=lambda _name: False,
    )
    outcome = await unavailable.run([call("web_search")])

    assert outcome.results[0].error == executor.TOOL_UNAVAILABLE
    assert surface.order == []
