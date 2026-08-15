"""One call, six rules, one regeneration, and nothing patched.

The generation is the only place a probabilistic thing touches the nightly
pipeline, so every test here is about the fence around it —

*The call is fixed.* One request per generation, temperature 0, a strict schema,
no tools and therefore no loop, and a system prompt that is byte-identical for
every symbol. A prompt built by branching on the envelope is a prompt nobody can
cache, review or compare across two Analyses.

*Provider validation is not trusted.* A gateway silently dropping
``response_format`` was measured. Prose where an object was asked for is caught
here and treated as an ordinary invalid fragment.

*The backend never repairs model output.* A first invalid fragment buys exactly
one regeneration, supplied with machine-readable errors. A second fails the
attempt with ``invalid_model_output``, and what comes back is discarded rather
than edited into shape.

*Nothing reaches a provider without a committed reservation.* Proven by reading
the ``SpendRequest`` the client was handed, on every call.

The client is a fake. What is under test is this module's control flow, and a
real route would make these tests measure a model instead.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest

from src.alpha.envelope import (
    EvidenceEnvelope,
    EvidenceFigure,
    EvidenceSection,
    Health,
)
from src.alpha.field_profile import AXIS_ORDER, AnalysisIndustry, Axis
from src.alpha.generation import (
    FRAGMENT_SCHEMA,
    MAX_OUTPUT_TOKENS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    AnalysisFragment,
    Emphasis,
    FragmentRejected,
    Verdict,
    build_request,
    generate_fragment,
    spend_for,
    validate_fragment,
)
from src.alpha.producer import FAILURE_CODES, ProductionFailure
from src.core.llm import (
    AuthUnavailable,
    BudgetLane,
    BudgetRefusal,
    Completion,
    GatewayTimeout,
    ModelRefusal,
    OwnerType,
    Role,
    Usage,
    Workload,
)

TRADING_DAY = date(2026, 8, 12)
RUN_ID = 4242
MODEL = "test-batch-model"

USABLE = "realized_volatility.yang_zhang_annualized_pct"
DEGRADED = "company_profile.foreign_room_pct"
REFUSED = "news_flow.approved_item_count_7_sessions"


def a_figure(
    field_id: str,
    health: Health = Health.OK,
    *,
    axis: Axis = Axis.TECHNICAL,
) -> EvidenceFigure:
    return EvidenceFigure(
        field_id=field_id,
        label=field_id,
        value=None if health is Health.REFUSED else 12.5,
        unit="percent",
        kind="estimator",
        source="computed",
        interpretation="How far this symbol usually travels in a day.",
        health=health,
        reason_code=None if health is Health.OK else "unavailable",
        reason=None if health is Health.OK else "Nothing holds this yet.",
        as_of=None if health is Health.REFUSED else TRADING_DAY,
        sessions_used=None if health is Health.REFUSED else 61,
        window_days=61,
        extras={},
    )


def an_envelope(symbol: str = "ENVSYM") -> EvidenceEnvelope:
    """One envelope with a usable figure, a degraded one and a refused one."""
    by_axis = {
        Axis.TECHNICAL: (a_figure(USABLE),),
        Axis.FUNDAMENTAL: (a_figure("factor_percentiles.roe_percentile"),),
        Axis.MONEY_FLOW: (a_figure(DEGRADED, Health.DEGRADED),),
        Axis.NEWS: (a_figure(REFUSED, Health.REFUSED),),
    }
    return EvidenceEnvelope(
        symbol=symbol,
        company_name="Công ty Cổ phần Thử Nghiệm",
        exchange="HOSE",
        industry=AnalysisIndustry.UNCLASSIFIED,
        trading_day=TRADING_DAY,
        price_zone=a_figure("price_zone.ordinary_range_pct"),
        sections=tuple(
            EvidenceSection(axis=axis, figures=by_axis[axis]) for axis in AXIS_ORDER
        ),
        window_health={"sessionsUsed": 21, "refusal": None},
    )


def a_fragment(**overrides) -> dict:
    payload = {
        "verdict": "hold",
        "verdictLine": "Ordinary volatility, thin evidence elsewhere.",
        "thesis": "The technical picture is the only whole one tonight.",
        "citedFieldIds": [USABLE],
        "axes": [
            {
                "axis": axis.value,
                "emphasis": "lead" if axis is Axis.TECHNICAL else "context",
                "emphasisReason": "Because the evidence sits here.",
                "read": "Nothing unusual for this symbol.",
            }
            for axis in AXIS_ORDER
        ],
    }
    payload.update(overrides)
    return payload


class FakeClient:
    """Every answer scripted, and every request kept for inspection."""

    def __init__(self, *answers) -> None:
        self._answers = list(answers)
        self.requests: list = []
        self.spends: list = []

    async def complete(self, request, spend=None):
        self.requests.append(request)
        self.spends.append(spend)
        if not self._answers:
            raise AssertionError("the generator asked for more calls than scripted")
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return Completion(
            model=MODEL,
            text=answer if isinstance(answer, str) else json.dumps(answer),
            usage=Usage(input_tokens=3_000, output_tokens=400),
        )

    @property
    def calls(self) -> int:
        return len(self.requests)


async def generate(client, envelope=None) -> AnalysisFragment:
    return await generate_fragment(
        client, envelope or an_envelope(), model=MODEL, run_id=RUN_ID
    )


class TestTheFixedCall:
    @pytest.mark.asyncio
    async def test_one_call_per_attempt_when_the_fragment_is_valid(self):
        client = FakeClient(a_fragment())
        await generate(client)
        assert client.calls == 1

    def test_it_is_temperature_zero_with_a_strict_schema_and_no_tools(self):
        request = build_request(an_envelope(), MODEL)
        assert request.temperature == 0.0
        assert request.response_format is not None
        assert request.response_format.strict is True
        assert request.tools == ()
        assert request.tool_choice == "none"
        assert request.max_output_tokens == MAX_OUTPUT_TOKENS

    def test_the_stable_prefix_does_not_vary_with_the_symbol(self):
        """Prompt caching covers the system prompt and the schema, and nothing else."""
        first = build_request(an_envelope("AAA"), MODEL)
        second = build_request(an_envelope("BBB"), MODEL)

        assert first.messages[0] == second.messages[0]
        assert first.messages[0].role is Role.SYSTEM
        assert first.response_format == second.response_format
        # And the varying half really does vary, or the assertion above is empty.
        assert first.messages[1] != second.messages[1]

    def test_the_system_prompt_is_a_constant_rather_than_a_template(self):
        assert "{" not in SYSTEM_PROMPT
        assert "%s" not in SYSTEM_PROMPT
        assert PROMPT_VERSION == "v1"

    def test_the_route_dropping_the_schema_is_caught_rather_than_trusted(self):
        """Prose where an object was asked for is a rejection, not an answer."""
        with pytest.raises(FragmentRejected) as rejected:
            validate_fragment("Tôi nghĩ mã này ổn.", an_envelope())
        assert rejected.value.errors[0].code == "not_an_object"


class TestWhatTheFragmentMayCarry:
    def test_exactly_the_five_model_owned_things(self):
        assert set(FRAGMENT_SCHEMA["properties"]) == {
            "verdict",
            "verdictLine",
            "thesis",
            "citedFieldIds",
            "axes",
        }

    def test_no_claim_field_exists_anywhere_in_the_schema(self):
        assert "claim" not in json.dumps(FRAGMENT_SCHEMA)

    def test_the_schema_closes_every_object_it_defines(self):
        assert FRAGMENT_SCHEMA["additionalProperties"] is False
        assert FRAGMENT_SCHEMA["properties"]["axes"]["items"][
            "additionalProperties"
        ] is False

    def test_a_sixth_field_is_rejected_even_if_the_route_let_it_through(self):
        with pytest.raises(FragmentRejected) as rejected:
            validate_fragment(a_fragment(claim="descriptive"), an_envelope())
        assert "unexpected_field" in {error.code for error in rejected.value.errors}

    def test_the_verdict_vocabulary_is_the_five_the_rail_renders(self):
        assert [item.value for item in Verdict] == [
            "accumulate",
            "hold",
            "reduce",
            "avoid",
            "watch",
        ]


class TestWhatTheModelIsShown:
    def test_refused_fields_and_their_reason_codes_reach_the_model(self):
        request = build_request(an_envelope(), MODEL)
        sent = json.loads(request.messages[1].content)
        news = sent["sections"][-1]["figures"][0]

        assert news["health"] == "refused"
        assert news["reasonCode"] == "unavailable"
        assert news["reason"]

    def test_a_fragment_citing_a_refused_field_is_rejected(self):
        with pytest.raises(FragmentRejected) as rejected:
            validate_fragment(
                a_fragment(citedFieldIds=[USABLE, REFUSED]), an_envelope()
            )
        assert "refused_field_cited" in {
            error.code for error in rejected.value.errors
        }

    def test_a_degraded_field_may_be_cited(self):
        fragment = validate_fragment(
            a_fragment(citedFieldIds=[DEGRADED]), an_envelope()
        )
        assert fragment.cited_field_ids == (DEGRADED,)


class TestTheSixRules:
    def test_an_empty_citation_list_is_rejected(self):
        assert _codes(a_fragment(citedFieldIds=[])) == {"no_citation"}

    def test_an_id_outside_the_envelope_is_rejected(self):
        assert "unknown_field" in _codes(
            a_fragment(citedFieldIds=["made.up_field"])
        )

    def test_a_refused_citation_is_rejected(self):
        assert "refused_field_cited" in _codes(a_fragment(citedFieldIds=[REFUSED]))

    def test_a_reordered_axis_list_is_rejected(self):
        axes = list(reversed(a_fragment()["axes"]))
        assert "axis_order" in _codes(a_fragment(axes=axes))

    def test_an_extra_axis_is_rejected(self):
        axes = a_fragment()["axes"] + [
            {
                "axis": "technical",
                "emphasis": "context",
                "emphasisReason": "…",
                "read": "…",
            }
        ]
        assert "axis_order" in _codes(a_fragment(axes=axes))

    def test_two_leads_are_rejected(self):
        axes = a_fragment()["axes"]
        axes[1]["emphasis"] = "lead"
        assert "lead_axis" in _codes(a_fragment(axes=axes))

    def test_no_lead_at_all_is_rejected(self):
        axes = a_fragment()["axes"]
        axes[0]["emphasis"] = "support"
        assert "lead_axis" in _codes(a_fragment(axes=axes))

    def test_a_verdict_outside_the_vocabulary_is_rejected(self):
        assert "verdict_out_of_range" in _codes(a_fragment(verdict="strong_buy"))

    def test_an_emphasis_outside_the_vocabulary_is_rejected(self):
        axes = a_fragment()["axes"]
        axes[2]["emphasis"] = "headline"
        assert "emphasis_out_of_range" in _codes(a_fragment(axes=axes))

    def test_missing_narration_is_rejected_field_by_field(self):
        assert "narration_missing" in _codes(a_fragment(thesis="   "))
        assert "narration_missing" in _codes(a_fragment(verdictLine=""))

        axes = a_fragment()["axes"]
        axes[3]["read"] = ""
        assert "narration_missing" in _codes(a_fragment(axes=axes))

    def test_a_refused_section_still_needs_its_narration(self):
        """Saying what is missing is the whole point of the axis being there."""
        axes = a_fragment()["axes"]
        axes[3]["emphasisReason"] = ""
        assert "narration_missing" in _codes(a_fragment(axes=axes))

    def test_every_error_is_machine_readable(self):
        with pytest.raises(FragmentRejected) as rejected:
            validate_fragment(a_fragment(verdict="nope", thesis=""), an_envelope())

        feedback = json.loads(rejected.value.as_feedback())
        assert len(feedback["validationErrors"]) >= 2
        for error in feedback["validationErrors"]:
            assert set(error) == {"path", "code", "message"}
            assert error["path"].startswith("$")

    def test_every_rule_is_evaluated_rather_than_the_first_one_raised(self):
        """A regeneration told one problem at a time is a loop, not a retry."""
        codes = _codes(a_fragment(verdict="nope", thesis="", citedFieldIds=[]))
        assert codes >= {"verdict_out_of_range", "narration_missing", "no_citation"}


class TestTheOneRegeneration:
    @pytest.mark.asyncio
    async def test_a_first_invalid_fragment_triggers_exactly_one_more_call(self):
        client = FakeClient(a_fragment(verdict="strong_buy"), a_fragment())

        fragment = await generate(client)

        assert client.calls == 2
        assert fragment.verdict is Verdict.HOLD

    @pytest.mark.asyncio
    async def test_the_regeneration_is_handed_the_validation_errors(self):
        client = FakeClient(a_fragment(citedFieldIds=[]), a_fragment())

        await generate(client)

        second = client.requests[1]
        assert second.messages[0] == client.requests[0].messages[0]
        assert second.messages[2].role is Role.ASSISTANT
        feedback = json.loads(second.messages[3].content)
        assert feedback["validationErrors"][0]["code"] == "no_citation"

    @pytest.mark.asyncio
    async def test_a_second_invalid_fragment_fails_the_attempt(self):
        client = FakeClient(a_fragment(verdict="nope"), a_fragment(verdict="also_no"))

        with pytest.raises(ProductionFailure) as raised:
            await generate(client)

        assert raised.value.code == "invalid_model_output"
        assert client.calls == 2

    @pytest.mark.asyncio
    async def test_nothing_is_patched_into_validity(self):
        """The invalid fragment is discarded, never edited and published."""
        client = FakeClient(a_fragment(verdict="nope"), a_fragment(verdict="nope"))

        with pytest.raises(ProductionFailure):
            await generate(client)

        assert client.calls == 2

    @pytest.mark.asyncio
    async def test_a_regeneration_the_budget_cannot_fund_is_not_attempted(self):
        client = FakeClient(
            a_fragment(verdict="nope"),
            BudgetRefusal("analysis_cost", "This Analysis has spent its allowance."),
        )

        with pytest.raises(ProductionFailure) as raised:
            await generate(client)

        assert raised.value.code == "invalid_model_output"
        assert "analysis_cost" in raised.value.message

    @pytest.mark.asyncio
    async def test_a_first_generation_the_budget_cannot_fund_says_so(self):
        client = FakeClient(
            BudgetRefusal("lane_budget_exhausted", "The lane is unavailable.")
        )

        with pytest.raises(ProductionFailure) as raised:
            await generate(client)

        assert raised.value.code == "budget_exhausted"
        assert client.calls == 1


class TestSpendAdmission:
    @pytest.mark.asyncio
    async def test_every_generation_carries_a_spend_request(self):
        client = FakeClient(a_fragment(verdict="nope"), a_fragment())

        await generate(client)

        assert len(client.spends) == 2
        for spend in client.spends:
            assert spend is not None
            assert spend.lane is BudgetLane.ANALYSIS
            assert spend.workload is Workload.BATCH

    def test_the_owner_is_the_run_so_the_ceiling_spans_every_attempt(self):
        spend = spend_for(build_request(an_envelope(), MODEL), RUN_ID)
        assert spend.owner.type is OwnerType.ANALYSIS_RUN
        assert spend.owner.id == str(RUN_ID)

    def test_the_worst_case_stays_inside_the_per_call_ceilings(self):
        from src.core.llm.admission import (
            ANALYSIS_INPUT_PER_CALL,
            ANALYSIS_OUTPUT_PER_CALL,
        )

        spend = spend_for(build_request(an_envelope(), MODEL), RUN_ID)
        assert 0 < spend.input_tokens <= ANALYSIS_INPUT_PER_CALL
        assert 0 < spend.output_tokens <= ANALYSIS_OUTPUT_PER_CALL

    def test_one_generation_leaves_room_for_the_sanctioned_regeneration(self):
        """Reserving the per-call ceiling would make the retry unfundable by design."""
        from src.core.llm.admission import ANALYSIS_INPUT_PER_CALL

        spend = spend_for(build_request(an_envelope(), MODEL), RUN_ID)
        assert spend.input_tokens * 2 <= ANALYSIS_INPUT_PER_CALL


class TestFailureMapping:
    @pytest.mark.asyncio
    async def test_a_dead_credential_is_auth_unavailable(self):
        client = FakeClient(AuthUnavailable("the route rejected the credential (401)"))

        with pytest.raises(ProductionFailure) as raised:
            await generate(client)

        assert raised.value.code == "auth_unavailable"

    @pytest.mark.asyncio
    async def test_a_route_that_did_not_answer_is_a_transport_error(self):
        client = FakeClient(GatewayTimeout("the route did not answer (504)"))

        with pytest.raises(ProductionFailure) as raised:
            await generate(client)

        assert raised.value.code == "llm_transport_error"

    @pytest.mark.asyncio
    async def test_a_model_refusal_ends_the_attempt_without_re_prompting(self):
        client = FakeClient(ModelRefusal("I cannot help with that."))

        with pytest.raises(ProductionFailure) as raised:
            await generate(client)

        assert raised.value.code == "invalid_model_output"
        assert client.calls == 1

    @pytest.mark.asyncio
    async def test_every_failure_is_one_bounded_line(self):
        """A route's body arrives multi-line and long; the column holds neither."""
        body = "\n".join(f"upstream detail line {index}" for index in range(200))
        for failure in (AuthUnavailable(body), GatewayTimeout(body)):
            client = FakeClient(failure)
            with pytest.raises(ProductionFailure) as raised:
                await generate(client)
            assert "\n" not in raised.value.message
            assert len(raised.value.message) <= 500

    @pytest.mark.asyncio
    async def test_the_message_is_the_one_this_module_declared(self):
        """Never ``str(exception)`` on its own, so a stack trace has no route in."""
        client = FakeClient(GatewayTimeout("connect timeout after 120s"))

        with pytest.raises(ProductionFailure) as raised:
            await generate(client)

        assert raised.value.message.startswith("Tuyến LLM không trả lời được:")

    def test_every_code_this_module_raises_is_in_the_taxonomy(self):
        assert {
            "auth_unavailable",
            "llm_transport_error",
            "invalid_model_output",
            "budget_exhausted",
        } <= FAILURE_CODES


class TestTheValidatedFragment:
    def test_it_names_its_lead_axis(self):
        fragment = validate_fragment(a_fragment(), an_envelope())
        assert fragment.lead_axis is Axis.TECHNICAL

    def test_it_round_trips_to_the_wire_shape_the_model_was_given(self):
        payload = a_fragment()
        fragment = validate_fragment(payload, an_envelope())
        assert fragment.as_wire() == payload

    def test_it_is_frozen_so_nothing_edits_a_validated_fragment_afterwards(self):
        """The backend never patches model output, including after it passed."""
        fragment = validate_fragment(a_fragment(), an_envelope())
        with pytest.raises(AttributeError):
            fragment.verdict = Verdict.AVOID  # type: ignore[misc]
        # A copy is a new object rather than an edit of the validated one.
        assert replace(fragment, verdict=Verdict.AVOID) is not fragment
        assert fragment.verdict is Verdict.HOLD

    def test_a_citation_of_the_price_zone_is_allowed(self):
        envelope = an_envelope()
        fragment = validate_fragment(
            a_fragment(citedFieldIds=["price_zone.ordinary_range_pct"]), envelope
        )
        assert fragment.cited_field_ids == ("price_zone.ordinary_range_pct",)

    def test_the_emphasis_vocabulary_is_the_three_the_layout_knows(self):
        assert [item.value for item in Emphasis] == ["lead", "support", "context"]


def _codes(payload: dict) -> set[str]:
    with pytest.raises(FragmentRejected) as rejected:
        validate_fragment(payload, an_envelope())
    return {error.code for error in rejected.value.errors}
