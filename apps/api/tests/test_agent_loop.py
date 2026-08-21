"""The agent loop: rounds, parallel dispatch, and the error taxonomy (#80)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date
from types import MappingProxyType

import pytest

from src.agent import loop as loop_module
from src.agent.context import (
    ContextBudget,
    TranscriptToolCall,
    TranscriptTurn,
    estimate_tokens,
)
from src.core.llm.budget import TURN_OUTPUT_TOKENS
from src.agent.loop import (
    ANSWER_TRUNCATED,
    CONTENT_POLICY_BLOCKED,
    CONTEXT_OVERFLOW,
    DEADLINE_EXPIRED,
    DEFAULT_MAX_OUTPUT_TOKENS,
    EXTERNAL_TOOL_EXHAUSTED_MESSAGE,
    CONTEXT_COMPRESSION_FACTOR,
    MAX_CONTEXT_COMPRESSIONS,
    MAX_EXTERNAL_TOOL_CALLS,
    MAX_OUTPUT_CAP_REDUCTIONS,
    MAX_TOOL_ROUNDS,
    MIN_OUTPUT_TOKENS,
    MODEL_UNAVAILABLE,
    OUTPUT_CAP_EXCEEDED,
    ROUNDS_EXHAUSTED_NOTE,
    SCHEMA_REJECTED,
    SESSION_CONCURRENCY,
    AgentLoop,
    SessionCapacityExceeded,
    SessionSlots,
    ToolCallIdMismatch,
    TurnDraft,
    _TurnState,
    TurnRequest,
    TurnStatus,
    admit_round,
    assert_distinct_ids,
    pair_results,
)
from src.agent.grounding import BlockKind
from src.agent.prompt import AnswerKind, MarketState, RuntimeContext, render
from src.agent.turns import draft_content, gate_outcomes
from src.agent.tools.catalog import ToolCatalog, ToolContext, ToolDataAccess, ToolSpec
from src.alpha.refusals import AlphaRefusal
from src.core.llm import (
    AuthUnavailable,
    BudgetLane,
    ContentPolicyBlocked,
    ContextOverflow,
    DeadlineExpired,
    ModelUnavailable,
    OutputCapExceeded,
    RouteAttempt,
    SchemaRejected,
    BudgetRefusal,
    Completion,
    GatewayTimeout,
    LLMError,
    MalformedArguments,
    Message,
    ModelRefusal,
    OwnerType,
    RouteRateLimited,
    Role,
    ToolAttempts,
    ToolCall,
    Usage,
    Workload,
    llm_metrics,
)
from src.core.llm.config import (
    BudgetLanes,
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
)

SESSION_MODEL = "gpt-5.6-luna"
BATCH_MODEL = "gpt-5.6-terra"


def config() -> LLMConfig:
    prices = TokenPrices(input=1.0, cached_input=0.5, cache_write=1.5, output=8.0)
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://route.example", api_key="k"),
        models=MappingProxyType(
            {Workload.BATCH: BATCH_MODEL, Workload.SESSION: SESSION_MODEL}
        ),
        pricing=PricingTable(
            version="2026-08", effective_from=None, batch=prices, session=prices
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=100.0,
            analysis_usd=40.0,
            turn_usd=40.0,
            emergency_usd=10.0,
            eval_usd=10.0,
        ),
    )


class FakeClient:
    """A scripted route: every ``complete`` is recorded, nothing is retried."""

    def __init__(self, script=()) -> None:
        self.script = list(script)
        self.requests = []
        self.spends = []

    async def complete(self, request, spend=None):
        self.requests.append(request)
        self.spends.append(spend)
        item = self.script.pop(0) if self.script else Completion(
            model=request.model, text="Kết luận cuối cùng."
        )
        if isinstance(item, BaseException):
            raise item
        return item


# The nudge the Gate is allowed, as a fixed string so a test can look for the
# message the model was actually sent rather than for the fact that some system
# message existed.
REPAIR_NOTE_TEXT = "Attach every figure to the reference it came from."


def _state_with_note(_agent) -> "_TurnState":
    """A Turn state mid-nudge, which only the Gate reaches through ``_run``."""
    state = _TurnState()
    state.repair_note = REPAIR_NOTE_TEXT
    return state


def answer(text: str = "Kết luận.") -> Completion:
    return Completion(model=SESSION_MODEL, text=text, usage=Usage(input_tokens=10, output_tokens=5))


def wants(*names: str, prefix: str = "call", symbol: str = "FPT") -> Completion:
    """One round of tool calls, as the route would send it.

    ``symbol`` is a knob because the guardrail ladder reads *arguments*: a test
    that spends the round budget has to ask a different question each round, or
    it is testing the ladder rather than the budget (``guardrails.py``).
    """
    return Completion(
        model=SESSION_MODEL,
        tool_calls=tuple(
            ToolCall(
                id=f"{prefix}_{index}",
                name=name,
                arguments={"symbol": symbol},
                output_index=index,
            )
            for index, name in enumerate(names)
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


async def _ok(_context: ToolContext, arguments: dict) -> dict:
    return {"symbol": arguments.get("symbol"), "close": 95.4}


async def _boom(_context: ToolContext, _arguments: dict) -> dict:
    raise RuntimeError("the store is unreachable")


async def _not_in_universe(_context: ToolContext, _arguments: dict) -> dict:
    return {"reason": "not_in_universe", "suggestions": ["CTG", "VCB"]}


def spec(name: str, callable_) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"Tool {name}.",
        parameters={
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "additionalProperties": False,
        },
        callable=callable_,
    )


def catalog(*specs, traces=None) -> ToolCatalog:
    registrations = specs or (
        spec("get_analysis", _ok),
        spec("get_price_series", _ok),
        spec("broken", _boom),
        spec("outside", _not_in_universe),
    )
    return ToolCatalog(
        registrations,
        trace_writer=(traces.append if traces is not None else (lambda _trace: None)),
    )


def turn_request(**overrides) -> TurnRequest:
    base = dict(
        thread_id="11111111-1111-1111-1111-111111111111",
        request_message_id=42,
        user_id=7,
        user_text="FPT đang ở vùng nào?",
        runtime=RuntimeContext(
            user_id=7,
            trading_day=date(2026, 8, 14),
            today=date(2026, 8, 16),
            market_state=MarketState.POST_CLOSE,
            active_symbol="FPT",
        ),
    )
    base.update(overrides)
    return TurnRequest(**base)


def loop(client, tools=None, **overrides) -> AgentLoop:
    return AgentLoop(
        client=client,
        catalog=tools or catalog(),
        config=config(),
        budget=ContextBudget(max_tokens=30_000),
        **overrides,
    )


# --- rounds ---------------------------------------------------------------


def test_the_module_docstring_states_the_round_count_the_constant_holds():
    """The docstring said eight while the constant said four, for months.

    The number is not free to choose — it is one half of the arithmetic the test
    below holds — so a docstring that disagrees with it is a docstring that
    invites somebody to raise the other half.
    """
    from src.agent import loop as loop_module

    assert MAX_TOOL_ROUNDS == 4
    heading = loop_module.__doc__.split("Four rather than eight")[0]
    assert "Four tool-call rounds" in heading
    assert "all four lookup steps" in heading
    assert "Eight" not in heading


def test_the_turn_cannot_outspend_what_it_was_admitted_against():
    # Admission funds a Turn against one aggregate output ceiling while the loop
    # spends it one call at a time. Raising the per-call ceiling or the number of
    # rounds without lowering the other is how a Turn quietly outgrows the cost
    # Budget Validation proved against the price table.
    assert (MAX_TOOL_ROUNDS + 1) * DEFAULT_MAX_OUTPUT_TOKENS <= TURN_OUTPUT_TOKENS


@pytest.mark.asyncio
async def test_a_truncated_completion_ends_the_turn_instead_of_passing_as_an_answer():
    # A reasoning route bills its thinking against the same per-call ceiling, so
    # it can spend the whole allowance and return the first few words of a reply.
    # Released as a complete Turn, that fragment reads as the whole answer.
    client = FakeClient([
        Completion(
            model=SESSION_MODEL,
            text="The user",
            finish_reason="length",
            usage=Usage(input_tokens=9_773, output_tokens=2_000),
        )
    ])

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == ANSWER_TRUNCATED
    # What did arrive is kept: the reader sees the fragment and the sentence
    # saying it stopped, rather than an empty Turn.
    assert outcome.text == "The user"



@pytest.mark.asyncio
async def test_a_turn_runs_its_rounds_then_answers_with_tool_choice_none():
    client = FakeClient(
        [
            wants("get_analysis", prefix=f"r{n}", symbol=f"SYM{n}")
            for n in range(20)
        ]
    )

    outcome = await loop(client).run(turn_request())

    assert outcome.rounds_used == MAX_TOOL_ROUNDS
    assert outcome.rounds_exhausted is True
    assert outcome.status is TurnStatus.COMPLETE
    assert len(client.requests) == MAX_TOOL_ROUNDS + 1
    assert [request.tool_choice for request in client.requests] == (
        ["auto"] * MAX_TOOL_ROUNDS + ["none"]
    )
    note = client.requests[-1].messages[-1]
    assert note.role is Role.SYSTEM
    assert note.content == ROUNDS_EXHAUSTED_NOTE
    assert f"{MAX_TOOL_ROUNDS} lookup rounds" in note.content


@pytest.mark.asyncio
async def test_a_turn_that_needs_no_tool_ends_after_one_call():
    client = FakeClient([answer("Đây là kiến thức chung.")])

    outcome = await loop(client).run(turn_request())

    assert len(client.requests) == 1
    assert outcome.rounds_used == 0
    assert outcome.rounds_exhausted is False
    assert outcome.text == "Đây là kiến thức chung."
    assert outcome.answer_kind is AnswerKind.EDUCATION


@pytest.mark.asyncio
async def test_the_constructed_context_never_exceeds_the_ceiling_with_the_note():
    # Derived from the Contract rather than written as a number: the system
    # prompt is a fixed cost in every call, so a hand-picked ceiling that
    # happens to sit above today's prose fails the day a section is added —
    # which says nothing about the ladder this test exercises. The headroom is
    # what the ladder gets to work in.
    request = turn_request()
    floor = estimate_tokens(Message(role=Role.SYSTEM, content=render(request.runtime)))
    ceiling = floor + 2_000

    client = FakeClient([wants("get_analysis", prefix=f"r{n}") for n in range(20)])
    agent = AgentLoop(
        client=client,
        catalog=catalog(),
        config=config(),
        budget=ContextBudget(max_tokens=ceiling),
    )

    await agent.run(request)

    for spend in client.spends:
        assert spend.input_tokens <= ceiling


# --- parallel dispatch and the id assertion -------------------------------


@pytest.mark.asyncio
async def test_parallel_calls_in_one_round_dispatch_concurrently():
    arrived = asyncio.Event()
    both = asyncio.Event()
    seen: list[str] = []

    async def gate(_context: ToolContext, _arguments: dict) -> dict:
        seen.append("in")
        if len(seen) == 2:
            both.set()
        arrived.set()
        # Serial dispatch would deadlock here; concurrent dispatch does not.
        await asyncio.wait_for(both.wait(), timeout=1)
        return {"ok": True}

    client = FakeClient([wants("first", "second"), answer()])
    tools = catalog(spec("first", gate), spec("second", gate))

    outcome = await loop(client, tools).run(turn_request())

    assert len(outcome.tool_calls) == 2
    assert all(call.result == {"ok": True} for call in outcome.tool_calls)


@pytest.mark.asyncio
async def test_one_failing_tool_does_not_kill_the_round():
    client = FakeClient([wants("get_analysis", "broken"), answer()])

    outcome = await loop(client).run(turn_request())

    healthy, failed = outcome.tool_calls
    assert healthy.result["close"] == 95.4
    assert failed.result["status"] == "tool_error"
    assert "unreachable" in failed.result["error"]
    assert outcome.status is TurnStatus.COMPLETE


def test_a_result_under_the_wrong_id_fails_loudly_and_is_never_handed_back():
    calls = (
        ToolCall(id="call_a", name="get_analysis", arguments={}),
        ToolCall(id="call_b", name="get_price_series", arguments={}),
    )

    assert pair_results(calls, (("call_a", {"ok": 1}), ("call_b", {"ok": 2})))

    with pytest.raises(ToolCallIdMismatch, match="cannot be trusted"):
        pair_results(calls, (("call_a", {"ok": 1}), ("call_a", {"ok": 2})))
    with pytest.raises(ToolCallIdMismatch, match="got back"):
        pair_results(calls, (("call_a", {"ok": 1}),))


def test_a_repeated_or_missing_tool_call_id_is_a_malformed_arguments():
    with pytest.raises(ToolCallIdMismatch, match="repeated"):
        assert_distinct_ids(
            (
                ToolCall(id="same", name="get_analysis", arguments={}),
                ToolCall(id="same", name="get_price_series", arguments={}),
            )
        )
    with pytest.raises(ToolCallIdMismatch, match="no tool-call id"):
        assert_distinct_ids((ToolCall(id="", name="get_analysis", arguments={}),))

    assert issubclass(ToolCallIdMismatch, MalformedArguments)


@pytest.mark.asyncio
async def test_a_repeated_id_from_the_route_fails_the_turn_before_any_dispatch():
    dispatched: list[str] = []

    async def watched(_context: ToolContext, _arguments: dict) -> dict:
        dispatched.append("called")
        return {"ok": True}

    repeated = Completion(
        model=SESSION_MODEL,
        tool_calls=(
            ToolCall(id="dup", name="watched", arguments={}),
            ToolCall(id="dup", name="watched", arguments={}),
        ),
    )
    client = FakeClient([repeated])
    llm_metrics().reset()

    with pytest.raises(ToolCallIdMismatch):
        await loop(client, catalog(spec("watched", watched))).run(turn_request())

    assert dispatched == []
    # Counted and logged loudly; the operator flips the flag, not the code.
    assert llm_metrics().malformed_arguments == 1


# --- the error taxonomy ---------------------------------------------------


@pytest.mark.asyncio
async def test_tool_error_is_returned_to_the_model_and_capped_at_two_attempts():
    attempts: list[str] = []

    async def always_fails(_context: ToolContext, _arguments: dict) -> dict:
        attempts.append("try")
        raise RuntimeError("nope")

    client = FakeClient(
        [
            wants("flaky", prefix="a"),
            wants("flaky", prefix="b"),
            wants("flaky", prefix="c"),
            wants("flaky", prefix="d"),
            answer(),
        ]
    )

    outcome = await loop(client, catalog(spec("flaky", always_fails))).run(turn_request())

    assert len(attempts) == 2
    assert outcome.status is TurnStatus.COMPLETE
    refused = outcome.tool_calls[-1].result
    assert refused["status"] == "tool_error"
    assert "already failed twice" in refused["error"]


def test_a_healthy_fan_out_is_never_gated_but_a_retry_spends_its_allowance():
    """The cap governs retries; one tool asked about three symbols is not one."""
    fan_out = tuple(
        ToolCall(id=f"call_{n}", name="get_price_series", arguments={}, output_index=n)
        for n in range(3)
    )

    untouched = ToolAttempts()
    assert admit_round(fan_out, untouched) == (True, True, True)

    once_failed = ToolAttempts()
    once_failed.record_failure("get_price_series")
    assert admit_round(fan_out, once_failed) == (True, False, False)

    twice_failed = ToolAttempts()
    twice_failed.record_failure("get_price_series")
    twice_failed.record_failure("get_price_series")
    assert admit_round(fan_out, twice_failed) == (False, False, False)


@pytest.mark.asyncio
async def test_three_parallel_calls_to_one_healthy_tool_all_dispatch():
    dispatched: list[str] = []

    async def counted(_context: ToolContext, arguments: dict) -> dict:
        dispatched.append(str(arguments.get("symbol")))
        return {"close": 95.4}

    fan_out = Completion(
        model=SESSION_MODEL,
        tool_calls=tuple(
            ToolCall(
                id=f"call_{n}",
                name="get_price_series",
                arguments={"symbol": symbol},
                output_index=n,
            )
            for n, symbol in enumerate(("FPT", "VCB", "HPG"))
        ),
    )
    client = FakeClient([fan_out, answer()])

    outcome = await loop(client, catalog(spec("get_price_series", counted))).run(
        turn_request()
    )

    assert sorted(dispatched) == ["FPT", "HPG", "VCB"]
    assert len(outcome.tool_calls) == 3
    assert all("error" not in call.result for call in outcome.tool_calls)


@pytest.mark.asyncio
async def test_external_calls_share_one_turn_budget_across_parallel_fan_out():
    dispatched: list[str] = []

    async def external(_context: ToolContext, arguments: dict) -> dict:
        dispatched.append(str(arguments.get("symbol")))
        return {"external_claim": {"claim_class": "external_claim", "result": 1}}

    external_spec = ToolSpec(
        name="external_lookup",
        description="A test external capability.",
        parameters={"type": "object", "properties": {"symbol": {"type": "string"}}},
        callable=external,
        data_access=ToolDataAccess.EXTERNAL,
    )
    # One symbol per call: the budget under test is the *number* of external
    # calls, and seven copies of one call is a repetition the guardrail ladder
    # refuses before this bound is ever reached (``guardrails.py``).
    fan_out = Completion(
        model=SESSION_MODEL,
        tool_calls=tuple(
            ToolCall(
                id=f"call_{index}",
                name="external_lookup",
                arguments={"symbol": f"SYM{index}"},
                output_index=index,
            )
            for index in range(MAX_EXTERNAL_TOOL_CALLS + 1)
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )
    client = FakeClient([fan_out, answer()])

    outcome = await loop(client, catalog(external_spec)).run(turn_request())

    assert len(dispatched) == MAX_EXTERNAL_TOOL_CALLS
    refused = outcome.tool_calls[-1].result
    assert refused["status"] == "tool_error"
    assert refused["error"] == EXTERNAL_TOOL_EXHAUSTED_MESSAGE


@pytest.mark.asyncio
async def test_malformed_arguments_raises_immediately_and_disables_nothing():
    client = FakeClient([MalformedArguments("the route returned invalid JSON")])

    with pytest.raises(MalformedArguments):
        await loop(client).run(turn_request())

    assert len(client.requests) == 1  # raised immediately, never re-prompted

    # No code path disabled the route: the very next Turn still dispatches.
    healthy = FakeClient([answer("Vẫn chạy.")])
    outcome = await loop(healthy).run(turn_request())
    assert outcome.text == "Vẫn chạy."
    assert config().enabled is True


@pytest.mark.asyncio
async def test_gateway_timeout_is_not_retried_again_inside_the_loop():
    client = FakeClient([GatewayTimeout("the route did not answer (504)")])

    outcome = await loop(client).run(turn_request())

    assert len(client.requests) == 1
    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "gateway_timeout"


@pytest.mark.asyncio
async def test_a_gateway_timeout_says_how_much_was_spent_reaching_it(caplog):
    """Measured: this branch ended Turns without logging anything at all.

    It was the largest single source of Turns that died on the route, and the
    only one with no line to classify it by — so the share of route failures
    that were timeouts was a guess. What a timeout needs beyond its message is
    how much was spent: a route that never spoke and a route that broke off
    mid-answer are different incidents wearing the same class.
    """
    client = FakeClient(
        [
            GatewayTimeout(
                "the route did not answer (504)",
                attempt=RouteAttempt(
                    attempts=2, elapsed_seconds=118.4, bytes_received=8_192
                ),
            )
        ]
    )

    with caplog.at_level("WARNING"):
        outcome = await loop(client).run(turn_request())

    assert outcome.terminal_reason == "gateway_timeout"
    line = next(
        record.message for record in caplog.records if "gateway timeout" in record.message
    )
    assert "2 attempt(s)" in line
    assert "118.4s" in line
    assert "8192 byte(s)" in line


@pytest.mark.asyncio
async def test_a_timeout_with_no_measurements_still_logs_a_classifiable_line(caplog):
    """The diagnostics are additive, so their absence must not lose the line."""
    client = FakeClient([GatewayTimeout("the route did not answer (504)")])

    with caplog.at_level("WARNING"):
        await loop(client).run(turn_request())

    assert any("gateway timeout" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_no_route_failure_log_carries_a_credential(caplog):
    """A route that quotes the request it refused quotes the header with it.

    Every one of these branches copies the route's own words into a log line,
    which makes redaction a property of the branch rather than a courtesy: a key
    that reaches a log file once has to be rotated.
    """
    echoed = 'refused: {"headers":{"Authorization":"Bearer sk-livekey0123456789"}}'
    for factory in (
        GatewayTimeout,
        ContextOverflow,
        OutputCapExceeded,
        ContentPolicyBlocked,
        ModelUnavailable,
        SchemaRejected,
        LLMError,
    ):
        caplog.clear()
        # Enough copies for the two classes the loop now recovers from to run out
        # of recoveries: the terminal line is the one that copies the route's
        # words, and a class that recovered never reaches it.
        script = [factory(echoed) for _ in range(MAX_CONTEXT_COMPRESSIONS + 1)]
        with caplog.at_level("INFO"):
            await loop(FakeClient(script)).run(turn_request(history=long_history()))
        assert caplog.records, f"{factory.__name__} logged nothing"
        for record in caplog.records:
            assert "sk-livekey0123456789" not in record.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "reason", "calls"),
    [
        # The first two are recovered from before they are terminal, so reaching
        # the reason costs the whole recovery budget; the last three are terminal
        # on arrival, and a second call would be one nothing could learn from.
        (ContextOverflow("the transcript does not fit (400)"), CONTEXT_OVERFLOW, 3),
        (
            OutputCapExceeded("the output ceiling does not fit (400)"),
            OUTPUT_CAP_EXCEEDED,
            3,
        ),
        (ContentPolicyBlocked("the filter refused (400)"), CONTENT_POLICY_BLOCKED, 1),
        (ModelUnavailable("the model is not served (404)"), MODEL_UNAVAILABLE, 1),
        (SchemaRejected("the tool schemas were refused (400)"), SCHEMA_REJECTED, 1),
    ],
)
async def test_each_named_route_condition_ends_the_turn_under_its_own_reason(
    error, reason, calls
):
    """`route_error` is no longer one bucket holding five different remedies.

    The reason is what the ops snapshot groups by, so a condition without its own
    reason cannot be counted — and the share of Turns lost to an oversized
    transcript versus a retired model is the number that chose the recovery each
    one now gets.
    """
    client = FakeClient([error] * calls)

    outcome = await loop(client).run(turn_request(history=long_history()))

    assert len(client.requests) == calls
    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == reason


def long_history(turns: int = 12) -> tuple[TranscriptTurn, ...]:
    """A transcript with enough behind it that the ladder has something to drop."""
    return tuple(
        TranscriptTurn(
            user_text=f"Câu hỏi {index} về FPT và thị trường",
            tool_calls=(
                TranscriptToolCall(
                    call_id=f"h{index}",
                    name="get_analysis",
                    arguments={"symbol": "FPT"},
                    result={"rows": ["x" * 400 for _ in range(6)]},
                ),
            ),
            assistant_text="Trả lời cũ. " * 40,
        )
        for index in range(turns)
    )


@pytest.mark.asyncio
async def test_an_oversized_transcript_is_compressed_and_asked_again():
    """The route measures what this loop only estimates.

    A ``ContextOverflow`` says the estimate that fit was wrong, so the next call
    is constructed against a smaller ceiling instead of the Turn ending. The
    second request carries strictly fewer input tokens than the first, which is
    the whole content of the word *compressed*.
    """
    client = FakeClient([ContextOverflow("the transcript does not fit (400)")])

    outcome = await loop(client).run(turn_request(history=long_history()))

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.terminal_reason is None
    assert len(client.requests) == 2
    assert client.spends[1].input_tokens < client.spends[0].input_tokens
    assert client.spends[1].lane is BudgetLane.TURN


@pytest.mark.asyncio
async def test_compression_stops_rather_than_thrashing():
    """Two attempts, then the reason stands.

    A Turn that compresses forever spends a call per attempt to discover that
    compression is not converging, which is a more expensive way of reaching the
    same blank screen.
    """
    overflow = ContextOverflow("the transcript does not fit (400)")
    client = FakeClient([overflow] * 10)

    outcome = await loop(client).run(turn_request(history=long_history()))

    assert len(client.requests) == MAX_CONTEXT_COMPRESSIONS + 1
    assert outcome.terminal_reason == CONTEXT_OVERFLOW


@pytest.mark.asyncio
async def test_a_short_turn_is_not_charged_for_a_compression_that_gives_nothing():
    """The prompt is most of a short Turn's input, and it is not compressible.

    The ladder protects the current Turn and there is no older one to drop, so
    the constructed context after compressing is the context that was just
    refused. Sending it again would buy one more refusal.
    """
    client = FakeClient([ContextOverflow("the transcript does not fit (400)")] * 5)

    outcome = await loop(client).run(turn_request())

    assert len(client.requests) == 1
    assert outcome.terminal_reason == CONTEXT_OVERFLOW


@pytest.mark.asyncio
async def test_a_ceiling_the_ladder_cannot_meet_still_ends_under_its_own_reason():
    """The compression probe can fail, and the reason must survive it.

    ``build_messages`` raises ``ConstructedContextTooLarge`` when even the
    protected Turn fully collapsed breaks the ceiling. That is not an
    ``LLMError``, so unhandled it escapes to the Turn lifecycle's catch-all and
    the Turn ends ``turn_failed`` — losing the classification this branch exists
    to record.
    """
    request = turn_request(history=long_history())
    floor = estimate_tokens(Message(role=Role.SYSTEM, content=render(request.runtime)))
    client = FakeClient([ContextOverflow("the transcript does not fit (400)")] * 5)
    agent = AgentLoop(
        client=client,
        catalog=catalog(),
        config=config(),
        # Fits at full size, and cannot fit once compressed: the compressed
        # ceiling lands below the system prompt the ladder cannot drop.
        budget=ContextBudget(max_tokens=int(floor / CONTEXT_COMPRESSION_FACTOR) + 500),
    )

    outcome = await agent.run(request)

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == CONTEXT_OVERFLOW


@pytest.mark.asyncio
async def test_one_round_cannot_spend_the_whole_turn_deadline(monkeypatch):
    """Five calls at the per-call ceiling would reach the Turn deadline.

    And the Turn deadline ends a Turn through the lifecycle rather than through
    the terminal branch that names the route condition, so the round carries its
    own bound and gives up inside the branch that can still report. The budget is
    zeroed here rather than waited out: a test that proves a ten-minute bound by
    taking ten minutes is a test nobody runs.
    """
    monkeypatch.setattr(loop_module, "ROUND_TIMEOUT_MULTIPLE", 0.0)
    client = FakeClient([ContextOverflow("the transcript does not fit (400)")] * 5)

    outcome = await loop(client).run(turn_request(history=long_history()))

    # One call, and the reason is still the route's rather than the deadline's.
    assert len(client.requests) == 1
    assert outcome.terminal_reason == CONTEXT_OVERFLOW


@pytest.mark.asyncio
async def test_a_refused_output_ceiling_is_lowered_rather_than_trimming_evidence():
    """The opposite remedy to the one above, and never confused with it.

    Here the transcript fits: what did not fit is the ceiling reserved for the
    answer. So the ceiling comes down and the transcript is left alone — trimming
    it would discard evidence the Turn already paid for.
    """
    client = FakeClient([OutputCapExceeded("the output ceiling does not fit (400)")])

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.COMPLETE
    assert len(client.requests) == 2
    assert client.requests[0].max_output_tokens == DEFAULT_MAX_OUTPUT_TOKENS
    assert client.requests[1].max_output_tokens < DEFAULT_MAX_OUTPUT_TOKENS
    # What was reserved moves with what was asked for, or the ledger funds a
    # ceiling the request no longer carries.
    assert client.spends[1].output_tokens == client.requests[1].max_output_tokens
    # The transcript is untouched by this recovery.
    assert client.spends[1].input_tokens == client.spends[0].input_tokens


@pytest.mark.asyncio
async def test_the_output_ceiling_never_falls_below_a_usable_answer():
    """An answer cut off mid-sentence is not a recovered Turn.

    ``answer_truncated`` is a failure this file already fixed once, so the floor
    is a floor: the ceiling stops falling and the Turn ends under its own reason
    rather than buying a call whose answer cannot be released.
    """
    capped = OutputCapExceeded("the output ceiling does not fit (400)")
    client = FakeClient([capped] * 10)

    outcome = await loop(client).run(turn_request())

    assert outcome.terminal_reason == OUTPUT_CAP_EXCEEDED
    assert len(client.requests) == MAX_OUTPUT_CAP_REDUCTIONS + 1
    assert all(
        request.max_output_tokens >= MIN_OUTPUT_TOKENS for request in client.requests
    )


@pytest.mark.asyncio
async def test_our_own_deadline_is_not_the_routes_deadline(caplog):
    """Two facts that used to share one reason and one log line.

    An expiry on this side points at the connection pool or at a deadline set
    too low for the model; a 504 points at the route. The ops snapshot can only
    tell them apart if the Turn records which one happened.
    """
    expired = DeadlineExpired(
        "this process stopped waiting for the route: ReadTimeout",
        attempt=RouteAttempt(attempts=2, elapsed_seconds=120.0, bytes_received=0),
    )
    client = FakeClient([expired])

    with caplog.at_level("WARNING"):
        outcome = await loop(client).run(turn_request())

    assert outcome.terminal_reason == DEADLINE_EXPIRED
    assert outcome.terminal_reason != "gateway_timeout"
    assert any("stopped waiting" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_a_compression_keeps_the_nudge_it_had_not_spent_yet():
    """A note paid for and not delivered is the one thing worse than no note.

    The Gate's single nudge costs a whole model call. It is cleared when a call
    carries it, not when a call is *built* with it, so a compression between the
    two does not throw it away.
    """
    client = FakeClient([ContextOverflow("the transcript does not fit (400)")])
    agent = loop(client)
    state = _state_with_note(agent)
    request = turn_request(history=long_history())

    completion = await agent._call(
        render(request.runtime),
        request,
        state,
        final=False,
        repairing=True,
    )

    assert completion is not None
    assert state.repair_note is None
    assert state.compressions == 1
    # Both calls carried the note: the first was refused, the second delivered it.
    assert all(
        any(
            message.content == REPAIR_NOTE_TEXT
            for message in request.messages
        )
        for request in client.requests
    )


@pytest.mark.asyncio
async def test_the_five_named_conditions_do_not_end_up_as_route_error():
    """Guards the `except` ordering: all five subclass `LLMError`."""
    reasons = set()
    for factory in (
        ContextOverflow,
        OutputCapExceeded,
        ContentPolicyBlocked,
        ModelUnavailable,
        SchemaRejected,
    ):
        script = [factory("x") for _ in range(MAX_CONTEXT_COMPRESSIONS + 1)]
        outcome = await loop(FakeClient(script)).run(
            turn_request(history=long_history())
        )
        reasons.add(outcome.terminal_reason)

    assert "route_error" not in reasons
    assert len(reasons) == 5


@pytest.mark.asyncio
async def test_a_rate_limited_route_ends_the_turn_under_its_own_reason():
    """Not a timeout: the route answered, and the remedy is credits or a wait."""
    client = FakeClient(
        [RouteRateLimited("the route is out of allowance (429)", retry_after=30.0)]
    )

    outcome = await loop(client).run(turn_request())

    assert len(client.requests) == 1
    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "route_rate_limited"


@pytest.mark.asyncio
async def test_auth_unavailable_is_never_retried_and_surfaces_re_auth_needed():
    client = FakeClient([AuthUnavailable("the route rejected the credential (401)")])

    outcome = await loop(client).run(turn_request())

    assert len(client.requests) == 1
    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "auth_unavailable"


@pytest.mark.asyncio
async def test_a_tool_whose_channel_died_ends_the_turn_the_same_way():
    async def dead_credential(_context: ToolContext, _arguments: dict) -> dict:
        raise AuthUnavailable("the news channel's credential died")

    client = FakeClient([wants("search_news"), answer()])

    outcome = await loop(client, catalog(spec("search_news", dead_credential))).run(
        turn_request()
    )

    assert outcome.terminal_reason == "auth_unavailable"
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_a_dead_credential_does_not_discard_the_round_it_shared():
    async def dead_credential(_context: ToolContext, _arguments: dict) -> dict:
        raise AuthUnavailable("the news channel's credential died")

    client = FakeClient([wants("get_analysis", "search_news"), answer()])
    tools = catalog(spec("get_analysis", _ok), spec("search_news", dead_credential))

    outcome = await loop(client, tools).run(turn_request())

    assert outcome.terminal_reason == "auth_unavailable"
    # The store read that succeeded beside it is still on the Turn.
    assert [call.name for call in outcome.tool_calls] == ["get_analysis"]
    assert outcome.tool_calls[0].result["close"] == 95.4


@pytest.mark.asyncio
async def test_a_model_refusal_is_shown_verbatim_and_never_re_prompted():
    client = FakeClient([ModelRefusal("Tôi không thể hỗ trợ việc này.")])

    outcome = await loop(client).run(turn_request())

    assert len(client.requests) == 1
    assert outcome.text == "Tôi không thể hỗ trợ việc này."
    assert outcome.terminal_reason == "model_refusal"
    assert outcome.answer_kind is AnswerKind.REFUSAL


@pytest.mark.asyncio
async def test_any_other_route_failure_ends_the_turn_incomplete(caplog):
    client = FakeClient([LLMError("the route refused the request (400)")])

    with caplog.at_level("WARNING"):
        outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "route_error"
    # The reason is one word for every route failure that is not its own class,
    # so what the route said has to reach the log or it reaches nobody.
    assert any(
        "the route refused the request (400)" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_the_second_round_hands_back_the_token_the_first_round_issued():
    # Gemini 3.x refuses a round whose function calls arrive without the
    # signature it issued for them, so the loop has to carry it across rounds.
    signed = Completion(
        model=SESSION_MODEL,
        tool_calls=(
            ToolCall(
                id="call_0",
                name="get_analysis",
                arguments={"symbol": "FPT"},
                output_index=0,
                signature="Eu0CCuo",
            ),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )
    client = FakeClient([signed, answer()])

    await loop(client).run(turn_request())

    second = client.requests[1]
    (assistant,) = [m for m in second.messages if m.role is Role.ASSISTANT]
    (call,) = assistant.tool_calls
    assert call.signature == "Eu0CCuo"


# --- money ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_model_call_carries_a_turn_spend_reservation():
    client = FakeClient([wants("get_analysis"), answer()])

    await loop(client).run(turn_request())

    assert len(client.spends) == 2
    for spend in client.spends:
        assert spend is not None
        assert spend.lane is BudgetLane.TURN
        assert spend.workload is Workload.SESSION
        assert spend.owner.type is OwnerType.TURN_REQUEST_MESSAGE
        assert spend.owner.id == "42"
        assert spend.owner.user_id == 7
        assert spend.input_tokens > 0
        assert spend.output_tokens > 0


@pytest.mark.asyncio
async def test_a_turn_that_cannot_fund_its_next_call_makes_no_further_call():
    saved: list = []
    client = FakeClient(
        [
            wants("get_analysis"),
            BudgetRefusal("turn_cost", "This Turn has exhausted its allowance."),
        ]
    )
    agent = AgentLoop(
        client=client,
        catalog=catalog(),
        config=config(),
        checkpoint=saved.append,
    )

    outcome = await agent.run(turn_request())

    assert len(client.requests) == 2  # the refused one is the last
    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "turn_cost"
    # The partial answer and the traces of what ran survive.
    assert len(outcome.tool_calls) == 1
    assert outcome.tool_calls[0].result["close"] == 95.4
    assert saved and saved[-1].tool_calls


@pytest.mark.asyncio
async def test_the_loop_uses_the_session_model_and_chooses_no_other():
    client = FakeClient([wants("get_analysis"), answer()])

    await loop(client).run(turn_request())

    assert {request.model for request in client.requests} == {SESSION_MODEL}
    assert BATCH_MODEL not in {request.model for request in client.requests}


# --- cancellation and concurrency -----------------------------------------


@pytest.mark.asyncio
async def test_cancellation_completes_the_in_flight_tool_call_then_persists():
    finished: list[str] = []
    saved: list = []
    stop = {"value": False}

    async def slow_and_cancel(_context: ToolContext, _arguments: dict) -> dict:
        # The cancel arrives while this read-only call is in flight.
        stop["value"] = True
        await asyncio.sleep(0)
        finished.append("done")
        return {"ok": True}

    client = FakeClient([wants("slow"), answer("Không bao giờ tới đây.")])
    agent = AgentLoop(
        client=client,
        catalog=catalog(spec("slow", slow_and_cancel)),
        config=config(),
        checkpoint=saved.append,
    )

    outcome = await agent.run(turn_request(), lambda: stop["value"])

    assert finished == ["done"]  # the in-flight call was allowed to complete
    assert outcome.status is TurnStatus.CANCELLED
    assert outcome.terminal_reason == "cancelled_by_user"
    assert len(outcome.tool_calls) == 1
    assert len(client.requests) == 1  # no further model call after the cancel
    assert saved[-1].tool_calls


@pytest.mark.asyncio
async def test_a_turn_cancelled_before_its_first_call_never_reaches_the_route():
    saved: list = []
    client = FakeClient([answer()])
    agent = AgentLoop(
        client=client, catalog=catalog(), config=config(), checkpoint=saved.append
    )

    outcome = await agent.run(turn_request(), lambda: True)

    assert client.requests == []
    assert outcome.status is TurnStatus.CANCELLED
    # Every terminal path checkpoints, including this one.
    assert len(saved) == 1
    assert saved[0].tool_calls == ()


@pytest.mark.asyncio
async def test_unlimited_slots_never_refuse_a_concurrent_turn():
    """``limit=None`` is the configured ``active_turns_system`` being unlimited."""
    slots = SessionSlots(limit=None)
    release = asyncio.Event()

    async def holder():
        async with slots.occupy():
            await release.wait()

    held = [asyncio.create_task(holder()) for _ in range(12)]
    await asyncio.sleep(0)

    assert slots.full is False
    async with slots.occupy():
        pass

    release.set()
    await asyncio.gather(*held)


@pytest.mark.asyncio
async def test_a_fourth_concurrent_session_is_refused_immediately_and_never_queued():
    slots = SessionSlots()
    release = asyncio.Event()

    async def holder():
        async with slots.occupy():
            await release.wait()

    held = [asyncio.create_task(holder()) for _ in range(SESSION_CONCURRENCY)]
    await asyncio.sleep(0)

    with pytest.raises(SessionCapacityExceeded) as refused:
        async with slots.occupy():  # pragma: no cover - must not be entered
            pass

    assert refused.value.status_code == 503
    assert refused.value.reason == "system_active_turns"

    release.set()
    await asyncio.gather(*held)

    # The slot is given back, so the next session is admitted.
    async with slots.occupy():
        pass


@pytest.mark.asyncio
async def test_the_loop_refuses_the_fourth_session_through_its_own_slots():
    slots = SessionSlots(limit=1)
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingClient(FakeClient):
        async def complete(self, request, spend=None):
            started.set()
            await release.wait()
            return answer()

    agent = AgentLoop(client=BlockingClient(), catalog=catalog(), config=config(), slots=slots)
    first = asyncio.create_task(agent.run(turn_request()))
    await started.wait()

    with pytest.raises(SessionCapacityExceeded):
        await agent.run(turn_request())

    release.set()
    await first


@pytest.mark.asyncio
async def test_the_refusal_reaches_the_client_as_a_503_with_no_retry_after():
    """The application's registered handler is what makes the 503 real."""
    from src.main import app

    handler = app.exception_handlers[AlphaRefusal]
    response = await handler(None, SessionCapacityExceeded())

    assert response.status_code == 503
    assert json.loads(response.body)["detail"] == {
        "reason": "system_active_turns",
        "message": "The service is at its active Turn capacity. Try again shortly.",
    }
    # No Retry-After: the only number that could go there is a guess at when
    # someone else's Turn ends.
    assert "retry-after" not in {name.lower() for name in response.headers}


# --- answer classification -------------------------------------------------


@pytest.mark.asyncio
async def test_grounded_evidence_makes_an_analysis_and_a_universe_refusal_does_not():
    grounded = FakeClient([wants("get_analysis"), answer()])
    assert (await loop(grounded).run(turn_request())).answer_kind is AnswerKind.ANALYSIS

    refused = FakeClient([wants("outside"), answer()])
    outcome = await loop(refused).run(turn_request())
    assert outcome.answer_kind is AnswerKind.REFUSAL


@pytest.mark.asyncio
async def test_any_structured_refusal_is_not_counted_as_grounded_evidence():
    """A refusal that is not `not_in_universe` is still not evidence."""

    async def needs_more_history(_context: ToolContext, _arguments: dict) -> dict:
        return {"reason": "edge_and_variance_required_together"}

    client = FakeClient([wants("indicator_pack"), answer()])

    outcome = await loop(client, catalog(spec("indicator_pack", needs_more_history))).run(
        turn_request()
    )

    assert outcome.answer_kind is AnswerKind.EDUCATION


@pytest.mark.asyncio
async def test_a_news_result_that_found_nothing_is_not_grounded_evidence():
    """`search_news` answers a successful call with `reason: None`."""

    async def empty_news(_context: ToolContext, _arguments: dict) -> dict:
        return {"untrusted_evidence": [], "reason": "no_cleared_news_in_window"}

    async def some_news(_context: ToolContext, _arguments: dict) -> dict:
        return {"untrusted_evidence": [{"title": "x"}], "reason": None}

    nothing = FakeClient([wants("search_news"), answer()])
    assert (
        await loop(nothing, catalog(spec("search_news", empty_news))).run(turn_request())
    ).answer_kind is AnswerKind.EDUCATION

    found = FakeClient([wants("search_news"), answer()])
    assert (
        await loop(found, catalog(spec("search_news", some_news))).run(turn_request())
    ).answer_kind is AnswerKind.ANALYSIS


# --- deadlines and the release path (#81, #82) ----------------------------


@pytest.mark.asyncio
async def test_a_call_that_never_answers_ends_the_turn_with_its_own_reason():
    class SilentClient(FakeClient):
        async def complete(self, request, spend=None):
            self.requests.append(request)
            await asyncio.sleep(5)
            return answer()

    outcome = await loop(SilentClient(), call_timeout_seconds=0.01).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "llm_call_timeout"


@pytest.mark.asyncio
async def test_a_tool_that_never_answers_ends_the_turn_with_its_own_reason():
    async def sleepy(_context: ToolContext, _arguments: dict) -> dict:
        await asyncio.sleep(5)
        return {"ok": True}

    client = FakeClient([wants("sleepy"), answer()])
    agent = loop(
        client,
        catalog(spec("sleepy", sleepy), spec("get_analysis", _ok)),
        tool_timeout_seconds=0.01,
    )

    outcome = await agent.run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "tool_timeout"
    assert len(client.requests) == 1  # no further round after the timeout


@pytest.mark.asyncio
async def test_a_slow_tool_beside_a_healthy_one_keeps_the_healthy_result():
    async def sleepy(_context: ToolContext, _arguments: dict) -> dict:
        await asyncio.sleep(5)
        return {"ok": True}

    client = FakeClient(
        [
            Completion(
                model=SESSION_MODEL,
                tool_calls=(
                    ToolCall(id="a", name="get_analysis", arguments={"symbol": "FPT"}, output_index=0),
                    ToolCall(id="b", name="sleepy", arguments={"symbol": "FPT"}, output_index=1),
                ),
                usage=Usage(input_tokens=10, output_tokens=5),
            ),
            answer(),
        ]
    )
    agent = loop(
        client,
        catalog(spec("get_analysis", _ok), spec("sleepy", sleepy)),
        tool_timeout_seconds=0.01,
    )

    outcome = await agent.run(turn_request())

    assert outcome.terminal_reason == "tool_timeout"
    assert [call.name for call in outcome.tool_calls] == ["get_analysis"]


@pytest.mark.asyncio
async def test_the_activity_line_marks_each_round_without_naming_a_tool():
    from src.agent.events import Activity, EventType, TurnPublisher

    published = TurnPublisher(uuid.uuid4())
    subscriber = published.subscribe()
    client = FakeClient([wants("get_analysis"), answer("Kết luận.")])

    await loop(client, publisher=published).run(turn_request())
    published.terminal(EventType.COMPLETED, status="complete", terminal_reason=None)

    seen = [event async for event in subscriber.events()]
    activities = [event for event in seen if event.type is EventType.ACTIVITY]
    assert [event.data["phase"] for event in activities] == [
        Activity.ANALYZING.value,
        Activity.READING_DATA.value,
        Activity.ANALYZING.value,
    ]
    # The phase is all it says: no tool name, symbol, argument or result.
    assert all(set(event.data) == {"phase"} for event in activities)


@pytest.mark.asyncio
async def test_a_news_round_reads_as_searching_rather_than_reading_data():
    from src.agent.events import Activity, EventType, TurnPublisher

    published = TurnPublisher(uuid.uuid4())
    subscriber = published.subscribe()
    client = FakeClient([wants("search_news"), answer("Kết luận.")])
    agent = loop(client, catalog(spec("search_news", _ok)), publisher=published)

    await agent.run(turn_request())
    published.terminal(EventType.COMPLETED, status="complete", terminal_reason=None)

    seen = [event async for event in subscriber.events()]
    assert Activity.SEARCHING.value in [
        event.data["phase"] for event in seen if event.type is EventType.ACTIVITY
    ]


@pytest.mark.asyncio
async def test_a_recommendation_the_gate_cannot_prove_leaves_an_answer_behind():
    """The Turn says why it could not recommend, instead of going blank.

    Before this, a recommendation failing an availability condition ended the
    Turn with nothing released at all when it was the first block — the reader
    got an empty answer for a question the system had partly answered. The
    recommendation itself is still never displayed.
    """
    unprovable = "[rec:FPT@2026-08-14] FPT đáng mua quanh vùng hiện tại."
    client = FakeClient(
        [wants("get_analysis"), answer(unprovable), answer(unprovable)]
    )

    outcome = await loop(client).run(turn_request())

    displayed = "\n\n".join(block.text for block in outcome.blocks)
    assert displayed.strip()
    assert "khuyến nghị" in displayed
    # The unprovable text never reaches the reader, and no block claims to be a
    # recommendation.
    assert "đáng mua" not in displayed
    assert all(block.kind is not BlockKind.RECOMMENDATION for block in outcome.blocks)
    # The record still says a recommendation was blocked, and by which condition.
    assert outcome.degraded_recommendation_code == "missing_reference_price"
    assert gate_outcomes(outcome).recommendation == "blocked"
    assert gate_outcomes(outcome).failure_code == "missing_reference_price"


# --- the Gate's one rewrite ------------------------------------------------


UNPROVABLE = "RSI đang ở 61,2 [ev:nope#registered_fields.indicator_pack.rsi_14.value]"


@pytest.mark.asyncio
async def test_a_blocked_block_earns_one_rewrite_and_the_rewrite_is_released():
    """A misplaced reference costs a round, not the whole answer.

    The first answer references a call this Turn never made, which is a
    non-degradable condition and used to end the Turn with nothing on screen.
    The model is told the condition once and rewrites; the rewrite is what the
    reader gets, and the withheld attempt is not part of it.
    """
    client = FakeClient(
        [wants("get_analysis"), answer(UNPROVABLE), answer("Kết luận không có số.")]
    )

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.terminal_reason is None
    assert [block.text for block in outcome.blocks] == ["Kết luận không có số."]
    # Three calls: the lookup, the blocked answer, and the rewrite it earned.
    assert len(client.requests) == 3
    note = client.requests[-1].messages[-1]
    assert note.role is Role.SYSTEM
    assert "withheld" in note.content
    # The instruction names the condition and never the figure behind it.
    assert "61,2" not in note.content
    assert "61.2" not in note.content


@pytest.mark.asyncio
async def test_the_nudge_is_spent_on_its_call_and_never_becomes_transcript():
    """The note funds one call and leaves no trace behind it.

    A nudge in the durable transcript would be replayed into every later Turn of
    the thread, and the model would read an instruction about an answer it can no
    longer see. It stays out by construction rather than by being filtered: the
    note is appended to the in-flight message list, and what is stored is blocks,
    widgets, traces and the activity trail.
    """
    client = FakeClient(
        [wants("get_analysis"), answer(UNPROVABLE), answer("Kết luận không có số.")]
    )

    outcome = await loop(client).run(turn_request())

    carried = client.requests[-1].messages[-1]
    assert carried.role is Role.SYSTEM
    assert "withheld" in carried.content
    # Nothing of it reaches what is kept: not the blocks, not the checkpoint.
    stored = draft_content(
        TurnDraft(
            text=outcome.text,
            rounds_used=outcome.rounds_used,
            tool_calls=outcome.tool_calls,
            blocks=outcome.blocks,
            widgets=outcome.widgets,
            progress=outcome.progress,
        )
    )
    assert "withheld" not in json.dumps(stored, ensure_ascii=False)
    assert all("withheld" not in block.text for block in outcome.blocks)


@pytest.mark.asyncio
async def test_a_buy_call_without_a_zone_or_a_reference_price_never_reaches_the_screen():
    """The condition the inversion was not allowed to relax.

    Fail-open lets a Turn answer around a paragraph it could not prove. It does
    not let a priced buy call through: a recommendation missing its price zone or
    its reference price is dropped exactly as before, and what the reader gets
    instead is the backend saying which evidence was not there.
    """
    for draft in (
        "[rec:FPT@2026-08-14] Nên mua FPT quanh vùng hiện tại.",
        "[rec:FPT@2026-08-14] Bán FPT ngay bây giờ.",
    ):
        client = FakeClient([wants("get_analysis"), answer(draft), answer(draft)])

        outcome = await loop(client).run(turn_request())

        displayed = "\n\n".join(block.text for block in outcome.blocks)
        assert all(
            block.kind is not BlockKind.RECOMMENDATION for block in outcome.blocks
        )
        assert "Nên mua" not in displayed
        assert "Bán FPT" not in displayed
        # And the record still says a recommendation was refused, which is the
        # dimension the ops query watches.
        assert gate_outcomes(outcome).recommendation == "blocked"
        assert outcome.degraded_codes


# A recommendation about a symbol no tool in this Turn served: an integrity
# failure, and one of the only four left. Figure-free on purpose, so it reaches
# the Universe check rather than failing an attribution rule on the way.
INTEGRITY_DRAFT = "[rec:XYZ@2026-08-14] Nên xem xét thêm."



@pytest.mark.asyncio
async def test_a_form_failure_survives_its_nudge_as_a_downgrade_not_a_dead_turn():
    """The inverted default, measured at the loop.

    `unknown_tool_call` is a marker naming a call this Turn never made — the
    model's punctuation, not its arithmetic. It used to end the Turn, and Turns
    ending this way were 58% of all of them. Now the model is nudged once, and
    if the rewrite repeats the mistake the block is replaced by the backend's
    sentence and the Turn completes.
    """
    client = FakeClient(
        [wants("get_analysis"), answer(UNPROVABLE), answer(UNPROVABLE), answer("Muộn.")]
    )

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.terminal_reason is None
    assert outcome.degraded_codes == ("unknown_tool_call",)
    # The nudge is spent once and only once: the lookup, the first answer, and
    # the rewrite. A fourth answer is never asked for.
    assert len(client.requests) == 3
    # The unprovable figure never reaches the reader, and what replaces it says
    # why in the reader's own language.
    displayed = "\n\n".join(block.text for block in outcome.blocks)
    assert "61,2" not in displayed
    assert "chưa dẫn được về dữ liệu đã đăng ký" in displayed


@pytest.mark.asyncio
async def test_an_integrity_failure_still_ends_the_turn_after_its_one_rewrite():
    """The four conditions the inversion did not touch, and must not.

    A block about a symbol no tool served is a confident statement about
    something this Turn has no evidence for — the class `docs/adr/0018` keeps as
    a hard failure in every block. It earns the same single rewrite, and when
    the rewrite repeats it the Turn ends rather than downgrading.
    """
    client = FakeClient(
        [
            wants("get_analysis"),
            answer(INTEGRITY_DRAFT),
            answer(INTEGRITY_DRAFT),
            answer("Muộn."),
        ]
    )

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "grounding_failed"
    assert outcome.grounding_failure_code == "symbol_not_in_universe"
    assert outcome.degraded_codes == ()
    assert len(client.requests) == 3


@pytest.mark.asyncio
async def test_a_turn_the_gate_emptied_says_so_rather_than_showing_nothing():
    """The floor under a blocked Turn is a sentence, not a blank answer."""
    from src.agent.grounding import BLOCKED_TURN_NOTICE

    client = FakeClient(
        [wants("get_analysis"), answer(INTEGRITY_DRAFT), answer(INTEGRITY_DRAFT)]
    )

    outcome = await loop(client).run(turn_request())

    assert [block.text for block in outcome.blocks] == [BLOCKED_TURN_NOTICE]
    assert outcome.blocks[0].citations == ()
    assert outcome.blocks[0].kind is BlockKind.PROSE
    # Nothing of the refused answer survives in it.
    assert "XYZ" not in outcome.blocks[0].text


@pytest.mark.asyncio
async def test_a_partly_proven_answer_keeps_its_proven_blocks_and_adds_no_notice():
    """The notice is only for a Turn the Gate emptied."""
    from src.agent.grounding import BLOCKED_TURN_NOTICE

    text = f"Phiên hôm nay đi ngang.\n\n{INTEGRITY_DRAFT}"
    client = FakeClient([wants("get_analysis"), answer(text), answer(text)])

    outcome = await loop(client).run(turn_request())

    assert outcome.terminal_reason == "grounding_failed"
    assert [block.text for block in outcome.blocks] == ["Phiên hôm nay đi ngang."]
    assert BLOCKED_TURN_NOTICE not in [block.text for block in outcome.blocks]


@pytest.mark.asyncio
async def test_a_downgraded_block_is_never_nudged_twice():
    """The ceiling holds whether the failure downgrades or refuses.

    The nudge costs a whole model call, and a Turn that spends two of them on a
    model that cannot fix its own reference has spent them to arrive at the same
    sentence it would have written after one.
    """
    client = FakeClient(
        [
            wants("get_analysis"),
            answer(UNPROVABLE),
            answer(UNPROVABLE),
            answer(UNPROVABLE),
            answer("Muộn."),
        ]
    )

    outcome = await loop(client).run(turn_request())

    assert len(client.requests) == 3
    assert outcome.status is TurnStatus.COMPLETE


@pytest.mark.asyncio
async def test_a_nudge_that_makes_the_answer_worse_keeps_the_earlier_draft(caplog):
    """The regression the downgrade nudge introduced, and its floor.

    Attempt 1 fails only degradable conditions, so its answer was releasable.
    The nudge then presses the model to attach every figure to a reference, and a
    reference attached to the wrong call is `figure_mismatch` — integrity, which
    ends the Turn. Without a floor the reader loses an answer they would have
    been given one call earlier, for a reason that had nothing to do with them.

    Driven here through `symbol_not_in_universe` rather than `figure_mismatch`,
    because it is the integrity condition this harness can reach: the test
    catalog serves no registered field for a figure to disagree with. The path
    under test is the same one — any integrity failure on the rewrite.
    """
    client = FakeClient(
        [wants("get_analysis"), answer(UNPROVABLE), answer(INTEGRITY_DRAFT)]
    )

    with caplog.at_level("INFO"):
        outcome = await loop(client).run(turn_request())

    # The fallback ran, rather than the rewrite merely downgrading again.
    assert any(
        "kept the draft from before its nudge" in record.message
        for record in caplog.records
    )
    assert any("symbol_not_in_universe" in record.message for record in caplog.records)
    # The Turn survives on the pre-nudge draft rather than blanking.
    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.terminal_reason is None
    assert outcome.blocks
    displayed = "\n\n".join(block.text for block in outcome.blocks)
    assert "chưa dẫn được về dữ liệu đã đăng ký" in displayed
    # And nothing of the rewrite the Gate refused reaches the screen.
    assert "XYZ" not in displayed


@pytest.mark.asyncio
async def test_an_integrity_failure_on_the_first_attempt_has_nothing_to_fall_back_to():
    """The floor is only under a draft that was already releasable.

    A Turn refused on its first attempt never had a publishable answer, so there
    is nothing to keep and the Gate still ends it.
    """
    client = FakeClient(
        [wants("get_analysis"), answer(INTEGRITY_DRAFT), answer(INTEGRITY_DRAFT)]
    )

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "grounding_failed"


@pytest.mark.asyncio
async def test_a_downgraded_prose_block_is_not_recorded_as_a_blocked_recommendation():
    """The dimension has to mean what its name says.

    Since the default inverted, twenty conditions downgrade on *any* block. Read
    off the code list, a market summary with one misplaced bracket reports a
    blocked recommendation it never attempted — and this is the dimension Phase
    8's baseline reads to decide whether the inversion let false figures through.
    """
    client = FakeClient([wants("get_analysis"), answer(UNPROVABLE), answer(UNPROVABLE)])

    outcome = await loop(client).run(turn_request())

    assert outcome.degraded_codes  # something was downgraded
    assert outcome.degraded_recommendations == 0
    outcomes = gate_outcomes(outcome)
    assert outcomes.recommendation == "not_applicable"
    # The condition is still on the record, in the field that carries all of them.
    assert outcomes.downgrades == outcome.degraded_codes


@pytest.mark.asyncio
async def test_one_condition_failing_three_blocks_says_it_once():
    """Three copies of one sentence read as a stutter, not as three facts."""
    text = "\n\n".join([UNPROVABLE] * 3)
    client = FakeClient([wants("get_analysis"), answer(text), answer(text)])

    outcome = await loop(client).run(turn_request())

    notices = [block.text for block in outcome.blocks]
    assert len(notices) == len(set(notices))
    # Every occurrence is still counted, because the record is what Phase 8 reads.
    assert len(outcome.degraded_codes) == 3


@pytest.mark.asyncio
async def test_every_downgrade_in_one_answer_is_recorded():
    """One field per Turn would report the last condition as the only one."""
    text = f"{UNPROVABLE}\n\nSố khác 44,5 [ev:nope#registered_fields.a.b.value]"
    client = FakeClient([wants("get_analysis"), answer(text), answer(text)])

    outcome = await loop(client).run(turn_request())

    assert len(outcome.degraded_codes) == 2
    assert gate_outcomes(outcome).downgrades == outcome.degraded_codes

# --- the guardrail ladder and the spillover ------------------------------


@pytest.mark.asyncio
async def test_a_repeated_call_is_warned_before_it_is_refused():
    # Round one asks; round two asks the identical question again. The tool
    # answered both times, so ``ToolAttempts`` sees nothing — this is the case
    # the ladder exists for (``guardrails.py``).
    client = FakeClient(
        [
            wants("get_analysis", prefix="a"),
            wants("get_analysis", prefix="b"),
            answer("Kết luận cuối cùng."),
        ]
    )

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.COMPLETE
    # Warned, not blocked: the second round still ran.
    assert outcome.rounds_used == 2
    notes = [
        message.content
        for request in client.requests
        for message in request.messages
        if message.role is Role.SYSTEM and message.content
    ]
    assert any("already called get_analysis" in note for note in notes)


@pytest.mark.asyncio
async def test_the_same_call_twice_in_one_round_is_answered_once():
    duplicate = Completion(
        model=SESSION_MODEL,
        tool_calls=tuple(
            ToolCall(
                id=f"call_{index}",
                name="get_analysis",
                arguments={"symbol": "FPT"},
                output_index=index,
            )
            for index in range(3)
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )
    dispatched: list[str] = []

    async def counted(_context: ToolContext, arguments: dict) -> dict:
        dispatched.append(str(arguments.get("symbol")))
        return {"symbol": arguments.get("symbol"), "close": 95.4}

    client = FakeClient([duplicate, answer()])

    outcome = await loop(client, catalog(spec("get_analysis", counted))).run(
        turn_request()
    )

    # One dispatch, three results: the copies are answered with the reason
    # rather than dropped, because half a tool exchange is a transcript the
    # model has to guess at.
    assert dispatched == ["FPT"]
    assert len(outcome.tool_calls) == 3
    assert outcome.status is TurnStatus.COMPLETE
    # A duplicate inside one round cannot halt the Turn: every call in it was
    # decided before any guidance existed.
    assert outcome.rounds_used == 1


@pytest.mark.asyncio
async def test_a_turn_that_keeps_repeating_stops_paying_for_the_repetition():
    dispatched: list[str] = []

    async def counted(_context: ToolContext, arguments: dict) -> dict:
        dispatched.append(str(arguments.get("symbol")))
        return {"symbol": arguments.get("symbol"), "close": 95.4}

    client = FakeClient(
        [
            wants("get_analysis", prefix="a"),
            wants("get_analysis", prefix="b"),
            wants("get_analysis", prefix="c"),
            wants("get_analysis", prefix="d"),
            answer("Kết luận từ bằng chứng đã có."),
        ]
    )

    outcome = await loop(client, catalog(spec("get_analysis", counted))).run(
        turn_request()
    )

    # Asked four times, dispatched twice: the third is refused before dispatch
    # and the fourth halts the tool loop. The Turn still answers — the halt ends
    # the *tool* loop, not the Turn, so the reader keeps the evidence that was
    # gathered before the model started going round in circles.
    assert dispatched == ["FPT", "FPT"]
    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.text == "Kết luận từ bằng chứng đã có."
    assert client.requests[-1].tool_choice == "none"


@pytest.mark.asyncio
async def test_a_halted_round_still_dispatches_the_calls_beside_it():
    dispatched: list[str] = []

    async def counted(_context: ToolContext, arguments: dict) -> dict:
        dispatched.append(f"{arguments.get('symbol')}")
        return {"symbol": arguments.get("symbol"), "close": 95.4}

    # Three rounds of the same call, then a fourth round carrying the repetition
    # *and* a question nobody has asked yet.
    mixed = Completion(
        model=SESSION_MODEL,
        tool_calls=(
            ToolCall(id="d_0", name="get_analysis", arguments={"symbol": "FPT"}, output_index=0),
            ToolCall(id="d_1", name="get_analysis", arguments={"symbol": "VNM"}, output_index=1),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )
    client = FakeClient(
        [
            wants("get_analysis", prefix="a"),
            wants("get_analysis", prefix="b"),
            wants("get_analysis", prefix="c"),
            mixed,
            answer("Kết luận."),
        ]
    )

    outcome = await loop(client, catalog(spec("get_analysis", counted))).run(
        turn_request()
    )

    # The new question ran; the repetition did not. A halt that discarded its
    # round would have thrown away evidence nobody had asked for twice.
    assert dispatched == ["FPT", "FPT", "VNM"]
    assert outcome.status is TurnStatus.COMPLETE


@pytest.mark.asyncio
async def test_a_result_too_large_for_its_tool_reaches_the_model_as_a_preview():
    async def bulky(_context: ToolContext, arguments: dict) -> dict:
        return {
            "symbol": arguments.get("symbol"),
            "as_of": "2026-08-14",
            "rows": [{"date": f"2026-08-{day:02d}", "close": 90.0 + day} for day in range(1, 29)],
        }

    recorded: list[tuple[int, dict]] = []

    async def record(request_message_id: int, spilled) -> None:
        recorded.append((request_message_id, dict(spilled)))

    client = FakeClient([wants("bulky"), answer()])
    tools = ToolCatalog(
        (
            ToolSpec(
                name="bulky",
                description="Return a long series.",
                parameters={
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "additionalProperties": False,
                },
                callable=bulky,
                # Small enough that the result above is over it, which is what
                # makes this a test of rung two rather than of the shipped
                # default.
                result_budget_bytes=400,
            ),
        ),
        trace_writer=lambda _trace: None,
    )

    outcome = await loop(client, tools, spill_recorder=record).run(turn_request())

    (call,) = outcome.tool_calls
    assert call.result is not None
    # The envelope survives, the bulk does not, and the reference says how much
    # was left out — the model can see the shape of what it is missing.
    assert call.result["symbol"] == "FPT"
    assert len(call.result["rows"]) < 28
    reference = call.result["spilled_ref"]
    assert reference["full_bytes"] > 400
    assert reference["truncated"][0]["key"] == "rows"
    # And the spill is written down, so a threshold can be tuned against
    # measured spills rather than guessed at.
    assert recorded == [(42, {"call_0": reference["full_bytes"]})]


@pytest.mark.asyncio
async def test_a_result_inside_its_budget_is_never_touched():
    client = FakeClient([wants("get_analysis"), answer()])

    outcome = await loop(client).run(turn_request())

    (call,) = outcome.tool_calls
    assert call.result == {"symbol": "FPT", "close": 95.4}
