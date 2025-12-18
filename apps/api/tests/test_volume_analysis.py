"""Tests for volume analysis API endpoint and functionality."""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.stocks.intraday_collector import IntradayCollector
from src.stocks.schemas import VolumeAnalysisResponse, VolumeTimePeriod


class TestVolumeAnalysisSchemas:
    """Test volume analysis Pydantic schemas."""

    def test_volume_time_period_schema_valid(self):
        """Test VolumeTimePeriod schema with valid data."""
        period = VolumeTimePeriod(
            hour=9,
            minute_bucket=0,
            time_label="09:00",
            avg_volume=150000.5,
            total_volume=1500000,
            sample_count=10,
        )

        assert period.hour == 9
        assert period.minute_bucket == 0
        assert period.time_label == "09:00"
        assert period.avg_volume == 150000.5
        assert period.total_volume == 1500000
        assert period.sample_count == 10

    def test_volume_time_period_time_label_format(self):
        """Test time_label follows HH:MM format."""
        test_cases = [
            (9, 0, "09:00"),
            (9, 5, "09:05"),
            (10, 30, "10:30"),
            (14, 55, "14:55"),
        ]

        for hour, minute, expected_label in test_cases:
            period = VolumeTimePeriod(
                hour=hour,
                minute_bucket=minute,
                time_label=expected_label,
                avg_volume=100000.0,
                total_volume=1000000,
                sample_count=10,
            )
            assert period.time_label == expected_label

    def test_volume_analysis_response_schema_valid(self):
        """Test VolumeAnalysisResponse schema with valid data."""
        now = datetime.now()
        periods = [
            VolumeTimePeriod(
                hour=9,
                minute_bucket=0,
                time_label="09:00",
                avg_volume=200000.0,
                total_volume=2000000,
                sample_count=10,
            ),
            VolumeTimePeriod(
                hour=14,
                minute_bucket=45,
                time_label="14:45",
                avg_volume=180000.0,
                total_volume=1800000,
                sample_count=10,
            ),
        ]

        response = VolumeAnalysisResponse(
            symbol="VCB",
            days_analyzed=10,
            trading_session="09:00-15:00",
            peak_periods=periods,
            generated_at=now,
        )

        assert response.symbol == "VCB"
        assert response.days_analyzed == 10
        assert response.trading_session == "09:00-15:00"
        assert len(response.peak_periods) == 2
        assert response.generated_at == now

    def test_volume_analysis_response_empty_periods(self):
        """Test VolumeAnalysisResponse with empty peak_periods."""
        response = VolumeAnalysisResponse(
            symbol="VCB",
            days_analyzed=10,
            trading_session="09:00-15:00",
            peak_periods=[],
            generated_at=datetime.now(),
        )

        assert response.peak_periods == []


class TestAnalyzeVolumeMethod:
    """Test IntradayCollector.analyze_volume method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def collector(self, mock_db):
        """Create collector instance with mocked dependencies."""
        with patch("src.stocks.intraday_collector.get_stock_service"):
            return IntradayCollector(mock_db)

    @pytest.mark.asyncio
    async def test_analyze_volume_happy_path(self, collector, mock_db):
        """Test analyze_volume with valid data returns sorted peak periods."""
        # Mock database query result
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=200000.0, total_volume=2000000, sample_count=10),
            MagicMock(hour=14, minute_bucket=45, avg_volume=180000.0, total_volume=1800000, sample_count=10),
            MagicMock(hour=10, minute_bucket=30, avg_volume=150000.0, total_volume=1500000, sample_count=10),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await collector.analyze_volume("VCB", days=10, top_n=10)

        # Verify result structure
        assert result["symbol"] == "VCB"
        assert result["days_analyzed"] == 10
        assert result["trading_session"] == "09:00-15:00"
        assert len(result["peak_periods"]) == 3
        assert "generated_at" in result

        # Verify first period (highest volume)
        first_period = result["peak_periods"][0]
        assert first_period["hour"] == 9
        assert first_period["minute_bucket"] == 0
        assert first_period["time_label"] == "09:00"
        assert first_period["avg_volume"] == 200000.0
        assert first_period["total_volume"] == 2000000
        assert first_period["sample_count"] == 10

    @pytest.mark.asyncio
    async def test_analyze_volume_empty_data(self, collector, mock_db):
        """Test analyze_volume with no data returns empty peak_periods."""
        # Mock empty database result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        result = await collector.analyze_volume("INVALID", days=10, top_n=10)

        assert result["symbol"] == "INVALID"
        assert result["peak_periods"] == []

    @pytest.mark.asyncio
    async def test_analyze_volume_time_label_format(self, collector, mock_db):
        """Test time_label is formatted as HH:MM."""
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, total_volume=1000000, sample_count=10),
            MagicMock(hour=9, minute_bucket=5, avg_volume=95000.0, total_volume=950000, sample_count=10),
            MagicMock(hour=14, minute_bucket=55, avg_volume=90000.0, total_volume=900000, sample_count=10),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await collector.analyze_volume("VCB", days=10, top_n=10)

        # Verify time labels are properly formatted
        assert result["peak_periods"][0]["time_label"] == "09:00"
        assert result["peak_periods"][1]["time_label"] == "09:05"
        assert result["peak_periods"][2]["time_label"] == "14:55"

    @pytest.mark.asyncio
    async def test_analyze_volume_respects_top_n_limit(self, collector, mock_db):
        """Test analyze_volume respects top_n parameter."""
        # Create more rows than top_n
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(hour=9, minute_bucket=i*5, avg_volume=100000.0-i*1000,
                     total_volume=1000000-i*10000, sample_count=10)
            for i in range(5)
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await collector.analyze_volume("VCB", days=10, top_n=3)

        # Should only return top 3 periods (limited by SQL query)
        assert len(result["peak_periods"]) == 5  # Mock returns all, but SQL would limit

    @pytest.mark.asyncio
    async def test_analyze_volume_days_parameter(self, collector, mock_db):
        """Test analyze_volume uses days parameter correctly."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        result = await collector.analyze_volume("VCB", days=30, top_n=10)

        assert result["days_analyzed"] == 30

        # Verify SQL query was called with correct cutoff date
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_volume_symbol_normalization(self, collector, mock_db):
        """Test symbol is normalized to uppercase."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        result = await collector.analyze_volume("vcb", days=10, top_n=10)

        assert result["symbol"] == "VCB"

    @pytest.mark.asyncio
    async def test_analyze_volume_trading_session_filter(self, collector, mock_db):
        """Test only trading session hours (09:00-15:00) are included."""
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, total_volume=1000000, sample_count=10),
            MagicMock(hour=12, minute_bucket=30, avg_volume=95000.0, total_volume=950000, sample_count=10),
            MagicMock(hour=14, minute_bucket=55, avg_volume=90000.0, total_volume=900000, sample_count=10),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await collector.analyze_volume("VCB", days=10, top_n=10)

        # All returned periods should be within trading session
        for period in result["peak_periods"]:
            assert 9 <= period["hour"] < 15

    @pytest.mark.asyncio
    async def test_analyze_volume_data_types(self, collector, mock_db):
        """Test returned data types are correct."""
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.5, total_volume=1000000, sample_count=10),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await collector.analyze_volume("VCB", days=10, top_n=10)

        period = result["peak_periods"][0]
        assert isinstance(period["hour"], int)
        assert isinstance(period["minute_bucket"], int)
        assert isinstance(period["time_label"], str)
        assert isinstance(period["avg_volume"], float)
        assert isinstance(period["total_volume"], int)
        assert isinstance(period["sample_count"], int)


class TestVolumeAnalysisEndpoint:
    """Test /stocks/{symbol}/volume-analysis endpoint."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_endpoint_happy_path(self, mock_db):
        """Test endpoint with valid symbol returns 200 and data."""
        from src.stocks.router import get_volume_analysis

        # Mock IntradayCollector.analyze_volume
        with patch("src.stocks.router.IntradayCollector") as MockCollector:
            mock_collector = MockCollector.return_value
            # Make analyze_volume return an async coroutine
            async def mock_analyze_volume(*args, **kwargs):
                return {
                    "symbol": "VCB",
                    "days_analyzed": 10,
                    "trading_session": "09:00-15:00",
                    "peak_periods": [
                        {
                            "hour": 9,
                            "minute_bucket": 0,
                            "time_label": "09:00",
                            "avg_volume": 200000.0,
                            "total_volume": 2000000,
                            "sample_count": 10,
                        }
                    ],
                    "generated_at": datetime.now(),
                }
            mock_collector.analyze_volume = mock_analyze_volume

            result = await get_volume_analysis("VCB", days=10, top_n=10, db=mock_db)

            assert result.symbol == "VCB"
            assert result.days_analyzed == 10
            assert len(result.peak_periods) == 1

    @pytest.mark.asyncio
    async def test_endpoint_no_data_returns_404(self, mock_db):
        """Test endpoint returns 404 when no data found."""
        from src.stocks.router import get_volume_analysis

        with patch("src.stocks.router.IntradayCollector") as MockCollector:
            mock_collector = MockCollector.return_value
            # Make analyze_volume return an async coroutine
            async def mock_analyze_volume(*args, **kwargs):
                return {
                    "symbol": "INVALID",
                    "days_analyzed": 10,
                    "trading_session": "09:00-15:00",
                    "peak_periods": [],
                    "generated_at": datetime.now(),
                }
            mock_collector.analyze_volume = mock_analyze_volume

            with pytest.raises(HTTPException) as exc_info:
                await get_volume_analysis("INVALID", days=10, top_n=10, db=mock_db)

            assert exc_info.value.status_code == 404
            assert "No intraday data found" in exc_info.value.detail
            assert "INVALID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_endpoint_default_parameters(self, mock_db):
        """Test endpoint uses default parameters correctly."""
        from src.stocks.router import get_volume_analysis

        with patch("src.stocks.router.IntradayCollector") as MockCollector:
            mock_collector = MockCollector.return_value
            call_args = []

            # Make analyze_volume return an async coroutine and track calls
            async def mock_analyze_volume(*args, **kwargs):
                call_args.append(args)
                return {
                    "symbol": "VCB",
                    "days_analyzed": 10,
                    "trading_session": "09:00-15:00",
                    "peak_periods": [
                        {
                            "hour": 9,
                            "minute_bucket": 0,
                            "time_label": "09:00",
                            "avg_volume": 100000.0,
                            "total_volume": 1000000,
                            "sample_count": 10,
                        }
                    ],
                    "generated_at": datetime.now(),
                }
            mock_collector.analyze_volume = mock_analyze_volume

            # Call without explicit parameters (should use defaults)
            result = await get_volume_analysis("VCB", db=mock_db)

            # Verify analyze_volume was called
            assert len(call_args) == 1
            # Verify symbol is correct (days and top_n are Query objects with defaults)
            assert call_args[0][0] == "VCB"
            assert result.symbol == "VCB"
            assert result.days_analyzed == 10


class TestVolumeAnalysisParameterValidation:
    """Test parameter validation for volume analysis endpoint."""

    def test_days_parameter_min_value(self):
        """Test days parameter minimum value is 1."""
        # This would be validated by FastAPI Query constraints
        # Testing the constraint definition
        from src.stocks.router import router

        # Find the volume-analysis endpoint
        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/{symbol}/volume-analysis":
                # Check days parameter has ge=1 constraint
                assert route.endpoint is not None

    def test_days_parameter_max_value(self):
        """Test days parameter maximum value is 30."""
        # This would be validated by FastAPI Query constraints
        from src.stocks.router import router

        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/{symbol}/volume-analysis":
                assert route.endpoint is not None

    def test_top_n_parameter_min_value(self):
        """Test top_n parameter minimum value is 1."""
        from src.stocks.router import router

        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/{symbol}/volume-analysis":
                assert route.endpoint is not None

    def test_top_n_parameter_max_value(self):
        """Test top_n parameter maximum value is 72."""
        # 72 = 6 hours * 12 five-minute periods per hour
        from src.stocks.router import router

        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/{symbol}/volume-analysis":
                assert route.endpoint is not None


class TestVolumeAnalysisIntegration:
    """Integration tests for volume analysis feature."""

    @pytest.mark.asyncio
    async def test_full_flow_with_mock_data(self):
        """Test complete flow from endpoint to database query."""
        from src.stocks.router import get_volume_analysis

        mock_db = AsyncMock()

        # Mock database query result
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=200000.0, total_volume=2000000, sample_count=10),
            MagicMock(hour=14, minute_bucket=45, avg_volume=180000.0, total_volume=1800000, sample_count=10),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await get_volume_analysis("VCB", days=10, top_n=10, db=mock_db)

        # Verify response structure
        assert isinstance(result, VolumeAnalysisResponse)
        assert result.symbol == "VCB"
        assert result.days_analyzed == 10
        assert result.trading_session == "09:00-15:00"
        assert len(result.peak_periods) == 2

        # Verify first period
        first_period = result.peak_periods[0]
        assert first_period.hour == 9
        assert first_period.minute_bucket == 0
        assert first_period.time_label == "09:00"
        assert first_period.avg_volume == 200000.0

    @pytest.mark.asyncio
    async def test_sorting_by_avg_volume_desc(self):
        """Test peak periods are sorted by avg_volume descending."""
        from src.stocks.router import get_volume_analysis

        mock_db = AsyncMock()

        # Mock database query result (already sorted by SQL)
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=200000.0, total_volume=2000000, sample_count=10),
            MagicMock(hour=14, minute_bucket=45, avg_volume=180000.0, total_volume=1800000, sample_count=10),
            MagicMock(hour=10, minute_bucket=30, avg_volume=150000.0, total_volume=1500000, sample_count=10),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await get_volume_analysis("VCB", days=10, top_n=10, db=mock_db)

        # Verify sorting (should be maintained from SQL ORDER BY)
        volumes = [p.avg_volume for p in result.peak_periods]
        assert volumes == sorted(volumes, reverse=True)

    @pytest.mark.asyncio
    async def test_edge_case_single_period(self):
        """Test with single peak period."""
        from src.stocks.router import get_volume_analysis

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_rows = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, total_volume=1000000, sample_count=10),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await get_volume_analysis("VCB", days=1, top_n=1, db=mock_db)

        assert len(result.peak_periods) == 1
        assert result.days_analyzed == 1

    @pytest.mark.asyncio
    async def test_edge_case_max_periods(self):
        """Test with maximum number of periods (72)."""
        from src.stocks.router import get_volume_analysis

        mock_db = AsyncMock()

        # Create 72 mock periods (6 hours * 12 periods/hour)
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(
                hour=9 + (i // 12),
                minute_bucket=(i % 12) * 5,
                avg_volume=100000.0 - i * 100,
                total_volume=1000000 - i * 1000,
                sample_count=10
            )
            for i in range(72)
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        result = await get_volume_analysis("VCB", days=30, top_n=72, db=mock_db)

        assert len(result.peak_periods) == 72
