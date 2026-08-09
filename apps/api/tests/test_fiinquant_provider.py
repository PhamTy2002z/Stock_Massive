"""Tests for FiinQuant normalization and collector protection."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pandas as pd
import pytest

from src.stocks.providers.fiinquant import (
    FiinQuantCircuitOpen,
    FiinQuantMarketProvider,
    FiinQuantProviderError,
    ProviderCircuitBreaker,
)
from src.stocks.shared import StockServiceError


class FakeEvent:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def get_data(self) -> pd.DataFrame:
        return self.frame


def make_provider(frame: pd.DataFrame) -> tuple[FiinQuantMarketProvider, Mock]:
    client = Mock()
    client.Fetch_Trading_Data.return_value = FakeEvent(frame)
    provider = FiinQuantMarketProvider(
        "configured-user",
        "configured-password",
        session_factory=lambda _username, _password: client,
        now=lambda: datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc),
    )
    return provider, client


def test_fetch_market_normalizes_vnd_prices_and_previous_close():
    frame = pd.DataFrame(
        [
            {
                "timestamp": "2026-08-09 14:59",
                "ticker": "VCB",
                "open": 59_000,
                "high": 60_000,
                "low": 58_900,
                "close": 59_500,
                "volume": 1_000,
            },
            {
                "timestamp": "2026-08-09 15:00",
                "ticker": "VCB",
                "open": 59_500,
                "high": 60_200,
                "low": 59_300,
                "close": 59_700,
                "volume": 2_500,
            },
        ]
    )
    provider, client = make_provider(frame)

    snapshots = provider.fetch_market(["vcb", "VCB"])

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.symbol == "VCB"
    assert snapshot.last_price == 59_700
    assert snapshot.reference_price == 59_500
    assert snapshot.volume == 2_500
    assert snapshot.change_pct == pytest.approx(0.33613445)
    assert snapshot.metadata.effective_at.utcoffset() is not None
    client.Fetch_Trading_Data.assert_called_once_with(
        realtime=False,
        tickers=["VCB"],
        fields=["open", "high", "low", "close", "volume"],
        adjusted=False,
        by="1m",
        period=2,
        lasted=True,
    )


def test_fetch_market_enforces_free_symbol_boundary():
    provider, _client = make_provider(pd.DataFrame())

    with pytest.raises(ValueError, match="33 symbols"):
        provider.fetch_market([f"S{i:02d}" for i in range(34)])


def test_invalid_symbol_is_rejected_before_provider_call():
    provider, client = make_provider(pd.DataFrame())

    with pytest.raises(StockServiceError, match="Invalid symbol format"):
        provider.fetch_market(["VCB;DROP"])
    client.Fetch_Trading_Data.assert_not_called()


def test_missing_credentials_fail_without_echoing_values():
    with pytest.raises(FiinQuantProviderError, match="not configured"):
        FiinQuantMarketProvider("", "")


def test_provider_wraps_login_failure_without_secret_text():
    def fail_login(_username: str, _password: str):
        raise RuntimeError("configured-password")

    provider = FiinQuantMarketProvider(
        "configured-user",
        "configured-password",
        session_factory=fail_login,
    )

    with pytest.raises(FiinQuantProviderError, match="login failed") as raised:
        provider.fetch_market(["VCB"])
    assert "configured-password" not in str(raised.value)


def test_circuit_breaker_opens_and_recovers_after_cooldown():
    current = [100.0]
    breaker = ProviderCircuitBreaker(
        failure_threshold=2,
        cooldown_seconds=30,
        clock=lambda: current[0],
    )
    breaker.record_failure()
    breaker.allow()
    breaker.record_failure()

    with pytest.raises(FiinQuantCircuitOpen):
        breaker.allow()

    current[0] = 130.0
    breaker.allow()
    assert breaker.failure_count == 0
