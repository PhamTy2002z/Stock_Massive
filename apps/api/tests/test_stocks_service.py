"""Tests for stock service layer."""
from datetime import date, timedelta

import pytest

from src.stocks.service import StockService, StockServiceError


class TestStockService:
    """Test cases for StockService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return StockService(source="VCI")

    def test_get_history_valid_symbol(self, service):
        """Test fetching history for valid symbol."""
        end = date.today()
        start = end - timedelta(days=30)

        prices = service.get_history("VCB", start, end, "1D")

        assert isinstance(prices, list)
        assert len(prices) > 0
        # Validate structure
        price = prices[0]
        assert hasattr(price, "time")
        assert hasattr(price, "open")
        assert hasattr(price, "high")
        assert hasattr(price, "low")
        assert hasattr(price, "close")
        assert hasattr(price, "volume")
        # Validate data types
        assert isinstance(price.open, float)
        assert isinstance(price.close, float)
        assert isinstance(price.volume, int)
        # Validate OHLC logic
        assert price.low <= price.high
        assert price.low <= price.open <= price.high
        assert price.low <= price.close <= price.high

    def test_get_history_invalid_symbol(self, service):
        """Test fetching history for invalid symbol raises error or returns empty."""
        end = date.today()
        start = end - timedelta(days=30)

        # Invalid symbols should either raise error or return empty list
        try:
            prices = service.get_history("INVALID_SYMBOL_XYZ", start, end, "1D")
            assert prices == [] or len(prices) == 0
        except StockServiceError:
            pass  # Expected behavior

    def test_list_symbols(self, service):
        """Test listing all symbols."""
        symbols = service.list_symbols()

        assert isinstance(symbols, list)
        assert len(symbols) > 100  # Vietnam market has many stocks
        # Validate structure
        symbol = symbols[0]
        assert hasattr(symbol, "symbol")
        assert symbol.symbol is not None

    def test_list_symbols_by_exchange(self, service):
        """Test listing symbols filtered by exchange."""
        # Note: symbols_by_exchange may have network issues, handle gracefully
        try:
            hose_symbols = service.list_symbols(exchange="HOSE")
            assert isinstance(hose_symbols, list)
            # If we got results, verify exchange is set
            if len(hose_symbols) > 0:
                for sym in hose_symbols[:10]:
                    assert sym.exchange.upper() == "HOSE"
        except StockServiceError:
            # Network issues with symbols_by_exchange are acceptable
            pytest.skip("symbols_by_exchange API unavailable")

    def test_list_symbols_by_group(self, service):
        """Test listing symbols by group."""
        vn30_symbols = service.list_symbols_by_group("VN30")

        assert isinstance(vn30_symbols, list)
        assert len(vn30_symbols) == 30  # VN30 has exactly 30 stocks
        # Should contain known VN30 stocks
        assert "VCB" in vn30_symbols or "VNM" in vn30_symbols

    def test_get_company_overview(self, service):
        """Test fetching company overview."""
        overview = service.get_company_overview("VCB")

        assert overview is not None
        assert overview.symbol == "VCB"
        # Should have some company info - vnstock returns company_profile and icb_name3
        assert overview.description is not None or overview.industry is not None

    def test_get_financial_ratios(self, service):
        """Test fetching financial ratios."""
        ratios = service.get_financial_ratios("VCB", period="year")

        assert isinstance(ratios, list)
        assert len(ratios) > 0
        # Validate structure
        ratio = ratios[0]
        assert hasattr(ratio, "year")
        assert hasattr(ratio, "roe")
        assert hasattr(ratio, "pe")

    def test_get_income_statement(self, service):
        """Test fetching income statement."""
        statements = service.get_income_statement("VCB", period="year")

        assert isinstance(statements, list)
        assert len(statements) > 0
        # Validate structure
        stmt = statements[0]
        assert hasattr(stmt, "year")
        assert hasattr(stmt, "revenue")
        assert hasattr(stmt, "net_income")

    def test_get_balance_sheet(self, service):
        """Test fetching balance sheet."""
        sheets = service.get_balance_sheet("VCB", period="year")

        assert isinstance(sheets, list)
        assert len(sheets) > 0
        # Validate structure
        sheet = sheets[0]
        assert hasattr(sheet, "year")
        assert hasattr(sheet, "total_assets")
        assert hasattr(sheet, "total_equity")

    def test_get_price_board(self, service):
        """Test fetching price board."""
        board = service.get_price_board(["VCB", "ACB", "TCB"])

        assert isinstance(board, list)
        # Should return data for requested symbols
        symbols_returned = {item.symbol for item in board}
        assert len(symbols_returned) > 0
