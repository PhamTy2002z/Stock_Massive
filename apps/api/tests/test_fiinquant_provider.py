"""Tests for FiinQuant normalization and collector protection.

Every frame here mirrors a shape measured against the live free tier and
recorded on the ``prototype/fiinquant-free-tier`` branch, so the adapter is
exercised without touching the network.
"""

import os
from datetime import datetime, timezone
from unittest.mock import Mock

import certifi
import pandas as pd
import pytest

from src.stocks.providers.fiinquant import (
    FiinQuantCircuitOpen,
    FiinQuantMarketProvider,
    FiinQuantProviderError,
    ProviderCircuitBreaker,
    ensure_ca_bundle,
)
from src.stocks.shared import StockServiceError


NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


class FakeEvent:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def get_data(self) -> pd.DataFrame:
        return self.frame


def daily_candles() -> pd.DataFrame:
    """Two sessions for HPG, with the duplicate live row the provider emits."""
    return pd.DataFrame(
        [
            {
                "ticker": "HPG",
                "timestamp": "2026-08-06 00:00",
                "open": 21_900,
                "high": 22_100,
                "low": 21_800,
                "close": 21_850,
                "volume": 20_000_000,
                "value": 437_000_000_000,
                "bu": 6_000_000,
                "sd": 9_000_000,
                "fb": 80_000_000_000,
                "fs": 60_000_000_000,
                "fn": 20_000_000_000,
            },
            {
                "ticker": "HPG",
                "timestamp": "2026-08-07 00:00",
                "open": 22_350,
                "high": 22_600,
                "low": 21_950,
                "close": 21_950,
                "volume": 27_000_000,
                "value": 600_000_000_000,
                "bu": 8_000_000,
                "sd": 17_000_000,
                "fb": 100_000_000_000,
                "fs": 65_000_000_000,
                "fn": 35_000_000_000,
            },
            {
                "ticker": "HPG",
                "timestamp": "2026-08-07 14:46",
                "open": 22_350,
                "high": 22_600,
                "low": 21_950,
                "close": 22_000,
                "volume": 28_003_806,
                "value": 621_432_544_300,
                "bu": 8_727_000,
                "sd": 17_403_100,
                "fb": 111_382_916_000,
                "fs": 69_002_320_650,
                "fn": 42_380_595_350,
            },
        ]
    )


def overview_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "HPG",
                "timestamp": "2026-08-06 00:00",
                "totalMatchVolume": 20_000_000,
                "totalMatchValue": 437_000_000_000,
                "totalDealVolume": 0,
                "totalDealValue": 0,
                "percentPriceChange": -0.004,
                "marketCap": 184_000_000_000_000,
            },
            {
                "ticker": "HPG",
                "timestamp": "2026-08-07 00:00",
                "totalMatchVolume": 13_044_079,
                "totalMatchValue": 287_684_908_850,
                "totalDealVolume": 200_000,
                "totalDealValue": 4_070_000_000,
                "percentPriceChange": 0.006864988558352492,
                "marketCap": 185_745_219_440_000,
            },
        ]
    )


def ceiling_floor_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ticker": "HPG",
                "Timestamp": "2026-08-07 14:46",
                "CeilingPrice": 23_350.0,
                "FloorPrice": 20_350.0,
            }
        ]
    )


def make_provider(
    candles: pd.DataFrame | None = None,
    overview: pd.DataFrame | None = None,
    ceiling_floor: pd.DataFrame | None = None,
) -> tuple[FiinQuantMarketProvider, Mock]:
    client = Mock()
    client.Fetch_Trading_Data.return_value = FakeEvent(
        daily_candles() if candles is None else candles
    )
    statistics = Mock()
    statistics.get_overview.return_value = (
        overview_frame() if overview is None else overview
    )
    statistics.get_ceilingfloor.return_value = (
        ceiling_floor_frame() if ceiling_floor is None else ceiling_floor
    )
    client.PriceStatistics.return_value = statistics
    provider = FiinQuantMarketProvider(
        "configured-user",
        "configured-password",
        session_factory=lambda _username, _password: client,
        now=lambda: NOW,
    )
    return provider, client


def test_fetch_market_builds_a_whole_session_from_three_calls():
    provider, client = make_provider()

    snapshots = provider.fetch_market(["hpg", "HPG"])

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.symbol == "HPG"
    # Prices stay exactly as the provider reported them: already VND.
    assert snapshot.last_price == 22_000
    assert snapshot.open_price == 22_350
    assert snapshot.high_price == 22_600
    assert snapshot.low_price == 21_950
    assert snapshot.volume == 28_003_806
    assert snapshot.total_value_vnd == 621_432_544_300
    # bu/sd are quantities, fb/fs/fn are money — the pairing that must not swap.
    assert snapshot.active_buy_volume == 8_727_000
    assert snapshot.active_sell_volume == 17_403_100
    assert snapshot.foreign_buy_value_vnd == 111_382_916_000
    assert snapshot.foreign_sell_value_vnd == 69_002_320_650
    assert snapshot.foreign_net_value_vnd == 42_380_595_350
    assert snapshot.ceiling_price == 23_350
    assert snapshot.floor_price == 20_350
    assert snapshot.market_cap_vnd == 185_745_219_440_000
    assert snapshot.metadata.effective_at.utcoffset() is not None
    assert snapshot.metadata.observed_at == NOW


def test_reference_price_and_change_come_from_the_previous_session():
    provider, _client = make_provider()

    snapshot = provider.fetch_market(["HPG"])[0]

    # 2026-08-07 has two rows; the session before it closed at 21_850.
    assert snapshot.reference_price == 21_850
    assert snapshot.change_pct == pytest.approx((22_000 - 21_850) / 21_850 * 100)


def test_fetch_market_asks_for_every_symbol_in_one_batched_call():
    provider, client = make_provider()

    provider.fetch_market(["HPG", "VCB", "FPT"])

    assert client.Fetch_Trading_Data.call_count == 1
    call = client.Fetch_Trading_Data.call_args.kwargs
    assert call["tickers"] == ["HPG", "VCB", "FPT"]
    assert call["by"] == "1d"
    assert call["realtime"] is False
    assert set(call["fields"]) >= {"value", "bu", "sd", "fb", "fs", "fn"}

    statistics = client.PriceStatistics.return_value
    assert statistics.get_overview.call_args.kwargs["tickers"] == ["HPG", "VCB", "FPT"]
    assert statistics.get_ceilingfloor.call_args.kwargs["tickers"] == [
        "HPG",
        "VCB",
        "FPT",
    ]


def test_symbols_absent_from_the_response_are_skipped_not_faked():
    provider, _client = make_provider()

    snapshots = provider.fetch_market(["HPG", "VCB"])

    assert [snapshot.symbol for snapshot in snapshots] == ["HPG"]


def test_a_symbol_missing_only_its_statistics_keeps_its_market_fields():
    provider, _client = make_provider(
        overview=overview_frame().iloc[0:0],
        ceiling_floor=ceiling_floor_frame().iloc[0:0],
    )

    snapshot = provider.fetch_market(["HPG"])[0]

    assert snapshot.last_price == 22_000
    assert snapshot.market_cap_vnd is None
    assert snapshot.ceiling_price is None
    assert snapshot.floor_price is None


def test_a_response_missing_a_requested_field_is_an_error_not_a_gap():
    provider, _client = make_provider(candles=daily_candles().drop(columns=["fn"]))

    with pytest.raises(FiinQuantProviderError, match="missing fields: fn"):
        provider.fetch_market(["HPG"])


def test_an_empty_response_is_reported_rather_than_read_as_an_empty_market():
    provider, _client = make_provider(candles=pd.DataFrame())

    with pytest.raises(FiinQuantProviderError, match="no market data"):
        provider.fetch_market(["HPG"])


def test_fetch_market_enforces_the_measured_batch_ceiling():
    provider, _client = make_provider()

    with pytest.raises(ValueError, match="100 symbols"):
        provider.fetch_market([f"S{i:03d}" for i in range(101)])


def test_invalid_symbol_is_rejected_before_provider_call():
    provider, client = make_provider()

    with pytest.raises(StockServiceError, match="Invalid symbol format"):
        provider.fetch_market(["VCB;DROP"])
    client.Fetch_Trading_Data.assert_not_called()


def test_missing_credentials_fail_without_echoing_values():
    with pytest.raises(FiinQuantProviderError, match="not configured"):
        FiinQuantMarketProvider("", "")


def test_provider_wraps_login_failure_without_secret_text():
    def fail_login(_username: str, _password: str):
        raise RuntimeError("configured-user / configured-password")

    provider = FiinQuantMarketProvider(
        "configured-user",
        "configured-password",
        session_factory=fail_login,
    )

    with pytest.raises(FiinQuantProviderError, match="login failed") as raised:
        provider.fetch_market(["VCB"])
    assert "configured-password" not in str(raised.value)
    assert "configured-user" not in str(raised.value)


def test_upstream_failure_text_never_reaches_the_caller():
    provider, client = make_provider()
    client.Fetch_Trading_Data.side_effect = RuntimeError(
        "auth failed for configured-user:configured-password"
    )

    with pytest.raises(FiinQuantProviderError) as raised:
        provider.fetch_market(["HPG"])
    assert "configured-password" not in str(raised.value)
    assert "configured-user" not in str(raised.value)


def test_circuit_opens_after_repeated_failures_and_recovers_after_cooldown():
    current = [100.0]
    breaker = ProviderCircuitBreaker(
        failure_threshold=2,
        cooldown_seconds=30,
        clock=lambda: current[0],
    )
    provider, client = make_provider()
    provider._circuit = breaker
    client.Fetch_Trading_Data.side_effect = RuntimeError("gateway timeout")

    for _ in range(2):
        with pytest.raises(FiinQuantProviderError):
            provider.fetch_market(["HPG"])

    with pytest.raises(FiinQuantCircuitOpen):
        provider.fetch_market(["HPG"])

    current[0] = 130.0
    client.Fetch_Trading_Data.side_effect = None
    assert provider.fetch_market(["HPG"])[0].symbol == "HPG"


def test_ensure_ca_bundle_sets_certifi_when_unset(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)

    bundle = ensure_ca_bundle()

    assert bundle == certifi.where()
    assert os.environ["SSL_CERT_FILE"] == certifi.where()


def test_ensure_ca_bundle_keeps_an_operator_supplied_bundle(monkeypatch, tmp_path):
    supplied = tmp_path / "company-ca.pem"
    supplied.write_text("-----BEGIN CERTIFICATE-----\n")
    monkeypatch.setenv("SSL_CERT_FILE", str(supplied))

    assert ensure_ca_bundle() == str(supplied)
    assert os.environ["SSL_CERT_FILE"] == str(supplied)


def test_a_ca_bundle_that_is_not_on_disk_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "absent.pem"))

    with pytest.raises(FiinQuantProviderError, match="CA bundle"):
        ensure_ca_bundle()
