"""Deterministic bar reconciliation that never adjusts source evidence."""

from __future__ import annotations

import hashlib
import json

from .contracts import BarResolution, ClosedBar, QualityState
from .policy import (
    ComparisonScope,
    EvidenceReference,
    MetricComparison,
    MetricComparisonOutcome,
    ReconciliationAudit,
    ReconciliationEnforcementMode,
    ReconciliationResult,
    ReconciliationStatus,
    ReconciliationToleranceProfile,
)


def reconcile_bars(
    left: ClosedBar,
    right: ClosedBar,
    profile: ReconciliationToleranceProfile,
    *,
    scope: ComparisonScope,
) -> ReconciliationResult:
    """Compare two evidence-bearing bars while retaining both originals."""
    left_ref = EvidenceReference.from_event(left)
    right_ref = EvidenceReference.from_event(right)
    if not _comparable(left, right):
        return ReconciliationResult(
            scope=scope,
            status=ReconciliationStatus.NOT_COMPARABLE,
            left=left_ref,
            right=right_ref,
            comparisons=(),
            method_version=profile.version,
        )

    comparisons = (
        MetricComparison(
            metric="open_price",
            left_value=left.open_price,
            right_value=right.open_price,
            absolute_tolerance=profile.price,
        ),
        MetricComparison(
            metric="high_price",
            left_value=left.high_price,
            right_value=right.high_price,
            absolute_tolerance=profile.price,
        ),
        MetricComparison(
            metric="low_price",
            left_value=left.low_price,
            right_value=right.low_price,
            absolute_tolerance=profile.price,
        ),
        MetricComparison(
            metric="close_price",
            left_value=left.close_price,
            right_value=right.close_price,
            absolute_tolerance=profile.price,
        ),
        MetricComparison(
            metric="volume",
            left_value=left.volume,
            right_value=right.volume,
            absolute_tolerance=profile.volume,
        ),
    )
    if left.total_value_vnd is None or right.total_value_vnd is None:
        status = (
            ReconciliationStatus.MISMATCH
            if any(not comparison.matches for comparison in comparisons)
            else ReconciliationStatus.INCOMPLETE
        )
    else:
        comparisons += (
            MetricComparison(
                metric="total_value_vnd",
                left_value=left.total_value_vnd,
                right_value=right.total_value_vnd,
                absolute_tolerance=profile.value,
            ),
        )
        status = (
            ReconciliationStatus.MATCH
            if all(comparison.matches for comparison in comparisons)
            else ReconciliationStatus.MISMATCH
        )
    return ReconciliationResult(
        scope=scope,
        status=status,
        left=left_ref,
        right=right_ref,
        comparisons=comparisons,
        method_version=profile.version,
    )


def reconciliation_quality(result: ReconciliationResult) -> QualityState:
    return {
        ReconciliationStatus.MATCH: QualityState.VALID,
        ReconciliationStatus.MISMATCH: QualityState.DEGRADED,
        ReconciliationStatus.INCOMPLETE: QualityState.GAP,
        ReconciliationStatus.NOT_COMPARABLE: QualityState.INVALID,
    }[result.status]


def build_reconciliation_audit(
    result: ReconciliationResult,
    profile: ReconciliationToleranceProfile,
    *,
    enforcement_mode: ReconciliationEnforcementMode = (
        ReconciliationEnforcementMode.SHADOW
    ),
) -> ReconciliationAudit:
    """Build a replay-stable append-only audit identity from both evidences."""
    identity = {
        "scope": result.scope.value,
        "left_evidence_id": result.left.evidence_id,
        "right_evidence_id": result.right.evidence_id,
        "profile": profile.model_dump(mode="json"),
        "enforcement_mode": enforcement_mode.value,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ReconciliationAudit(
        audit_id=f"rec_{digest}",
        profile=profile,
        enforcement_mode=enforcement_mode,
        result=result,
        comparison_outcomes=tuple(
            MetricComparisonOutcome(
                metric=item.metric,
                absolute_delta=item.absolute_delta,
                matches=item.matches,
            )
            for item in result.comparisons
        ),
        quality_state=reconciliation_quality(result),
        checked_at=max(result.left.observed_time, result.right.observed_time),
    )


def _comparable(left: ClosedBar, right: ClosedBar) -> bool:
    return (
        left.metadata.symbol == right.metadata.symbol
        and left.metadata.trading_day == right.metadata.trading_day
        and left.metadata.exchange is right.metadata.exchange
        and left.metadata.board == right.metadata.board
        and left.metadata.product_group is right.metadata.product_group
        and left.metadata.units == right.metadata.units
        and left.resolution is right.resolution
        and left.price_basis is right.price_basis
        and (
            left.resolution is BarResolution.DAY_1
            or (
                left.window_start == right.window_start
                and left.window_end == right.window_end
            )
        )
    )
