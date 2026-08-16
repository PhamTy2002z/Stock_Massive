"""The deployment's own arithmetic, checked against the code it is sized for.

A Turn is given thirty seconds to reach a safe checkpoint on shutdown
(``docs/adr/0013``), and that window is only real if the container is still
alive to spend it. Three numbers have to line up for that, and they live in
three different files — a constant in ``src/agent/turns.py``, a uvicorn flag in
``Dockerfile.prod``, and a stop grace in ``docker-compose.prod.yml``. Nothing
fails loudly when they drift; the failure is a deploy that kills Turns between
checkpoints, months later, in production.

So the arithmetic is asserted here rather than written in a comment: uvicorn
drains connections *before* the ASGI lifespan shuts down, so the container has
to outlive both windows in sequence. The end-to-end acceptance (#92) proves the
streaming; this proves the deployment it streams inside of.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from src.agent.turns import GRACEFUL_SHUTDOWN_SECONDS

REPO = Path(__file__).resolve().parents[3]
COMPOSE = REPO / "docker-compose.prod.yml"
API_DOCKERFILE = REPO / "apps" / "api" / "Dockerfile.prod"
CADDYFILE = REPO / "deploy" / "Caddyfile"
TOPOLOGY = REPO / "docs" / "streaming-topology.md"


def _seconds(value: str) -> float:
    """A compose duration — `45s`, `1m30s` — in seconds."""
    total = 0.0
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)(h|m|s|ms)", value):
        total += float(amount) * {"h": 3600, "m": 60, "s": 1, "ms": 0.001}[unit]
    if total == 0:
        raise AssertionError(f"unparsable duration: {value!r}")
    return total


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text())


@pytest.fixture(scope="module")
def api_dockerfile() -> str:
    return API_DOCKERFILE.read_text()


def _connection_drain(dockerfile: str) -> float:
    match = re.search(
        r"--timeout-graceful-shutdown\"?,?\s*\"?(\d+)", dockerfile
    )
    assert match is not None, (
        "uvicorn must be given a graceful-shutdown timeout: without one it "
        "waits for an SSE connection that stays open for the whole Turn, and "
        "the lifespan's checkpoint window never begins"
    )
    return float(match.group(1))


class TestTheShutdownWindows:
    def test_the_api_bounds_how_long_it_waits_for_open_connections(
        self, api_dockerfile
    ):
        drain = _connection_drain(api_dockerfile)

        # Long enough for an ordinary request to finish, short enough that the
        # checkpoint window still fits inside the stop grace.
        assert 0 < drain <= 30

    def test_the_api_stop_grace_covers_the_drain_and_the_checkpoint_window(
        self, compose, api_dockerfile
    ):
        grace = _seconds(compose["services"]["api"]["stop_grace_period"])
        drain = _connection_drain(api_dockerfile)

        # In sequence, not in parallel: uvicorn drains, *then* the lifespan
        # shuts down and Alpha Desk spends its thirty seconds.
        assert grace > drain + GRACEFUL_SHUTDOWN_SECONDS

    def test_the_web_container_is_given_time_to_end_a_proxied_stream(self, compose):
        grace = _seconds(compose["services"]["web"]["stop_grace_period"])

        assert grace >= 30

    def test_the_outer_proxy_outlives_the_containers_behind_it(self, compose):
        # Cutting the outermost connection first would end a stream whose two
        # inner hops were still being given time to finish it.
        proxy = _seconds(compose["services"]["proxy"]["stop_grace_period"])
        web = _seconds(compose["services"]["web"]["stop_grace_period"])

        assert proxy > web


class TestTheInternalRoute:
    def test_the_web_container_reaches_the_api_over_the_internal_network(
        self, compose
    ):
        environment = compose["services"]["web"]["environment"]

        # Without this the route handlers fall back to the public build-time
        # URL and hairpin out through the internet to reach the container next
        # door (docs/adr/0013).
        assert environment["INTERNAL_API_URL"].startswith("http://api:8000")


class TestTheOuterProxy:
    def test_the_stream_route_is_told_not_to_buffer(self):
        caddyfile = CADDYFILE.read_text()

        # A hop permitted to buffer is a hop that delivers the whole Turn at
        # the end, which is indistinguishable from one that is hung.
        assert "flush_interval -1" in caddyfile
        # No read timeout: the response is open for as long as the Turn is.
        assert "read_timeout 0" in caddyfile

    def test_compression_is_excluded_by_a_matcher_rather_than_by_placement(self):
        caddyfile = CADDYFILE.read_text()

        # `handle` scopes only what is inside it, so a bare site-level `encode`
        # compresses the stream too — and a compressor filling its window holds
        # the stream until the Turn ends. The exclusion has to be a matcher on
        # `encode` itself, which is exactly the kind of detail that reads as
        # correct and is not.
        assert re.search(r"^\s*encode\s+zstd", caddyfile, re.MULTILINE) is None, (
            "every `encode` must carry a matcher excluding the event-stream path"
        )
        assert caddyfile.count("encode @compressible") == 2

    def test_the_topology_is_written_down_where_the_next_reader_will_look(self):
        # Spec 0003 §14.4 is closed against this file, and ADR-0013 points at
        # it. A test rather than trust, because a deleted document is exactly
        # the kind of loss nothing else notices.
        assert TOPOLOGY.exists()
        text = TOPOLOGY.read_text()
        assert "pnpm test:e2e" in text
