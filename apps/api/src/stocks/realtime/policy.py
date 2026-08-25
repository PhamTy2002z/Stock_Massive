"""Source ownership, outcomes, provenance, reconciliation, and retention."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping, Self

from pydantic import Field, field_validator, model_validator

from ..shared import StockServiceError, validate_symbol

from .contracts import (
    EventFamily,
    MarketDataSource,
    NormalizedMarketEvent,
    QualityState,
    RealtimeContract,
)


class DataDomain(str, Enum):
    REALTIME_MICROSTRUCTURE = "realtime_microstructure"
    HISTORICAL_EOD = "historical_eod"
    VALUATION = "valuation"
    REFERENCE = "reference"
    FUNDAMENTAL = "fundamental"


class SourceOwnership(RealtimeContract):
    main: MarketDataSource
    cover: tuple[MarketDataSource, ...] = ()

    @model_validator(mode="after")
    def require_distinct_sources(self) -> Self:
        if self.main in self.cover or len(self.cover) != len(set(self.cover)):
            raise ValueError("source ownership entries must be distinct")
        return self

    def admits(self, source: MarketDataSource) -> bool:
        return source is self.main or source in self.cover


SOURCE_OWNERSHIP: Mapping[DataDomain, SourceOwnership] = MappingProxyType(
    {
        DataDomain.REALTIME_MICROSTRUCTURE: SourceOwnership(
            main=MarketDataSource.DNSE
        ),
        DataDomain.HISTORICAL_EOD: SourceOwnership(
            main=MarketDataSource.FIINQUANT,
            cover=(MarketDataSource.VNSTOCK,),
        ),
        DataDomain.VALUATION: SourceOwnership(
            main=MarketDataSource.FIINQUANT,
            cover=(MarketDataSource.VNSTOCK,),
        ),
        DataDomain.REFERENCE: SourceOwnership(main=MarketDataSource.VNSTOCK),
        DataDomain.FUNDAMENTAL: SourceOwnership(main=MarketDataSource.VNSTOCK),
    }
)


class DataOutcomeKind(str, Enum):
    INVALID_REQUEST = "invalid_request"
    UNKNOWN_SYMBOL = "unknown_symbol"
    NO_SESSION = "no_session"
    RETENTION_MISS = "retention_miss"
    SILENT_EMPTY = "silent_empty"
    STALE_DATA = "stale_data"
    DUPLICATE = "duplicate"
    GAP = "gap"
    PROVIDER_FAILURE = "provider_failure"


class OutcomeDisposition(str, Enum):
    REFUSE = "refuse"
    ABSENT = "absent"
    DEGRADE = "degrade"
    IGNORE = "ignore"
    RECONCILE = "reconcile"
    RETRY = "retry"


OUTCOME_DISPOSITION: Mapping[DataOutcomeKind, OutcomeDisposition] = MappingProxyType(
    {
        DataOutcomeKind.INVALID_REQUEST: OutcomeDisposition.REFUSE,
        DataOutcomeKind.UNKNOWN_SYMBOL: OutcomeDisposition.REFUSE,
        DataOutcomeKind.NO_SESSION: OutcomeDisposition.ABSENT,
        DataOutcomeKind.RETENTION_MISS: OutcomeDisposition.REFUSE,
        DataOutcomeKind.SILENT_EMPTY: OutcomeDisposition.DEGRADE,
        DataOutcomeKind.STALE_DATA: OutcomeDisposition.DEGRADE,
        DataOutcomeKind.DUPLICATE: OutcomeDisposition.IGNORE,
        DataOutcomeKind.GAP: OutcomeDisposition.RECONCILE,
        DataOutcomeKind.PROVIDER_FAILURE: OutcomeDisposition.RETRY,
    }
)


class DataOutcome(RealtimeContract):
    """A safe typed result with no free-form provider payload or exception text."""

    kind: DataOutcomeKind
    source: MarketDataSource | None
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    evidence_ids: tuple[str, ...] = ()

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("outcome evidence IDs must be unique")
        if any(
            len(item) != 68
            or not item.startswith("evt_")
            or any(character not in "0123456789abcdef" for character in item[4:])
            for item in value
        ):
            raise ValueError("outcome evidence IDs must be canonical event identities")
        return value

    @property
    def disposition(self) -> OutcomeDisposition:
        return OUTCOME_DISPOSITION[self.kind]

    @property
    def retryable(self) -> bool:
        return self.disposition is OutcomeDisposition.RETRY


class EvidenceReference(RealtimeContract):
    evidence_id: str = Field(pattern=r"^evt_[0-9a-f]{64}$")
    source: MarketDataSource
    event_family: EventFamily
    symbol: str
    trading_day: date
    observed_time: datetime
    schema_version: int = Field(ge=1)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        try:
            return validate_symbol(value)
        except StockServiceError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("observed_time")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evidence timestamps must be timezone-aware")
        return value

    @classmethod
    def from_event(cls, event: NormalizedMarketEvent) -> "EvidenceReference":
        metadata = event.metadata
        return cls(
            evidence_id=metadata.evidence_id,
            source=metadata.source,
            event_family=metadata.event_family,
            symbol=metadata.symbol,
            trading_day=metadata.trading_day,
            observed_time=metadata.observed_time,
            schema_version=metadata.schema_version,
        )


def merge_evidence(
    events: Iterable[NormalizedMarketEvent],
) -> Mapping[str, NormalizedMarketEvent]:
    """Index evidence without permitting an identity collision to overwrite."""
    merged: dict[str, NormalizedMarketEvent] = {}
    for event in events:
        evidence_id = event.metadata.evidence_id
        existing = merged.get(evidence_id)
        if existing is not None:
            raise ValueError(
                f"duplicate evidence {evidence_id} must carry explicit duplicate semantics"
            )
        if event.metadata.quality_state is QualityState.DUPLICATE:
            if event.metadata.duplicate_of not in merged:
                raise ValueError("duplicate_of must reference evidence already in the batch")
        merged[evidence_id] = event
    return MappingProxyType(merged)


class ComparisonScope(str, Enum):
    DAILY = "daily"
    INTRADAY = "intraday"
    CROSS_PROVIDER = "cross_provider"


class ReconciliationStatus(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    INCOMPLETE = "incomplete"
    NOT_COMPARABLE = "not_comparable"


class MetricComparison(RealtimeContract):
    metric: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    left_value: Decimal
    right_value: Decimal
    absolute_tolerance: Decimal = Field(ge=0)

    @property
    def absolute_delta(self) -> Decimal:
        return abs(self.left_value - self.right_value)

    @property
    def matches(self) -> bool:
        return self.absolute_delta <= self.absolute_tolerance


class MetricComparisonOutcome(RealtimeContract):
    metric: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    absolute_delta: Decimal = Field(ge=0)
    matches: bool


class ReconciliationEnforcementMode(str, Enum):
    SHADOW = "shadow"


class ReconciliationToleranceProfile(RealtimeContract):
    """Owner-approved absolute tolerances for one deterministic method."""

    version: int = Field(ge=1)
    price: Decimal = Field(ge=0)
    volume: Decimal = Field(ge=0)
    value: Decimal = Field(ge=0)


STRICT_RECONCILIATION_PROFILE_V1 = ReconciliationToleranceProfile(
    version=1,
    price=Decimal(0),
    volume=Decimal(0),
    value=Decimal(0),
)


class ReconciliationResult(RealtimeContract):
    scope: ComparisonScope
    status: ReconciliationStatus
    left: EvidenceReference
    right: EvidenceReference
    comparisons: tuple[MetricComparison, ...]
    method_version: int = Field(ge=1)

    @model_validator(mode="after")
    def preserve_distinct_comparable_evidence(self) -> Self:
        if self.left.evidence_id == self.right.evidence_id:
            raise ValueError("reconciliation requires two distinct evidence records")
        if self.left.symbol != self.right.symbol:
            raise ValueError("reconciliation evidence must address the same symbol")
        if self.left.trading_day != self.right.trading_day:
            raise ValueError("reconciliation evidence must address the same trading day")
        if (
            self.scope is ComparisonScope.CROSS_PROVIDER
            and self.left.source is self.right.source
        ):
            raise ValueError("cross-provider reconciliation requires distinct sources")
        computed_match = bool(self.comparisons) and all(
            comparison.matches for comparison in self.comparisons
        )
        if self.status is ReconciliationStatus.MATCH and not computed_match:
            raise ValueError("match status conflicts with metric comparisons")
        if self.status is ReconciliationStatus.MISMATCH and computed_match:
            raise ValueError("mismatch status conflicts with metric comparisons")
        return self


class ReconciliationAudit(RealtimeContract):
    """Immutable shadow-mode record of one evidence comparison."""

    audit_id: str = Field(pattern=r"^rec_[0-9a-f]{64}$")
    profile: ReconciliationToleranceProfile
    enforcement_mode: ReconciliationEnforcementMode
    result: ReconciliationResult
    comparison_outcomes: tuple[MetricComparisonOutcome, ...]
    quality_state: QualityState
    checked_at: datetime

    @field_validator("checked_at")
    @classmethod
    def require_aware_checked_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reconciliation checked_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_profile_and_quality_consistency(self) -> Self:
        if self.profile.version != self.result.method_version:
            raise ValueError("reconciliation profile and method versions must match")
        expected_outcomes = tuple(
            MetricComparisonOutcome(
                metric=item.metric,
                absolute_delta=item.absolute_delta,
                matches=item.matches,
            )
            for item in self.result.comparisons
        )
        if self.comparison_outcomes != expected_outcomes:
            raise ValueError("reconciliation comparison outcomes conflict with result")
        expected = {
            ReconciliationStatus.MATCH: QualityState.VALID,
            ReconciliationStatus.MISMATCH: QualityState.DEGRADED,
            ReconciliationStatus.INCOMPLETE: QualityState.GAP,
            ReconciliationStatus.NOT_COMPARABLE: QualityState.INVALID,
        }[self.result.status]
        if self.quality_state is not expected:
            raise ValueError("reconciliation quality conflicts with its status")
        return self


class RetentionClass(str, Enum):
    RAW_EVENT = "raw_event"
    NORMALIZED_EVENT = "normalized_event"
    PROJECTION = "projection"
    REPLAY_ARTIFACT = "replay_artifact"
    OPERATIONAL_METADATA = "operational_metadata"


class RetentionRule(RealtimeContract):
    retention_class: RetentionClass
    days: int = Field(gt=0)
    contains_raw_payload: bool
    rationale: str = Field(min_length=1, max_length=240)


RETENTION_POLICY_VERSION = 1
RETENTION_POLICY: Mapping[int, Mapping[RetentionClass, RetentionRule]] = MappingProxyType(
    {
        RETENTION_POLICY_VERSION: MappingProxyType(
            {
                RetentionClass.RAW_EVENT: RetentionRule(
                    retention_class=RetentionClass.RAW_EVENT,
                    days=30,
                    contains_raw_payload=True,
                    rationale="Bound incident replay while minimizing provider-payload exposure.",
                ),
                RetentionClass.NORMALIZED_EVENT: RetentionRule(
                    retention_class=RetentionClass.NORMALIZED_EVENT,
                    days=400,
                    contains_raw_payload=False,
                    rationale="Support one-year comparison and deterministic recomputation.",
                ),
                RetentionClass.PROJECTION: RetentionRule(
                    retention_class=RetentionClass.PROJECTION,
                    days=400,
                    contains_raw_payload=False,
                    rationale="Keep projections aligned with their normalized evidence window.",
                ),
                RetentionClass.REPLAY_ARTIFACT: RetentionRule(
                    retention_class=RetentionClass.REPLAY_ARTIFACT,
                    days=180,
                    contains_raw_payload=False,
                    rationale="Retain bounded evaluation fixtures without indefinite duplication.",
                ),
                RetentionClass.OPERATIONAL_METADATA: RetentionRule(
                    retention_class=RetentionClass.OPERATIONAL_METADATA,
                    days=90,
                    contains_raw_payload=False,
                    rationale="Cover incident trends while keeping telemetry retention bounded.",
                ),
            }
        )
    }
)


def retention_rule(retention_class: RetentionClass, *, version: int = 1) -> RetentionRule:
    policy = RETENTION_POLICY.get(version)
    if policy is None:
        raise ValueError(f"unknown retention policy version: {version}")
    return policy[retention_class]
