"""Pytest configuration and fixtures."""
import asyncio

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select

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
