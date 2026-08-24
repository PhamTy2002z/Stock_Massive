"""Conformance tests for DNSE auth, local validation, rate handling, and REST."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import httpx
import pytest

from src.stocks.realtime import DataOutcomeKind
from src.stocks.realtime.dnse import (
    DnseCredentials,
    DnseRestClient,
    EndpointFamily,
    EventWindow,
    OhlcRequest,
    RateBudget,
    RestSigner,
    WebSocketSigner,
)


def test_credentials_are_redacted_and_rest_signature_matches_official_shape():
    credentials = DnseCredentials("public-key", "private-secret")
    signer = RestSigner(
        credentials,
        clock=lambda: datetime(2026, 5, 15, 7, 11, 30, tzinfo=UTC),
        nonce_factory=lambda: "c9a8f88b472c9721fde161e0d89df8cc",
    )

    headers = signer.headers("GET", "/accounts")

    assert "private-secret" not in repr(credentials)
    assert headers["Date"] == "Fri, 15 May 2026 07:11:30 +0000"
    assert headers["X-Api-Key"] == "public-key"
    assert 'headers="(request-target) date"' in headers["X-Signature"]
    assert 'nonce="c9a8f88b472c9721fde161e0d89df8cc"' in headers["X-Signature"]
    assert "private-secret" not in json.dumps(dict(headers))


def test_websocket_auth_nonce_is_text_and_signature_is_deterministic():
    signer = WebSocketSigner(
        DnseCredentials("key", "secret"), timestamp=lambda: 1_777_777_777.125
    )
    message = signer.message()
    next_message = signer.message()

    assert isinstance(message["nonce"], str)
    assert len(str(message["signature"])) == 64
    assert int(str(next_message["nonce"])) == int(str(message["nonce"])) + 1
    assert next_message["signature"] != message["signature"]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: EventWindow(date(2026, 8, 23), date(2026, 8, 24)),
        lambda: EventWindow(date(2026, 8, 24), date(2026, 8, 24), limit=1001),
        lambda: OhlcRequest("FPT", "1h", date(2026, 8, 1), date(2026, 8, 24)),
        lambda: OhlcRequest(
            "FPT", "1", date(2026, 8, 1), date(2026, 8, 24), "bond"
        ),
        lambda: OhlcRequest("FPT", "1", date(2026, 8, 24), date(2026, 8, 1)),
    ],
)
def test_invalid_requests_are_refused_before_transport(factory):
    with pytest.raises(ValueError):
        factory()


def test_rate_budget_learns_headers_without_increasing_local_allowance():
    budget = RateBudget(clock=lambda: 100.0)
    budget.update(EndpointFamily.REFERENCE, {"X-RateLimit-Remaining": "3"})
    assert budget.remaining(EndpointFamily.REFERENCE) == 3
    budget.update(EndpointFamily.REFERENCE, {"X-RateLimit-Remaining": "900"})
    assert budget.remaining(EndpointFamily.REFERENCE) == 3


def test_rate_budget_restores_daily_allowance_after_the_daily_window():
    now = [100.0]
    budget = RateBudget(clock=lambda: now[0])
    budget.update(EndpointFamily.REFERENCE, {"X-RateLimit-Daily-Remaining": "0"})
    with pytest.raises(RuntimeError, match="exhausted locally"):
        budget.acquire(EndpointFamily.REFERENCE)

    now[0] += 86_401
    budget.acquire(EndpointFamily.REFERENCE)
    assert budget.remaining(EndpointFamily.REFERENCE) > 0


@pytest.mark.asyncio
async def test_rest_uses_signed_https_and_classifies_silent_empty():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[], headers={"X-RateLimit-Remaining": "12"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = DnseRestClient(
            RestSigner(
                DnseCredentials("key", "secret"),
                nonce_factory=iter(("a" * 32, "b" * 32)).__next__,
            ),
            client=http_client,
        )
        result = await client.trades(
            "fpt", EventWindow(date(2026, 8, 24), date(2026, 8, 24)), "g1"
        )

    assert result.outcome and result.outcome.kind is DataOutcomeKind.SILENT_EMPTY
    assert requests[0].url.scheme == "https"
    assert requests[0].url.path == "/price/FPT/trades"
    assert requests[0].url.params["boardId"] == "G1"
    assert requests[0].headers["x-signature"].startswith("Signature ")


@pytest.mark.asyncio
async def test_opaque_pagination_is_idempotent_and_replay_is_detected():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        row = {"T": "t", "symbol": "FPT", "matchPrice": 71.4}
        token = "opaque-A" if calls <= 2 else None
        return httpx.Response(200, json={"data": [row], "nextPageToken": token})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = DnseRestClient(
            RestSigner(
                DnseCredentials("key", "secret"),
                nonce_factory=iter(("b" * 32, "c" * 32, "d" * 32)).__next__,
            ),
            client=http_client,
        )
        pages = []
        iterator = client.pages(
            "FPT",
            "trades",
            EventWindow(date(2026, 8, 24), date(2026, 8, 24)),
        )
        pages.append(await anext(iterator))
        pages.append(await anext(iterator))
        with pytest.raises(RuntimeError, match="token replay"):
            await anext(iterator)

    assert len(pages) == 2
    assert pages[0].items
    assert pages[1].items == ()
    assert client.metrics.snapshot().counters["duplicates"] == 1
