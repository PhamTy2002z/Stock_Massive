"""A connector reaches public addresses only: by literal, by DNS, after redirects,
and across a DNS answer that changes between the check and the connection."""

from __future__ import annotations

import socket

import pytest

from src.connectors import mcp_client, netguard
from src.core.config import Settings

from .fake_mcp import FakeMCP

TEST_SETTINGS = Settings(deployment_profile="test")


def _answer(address: str):
    def resolver(host, port, type=None):  # noqa: A002 - getaddrinfo's own name
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    return resolver


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/mcp",
        "https://10.0.0.5/mcp",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/mcp",
        "https://localhost/mcp",
        "https://192.168.1.10/mcp",
    ],
)
def test_a_private_address_is_refused(url):
    with pytest.raises(netguard.ConnectorURLRefused):
        netguard.validate_connector_url(url)


def test_a_public_name_that_resolves_private_is_refused():
    with pytest.raises(netguard.ConnectorURLRefused, match="non-public"):
        netguard.validate_connector_url("https://notes.example.com/mcp", resolver=_answer("10.1.2.3"))


def test_a_public_name_that_resolves_public_is_accepted():
    url = netguard.validate_connector_url("https://Notes.Example.com/mcp", resolver=_answer("93.184.216.34"))
    assert url == "https://notes.example.com/mcp"


@pytest.mark.parametrize("url", ["http://93.184.216.34/mcp", "ftp://93.184.216.34/", "https://user:pw@93.184.216.34/"])
def test_only_plain_https_urls_are_accepted(url):
    with pytest.raises(netguard.ConnectorURLRefused):
        netguard.validate_connector_url(url)


@pytest.mark.asyncio
async def test_the_first_answer_is_pinned_so_a_rebinding_dns_is_never_asked_again():
    answers = iter(["93.184.216.34", "127.0.0.1"])
    asked: list[str] = []

    def rebinding(host, port, type=None):  # noqa: A002
        address = next(answers)
        asked.append(address)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    backend = netguard.PinnedBackend(resolver=rebinding)
    connected: list[str] = []

    async def record(address, port, **kwargs):
        connected.append(address)
        raise OSError("not really connecting")

    backend._inner.connect_tcp = record  # noqa: SLF001 - observe the socket target
    for _ in range(2):
        with pytest.raises(OSError):
            await backend.connect_tcp("notes.example.com", 443)
    assert asked == ["93.184.216.34"]
    assert connected == ["93.184.216.34", "93.184.216.34"]


@pytest.mark.asyncio
async def test_a_dns_answer_that_turns_private_at_connect_time_is_refused():
    backend = netguard.PinnedBackend(resolver=_answer("169.254.169.254"))
    with pytest.raises(netguard.ConnectorURLRefused):
        await backend.connect_tcp("metadata.example.com", 443)


def test_the_client_connects_through_the_pinned_backend():
    client = netguard.pinned_client()
    assert isinstance(client._transport._pool._network_backend, netguard.PinnedBackend)  # noqa: SLF001
    assert client.follow_redirects is False


def test_the_private_host_override_is_refused_in_production():
    with pytest.raises(RuntimeError, match="production"):
        with netguard.allow_private_hosts_for_tests(Settings(deployment_profile="production")):
            pass
    assert netguard.private_hosts_allowed() is False


def test_no_environment_variable_opens_private_hosts(monkeypatch):
    for name in ("CONNECTORS_ALLOW_PRIVATE_HOSTS", "ALLOW_PRIVATE_HOSTS", "CONNECTORS_TEST_MODE"):
        monkeypatch.setenv(name, "true")
    with pytest.raises(netguard.ConnectorURLRefused):
        netguard.validate_connector_url("https://127.0.0.1/mcp")


@pytest.fixture(scope="module")
def two_servers():
    target, landing = FakeMCP().start(), FakeMCP(token=None).start()
    yield target, landing
    target.stop()
    landing.stop()


@pytest.mark.asyncio
async def test_a_redirect_is_never_followed(two_servers):
    target, landing = two_servers
    target.redirect_to = landing.url
    before = landing.requests
    with netguard.allow_private_hosts_for_tests(TEST_SETTINGS):
        with pytest.raises(mcp_client.ConnectorProtocolError, match="redirect"):
            await mcp_client.list_tools(
                mcp_client.Target(url=f"{target.base}/redirect", headers={"Authorization": "Bearer s3cret"})
            )
    assert landing.requests == before
