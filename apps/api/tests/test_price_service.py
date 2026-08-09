"""Unit tests for PriceService converters (no upstream calls)."""

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
            prices = service.get_history("VCB", pd.Timestamp("2026-08-01").date(), pd.Timestamp("2026-08-07").date())

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
