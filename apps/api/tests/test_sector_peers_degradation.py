"""Sector peers must survive an upstream quota running out mid-fan-out.

One request fans out over every peer in an industry. Before these tests, a
single throttled peer aborted the whole request, nothing reached the cache, and
the next request repeated the same fan-out — the loop that exhausted the quota
in the first place.
"""
from unittest.mock import patch

import pytest

from src.core.vnstock_client import VnstockUnavailable
from src.stocks.financial.cache import SECTOR_PEERS_PARTIAL_TTL
from src.stocks.financial.service import FinancialService

INDUSTRY_MAP = {
    symbol: {
        "icb_code": "8300",
        "icb_name": "Ngân hàng",
        "company_name": f"{symbol} Bank",
    }
    for symbol in ("VCB", "ACB", "TCB", "MBB", "STB")
}

RATIOS = {
    "P/E": 12.0,
    "P/B": 2.0,
    "ROE (%)": 20.0,
    "ROA (%)": 2.0,
    "Market Capital (Bn. VND)": 500000.0,
}


def _service_with_ratios(ratio_side_effect):
    """Build a service whose industry map is fixed and whose ratios are staged."""
    service = FinancialService()
    patches = [
        patch("src.stocks.financial.service.Listing"),
        patch(
            "src.stocks.financial.service.fetch_industry_mapping",
            return_value=INDUSTRY_MAP,
        ),
        patch.object(
            FinancialService, "get_ratio_history", side_effect=ratio_side_effect
        ),
    ]
    return service, patches


def _run(service, patches, **kwargs):
    for active in patches:
        active.start()
    try:
        return service.get_sector_peers(**kwargs)
    finally:
        for active in reversed(patches):
            active.stop()


def test_throttled_peer_yields_a_partial_comparison_instead_of_failing():
    """Three symbols fetched, fourth throttled: the response still ships."""
    calls = []

    def ratios(symbol, periods=8):
        calls.append(symbol)
        if len(calls) > 3:
            raise VnstockUnavailable("Rate Limit Exceeded")
        return [RATIOS]

    service, patches = _service_with_ratios(ratios)
    with patch(
        "src.stocks.financial.service.sector_peers_cache"
    ) as cache:
        cache.get.return_value = None
        response = _run(service, patches, symbol="VCB", limit=10)

    assert response.symbol == "VCB"
    assert len(response.peers) == 3
    # A partial set must not squat in the cache for the full trading-hours TTL.
    assert cache.set.call_args.kwargs["ttl"] == SECTOR_PEERS_PARTIAL_TTL


def test_a_complete_comparison_keeps_the_normal_ttl():
    """No throttling means no TTL override — the default policy applies."""
    service, patches = _service_with_ratios(lambda symbol, periods=8: [RATIOS])
    with patch(
        "src.stocks.financial.service.sector_peers_cache"
    ) as cache:
        cache.get.return_value = None
        response = _run(service, patches, symbol="VCB", limit=10)

    assert len(response.peers) == len(INDUSTRY_MAP)
    assert cache.set.call_args.kwargs["ttl"] is None


def test_throttling_before_enough_peers_still_fails():
    """A median built from the target alone would compare it against itself."""

    def ratios(symbol, periods=8):
        if symbol == "VCB":
            return [RATIOS]
        raise VnstockUnavailable("Rate Limit Exceeded")

    service, patches = _service_with_ratios(ratios)
    with patch(
        "src.stocks.financial.service.sector_peers_cache"
    ) as cache:
        cache.get.return_value = None
        with pytest.raises(VnstockUnavailable):
            _run(service, patches, symbol="VCB", limit=10)

    cache.set.assert_not_called()


def test_a_throttled_target_fails_outright():
    """The target has no substitute, so its own failure ends the request."""

    def ratios(symbol, periods=8):
        raise VnstockUnavailable("Rate Limit Exceeded")

    service, patches = _service_with_ratios(ratios)
    with patch(
        "src.stocks.financial.service.sector_peers_cache"
    ) as cache:
        cache.get.return_value = None
        with pytest.raises(VnstockUnavailable):
            _run(service, patches, symbol="VCB", limit=10)

    cache.set.assert_not_called()


def test_ratio_history_is_fetched_once_per_symbol():
    """The per-symbol cache is what stops the fan-out re-hitting the provider."""
    from src.stocks.financial import service as service_module

    upstream_calls = []

    class FakeFinance:
        def __init__(self, symbol, source=None):
            self.symbol = symbol

        def ratio(self, **_kwargs):
            upstream_calls.append(self.symbol)
            raise AssertionError("cached path must not reach the provider")

    store = {}

    with patch.object(service_module, "ratio_history_cache") as cache:
        cache.get.side_effect = lambda key: store.get(key)
        cache.set.side_effect = lambda key, value, ttl=None: store.__setitem__(
            key, value
        )
        store["VCB:1"] = [RATIOS]

        with patch.object(service_module, "Finance", FakeFinance):
            first = FinancialService().get_ratio_history("VCB", periods=1)
            second = FinancialService().get_ratio_history("VCB", periods=1)

    assert first == second == [RATIOS]
    assert upstream_calls == []
