"""Tests for sector performance feature.

Tests cover:
- SectorPerformanceItem and SectorPerformanceResponse schemas
- StockService.get_sector_performance() method
- Edge cases: empty data, missing columns, error handling
- Market-cap weighted calculation logic
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.stocks.schemas import SectorPerformanceItem, SectorPerformanceResponse
from src.stocks.service import StockService, StockServiceError


# === Schema Tests ===


class TestSectorPerformanceSchemas:
    """Test cases for sector performance Pydantic schemas."""

    def test_sector_performance_item_valid(self):
        """Test SectorPerformanceItem with valid data."""
        item = SectorPerformanceItem(
            icb_code="8000",
            icb_name="Tai chinh",
            change_pct=1.25,
            total_market_cap=150000.5,
            stock_count=45,
            top_gainers=["VCB", "ACB", "TCB"],
            top_losers=["STB", "EIB", "SHB"],
        )

        assert item.icb_code == "8000"
        assert item.icb_name == "Tai chinh"
        assert item.change_pct == 1.25
        assert item.total_market_cap == 150000.5
        assert item.stock_count == 45
        assert item.top_gainers == ["VCB", "ACB", "TCB"]
        assert item.top_losers == ["STB", "EIB", "SHB"]

    def test_sector_performance_item_required_fields(self):
        """Test SectorPerformanceItem requires mandatory fields."""
        with pytest.raises(ValueError):
            SectorPerformanceItem()  # Missing required fields

    def test_sector_performance_item_default_lists(self):
        """Test SectorPerformanceItem default empty lists."""
        item = SectorPerformanceItem(
            icb_code="1000",
            icb_name="Nang luong",
            change_pct=-0.5,
            total_market_cap=50000.0,
            stock_count=10,
        )

        assert item.top_gainers == []
        assert item.top_losers == []

    def test_sector_performance_item_negative_change(self):
        """Test SectorPerformanceItem with negative change."""
        item = SectorPerformanceItem(
            icb_code="2000",
            icb_name="Vat lieu co ban",
            change_pct=-2.75,
            total_market_cap=30000.0,
            stock_count=25,
        )

        assert item.change_pct == -2.75

    def test_sector_performance_response_valid(self):
        """Test SectorPerformanceResponse with valid data."""
        now = datetime.now()
        sectors = [
            SectorPerformanceItem(
                icb_code="8000",
                icb_name="Tai chinh",
                change_pct=1.5,
                total_market_cap=150000.0,
                stock_count=45,
            ),
            SectorPerformanceItem(
                icb_code="5000",
                icb_name="Hang tieu dung",
                change_pct=0.8,
                total_market_cap=80000.0,
                stock_count=30,
            ),
        ]

        response = SectorPerformanceResponse(
            sectors=sectors,
            generated_at=now,
            total_sectors=2,
        )

        assert len(response.sectors) == 2
        assert response.generated_at == now
        assert response.total_sectors == 2

    def test_sector_performance_response_empty(self):
        """Test SectorPerformanceResponse with empty sectors."""
        now = datetime.now()
        response = SectorPerformanceResponse(
            sectors=[],
            generated_at=now,
            total_sectors=0,
        )

        assert response.sectors == []
        assert response.total_sectors == 0


# === Service Tests with Mocks ===


class TestGetSectorPerformance:
    """Test cases for StockService.get_sector_performance() method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return StockService(source="VCI")

    @pytest.fixture
    def mock_symbols_by_industries_df(self):
        """Mock symbols_by_industries DataFrame with ICB classification."""
        return pd.DataFrame({
            'symbol': ['VCB', 'ACB', 'TCB', 'VNM', 'MSN', 'HPG', 'HSG'],
            'industry_code': ['11', '11', '11', '19', '19', '21', '21'],
            'industry_name': ['Ngan hang', 'Ngan hang', 'Ngan hang', 'Thuc pham - Do uong', 'Thuc pham - Do uong', 'Vat lieu xay dung', 'Vat lieu xay dung'],
        })

    @pytest.fixture
    def mock_price_board_df(self):
        """Mock price board DataFrame."""
        return pd.DataFrame({
            'symbol': ['VCB', 'ACB', 'TCB'],
            'change_pct': [1.5, 2.0, -0.5],
            'accumulated_value': [100_000_000_000, 50_000_000_000, 30_000_000_000],
        })

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_get_sector_performance_success(self, mock_trading_cls, mock_listing_cls, service, mock_symbols_by_industries_df):
        """Test successful sector performance retrieval."""
        # Setup mocks
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = mock_symbols_by_industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        # Return price board with all symbols in batches
        def price_board_side_effect(symbols_list, **kwargs):
            # Return price data for requested symbols
            data = {
                'VCB': {'match_price': 101.5, 'ref_price': 100.0, 'accumulated_value': 100e9},
                'ACB': {'match_price': 25.5, 'ref_price': 25.0, 'accumulated_value': 50e9},
                'TCB': {'match_price': 29.5, 'ref_price': 30.0, 'accumulated_value': 30e9},
                'VNM': {'match_price': 81.0, 'ref_price': 80.0, 'accumulated_value': 80e9},
                'MSN': {'match_price': 66.0, 'ref_price': 65.0, 'accumulated_value': 40e9},
                'HPG': {'match_price': 24.5, 'ref_price': 25.0, 'accumulated_value': 60e9},
                'HSG': {'match_price': 14.0, 'ref_price': 15.0, 'accumulated_value': 20e9},
            }
            rows = []
            for s in symbols_list:
                if s in data:
                    rows.append({'symbol': s, **data[s]})
            return pd.DataFrame(rows) if rows else pd.DataFrame()

        mock_trading.price_board.side_effect = price_board_side_effect
        mock_trading_cls.return_value = mock_trading

        # Execute
        result = service.get_sector_performance()

        # Verify
        assert isinstance(result, SectorPerformanceResponse)
        assert result.total_sectors == 3
        assert len(result.sectors) == 3
        assert result.generated_at is not None

        # Verify sectors are sorted by change_pct descending
        changes = [s.change_pct for s in result.sectors]
        assert changes == sorted(changes, reverse=True)

    @patch('src.stocks.market.service.Listing')
    def test_get_sector_performance_empty_symbols(self, mock_listing_cls, service):
        """Test with empty symbols_by_industries DataFrame."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = pd.DataFrame()
        mock_listing_cls.return_value = mock_listing

        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.sectors == []
        assert result.total_sectors == 0

    @patch('src.stocks.market.service.Listing')
    def test_get_sector_performance_none_symbols(self, mock_listing_cls, service):
        """Test with None symbols_by_industries DataFrame."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = None
        mock_listing_cls.return_value = mock_listing

        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.sectors == []
        assert result.total_sectors == 0

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_get_sector_performance_empty_price_board(self, mock_trading_cls, mock_listing_cls, service, mock_symbols_by_industries_df):
        """Test with empty price board response."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = mock_symbols_by_industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame()
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.sectors == []
        assert result.total_sectors == 0

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_get_sector_performance_price_board_exception(self, mock_trading_cls, mock_listing_cls, service, mock_symbols_by_industries_df):
        """Test graceful handling of price board exceptions."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = mock_symbols_by_industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.side_effect = Exception("API Error")
        mock_trading_cls.return_value = mock_trading

        # Should not raise, just return empty sectors
        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.sectors == []

    @patch('src.stocks.market.service.Listing')
    def test_get_sector_performance_listing_exception(self, mock_listing_cls, service):
        """Test exception from Listing API raises StockServiceError."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.side_effect = Exception("Network Error")
        mock_listing_cls.return_value = mock_listing

        with pytest.raises(StockServiceError) as exc_info:
            service.get_sector_performance()

        assert "Failed to fetch sector performance" in str(exc_info.value)

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_get_sector_performance_with_icb_columns(self, mock_trading_cls, mock_listing_cls, service):
        """Test sector grouping off the industry_name column."""
        symbols_df = pd.DataFrame({
            'symbol': ['VCB', 'ACB'],
            'industry_code': ['11', '11'],
            'industry_name': ['Ngan hang', 'Ngan hang'],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = symbols_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['VCB', 'ACB'],
            'match_price': [101.0, 25.5],
            'ref_price': [100.0, 25.0],
            'accumulated_value': [100e9, 50e9],
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.total_sectors == 1
        assert result.sectors[0].icb_name == 'Ngan hang'
        assert result.sectors[0].icb_code == '11'

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_get_sector_performance_nan_sector_skipped(self, mock_trading_cls, mock_listing_cls, service):
        """Test handling of NaN sector names - they should be skipped."""
        symbols_df = pd.DataFrame({
            'symbol': ['VCB', 'ACB', 'XXX'],
            'industry_code': ['11', '11', None],
            'industry_name': ['Ngan hang', 'Ngan hang', None],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = symbols_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['VCB', 'ACB', 'XXX'],
            'match_price': [101.0, 25.5, 10.0],
            'ref_price': [100.0, 25.0, 10.0],
            'accumulated_value': [100e9, 50e9, 1e9],
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        # Should only have 1 sector (NaN sector name skipped)
        assert result.total_sectors == 1


# === Market-Cap Weighted Calculation Tests ===


class TestMarketCapWeightedCalculation:
    """Test change calculation and top gainers/losers logic."""

    @pytest.fixture
    def service(self):
        return StockService(source="VCI")

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_change_calculation_accuracy(self, mock_trading_cls, mock_listing_cls, service):
        """Test change percentage calculation is accurate."""
        symbols_df = pd.DataFrame({
            'symbol': ['A', 'B'],
            'industry_code': ['1000', '1000'],
            'industry_name': ['Test Sector', 'Test Sector'],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = symbols_df
        mock_listing_cls.return_value = mock_listing

        # Stock A: 2% change (102/100), Stock B: -1% change (99/100)
        # Simple average = (2 + -1) / 2 = 0.5%
        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['A', 'B'],
            'match_price': [102.0, 99.0],
            'ref_price': [100.0, 100.0],
            'accumulated_value': [100e9, 50e9],
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        assert result.total_sectors == 1
        assert result.sectors[0].change_pct == 0.5

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_top_gainers_losers_sorting(self, mock_trading_cls, mock_listing_cls, service):
        """Test top gainers and losers are correctly sorted."""
        symbols_df = pd.DataFrame({
            'symbol': ['A', 'B', 'C', 'D', 'E'],
            'industry_code': ['1000'] * 5,
            'industry_name': ['Test'] * 5,
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = symbols_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        # +5%, +3%, 0%, -2%, -4% changes
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['A', 'B', 'C', 'D', 'E'],
            'match_price': [105.0, 103.0, 100.0, 98.0, 96.0],
            'ref_price': [100.0, 100.0, 100.0, 100.0, 100.0],
            'accumulated_value': [10e9] * 5,
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        sector = result.sectors[0]
        assert sector.top_gainers == ['A', 'B', 'C']
        assert sector.top_losers == ['C', 'D', 'E']

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_zero_accumulated_value_handling(self, mock_trading_cls, mock_listing_cls, service):
        """Test handling of zero/missing accumulated_value."""
        symbols_df = pd.DataFrame({
            'symbol': ['A', 'B'],
            'industry_code': ['1000', '1000'],
            'industry_name': ['Test', 'Test'],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = symbols_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['A', 'B'],
            'match_price': [102.0, 101.0],
            'ref_price': [100.0, 100.0],
            'accumulated_value': [0, None],  # Zero and None values
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        # Should handle gracefully
        assert isinstance(result, SectorPerformanceResponse)
        assert result.total_sectors == 1

    @patch('src.stocks.market.service.Listing')
    @patch('src.stocks.market.service.Trading')
    def test_total_market_cap_in_billions(self, mock_trading_cls, mock_listing_cls, service):
        """Test total market cap is converted to billions."""
        symbols_df = pd.DataFrame({
            'symbol': ['A'],
            'industry_code': ['1000'],
            'industry_name': ['Test'],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = symbols_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['A'],
            'match_price': [101.0],
            'ref_price': [100.0],
            # vnstock reports accumulated_value in million VND, so 150_000 of
            # them is 150 billion. Checked against a live price board: VCB
            # traded 6,522,200 shares at 59,700 VND (389.4 billion) and the
            # field came back as 392,536.84.
            'accumulated_value': [150_000],
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        assert result.sectors[0].total_market_cap == 150.0  # In billions


# === Integration Test (Optional - requires network) ===


class TestSectorPerformanceIntegration:
    """Integration tests - require network access to vnstock API."""

    @pytest.fixture
    def service(self):
        return StockService(source="VCI")

    @pytest.mark.skip(reason="Integration test - requires network")
    def test_get_sector_performance_live(self, service):
        """Test actual API call to get sector performance."""
        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.generated_at is not None
        # Should have some sectors
        if result.total_sectors > 0:
            sector = result.sectors[0]
            assert sector.icb_code is not None
            assert sector.icb_name is not None
            assert isinstance(sector.change_pct, float)
            assert isinstance(sector.stock_count, int)
