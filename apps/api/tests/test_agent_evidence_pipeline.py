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

    async def complete(self, request, spend=None):
        self.requests.append(request)
        self.spends.append(spend)
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
        text = (
            "not-json"
            if self.invalid_verifier
            else json.dumps(
                {
                    "claims": [
                        {
                            "claim_id": "profit",
                            "verdict": "conflicting",
                            "supporting_evidence_ids": [evidence["Issuer IR"]],
                            "contradicting_evidence_ids": [evidence["Audit News"]],
                            "invalidation_text": "Sai nếu số kiểm toán thay thế số công bố.",
                        },
                        {
                            "claim_id": "adjusted",
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
    assert "planner_did_not_produce_four_independent_searches" in outcome.answer


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
