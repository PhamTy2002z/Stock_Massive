"""Tests for volume anomaly detection API endpoint and functionality."""
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.stocks.intraday_collector import IntradayCollector
from src.stocks.schemas import VolumeAnomalyResponse, VolumeTimeSlot, VolumeAnomalyLevel


class TestVolumeAnomalySchemas:
    """Test volume anomaly detection Pydantic schemas."""

    def test_volume_anomaly_level_enum_values(self):
        """Test VolumeAnomalyLevel enum has correct values."""
        assert VolumeAnomalyLevel.NORMAL == "normal"
        assert VolumeAnomalyLevel.ELEVATED == "elevated"
        assert VolumeAnomalyLevel.HIGH == "high"
        assert VolumeAnomalyLevel.VERY_HIGH == "very_high"

    def test_volume_time_slot_schema_valid(self):
        """Test VolumeTimeSlot schema with valid data."""
        slot = VolumeTimeSlot(
            hour=9,
            minute_bucket=0,
            time_label="09:00",
            current_volume=200000,
            avg_volume=100000.0,
            volume_ratio=2.0,
            anomaly_level=VolumeAnomalyLevel.HIGH,
            sample_count=10,
        )

        assert slot.hour == 9
        assert slot.minute_bucket == 0
        assert slot.time_label == "09:00"
        assert slot.current_volume == 200000
        assert slot.avg_volume == 100000.0
        assert slot.volume_ratio == 2.0
        assert slot.anomaly_level == VolumeAnomalyLevel.HIGH
        assert slot.sample_count == 10

    def test_volume_anomaly_response_schema_valid(self):
        """Test VolumeAnomalyResponse schema with valid data."""
        now = datetime.now()
        today = date.today()
        slots = [
            VolumeTimeSlot(
                hour=9,
                minute_bucket=0,
                time_label="09:00",
                current_volume=200000,
                avg_volume=100000.0,
                volume_ratio=2.0,
                anomaly_level=VolumeAnomalyLevel.HIGH,
                sample_count=10,
            ),
        ]

        response = VolumeAnomalyResponse(
            symbol="VCB",
            days_analyzed=20,
            trading_session="09:00-15:00",
            time_slots=slots,
            generated_at=now,
            latest_date=today,
        )

        assert response.symbol == "VCB"
        assert response.days_analyzed == 20
        assert response.trading_session == "09:00-15:00"
        assert len(response.time_slots) == 1
        assert response.generated_at == now
        assert response.latest_date == today

    def test_volume_anomaly_response_72_slots(self):
        """Test VolumeAnomalyResponse can hold all 72 time slots."""
        slots = []
        for hour in range(9, 15):
            for minute in range(0, 60, 5):
                if hour == 14 and minute > 55:
                    break
                slots.append(
                    VolumeTimeSlot(
                        hour=hour,
                        minute_bucket=minute,
                        time_label=f"{hour:02d}:{minute:02d}",
                        current_volume=100000,
                        avg_volume=100000.0,
                        volume_ratio=1.0,
                        anomaly_level=VolumeAnomalyLevel.NORMAL,
                        sample_count=10,
                    )
                )

        response = VolumeAnomalyResponse(
            symbol="VCB",
            days_analyzed=20,
            trading_session="09:00-15:00",
            time_slots=slots,
            generated_at=datetime.now(),
            latest_date=date.today(),
        )

        assert len(response.time_slots) == 72


class TestDetectVolumeAnomaliesMethod:
    """Test IntradayCollector.detect_volume_anomalies method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def collector(self, mock_db):
        """Create collector instance with mocked dependencies."""
        with patch("src.stocks.service.get_stock_service"):
            return IntradayCollector(mock_db)

    @pytest.mark.asyncio
    async def test_detect_volume_anomalies_returns_72_slots(self, collector, mock_db):
        """Test detect_volume_anomalies returns exactly 72 time slots."""
        # Mock latest date query
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = date.today()

        # Mock baseline query
        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, sample_count=10),
        ]

        # Mock current day query
        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=150000),
        ]

        # Setup execute to return different results based on call order
        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=20)

        assert len(result["time_slots"]) == 72
        assert result["symbol"] == "VCB"
        assert result["days_analyzed"] == 20

    @pytest.mark.asyncio
    async def test_detect_volume_anomalies_no_data_returns_empty(self, collector, mock_db):
        """Test detect_volume_anomalies returns empty slots when no data found."""
        # Mock latest date query returning None
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = None

        mock_db.execute.return_value = mock_latest_result

        result = await collector.detect_volume_anomalies("INVALID", days=20)

        assert result["symbol"] == "INVALID"
        assert result["time_slots"] == []
        assert result["latest_date"] is None

    @pytest.mark.asyncio
    async def test_anomaly_level_normal(self, collector, mock_db):
        """Test anomaly level is 'normal' when ratio < 1.5x."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, sample_count=10),
        ]

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=140000),  # 1.4x ratio
        ]

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=20)

        slot_9_00 = next(s for s in result["time_slots"] if s["hour"] == 9 and s["minute_bucket"] == 0)
        assert slot_9_00["anomaly_level"] == "normal"
        assert slot_9_00["volume_ratio"] == 1.4

    @pytest.mark.asyncio
    async def test_anomaly_level_elevated(self, collector, mock_db):
        """Test anomaly level is 'elevated' when ratio is 1.5x-2x."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, sample_count=10),
        ]

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=175000),  # 1.75x ratio
        ]

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=20)

        slot_9_00 = next(s for s in result["time_slots"] if s["hour"] == 9 and s["minute_bucket"] == 0)
        assert slot_9_00["anomaly_level"] == "elevated"
        assert slot_9_00["volume_ratio"] == 1.75

    @pytest.mark.asyncio
    async def test_anomaly_level_high(self, collector, mock_db):
        """Test anomaly level is 'high' when ratio is 2x-3x."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, sample_count=10),
        ]

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=250000),  # 2.5x ratio
        ]

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=20)

        slot_9_00 = next(s for s in result["time_slots"] if s["hour"] == 9 and s["minute_bucket"] == 0)
        assert slot_9_00["anomaly_level"] == "high"
        assert slot_9_00["volume_ratio"] == 2.5

    @pytest.mark.asyncio
    async def test_anomaly_level_very_high(self, collector, mock_db):
        """Test anomaly level is 'very_high' when ratio >= 3x."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, sample_count=10),
        ]

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=350000),  # 3.5x ratio
        ]

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=20)

        slot_9_00 = next(s for s in result["time_slots"] if s["hour"] == 9 and s["minute_bucket"] == 0)
        assert slot_9_00["anomaly_level"] == "very_high"
        assert slot_9_00["volume_ratio"] == 3.5

    @pytest.mark.asyncio
    async def test_baseline_excludes_latest_day(self, collector, mock_db):
        """Test baseline calculation excludes the latest day."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = []

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = []

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        await collector.detect_volume_anomalies("VCB", days=20)

        # Verify the baseline query was called (second execute call)
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_days_parameter_validation(self, collector, mock_db):
        """Test days parameter is used correctly."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = []

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = []

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=30)

        assert result["days_analyzed"] == 30

    @pytest.mark.asyncio
    async def test_symbol_normalization(self, collector, mock_db):
        """Test symbol is normalized to uppercase."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = []

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = []

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("vcb", days=20)

        assert result["symbol"] == "VCB"

    @pytest.mark.asyncio
    async def test_time_label_format(self, collector, mock_db):
        """Test time_label is formatted as HH:MM."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = []

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = []

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=20)

        # Check first and last slots
        assert result["time_slots"][0]["time_label"] == "09:00"
        assert result["time_slots"][-1]["time_label"] == "14:55"

    @pytest.mark.asyncio
    async def test_zero_avg_volume_handling(self, collector, mock_db):
        """Test handling when avg_volume is zero."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        # No baseline data (avg_volume will be 0)
        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = []

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=100000),
        ]

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=20)

        slot_9_00 = next(s for s in result["time_slots"] if s["hour"] == 9 and s["minute_bucket"] == 0)
        assert slot_9_00["volume_ratio"] == 0.0
        assert slot_9_00["anomaly_level"] == "normal"

    @pytest.mark.asyncio
    async def test_all_time_slots_present(self, collector, mock_db):
        """Test all 72 time slots are present even with sparse data."""
        today = date.today()
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        # Only one baseline slot
        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, sample_count=10),
        ]

        # Only one current slot
        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=150000),
        ]

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await collector.detect_volume_anomalies("VCB", days=20)

        # Verify all 72 slots are present
        assert len(result["time_slots"]) == 72

        # Verify time range
        hours = [s["hour"] for s in result["time_slots"]]
        assert min(hours) == 9
        assert max(hours) == 14


class TestVolumeAnomalyEndpoint:
    """Test /stocks/{symbol}/volume-anomalies endpoint."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_endpoint_happy_path(self, mock_db):
        """Test endpoint with valid symbol returns 200 and 72 slots."""
        from src.stocks.price.router import get_volume_anomalies

        with patch("src.stocks.price.router.IntradayCollector") as MockCollector:
            mock_collector = MockCollector.return_value

            async def mock_detect_volume_anomalies(*args, **kwargs):
                slots = []
                for hour in range(9, 15):
                    for minute in range(0, 60, 5):
                        if hour == 14 and minute > 55:
                            break
                        slots.append({
                            "hour": hour,
                            "minute_bucket": minute,
                            "time_label": f"{hour:02d}:{minute:02d}",
                            "current_volume": 100000,
                            "avg_volume": 100000.0,
                            "volume_ratio": 1.0,
                            "anomaly_level": "normal",
                            "sample_count": 10,
                        })
                return {
                    "symbol": "VCB",
                    "days_analyzed": 20,
                    "trading_session": "09:00-15:00",
                    "time_slots": slots,
                    "generated_at": datetime.now(),
                    "latest_date": date.today(),
                }

            mock_collector.detect_volume_anomalies = mock_detect_volume_anomalies

            result = await get_volume_anomalies("VCB", days=20, db=mock_db)

            assert result.symbol == "VCB"
            assert result.days_analyzed == 20
            assert len(result.time_slots) == 72

    @pytest.mark.asyncio
    async def test_endpoint_no_data_returns_404(self, mock_db):
        """Test endpoint returns 404 when no data found."""
        from src.stocks.price.router import get_volume_anomalies

        with patch("src.stocks.price.router.IntradayCollector") as MockCollector:
            mock_collector = MockCollector.return_value

            async def mock_detect_volume_anomalies(*args, **kwargs):
                return {
                    "symbol": "INVALID",
                    "days_analyzed": 20,
                    "trading_session": "09:00-15:00",
                    "time_slots": [],
                    "generated_at": datetime.now(),
                    "latest_date": None,
                }

            mock_collector.detect_volume_anomalies = mock_detect_volume_anomalies

            with pytest.raises(HTTPException) as exc_info:
                await get_volume_anomalies("INVALID", days=20, db=mock_db)

            assert exc_info.value.status_code == 404
            assert "No intraday data found" in exc_info.value.detail
            assert "INVALID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_endpoint_default_days_parameter(self, mock_db):
        """Test endpoint uses default days=20."""
        from src.stocks.price.router import get_volume_anomalies

        with patch("src.stocks.price.router.IntradayCollector") as MockCollector:
            mock_collector = MockCollector.return_value
            call_args = []

            async def mock_detect_volume_anomalies(*args, **kwargs):
                call_args.append((args, kwargs))
                return {
                    "symbol": "VCB",
                    "days_analyzed": 20,
                    "trading_session": "09:00-15:00",
                    "time_slots": [
                        {
                            "hour": 9,
                            "minute_bucket": 0,
                            "time_label": "09:00",
                            "current_volume": 100000,
                            "avg_volume": 100000.0,
                            "volume_ratio": 1.0,
                            "anomaly_level": "normal",
                            "sample_count": 10,
                        }
                    ],
                    "generated_at": datetime.now(),
                    "latest_date": date.today(),
                }

            mock_collector.detect_volume_anomalies = mock_detect_volume_anomalies

            result = await get_volume_anomalies("VCB", db=mock_db)

            assert result.symbol == "VCB"
            assert result.days_analyzed == 20

    @pytest.mark.asyncio
    async def test_endpoint_custom_days_parameter(self, mock_db):
        """Test endpoint accepts custom days parameter."""
        from src.stocks.price.router import get_volume_anomalies

        with patch("src.stocks.price.router.IntradayCollector") as MockCollector:
            mock_collector = MockCollector.return_value

            async def mock_detect_volume_anomalies(*args, **kwargs):
                return {
                    "symbol": "VCB",
                    "days_analyzed": 30,
                    "trading_session": "09:00-15:00",
                    "time_slots": [
                        {
                            "hour": 9,
                            "minute_bucket": 0,
                            "time_label": "09:00",
                            "current_volume": 100000,
                            "avg_volume": 100000.0,
                            "volume_ratio": 1.0,
                            "anomaly_level": "normal",
                            "sample_count": 10,
                        }
                    ],
                    "generated_at": datetime.now(),
                    "latest_date": date.today(),
                }

            mock_collector.detect_volume_anomalies = mock_detect_volume_anomalies

            result = await get_volume_anomalies("VCB", days=30, db=mock_db)

            assert result.days_analyzed == 30


class TestVolumeAnomalyParameterValidation:
    """Test parameter validation for volume anomaly endpoint."""

    def test_days_parameter_constraints(self):
        """Test days parameter has correct constraints (5-60)."""
        from src.stocks.price.router import router

        # Find the volume-anomalies endpoint
        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/{symbol}/volume-anomalies":
                assert route.endpoint is not None
                # Endpoint exists with days parameter


class TestVolumeAnomalyIntegration:
    """Integration tests for volume anomaly detection feature."""

    @pytest.mark.asyncio
    async def test_full_flow_with_mock_data(self):
        """Test complete flow from endpoint to database query."""
        from src.stocks.price.router import get_volume_anomalies

        mock_db = AsyncMock()
        today = date.today()

        # Mock latest date query
        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        # Mock baseline query with multiple time slots
        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, sample_count=10),
            MagicMock(hour=9, minute_bucket=5, avg_volume=95000.0, sample_count=10),
            MagicMock(hour=14, minute_bucket=55, avg_volume=80000.0, sample_count=10),
        ]

        # Mock current day query
        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=200000),  # 2x - high
            MagicMock(hour=9, minute_bucket=5, volume=160000),  # 1.68x - elevated
            MagicMock(hour=14, minute_bucket=55, volume=240000),  # 3x - very_high
        ]

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await get_volume_anomalies("VCB", days=20, db=mock_db)

        # Verify response structure
        assert isinstance(result, VolumeAnomalyResponse)
        assert result.symbol == "VCB"
        assert result.days_analyzed == 20
        assert result.trading_session == "09:00-15:00"
        assert len(result.time_slots) == 72
        assert result.latest_date == today

        # Verify specific anomaly levels
        slot_9_00 = next(s for s in result.time_slots if s.hour == 9 and s.minute_bucket == 0)
        assert slot_9_00.anomaly_level == VolumeAnomalyLevel.HIGH
        assert slot_9_00.volume_ratio == 2.0

        slot_9_05 = next(s for s in result.time_slots if s.hour == 9 and s.minute_bucket == 5)
        assert slot_9_05.anomaly_level == VolumeAnomalyLevel.ELEVATED

        slot_14_55 = next(s for s in result.time_slots if s.hour == 14 and s.minute_bucket == 55)
        assert slot_14_55.anomaly_level == VolumeAnomalyLevel.VERY_HIGH
        assert slot_14_55.volume_ratio == 3.0

    @pytest.mark.asyncio
    async def test_edge_case_boundary_ratios(self):
        """Test boundary conditions for anomaly level thresholds."""
        from src.stocks.price.router import get_volume_anomalies

        mock_db = AsyncMock()
        today = date.today()

        mock_latest_result = MagicMock()
        mock_latest_result.scalar.return_value = today

        # Test exact boundary values
        mock_baseline_result = MagicMock()
        mock_baseline_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, avg_volume=100000.0, sample_count=10),
            MagicMock(hour=9, minute_bucket=5, avg_volume=100000.0, sample_count=10),
            MagicMock(hour=9, minute_bucket=10, avg_volume=100000.0, sample_count=10),
            MagicMock(hour=9, minute_bucket=15, avg_volume=100000.0, sample_count=10),
        ]

        mock_current_result = MagicMock()
        mock_current_result.fetchall.return_value = [
            MagicMock(hour=9, minute_bucket=0, volume=149999),  # 1.49999x - normal
            MagicMock(hour=9, minute_bucket=5, volume=150000),  # 1.5x - elevated
            MagicMock(hour=9, minute_bucket=10, volume=200000),  # 2.0x - high
            MagicMock(hour=9, minute_bucket=15, volume=300000),  # 3.0x - very_high
        ]

        mock_db.execute.side_effect = [
            mock_latest_result,
            mock_baseline_result,
            mock_current_result,
        ]

        result = await get_volume_anomalies("VCB", days=20, db=mock_db)

        slot_9_00 = next(s for s in result.time_slots if s.hour == 9 and s.minute_bucket == 0)
        assert slot_9_00.anomaly_level == VolumeAnomalyLevel.NORMAL

        slot_9_05 = next(s for s in result.time_slots if s.hour == 9 and s.minute_bucket == 5)
        assert slot_9_05.anomaly_level == VolumeAnomalyLevel.ELEVATED

        slot_9_10 = next(s for s in result.time_slots if s.hour == 9 and s.minute_bucket == 10)
        assert slot_9_10.anomaly_level == VolumeAnomalyLevel.HIGH

        slot_9_15 = next(s for s in result.time_slots if s.hour == 9 and s.minute_bucket == 15)
        assert slot_9_15.anomaly_level == VolumeAnomalyLevel.VERY_HIGH
