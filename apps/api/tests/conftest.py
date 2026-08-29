"""Pytest configuration and fixtures."""
import asyncio
import os

# Paid startup calls are disabled by an explicit configuration flag. This is
# deliberately set before importing `src.main`; no production code detects
# pytest, CI, or a test environment on its own.
os.environ["LLM_CAPABILITY_PROBE_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.stocks.providers import PriceBasis, ProviderSource


def basis_of(source: ProviderSource) -> PriceBasis:
    """The Price Basis each source's market rows have always carried.

    Shared by every file that builds a market Snapshot, because the pairing is
    a fact about the stored data rather than about any one test. It used to be a
    branch: the retired source asked for raw prices, and the surviving one's
    quote history has no raw option (``docs/adr/0006``). With one source left
    there is one answer, and the function stays rather than being inlined
    because it is the place that sentence is recorded — a fixture pairing a
    source with a basis any other way would be inventing a store that has never
    existed.

    The code under test reads the basis off the row and never derives it this
    way. That separation is the point of the field.
    """
    return PriceBasis.ADJUSTED_AT_SOURCE


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
