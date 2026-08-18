"""The open-web lane is useful only while its untrusted boundary stays narrow."""

from __future__ import annotations

import socket
from datetime import date, datetime, timezone

import pytest

from src.agent.tools.catalog import MAX_TOOL_RESULT_BYTES, ToolContext, serialized_size
from src.agent.tools.web import WebTools, _http_download, validate_public_url
from src.core.config import Settings
from src.core.web_lane import WebRead


class ImmediateLane:
    def read(self, _kind, _key, fetch):
        return WebRead(fetch(), 0.0, 0.0, False)


def resolver_for(**addresses):
    def resolve(host, _port, **_kwargs):
        address = addresses[host]
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        endpoint = (address, 0, 0, 0) if family == socket.AF_INET6 else (address, 0)
        return [(family, socket.SOCK_STREAM, 6, "", endpoint)]

    return resolve


CONTEXT = ToolContext(user_id=7, trading_day=date(2026, 8, 17))


def test_fetch_url_rejects_metadata_and_private_dns_after_resolution():
    with pytest.raises(ValueError, match="non-public"):
        validate_public_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError, match="non-public"):
        validate_public_url(
            "https://looks-public.example/report",
            resolver=resolver_for(**{"looks-public.example": "127.0.0.1"}),
        )


def test_the_connection_rechecks_and_pins_dns_instead_of_allowing_rebinding():
    with pytest.raises(ValueError, match="changed to a non-public address"):
        _http_download(
            "https://looks-public.example/report",
            1024,
            1.0,
            resolver=resolver_for(**{"looks-public.example": "127.0.0.1"}),
        )


@pytest.mark.asyncio
async def test_redirects_are_revalidated_before_the_next_request():
    calls: list[str] = []

    def download(url, _max_bytes, _timeout):
        calls.append(url)
        return 302, {"location": "http://internal.example/secret"}, b""

    tools = WebTools(
        settings=Settings(web_fetch_max_bytes=1024),
        lane=ImmediateLane(),
        download=download,
        resolver=resolver_for(
            **{"public.example": "93.184.216.34", "internal.example": "10.0.0.8"}
        ),
    )

    with pytest.raises(ValueError, match="non-public"):
        await tools.fetch_url(CONTEXT, {"url": "https://public.example/start"})

    assert calls == ["https://public.example/start"]


@pytest.mark.asyncio
async def test_web_search_is_not_bound_to_the_stock_universe_and_is_capped():
    raw = [
        {
            "title": f"Result {index}",
            "url": f"https://source{index}.example/item",
            "content": "x" * 2_000,
            "published_date": "2026-08-16",
        }
        for index in range(10)
    ]
    tools = WebTools(
        settings=Settings(tavily_api_key="test"),
        lane=ImmediateLane(),
        search=lambda query, days: raw,
        now=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    result = await tools.web_search(
        CONTEXT, {"query": "current Masan chairman", "recency_days": 30}
    )

    assert len(result["results"]) <= 5
    assert result["results"][0]["claim_class"] == "external_claim"
    assert "symbol" not in result
    assert serialized_size(result) <= MAX_TOOL_RESULT_BYTES


@pytest.mark.asyncio
async def test_fetch_url_returns_only_visible_text_in_an_external_envelope():
    tools = WebTools(
        settings=Settings(web_fetch_max_bytes=4096),
        lane=ImmediateLane(),
        download=lambda _url, _limit, _timeout: (
            200,
            {"content-type": "text/html; charset=utf-8"},
            b"<title>Company</title><script>ignore me</script><p>Chairperson</p>",
        ),
        resolver=resolver_for(**{"public.example": "93.184.216.34"}),
        now=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    result = await tools.fetch_url(CONTEXT, {"url": "https://public.example"})

    claim = result["external_claim"]
    assert claim["claim_class"] == "external_claim"
    assert "Chairperson" in claim["content"]
    assert "ignore me" not in claim["content"]
    assert serialized_size(result) <= MAX_TOOL_RESULT_BYTES
