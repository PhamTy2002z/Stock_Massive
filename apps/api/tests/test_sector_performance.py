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
    def mock_industries_df(self):
        """Mock industries DataFrame."""
        return pd.DataFrame({
            'symbol': ['VCB', 'ACB', 'TCB', 'VNM', 'MSN', 'HPG', 'HSG'],
            'icb_code2': ['8000', '8000', '8000', '5000', '5000', '2000', '2000'],
            'icb_name2': ['Tai chinh', 'Tai chinh', 'Tai chinh', 'Hang tieu dung', 'Hang tieu dung', 'Vat lieu co ban', 'Vat lieu co ban'],
        })

    @pytest.fixture
    def mock_price_board_df(self):
        """Mock price board DataFrame."""
        return pd.DataFrame({
            'symbol': ['VCB', 'ACB', 'TCB'],
            'change_pct': [1.5, 2.0, -0.5],
            'accumulated_value': [100_000_000_000, 50_000_000_000, 30_000_000_000],
        })

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_get_sector_performance_success(self, mock_trading_cls, mock_listing_cls, service, mock_industries_df):
        """Test successful sector performance retrieval."""
        # Setup mocks
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = mock_industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        # Return different price boards for different sectors
        def price_board_side_effect(symbols_list, **kwargs):
            if 'VCB' in symbols_list:
                return pd.DataFrame({
                    'symbol': ['VCB', 'ACB', 'TCB'],
                    'change_pct': [1.5, 2.0, -0.5],
                    'accumulated_value': [100e9, 50e9, 30e9],
                })
            elif 'VNM' in symbols_list:
                return pd.DataFrame({
                    'symbol': ['VNM', 'MSN'],
                    'change_pct': [0.8, 1.2],
                    'accumulated_value': [80e9, 40e9],
                })
            elif 'HPG' in symbols_list:
                return pd.DataFrame({
                    'symbol': ['HPG', 'HSG'],
                    'change_pct': [-1.0, -2.0],
                    'accumulated_value': [60e9, 20e9],
                })
            return pd.DataFrame()

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

    @patch('src.stocks.service.Listing')
    def test_get_sector_performance_empty_industries(self, mock_listing_cls, service):
        """Test with empty industries DataFrame."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = pd.DataFrame()
        mock_listing_cls.return_value = mock_listing

        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.sectors == []
        assert result.total_sectors == 0

    @patch('src.stocks.service.Listing')
    def test_get_sector_performance_none_industries(self, mock_listing_cls, service):
        """Test with None industries DataFrame."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = None
        mock_listing_cls.return_value = mock_listing

        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.sectors == []
        assert result.total_sectors == 0

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_get_sector_performance_empty_price_board(self, mock_trading_cls, mock_listing_cls, service, mock_industries_df):
        """Test with empty price board response."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = mock_industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame()
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.sectors == []
        assert result.total_sectors == 0

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_get_sector_performance_price_board_exception(self, mock_trading_cls, mock_listing_cls, service, mock_industries_df):
        """Test graceful handling of price board exceptions."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = mock_industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.side_effect = Exception("API Error")
        mock_trading_cls.return_value = mock_trading

        # Should not raise, just return empty sectors
        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.sectors == []

    @patch('src.stocks.service.Listing')
    def test_get_sector_performance_listing_exception(self, mock_listing_cls, service):
        """Test exception from Listing API raises StockServiceError."""
        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.side_effect = Exception("Network Error")
        mock_listing_cls.return_value = mock_listing

        with pytest.raises(StockServiceError) as exc_info:
            service.get_sector_performance()

        assert "Failed to fetch sector performance" in str(exc_info.value)

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_get_sector_performance_alternative_columns(self, mock_trading_cls, mock_listing_cls, service):
        """Test with alternative column names (icb_code instead of icb_code2)."""
        # Use icb_code/icb_name instead of icb_code2/icb_name2
        industries_df = pd.DataFrame({
            'symbol': ['VCB', 'ACB'],
            'icb_code': ['8000', '8000'],
            'icb_name': ['Tai chinh', 'Tai chinh'],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['VCB', 'ACB'],
            'change_pct': [1.0, 2.0],
            'accumulated_value': [100e9, 50e9],
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        assert isinstance(result, SectorPerformanceResponse)
        assert result.total_sectors == 1
        assert result.sectors[0].icb_code == '8000'
        assert result.sectors[0].icb_name == 'Tai chinh'

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_get_sector_performance_nan_icb_code(self, mock_trading_cls, mock_listing_cls, service):
        """Test handling of NaN ICB codes."""
        industries_df = pd.DataFrame({
            'symbol': ['VCB', 'ACB', 'XXX'],
            'icb_code2': ['8000', '8000', None],
            'icb_name2': ['Tai chinh', 'Tai chinh', None],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['VCB', 'ACB'],
            'change_pct': [1.0, 2.0],
            'accumulated_value': [100e9, 50e9],
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        # Should only have 1 sector (NaN icb_code skipped)
        assert result.total_sectors == 1


# === Market-Cap Weighted Calculation Tests ===


class TestMarketCapWeightedCalculation:
    """Test market-cap weighted change calculation logic."""

    @pytest.fixture
    def service(self):
        return StockService(source="VCI")

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_weighted_calculation_accuracy(self, mock_trading_cls, mock_listing_cls, service):
        """Test market-cap weighted calculation is accurate."""
        industries_df = pd.DataFrame({
            'symbol': ['A', 'B'],
            'icb_code2': ['1000', '1000'],
            'icb_name2': ['Test Sector', 'Test Sector'],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = industries_df
        mock_listing_cls.return_value = mock_listing

        # Stock A: 2% change, 100B market cap
        # Stock B: -1% change, 50B market cap
        # Weighted avg = (2*100 + -1*50) / (100+50) = 150/150 = 1.0%
        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['A', 'B'],
            'change_pct': [2.0, -1.0],
            'accumulated_value': [100e9, 50e9],
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        assert result.total_sectors == 1
        assert result.sectors[0].change_pct == 1.0

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_top_gainers_losers_sorting(self, mock_trading_cls, mock_listing_cls, service):
        """Test top gainers and losers are correctly sorted."""
        industries_df = pd.DataFrame({
            'symbol': ['A', 'B', 'C', 'D', 'E'],
            'icb_code2': ['1000'] * 5,
            'icb_name2': ['Test'] * 5,
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['A', 'B', 'C', 'D', 'E'],
            'change_pct': [5.0, 3.0, 0.0, -2.0, -4.0],
            'accumulated_value': [10e9] * 5,
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        sector = result.sectors[0]
        assert sector.top_gainers == ['A', 'B', 'C']
        assert sector.top_losers == ['C', 'D', 'E']

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_zero_market_cap_handling(self, mock_trading_cls, mock_listing_cls, service):
        """Test handling of zero/missing market cap values."""
        industries_df = pd.DataFrame({
            'symbol': ['A', 'B'],
            'icb_code2': ['1000', '1000'],
            'icb_name2': ['Test', 'Test'],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['A', 'B'],
            'change_pct': [2.0, 1.0],
            'accumulated_value': [0, None],  # Zero and None values
        })
        mock_trading_cls.return_value = mock_trading

        result = service.get_sector_performance()

        # Should handle gracefully - uses default 1.0 for missing market cap
        assert isinstance(result, SectorPerformanceResponse)

    @patch('src.stocks.service.Listing')
    @patch('src.stocks.service.Trading')
    def test_total_market_cap_in_billions(self, mock_trading_cls, mock_listing_cls, service):
        """Test total market cap is converted to billions."""
        industries_df = pd.DataFrame({
            'symbol': ['A'],
            'icb_code2': ['1000'],
            'icb_name2': ['Test'],
        })

        mock_listing = MagicMock()
        mock_listing.symbols_by_industries.return_value = industries_df
        mock_listing_cls.return_value = mock_listing

        mock_trading = MagicMock()
        mock_trading.price_board.return_value = pd.DataFrame({
            'symbol': ['A'],
            'change_pct': [1.0],
            'accumulated_value': [150_000_000_000],  # 150 billion
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
