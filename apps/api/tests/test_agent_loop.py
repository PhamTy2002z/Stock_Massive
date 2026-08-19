"""The agent loop: rounds, parallel dispatch, and the error taxonomy (#80)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date
from types import MappingProxyType

import pytest

from src.agent.context import ContextBudget
from src.core.llm.budget import TURN_OUTPUT_TOKENS
from src.agent.loop import (
    ANSWER_TRUNCATED,
    DEFAULT_MAX_OUTPUT_TOKENS,
    EXTERNAL_TOOL_EXHAUSTED_MESSAGE,
    MAX_EXTERNAL_TOOL_CALLS,
    MAX_TOOL_ROUNDS,
    ROUNDS_EXHAUSTED_NOTE,
    SESSION_CONCURRENCY,
    AgentLoop,
    SessionCapacityExceeded,
    SessionSlots,
    ToolCallIdMismatch,
    TurnRequest,
    TurnStatus,
    admit_round,
    assert_distinct_ids,
    pair_results,
)
from src.agent.grounding import BlockKind
from src.agent.prompt import AnswerKind, MarketState, RuntimeContext
from src.agent.turns import gate_outcomes
from src.agent.tools.catalog import ToolCatalog, ToolContext, ToolDataAccess, ToolSpec
from src.alpha.refusals import AlphaRefusal
from src.core.llm import (
    AuthUnavailable,
    BudgetLane,
    BudgetRefusal,
    Completion,
    GatewayTimeout,
    LLMError,
    MalformedArguments,
    ModelRefusal,
    OwnerType,
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


def answer(text: str = "Kết luận.") -> Completion:
    return Completion(model=SESSION_MODEL, text=text, usage=Usage(input_tokens=10, output_tokens=5))


def wants(*names: str, prefix: str = "call") -> Completion:
    return Completion(
        model=SESSION_MODEL,
        tool_calls=tuple(
            ToolCall(id=f"{prefix}_{index}", name=name, arguments={"symbol": "FPT"}, output_index=index)
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
    client = FakeClient([wants("get_analysis", prefix=f"r{n}") for n in range(20)])

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
    client = FakeClient([wants("get_analysis", prefix=f"r{n}") for n in range(20)])
    agent = AgentLoop(
        client=client,
        catalog=catalog(),
        config=config(),
        budget=ContextBudget(max_tokens=6_000),
    )

    await agent.run(turn_request())

    for spend in client.spends:
        assert spend.input_tokens <= 6_000


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
    names = ("external_lookup",) * (MAX_EXTERNAL_TOOL_CALLS + 1)
    client = FakeClient([wants(*names), answer()])

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
async def test_any_other_route_failure_ends_the_turn_incomplete():
    client = FakeClient([LLMError("the route refused the request (400)")])

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "route_error"


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
    client = FakeClient([wants("get_analysis"), answer(unprovable)])

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
async def test_the_rewrite_is_offered_once_and_the_second_failure_ends_the_turn():
    client = FakeClient(
        [wants("get_analysis"), answer(UNPROVABLE), answer(UNPROVABLE), answer("Muộn.")]
    )

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == "grounding_failed"
    assert outcome.grounding_failure_code == "unknown_tool_call"
    # The third answer is never asked for: the rewrite was the last chance.
    assert len(client.requests) == 3


@pytest.mark.asyncio
async def test_a_turn_the_gate_emptied_says_so_rather_than_showing_nothing():
    """The floor under a blocked Turn is a sentence, not a blank answer."""
    from src.agent.grounding import BLOCKED_TURN_NOTICE

    client = FakeClient([wants("get_analysis"), answer(UNPROVABLE), answer(UNPROVABLE)])

    outcome = await loop(client).run(turn_request())

    assert [block.text for block in outcome.blocks] == [BLOCKED_TURN_NOTICE]
    assert outcome.blocks[0].citations == ()
    assert outcome.blocks[0].kind is BlockKind.PROSE
    # Nothing of the withheld answer survives in it.
    assert "61,2" not in outcome.blocks[0].text


@pytest.mark.asyncio
async def test_a_partly_proven_answer_keeps_its_proven_blocks_and_adds_no_notice():
    """The notice is only for a Turn the Gate emptied."""
    from src.agent.grounding import BLOCKED_TURN_NOTICE

    text = f"Phiên hôm nay đi ngang.\n\n{UNPROVABLE}"
    client = FakeClient([wants("get_analysis"), answer(text), answer(text)])

    outcome = await loop(client).run(turn_request())

    assert outcome.terminal_reason == "grounding_failed"
    assert [block.text for block in outcome.blocks] == ["Phiên hôm nay đi ngang."]
    assert BLOCKED_TURN_NOTICE not in [block.text for block in outcome.blocks]
