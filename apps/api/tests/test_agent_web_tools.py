"""The rules that keep a model-chosen URL from reaching anything private."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
