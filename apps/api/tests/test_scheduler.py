"""Tests for scheduler module and job functions."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.config import Settings
from src.stocks.jobs import collect_intraday_data_job, cleanup_old_data_job


class TestCollectIntradayDataJob:
    """Tests for collect_intraday_data_job function."""

    @pytest.mark.asyncio
    async def test_collect_intraday_data_job_success(self):
        """Test successful intraday data collection."""
        mock_result = {
            "success": ["VCB", "FPT"],
            "failed": [],
            "total_bars": 100,
        }

        with patch("src.stocks.jobs.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = mock_session

            with patch("src.stocks.jobs.IntradayCollector") as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect_and_save.return_value = mock_result
                mock_collector_class.return_value = mock_collector

                result = await collect_intraday_data_job()

                assert result == mock_result
                assert len(result["success"]) == 2
                assert len(result["failed"]) == 0
                mock_collector.collect_and_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_intraday_data_job_exception_handling(self):
        """Test error handling when collection fails."""
        with patch("src.stocks.jobs.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB error")

            result = await collect_intraday_data_job()

            assert len(result["success"]) == 0
            assert "error" in result

    @pytest.mark.asyncio
    async def test_collect_intraday_data_job_partial_failure(self):
        """Test collection with some symbols failing."""
        mock_result = {
            "success": ["VCB"],
            "failed": [{"symbol": "INVALID", "error": "Not found"}],
            "total_bars": 50,
        }

        with patch("src.stocks.jobs.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = mock_session

            with patch("src.stocks.jobs.IntradayCollector") as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect_and_save.return_value = mock_result
                mock_collector_class.return_value = mock_collector

                result = await collect_intraday_data_job()

                assert len(result["success"]) == 1
                assert len(result["failed"]) == 1

    @pytest.mark.asyncio
    async def test_collect_intraday_data_job_parses_symbols(self):
        """Test that symbols are correctly parsed from config."""
        with patch("src.stocks.jobs.settings") as mock_settings:
            mock_settings.intraday_symbols = "VCB, FPT, VNM"

            with patch("src.stocks.jobs.async_session_factory") as mock_factory:
                mock_session = AsyncMock()
                mock_factory.return_value.__aenter__.return_value = mock_session

                with patch("src.stocks.jobs.IntradayCollector") as mock_collector_class:
                    mock_collector = AsyncMock()
                    mock_collector.collect_and_save.return_value = {
                        "success": [], "failed": [], "total_bars": 0
                    }
                    mock_collector_class.return_value = mock_collector

                    await collect_intraday_data_job()

                    # Verify symbols were parsed and stripped
                    call_args = mock_collector.collect_and_save.call_args[0][0]
                    assert call_args == ["VCB", "FPT", "VNM"]


class TestCleanupOldDataJob:
    """Tests for cleanup_old_data_job function."""

    @pytest.mark.asyncio
    async def test_cleanup_old_data_job_success(self):
        """Test successful cleanup of old data."""
        with patch("src.stocks.jobs.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 50
            mock_session.execute.return_value = mock_result
            mock_factory.return_value.__aenter__.return_value = mock_session

            deleted_count = await cleanup_old_data_job()

            assert deleted_count == 50
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_data_job_no_old_data(self):
        """Test cleanup when no old data exists."""
        with patch("src.stocks.jobs.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 0
            mock_session.execute.return_value = mock_result
            mock_factory.return_value.__aenter__.return_value = mock_session

            deleted_count = await cleanup_old_data_job()

            assert deleted_count == 0


class TestSchedulerSetup:
    """Tests for scheduler setup function."""

    @pytest.mark.asyncio
    async def test_setup_scheduler_enabled(self):
        """Test scheduler setup when enabled."""
        from src.core.scheduler import setup_scheduler

        mock_scheduler = AsyncMock()

        with patch("src.core.scheduler.settings") as mock_settings:
            mock_settings.scheduler_enabled = True
            mock_settings.intraday_collect_hour = 15
            mock_settings.intraday_collect_minute = 30

            await setup_scheduler(mock_scheduler)

            # Should add 2 schedules: collection and cleanup
            assert mock_scheduler.add_schedule.call_count == 2

    @pytest.mark.asyncio
    async def test_setup_scheduler_disabled(self):
        """Test scheduler setup when disabled."""
        from src.core.scheduler import setup_scheduler

        mock_scheduler = AsyncMock()

        with patch("src.core.scheduler.settings") as mock_settings:
            mock_settings.scheduler_enabled = False

            await setup_scheduler(mock_scheduler)

            # Should not add any schedules
            mock_scheduler.add_schedule.assert_not_called()


class TestConfigSettings:
    """Tests for scheduler-related config settings."""

    def test_scheduler_settings_defaults(self):
        """Test default scheduler settings."""
        settings = Settings()

        assert settings.scheduler_enabled is True
        assert settings.intraday_collect_hour == 15
        assert settings.intraday_collect_minute == 30
        assert settings.intraday_retention_days == 30
        assert "VCB" in settings.intraday_symbols

    def test_scheduler_symbols_parsing(self):
        """Test parsing of comma-separated symbols."""
        settings = Settings(intraday_symbols="AAA,BBB,CCC")
        symbols = [s.strip() for s in settings.intraday_symbols.split(",")]

        assert symbols == ["AAA", "BBB", "CCC"]
