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
