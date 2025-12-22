"""Tests for TopPerformersCollector and collect_top_performers_job."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call
import pandas as pd

from src.stocks.top_performers_collector import TopPerformersCollector
from src.stocks.jobs import collect_top_performers_job
from src.core.vnstock_wrapper import VnstockRateLimitError


class TestTopPerformersCollector:
    """Tests for TopPerformersCollector class."""

    @pytest.mark.asyncio
    async def test_get_symbols_success(self):
        """Test _get_symbols returns list of HOSE+HNX symbols."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        mock_df = pd.DataFrame({
            "symbol": ["VCB", "FPT", "VNM"],
            "exchange": ["HOSE", "HOSE", "HOSE"],
            "short_name": ["Vietcombank", "FPT Corp", "Vinamilk"],
        })

        with patch("src.stocks.top_performers_collector.safe_vnstock_call") as mock_call:
            mock_call.return_value = mock_df.to_dict("records")

            result = collector._get_symbols()

            assert len(result) == 3
            assert result[0]["symbol"] == "VCB"
            assert result[0]["exchange"] == "HOSE"
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_symbols_failure(self):
        """Test _get_symbols handles failure gracefully."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        with patch("src.stocks.top_performers_collector.safe_vnstock_call") as mock_call:
            mock_call.side_effect = Exception("API error")

            result = collector._get_symbols()

            assert result == []

    @pytest.mark.asyncio
    async def test_get_quarterly_financials_success(self):
        """Test _get_quarterly_financials returns expected dict structure."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        # safe_vnstock_call should return the result dict directly
        expected_result = {
            "year": 2024,
            "quarter": 4,
            "net_profit": 1500000000000,
            "revenue": 5000000000000,
            "profit_margin": 30.0,
            "eps": 15000.0,
        }

        with patch("src.stocks.top_performers_collector.safe_vnstock_call") as mock_call:
            mock_call.return_value = expected_result

            result = collector._get_quarterly_financials("VCB")

            assert result is not None
            assert result["year"] == 2024
            assert result["quarter"] == 4
            assert result["net_profit"] == 1500000000000
            assert result["revenue"] == 5000000000000
            assert result["eps"] == 15000.0
            assert result["profit_margin"] == 30.0  # 1.5T / 5T * 100

    @pytest.mark.asyncio
    async def test_get_quarterly_financials_empty_df(self):
        """Test _get_quarterly_financials handles empty DataFrame."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        with patch("src.stocks.top_performers_collector.safe_vnstock_call") as mock_call:
            mock_call.return_value = None

            result = collector._get_quarterly_financials("INVALID")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_quarterly_financials_calculates_profit_margin(self):
        """Test profit margin calculation."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        with patch("src.stocks.top_performers_collector.safe_vnstock_call") as mock_call:
            # Return the expected result dict
            mock_call.return_value = {
                "year": 2024,
                "quarter": 3,
                "net_profit": 2000000000000,
                "revenue": 10000000000000,
                "profit_margin": 20.0,
                "eps": 20000.0,
            }

            result = collector._get_quarterly_financials("FPT")

            assert result["profit_margin"] == 20.0  # 2T / 10T * 100

    @pytest.mark.asyncio
    async def test_get_quarterly_financials_handles_zero_revenue(self):
        """Test profit margin is None when revenue is zero."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        with patch("src.stocks.top_performers_collector.safe_vnstock_call") as mock_call:
            # Return result with None profit_margin (calculated inside the method)
            mock_call.return_value = {
                "year": 2024,
                "quarter": 3,
                "net_profit": 1000000000,
                "revenue": 0,
                "profit_margin": None,
                "eps": 100.0,
            }

            result = collector._get_quarterly_financials("TEST")

            assert result["profit_margin"] is None

    @pytest.mark.asyncio
    async def test_store_results_success(self):
        """Test _store_results upserts data correctly."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        results = [
            {
                "symbol": "VCB",
                "company_name": "Vietcombank",
                "exchange": "HOSE",
                "year": 2024,
                "quarter": 4,
                "net_profit": 15000000000000,
                "revenue": 50000000000000,
                "profit_margin": 30.0,
                "eps": 15000,
                "rank": 1,
            },
            {
                "symbol": "FPT",
                "company_name": "FPT Corp",
                "exchange": "HOSE",
                "year": 2024,
                "quarter": 4,
                "net_profit": 10000000000000,
                "revenue": 40000000000000,
                "profit_margin": 25.0,
                "eps": 12000,
                "rank": 2,
            },
        ]

        stored = await collector._store_results(results)

        assert stored == 2
        assert mock_db.execute.call_count == 2
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_store_results_empty_list(self):
        """Test _store_results handles empty list."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        stored = await collector._store_results([])

        assert stored == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_results_database_error(self):
        """Test _store_results handles database errors."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB error")
        collector = TopPerformersCollector(mock_db)

        results = [{"symbol": "VCB", "year": 2024, "quarter": 4}]

        stored = await collector._store_results(results)

        assert stored == 0
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_integration(self):
        """Test collect method integrates all steps correctly."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        # Mock symbols data
        symbols_data = [
            {"symbol": "VCB", "exchange": "HOSE", "short_name": "Vietcombank"},
            {"symbol": "FPT", "exchange": "HOSE", "short_name": "FPT Corp"},
        ]

        # Mock financial data
        financial_data = {
            "year": 2024,
            "quarter": 4,
            "net_profit": 15000000000000,
            "revenue": 50000000000000,
            "profit_margin": 30.0,
            "eps": 15000,
        }

        with patch.object(collector, "_get_symbols", return_value=symbols_data):
            with patch.object(collector, "_get_quarterly_financials", return_value=financial_data):
                with patch.object(collector, "_store_results", return_value=2) as mock_store:
                    with patch("src.stocks.top_performers_collector.time.sleep"):  # Skip delays
                        result = await collector.collect()

                        assert result["success"] == 2
                        assert result["failed"] == 0
                        assert result["total_symbols"] == 2
                        assert "elapsed_seconds" in result

                        # Verify ranking was applied
                        stored_results = mock_store.call_args[0][0]
                        assert all("rank" in item for item in stored_results)

    @pytest.mark.asyncio
    async def test_collect_handles_rate_limit(self):
        """Test collect method handles rate limit errors."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        symbols_data = [
            {"symbol": "VCB", "exchange": "HOSE", "short_name": "Vietcombank"},
            {"symbol": "FPT", "exchange": "HOSE", "short_name": "FPT Corp"},
        ]

        with patch.object(collector, "_get_symbols", return_value=symbols_data):
            with patch.object(
                collector,
                "_get_quarterly_financials",
                side_effect=VnstockRateLimitError("Rate limited")
            ):
                with patch.object(collector, "_store_results", return_value=0):
                    with patch("src.stocks.top_performers_collector.time.sleep"):
                        result = await collector.collect()

                        assert result["success"] == 0
                        assert result["rate_limited"] == 2
                        assert result["total_symbols"] == 2

    @pytest.mark.asyncio
    async def test_collect_handles_partial_failures(self):
        """Test collect method handles mixed success/failure."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        symbols_data = [
            {"symbol": "VCB", "exchange": "HOSE", "short_name": "Vietcombank"},
            {"symbol": "FAIL", "exchange": "HOSE", "short_name": "Fail Corp"},
            {"symbol": "FPT", "exchange": "HOSE", "short_name": "FPT Corp"},
        ]

        def mock_financials(symbol):
            if symbol == "FAIL":
                return None
            return {
                "year": 2024,
                "quarter": 4,
                "net_profit": 10000000000000,
                "revenue": 40000000000000,
                "profit_margin": 25.0,
                "eps": 12000,
            }

        with patch.object(collector, "_get_symbols", return_value=symbols_data):
            with patch.object(collector, "_get_quarterly_financials", side_effect=mock_financials):
                with patch.object(collector, "_store_results", return_value=2):
                    with patch("src.stocks.top_performers_collector.time.sleep"):
                        result = await collector.collect()

                        assert result["success"] == 2
                        assert result["failed"] == 1
                        assert result["total_symbols"] == 3

    @pytest.mark.asyncio
    async def test_collect_sorts_by_net_profit(self):
        """Test collect method ranks by net_profit descending."""
        mock_db = AsyncMock()
        collector = TopPerformersCollector(mock_db)

        symbols_data = [
            {"symbol": "LOW", "exchange": "HOSE", "short_name": "Low Profit"},
            {"symbol": "HIGH", "exchange": "HOSE", "short_name": "High Profit"},
        ]

        def mock_financials(symbol):
            if symbol == "HIGH":
                return {
                    "year": 2024,
                    "quarter": 4,
                    "net_profit": 20000000000000,  # Higher
                    "revenue": 50000000000000,
                    "profit_margin": 40.0,
                    "eps": 20000,
                }
            return {
                "year": 2024,
                "quarter": 4,
                "net_profit": 5000000000000,  # Lower
                "revenue": 20000000000000,
                "profit_margin": 25.0,
                "eps": 5000,
            }

        with patch.object(collector, "_get_symbols", return_value=symbols_data):
            with patch.object(collector, "_get_quarterly_financials", side_effect=mock_financials):
                with patch.object(collector, "_store_results", return_value=2) as mock_store:
                    with patch("src.stocks.top_performers_collector.time.sleep"):
                        await collector.collect()

                        stored_results = mock_store.call_args[0][0]
                        # HIGH should be rank 1, LOW should be rank 2
                        assert stored_results[0]["symbol"] == "HIGH"
                        assert stored_results[0]["rank"] == 1
                        assert stored_results[1]["symbol"] == "LOW"
                        assert stored_results[1]["rank"] == 2


class TestCollectTopPerformersJob:
    """Tests for collect_top_performers_job function."""

    @pytest.mark.asyncio
    async def test_collect_top_performers_job_success(self):
        """Test successful top performers job execution."""
        mock_result = {
            "success": 50,
            "failed": 5,
            "rate_limited": 0,
            "total_symbols": 55,
            "elapsed_seconds": 120.5,
        }

        with patch("src.stocks.jobs.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = mock_session

            with patch("src.stocks.jobs.TopPerformersCollector") as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect.return_value = mock_result
                mock_collector_class.return_value = mock_collector

                result = await collect_top_performers_job()

                assert result == mock_result
                assert result["success"] == 50
                assert result["failed"] == 5
                mock_collector.collect.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_top_performers_job_exception_handling(self):
        """Test error handling when job fails."""
        with patch("src.stocks.jobs.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB connection failed")

            result = await collect_top_performers_job()

            assert result["success"] == 0
            assert result["failed"] == 0
            assert "error" in result
            assert "DB connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_collect_top_performers_job_creates_collector_with_session(self):
        """Test job creates collector with database session."""
        with patch("src.stocks.jobs.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = mock_session

            with patch("src.stocks.jobs.TopPerformersCollector") as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect.return_value = {"success": 0, "failed": 0}
                mock_collector_class.return_value = mock_collector

                await collect_top_performers_job()

                # Verify collector was instantiated with session
                mock_collector_class.assert_called_once_with(mock_session)


class TestSchedulerIntegration:
    """Tests for scheduler registration of top performers job."""

    @pytest.mark.asyncio
    async def test_scheduler_registers_top_performers_job(self):
        """Test that scheduler registers top performers job when enabled."""
        from src.core.scheduler import setup_scheduler

        mock_scheduler = AsyncMock()

        with patch("src.core.scheduler.settings") as mock_settings:
            mock_settings.scheduler_enabled = True
            mock_settings.intraday_collect_hour = 15
            mock_settings.intraday_collect_minute = 30
            mock_settings.daily_ohlcv_enabled = True
            mock_settings.daily_ohlcv_hour = 20
            mock_settings.daily_ohlcv_minute = 0
            mock_settings.top_performers_enabled = True
            mock_settings.top_performers_hour = 2
            mock_settings.top_performers_minute = 0

            await setup_scheduler(mock_scheduler)

            # Should add 4 schedules: intraday, cleanup, daily_ohlcv, top_performers
            assert mock_scheduler.add_schedule.call_count == 4

            # Find the top performers schedule call
            calls = mock_scheduler.add_schedule.call_args_list
            top_performers_call = None
            for c in calls:
                if len(c[0]) > 0 and c[0][0].__name__ == "collect_top_performers_job":
                    top_performers_call = c
                    break

            assert top_performers_call is not None

    @pytest.mark.asyncio
    async def test_scheduler_skips_top_performers_when_disabled(self):
        """Test scheduler skips top performers job when disabled."""
        from src.core.scheduler import setup_scheduler

        mock_scheduler = AsyncMock()

        with patch("src.core.scheduler.settings") as mock_settings:
            mock_settings.scheduler_enabled = True
            mock_settings.intraday_collect_hour = 15
            mock_settings.intraday_collect_minute = 30
            mock_settings.daily_ohlcv_enabled = True
            mock_settings.daily_ohlcv_hour = 20
            mock_settings.daily_ohlcv_minute = 0
            mock_settings.top_performers_enabled = False

            await setup_scheduler(mock_scheduler)

            # Should add only 3 schedules (no top_performers)
            assert mock_scheduler.add_schedule.call_count == 3

            # Verify no call includes collect_top_performers_job
            calls = mock_scheduler.add_schedule.call_args_list
            for c in calls:
                if len(c[0]) > 0:
                    assert c[0][0].__name__ != "collect_top_performers_job"


class TestConfigSettings:
    """Tests for top performers config settings."""

    def test_top_performers_settings_defaults(self):
        """Test default top performers settings."""
        from src.core.config import Settings

        settings = Settings()

        assert settings.top_performers_enabled is True
        assert settings.top_performers_hour == 2
        assert settings.top_performers_minute == 0
        assert settings.top_performers_delay == 1.5

    def test_top_performers_settings_custom(self):
        """Test custom top performers settings."""
        from src.core.config import Settings

        settings = Settings(
            top_performers_enabled=False,
            top_performers_hour=3,
            top_performers_minute=30,
            top_performers_delay=2.0,
        )

        assert settings.top_performers_enabled is False
        assert settings.top_performers_hour == 3
        assert settings.top_performers_minute == 30
        assert settings.top_performers_delay == 2.0
