"""Compact builders shared by the Phase 2 evaluation tests."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from src.core.llm import Completion, ToolCall, Usage
from src.eval.contracts import (
    CaseFile,
    CaseInput,
    EvidenceRecord,
    Expectation,
    SnapshotFile,
    UserContext,
)
from src.stocks.providers import Capability, PriceBasis, ProviderSource
from src.stocks.providers.contracts import (
    MARKET_SCHEMA_VERSION,
    MarketSnapshot,
    SnapshotMetadata,
)
from src.stocks.providers.normalize import VN_TZ

NOW = datetime(2026, 8, 23, 13, 0, tzinfo=timezone.utc)
TRADING_DAY = date(2026, 8, 21)
SYMBOL = "EVLFPT"


def conversation_case() -> CaseFile:
    return CaseFile(
        schema="eval.case@1",
        case_id="conversation-frozen-field",
        surface="conversation",
        family="fact-unit-as-of",
        title="Read one frozen closing price",
        as_of=TRADING_DAY,
        input=CaseInput(prompt="What was the frozen closing price?"),
        user_context=UserContext(
            synthetic_user_id="synthetic-eval-user", display_name="Eval User"
        ),
        expectations=(Expectation(kind="terminal_completed"),),
    )


def conversation_snapshot() -> SnapshotFile:
    return SnapshotFile(
        schema="eval.snapshot@1",
        snapshot_id="conversation-field-result",
        description="One normalized fixture tool result.",
        evidence=(
            EvidenceRecord(
                source="fiinquant",
                capability="market",
                entity="EVLFPT",
                unit="VND",
                value=100_000,
                effective_at=NOW,
                published_at=NOW,
                ingested_at=NOW,
                provenance="synthetic fixture",
                price_basis="raw",
                metadata={
                    "fixture_kind": "tool_result",
                    "tool_name": "get_field",
                    "arguments": {"field_id": "price.close"},
                    "result": {
                        "fieldId": "price.close",
                        "value": 100_000,
                        "unit": "VND",
                        "asOf": TRADING_DAY.isoformat(),
                        "evidence_references": ["snapshot:conversation-field-result"],
                    },
                },
            ),
        ),
    )


def conversation_script(model: str) -> tuple[Completion, Completion]:
    return (
        Completion(
            model=model,
            tool_calls=(
                ToolCall(
                    id="field-1",
                    name="get_field",
                    arguments={"field_id": "price.close"},
                ),
            ),
            usage=Usage(input_tokens=10, output_tokens=5),
            finish_reason="tool_calls",
            request_id="req-conversation-tool",
        ),
        Completion(
            model=model,
            text="The frozen close was 100,000 VND.",
            usage=Usage(input_tokens=20, output_tokens=8),
            request_id="req-conversation-answer",
        ),
    )


def analysis_case() -> CaseFile:
    return CaseFile(
        schema="eval.case@1",
        case_id="analysis-frozen-market",
        surface="analysis",
        family="multi-axis-synthesis",
        title="Produce one Analysis from frozen sessions",
        as_of=TRADING_DAY,
        input=CaseInput(symbol=SYMBOL, trading_day=TRADING_DAY),
        expectations=(Expectation(kind="terminal_completed"),),
    )


def analysis_snapshot() -> SnapshotFile:
    sessions = _weekdays_back(TRADING_DAY, 61)
    evidence = [
        EvidenceRecord(
            source="vnstock",
            capability="reference",
            entity=SYMBOL,
            effective_at=NOW,
            published_at=NOW,
            ingested_at=NOW,
            provenance="synthetic listing fixture",
            metadata={
                "fixture_kind": "listing_roster",
                "exchange": "HOSE",
                "company_name": "Evaluation FPT",
                "icb_code": None,
            },
        )
    ]
    evidence.append(
        EvidenceRecord(
            source="fiinquant",
            capability="market",
            entity=SYMBOL,
            effective_at=NOW,
            published_at=NOW,
            ingested_at=NOW,
            provenance="synthetic field-catalog fixture",
            metadata={
                "fixture_kind": "tool_result",
                "tool_name": "list_fields",
                "arguments": {},
                "result": {
                    "fields": ["realized_volatility.yang_zhang_annualized_pct"],
                    "evidence_references": ["snapshot:analysis-market-window"],
                },
            },
        )
    )
    for index, day in enumerate(sessions):
        stamp = datetime.combine(day, time.min, tzinfo=VN_TZ)
        close = 100_000.0 + (index % 7) * 250.0
        snapshot = MarketSnapshot(
            symbol=SYMBOL,
            metadata=SnapshotMetadata(
                source=ProviderSource.FIINQUANT,
                effective_at=stamp,
                observed_at=NOW,
                schema_version=MARKET_SCHEMA_VERSION,
            ),
            price_basis=PriceBasis.RAW,
            open_price=close - 100.0,
            high_price=close + 500.0,
            low_price=close - 500.0,
            last_price=close,
            volume=1_000_000,
            total_value_vnd=100_000_000_000.0,
            market_cap_vnd=10_000_000_000_000.0,
        )
        evidence.append(
            EvidenceRecord(
                source="fiinquant",
                capability=Capability.MARKET.value,
                entity=SYMBOL,
                unit="VND",
                value=close,
                effective_at=stamp,
                published_at=stamp,
                ingested_at=NOW,
                provenance="synthetic market fixture",
                price_basis="raw",
                metadata={
                    "fixture_kind": "provider_snapshot",
                    "schema_version": MARKET_SCHEMA_VERSION,
                    "payload": snapshot.model_dump(mode="json"),
                },
            )
        )
    return SnapshotFile(
        schema="eval.snapshot@1",
        snapshot_id="analysis-market-window",
        description="Sixty-one normalized sessions and one listing row.",
        evidence=tuple(evidence),
    )


def analysis_fragment() -> dict:
    axes = ("technical", "fundamental", "money_flow", "news")
    return {
        "verdict": "hold",
        "verdictLine": "Measured volatility is the usable evidence tonight.",
        "thesis": "The frozen technical record supports a neutral stance.",
        "citedFieldIds": ["realized_volatility.yang_zhang_annualized_pct"],
        "axes": [
            {
                "axis": axis,
                "emphasis": "lead" if axis == "technical" else "context",
                "emphasisReason": "The frozen store is strongest here.",
                "read": "Use only the available point-in-time evidence.",
            }
            for axis in axes
        ],
    }


def _weekdays_back(end: date, count: int) -> tuple[date, ...]:
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(days))


__all__ = [
    "NOW",
    "SYMBOL",
    "TRADING_DAY",
    "analysis_case",
    "analysis_fragment",
    "analysis_snapshot",
    "conversation_case",
    "conversation_script",
    "conversation_snapshot",
]
