"""Tests for market overview endpoint."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.stocks.overview.schemas import (
    ForeignFlowData,
    ForeignFlowItem,
    MarketBreadth,
    MarketOverviewResponse,
    TopMoverItem,
    TopVolumeItem,
)
from src.stocks.overview.service import MarketOverviewService


class TestMarketOverviewSchemas:
    """Test Pydantic schemas validation."""

    def test_market_breadth_schema(self):
        """Test MarketBreadth schema."""
        data = MarketBreadth(
            advances=150,
            declines=80,
            unchanged=20,
            total=250,
        )
        assert data.advances == 150
        assert data.declines == 80
        assert data.unchanged == 20
        assert data.total == 250

    def test_top_mover_item_schema(self):
        """Test TopMoverItem schema."""
        data = TopMoverItem(
            symbol="VCB",
            price=95000.0,
            change_pct=3.5,
            volume=1000000,
        )
        assert data.symbol == "VCB"
        assert data.price == 95000.0
        assert data.change_pct == 3.5
        assert data.volume == 1000000

    def test_top_mover_item_optional_volume(self):
        """Test TopMoverItem with None volume."""
        data = TopMoverItem(
            symbol="VCB",
            price=95000.0,
            change_pct=3.5,
        )
        assert data.volume is None

    def test_foreign_flow_item_schema(self):
        """Test ForeignFlowItem schema."""
        data = ForeignFlowItem(symbol="VCB", net_value=50000000000.0)
        assert data.symbol == "VCB"
        assert data.net_value == 50000000000.0

    def test_foreign_flow_data_schema(self):
        """Test ForeignFlowData schema."""
        data = ForeignFlowData(
            net_buy=[
                ForeignFlowItem(symbol="VCB", net_value=50000000000.0),
                ForeignFlowItem(symbol="VNM", net_value=30000000000.0),
            ],
            net_sell=[
                ForeignFlowItem(symbol="HPG", net_value=-20000000000.0),
            ],
            total_net_value=60000000000.0,
        )
        assert len(data.net_buy) == 2
        assert len(data.net_sell) == 1
        assert data.total_net_value == 60000000000.0

    def test_top_volume_item_schema(self):
        """Test TopVolumeItem schema."""
        data = TopVolumeItem(
            symbol="VCB",
            price=95000.0,
            volume=5000000,
            value=475000000000.0,
        )
        assert data.symbol == "VCB"
        assert data.price == 95000.0
        assert data.volume == 5000000
        assert data.value == 475000000000.0

    def test_market_overview_response_schema(self):
        """Test complete MarketOverviewResponse schema."""
        now = datetime.now()
        data = MarketOverviewResponse(
            market_breadth=MarketBreadth(
                advances=150, declines=80, unchanged=20, total=250
            ),
            top_gainers=[
                TopMoverItem(symbol="VCB", price=95000.0, change_pct=3.5),
            ],
            top_losers=[
                TopMoverItem(symbol="HPG", price=45000.0, change_pct=-2.1),
            ],
            foreign_flow=ForeignFlowData(
                net_buy=[ForeignFlowItem(symbol="VCB", net_value=50000000000.0)],
                net_sell=[],
                total_net_value=50000000000.0,
            ),
            top_volume=[
                TopVolumeItem(
                    symbol="VCB", price=95000.0, volume=5000000, value=475000000000.0
                ),
            ],
            generated_at=now,
        )
        assert data.market_breadth.total == 250
        assert len(data.top_gainers) == 1
        assert len(data.top_losers) == 1
        assert data.generated_at == now


class TestMarketOverviewServiceParsing:
    """Test MarketOverviewService parsing methods."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return MarketOverviewService(source="VCI")

    def _create_mock_gainer_df(self):
        """Create mock DataFrame for gainers."""
        return pd.DataFrame(
            {
                "symbol": ["VCB", "VNM", "HPG", "VIC", "GAS"],
                "last_price": [95000, 85000, 45000, 55000, 75000],
                "price_change_pct_1d": [3.5, 2.8, 2.1, 1.9, 1.5],
                "accumulated_volume": [1000000, 800000, 1200000, 600000, 500000],
            }
        )

    def _create_mock_foreign_buy_df(self):
        """Create mock DataFrame for foreign buy."""
        return pd.DataFrame(
            {
                "symbol": ["VCB", "VNM", "HPG", "VIC", "GAS"],
                "net_value": [
                    50000000000,
                    30000000000,
                    20000000000,
                    15000000000,
                    10000000000,
                ],
            }
        )

    def _create_mock_foreign_sell_df(self):
        """Create mock DataFrame for foreign sell."""
        return pd.DataFrame(
            {
                "symbol": ["MSN", "MWG", "TCB", "ACB", "CTG"],
                "net_value": [
                    -40000000000,
                    -25000000000,
                    -15000000000,
                    -10000000000,
                    -5000000000,
                ],
            }
        )

    def _create_mock_volume_df(self):
        """Create mock DataFrame for top volume."""
        return pd.DataFrame(
            {
                "symbol": ["VCB", "HPG", "MSN", "VNM", "VIC"],
                "last_price": [95000, 45000, 65000, 85000, 55000],
                "accumulated_volume": [5000000, 4500000, 4000000, 3500000, 3000000],
                "accumulated_value": [
                    475000000000,
                    202500000000,
                    260000000000,
                    297500000000,
                    165000000000,
                ],
            }
        )

    def test_parse_movers_valid_data(self, service):
        """Test parsing movers DataFrame."""
        df = self._create_mock_gainer_df()
        result = service._parse_movers(df)

        assert len(result) == 5
        assert result[0].symbol == "VCB"
        assert result[0].price == 95000.0
        assert result[0].change_pct == 3.5
        assert result[0].volume == 1000000

    def test_parse_movers_empty_df(self, service):
        """Test parsing empty DataFrame."""
        df = pd.DataFrame()
        result = service._parse_movers(df)
        assert result == []

    def test_parse_movers_none_df(self, service):
        """Test parsing None DataFrame."""
        result = service._parse_movers(None)
        assert result == []

    def test_parse_movers_missing_columns(self, service):
        """Test parsing DataFrame with missing optional columns."""
        df = pd.DataFrame(
            {
                "symbol": ["VCB"],
                "last_price": [95000],
                "price_change_pct_1d": [3.5],
                # accumulated_volume missing
            }
        )
        result = service._parse_movers(df)

        assert len(result) == 1
        assert result[0].symbol == "VCB"
        assert result[0].volume is None

    def test_parse_foreign_both_dfs_valid(self, service):
        """Test parsing foreign flow with both buy and sell data."""
        buy_df = self._create_mock_foreign_buy_df()
        sell_df = self._create_mock_foreign_sell_df()

        result = service._parse_foreign(buy_df, sell_df)

        assert len(result.net_buy) == 5
        assert len(result.net_sell) == 5
        assert result.net_buy[0].symbol == "VCB"
        assert result.net_buy[0].net_value == 50000000000.0
        assert result.total_net_value == 30000000000.0  # 125B - 95B

    def test_parse_foreign_only_buy(self, service):
        """Test parsing foreign flow with only buy data."""
        buy_df = self._create_mock_foreign_buy_df()

        result = service._parse_foreign(buy_df, None)

        assert len(result.net_buy) == 5
        assert len(result.net_sell) == 0
        assert result.total_net_value == 125000000000.0

    def test_parse_foreign_only_sell(self, service):
        """Test parsing foreign flow with only sell data."""
        sell_df = self._create_mock_foreign_sell_df()

        result = service._parse_foreign(None, sell_df)

        assert len(result.net_buy) == 0
        assert len(result.net_sell) == 5
        assert result.total_net_value == -95000000000.0

    def test_parse_foreign_both_none(self, service):
        """Test parsing foreign flow with both None."""
        result = service._parse_foreign(None, None)

        assert len(result.net_buy) == 0
        assert len(result.net_sell) == 0
        assert result.total_net_value == 0

    def test_parse_volume_valid_data(self, service):
        """Test parsing volume DataFrame."""
        df = self._create_mock_volume_df()
        result = service._parse_volume(df)

        assert len(result) == 5
        assert result[0].symbol == "VCB"
        assert result[0].price == 95000.0
        assert result[0].volume == 5000000
        assert result[0].value == 475000000000.0

    def test_parse_volume_empty_df(self, service):
        """Test parsing empty volume DataFrame."""
        df = pd.DataFrame()
        result = service._parse_volume(df)
        assert result == []

    def test_parse_volume_none_df(self, service):
        """Test parsing None volume DataFrame."""
        result = service._parse_volume(None)
        assert result == []


class TestMarketOverviewAPI:
    """Test market overview API endpoint."""

    @pytest.mark.asyncio
    async def test_get_market_overview_endpoint_success(self, client):
        """Test GET /api/v1/stocks/market-overview endpoint returns valid data."""
        with patch(
            "src.stocks.overview.router.MarketOverviewService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service

            # Mock service response
            mock_response = MarketOverviewResponse(
                market_breadth=MarketBreadth(
                    advances=150, declines=80, unchanged=20, total=250
                ),
                top_gainers=[
                    TopMoverItem(
                        symbol="VCB", price=95000.0, change_pct=3.5, volume=1000000
                    ),
                ],
                top_losers=[
                    TopMoverItem(
                        symbol="MSN", price=65000.0, change_pct=-3.2, volume=900000
                    ),
                ],
                foreign_flow=ForeignFlowData(
                    net_buy=[ForeignFlowItem(symbol="VCB", net_value=50000000000.0)],
                    net_sell=[ForeignFlowItem(symbol="MSN", net_value=-40000000000.0)],
                    total_net_value=10000000000.0,
                ),
                top_volume=[
                    TopVolumeItem(
                        symbol="VCB",
                        price=95000.0,
                        volume=5000000,
                        value=475000000000.0,
                    ),
                ],
                generated_at=datetime.now(),
            )
            mock_service.get_market_overview.return_value = mock_response

            response = client.get("/api/v1/stocks/market-overview")

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "market_breadth" in data
            assert "top_gainers" in data
            assert "top_losers" in data
            assert "foreign_flow" in data
            assert "top_volume" in data
            assert "generated_at" in data

            # Verify data content
            assert data["market_breadth"]["total"] == 250
            assert len(data["top_gainers"]) == 1
            assert data["top_gainers"][0]["symbol"] == "VCB"
            assert len(data["top_losers"]) == 1
            assert len(data["foreign_flow"]["net_buy"]) == 1
            assert len(data["top_volume"]) == 1

    @pytest.mark.asyncio
    async def test_get_market_overview_endpoint_cache_behavior(self, client):
        """Test cache behavior on multiple requests."""
        with patch(
            "src.stocks.overview.router.overview_cache"
        ) as mock_cache:
            with patch(
                "src.stocks.overview.router.MarketOverviewService"
            ) as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service

                # Cache miss scenario
                mock_cache.get.return_value = None

                mock_response = MarketOverviewResponse(
                    market_breadth=MarketBreadth(
                        advances=150, declines=80, unchanged=20, total=250
                    ),
                    top_gainers=[],
                    top_losers=[],
                    foreign_flow=ForeignFlowData(
                        net_buy=[], net_sell=[], total_net_value=0
                    ),
                    top_volume=[],
                    generated_at=datetime.now(),
                )
                mock_service.get_market_overview.return_value = mock_response

                response = client.get("/api/v1/stocks/market-overview")

                assert response.status_code == 200
                # Service should be called on cache miss
                mock_service.get_market_overview.assert_called_once()
                # Cache set should be called
                mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_market_overview_endpoint_partial_data(self, client):
        """Test endpoint returns partial data gracefully."""
        with patch(
            "src.stocks.overview.router.MarketOverviewService"
        ) as mock_service_class:
            with patch("src.stocks.overview.router.overview_cache") as mock_cache:
                mock_cache.get.return_value = None

                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service

                # Mock partial response (some sections empty)
                mock_response = MarketOverviewResponse(
                    market_breadth=MarketBreadth(
                        advances=0, declines=0, unchanged=0, total=0
                    ),
                    top_gainers=[],
                    top_losers=[],
                    foreign_flow=ForeignFlowData(
                        net_buy=[], net_sell=[], total_net_value=0
                    ),
                    top_volume=[
                        TopVolumeItem(
                            symbol="VCB",
                            price=95000.0,
                            volume=5000000,
                            value=475000000000.0,
                        ),
                    ],
                    generated_at=datetime.now(),
                )
                mock_service.get_market_overview.return_value = mock_response

                response = client.get("/api/v1/stocks/market-overview")

                assert response.status_code == 200
                data = response.json()

                # Verify empty sections
                assert data["market_breadth"]["total"] == 0
                assert len(data["top_gainers"]) == 0
                assert len(data["top_losers"]) == 0
                # But volume has data
                assert len(data["top_volume"]) == 1
