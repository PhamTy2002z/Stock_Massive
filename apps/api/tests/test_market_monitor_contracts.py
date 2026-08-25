"""Public Market Monitor contracts keep evidence and coverage interpretable."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.stocks.monitor.schemas import (
    MetricValue,
    MonitorCoverage,
    MonitorExchange,
    MonitorMeta,
    MonitorSource,
    MonitorState,
)


AS_OF = datetime(2026, 8, 24, 8, tzinfo=UTC)


def coverage(**overrides) -> MonitorCoverage:
    values = {
        "eligible": 100,
        "evaluated": 80,
        "missing": 20,
        "state": MonitorState.PARTIAL,
    }
    values.update(overrides)
    return MonitorCoverage(**values)


def test_coverage_counts_and_state_must_agree() -> None:
    assert coverage().missing == 20

    with pytest.raises(ValidationError, match="eligible minus evaluated"):
        coverage(missing=19)
    with pytest.raises(ValidationError, match="complete coverage"):
        coverage(evaluated=80, missing=20, state=MonitorState.COMPLETE)
    with pytest.raises(ValidationError, match="unavailable coverage"):
        coverage(evaluated=1, missing=99, state=MonitorState.UNAVAILABLE)


def test_metric_requires_timezone_method_unit_and_reason_when_absent() -> None:
    metric = MetricValue(
        value=1.25,
        unit="ratio",
        as_of=AS_OF,
        method="breadth.advance_decline.v1",
    )
    assert metric.value == 1.25

    with pytest.raises(ValidationError, match="timezone-aware"):
        MetricValue(value=1, unit="count", as_of=AS_OF.replace(tzinfo=None), method="v1")
    with pytest.raises(ValidationError, match="reason"):
        MetricValue(value=None, unit="count", as_of=AS_OF, method="v1")


def test_monitor_metadata_keeps_source_time_quality_and_methods() -> None:
    source = MonitorSource(
        source="fiinquant",
        effective_at=AS_OF,
        observed_at=AS_OF,
        freshness_seconds=0,
        stale=False,
    )
    meta = MonitorMeta(
        exchange=MonitorExchange.ALL,
        as_of=AS_OF,
        generated_at=AS_OF,
        state=MonitorState.PARTIAL,
        coverage=coverage(),
        sources=(source,),
        issues=("realtime_partial",),
        method_versions={"breadth": "v1"},
    )

    assert meta.coverage.evaluated == 80
    assert meta.sources[0].source == "fiinquant"
    assert meta.method_versions == {"breadth": "v1"}

    with pytest.raises(ValidationError, match="Extra inputs"):
        MonitorMeta(
            exchange=MonitorExchange.ALL,
            as_of=AS_OF,
            generated_at=AS_OF,
            state=MonitorState.PARTIAL,
            coverage=coverage(),
            sources=(source,),
            method_versions={"breadth": "v1"},
            provider_payload={"secret": "must not cross the boundary"},
        )


def test_monitor_metadata_rejects_future_as_of_and_missing_methods() -> None:
    with pytest.raises(ValidationError, match="as-of cannot follow generation"):
        MonitorMeta(
            exchange=MonitorExchange.HOSE,
            as_of=AS_OF,
            generated_at=AS_OF.replace(hour=7),
            state=MonitorState.UNAVAILABLE,
            coverage=coverage(
                evaluated=0,
                missing=100,
                state=MonitorState.UNAVAILABLE,
            ),
            method_versions={"breadth": "v1"},
        )
    with pytest.raises(ValidationError, match="method version"):
        MonitorMeta(
            exchange=MonitorExchange.HNX,
            as_of=AS_OF,
            generated_at=AS_OF,
            state=MonitorState.UNAVAILABLE,
            coverage=coverage(
                evaluated=0,
                missing=100,
                state=MonitorState.UNAVAILABLE,
            ),
            method_versions={},
        )
