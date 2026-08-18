"""Pytest configuration and fixtures."""
import asyncio
import os

# Paid startup calls are disabled by an explicit configuration flag. This is
# deliberately set before importing `src.main`; no production code detects
# pytest, CI, or a test environment on its own.
os.environ["LLM_CAPABILITY_PROBE_ENABLED"] = "false"

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.main import app
from src.stocks.providers import PriceBasis, ProviderSource


def basis_of(source: ProviderSource) -> PriceBasis:
    """The Price Basis each source's market rows have always carried.

    Shared by every file that builds a market Snapshot, because the pairing is
    a fact about the stored data rather than about any one test: every
    FiinQuant call asked for raw prices and the vnstock quote history has no
    raw option (``docs/adr/0006``). The code under test reads the basis off the
    row and never derives it this way — that separation is the point of the
    field — but a fixture pairing them any other way would be inventing a store
    that has never existed.
    """
    if source is ProviderSource.FIINQUANT:
        return PriceBasis.RAW
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


@pytest_asyncio.fixture
async def cleanup_intraday_test_data():
    """Fixture to clean up test data after async tests."""
    yield  # Run test first
    from src.core.database import async_session_factory
    from src.stocks.models import StockIntradayBar

    async with async_session_factory() as session:
        result = await session.execute(
            select(StockIntradayBar).where(StockIntradayBar.symbol.in_(["TEST", "UNIQ"]))
        )
        test_records = result.scalars().all()
        for record in test_records:
            await session.delete(record)
        await session.commit()
