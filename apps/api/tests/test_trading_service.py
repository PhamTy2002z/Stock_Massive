"""Deterministic tests for the retained vnstock 4 intraday trade adapter."""

from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.stocks.shared import StockServiceError
from src.stocks.trading.service import TradingService


def _market_with_trades(frame):
    market = Mock()
    equity = market.return_value.equity.return_value
    equity.trades.return_value = frame
    return market, equity


def test_intraday_order_stats_uses_vnstock_4_market_api():
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2026-08-07 09:15:06",
                    "2026-08-07 09:30:00",
                    "2026-08-07 10:00:00",
                    "2026-08-07 11:00:00",
                    "2026-08-07 14:30:00",
                    "2026-08-07 14:45:15",
                ]
            ),
            "match_type": ["Buy", "buy", "Sell", "ATO", "ATC", "unknown"],
            "volume": [100, 250, 80, 40, 60, 999],
        }
    )
    market, equity = _market_with_trades(frame)

    with patch("src.stocks.trading.service.Market", market):
        result = TradingService().get_intraday_order_stats("vcb")

    market.return_value.equity.assert_called_once_with("VCB")
    equity.trades.assert_called_once_with(source="KBS", page_size=10_000)
    assert result.date == "2026-08-07"
    assert result.buy_orders == 2
    assert result.sell_orders == 1
    assert result.buy_volume == 350
    assert result.sell_volume == 80
    assert result.net_volume == 270
    assert result.ato_volume == 40
    assert result.atc_volume == 60


@pytest.mark.parametrize("frame", [None, pd.DataFrame()])
def test_intraday_order_stats_returns_zeroes_for_empty_trades(frame):
    market, _ = _market_with_trades(frame)

    with patch("src.stocks.trading.service.Market", market):
        result = TradingService().get_intraday_order_stats("VCB")

    assert result.buy_orders == 0
    assert result.sell_orders == 0
    assert result.buy_volume == 0
    assert result.sell_volume == 0
    assert result.net_volume == 0
    assert result.date is None


def test_intraday_order_stats_validates_symbol_before_calling_market():
    market = Mock()

    with patch("src.stocks.trading.service.Market", market):
        with pytest.raises(StockServiceError, match="Invalid symbol format"):
            TradingService().get_intraday_order_stats("INVALID_SYMBOL")

    market.assert_not_called()
