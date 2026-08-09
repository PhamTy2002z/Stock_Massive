"""Regression tests for stock endpoints removed with upstream capabilities."""


def test_price_depth_endpoint_is_not_exposed(client):
    """vnstock removed VCI price-depth support, so the API must not advertise it."""
    response = client.get("/api/v1/stocks/VCB/price-depth")

    assert response.status_code == 404
