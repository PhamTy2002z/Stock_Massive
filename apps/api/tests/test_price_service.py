"""Unit tests for PriceService converters (no upstream calls)."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.stocks.price.service import PriceService


@pytest.fixture
def service():
    return PriceService(source="VCI")


class TestQuotePricesAreVnd:
    """Quote history and intraday ticks arrive in thousands of VND.

    The price board — which fills the same screen — arrives in plain VND, so the
    chart drew its line against a reference price a thousand times larger.
    """

    def test_history_scales_ohlc_to_vnd(self, service):
        frame = pd.DataFrame(
            [
                {
                    "time": "2026-08-07",
                    "open": 59.0,
                    "high": 60.8,
                    "low": 58.7,
                    "close": 59.7,
                    "volume": 6_522_200,
                }
            ]
        )
        quote = MagicMock()
        quote.return_value.history.return_value = frame

        with patch("src.stocks.price.service.Quote", quote):
            prices = service.get_history("VCB", date(2026, 8, 1), date(2026, 8, 7))

        assert len(prices) == 1
        assert prices[0].open == 59_000.0
        assert prices[0].high == 60_800.0
        assert prices[0].low == 58_700.0
        assert prices[0].close == 59_700.0
        # Volume is a share count, not a price — it must not be scaled.
        assert prices[0].volume == 6_522_200

    def test_intraday_scales_price_to_vnd(self, service):
        frame = pd.DataFrame(
            [
                {
                    "time": "2026-08-07 14:26:56",
                    "price": 59.9,
                    "volume": 100,
                    "match_type": "Sell",
                }
            ]
        )
        quote = MagicMock()
        quote.return_value.intraday.return_value = frame

        with patch("src.stocks.price.service.Quote", quote):
            ticks = service.get_intraday("VCB")

        assert len(ticks) == 1
        assert ticks[0].price == 59_900.0
        assert ticks[0].volume == 100

    def test_intraday_interval_keeps_the_time_of_day(self, service):
        """A 5-minute series collapses onto one label without the clock."""
        frame = pd.DataFrame(
            [
                {
                    "time": pd.Timestamp("2026-08-07 09:15:00"),
                    "open": 58.7,
                    "high": 59.0,
                    "low": 58.7,
                    "close": 59.0,
                    "volume": 112_500,
                },
                {
                    "time": pd.Timestamp("2026-08-07 14:45:00"),
                    "open": 59.7,
                    "high": 59.7,
                    "low": 59.7,
                    "close": 59.7,
                    "volume": 134_600,
                },
            ]
        )
        quote = MagicMock()
        quote.return_value.history.return_value = frame

        with patch("src.stocks.price.service.Quote", quote):
            prices = service.get_history(
                "VCB", date(2026, 8, 7), date(2026, 8, 7), interval="5m"
            )

        assert [str(p.time) for p in prices] == [
            "2026-08-07 09:15:00",
            "2026-08-07 14:45:00",
        ]
        assert prices[0].close == 59_000.0

    def test_minutes_with_no_matches_are_left_out(self, service):
        """An empty 5-minute bucket is a gap in the session, not a price of 0."""
        frame = pd.DataFrame(
            [
                {
                    "time": pd.Timestamp("2026-08-07 09:15:00"),
                    "open": 58.7,
                    "high": 59.0,
                    "low": 58.7,
                    "close": 59.0,
                    "volume": 112_500,
                },
                {
                    "time": pd.Timestamp("2026-08-07 09:20:00"),
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": None,
                    "volume": 0,
                },
            ]
        )
        quote = MagicMock()
        quote.return_value.history.return_value = frame

        with patch("src.stocks.price.service.Quote", quote):
            prices = service.get_history(
                "VCB", date(2026, 8, 7), date(2026, 8, 7), interval="5m"
            )

        assert len(prices) == 1
        assert str(prices[0].time) == "2026-08-07 09:15:00"

    def test_intraday_frame_is_trimmed_to_the_requested_window(self, service):
        """Upstream answers intraday with a fixed lookback, not the range asked for."""
        frame = pd.DataFrame(
            [
                {
                    "time": pd.Timestamp("2026-08-06 14:00:00"),
                    "open": 59.4,
                    "high": 59.4,
                    "low": 59.1,
                    "close": 59.2,
                    "volume": 112_500,
                },
                {
                    "time": pd.Timestamp("2026-08-07 09:15:00"),
                    "open": 58.7,
                    "high": 59.0,
                    "low": 58.7,
                    "close": 59.0,
                    "volume": 98_000,
                },
            ]
        )
        quote = MagicMock()
        quote.return_value.history.return_value = frame

        with patch("src.stocks.price.service.Quote", quote):
            prices = service.get_history(
                "VCB", date(2026, 8, 7), date(2026, 8, 7), interval="5m"
            )

        assert [str(p.time) for p in prices] == ["2026-08-07 09:15:00"]

    def test_market_indices_keep_their_own_scale(self, service):
        """VN-INDEX is quoted in points, so the thousands rule must not reach it."""
        frame = pd.DataFrame(
            [
                {"time": "2026-08-06", "close": 1_600.0},
                {"time": "2026-08-07", "close": 1_632.0},
            ]
        )
        quote = MagicMock()
        quote.return_value.history.return_value = frame

        with patch("src.stocks.price.service.Quote", quote):
            indices = service.get_market_indices()

        assert indices[0].value == 1_632.0
        assert indices[0].change == 32.0
