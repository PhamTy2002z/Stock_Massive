"""What a Turn is allowed to say about its own work (``docs/adr/0020``).

Two claims run through every test here, and they pull in opposite directions:
the **open web describes itself** — the sentence searched for, the pages found —
and **every other lane still does not**. A change that widened the second is the
failure this file exists to catch, so the store-lane assertions are written as
absences rather than as a shape.
"""

from __future__ import annotations

import json
from datetime import date
from types import MappingProxyType

import pytest

from src.agent.context import ContextBudget
from src.agent.events import (
    MAX_TRAIL_STEPS,
    Activity,
    EventType,
    TurnPublisher,
    append_step,
)
from src.agent.loop import AgentLoop, TurnRequest, TurnStatus
from src.agent.context import TranscriptToolCall
from src.agent.progress import (
    MAX_SNIPPET_CHARS,
    MAX_SOURCES,
    ProgressSource,
    block_source_ids,
    domain_of,
    found_detail,
    merge_sources,
    queries_of,
    searching_detail,
    sources_by_call,
    sources_of,
)
from src.agent.prompt import MarketState, RuntimeContext
from src.agent import suggestions
from src.agent.tools.catalog import ToolCatalog, ToolContext, ToolDataAccess, ToolSpec
from src.core.llm import (
    BudgetLane,
    BudgetRefusal,
    Completion,
    LLMError,
    OwnerType,
    SpendRequest,
    ToolCall,
    Usage,
    Workload,
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
TURN = "11111111-1111-1111-1111-111111111111"


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
    def __init__(self, script=()) -> None:
        self.script = list(script)
        self.requests = []

    async def complete(self, request, spend=None):
        self.requests.append((request, spend))
        item = self.script.pop(0) if self.script else Completion(
            model=request.model, text="Kết luận cuối cùng."
        )
        if isinstance(item, BaseException):
            raise item
        return item


def answer(text: str = "Kết luận cuối cùng.") -> Completion:
    return Completion(
        model=SESSION_MODEL, text=text, usage=Usage(input_tokens=10, output_tokens=5)
    )


def wants_web(query: str = "chủ tịch Masan Group") -> Completion:
    return Completion(
        model=SESSION_MODEL,
        tool_calls=(
            ToolCall(id="call_0", name="web_search", arguments={"query": query}, output_index=0),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def wants_store() -> Completion:
    return Completion(
        model=SESSION_MODEL,
        tool_calls=(
            ToolCall(
                id="call_0",
                name="get_price_series",
                arguments={"symbol": "MSN"},
                output_index=0,
            ),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


async def _web_results(_context: ToolContext, arguments: dict) -> dict:
    return {
        "query": arguments["query"],
        "results": [
            {
                "title": "Ban lãnh đạo của Công ty CP Tập đoàn Masan",
                "url": "https://www.masangroup.com/leadership",
                "source": "www.masangroup.com",
                "claim_class": "external_claim",
            },
            {
                "title": "Masan Group chairman",
                "url": "https://e.vnexpress.net/news/masan",
                "source": "e.vnexpress.net",
                "claim_class": "external_claim",
            },
        ],
        "reason": None,
    }


async def _store_read(_context: ToolContext, arguments: dict) -> dict:
    return {"symbol": arguments.get("symbol"), "close": 95.4}


def catalog() -> ToolCatalog:
    return ToolCatalog(
        (
            ToolSpec(
                name="web_search",
                description="Search the open web.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "additionalProperties": False,
                },
                callable=_web_results,
                data_access=ToolDataAccess.EXTERNAL,
            ),
            ToolSpec(
                name="get_price_series",
                description="Read stored prices.",
                parameters={
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "additionalProperties": False,
                },
                callable=_store_read,
            ),
        ),
        trace_writer=lambda _trace: None,
    )


def turn_request(**overrides) -> TurnRequest:
    base = dict(
        thread_id=TURN,
        request_message_id=42,
        user_id=7,
        user_text="Chủ tịch của Masan hiện tại là ai?",
        runtime=RuntimeContext(
            user_id=7,
            trading_day=date(2026, 8, 14),
            today=date(2026, 8, 16),
            market_state=MarketState.POST_CLOSE,
            active_symbol="MSN",
        ),
    )
    base.update(overrides)
    return TurnRequest(**base)


def loop(client, **overrides) -> AgentLoop:
    return AgentLoop(
        client=client,
        catalog=catalog(),
        config=config(),
        budget=ContextBudget(max_tokens=30_000),
        **overrides,
    )


def activities(publisher: TurnPublisher, events: list) -> list[dict]:
    return [
        dict(event.data) for event in events if event.type is EventType.ACTIVITY
    ]


class RecordingPublisher(TurnPublisher):
    """The real publisher, with every event it emitted kept in order."""

    def __init__(self) -> None:
        super().__init__(TURN)
        self.events: list = []

    def publish(self, event_type, data=None):
        event = super().publish(event_type, data)
        self.events.append(event)
        return event


# --- the projection -------------------------------------------------------


def test_a_domain_is_the_host_without_its_www():
    assert domain_of("https://www.masangroup.com/leadership") == "masangroup.com"
    assert domain_of("https://e.vnexpress.net/a") == "e.vnexpress.net"
    assert domain_of("not a url") == ""


def test_queries_come_from_the_arguments_of_open_web_calls_only():
    calls = (
        ToolCall(id="a", name="web_search", arguments={"query": "một"}, output_index=0),
        ToolCall(id="b", name="fetch_url", arguments={"url": "https://x.vn/a"}, output_index=1),
        ToolCall(id="c", name="get_price_series", arguments={"symbol": "MSN"}, output_index=2),
        ToolCall(id="d", name="search_news", arguments={"symbol": "MSN"}, output_index=3),
    )

    # The store read and the news lane contribute nothing: one reads the store,
    # and the other's argument is a Universe symbol rather than a sentence.
    assert queries_of(calls) == ("một", "https://x.vn/a")


def test_a_repeated_query_is_listed_once():
    calls = tuple(
        ToolCall(id=str(index), name="web_search", arguments={"query": "một"}, output_index=index)
        for index in range(3)
    )

    assert queries_of(calls) == ("một",)


def test_sources_are_read_from_each_tools_own_shape():
    search = {"results": [{"title": "A", "url": "https://a.vn/1"}]}
    fetched = {
        "url": "https://b.vn/2",
        "external_claim": {"title": "B", "source_url": "https://b.vn/2"},
    }

    assert sources_of("web_search", search)[0].domain == "a.vn"
    assert sources_of("fetch_url", fetched)[0].title == "B"
    # The store lane discloses nothing, whatever its result happens to contain.
    assert sources_of("get_price_series", search) == ()


def test_a_source_carries_its_excerpt_and_timestamps_when_the_result_offered_them():
    # The drawer under an answer shows what the page claims and when: excerpt and
    # timestamps ride the wire when present, and are simply absent when not —
    # a client reads presence, never an empty string.
    search = {
        "results": [
            {
                "title": "A",
                "url": "https://a.vn/1",
                "snippet": "  Ban lãnh đạo gồm năm thành viên.  ",
                "published_at": "2026-06-19",
                "retrieved_at": "2026-08-16T05:13:58+00:00",
            },
            {"title": "B", "url": "https://b.vn/2"},
        ]
    }

    rich, bare = sources_of("web_search", search)

    assert rich.snippet == "Ban lãnh đạo gồm năm thành viên."
    assert rich.as_wire()["published_at"] == "2026-06-19"
    assert rich.as_wire()["retrieved_at"] == "2026-08-16T05:13:58+00:00"
    assert set(bare.as_wire()) == {"title", "url", "domain"}


def test_a_snippet_is_capped_at_a_preview():
    long = "x" * (MAX_SNIPPET_CHARS + 50)
    search = {"results": [{"title": "A", "url": "https://a.vn/1", "snippet": long}]}

    (found,) = sources_of("web_search", search)

    assert len(found.snippet) == MAX_SNIPPET_CHARS


def test_a_fetched_page_discloses_when_it_was_retrieved():
    fetched = {
        "url": "https://b.vn/2",
        "external_claim": {
            "title": "B",
            "source_url": "https://b.vn/2",
            "retrieved_at": "2026-08-16T05:13:58+00:00",
        },
    }

    (found,) = sources_of("fetch_url", fetched)

    assert found.retrieved_at == "2026-08-16T05:13:58+00:00"
    assert found.snippet == ""


def test_a_malformed_result_costs_one_entry_and_never_the_turn():
    rows = {"results": ["not a mapping", {"title": "A"}, {"url": "https://a.vn/1"}]}

    found = sources_of("web_search", rows)

    # No URL means nothing to link to; a row with a URL and no title falls back
    # to the domain rather than rendering as a blank line.
    assert [source.title for source in found] == ["a.vn"]


def test_sources_merge_once_each_and_stay_bounded():
    first = (ProgressSource(title="A", url="https://a.vn/1", domain="a.vn"),)
    again = [
        ProgressSource(title="A again", url="https://a.vn/1", domain="a.vn"),
        ProgressSource(title="B", url="https://b.vn/2", domain="b.vn"),
    ]

    merged = merge_sources(first, again)

    assert [source.url for source in merged] == ["https://a.vn/1", "https://b.vn/2"]

    flood = [
        ProgressSource(title=str(n), url=f"https://x.vn/{n}", domain="x.vn")
        for n in range(MAX_SOURCES + 5)
    ]
    assert len(merge_sources((), flood)) == MAX_SOURCES


def test_a_detail_with_nothing_to_say_is_absent_rather_than_empty():
    # A client reads presence as "this lane discloses", so an empty object would
    # say the opposite of what it means.
    assert searching_detail(()) is None
    assert found_detail((), 0) is None


def test_the_result_count_is_what_was_read_not_what_is_listed():
    sources = tuple(
        ProgressSource(title=str(n), url=f"https://x.vn/{n}", domain="x.vn")
        for n in range(3)
    )

    detail = found_detail(sources, 15)

    assert detail is not None
    assert detail["result_count"] == 15
    assert len(detail["sources"]) == 3


# --- the trail ------------------------------------------------------------


def test_a_phase_that_merely_repeated_is_one_step():
    trail: list[dict] = []

    append_step(trail, {"phase": "analyzing"})
    append_step(trail, {"phase": "analyzing"})
    append_step(trail, {"phase": "searching", "detail": {"queries": ["một"]}})
    append_step(trail, {"phase": "searching", "detail": {"queries": ["hai"]}})

    assert [step["phase"] for step in trail] == ["analyzing", "searching", "searching"]
    assert trail[-1]["detail"]["queries"] == ["hai"]


def test_the_trail_is_bounded_however_chatty_the_turn_is():
    # It rides every snapshot, so its size cannot be a function of how many
    # activity events a Turn managed to emit.
    trail: list[dict] = []
    phases = ("searching", "reading_data", "analyzing")

    for index in range(MAX_TRAIL_STEPS * 3):
        append_step(trail, {"phase": phases[index % len(phases)]})

    assert len(trail) == MAX_TRAIL_STEPS


def test_a_snapshot_carries_the_whole_trail():
    publisher = TurnPublisher(TURN)
    publisher.activity(Activity.ANALYZING)
    publisher.activity(Activity.SEARCHING, {"queries": ["một"]})

    snapshot = publisher.subscribe().snapshot

    assert snapshot.data["progress"] == [
        {"phase": "analyzing"},
        {"phase": "searching", "detail": {"queries": ["một"]}},
    ]


def test_only_the_disclosing_tools_are_indexed_by_call():
    calls = [
        TranscriptToolCall(
            call_id="w1",
            name="web_search",
            arguments={"query": "một"},
            result={
                "results": [
                    {"title": "A", "url": "https://a.vn/x"},
                    {"title": "B", "url": "https://b.vn/y"},
                ]
            },
        ),
        TranscriptToolCall(
            call_id="s1",
            name="get_price_series",
            arguments={"symbol": "MSN"},
            result={"symbol": "MSN", "close": 95.4},
        ),
    ]

    index = sources_by_call(calls)

    assert index == {"w1": {0: "https://a.vn/x", 1: "https://b.vn/y"}}


def test_a_block_names_only_pages_the_turn_itself_listed():
    index = {
        "w1": {0: "https://a.vn/x", 1: "https://gone.vn/z"},
        "w2": {0: "https://a.vn/x"},
    }
    listed = ("https://a.vn/x", "https://b.vn/y")

    found = block_source_ids(
        [("w1", "results.1.title"), ("w2", "results.0.title"), ("unknown", "x")],
        index,
        listed,
    )

    # The page the trail never showed is dropped even though the path named it,
    # the page two calls returned is named once, and a call id from nowhere
    # costs the chips nothing: this is display metadata, so an id that resolves
    # to nothing is not a failure.
    assert found == ("https://a.vn/x",)


def test_a_cited_row_names_that_row_and_not_the_whole_search():
    index = {
        "w1": {0: "https://a.vn/x", 1: "https://b.vn/y", 2: "https://c.vn/z"}
    }
    listed = tuple(index["w1"].values())

    one = block_source_ids([("w1", "results.1.title")], index, listed)
    whole = block_source_ids([("w1", "query")], index, listed)

    # A sentence citing one result rests on one page; a reference to the call as
    # a whole rests on everything it came back with.
    assert one == ("https://b.vn/y",)
    assert whole == listed


def test_a_result_row_with_no_url_does_not_shift_the_rows_after_it():
    # The failure this pins: a search result the provider returned without a URL
    # is dropped from the trail, and a list of survivors would make every later
    # citation name the page one row further down.
    calls = [
        TranscriptToolCall(
            call_id="w1",
            name="web_search",
            arguments={"query": "một"},
            result={
                "results": [
                    {"title": "A", "url": "https://a.vn/x"},
                    {"title": "no link", "url": ""},
                    {"title": "C", "url": "https://c.vn/z"},
                ]
            },
        )
    ]
    index = sources_by_call(calls)
    listed = ("https://a.vn/x", "https://c.vn/z")

    assert index == {"w1": {0: "https://a.vn/x", 2: "https://c.vn/z"}}
    assert block_source_ids([("w1", "results.2.title")], index, listed) == (
        "https://c.vn/z",
    )
    # And the row that had no page names none, rather than borrowing a neighbour.
    assert block_source_ids([("w1", "results.1.title")], index, listed) == ()
    # A cited row past the end is the same case, and is not the whole search.
    assert block_source_ids([("w1", "results.9.title")], index, listed) == ()


# --- the loop -------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_open_web_round_publishes_its_queries_then_what_it_found():
    publisher = RecordingPublisher()
    client = FakeClient([wants_web(), answer()])

    await loop(client, publisher=publisher).run(turn_request())

    trail = [dict(event.data) for event in publisher.events if event.type is EventType.ACTIVITY]
    searching = next(step for step in trail if step["phase"] == "searching")
    found = next(step for step in trail if step["phase"] == "found_sources")

    assert searching["detail"]["queries"] == ["chủ tịch Masan Group"]
    assert found["detail"]["result_count"] == 2
    assert [source["domain"] for source in found["detail"]["sources"]] == [
        "masangroup.com",
        "e.vnexpress.net",
    ]


@pytest.mark.asyncio
async def test_a_block_carries_the_pages_its_own_evidence_stood_on():
    publisher = RecordingPublisher()
    client = FakeClient(
        [
            wants_web(),
            answer(
                "Chủ tịch hiện tại được trang chủ công ty nêu tên "
                "[ev:call_0#results.0.title]."
            ),
        ]
    )

    outcome = await loop(client, publisher=publisher).run(turn_request())

    (block,) = outcome.blocks
    assert block.source_ids == ("https://www.masangroup.com/leadership",)
    # The same list reaches the browser, so the chip under the sentence and the
    # source list in the trail cannot disagree about which page it was.
    released = [
        dict(event.data)["block"]
        for event in publisher.events
        if event.type is EventType.CONTENT_BLOCK
    ]
    assert released[0]["source_ids"] == ["https://www.masangroup.com/leadership"]


@pytest.mark.asyncio
async def test_a_block_resting_on_the_store_names_no_pages():
    client = FakeClient([wants_store(), answer("Phiên gần nhất đã đóng cửa.")])

    outcome = await loop(client).run(turn_request())

    (block,) = outcome.blocks
    assert block.source_ids == ()


@pytest.mark.asyncio
async def test_a_store_round_says_a_phase_and_nothing_else():
    publisher = RecordingPublisher()
    client = FakeClient([wants_store(), answer()])

    await loop(client, publisher=publisher).run(turn_request())

    trail = [dict(event.data) for event in publisher.events if event.type is EventType.ACTIVITY]

    assert {step["phase"] for step in trail} == {"analyzing", "reading_data"}
    assert all("detail" not in step for step in trail)
    # No tool name, no symbol, no field: ADR-0013's rule for every lane that
    # reads the store, which ADR-0020 deliberately did not touch.
    encoded = json.dumps(trail, ensure_ascii=False)
    assert "get_price_series" not in encoded
    assert "MSN" not in encoded


@pytest.mark.asyncio
async def test_the_trail_is_carried_on_the_outcome_and_the_checkpoint():
    publisher = RecordingPublisher()
    drafts: list = []
    client = FakeClient([wants_web(), answer()])

    outcome = await loop(
        client, publisher=publisher, checkpoint=drafts.append
    ).run(turn_request())

    assert [step["phase"] for step in outcome.progress] == [
        "analyzing",
        "searching",
        "found_sources",
        "analyzing",
    ]
    assert drafts[-1].progress == outcome.progress


# --- follow-up suggestions ------------------------------------------------


def suggestion_completion(*questions: str) -> Completion:
    return Completion(
        model=BATCH_MODEL,
        text=json.dumps({"suggestions": list(questions)}),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


@pytest.mark.asyncio
async def test_suggestions_are_off_unless_the_deployment_asks_for_them():
    client = FakeClient([answer()])

    outcome = await loop(client).run(turn_request())

    assert outcome.suggestions == ()
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_an_answered_turn_asks_the_cheap_model_for_follow_ups():
    client = FakeClient([answer(), suggestion_completion("Chủ tịch Masan là ai?", "MSN quý gần nhất?")])

    outcome = await loop(client, suggest=True).run(turn_request())

    assert outcome.suggestions == ("Chủ tịch Masan là ai?", "MSN quý gần nhất?")
    request, spend = client.requests[-1]
    # The cheap model, the batch workload, and charged to the Turn that earned
    # them (``docs/adr/0014``).
    assert request.model == BATCH_MODEL
    assert spend.workload is Workload.BATCH
    assert spend.lane is BudgetLane.TURN
    assert spend.owner.type is OwnerType.TURN_REQUEST_MESSAGE
    assert spend.owner.id == "42"


@pytest.mark.asyncio
async def test_a_turn_that_ended_badly_is_offered_no_follow_ups():
    # Offering "what else would you like to know" under an answer that could not
    # be given reads as the system not having noticed.
    client = FakeClient([LLMError("route down")])

    outcome = await loop(client, suggest=True).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.suggestions == ()
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_a_refused_budget_costs_the_panel_and_nothing_else():
    client = FakeClient(
        [answer(), BudgetRefusal(reason="user_daily_turns", message="No allowance left.")]
    )

    outcome = await loop(client, suggest=True).run(turn_request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.blocks
    assert outcome.suggestions == ()


@pytest.mark.asyncio
async def test_a_malformed_answer_yields_no_suggestions():
    client = FakeClient([answer(), Completion(model=BATCH_MODEL, text="not json at all")])

    outcome = await loop(client, suggest=True).run(turn_request())

    assert outcome.suggestions == ()


def test_parsing_keeps_only_what_is_usable():
    payload = json.dumps(
        {
            "suggestions": [
                "  Câu   hỏi một  ",
                "Câu hỏi một",
                "",
                "x" * (suggestions.MAX_SUGGESTION_CHARS + 1),
                42,
                "Câu hỏi hai",
            ]
        }
    )

    assert suggestions.parse(payload) == ("Câu hỏi một", "Câu hỏi hai")


def test_parsing_never_raises_on_a_shape_it_did_not_ask_for():
    for text in (None, "", "[]", "{}", '{"suggestions": "một"}', '{"suggestions": null}'):
        assert suggestions.parse(text) == ()


def test_at_most_two_are_kept():
    payload = json.dumps({"suggestions": [f"Câu hỏi {n}" for n in range(12)]})

    assert len(suggestions.parse(payload)) == suggestions.MAX_SUGGESTIONS


def test_the_request_asks_for_a_strict_schema_and_no_tools():
    request = suggestions.build_request(
        model=BATCH_MODEL, user_text="Chủ tịch Masan?", answer_text="Ông Nguyễn Đăng Quang."
    )

    assert request.tools == ()
    assert request.tool_choice == "none"
    assert request.response_format is not None
    assert request.response_format.strict is True
    assert request.stream is False


def test_the_spend_names_the_worst_case_on_the_batch_workload():
    request = suggestions.build_request(
        model=BATCH_MODEL, user_text="a", answer_text="b"
    )

    spend = suggestions.spend_for(
        request,
        owner=None,
        lane=BudgetLane.TURN,
        estimated_input_tokens=120,
    )

    assert isinstance(spend, SpendRequest)
    assert spend.workload is Workload.BATCH
    assert spend.input_tokens == 120
    assert spend.output_tokens == suggestions.MAX_OUTPUT_TOKENS
