"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient

from src.main import app


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
