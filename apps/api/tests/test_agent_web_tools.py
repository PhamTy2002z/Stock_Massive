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
