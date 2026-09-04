"""The rules that keep a model-chosen URL from reaching anything private."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

import pytest

from src.agent.registry import ToolContext
from src.agent.tools import web
from src.core.config import Settings
from src.core.web_lane import WebRead, WebUnavailable

CONTEXT = ToolContext(user_id=11)

PAGE_HTML = (
    "<html><head><title>Rates hold</title></head>"
    "<body><script>alert(1)</script><p>The rate was unchanged.</p></body></html>"
)


def resolver_for(*addresses: str):
    """A DNS answer of exactly these addresses, whatever was asked."""

    def resolve(_host: str, _port: Any, **_kwargs: Any) -> Sequence[tuple[Any, ...]]:
        return [(2, 1, 6, "", (address, 80)) for address in addresses]

    return resolve


class DirectLane:
    """The web lane with its cache, allowance and single-flight taken out."""

    def read(self, _kind: str, _key: str, fetch) -> WebRead:
        return WebRead(fetch(), 0.0, 0.0, False)


class ClosedLane:
    """A lane that can serve nothing, which is what a missing Redis looks like."""

    def read(self, _kind: str, _key: str, _fetch) -> WebRead:
        raise WebUnavailable("no Redis is configured, so the web lane is disabled")


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "web_tools_enabled": True,
        "tavily_api_key": "test-key",
        "web_fetch_max_bytes": 2_048,
        "web_domain_denylist": "evil.example, internal.corp",
    }
    base.update(overrides)
    return Settings(**base)


def download_returning(
    status: int, headers: Mapping[str, str], body: bytes, *, seen: list[tuple[Any, ...]]
):
    def download(url: str, max_bytes: int, timeout: float) -> tuple[int, Mapping[str, str], bytes]:
        seen.append((url, max_bytes, timeout))
        return status, headers, body

    return download


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:5432/",
        "http://[::1]/",
        "http://10.0.0.5/",
        "http://192.168.33.101:5432/",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/",
    ],
)
def test_an_address_that_is_not_publicly_routable_is_refused(url):
    with pytest.raises(ValueError, match="non-public address"):
        web.validate_public_url(url, resolver=resolver_for("127.0.0.1"))


def test_a_public_name_whose_dns_answer_is_private_is_refused():
    with pytest.raises(ValueError, match="non-public address"):
        web.validate_public_url(
            "https://rebind.example/page", resolver=resolver_for("10.1.2.3")
        )


def test_every_address_in_the_answer_must_be_public():
    with pytest.raises(ValueError, match="non-public address"):
        web.validate_public_url(
            "https://mixed.example/", resolver=resolver_for("93.184.216.34", "127.0.0.1")
        )


def test_a_scheme_that_is_not_http_is_refused():
    for url in ("ftp://example.com/x", "file:///etc/passwd", "gopher://example.com"):
        with pytest.raises(ValueError, match="only http and https"):
            web.validate_public_url(url, resolver=resolver_for("93.184.216.34"))


def test_credentials_in_the_url_are_refused():
    with pytest.raises(ValueError, match="must not contain credentials"):
        web.validate_public_url(
            "https://user:secret@example.com/", resolver=resolver_for("93.184.216.34")
        )


def test_a_denied_domain_and_its_subdomains_are_refused():
    denylist = ("evil.example", "internal.corp")
    resolver = resolver_for("93.184.216.34")

    for url in (
        "https://evil.example/page",
        "https://deep.sub.evil.example/page",
        "https://INTERNAL.CORP./page",
    ):
        with pytest.raises(ValueError, match="denied by configuration"):
            web.validate_public_url(url, denylist=denylist, resolver=resolver)


def test_a_public_url_is_normalized_and_kept():
    normalized = web.validate_public_url(
        "HTTPS://Example.COM?q=1", resolver=resolver_for("93.184.216.34")
    )

    assert normalized == "https://example.com/?q=1"


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, size: int) -> bytes:
        chunk, self._body = self._body[:size], self._body[size:]
        return chunk


def test_a_declared_length_over_the_cap_is_refused_before_reading():
    response = _Response(b"x" * 10)

    with pytest.raises(ValueError, match="WEB_FETCH_MAX_BYTES"):
        web.capped_body(response, {"content-length": "100000"}, 1_000)


def test_a_body_that_grows_past_the_cap_is_refused_while_reading():
    response = _Response(b"x" * 5_000)

    with pytest.raises(ValueError, match="WEB_FETCH_MAX_BYTES"):
        web.capped_body(response, {}, 1_000)


def test_a_body_inside_the_cap_is_returned_whole():
    assert web.capped_body(_Response(b"x" * 900), {}, 1_000) == b"x" * 900


@pytest.mark.asyncio
async def test_a_page_read_returns_visible_text_and_the_configured_byte_cap():
    seen: list[tuple[Any, ...]] = []
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(
            200, {"content-type": "text/html; charset=utf-8"}, PAGE_HTML.encode(), seen=seen
        ),
        resolver=resolver_for("93.184.216.34"),
    )

    result = await tools.fetch_url(CONTEXT, {"url": "https://news.example/rates"})

    assert result["title"] == "Rates hold"
    assert "The rate was unchanged." in result["content"]
    assert "alert(1)" not in result["content"]
    assert result["source"] == "news.example"
    assert seen[0][1] == 2_048


@pytest.mark.asyncio
async def test_a_page_read_carries_typed_source_and_html_publication_metadata():
    page = (
        '<html><head><title>Official release</title>'
        '<meta property="og:site_name" content="State Securities Commission">'
        '<meta property="article:published_time" content="2026-08-20T09:30:00+07:00">'
        '</head><body><p>Công bố chính thức.</p></body></html>'
    ).encode()
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(200, {"content-type": "text/html"}, page, seen=[]),
        resolver=resolver_for("93.184.216.34"),
    )

    result = await tools.fetch_url(CONTEXT, {"url": "https://ssc.gov.vn/release?utm_source=x"})

    assert result["canonical_url"] == "https://ssc.gov.vn/release"
    assert result["publisher"] == "State Securities Commission"
    assert result["source_class"] == "regulator"
    assert result["source_tier"] == "primary"
    assert result["tos_risk"] == "low"
    assert result["durable_evidence"] is True
    assert result["publication"] == {
        "publishedAt": "2026-08-20T09:30:00+07:00",
        "publicationMethod": "html_meta",
        "publicationConfidence": "high",
        "publicationPrecision": "instant",
    }


@pytest.mark.asyncio
async def test_json_ld_publication_is_extracted_but_script_is_not_visible_evidence():
    page = (
        '<html><head><script type="application/ld+json">'
        '{"@type":"NewsArticle","datePublished":"2026-08-19"}'
        '</script></head><body><p>Nội dung bài viết.</p></body></html>'
    ).encode()
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(200, {"content-type": "text/html"}, page, seen=[]),
        resolver=resolver_for("93.184.216.34"),
    )

    result = await tools.fetch_url(CONTEXT, {"url": "https://news.example/story"})

    assert "datePublished" not in result["content"]
    assert result["publication"]["publishedAt"] == "2026-08-19T00:00:00+07:00"
    assert result["publication"]["publicationMethod"] == "json_ld"


@pytest.mark.asyncio
async def test_a_redirect_is_revalidated_and_cannot_reach_a_private_address():
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(
            302, {"location": "http://169.254.169.254/latest/"}, b"", seen=[]
        ),
        resolver=resolver_for("93.184.216.34"),
    )

    with pytest.raises(ValueError, match="non-public address"):
        await tools.fetch_url(CONTEXT, {"url": "https://news.example/rates"})


@pytest.mark.asyncio
async def test_a_redirect_loop_stops_at_the_limit():
    hops: list[tuple[Any, ...]] = []
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(
            302, {"location": "https://news.example/next"}, b"", seen=hops
        ),
        resolver=resolver_for("93.184.216.34"),
    )

    with pytest.raises(ValueError, match="redirect limit"):
        await tools.fetch_url(CONTEXT, {"url": "https://news.example/rates"})

    assert len(hops) == web.MAX_REDIRECTS + 1


@pytest.mark.asyncio
async def test_a_denied_domain_is_refused_before_any_request_is_made():
    seen: list[tuple[Any, ...]] = []
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(200, {}, b"", seen=seen),
        resolver=resolver_for("93.184.216.34"),
    )

    with pytest.raises(ValueError, match="denied by configuration"):
        await tools.fetch_url(CONTEXT, {"url": "https://evil.example/page"})

    assert seen == []


@pytest.mark.asyncio
async def test_a_page_read_with_no_lane_states_the_reason_instead_of_failing():
    tools = web.WebTools(
        settings=settings(), lane=ClosedLane(), resolver=resolver_for("93.184.216.34")
    )

    result = await tools.fetch_url(CONTEXT, {"url": "https://news.example/rates"})

    assert result["reason"] == "web_unavailable"


@pytest.mark.asyncio
async def test_search_results_are_capped_stripped_and_attributed():
    raw = [
        {
            "title": f"<b>Result {index}</b>",
            "url": f"https://source{index}.example/a",
            "content": "y" * 5_000,
            "published_date": "2026-08-20",
        }
        for index in range(web.MAX_RESULTS + 3)
    ]
    tools = web.WebTools(
        settings=settings(), lane=DirectLane(), search=lambda _query, _recency: raw
    )

    result = await tools.web_search(CONTEXT, {"query": "lãi suất"})

    assert len(result["results"]) == web.MAX_RESULTS
    first = result["results"][0]
    assert first["title"] == "Result 0"
    assert len(first["snippet"]) == web.MAX_SNIPPET_CHARS
    assert first["source"] == "source0.example"
    assert result["reason"] is None


@pytest.mark.asyncio
async def test_a_blank_query_is_refused():
    tools = web.WebTools(settings=settings(), lane=DirectLane(), search=lambda *_: [])

    with pytest.raises(ValueError, match="must not be blank"):
        await tools.web_search(CONTEXT, {"query": "   "})


def test_search_is_offered_only_with_the_flag_and_the_key():
    entries = {entry.name: entry for entry in web.WebTools(settings=settings()).entries()}

    assert entries["web_search"].check_fn() is True
    assert entries["fetch_url"].check_fn() is True

    off = {
        entry.name: entry
        for entry in web.WebTools(settings=settings(web_tools_enabled=False)).entries()
    }
    assert off["web_search"].check_fn() is False
    assert off["fetch_url"].check_fn() is False

    keyless = {
        entry.name: entry
        for entry in web.WebTools(settings=settings(tavily_api_key="")).entries()
    }
    assert keyless["web_search"].check_fn() is False
    assert keyless["fetch_url"].check_fn() is True


def test_the_web_tools_declare_what_their_results_may_weigh():
    entries = {entry.name: entry for entry in web.WebTools(settings=settings()).entries()}

    assert entries["web_search"].max_result_size_chars == web.SEARCH_RESULT_CHARS
    assert entries["fetch_url"].max_result_size_chars == web.PAGE_RESULT_CHARS
    assert {entry.toolset for entry in entries.values()} == {"web"}


# -- what a search result now carries --------------------------------------


@pytest.mark.asyncio
async def test_every_result_carries_the_position_the_provider_returned_it_in():
    """Five snippets with no order at all give a model nothing to prefer."""
    raw = [
        {"title": f"R{index}", "url": f"https://s{index}.example/a", "content": "x"}
        for index in range(web.MAX_RESULTS)
    ]
    tools = web.WebTools(
        settings=settings(), lane=DirectLane(), search=lambda _query, _recency: raw
    )

    result = await tools.web_search(CONTEXT, {"query": "vn-index"})

    assert [item["rank"] for item in result["results"]] == [1, 2, 3, 4, 5]
    assert [item["url"] for item in result["results"]] == [
        f"https://s{index}.example/a" for index in range(web.MAX_RESULTS)
    ]


@pytest.mark.asyncio
async def test_the_providers_score_rides_along_under_a_name_that_says_what_it_is():
    raw = [
        {"title": "A", "url": "https://a.example/x", "content": "x", "score": 0.8231},
        {"title": "B", "url": "https://b.example/x", "content": "x"},
    ]
    tools = web.WebTools(
        settings=settings(), lane=DirectLane(), search=lambda _query, _recency: raw
    )

    results = (await tools.web_search(CONTEXT, {"query": "vn-index"}))["results"]

    assert results[0]["relevance"] == 0.8231
    # Absent rather than invented. A provider that stops sending the field must
    # not look like a provider reporting a score of zero.
    assert results[1]["relevance"] is None


@pytest.mark.asyncio
async def test_the_publication_date_still_comes_through_untouched():
    raw = [{"title": "A", "url": "https://a.example/x", "content": "x", "published_date": "2026-08-20"}]
    tools = web.WebTools(
        settings=settings(), lane=DirectLane(), search=lambda _query, _recency: raw
    )

    results = (await tools.web_search(CONTEXT, {"query": "q"}))["results"]

    assert results[0]["published_at"] == "2026-08-20"


@pytest.mark.asyncio
async def test_search_result_is_typed_as_discovery_only_even_for_a_primary_domain():
    raw = [
        {
            "title": "A",
            "url": "https://hnx.vn/report?utm_campaign=x",
            "content": "snippet",
            "published_date": "2026-08-20",
        }
    ]
    tools = web.WebTools(
        settings=settings(), lane=DirectLane(), search=lambda _query, _recency: raw
    )

    item = (await tools.web_search(CONTEXT, {"query": "q"}))["results"][0]

    assert item["canonical_url"] == "https://hnx.vn/report"
    assert item["source_class"] == "exchange"
    assert item["source_tier"] == "primary"
    assert item["evidence_tier"] == "snippet"
    assert item["durable_evidence"] is False
    assert item["material_min_publishers"] is None
    assert item["publication"]["publicationMethod"] == "provider"


# -- reading a page with a question in hand --------------------------------


def long_page(needle: str) -> str:
    """A page whose answer sits far past where the old cut fell."""
    filler = "Tin thị trường chung không liên quan. " * 900
    assert len(filler) > web.MAX_PAGE_TEXT_CHARS
    return filler + needle + " " + filler


def test_a_passage_past_the_old_cut_is_still_found():
    body = long_page("Lãi suất điều hành giữ nguyên ở mức 4,5 phần trăm.")

    passages = web.select_passages(body, "lãi suất điều hành", web.MAX_PAGE_TEXT_CHARS)

    assert any("4,5 phần trăm" in passage for passage in passages)
    assert body.index("4,5 phần trăm") > web.MAX_PAGE_TEXT_CHARS


def test_every_passage_returned_is_verbatim_page_text():
    body = long_page("Khối ngoại bán ròng 1.245 tỷ đồng.")

    passages = web.select_passages(body, "khối ngoại bán ròng", web.MAX_PAGE_TEXT_CHARS)

    assert passages
    for passage in passages:
        assert passage in body


def test_passages_come_back_in_the_order_the_page_had_them():
    body = long_page("Đầu tiên là thanh khoản.") + "Sau đó là thanh khoản lần hai."

    passages = web.select_passages(body, "thanh khoản", 4_000)

    cursor = -1
    for passage in passages:
        found = body.index(passage)
        assert found > cursor
        cursor = found


def test_a_page_read_with_no_question_reads_from_the_top():
    body = "A" * 40_000

    passages = web.select_passages(body, "", web.MAX_PAGE_TEXT_CHARS)

    assert passages == (body[: web.MAX_PAGE_TEXT_CHARS],)


def test_a_question_sharing_no_word_with_the_page_falls_back_to_the_top():
    body = "A" * 40_000

    passages = web.select_passages(body, "zzzz qqqq", web.MAX_PAGE_TEXT_CHARS)

    assert passages == (body[: web.MAX_PAGE_TEXT_CHARS],)


def test_the_excerpt_never_exceeds_the_page_ceiling():
    body = long_page("thanh khoản cao")

    passages = web.select_passages(body, "thanh khoản", web.MAX_PAGE_TEXT_CHARS)

    assert sum(len(passage) for passage in passages) <= web.MAX_PAGE_TEXT_CHARS


class CountingLane:
    """One entry per key, and it counts how often the page was actually fetched.

    Standing in for the real lane's behaviour that matters here: it is keyed by
    URL alone, it is shared, and it holds a page for a day.
    """

    def __init__(self) -> None:
        self.entries: dict[str, Any] = {}
        self.fetches = 0

    def read(self, kind: str, key: str, fetch) -> WebRead:
        slot = f"{kind}:{key}"
        if slot not in self.entries:
            self.fetches += 1
            self.entries[slot] = fetch()
        return WebRead(self.entries[slot], 0.0, 0.0, False)


@pytest.mark.asyncio
async def test_two_questions_about_one_cached_page_get_two_different_excerpts():
    """The bug this test exists for delivers the wrong evidence, silently.

    The lane is keyed by URL and shared across threads. If the excerpt were
    computed inside the cache callback, the second question about a page would
    be handed the passages chosen for the first — a citation pointing at text
    that does not answer it, with nothing on any screen to say so.
    """
    body = (
        "<html><body>"
        + "<p>Lãi suất điều hành giữ ở 4,5 phần trăm.</p>"
        + "<p>Nội dung xen giữa. </p>" * 1_400
        + "<p>Khối ngoại bán ròng 1.245 tỷ đồng.</p>"
        + "</body></html>"
    ).encode("utf-8")
    seen: list[tuple[Any, ...]] = []
    lane = CountingLane()
    tools = web.WebTools(
        settings=settings(web_fetch_max_bytes=1_000_000),
        lane=lane,
        download=download_returning(200, {"content-type": "text/html"}, body, seen=seen),
        resolver=resolver_for("93.184.216.34"),
    )

    rates = await tools.fetch_url(CONTEXT, {"url": "https://a.example/p", "looking_for": "lãi suất điều hành"})
    flow = await tools.fetch_url(CONTEXT, {"url": "https://a.example/p", "looking_for": "khối ngoại bán ròng"})

    assert lane.fetches == 1, "the second read must come from the cache"
    assert rates["content"] != flow["content"]
    assert "4,5 phần trăm" in rates["content"]
    assert "1.245 tỷ đồng" in flow["content"]


@pytest.mark.asyncio
async def test_a_page_read_without_the_question_still_works():
    body = b"<html><body><p>Ngan hang giu nguyen lai suat.</p></body></html>"
    seen: list[tuple[Any, ...]] = []
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(200, {"content-type": "text/html"}, body, seen=seen),
        resolver=resolver_for("93.184.216.34"),
    )

    result = await tools.fetch_url(CONTEXT, {"url": "https://a.example/p"})

    assert result["reason"] is None
    assert "lai suat" in result["content"]
    assert result["looking_for"] is None


def test_the_question_is_an_argument_the_model_fills_in_not_part_of_identity():
    """Identity arrives on the context and arguments arrive from the model.

    Merging the two is the thing ``registry.ToolContext`` refuses to do, so the
    question has to be declared on the schema and nowhere else.
    """
    entries = {entry.name: entry for entry in web.WebTools(settings=settings()).entries()}
    schema = entries["fetch_url"].schema

    assert "looking_for" in schema["properties"]
    assert schema["required"] == ["url"]
    assert not hasattr(ToolContext(user_id=11), "looking_for")


def test_the_page_ceiling_is_unchanged_by_this_phase():
    assert web.MAX_PAGE_TEXT_CHARS == 20_000


# -- the page this conversation has already read -----------------------------

THREAD = uuid.UUID("6f1d5a3c-0e2b-4b5a-9c47-2f0a1d8e7b30")
IN_THREAD = ToolContext(user_id=11, thread_id=THREAD)
READ_AT = "2026-08-20T09:30:00+00:00"


def recorded_page(
    content: str = "Lãi suất điều hành giữ nguyên.",
    *,
    url: str = "https://news.example/rates",
    **overrides: Any,
) -> dict[str, Any]:
    """One earlier page read, in the shape the tool itself returned it."""
    page: dict[str, Any] = {
        "url": url,
        "title": "Rates hold",
        "content": content,
        "looking_for": None,
        "excerpted": False,
        "page_chars": len(content),
        "source": "news.example",
        "retrieved_at": READ_AT,
        "stale": False,
        "age_seconds": 0.0,
        "from_record": False,
        "reason": None,
    }
    page.update(overrides)
    return page


def records_of(*pages: Mapping[str, Any], asked: list[str] | None = None):
    """A thread's own record of the pages it has read, keyed by URL."""
    held = {str(page["url"]): page for page in pages}

    async def read(_thread_id: Any, url: str) -> Mapping[str, Any] | None:
        if asked is not None:
            asked.append(url)
        return held.get(url)

    return read


def at(moment: str):
    return lambda: datetime.fromisoformat(moment)


@pytest.mark.asyncio
async def test_a_page_this_thread_already_read_needs_no_request_at_all():
    """The gate this whole path exists for, with the cache taken away.

    ``ClosedLane`` is what an evicted or missing Redis looks like, and the page
    still comes back — from the Thread's own trace, which outlives the cache.
    Nothing is downloaded, and nothing asks the lane to serve.
    """
    seen: list[tuple[Any, ...]] = []
    tools = web.WebTools(
        settings=settings(),
        lane=ClosedLane(),
        download=download_returning(200, {}, b"", seen=seen),
        resolver=resolver_for("93.184.216.34"),
        records=records_of(recorded_page()),
    )

    result = await tools.fetch_url(IN_THREAD, {"url": "https://news.example/rates"})

    assert seen == []
    assert result["reason"] is None
    assert result["from_record"] is True
    assert "Lãi suất điều hành giữ nguyên." in result["content"]
    assert result["title"] == "Rates hold"


@pytest.mark.asyncio
async def test_a_served_record_keeps_the_instant_the_page_was_read():
    """Temporal validity rests on this field and on nothing else.

    Stamping the record with now would say a figure is current today because
    the harness re-read its own notes today. So the instant travels unchanged,
    and how old that makes the page is stated beside it under the same
    freshness window the lane uses.
    """
    tools = web.WebTools(
        settings=settings(),
        lane=ClosedLane(),
        resolver=resolver_for("93.184.216.34"),
        now=at("2026-08-23T09:30:00+00:00"),
        records=records_of(recorded_page()),
    )

    result = await tools.fetch_url(IN_THREAD, {"url": "https://news.example/rates"})

    assert result["retrieved_at"] == READ_AT
    assert result["age_seconds"] == 3 * 24 * 60 * 60
    assert result["stale"] is True


@pytest.mark.asyncio
async def test_a_url_this_thread_has_not_read_is_fetched_the_ordinary_way():
    seen: list[tuple[Any, ...]] = []
    asked: list[str] = []
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(
            200, {"content-type": "text/html"}, PAGE_HTML.encode(), seen=seen
        ),
        resolver=resolver_for("93.184.216.34"),
        records=records_of(recorded_page(url="https://news.example/other"), asked=asked),
    )

    result = await tools.fetch_url(IN_THREAD, {"url": "https://news.example/rates"})

    assert asked == ["https://news.example/rates"]
    assert len(seen) == 1
    assert result["from_record"] is False
    assert "The rate was unchanged." in result["content"]


@pytest.mark.asyncio
async def test_outside_a_persisted_turn_there_is_no_record_to_ask_for():
    """No Thread, no record — the case every offline harness runs in."""
    asked: list[str] = []
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(
            200, {"content-type": "text/html"}, PAGE_HTML.encode(), seen=[]
        ),
        resolver=resolver_for("93.184.216.34"),
        records=records_of(recorded_page(), asked=asked),
    )

    result = await tools.fetch_url(CONTEXT, {"url": "https://news.example/rates"})

    assert asked == []
    assert result["from_record"] is False


@pytest.mark.asyncio
async def test_passages_chosen_for_another_question_are_not_served_as_this_answer():
    """A record holds what the earlier call returned, not always the page.

    When that call had to excerpt, what is stored answers *its* question. A
    different question asked of the same URL is worth a real read, because the
    alternative is a citation pointing at text that does not answer it.
    """
    seen: list[tuple[Any, ...]] = []
    excerpt = recorded_page(
        "Lãi suất điều hành giữ nguyên.",
        looking_for="lãi suất điều hành",
        excerpted=True,
        page_chars=90_000,
    )
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(
            200, {"content-type": "text/html"}, PAGE_HTML.encode(), seen=seen
        ),
        resolver=resolver_for("93.184.216.34"),
        records=records_of(excerpt),
    )

    result = await tools.fetch_url(
        IN_THREAD,
        {"url": "https://news.example/rates", "looking_for": "khối ngoại bán ròng"},
    )

    assert len(seen) == 1
    assert result["from_record"] is False


@pytest.mark.asyncio
async def test_the_same_question_is_answered_from_the_excerpt_that_answered_it():
    seen: list[tuple[Any, ...]] = []
    excerpt = recorded_page(
        "Lãi suất điều hành giữ nguyên.",
        looking_for="lãi suất điều hành",
        excerpted=True,
        page_chars=90_000,
    )
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(200, {}, b"", seen=seen),
        resolver=resolver_for("93.184.216.34"),
        records=records_of(excerpt),
    )

    result = await tools.fetch_url(
        IN_THREAD,
        {"url": "https://news.example/rates", "looking_for": "lãi suất điều hành"},
    )

    assert seen == []
    assert result["from_record"] is True
    assert result["looking_for"] == "lãi suất điều hành"


@pytest.mark.asyncio
async def test_a_record_that_cannot_say_when_it_was_read_is_read_again():
    """A page with no retrieval time is worth less than a fresh read."""
    seen: list[tuple[Any, ...]] = []
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(
            200, {"content-type": "text/html"}, PAGE_HTML.encode(), seen=seen
        ),
        resolver=resolver_for("93.184.216.34"),
        records=records_of(recorded_page(retrieved_at="")),
    )

    result = await tools.fetch_url(IN_THREAD, {"url": "https://news.example/rates"})

    assert len(seen) == 1
    assert result["from_record"] is False


@pytest.mark.asyncio
async def test_a_denied_domain_stays_denied_however_often_it_was_read():
    """Configuration decides, and it decides now rather than when the row was written."""
    seen: list[tuple[Any, ...]] = []
    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(200, {}, b"", seen=seen),
        resolver=resolver_for("93.184.216.34"),
        records=records_of(recorded_page(url="https://evil.example/page")),
    )

    with pytest.raises(ValueError, match="denied by configuration"):
        await tools.fetch_url(IN_THREAD, {"url": "https://evil.example/page"})

    assert seen == []


@pytest.mark.asyncio
async def test_a_store_that_cannot_answer_leaves_the_page_read_working():
    """A database hiccup must not take down a capability aimed at the open web."""
    seen: list[tuple[Any, ...]] = []

    async def broken(_thread_id: Any, _url: str) -> Mapping[str, Any] | None:
        raise RuntimeError("the connection pool is exhausted")

    tools = web.WebTools(
        settings=settings(),
        lane=DirectLane(),
        download=download_returning(
            200, {"content-type": "text/html"}, PAGE_HTML.encode(), seen=seen
        ),
        resolver=resolver_for("93.184.216.34"),
        records=broken,
    )

    result = await tools.fetch_url(IN_THREAD, {"url": "https://news.example/rates"})

    assert len(seen) == 1
    assert result["from_record"] is False
    assert "The rate was unchanged." in result["content"]


def test_reshaping_a_page_result_keeps_the_passages_the_call_asked_for():
    """A page read shrunk by the budget must not come back as its own menu."""
    payload = json.dumps(
        {
            "url": "https://finance.example.vn/stb.htm",
            "looking_for": "giá đóng cửa và khối lượng của STB",
            "content": (
                "Trang chủ Vĩ mô Dữ liệu Doanh nghiệp Báo cáo Tin tức " * 60
                + "STB HOSE giá đóng cửa 74,500 khối lượng 9,129,600 "
                + "Điều khoản Liên hệ Quảng cáo " * 60
            ),
        },
        ensure_ascii=False,
    )

    narrowed = web.reshape_page_result(payload, 2_000)

    assert narrowed
    assert len(narrowed) <= 2_000
    reshaped = json.loads(narrowed)
    assert "74,500" in reshaped["content"]
    assert reshaped["excerpted"] is True
    assert reshaped["url"] == "https://finance.example.vn/stb.htm"


def test_a_result_without_a_question_or_content_is_left_to_the_generic_cut():
    assert web.reshape_page_result("not json at all", 500) == ""
    assert web.reshape_page_result(json.dumps({"content": "x" * 900}), 500) == ""
    assert web.reshape_page_result(json.dumps({"looking_for": "giá"}), 500) == ""


@pytest.mark.asyncio
async def test_search_drops_what_was_published_after_the_boundary_and_says_so():
    """A reader who asked "tính đến 20/8" is not answered with the 21st.

    Dropping the result is the whole point — the graded corpus reads the sources
    a Turn *carried*, so a page the model saw and declined still counts against
    it. Saying how many were dropped matters as much: a model handed a silently
    shorter list re-runs the same query looking for what it half remembers.
    """
    raw = [
        {"title": "Sau", "url": "https://a.example/1", "content": "x", "published_date": "2026-08-21"},
        {"title": "Trước", "url": "https://b.example/2", "content": "x", "published_date": "2026-08-19"},
    ]
    tools = web.WebTools(
        settings=settings(), lane=DirectLane(), search=lambda _query, _recency: raw
    )
    bounded = ToolContext(user_id=11, as_of=datetime(2026, 8, 20, 23, 59, tzinfo=web.ICT))

    result = await tools.web_search(bounded, {"query": "thanh khoản"})

    assert [item["title"] for item in result["results"]] == ["Trước"]
    assert result["excluded_outside_as_of"] == 1

    # And with no boundary the same search keeps both: this filter exists only
    # for a question that named a date.
    unbounded = await tools.web_search(CONTEXT, {"query": "thanh khoản"})
    assert len(unbounded["results"]) == 2
    assert unbounded["excluded_outside_as_of"] is None


@pytest.mark.asyncio
async def test_an_undated_result_survives_the_boundary():
    """Silence about publication time is not evidence of lateness.

    Refusing the undated was tried against the corpus and measured: on the
    session-memo case it excluded every result of every search and the Turn
    answered with no evidence at all — a dimension that was failing became one
    that could not be decided. Whether a snippet the Turn never opened should
    count as carried evidence is the question underneath, and it is not one a
    filter here can settle.
    """
    raw = [{"title": "Không ngày", "url": "https://c.example/3", "content": "x"}]
    tools = web.WebTools(
        settings=settings(), lane=DirectLane(), search=lambda _query, _recency: raw
    )
    bounded = ToolContext(user_id=11, as_of=datetime(2026, 8, 20, 23, 59, tzinfo=web.ICT))

    result = await tools.web_search(bounded, {"query": "thanh khoản"})

    assert len(result["results"]) == 1
    assert result["excluded_outside_as_of"] is None


@pytest.mark.asyncio
async def test_a_page_without_a_title_is_still_named():
    """§6.6 identity is four facts, and a titleless page would arrive with three.

    A corporate IR index is the ordinary case: it ships an empty ``<title>`` and
    an ``og:title``. Naming it from the document, or failing that from its own
    URL, keeps the source traceable without inventing anything about it.
    """
    html = (
        "<html><head><title></title>"
        "<meta property='og:title' content='Quan hệ cổ đông'>"
        "</head><body><p>Tài liệu công bố.</p></body></html>"
    )
    title, _content, metadata, _json_ld = web.extract_page_details(html, 10_000)

    assert title == ""
    assert web._named_from(metadata, "https://x.example/quan-he-co-dong.html") == (
        "Quan hệ cổ đông"
    )
    # No metadata either: the URL's own last segment names it.
    assert web._named_from({}, "https://x.example/quan-he-co-dong.html") == (
        "quan-he-co-dong.html"
    )
