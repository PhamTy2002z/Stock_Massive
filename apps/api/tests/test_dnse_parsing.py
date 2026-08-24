"""Sanitized DNSE wire fixtures must map or refuse at the S0 boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.stocks.realtime import DataOutcomeKind, EventFamily
from src.stocks.realtime.dnse import DnseEventParser, SnapshotDeduplicator


NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
BASE = {
    "marketId": "STO",
    "boardId": "G1",
    "symbol": "FPT",
    "time": "2026-08-24T07:00:00Z",
    "tradingSessionId": 2,
}


@pytest.fixture
def parser() -> DnseEventParser:
    return DnseEventParser(clock=lambda: NOW)


@pytest.mark.parametrize(
    ("payload", "family"),
    [
        (
            {
                **BASE,
                "T": "te",
                "matchPrice": "71.4",
                "matchQtty": 10,
                "grossTradeAmount": "0.000714",
                "side": 1,
                "tradeId": "trade-1",
            },
            EventFamily.TRADE,
        ),
        (
            {
                **BASE,
                "T": "f",
                "transactTime": "2026-08-24T07:00:00Z",
                "totalBuyVolume": 100,
                "totalSellVolume": 50,
                "totalBuyTradedAmount": 7_140_000,
                "totalSellTradedAmount": 3_570_000,
                "foreignerBuyPossibleQuantity": 1_000,
                "foreignerOrderLimitQuantity": 2_000,
            },
            EventFamily.FOREIGN_FLOW,
        ),
        (
            {
                **BASE,
                "T": "ep",
                "auctionSession": "ATC",
                "expectedTradePrice": "71.4",
                "expectedTradeQuantity": 500,
            },
            EventFamily.AUCTION,
        ),
        (
            {
                "T": "s",
                "marketId": "STO",
                "boardId": "G1",
                "symbol": "MARKET",
                "time": "2026-08-24T07:00:00Z",
                "tradingSessionId": 2,
                "eventId": "session-2",
                "isTrading": True,
            },
            EventFamily.SESSION,
        ),
        (
            {
                "T": "mi",
                "marketId": "STO",
                "indexName": "VNINDEX",
                "time": "2026-08-24T07:00:00Z",
                "valueIndexes": "1285.42",
                "changedValue": "3.1",
                "changedRatio": "0.24",
            },
            EventFamily.INDEX,
        ),
        (
            {
                **BASE,
                "T": "sd",
                "productGrpId": "ST",
                "securityGroupId": "ST",
                "securityStatus": "listed",
                "isin": "VN000000FPT1",
                "basicPrice": "71.4",
                "ceilingPrice": "76.3",
                "floorPrice": "66.5",
            },
            EventFamily.SECURITY_DEFINITION,
        ),
        (
            {
                **BASE,
                "T": "oc",
                "resolution": "1",
                "endTime": "2026-08-24T07:00:00Z",
                "open": "71.5",
                "high": "71.6",
                "low": "71.3",
                "close": "71.4",
                "volume": 1000,
            },
            EventFamily.CLOSED_BAR,
        ),
    ],
)
def test_sanitized_admitted_json_fixtures_map_to_valid_contracts(parser, payload, family):
    result = parser.parse(payload, request_id=f"fixture-{family.value}")

    assert result.outcome is None
    assert result.event is not None
    assert result.event.metadata.event_family is family
    assert result.event.metadata.source.value == "dnse"
    assert len(result.event.metadata.raw_payload_hash) == 64


def test_checked_in_sanitized_fixture_covers_every_currently_admitted_family(parser):
    fixture = Path(__file__).parent / "fixtures/dnse/admitted-json-events.json"
    payloads = json.loads(fixture.read_text())
    results = [parser.parse(payload, request_id=f"fixture-{index}") for index, payload in enumerate(payloads)]

    assert all(result.event is not None for result in results)
    assert {result.event.metadata.event_family for result in results if result.event} == set(EventFamily) - {EventFamily.BOOK}


def test_quote_and_malformed_payloads_refuse_without_raw_field_leakage(parser):
    secret = "must-never-leak"
    quote = parser.parse({**BASE, "T": "q", "bids": [], "authorization": secret}, request_id="quote-1")
    malformed = parser.parse({"T": "te", "api_secret": secret}, request_id="bad-1")

    for result in (quote, malformed):
        assert result.outcome and result.outcome.kind is DataOutcomeKind.INVALID_REQUEST
        assert secret not in result.outcome.model_dump_json()


def test_duplicate_identity_uses_payload_hash_not_provider_timestamp(parser):
    first = parser.parse(
        {**BASE, "T": "te", "matchPrice": 71.4, "matchQtty": 10, "side": 1},
        request_id="one",
    ).event
    changed = parser.parse(
        {**BASE, "T": "te", "matchPrice": 71.5, "matchQtty": 10, "side": 1},
        request_id="two",
    ).event
    assert first and changed
    dedupe = SnapshotDeduplicator()

    assert dedupe.classify(first) is None
    assert dedupe.classify(changed) is None
    duplicate = dedupe.classify(first)
    assert duplicate and duplicate.kind is DataOutcomeKind.DUPLICATE
