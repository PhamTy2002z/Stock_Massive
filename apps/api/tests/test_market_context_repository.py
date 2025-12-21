"""Unit tests for market context repository."""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.stocks.market_context_repository import MarketContextRepository
from src.stocks.models import SectorDailyBenchmark, StockDailyReturn, StockMarketMetric


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def repository(mock_db):
    """Create repository with mock db."""
    return MarketContextRepository(mock_db)


class TestStockDailyReturnRepository:
    """Tests for daily return operations."""

    def test_upsert_daily_return_insert(self, repository, mock_db):
        """Test inserting new daily return."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = repository.upsert_daily_return(
            symbol="VCB",
            target_date=date(2025, 1, 1),
            close_price=100.0,
            return_1d=0.02,
            return_1d_log=0.0198,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_upsert_daily_return_update(self, repository, mock_db):
        """Test updating existing daily return."""
        existing = StockDailyReturn(
            symbol="VCB",
            date=date(2025, 1, 1),
            close_price=Decimal("99.0"),
            return_1d=Decimal("0.01"),
            return_1d_log=Decimal("0.00995"),
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing

        repository.upsert_daily_return(
            symbol="VCB",
            target_date=date(2025, 1, 1),
            close_price=100.0,
            return_1d=0.02,
            return_1d_log=0.0198,
        )

        assert existing.close_price == 100.0
        assert existing.return_1d == 0.02
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()

    def test_get_daily_returns(self, repository, mock_db):
        """Test fetching daily returns for date range."""
        mock_returns = [
            StockDailyReturn(symbol="VCB", date=date(2025, 1, 1), close_price=Decimal("100")),
            StockDailyReturn(symbol="VCB", date=date(2025, 1, 2), close_price=Decimal("102")),
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_returns

        result = repository.get_daily_returns("VCB", date(2025, 1, 1), date(2025, 1, 2))

        assert len(result) == 2
        assert result[0].symbol == "VCB"

    def test_get_daily_return_single(self, repository, mock_db):
        """Test fetching single daily return."""
        mock_return = StockDailyReturn(
            symbol="VCB", date=date(2025, 1, 1), close_price=Decimal("100")
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_return

        result = repository.get_daily_return("VCB", date(2025, 1, 1))

        assert result is not None
        assert result.symbol == "VCB"


class TestStockMarketMetricRepository:
    """Tests for market metric operations."""

    def test_upsert_market_metric_insert(self, repository, mock_db):
        """Test inserting new market metric."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        repository.upsert_market_metric(
            symbol="VCB",
            target_date=date(2025, 1, 1),
            corr_20d=0.85,
            beta_20d=1.2,
            rs_market_20d=1.05,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_upsert_market_metric_update(self, repository, mock_db):
        """Test updating existing market metric."""
        existing = StockMarketMetric(
            symbol="VCB",
            date=date(2025, 1, 1),
            corr_20d=Decimal("0.80"),
            beta_20d=Decimal("1.1"),
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing

        repository.upsert_market_metric(
            symbol="VCB",
            target_date=date(2025, 1, 1),
            corr_20d=0.85,
            beta_20d=1.2,
        )

        assert existing.corr_20d == 0.85
        assert existing.beta_20d == 1.2
        mock_db.add.assert_not_called()

    def test_get_latest_metric(self, repository, mock_db):
        """Test fetching latest metric for symbol."""
        mock_metric = StockMarketMetric(
            symbol="VCB",
            date=date(2025, 1, 5),
            corr_20d=Decimal("0.85"),
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_metric

        result = repository.get_latest_metric("VCB")

        assert result is not None
        assert result.date == date(2025, 1, 5)

    def test_get_market_metrics_range(self, repository, mock_db):
        """Test fetching market metrics for date range."""
        mock_metrics = [
            StockMarketMetric(symbol="VCB", date=date(2025, 1, 1)),
            StockMarketMetric(symbol="VCB", date=date(2025, 1, 2)),
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_metrics

        result = repository.get_market_metrics("VCB", date(2025, 1, 1), date(2025, 1, 2))

        assert len(result) == 2


class TestSectorDailyBenchmarkRepository:
    """Tests for sector benchmark operations."""

    def test_upsert_sector_benchmark_insert(self, repository, mock_db):
        """Test inserting new sector benchmark."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        repository.upsert_sector_benchmark(
            icb_code="8355",
            target_date=date(2025, 1, 1),
            mcap_weighted_return=0.015,
            total_mcap=1000000000000,
            stock_count=27,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_upsert_sector_benchmark_update(self, repository, mock_db):
        """Test updating existing sector benchmark."""
        existing = SectorDailyBenchmark(
            icb_code="8355",
            date=date(2025, 1, 1),
            mcap_weighted_return=Decimal("0.01"),
            total_mcap=900000000000,
            stock_count=26,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing

        repository.upsert_sector_benchmark(
            icb_code="8355",
            target_date=date(2025, 1, 1),
            mcap_weighted_return=0.015,
            total_mcap=1000000000000,
            stock_count=27,
        )

        assert existing.mcap_weighted_return == 0.015
        assert existing.stock_count == 27
        mock_db.add.assert_not_called()

    def test_get_sector_benchmark_range(self, repository, mock_db):
        """Test fetching sector benchmarks for date range."""
        mock_benchmarks = [
            SectorDailyBenchmark(
                icb_code="8355",
                date=date(2025, 1, 1),
                mcap_weighted_return=Decimal("0.01"),
                total_mcap=1000000000000,
                stock_count=27,
            ),
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_benchmarks

        result = repository.get_sector_benchmark("8355", date(2025, 1, 1), date(2025, 1, 1))

        assert len(result) == 1
        assert result[0].icb_code == "8355"

    def test_get_sector_benchmark_single(self, repository, mock_db):
        """Test fetching single sector benchmark."""
        mock_benchmark = SectorDailyBenchmark(
            icb_code="8355",
            date=date(2025, 1, 1),
            mcap_weighted_return=Decimal("0.015"),
            total_mcap=1000000000000,
            stock_count=27,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_benchmark

        result = repository.get_sector_benchmark_single("8355", date(2025, 1, 1))

        assert result is not None
        assert result.stock_count == 27


class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_stock_daily_return_schema(self):
        """Test StockDailyReturnSchema validation."""
        from src.stocks.schemas.market_context import StockDailyReturnSchema

        schema = StockDailyReturnSchema(
            symbol="VCB",
            date=date(2025, 1, 1),
            close_price=100.0,
            return_1d=0.02,
            return_1d_log=0.0198,
        )

        assert schema.symbol == "VCB"
        assert schema.close_price == 100.0

    def test_stock_market_metric_schema(self):
        """Test StockMarketMetricSchema validation."""
        from src.stocks.schemas.market_context import StockMarketMetricSchema

        schema = StockMarketMetricSchema(
            symbol="VCB",
            date=date(2025, 1, 1),
            corr_20d=0.85,
            beta_20d=1.2,
        )

        assert schema.corr_20d == 0.85
        assert schema.sector_rank is None  # Optional field

    def test_sector_daily_benchmark_schema(self):
        """Test SectorDailyBenchmarkSchema validation."""
        from src.stocks.schemas.market_context import SectorDailyBenchmarkSchema

        schema = SectorDailyBenchmarkSchema(
            icb_code="8355",
            date=date(2025, 1, 1),
            mcap_weighted_return=0.015,
            total_mcap=1000000000000,
            stock_count=27,
        )

        assert schema.icb_code == "8355"
        assert schema.stock_count == 27
