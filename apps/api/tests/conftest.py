"""Pytest configuration and fixtures."""
import asyncio
import os

# Paid startup calls are disabled by an explicit configuration flag. This is
# deliberately set before importing `src.main`; no production code detects
# pytest, CI, or a test environment on its own.
os.environ["LLM_CAPABILITY_PROBE_ENABLED"] = "false"
# The same kind of flag for the request limiter. `.env` can name a shared Redis,
# and a suite of a few hundred requests from one address spends that window for
# every other process using it — then fails its own later tests with 429s that
# say nothing about the code. The limiter's behaviour is tested against explicit
# Settings in `tests/test_ratelimit.py`.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from src.agent.tools import vnstock_provider
from src.main import app


@pytest.fixture(autouse=True)
def _fresh_provider_reads():
    """Provider reads are memoised process-wide; each test starts with none."""
    vnstock_provider.READS.clear()
    yield
    vnstock_provider.READS.clear()
@pytest.fixture(scope="session")
def event_loop():
    """Create session-scoped event loop for async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def valid_symbol():
    """Known valid stock symbol."""
    return "VCB"


@pytest.fixture
def valid_symbols():
    """List of known valid symbols."""
    return ["VCB", "ACB", "TCB"]
