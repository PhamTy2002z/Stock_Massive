"""Regression tests for stock endpoints removed with upstream capabilities."""

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "price-depth",
        "trading-stats",
        "foreign-trading",
        "prop-trading",
        "order-stats",
        "foreign-snapshot",
    ],
)
def test_unsupported_stock_endpoint_is_not_exposed(client, path):
    """Unsupported vnstock capabilities must not remain in the public API."""
    response = client.get(f"/api/v1/stocks/VCB/{path}")

    assert response.status_code == 404
