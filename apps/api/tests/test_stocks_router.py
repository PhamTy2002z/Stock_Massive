"""Tests for stock API endpoints."""
from datetime import date, timedelta

import pytest

# Every test in this module calls the live vnstock API — there are no mocks.
# They go red on upstream throttling rather than on anything in this repo,
# so they sit out the default run. Run them with: pytest -m network
pytestmark = pytest.mark.network


class TestStocksRouter:
    """Test cases for stocks API endpoints."""

    def test_health_check(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_list_symbols(self, client):
        """Test GET /api/v1/stocks/symbols."""
        response = client.get("/api/v1/stocks/symbols")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Validate schema
        assert "symbol" in data[0]

    def test_list_symbols_by_exchange(self, client):
        """Test GET /api/v1/stocks/symbols with exchange filter."""
        response = client.get("/api/v1/stocks/symbols?exchange=HOSE")

        # symbols_by_exchange may have network issues, accept 200 or 502
        if response.status_code == 502:
            pytest.skip("symbols_by_exchange API unavailable")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_symbols_by_group(self, client):
        """Test GET /api/v1/stocks/symbols/group/{group}."""
        response = client.get("/api/v1/stocks/symbols/group/VN30")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 30

    def test_get_history(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/history."""
        end = date.today()
        start = end - timedelta(days=30)

        response = client.get(
            f"/api/v1/stocks/{valid_symbol}/history",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Validate schema
        price = data[0]
        assert "time" in price
        assert "open" in price
        assert "high" in price
        assert "low" in price
        assert "close" in price
        assert "volume" in price

    def test_get_history_invalid_interval(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/history with invalid interval."""
        end = date.today()
        start = end - timedelta(days=30)

        response = client.get(
            f"/api/v1/stocks/{valid_symbol}/history",
            params={
                "start": start.isoformat(),
                "end": end.isoformat(),
                "interval": "INVALID",
            },
        )

        assert response.status_code == 400
        assert "Invalid interval" in response.json()["detail"]

    def test_get_history_invalid_date_range(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/history with start > end."""
        end = date.today()
        start = end + timedelta(days=30)  # Start after end

        response = client.get(
            f"/api/v1/stocks/{valid_symbol}/history",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )

        assert response.status_code == 400
        assert "Start date must be before end date" in response.json()["detail"]

    def test_get_company_overview(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/company."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/company")

        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == valid_symbol

    def test_get_financial_ratios(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/financials/ratios."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/financials/ratios")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_financial_ratios_quarterly(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/financials/ratios with quarter period."""
        response = client.get(
            f"/api/v1/stocks/{valid_symbol}/financials/ratios",
            params={"period": "quarter"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_financial_ratios_invalid_period(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/financials/ratios with invalid period."""
        response = client.get(
            f"/api/v1/stocks/{valid_symbol}/financials/ratios",
            params={"period": "invalid"},
        )

        assert response.status_code == 400
        assert "Invalid period" in response.json()["detail"]

    def test_get_income_statement(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/financials/income."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/financials/income")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_balance_sheet(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/financials/balance-sheet."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/financials/balance-sheet")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_price_board(self, client, valid_symbols):
        """Test GET /api/v1/stocks/price-board."""
        symbols_str = ",".join(valid_symbols)
        response = client.get(
            "/api/v1/stocks/price-board",
            params={"symbols": symbols_str},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_price_board_empty_symbols(self, client):
        """Test GET /api/v1/stocks/price-board with empty symbols."""
        response = client.get(
            "/api/v1/stocks/price-board",
            params={"symbols": ""},
        )

        assert response.status_code == 400
        assert "At least one symbol" in response.json()["detail"]

    def test_get_price_board_too_many_symbols(self, client):
        """Test GET /api/v1/stocks/price-board with too many symbols."""
        symbols = ",".join([f"SYM{i}" for i in range(51)])
        response = client.get(
            "/api/v1/stocks/price-board",
            params={"symbols": symbols},
        )

        assert response.status_code == 400
        assert "Maximum 50 symbols" in response.json()["detail"]
