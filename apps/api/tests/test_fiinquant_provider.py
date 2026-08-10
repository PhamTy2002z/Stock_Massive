"""Tests for FiinQuant normalization and collector protection.

Every frame here mirrors a shape measured against the live free tier and
recorded on the ``prototype/fiinquant-free-tier`` branch, so the adapter is
exercised without touching the network.
"""

import os
from datetime import date, datetime, timezone
from unittest.mock import Mock

import certifi
import pandas as pd
import pytest

from src.stocks.providers.contracts import BatchTooLarge
from src.stocks.providers.fiinquant import (
    FiinQuantCircuitOpen,
    FiinQuantMarketProvider,
    FiinQuantProviderError,
    FiinQuantValuationProvider,
    ProviderCircuitBreaker,
    ensure_ca_bundle,
    shared_session_factory,
)
from src.stocks.shared import StockServiceError


NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


class FakeEvent:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def get_data(self) -> pd.DataFrame:
        return self.frame


def daily_candles() -> pd.DataFrame:
    """Two sessions for HPG, with the duplicate live row the provider emits.

    The midnight row holds the consolidated session — its volume and value are
    the ones measured to match ``get_overview`` — while the row stamped mid
    session is the live one the adapter must not prefer.
    """
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
                "close": 22_000,
                "volume": 28_003_806,
                "value": 621_432_544_300,
                "bu": 8_727_000,
                "sd": 17_403_100,
                "fb": 111_382_916_000,
                "fs": 69_002_320_650,
                "fn": 42_380_595_350,
            },
            {
                "ticker": "HPG",
                "timestamp": "2026-08-07 14:46",
                "open": 22_350,
                "high": 22_600,
                "low": 21_950,
                "close": 21_900,
                "volume": 500_000,
                "value": 11_000_000_000,
                "bu": 100_000,
                "sd": 200_000,
                "fb": 1_000_000_000,
                "fs": 900_000_000,
                "fn": 100_000_000,
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
    circuit_breaker: ProviderCircuitBreaker | None = None,
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
        circuit_breaker=circuit_breaker,
        now=lambda: NOW,
    )
    return provider, client


def assert_no_credentials(error: BaseException) -> None:
    """Walk the whole chain: __cause__ reaches the logs as readily as the text."""
    current: BaseException | None = error
    while current is not None:
        assert "configured-user" not in str(current)
        assert "configured-password" not in str(current)
        current = current.__cause__ or current.__context__


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


def test_the_live_row_never_displaces_the_consolidated_session_bar():
    provider, _client = make_provider()

    snapshot = provider.fetch_market(["HPG"])[0]

    # The 14:46 row carries a part-session volume; taking it would understate
    # the day by an order of magnitude.
    assert snapshot.volume == 28_003_806
    assert snapshot.last_price == 22_000


def test_statistics_from_an_older_session_are_left_off_rather_than_stamped_on():
    stale = overview_frame().iloc[0:1]  # 2026-08-06 only
    provider, _client = make_provider(overview=stale)

    snapshot = provider.fetch_market(["HPG"])[0]

    assert snapshot.market_cap_vnd is None
    assert snapshot.ceiling_price == 23_350


def test_one_unusable_symbol_does_not_cost_the_batch_its_snapshots():
    halted = pd.DataFrame(
        [
            {
                "ticker": "VCB",
                "timestamp": "2026-08-07 00:00",
                "open": 0,
                "high": 0,
                "low": 0,
                "close": 0,
                "volume": 0,
                "value": 0,
                "bu": 0,
                "sd": 0,
                "fb": 0,
                "fs": 0,
                "fn": 0,
            }
        ]
    )
    provider, _client = make_provider(
        candles=pd.concat([daily_candles(), halted], ignore_index=True)
    )

    snapshots = provider.fetch_market(["HPG", "VCB"])

    assert [snapshot.symbol for snapshot in snapshots] == ["HPG"]
    assert snapshots[0].volume == 28_003_806


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
    assert_no_credentials(raised.value)


def test_upstream_failure_text_never_reaches_the_caller():
    provider, client = make_provider()
    client.Fetch_Trading_Data.side_effect = RuntimeError(
        "auth failed for configured-user:configured-password"
    )

    with pytest.raises(FiinQuantProviderError) as raised:
        provider.fetch_market(["HPG"])
    assert_no_credentials(raised.value)


class GatewayTimeout(Exception):
    """A 504 the way requests raises it, with the response still attached."""

    def __init__(self):
        super().__init__("504 Server Error: Gateway Time-out for url: /Trading_Data")
        self.response = Mock(status_code=504)


def test_a_gateway_timeout_is_reported_as_a_batch_the_caller_can_split():
    """A 504 says the request was too big, not that FiinQuant is down. The
    caller can only act on that — halving and retrying — if it is told apart
    from every other provider failure."""
    provider, client = make_provider()
    client.Fetch_Trading_Data.side_effect = GatewayTimeout()

    with pytest.raises(BatchTooLarge) as raised:
        provider.fetch_market(["HPG", "VCB"])
    assert_no_credentials(raised.value)


def test_a_gateway_timeout_recognised_only_by_its_text_is_still_splittable():
    """Not every layer between here and the gateway keeps the response object."""
    provider, client = make_provider()
    client.Fetch_Trading_Data.side_effect = RuntimeError(
        "504 Gateway Time-out"
    )

    with pytest.raises(BatchTooLarge):
        provider.fetch_market(["HPG", "VCB"])


def test_an_oversized_batch_does_not_count_against_the_circuit():
    """Halving a batch would trip a breaker that counted each 504 as an outage,
    and the cycle would give up on data smaller batches would have returned."""
    breaker = ProviderCircuitBreaker(failure_threshold=2, cooldown_seconds=30)
    provider, client = make_provider(circuit_breaker=breaker)
    client.Fetch_Trading_Data.side_effect = GatewayTimeout()

    for _ in range(3):
        with pytest.raises(BatchTooLarge):
            provider.fetch_market(["HPG"])

    client.Fetch_Trading_Data.side_effect = None
    assert provider.fetch_market(["HPG"])[0].symbol == "HPG"


def test_one_login_is_shared_by_every_adapter_on_the_account():
    """The free tier grants a single concurrent connection, so two adapters
    logging in separately is one of them being kicked off."""
    logins = []
    client = Mock()
    client.Fetch_Trading_Data.return_value = FakeEvent(daily_candles())
    statistics = Mock()
    statistics.get_overview.return_value = overview_frame()
    statistics.get_ceilingfloor.return_value = ceiling_floor_frame()
    client.PriceStatistics.return_value = statistics
    client.MarketDepth.return_value.get_stock_valuation.return_value = valuation_frame()

    def count_login(username, password):
        logins.append(username)
        return client

    factory = shared_session_factory(count_login)
    market = FiinQuantMarketProvider(
        "user", "password", session_factory=factory, now=lambda: NOW
    )
    valuation = FiinQuantValuationProvider(
        "user", "password", session_factory=factory, now=lambda: NOW
    )

    market.fetch_market(["HPG"])
    valuation.fetch_valuation(["HPG"], date(2026, 8, 6), date(2026, 8, 7))

    assert len(logins) == 1


def test_circuit_opens_after_repeated_failures_and_recovers_after_cooldown():
    current = [100.0]
    breaker = ProviderCircuitBreaker(
        failure_threshold=2,
        cooldown_seconds=30,
        clock=lambda: current[0],
    )
    provider, client = make_provider(circuit_breaker=breaker)
    # Deliberately not a 504: that one is the batch being too large, which the
    # breaker leaves alone so the caller can halve and retry.
    client.Fetch_Trading_Data.side_effect = RuntimeError("connection reset by peer")

    for _ in range(2):
        with pytest.raises(FiinQuantProviderError):
            provider.fetch_market(["HPG"])

    with pytest.raises(FiinQuantCircuitOpen):
        provider.fetch_market(["HPG"])

    current[0] = 130.0
    client.Fetch_Trading_Data.side_effect = None
    assert provider.fetch_market(["HPG"])[0].symbol == "HPG"


def valuation_frame() -> pd.DataFrame:
    """Two sessions of ratios for two symbols, the shape measured on the free tier.

    ``get_stock_valuation`` returns one row per symbol per session, so a window
    of N sessions across M symbols comes back as N * M rows in one frame.
    """
    return pd.DataFrame(
        [
            {
                "ticker": "HPG",
                "timestamp": "2026-08-06 00:00",
                "pe": 12.86,
                "pb": 1.61,
            },
            {
                "ticker": "VCB",
                "timestamp": "2026-08-06 00:00",
                "pe": 13.13639165,
                "pb": 2.01789326,
            },
            {
                "ticker": "HPG",
                "timestamp": "2026-08-07 00:00",
                "pe": 12.94,
                "pb": 1.62,
            },
            {
                "ticker": "VCB",
                "timestamp": "2026-08-07 00:00",
                "pe": 13.21,
                "pb": 2.03,
            },
        ]
    )


# The window the adapter is asked for; every valuation test names one, because
# the adapter has no default to fall through to.
WINDOW_START = date(2026, 8, 6)
WINDOW_END = date(2026, 8, 7)


def make_valuation_provider(
    valuation: pd.DataFrame | None = None,
    circuit_breaker: ProviderCircuitBreaker | None = None,
) -> tuple[FiinQuantValuationProvider, Mock]:
    client = Mock()
    depth = Mock()
    depth.get_stock_valuation.return_value = (
        valuation_frame() if valuation is None else valuation
    )
    client.MarketDepth.return_value = depth
    provider = FiinQuantValuationProvider(
        "configured-user",
        "configured-password",
        session_factory=lambda _username, _password: client,
        circuit_breaker=circuit_breaker,
        now=lambda: NOW,
    )
    return provider, client


def test_fetch_valuation_yields_one_snapshot_per_session():
    provider, _client = make_valuation_provider()

    snapshots = provider.fetch_valuation(["hpg"], WINDOW_START, WINDOW_END)

    assert [snapshot.symbol for snapshot in snapshots] == ["HPG", "HPG"]
    assert [snapshot.provider_pe for snapshot in snapshots] == [12.86, 12.94]
    assert [snapshot.provider_pb for snapshot in snapshots] == [1.61, 1.62]
    # effective_at is the session the ratios describe, not the moment collected.
    assert [
        snapshot.metadata.effective_at.date() for snapshot in snapshots
    ] == [date(2026, 8, 6), date(2026, 8, 7)]
    assert all(
        snapshot.metadata.effective_at.utcoffset() is not None
        for snapshot in snapshots
    )
    assert all(snapshot.metadata.observed_at == NOW for snapshot in snapshots)


def test_fetch_valuation_asks_for_every_symbol_in_one_batched_call():
    provider, client = make_valuation_provider()

    snapshots = provider.fetch_valuation(["HPG", "VCB"], WINDOW_START, WINDOW_END)

    assert client.MarketDepth.return_value.get_stock_valuation.call_count == 1
    call = client.MarketDepth.return_value.get_stock_valuation.call_args.kwargs
    assert call["tickers"] == ["HPG", "VCB"]
    assert {snapshot.symbol for snapshot in snapshots} == {"HPG", "VCB"}


def test_the_window_reaching_the_provider_is_the_one_the_caller_named():
    provider, client = make_valuation_provider()

    provider.fetch_valuation(
        ["HPG"],
        from_date=date(2026, 1, 2),
        to_date=date(2026, 3, 4),
    )

    call = client.MarketDepth.return_value.get_stock_valuation.call_args.kwargs
    assert call["from_date"] == "2026-01-02"
    assert call["to_date"] == "2026-03-04"


def test_a_backwards_window_is_refused_before_the_provider_is_called():
    provider, client = make_valuation_provider()

    with pytest.raises(ValueError, match="from_date"):
        provider.fetch_valuation(
            ["HPG"],
            from_date=date(2026, 3, 4),
            to_date=date(2026, 1, 2),
        )
    client.MarketDepth.assert_not_called()


def test_symbols_without_valuation_data_are_skipped_not_faked():
    provider, _client = make_valuation_provider()

    snapshots = provider.fetch_valuation(["HPG", "FPT"], WINDOW_START, WINDOW_END)

    assert {snapshot.symbol for snapshot in snapshots} == {"HPG"}


def test_a_session_carrying_neither_ratio_is_dropped_without_costing_the_rest():
    blank = valuation_frame()
    blank.loc[blank["timestamp"] == "2026-08-06 00:00", ["pe", "pb"]] = None
    provider, _client = make_valuation_provider(valuation=blank)

    snapshots = provider.fetch_valuation(["HPG", "VCB"], WINDOW_START, WINDOW_END)

    assert [
        (snapshot.symbol, snapshot.metadata.effective_at.date())
        for snapshot in snapshots
    ] == [("HPG", date(2026, 8, 7)), ("VCB", date(2026, 8, 7))]


def test_a_session_carrying_one_ratio_keeps_it_rather_than_dropping_both():
    partial = valuation_frame()
    partial.loc[partial["ticker"] == "HPG", "pb"] = None
    provider, _client = make_valuation_provider(valuation=partial)

    snapshots = provider.fetch_valuation(["HPG"], WINDOW_START, WINDOW_END)

    assert [snapshot.provider_pe for snapshot in snapshots] == [12.86, 12.94]
    assert [snapshot.provider_pb for snapshot in snapshots] == [None, None]


def test_a_valuation_response_missing_a_ratio_column_is_an_error_not_a_gap():
    provider, _client = make_valuation_provider(
        valuation=valuation_frame().drop(columns=["pb"])
    )

    with pytest.raises(FiinQuantProviderError, match="missing fields: pb"):
        provider.fetch_valuation(["HPG"], WINDOW_START, WINDOW_END)


def test_an_empty_valuation_response_is_reported_rather_than_read_as_no_ratios():
    provider, _client = make_valuation_provider(valuation=pd.DataFrame())

    with pytest.raises(FiinQuantProviderError, match="no valuation data"):
        provider.fetch_valuation(["HPG"], WINDOW_START, WINDOW_END)


def test_fetch_valuation_enforces_the_measured_batch_ceiling():
    provider, _client = make_valuation_provider()

    with pytest.raises(ValueError, match="100 symbols"):
        provider.fetch_valuation(
            [f"S{i:03d}" for i in range(101)],
            WINDOW_START,
            WINDOW_END,
        )


def test_invalid_symbol_is_rejected_before_the_valuation_call():
    provider, client = make_valuation_provider()

    with pytest.raises(StockServiceError, match="Invalid symbol format"):
        provider.fetch_valuation(["VCB;DROP"], WINDOW_START, WINDOW_END)
    client.MarketDepth.assert_not_called()


def test_valuation_upstream_failure_text_never_reaches_the_caller():
    provider, client = make_valuation_provider()
    client.MarketDepth.return_value.get_stock_valuation.side_effect = RuntimeError(
        "auth failed for configured-user:configured-password"
    )

    with pytest.raises(FiinQuantProviderError) as raised:
        provider.fetch_valuation(["HPG"], WINDOW_START, WINDOW_END)
    assert_no_credentials(raised.value)


def test_valuation_circuit_opens_after_repeated_failures():
    breaker = ProviderCircuitBreaker(failure_threshold=2, clock=lambda: 100.0)
    provider, client = make_valuation_provider(circuit_breaker=breaker)
    client.MarketDepth.return_value.get_stock_valuation.side_effect = RuntimeError(
        "connection reset by peer"
    )

    for _ in range(2):
        with pytest.raises(FiinQuantProviderError):
            provider.fetch_valuation(["HPG"], WINDOW_START, WINDOW_END)

    with pytest.raises(FiinQuantCircuitOpen):
        provider.fetch_valuation(["HPG"], WINDOW_START, WINDOW_END)


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
