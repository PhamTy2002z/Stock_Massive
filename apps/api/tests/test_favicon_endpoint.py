"""The favicon endpoint: server-fetched icons, never a browser's direct request."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.alpha.favicons import FaviconTools, get_favicon_tools
from src.auth.dependencies import get_current_user
from src.main import app

FAKE_USER = SimpleNamespace(id=1, is_active=True)


def resolver_for(*addresses: str):
    """A DNS answer of exactly these addresses, whatever host was asked."""

    def resolve(_host: str, _port: Any, **_kwargs: Any) -> Sequence[tuple[Any, ...]]:
        return [(2, 1, 6, "", (address, 80)) for address in addresses]

    return resolve


class FakeRedis:
    """An in-memory stand-in for the real Redis client the cache reads."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        return True


def download_returning(
    status: int, headers: Mapping[str, str], body: bytes, *, calls: list[str]
):
    def download(url: str, max_bytes: int, timeout: float) -> tuple[int, Mapping[str, str], bytes]:
        calls.append(url)
        return status, headers, body

    return download


def download_raising(*, calls: list[str]):
    def download(url: str, max_bytes: int, timeout: float) -> tuple[int, Mapping[str, str], bytes]:
        calls.append(url)
        raise OSError("connection refused")

    return download


@pytest.fixture(autouse=True)
def _authenticated() -> Any:
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_favicon_tools, None)


def _use(tools: FaviconTools) -> None:
    app.dependency_overrides[get_favicon_tools] = lambda: tools


def _client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize(
    "domain",
    [
        "http://example.com",  # scheme
        "example.com/path",  # path
        "example.com:8080",  # port
        "example .com",  # whitespace
        "localhost",  # no dot at all
    ],
)
def test_a_malformed_domain_is_refused_before_any_fetch_is_attempted(domain: str):
    calls: list[str] = []
    _use(FaviconTools(redis_factory=lambda: None, download=download_returning(200, {}, b"", calls=calls)))

    response = _client().get("/api/v1/assets/favicon", params={"domain": domain})

    assert response.status_code == 400
    assert calls == []


def test_a_domain_resolving_to_a_private_address_is_refused_with_no_outbound_request():
    calls: list[str] = []
    tools = FaviconTools(
        redis_factory=lambda: None,
        resolver=resolver_for("10.0.0.5"),
        download=download_returning(200, {"content-type": "image/png"}, b"\x89PNG", calls=calls),
    )
    _use(tools)

    response = _client().get("/api/v1/assets/favicon", params={"domain": "internal.example"})

    assert response.status_code == 404
    assert calls == []


def test_a_literal_loopback_address_is_refused_with_no_outbound_request():
    calls: list[str] = []
    tools = FaviconTools(
        redis_factory=lambda: None,
        download=download_returning(200, {"content-type": "image/png"}, b"\x89PNG", calls=calls),
    )
    _use(tools)

    response = _client().get("/api/v1/assets/favicon", params={"domain": "127.0.0.1"})

    assert response.status_code == 404
    assert calls == []


def test_a_non_image_upstream_response_is_answered_with_404():
    calls: list[str] = []
    tools = FaviconTools(
        redis_factory=lambda: FakeRedis(),
        resolver=resolver_for("93.184.216.34"),
        download=download_returning(
            200, {"content-type": "text/html; charset=utf-8"}, b"<html></html>", calls=calls
        ),
    )
    _use(tools)

    response = _client().get("/api/v1/assets/favicon", params={"domain": "no-icon.example"})

    assert response.status_code == 404
    assert response.content == b""
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert len(calls) == 1


def test_an_image_upstream_response_is_served_with_its_content_type_and_cache_control():
    calls: list[str] = []
    icon_bytes = b"\x89PNG\r\n\x1a\n"
    tools = FaviconTools(
        redis_factory=lambda: FakeRedis(),
        resolver=resolver_for("93.184.216.34"),
        download=download_returning(
            200, {"content-type": "image/png"}, icon_bytes, calls=calls
        ),
    )
    _use(tools)

    response = _client().get("/api/v1/assets/favicon", params={"domain": "has-icon.example"})

    assert response.status_code == 200
    assert response.content == icon_bytes
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=604800, immutable"
    assert len(calls) == 1


def test_a_second_request_for_the_same_domain_is_served_from_cache_without_a_new_fetch():
    calls: list[str] = []
    icon_bytes = b"\x89PNG\r\n\x1a\n"
    redis = FakeRedis()
    tools = FaviconTools(
        redis_factory=lambda: redis,
        resolver=resolver_for("93.184.216.34"),
        download=download_returning(
            200, {"content-type": "image/png"}, icon_bytes, calls=calls
        ),
    )
    _use(tools)
    client = _client()

    first = client.get("/api/v1/assets/favicon", params={"domain": "cached-icon.example"})
    second = client.get("/api/v1/assets/favicon", params={"domain": "cached-icon.example"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.content == icon_bytes
    assert len(calls) == 1


def test_a_failed_fetch_is_also_cached_so_a_second_request_makes_no_new_call():
    calls: list[str] = []
    redis = FakeRedis()
    tools = FaviconTools(
        redis_factory=lambda: redis,
        resolver=resolver_for("93.184.216.34"),
        download=download_raising(calls=calls),
    )
    _use(tools)
    client = _client()

    first = client.get("/api/v1/assets/favicon", params={"domain": "unreachable.example"})
    second = client.get("/api/v1/assets/favicon", params={"domain": "unreachable.example"})

    assert first.status_code == 404
    assert second.status_code == 404
    assert len(calls) == 1
