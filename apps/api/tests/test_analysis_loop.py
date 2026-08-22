"""The loop that lets an Analysis ask for evidence it was not handed.

What is under test is the control flow and everything it must not break —

*A loop that asks for nothing says what the one shot said.* Same seed, same six
rules, same payload. If that is not true then every Analysis of every symbol that
needed nothing extra has been changed for nothing.

*A refusal is a fork, not a wall.* Seeded with a refused figure, a model that
fetches a usable substitute gets an Analysis that carries both — the refusal as
honesty evidence, the substitute as something citable — and can cite the one it
fetched.

*The backend still owns every number.* The tool phase only ever adds figures. It
cannot replace one, edit one, or put a model-supplied number where a figure goes,
and the citation rules apply to a fetched figure exactly as to a seeded one.

*Nothing is published empty.* Rounds spent, a route that will not answer, a
fragment invalid twice — each fails under a code the taxonomy already has, and
none of them writes an Analysis.

*Every call is on the record.* One trace row per call, ``seq`` in the order the
model issued them, ``round_index`` climbing — because the reproducibility this
lane gave up is only bought back if the path is readable.

The client is a fake. A real route would make these tests measure a model.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from src.agent import registry
from src.agent.tools import signals as signal_tools
from src.alpha.analysis_loop import (
    ANALYSIS_THRESHOLDS,
    LOOP_CONTRACT,
    LOOP_PROMPT_VERSION,
    LOOP_SYSTEM_PROMPT,
    MAX_TOOL_ROUNDS,
    ROUND_OUTPUT_TOKENS,
    generate_fragment_in_loop,
)
from src.alpha.envelope import Health
from src.alpha.field_profile import AXIS_ORDER, Axis
from src.alpha.generation import (
    MAX_OUTPUT_TOKENS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    Verdict,
)
from src.alpha.producer import FAILURE_CODES, ProductionFailure
from src.core.llm import (
    AuthUnavailable,
    BudgetLane,
    BudgetRefusal,
    Completion,
    GatewayTimeout,
    OwnerType,
    Role,
    ToolCall,
    Usage,
)
from src.core.llm.admission import (
    ANALYSIS_COST_MICRO_USD,
    ANALYSIS_INPUT_PER_CALL,
    ANALYSIS_OUTPUT_PER_CALL,
)
from src.core.llm.budget import (
    ANALYSIS_COST_CEILING_USD,
    ANALYSIS_INPUT_TOKENS,
    ANALYSIS_OUTPUT_TOKENS,
)

from .test_generation import (
    MODEL,
    REFUSED,
    RUN_ID,
    TRADING_DAY,
    USABLE,
    a_fragment,
    an_envelope,
)

# A registered field the profile never names, so it can only arrive through the
# loop. Its axis decides which section it lands in.
SUBSTITUTE = "risk_adjusted.sharpe_annualized"


def a_figure_payload(field_id: str = SUBSTITUTE, *, health: str = "ok") -> dict:
    """What ``get_field`` answers with, in the wire shape the envelope defines."""
    return {
        "fieldId": field_id,
        "label": field_id,
        "value": None if health == "refused" else 1.4,
        "unit": "ratio",
        "kind": "estimator",
        "source": "computed",
        "interpretation": "Return per unit of realized volatility.",
        "health": health,
        "reasonCode": None if health == "ok" else "insufficient_history",
        "reason": None if health == "ok" else "The store holds fewer sessions.",
        "asOf": None if health == "refused" else TRADING_DAY.isoformat(),
        "sessionsUsed": None if health == "refused" else 260,
        "windowDays": 250,
        "extras": {"standard_error": 0.2},
    }


def wants(name: str, call_id: str = "t1", **arguments) -> Completion:
    return Completion(
        model=MODEL,
        tool_calls=(ToolCall(id=call_id, name=name, arguments=arguments),),
        usage=Usage(input_tokens=5_000, output_tokens=60),
    )


def wants_many(*calls: tuple[str, str, dict]) -> Completion:
    return Completion(
        model=MODEL,
        tool_calls=tuple(
            ToolCall(id=call_id, name=name, arguments=arguments)
            for call_id, name, arguments in calls
        ),
        usage=Usage(input_tokens=5_000, output_tokens=90),
    )


def says(payload) -> Completion:
    """A call that produced no tool calls — the model is done asking."""
    return Completion(
        model=MODEL,
        text=payload if isinstance(payload, str) else json.dumps(payload),
        usage=Usage(input_tokens=5_000, output_tokens=400),
    )


class FakeClient:
    """Every answer scripted, every request and reservation kept.

    ``rounds`` and ``final`` are the open-ended form, used once the positional
    script runs out: a tool round gets ``rounds`` and the fragment call gets
    ``final``, told apart by whether a response format was asked for. It exists
    so a test about the round ceiling does not have to know how many rounds the
    guardrail ladder will actually allow — pinning a script's length to a
    threshold is how a test starts asserting its own arithmetic.
    """

    def __init__(self, *answers, rounds=None, final=None) -> None:
        self._answers = list(answers)
        self._rounds = rounds
        self._final = final
        self.requests: list = []
        self.spends: list = []

    async def complete(self, request, spend=None):
        self.requests.append(request)
        self.spends.append(spend)
        answer = self._next(request)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def _next(self, request):
        if self._answers:
            return self._answers.pop(0)
        asking_for_the_fragment = request.response_format is not None
        chosen = self._final if asking_for_the_fragment else self._rounds
        if chosen is None:
            raise AssertionError("the loop asked for more calls than scripted")
        return chosen

    @property
    def calls(self) -> int:
        return len(self.requests)


class FakeTools:
    """The two store tools, answering from a script instead of from Postgres.

    Registered under the real names and the real toolset, so what the loop offers
    the model is the real schema list and what it dispatches to is the real
    registry — only the store underneath is scripted.
    """

    def __init__(self, **answers) -> None:
        self.answers = answers
        self.seen: list[tuple[str, dict]] = []

    def entries(self) -> tuple[registry.ToolEntry, ...]:
        real = signal_tools.SignalTools().entries()
        return tuple(
            registry.ToolEntry(
                name=entry.name,
                toolset=entry.toolset,
                schema=entry.schema,
                description=entry.description,
                handler=self._handler(entry.name),
                is_async=True,
                max_result_size_chars=entry.max_result_size_chars,
            )
            for entry in real
        )

    def _handler(self, name: str):
        def handle(_context, arguments):
            self.seen.append((name, dict(arguments)))
            answer = self.answers.get(name)
            if isinstance(answer, Exception):
                raise answer
            if callable(answer):
                return answer(dict(arguments))
            return answer

        return handle


@pytest.fixture(autouse=True)
def _isolated_tools():
    from .agent_tool_world import isolated_registry

    with isolated_registry():
        yield


def install(tools: FakeTools) -> FakeTools:
    from src.agent import definitions

    for entry in tools.entries():
        registry.register(entry)
    definitions.clear_cache()
    return tools


class Recorder:
    """A stand-in for the trace store that keeps the rows instead of writing them.

    Every test runs with one, because the trace is not optional in production and
    a test that silently skipped it would not notice the day writing one started
    failing for a real reason.
    """

    def __init__(self) -> None:
        self.rows: list = []
        self.committed = False

    def __call__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add_all(self, rows) -> None:
        self.rows.extend(rows)

    def commit(self) -> None:
        self.committed = True


async def run_loop(client, envelope=None, **overrides):
    """The loop, with a recording trace store unless a test supplies its own."""
    overrides.setdefault("session_opener", Recorder())
    return await generate_fragment_in_loop(
        client,
        envelope or an_envelope(),
        model=MODEL,
        run_id=RUN_ID,
        clock=lambda: datetime(2026, 8, 12, tzinfo=timezone.utc),
        **overrides,
    )


class TestTheContract:
    def test_it_adds_to_the_one_shot_contract_rather_than_replacing_it(self):
        assert LOOP_SYSTEM_PROMPT.startswith(SYSTEM_PROMPT)
        assert LOOP_SYSTEM_PROMPT.endswith(LOOP_CONTRACT)

    def test_it_carries_its_own_version_because_it_is_a_different_contract(self):
        assert LOOP_PROMPT_VERSION == "v2"
        assert LOOP_PROMPT_VERSION != PROMPT_VERSION

    def test_it_is_a_constant_rather_than_a_template(self):
        assert "{" not in LOOP_CONTRACT
        assert "%s" not in LOOP_CONTRACT

    def test_it_names_the_substitution_the_loop_exists_for(self):
        assert "list_fields" in LOOP_CONTRACT
        assert "get_field" in LOOP_CONTRACT
        assert "minSessions" in LOOP_CONTRACT
        # And the rule that survives from the one shot unchanged.
        assert "refused" in LOOP_CONTRACT

    def test_it_tells_the_model_it_cannot_choose_the_symbol_or_the_day(self):
        assert "do not name a symbol" in LOOP_CONTRACT.lower()


class TestTheArithmetic:
    def test_the_rounds_and_the_final_call_fit_one_analysis_s_output(self):
        assert (
            MAX_TOOL_ROUNDS * ROUND_OUTPUT_TOKENS + MAX_OUTPUT_TOKENS
            <= ANALYSIS_OUTPUT_TOKENS
        )

    def test_the_two_places_the_cost_ceiling_is_written_agree(self):
        assert ANALYSIS_COST_MICRO_USD == round(ANALYSIS_COST_CEILING_USD * 1_000_000)

    def test_no_single_call_can_be_refused_for_a_bound_the_loop_needs(self):
        assert ANALYSIS_INPUT_PER_CALL >= ANALYSIS_INPUT_TOKENS
        assert ANALYSIS_OUTPUT_PER_CALL >= MAX_OUTPUT_TOKENS * 2

    def test_every_guardrail_rung_is_reachable_inside_the_round_budget(self):
        """The defect the chat lane carries at this base: a warn-only ladder."""
        assert ANALYSIS_THRESHOLDS.exact_failure_block_after <= MAX_TOOL_ROUNDS
        assert ANALYSIS_THRESHOLDS.same_tool_failure_halt_after <= MAX_TOOL_ROUNDS
        assert (
            ANALYSIS_THRESHOLDS.exact_failure_warn_after
            < ANALYSIS_THRESHOLDS.exact_failure_block_after
        )


class TestWhenNothingIsAsked:
    @pytest.mark.asyncio
    async def test_the_fragment_is_the_one_the_one_shot_lane_would_have_produced(self):
        install(FakeTools())
        client = FakeClient(says("no tools please"), says(a_fragment()))

        outcome = await run_loop(client)

        assert outcome.fragment.verdict is Verdict.HOLD
        assert outcome.rounds_used == 0
        assert outcome.calls == 0
        assert outcome.fetched_field_ids == ()

    @pytest.mark.asyncio
    async def test_the_envelope_comes_back_untouched(self):
        install(FakeTools())
        seed = an_envelope()
        client = FakeClient(says(""), says(a_fragment()))

        outcome = await run_loop(client, seed)

        assert outcome.envelope is seed
        assert outcome.envelope.as_wire() == seed.as_wire()
        assert outcome.envelope.fingerprint() == seed.fingerprint()

    @pytest.mark.asyncio
    async def test_the_last_call_offers_no_tools_and_asks_for_the_schema(self):
        install(FakeTools())
        client = FakeClient(says(""), says(a_fragment()))

        await run_loop(client)

        last = client.requests[-1]
        assert last.tools == ()
        assert last.tool_choice == "none"
        assert last.response_format is not None
        assert last.response_format.strict is True
        assert last.temperature == 0.0
        assert last.stream is False


class TestWhenTheStoreIsAsked:
    @pytest.mark.asyncio
    async def test_the_model_is_offered_exactly_the_two_store_tools(self):
        install(FakeTools())
        client = FakeClient(says(""), says(a_fragment()))

        await run_loop(client)

        offered = {schema.name for schema in client.requests[0].tools}
        assert offered == {"list_fields", "get_field"}
        assert client.requests[0].tool_choice == "auto"

    @pytest.mark.asyncio
    async def test_a_fetched_figure_lands_in_the_envelope_on_its_own_axis(self):
        install(FakeTools(get_field=a_figure_payload()))
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE),
            says(""),
            says(a_fragment(citedFieldIds=[USABLE, SUBSTITUTE])),
        )

        outcome = await run_loop(client)

        assert SUBSTITUTE in outcome.envelope.field_ids
        assert SUBSTITUTE in outcome.envelope.citable_field_ids
        assert outcome.fetched_field_ids == (SUBSTITUTE,)
        landed = next(
            section
            for section in outcome.envelope.sections
            if SUBSTITUTE in {figure.field_id for figure in section.figures}
        )
        assert landed.axis is signal_tools.axis_of(SUBSTITUTE)

    @pytest.mark.asyncio
    async def test_the_refusal_it_was_seeded_with_is_still_there(self):
        """A substitute answers beside a refusal; it does not delete it."""
        install(FakeTools(get_field=a_figure_payload()))
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE),
            says(""),
            says(a_fragment(citedFieldIds=[SUBSTITUTE])),
        )

        outcome = await run_loop(client)

        refused = outcome.envelope.figure(REFUSED)
        assert refused is not None
        assert refused.health is Health.REFUSED
        assert REFUSED not in outcome.envelope.citable_field_ids

    @pytest.mark.asyncio
    async def test_a_fetched_figure_may_be_cited_and_a_refused_one_may_not(self):
        install(FakeTools(get_field=a_figure_payload(health="refused")))
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE),
            says(""),
            says(a_fragment(citedFieldIds=[SUBSTITUTE])),
            says(a_fragment(citedFieldIds=[USABLE])),
        )

        outcome = await run_loop(client)

        # The first fragment cited the figure it had just fetched refused; the
        # sanctioned regeneration produced one that cites a usable figure.
        assert outcome.fragment.cited_field_ids == (USABLE,)
        assert client.calls == 4

    @pytest.mark.asyncio
    async def test_the_sections_keep_their_fixed_order_after_the_loop_widens_them(self):
        install(FakeTools(get_field=a_figure_payload()))
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE),
            says(""),
            says(a_fragment()),
        )

        outcome = await run_loop(client)

        assert tuple(s.axis for s in outcome.envelope.sections) == AXIS_ORDER

    @pytest.mark.asyncio
    async def test_the_results_reach_the_model_as_tool_messages_in_order(self):
        install(
            FakeTools(
                get_field=a_figure_payload(),
                list_fields={"count": 30, "fields": []},
            )
        )
        client = FakeClient(
            wants_many(
                ("a", "list_fields", {}),
                ("b", "get_field", {"field_id": SUBSTITUTE}),
            ),
            says(""),
            says(a_fragment()),
        )

        await run_loop(client)

        final = client.requests[-1].messages
        tool_messages = [m for m in final if m.role is Role.TOOL]
        assert [m.tool_call_id for m in tool_messages] == ["a", "b"]
        assert [m.name for m in tool_messages] == ["list_fields", "get_field"]
        assert any(m.role is Role.ASSISTANT and m.tool_calls for m in final)

    @pytest.mark.asyncio
    async def test_a_field_the_registry_does_not_hold_is_a_result_and_the_loop_goes_on(
        self,
    ):
        install(FakeTools(get_field=ValueError("nope.nope is not registered")))
        client = FakeClient(
            wants("get_field", field_id="nope.nope"),
            says(""),
            says(a_fragment()),
        )

        outcome = await run_loop(client)

        assert outcome.fragment.verdict is Verdict.HOLD
        assert outcome.fetched_field_ids == ()
        failed = [
            m
            for m in client.requests[-1].messages
            if m.role is Role.TOOL and "nope.nope" in (m.content or "")
        ]
        assert failed

    @pytest.mark.asyncio
    async def test_a_figure_already_in_the_seed_is_not_added_twice(self):
        install(FakeTools(get_field=a_figure_payload(USABLE)))
        client = FakeClient(
            wants("get_field", field_id=USABLE),
            says(""),
            says(a_fragment()),
        )

        outcome = await run_loop(client)

        assert outcome.fetched_field_ids == ()
        ids = [
            figure.field_id
            for section in outcome.envelope.sections
            for figure in section.figures
        ]
        assert ids.count(USABLE) == 1


class TestTheRoundCeiling:
    @pytest.mark.asyncio
    async def test_the_loop_stops_at_the_ceiling_and_still_answers(self):
        install(FakeTools(get_field=a_figure_payload()))
        client = FakeClient(
            rounds=wants("get_field", field_id=SUBSTITUTE),
            final=says(a_fragment()),
        )

        outcome = await run_loop(client, max_rounds=2)

        assert outcome.rounds_used == 2
        assert outcome.fragment.verdict is Verdict.HOLD
        assert client.calls == 3

    @pytest.mark.asyncio
    async def test_repeating_one_failing_call_is_refused_before_the_rounds_run_out(
        self,
    ):
        install(FakeTools(get_field=ValueError("the store is not answering")))
        client = FakeClient(
            rounds=wants("get_field", field_id=SUBSTITUTE),
            final=says(a_fragment()),
        )

        outcome = await run_loop(client)

        # The guardrail either blocked or halted, so the ladder is not warn-only.
        assert outcome.rounds_used <= MAX_TOOL_ROUNDS
        assert outcome.fragment.verdict is Verdict.HOLD
        blocked = [
            m
            for m in client.requests[-1].messages
            if m.role is Role.TOOL and "Do not repeat it" in (m.content or "")
        ]
        assert blocked


class TestNothingIsPublishedEmpty:
    @pytest.mark.asyncio
    async def test_a_fragment_invalid_twice_fails_the_attempt_by_name(self):
        install(FakeTools())
        client = FakeClient(says(""), says("not json"), says("still not json"))

        with pytest.raises(ProductionFailure) as raised:
            await run_loop(client)

        assert raised.value.code == "invalid_model_output"
        assert raised.value.code in FAILURE_CODES

    @pytest.mark.asyncio
    async def test_a_dead_credential_is_auth_unavailable(self):
        install(FakeTools())
        client = FakeClient(AuthUnavailable("the route rejected the credential"))

        with pytest.raises(ProductionFailure) as raised:
            await run_loop(client)

        assert raised.value.code == "auth_unavailable"

    @pytest.mark.asyncio
    async def test_a_route_that_will_not_answer_is_a_transport_error(self):
        install(FakeTools())
        client = FakeClient(GatewayTimeout("upstream took too long"))

        with pytest.raises(ProductionFailure) as raised:
            await run_loop(client)

        assert raised.value.code == "llm_transport_error"

    @pytest.mark.asyncio
    async def test_a_refused_first_reservation_is_a_spend_failure(self):
        install(FakeTools())
        client = FakeClient(
            BudgetRefusal("analysis_cost", "This Analysis has spent its allowance.")
        )

        with pytest.raises(ProductionFailure) as raised:
            await run_loop(client)

        assert raised.value.code == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_a_refused_regeneration_blames_the_fragment_and_not_the_ledger(self):
        install(FakeTools())
        client = FakeClient(
            says(""),
            says("not json"),
            BudgetRefusal("analysis_cost", "This Analysis has spent its allowance."),
        )

        with pytest.raises(ProductionFailure) as raised:
            await run_loop(client)

        assert raised.value.code == "invalid_model_output"


class TestEveryCallIsReserved:
    @pytest.mark.asyncio
    async def test_every_call_reserves_against_the_run_that_owns_the_analysis(self):
        install(FakeTools(get_field=a_figure_payload()))
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE),
            says(""),
            says(a_fragment()),
        )

        await run_loop(client)

        assert len(client.spends) == client.calls
        for spend in client.spends:
            assert spend is not None
            assert spend.owner.type is OwnerType.ANALYSIS_RUN
            assert spend.owner.id == str(RUN_ID)
            assert spend.lane is BudgetLane.ANALYSIS

    @pytest.mark.asyncio
    async def test_a_tool_round_reserves_less_output_than_the_final_call(self):
        install(FakeTools(get_field=a_figure_payload()))
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE),
            says(""),
            says(a_fragment()),
        )

        await run_loop(client)

        assert client.spends[0].output_tokens == ROUND_OUTPUT_TOKENS
        assert client.spends[-1].output_tokens == MAX_OUTPUT_TOKENS


class TestTheTrace:
    """The audit record that is what this lane bought with reproducibility."""

    @pytest.mark.asyncio
    async def test_one_row_per_call_in_the_order_the_model_issued_them(self):
        install(
            FakeTools(
                get_field=a_figure_payload(),
                list_fields={"count": 30, "fields": []},
            )
        )
        recorder = Recorder()
        client = FakeClient(
            wants_many(
                ("a", "list_fields", {}),
                ("b", "get_field", {"field_id": SUBSTITUTE}),
            ),
            wants("get_field", "c", field_id="factor_percentiles.size_percentile"),
            says(""),
            says(a_fragment()),
        )

        outcome = await run_loop(client, session_opener=recorder)

        assert len(recorder.rows) == outcome.calls == 3
        assert [row.tool_name for row in recorder.rows] == [
            "list_fields",
            "get_field",
            "get_field",
        ]
        assert [(row.round_index, row.seq) for row in recorder.rows] == [
            (0, 1),
            (0, 2),
            (1, 1),
        ]
        assert [row.tool_call_id for row in recorder.rows] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_every_row_is_anchored_to_the_run_and_carries_its_status(self):
        install(FakeTools(get_field=a_figure_payload()))
        recorder = Recorder()
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE), says(""), says(a_fragment())
        )

        await run_loop(client, session_opener=recorder)

        row = recorder.rows[0]
        assert row.run_id == RUN_ID
        assert row.status == "ok"
        assert row.error is None
        assert row.arguments == {"field_id": SUBSTITUTE}
        assert row.result["fieldId"] == SUBSTITUTE
        assert row.started_at == datetime(2026, 8, 12, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_a_failed_call_is_recorded_with_the_reason_it_failed(self):
        install(FakeTools(get_field=ValueError("nope.nope is not registered")))
        recorder = Recorder()
        client = FakeClient(
            wants("get_field", field_id="nope.nope"), says(""), says(a_fragment())
        )

        await run_loop(client, session_opener=recorder)

        row = recorder.rows[0]
        assert row.status == "tool_error"
        assert "nope.nope" in row.error
        # The text is kept as well as the code: a status alone is blank to a
        # person reading the trace six weeks later.
        assert row.result["text"]

    @pytest.mark.asyncio
    async def test_a_call_the_guardrail_refused_is_recorded_as_blocked(self):
        install(FakeTools(get_field=ValueError("the store is not answering")))
        recorder = Recorder()
        client = FakeClient(
            rounds=wants("get_field", field_id=SUBSTITUTE),
            final=says(a_fragment()),
        )

        await run_loop(client, session_opener=recorder)

        statuses = [row.status for row in recorder.rows]
        assert "tool_error" in statuses
        assert "blocked" in statuses

    @pytest.mark.asyncio
    async def test_a_lost_trace_row_does_not_lose_the_analysis(self):
        """A bookkeeping failure must not turn into a missing artifact."""

        class _Broken:
            def __call__(self):
                return self

            def __enter__(self):
                raise RuntimeError("the trace table is gone")

            def __exit__(self, *exc):
                return False

        install(FakeTools(get_field=a_figure_payload()))
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE), says(""), says(a_fragment())
        )

        outcome = await run_loop(client, session_opener=_Broken())

        assert outcome.fragment.verdict is Verdict.HOLD
        assert SUBSTITUTE in outcome.envelope.field_ids

    @pytest.mark.asyncio
    async def test_a_round_that_never_answers_is_recorded_as_a_timeout(
        self, monkeypatch
    ):
        async def never(awaitable, _timeout):
            # Closed rather than abandoned, so the test does not leave a
            # never-awaited coroutine behind for the next one to trip over.
            awaitable.close()
            raise TimeoutError

        monkeypatch.setattr(
            "src.alpha.analysis_loop.asyncio.wait_for", never, raising=True
        )
        install(FakeTools(get_field=a_figure_payload()))
        recorder = Recorder()
        client = FakeClient(
            wants("get_field", field_id=SUBSTITUTE), says(a_fragment())
        )

        outcome = await run_loop(client, session_opener=recorder)

        assert [row.status for row in recorder.rows] == ["timeout"]
        # And the Analysis is still written, from the evidence it already had.
        assert outcome.fragment.verdict is Verdict.HOLD
        assert outcome.fetched_field_ids == ()
