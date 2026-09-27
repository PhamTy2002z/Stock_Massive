"""The deep lane's real research, counterevidence, and clean verifier passes."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Any

import pytest

from src.agent import registry
from src.agent.loop import AgentLoop, TurnRequest, TurnStatus
from src.agent.lanes import DEEP
from src.agent.messages import ANSWER, THOUGHT
from src.agent.prompt import RuntimeContext
from src.agent.toolsets import clear_memo
from src.core.llm import Completion, LLMConfig, LLMRoute, ToolCall, Usage, Workload
from src.core.llm.config import BudgetLanes, PricingTable, TokenPrices

from .agent_tool_world import isolated_registry

MODEL = "gpt-5.6-luna"
NOW = datetime.fromisoformat("2026-08-21T15:00:00+07:00")


def config() -> LLMConfig:
    prices = TokenPrices(input=1.0, cached_input=0.5, cache_write=1.5, output=8.0)
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://route.example", api_key="k"),
        models=MappingProxyType({Workload.BATCH: MODEL, Workload.SESSION: MODEL}),
        pricing=PricingTable(
            version="2026-08", effective_from=None, batch=prices, session=prices
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=90,
            analysis_usd=40.0,
            turn_usd=40.0,
            emergency_usd=10.0,
        ),
    )


def completion(*, text: str | None = None, calls=()):
    return Completion(
        model=MODEL,
        text=text,
        tool_calls=tuple(calls),
        usage=Usage(input_tokens=20, output_tokens=10),
    )


def _first_claim_id(claims) -> str:
    """The ID the verifier was shown, or none when it was shown no claims."""
    return next((str(item["claimId"]) for item in claims), "")


def call(call_id: str, name: str, **arguments):
    return ToolCall(id=call_id, name=name, arguments=arguments)


def research_draft():
    return json.dumps(
        {
            "claims": [
                {
                    "claim_id": "profit",
                    "text": "Lợi nhuận đạt 1.245 tỷ đồng.",
                    "kind": "fact",
                    "material": True,
                    "candidate_evidence_ids": [],
                    "unit": "tỷ đồng",
                    "currency": "VND",
                }
            ],
            "gaps": [],
            "assumptions": ["So sánh theo số đã công bố."],
            "invalidations": [],
            "question": None,
        },
        ensure_ascii=False,
    )


def counter_draft():
    return json.dumps(
        {
            "claims": [
                {
                    "claim_id": "adjusted",
                    "text": "Một nguồn cho rằng lợi nhuận điều chỉnh còn 1.100 tỷ đồng.",
                    "kind": "fact",
                    "material": True,
                    "candidate_evidence_ids": [],
                    "unit": "tỷ đồng",
                    "currency": "VND",
                }
            ],
            "gaps": ["Chưa có xác nhận thứ hai cho số điều chỉnh."],
            "assumptions": [],
            "invalidations": ["Luận điểm sai nếu số kiểm toán thay thế số công bố."],
            "question": None,
        },
        ensure_ascii=False,
    )


class PipelineClient:
    def __init__(self, *, invalid_verifier: bool = False) -> None:
        self.requests = []
        self.spends = []
        self.invalid_verifier = invalid_verifier
        self.step = 0
        #: The tool names offered on each call, in order.
        self.offered: list[list[str]] = []

    async def complete(self, request, spend=None):
        self.requests.append(request)
        self.spends.append(spend)
        self.offered.append([tool.name for tool in request.tools])
        self.step += 1
        if self.step == 1:
            return completion(
                calls=(
                    call("plan-price", "web_search", query="HPG giá biến động phiên 20/8/2026"),
                    call("plan-event", "web_search", query="HPG sự kiện công bố lợi nhuận 2026"),
                    call("plan-company", "web_search", query="HPG ngành thép kết quả kinh doanh 2026"),
                    call("plan-counter", "web_search", query="HPG rủi ro phản biện lợi nhuận 2026"),
                )
            )
        if self.step == 2:
            return completion(
                text="Tôi đang đọc công bố gốc.",
                calls=(call("fetch-issuer", "fetch_url", url="https://issuer.example/report"),),
            )
        if self.step == 3:
            return completion(text=research_draft())
        if self.step == 4:
            return completion(
                text="Tôi đang kiểm tra số liệu phản bác.",
                calls=(call("fetch-audit", "fetch_url", url="https://audit.example/story"),),
            )
        if self.step == 5:
            return completion(text=counter_draft())
        assert request.response_format is not None
        assert request.tools == ()
        assert request.tool_choice == "none"
        clean = json.loads(str(request.messages[-1].content))
        evidence = {item["publisher"]: item["evidenceId"] for item in clean["evidence"]}
        # The IDs the verifier answers with are the ones it was shown, which is
        # how a research claim and a counter claim numbered alike stay apart.
        research_id = _first_claim_id(clean["research_claims"])
        counter_id = _first_claim_id(clean["counter_claims"])
        text = (
            "not-json"
            if self.invalid_verifier
            else json.dumps(
                {
                    "claims": [
                        {
                            "claim_id": research_id,
                            "verdict": "conflicting",
                            "supporting_evidence_ids": [evidence["Issuer IR"]],
                            "contradicting_evidence_ids": [evidence["Audit News"]],
                            "invalidation_text": "Sai nếu số kiểm toán thay thế số công bố.",
                        },
                        {
                            "claim_id": counter_id,
                            "verdict": "single_source",
                            "supporting_evidence_ids": [evidence["Audit News"]],
                            "contradicting_evidence_ids": [],
                            "invalidation_text": "Sai nếu tổ chức phát hành bác bỏ điều chỉnh.",
                        },
                    ],
                    "gaps": ["Cần thêm xác nhận độc lập."],
                },
                ensure_ascii=False,
            )
        )
        return completion(text=text)


class Publisher:
    def __init__(self):
        self.deltas = []
        self.thoughts = []
        self.calls = []
        self.parts = []

    def content_delta(self, text, *, kind=ANSWER, round=0):
        (self.thoughts if kind == THOUGHT else self.deltas).append(text)

    def tool_call(self, payload):
        self.calls.append(dict(payload))

    def progress(self, payload):
        self.parts.append(dict(payload))


def entry(name: str, handler, *, network: bool):
    return registry.ToolEntry(
        name=name,
        toolset="web" if network else "memory",
        description=f"stub {name}",
        schema=registry.object_schema(
            {"query": {"type": "string"}, "url": {"type": "string"}}
        ),
        handler=handler,
        display_name=name,
        summary_detail_arg="query" if name != "fetch_url" else "url",
        effect=registry.ToolEffect.READ,
        idempotency=registry.ToolIdempotency.IDEMPOTENT,
        access=registry.ToolAccess.NETWORK if network else registry.ToolAccess.STORE,
        concurrency=registry.ToolConcurrency.PARALLEL_SAFE,
        content_trust=(
            registry.ContentTrust.UNTRUSTED
            if network
            else registry.ContentTrust.TRUSTED_STRUCTURED
        ),
        permission=registry.ToolPermission.ALLOW,
    )


async def search(_context, arguments):
    query = str(arguments["query"])
    return {
        "query": query,
        "results": [
            {
                "url": "https://issuer.example/report",
                "title": "Issuer report",
                "snippet": "discovery only",
                "source": "issuer.example",
                "durable_evidence": False,
            }
        ],
        "reason": None,
    }


async def fetch(_context, arguments):
    url = str(arguments["url"])
    issuer = "issuer" in url
    content = (
        "Lợi nhuận đạt 1.245 tỷ đồng."
        if issuer
        else "Lợi nhuận điều chỉnh còn 1.100 tỷ đồng."
    )
    return {
        "url": url,
        "canonical_url": url,
        "title": "Issuer filing" if issuer else "Audit story",
        "publisher": "Issuer IR" if issuer else "Audit News",
        "source": "issuer.example" if issuer else "audit.example",
        "source_class": "issuer" if issuer else "media",
        "source_tier": "primary" if issuer else "professional_media",
        "tos_risk": "low" if issuer else "medium",
        "durable_evidence": True,
        "content": content,
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "retrieved_at": "2026-08-21T08:00:00+07:00",
        "publication": {
            "publishedAt": "2026-08-20T09:00:00+07:00",
            "publicationMethod": "html_meta",
            "publicationConfidence": "high",
            "publicationPrecision": "instant",
        },
        "reason": None,
    }


async def memory(_context, _arguments):
    return {"results": []}


@pytest.fixture(autouse=True)
def tools():
    with isolated_registry():
        for item in (
            entry("web_search", search, network=True),
            entry("fetch_url", fetch, network=True),
            entry("session_search", memory, network=False),
            entry("remember_fact", memory, network=False),
            entry("recall_facts", memory, network=False),
        ):
            registry.register(item)
        clear_memo()
        yield
        clear_memo()


def request():
    return TurnRequest(
        thread_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        request_message_id=42,
        user_id=7,
        user_text="Viết memo kiểm chứng luận điểm lợi nhuận HPG.",
        runtime=RuntimeContext(today=date(2026, 8, 21), user_name="Ty"),
        lane_reason="keyword:memo",
    )


@pytest.mark.asyncio
async def test_deep_lane_runs_three_real_passes_and_renders_only_checked_ledger():
    client = PipelineClient()
    publisher = Publisher()
    trajectories = []
    cached = []

    async def trajectory(user_id, turn_id, *, stage, payload):
        trajectories.append((user_id, turn_id, stage, payload))

    async def cache(payload):
        cached.append(dict(payload))

    outcome = await AgentLoop(
        client=client,
        config=config(),
        lane=DEEP,
        publisher=publisher,
        trajectory=trajectory,
        evidence_cache=cache,
        clock=lambda: NOW,
    ).run(request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.claim_ledger is not None
    assert outcome.claim_ledger["verifierOutcome"] == "verified"
    assert [item["verdict"] for item in outcome.claim_ledger["claims"]] == [
        "conflicting",
        "single_source",
    ]
    assert "Nguồn mâu thuẫn" in outcome.answer
    assert "Một nguồn" in outcome.answer
    assert "https://issuer.example/report" in outcome.answer
    assert "https://audit.example/story" in outcome.answer
    assert publisher.thoughts == [
        "Tôi đang đọc công bố gốc.",
        "Tôi đang kiểm tra số liệu phản bác.",
    ]
    passes = [
        part["payload"]
        for part in publisher.parts
        if part["kind"] == "pipeline_pass"
    ]
    assert [item["stage"] for item in passes] == [
        "planning",
        "research",
        "counterevidence",
        "verification",
    ]
    assert passes[-1]["outcome"] == "passed"
    # Each pass files its own output under its own name: the first row is the
    # planner's four queries, and calling it "research" would make the trail say
    # the research pass returned queries and no claims.
    assert [item[2] for item in trajectories] == [
        "planning",
        "research",
        "counterevidence",
        "verification",
    ]
    assert len(cached) == 2
    assert all("user_id" not in item and "turn_id" not in item for item in cached)
    assert client.requests[0].tool_choice == "required"
    assert [tool.name for tool in client.requests[0].tools] == ["web_search"]
    assert len(client.requests[-1].messages) == 2
    assert client.requests[-1].response_format is not None


@pytest.mark.asyncio
async def test_verifier_parse_failure_fails_closed_but_returns_a_nonblank_answer():
    client = PipelineClient(invalid_verifier=True)

    outcome = await AgentLoop(
        client=client,
        config=config(),
        lane=DEEP,
        clock=lambda: NOW,
    ).run(request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.answer
    assert outcome.claim_ledger is not None
    assert outcome.claim_ledger["verifierOutcome"] == "verifier_failed"
    assert outcome.claim_ledger["claims"] == []
    assert "verification_schema_invalid" in outcome.answer


@pytest.mark.asyncio
async def test_planner_must_generate_four_distinct_search_queries():
    client = PipelineClient()
    client.complete = lambda request, spend=None: _one_bad_planner(request)  # type: ignore[method-assign]

    outcome = await AgentLoop(
        client=client,
        config=config(),
        lane=DEEP,
        clock=lambda: NOW,
    ).run(request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.claim_ledger["verifierOutcome"] == "verifier_failed"
    assert "planner_did_not_produce_the_batch_the_note_asked_for" in outcome.answer


async def _one_bad_planner(request):
    return completion(calls=(call("only-one", "web_search", query="HPG"),))


class ProseThenTypedClient(PipelineClient):
    """The research pass answers in prose; the strict retry returns the draft.

    Measured behaviour, not a hypothetical: on the first live Phase 6 run the
    research pass wrote a memo where the harness needed the object, because the
    shape was asked for by a note and not enforced by the route.
    """

    def __init__(self, *, recover: bool = True) -> None:
        super().__init__()
        self.recover = recover
        self.recovered = 0

    async def complete(self, request, spend=None):
        if self.step == 2:
            self.requests.append(request)
            self.spends.append(spend)
            self.step += 1
            return completion(text="Tôi kết luận rằng lợi nhuận đạt 1.245 tỷ đồng.")
        if request.response_format is not None and request.response_format.name == (
            "finance_research_draft"
        ):
            self.requests.append(request)
            self.spends.append(spend)
            self.recovered += 1
            assert request.tools == ()
            assert request.tool_choice == "none"
            return completion(text=research_draft() if self.recover else "still prose")
        return await super().complete(request, spend)


@pytest.mark.asyncio
async def test_a_pass_that_answers_in_prose_is_asked_once_more_and_the_memo_survives():
    client = ProseThenTypedClient()
    publisher = Publisher()

    outcome = await AgentLoop(
        client=client, config=config(), lane=DEEP, publisher=publisher, clock=lambda: NOW
    ).run(request())

    assert client.recovered == 1
    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.claim_ledger is not None
    # The pipeline ran on past the recovery rather than settling on it.
    assert outcome.claim_ledger["verifierOutcome"] == "verified"


@pytest.mark.asyncio
async def test_a_retry_that_also_misses_the_shape_fails_the_pipeline_honestly():
    """One retry, not a loop: the second miss is the pass's answer."""
    client = ProseThenTypedClient(recover=False)
    publisher = Publisher()

    outcome = await AgentLoop(
        client=client, config=config(), lane=DEEP, publisher=publisher, clock=lambda: NOW
    ).run(request())

    assert client.recovered == 1
    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.claim_ledger is not None
    assert outcome.claim_ledger["verifierOutcome"] != "verified"
    assert "research_draft_schema_invalid" in json.dumps(
        outcome.claim_ledger, ensure_ascii=False
    )


# -- the Signal Desk planning batch ----------------------------------------


def test_the_planning_gate_accepts_the_batch_the_market_note_asks_for():
    """The note and the gate have to agree, or every desk Turn fails round one.

    The Signal Desk note asks for three searches and one market read. A gate
    counting four searches rejects exactly that batch — so a Turn obeying its own
    instructions would settle ``planner_did_not_produce…`` before it read
    anything. Asserted directly on the predicate because the failure it guards
    against is a disagreement between two files.
    """
    from src.agent.loop import AgentLoop as Loop

    desk_batch = (
        call("plan-event", "web_search", query="FPT sự kiện"),
        call("plan-company", "web_search", query="FPT ngành công nghệ"),
        call("plan-counter", "web_search", query="FPT rủi ro phản biện"),
        call("plan-market", "get_market_data", symbol="FPT"),
    )
    chat_batch = tuple(
        call(f"plan-{index}", "web_search", query=f"FPT {index}") for index in range(4)
    )

    assert Loop._valid_planner_calls(desk_batch, market=True) is True
    assert Loop._valid_planner_calls(chat_batch, market=False) is True
    # And neither shape is accepted on the other surface: a Turn with no market
    # read that spends a slot on one is a Turn that lost a search.
    assert Loop._valid_planner_calls(desk_batch, market=False) is False
    assert Loop._valid_planner_calls(chat_batch, market=True) is False


def test_the_planning_gate_accepts_one_market_read_for_a_chart_only_request():
    """A chart does not need three unrelated web searches before it can exist."""
    from src.agent.loop import AgentLoop as Loop

    market_only = (call("plan-market", "get_market_data", symbol="FPT"),)
    mixed_partial = (
        call("plan-market", "get_market_data", symbol="FPT"),
        call("plan-search", "web_search", query="FPT"),
    )

    assert Loop._valid_planner_calls(market_only, market=True) is True
    assert Loop._valid_planner_calls(mixed_partial, market=True) is False


def test_the_planning_gate_still_refuses_one_query_asked_three_ways():
    from src.agent.loop import AgentLoop as Loop

    same = (
        call("plan-1", "web_search", query="FPT"),
        call("plan-2", "web_search", query="fpt"),
        call("plan-3", "web_search", query="  FPT "),
        call("plan-market", "get_market_data", symbol="FPT"),
    )

    assert Loop._valid_planner_calls(same, market=True) is False


# -- a Signal Desk Turn, from the planning batch to the chart --------------

MARKET_ROWS = [
    {
        "bar_opened_at": "2026-08-19T07:00:00+07:00",
        "bar_closed_at": "2026-08-19T15:00:00+07:00",
        "open": 72_500, "high": 72_700, "low": 71_400, "close": 71_400,
        "volume": 4_611_900,
    },
    {
        "bar_opened_at": "2026-08-20T07:00:00+07:00",
        "bar_closed_at": "2026-08-20T15:00:00+07:00",
        "open": 71_400, "high": 72_000, "low": 71_000, "close": 71_900,
        "volume": 3_100_200,
    },
]

MARKET_EXCERPT = "\n".join(
    ["FPT · nến 1D · nguồn KB Securities qua vnstock · giá đã quy đổi sang VND đầy đủ"]
    + [
        f"{row['bar_closed_at']}: mở {row['open']:,} đồng · cao {row['high']:,} đồng · "
        f"thấp {row['low']:,} đồng · đóng {row['close']:,} đồng · "
        f"khối lượng {row['volume']:,} cổ phiếu".replace(",", ".")
        for row in MARKET_ROWS
    ]
)


async def market(_context, _arguments):
    """The one market read, shaped exactly as ``tools/market_data`` returns it."""
    return {
        "symbol": "FPT",
        "interval": "1D",
        "provider": "vnstock",
        "provider_version": "3.2.0",
        "source": "kbs",
        "publisher": "KB Securities",
        "source_class": "store",
        "currency": "VND",
        "price_unit": "VND",
        "price_scale_applied": 1000,
        "timezone": "Asia/Ho_Chi_Minh",
        "requested": {"start": "2026-08-19", "end": "2026-08-20"},
        "actual": {
            "start": MARKET_ROWS[0]["bar_closed_at"],
            "end": MARKET_ROWS[-1]["bar_closed_at"],
        },
        "row_count": len(MARKET_ROWS),
        "rows_dropped_after_horizon": 0,
        "truncated": False,
        "quality": "ok",
        "retrieved_at": "2026-08-21T08:00:00+07:00",
        "content_sha256": hashlib.sha256(MARKET_EXCERPT.encode()).hexdigest(),
        "rows": [dict(row) for row in MARKET_ROWS],
        "excerpt": MARKET_EXCERPT,
    }


def market_entry():
    return registry.ToolEntry(
        name="get_market_data",
        toolset="market_data",
        description="stub market read",
        schema=registry.object_schema({"symbol": {"type": "string"}}),
        handler=market,
        display_name="Đọc dữ liệu giá",
        summary_detail_arg="symbol",
        effect=registry.ToolEffect.READ,
        idempotency=registry.ToolIdempotency.IDEMPOTENT,
        access=registry.ToolAccess.NETWORK,
        concurrency=registry.ToolConcurrency.PARALLEL_SAFE,
        content_trust=registry.ContentTrust.UNTRUSTED,
        permission=registry.ToolPermission.ALLOW,
    )


class DeskClient:
    """A Signal Desk Turn as the notes ask for it, and nothing more."""

    def __init__(self, *, verdict: str = "single_source", cite: str | None = None) -> None:
        self.step = 0
        #: The tool names offered on each call, in order. The planning round's
        #: entry is the one that matters: the note tells the model to call the
        #: market read, and a round that does not offer it makes that
        #: instruction impossible to obey.
        self.offered: list[list[str]] = []
        self.verdict = verdict
        # Which evidence the verifier names. ``None`` means the market row it
        # actually read; a string is an id nobody holds, which is how a claim is
        # driven to ``unsupported`` without touching policy.
        self.cite = cite

    async def complete(self, request, spend=None):
        self.step += 1
        self.offered.append([tool.name for tool in request.tools])
        if self.step == 1:
            return completion(
                calls=(
                    call("plan-event", "web_search", query="FPT sự kiện tháng 8/2026"),
                    call("plan-company", "web_search", query="FPT ngành công nghệ 2026"),
                    call("plan-counter", "web_search", query="FPT rủi ro phản biện 2026"),
                    call("plan-market", "get_market_data", symbol="FPT"),
                )
            )
        if self.step == 2:
            return completion(
                text="Tôi đang đọc công bố gốc.",
                calls=(call("fetch-issuer", "fetch_url", url="https://issuer.example/report"),),
            )
        if self.step == 3:
            return completion(text=self._draft("price", "FPT đóng cửa ở 71.400 đồng."))
        if self.step == 4:
            return completion(
                text="Tôi đang kiểm tra số liệu phản bác.",
                calls=(call("fetch-audit", "fetch_url", url="https://audit.example/story"),),
            )
        if self.step == 5:
            return completion(text=self._draft("price", "FPT đóng cửa ở 71.400 đồng."))
        clean = json.loads(str(request.messages[-1].content))
        research_id = _first_claim_id(clean["research_claims"])
        market_id = self.cite or next(
            item["evidenceId"]
            for item in clean["evidence"]
            if item["publisher"] == "KB Securities"
        )
        return completion(
            text=json.dumps(
                {
                    "claims": [
                        {
                            "claim_id": research_id,
                            "verdict": self.verdict,
                            "supporting_evidence_ids": [market_id],
                            "contradicting_evidence_ids": [],
                            "invalidation_text": "Sai nếu nguồn khác công bố mức đóng cửa khác.",
                        }
                    ],
                    "gaps": [],
                },
                ensure_ascii=False,
            )
        )

    @staticmethod
    def _draft(claim_id: str, text: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "claim_id": claim_id,
                        "text": text,
                        "kind": "fact",
                        "material": True,
                        "candidate_evidence_ids": [],
                        "unit": "đồng",
                        "currency": "VND",
                    }
                ],
                "gaps": [],
                "assumptions": ["Số liệu từ feed công ty chứng khoán."],
                "invalidations": [],
                "question": None,
            },
            ensure_ascii=False,
        )


async def desk_run(**client_kwargs):
    from src.agent.toolsets import SIGNAL_DESK_TOOLSETS

    registry.register(market_entry())
    clear_memo()
    client = DeskClient(**client_kwargs)
    outcome = await AgentLoop(
        client=client,
        config=config(),
        lane=DEEP,
        toolsets=SIGNAL_DESK_TOOLSETS,
        clock=lambda: NOW,
    ).run(request())
    return outcome, client


async def desk_outcome(**client_kwargs):
    outcome, _ = await desk_run(**client_kwargs)
    return outcome


@pytest.mark.asyncio
async def test_the_planning_round_offers_the_market_read_it_asks_for():
    """The note and the offered surface have to agree, not just the note and the gate.

    The planning round is deliberately narrowed — planning is for looking, so a
    page fetch or a memory write does not belong in it. But the Signal Desk note
    asks for a market read in that same batch, and a narrowing that dropped it
    made the instruction impossible to obey: the model returned three searches,
    which is all it was able to return, and the gate then refused the Turn for
    not producing a fourth call nobody had offered it.
    """
    _outcome, client = await desk_run()

    # Still narrowed, and now narrowed to what the note actually asks for.
    assert set(client.offered[0]) == {"web_search", "get_market_data"}


@pytest.mark.asyncio
async def test_a_deep_turn_with_no_market_surface_plans_on_searches_alone():
    """The other half of the same rule: no market read offered, none demanded."""
    from src.agent.toolsets import CHAT_TOOLSETS

    clear_memo()
    client = PipelineClient()
    await AgentLoop(
        client=client,
        config=config(),
        lane=DEEP,
        toolsets=CHAT_TOOLSETS,
        clock=lambda: NOW,
    ).run(request())

    assert set(client.offered[0]) == {"web_search"}


@pytest.mark.asyncio
async def test_a_signal_desk_turn_leaves_a_chart_built_from_the_call_it_made():
    """The whole path, and the property that matters at the end of it.

    Nothing in the model's script carries a price. The claim states one, the
    verifier admits it, and the chart is assembled by the host from the rows the
    tool returned — so every number below can be traced to the call and to
    nothing the model wrote.
    """
    outcome = await desk_outcome()

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.claim_ledger["claims"][0]["verdict"] == "single_source"
    assert outcome.visual is not None
    assert [item["chart_spec"]["chartType"] for item in outcome.visual["assemblies"]] == [
        "Candlestick Chart",
        "Bar Chart",
    ]
    drawn = outcome.visual["assemblies"][0]["data"]["values"]
    assert [row["Đóng"] for row in drawn] == [71_400, 71_900]
    assert outcome.visual["sourceCallIds"] == ["plan-market"]
    assert outcome.visual["evidenceIds"][0] in {
        item["evidenceId"] for item in outcome.claim_ledger["evidence"]
    }


@pytest.mark.asyncio
async def test_a_ledger_that_refuses_the_figures_leaves_no_chart():
    """The gate, from the other side: the answer survives, the chart does not.

    The verifier names evidence nobody holds, so the claim recomputes to
    ``unsupported`` — and a chart of figures the answer was not allowed to state
    is exactly what must not reach the pane. The prose survives and says why.
    """
    outcome = await desk_outcome(cite="ev_nobody_holds_this")

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.answer
    assert outcome.claim_ledger["claims"][0]["verdict"] == "unsupported"
    assert outcome.visual is None


@pytest.mark.asyncio
async def test_a_label_policy_corrects_still_earns_the_chart_it_evidenced():
    """A wrong label is not missing evidence, and the two must not be conflated.

    ``verified`` on a market-only claim is refused and recomputed to
    ``single_source`` — which is the verdict the figures always deserved. The
    chart follows the recomputed verdict, because that is the one the answer is
    rendered from; withholding it here would punish the reader for a label the
    host had already corrected.
    """
    outcome = await desk_outcome(verdict="verified")

    assert outcome.claim_ledger["claims"][0]["verdict"] == "single_source"
    assert outcome.visual is not None


class ProsePlannerClient(PipelineClient):
    """The planning pass answers in prose before it plans.

    Measured on 2026-09-27: the kiro route ignores ``tool_choice="required"``
    (and a named function), so a model that decides to answer at once returns
    text on the planning pass and nothing the gate can dispatch.
    """

    def __init__(self, *, prose_replies: int = 1) -> None:
        super().__init__()
        self.prose_left = prose_replies

    async def complete(self, request, spend=None):
        if self.prose_left:
            self.prose_left -= 1
            self.requests.append(request)
            return completion(text="HPG đang giao dịch quanh 28.000 đồng.")
        return await super().complete(request, spend)


def _notes(request) -> str:
    return "\n".join(str(message.content) for message in request.messages)


@pytest.mark.asyncio
async def test_a_planning_pass_answered_in_prose_is_asked_once_more_for_the_batch():
    client = ProsePlannerClient()

    outcome = await AgentLoop(client=client, config=config(), lane=DEEP, clock=lambda: NOW).run(request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.claim_ledger["verifierOutcome"] != "verifier_failed"
    assert "planner_returned_no_search_batch" not in outcome.answer
    # The prose is not the answer, and the retry says why it was not taken.
    assert "28.000" not in outcome.answer
    assert "PLANNING PASS" in _notes(client.requests[1])
    assert "no tool call" in _notes(client.requests[1])


@pytest.mark.asyncio
async def test_a_planning_pass_that_answers_in_prose_twice_still_fails_closed():
    client = ProsePlannerClient(prose_replies=2)

    outcome = await AgentLoop(client=client, config=config(), lane=DEEP, clock=lambda: NOW).run(request())

    assert outcome.claim_ledger["verifierOutcome"] == "verifier_failed"
    assert "planner_returned_no_search_batch" in outcome.answer
    assert len(client.requests) == 2
