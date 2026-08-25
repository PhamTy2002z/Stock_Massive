"""Durable normalized-event, checkpoint, spill, health, and replay storage."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.database import sync_session_factory
from src.stocks.models import (
    RealtimeCheckpoint,
    RealtimeEvent,
    RealtimeHealth,
    RealtimeReconciliationAudit,
    RealtimeSpill,
)

from .contracts import (
    AuctionSnapshot,
    BookSnapshot,
    ClosedBar,
    EventFamily,
    ForeignFlowSnapshot,
    IndexTick,
    NormalizedMarketEvent,
    SecurityDefinition,
    SessionState,
    TradeTick,
    MarketDataSource,
)
from .health import HealthSnapshot
from .policy import (
    RETENTION_POLICY_VERSION,
    ComparisonScope,
    ReconciliationAudit,
    RetentionClass,
    retention_rule,
)


_EVENT_MODEL_BY_FAMILY = {
    EventFamily.TRADE: TradeTick,
    EventFamily.BOOK: BookSnapshot,
    EventFamily.FOREIGN_FLOW: ForeignFlowSnapshot,
    EventFamily.AUCTION: AuctionSnapshot,
    EventFamily.SESSION: SessionState,
    EventFamily.INDEX: IndexTick,
    EventFamily.SECURITY_DEFINITION: SecurityDefinition,
    EventFamily.CLOSED_BAR: ClosedBar,
}


def serialize_event(event: NormalizedMarketEvent) -> dict[str, Any]:
    """Serialize only the strict normalized contract, never provider wire data."""
    return event.model_dump(mode="json")


def deserialize_event(payload: dict[str, Any]) -> NormalizedMarketEvent:
    """Decode by the embedded family and re-run every S0 model invariant."""
    try:
        family = EventFamily(payload["metadata"]["event_family"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("stored realtime event has no valid event family") from exc
    return _EVENT_MODEL_BY_FAMILY[family].model_validate(payload)


def partition_key(event: NormalizedMarketEvent) -> str:
    metadata = event.metadata
    return f"{metadata.trading_day.isoformat()}:{metadata.event_family.value}"


@dataclass(frozen=True, slots=True)
class Checkpoint:
    consumer: str
    partition_key: str
    evidence_id: str
    provider_time: datetime
    observed_time: datetime

    @property
    def order_key(self) -> tuple[datetime, datetime, str]:
        return self.provider_time, self.observed_time, self.evidence_id


@dataclass(frozen=True, slots=True)
class SpillRecord:
    spill_id: int
    event: NormalizedMarketEvent
    reason: str


@dataclass(frozen=True, slots=True)
class EventPage:
    events: tuple[NormalizedMarketEvent, ...]
    next_cursor: Checkpoint | None


@dataclass(frozen=True, slots=True)
class RetentionPurge:
    events: int
    recovered_spills: int
    checkpoints: int
    health_records: int


_T = TypeVar("_T")


class RealtimeEventStore:
    """Short-transaction PostgreSQL owner exposed through async operations."""

    def __init__(self, session_factory: Callable[[], Session] = sync_session_factory):
        self._session_factory = session_factory

    async def append(self, event: NormalizedMarketEvent) -> bool:
        return await asyncio.to_thread(self._append, event)

    async def replay(
        self,
        trading_day: date,
        family: EventFamily,
        *,
        after: Checkpoint | None = None,
    ) -> tuple[NormalizedMarketEvent, ...]:
        return await asyncio.to_thread(self._replay, trading_day, family, after)

    async def query(
        self,
        family: EventFamily,
        symbol: str,
        *,
        start: datetime,
        end: datetime,
        source: MarketDataSource | None = None,
        after: Checkpoint | None = None,
        limit: int = 200,
    ) -> EventPage:
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("realtime query requires a valid timezone-aware window")
        if not 1 <= limit <= 1_000:
            raise ValueError("realtime query limit must be between 1 and 1000")
        return await asyncio.to_thread(
            self._query,
            family,
            symbol.upper(),
            start.astimezone(UTC),
            end.astimezone(UTC),
            source,
            after,
            limit,
        )

    async def save_checkpoint(self, consumer: str, event: NormalizedMarketEvent) -> Checkpoint:
        return await asyncio.to_thread(self._save_checkpoint, consumer, event)

    async def load_checkpoint(self, consumer: str, key: str) -> Checkpoint | None:
        return await asyncio.to_thread(self._load_checkpoint, consumer, key)

    async def spill(self, event: NormalizedMarketEvent, reason: str) -> bool:
        return await asyncio.to_thread(self._spill, event, reason)

    async def pending_spills(self, limit: int = 1_000) -> tuple[SpillRecord, ...]:
        if not 1 <= limit <= 10_000:
            raise ValueError("spill batch limit must be between 1 and 10000")
        return await asyncio.to_thread(self._pending_spills, limit)

    async def mark_spill_recovered(self, spill_id: int) -> None:
        await asyncio.to_thread(self._mark_spill_recovered, spill_id)

    async def save_health(self, snapshot: HealthSnapshot) -> None:
        await asyncio.to_thread(self._save_health, snapshot)

    async def append_reconciliation(self, audit: ReconciliationAudit) -> bool:
        return await asyncio.to_thread(self._append_reconciliation, audit)

    async def read_reconciliations(
        self,
        symbol: str,
        trading_day: date,
        *,
        scope: ComparisonScope | None = None,
        limit: int = 200,
    ) -> tuple[ReconciliationAudit, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("reconciliation query limit must be between 1 and 1000")
        return await asyncio.to_thread(
            self._read_reconciliations,
            symbol.upper(),
            trading_day,
            scope,
            limit,
        )

    async def read_health(self, scope: str) -> HealthSnapshot | None:
        return await asyncio.to_thread(self._read_health, scope)

    async def purge_expired(self, *, now: datetime | None = None) -> RetentionPurge:
        instant = now or datetime.now(UTC)
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("retention clock must be timezone-aware")
        return await asyncio.to_thread(self._purge_expired, instant)

    def _read(self, work: Callable[[Session], _T]) -> _T:
        with self._session_factory() as session:
            return work(session)

    def _write(self, work: Callable[[Session], _T]) -> _T:
        with self._session_factory() as session:
            try:
                result = work(session)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise

    def _append(self, event: NormalizedMarketEvent) -> bool:
        metadata = event.metadata

        def write(session: Session) -> bool:
            if session.get(RealtimeEvent, metadata.evidence_id) is not None:
                return False
            session.add(
                RealtimeEvent(
                    evidence_id=metadata.evidence_id,
                    trading_day=metadata.trading_day,
                    event_family=metadata.event_family.value,
                    symbol=metadata.symbol,
                    source=metadata.source.value,
                    provider_time=metadata.provider_time.astimezone(UTC),
                    observed_time=metadata.observed_time.astimezone(UTC),
                    schema_version=metadata.schema_version,
                    normalization_version=metadata.normalization_version,
                    retention_policy_version=RETENTION_POLICY_VERSION,
                    quality_state=metadata.quality_state.value,
                    payload=serialize_event(event),
                )
            )
            session.flush()
            return True

        try:
            return self._write(write)
        except IntegrityError:
            return False

    def _append_reconciliation(self, audit: ReconciliationAudit) -> bool:
        result = audit.result

        def write(session: Session) -> bool:
            if session.get(RealtimeReconciliationAudit, audit.audit_id) is not None:
                return False
            session.add(
                RealtimeReconciliationAudit(
                    audit_id=audit.audit_id,
                    trading_day=result.left.trading_day,
                    scope=result.scope.value,
                    symbol=result.left.symbol,
                    status=result.status.value,
                    quality_state=audit.quality_state.value,
                    left_evidence_id=result.left.evidence_id,
                    right_evidence_id=result.right.evidence_id,
                    left_source=result.left.source.value,
                    right_source=result.right.source.value,
                    profile_version=audit.profile.version,
                    enforcement_mode=audit.enforcement_mode.value,
                    checked_at=audit.checked_at.astimezone(UTC),
                    payload=audit.model_dump(mode="json"),
                )
            )
            session.flush()
            return True

        try:
            return self._write(write)
        except IntegrityError:
            return False

    def _read_reconciliations(
        self,
        symbol: str,
        trading_day: date,
        scope: ComparisonScope | None,
        limit: int,
    ) -> tuple[ReconciliationAudit, ...]:
        def read(session: Session) -> tuple[ReconciliationAudit, ...]:
            statement = select(RealtimeReconciliationAudit).where(
                RealtimeReconciliationAudit.symbol == symbol,
                RealtimeReconciliationAudit.trading_day == trading_day,
            )
            if scope is not None:
                statement = statement.where(
                    RealtimeReconciliationAudit.scope == scope.value
                )
            rows: Sequence[RealtimeReconciliationAudit] = session.scalars(
                statement.order_by(
                    RealtimeReconciliationAudit.checked_at,
                    RealtimeReconciliationAudit.audit_id,
                ).limit(limit)
            ).all()
            return tuple(
                ReconciliationAudit.model_validate(row.payload) for row in rows
            )

        return self._read(read)

    def _replay(
        self, trading_day: date, family: EventFamily, after: Checkpoint | None
    ) -> tuple[NormalizedMarketEvent, ...]:
        def read(session: Session) -> tuple[NormalizedMarketEvent, ...]:
            statement = select(RealtimeEvent).where(
                RealtimeEvent.trading_day == trading_day,
                RealtimeEvent.event_family == family.value,
            )
            if after is not None:
                statement = statement.where(
                    or_(
                        RealtimeEvent.provider_time > after.provider_time,
                        and_(
                            RealtimeEvent.provider_time == after.provider_time,
                            RealtimeEvent.observed_time > after.observed_time,
                        ),
                        and_(
                            RealtimeEvent.provider_time == after.provider_time,
                            RealtimeEvent.observed_time == after.observed_time,
                            RealtimeEvent.evidence_id > after.evidence_id,
                        ),
                    )
                )
            rows: Sequence[RealtimeEvent] = session.scalars(
                statement.order_by(
                    RealtimeEvent.provider_time,
                    RealtimeEvent.observed_time,
                    RealtimeEvent.evidence_id,
                )
            ).all()
            return tuple(deserialize_event(row.payload) for row in rows)

        return self._read(read)

    def _query(
        self,
        family: EventFamily,
        symbol: str,
        start: datetime,
        end: datetime,
        source: MarketDataSource | None,
        after: Checkpoint | None,
        limit: int,
    ) -> EventPage:
        def read(session: Session) -> EventPage:
            statement = select(RealtimeEvent).where(
                RealtimeEvent.event_family == family.value,
                RealtimeEvent.symbol == symbol,
                RealtimeEvent.provider_time >= start,
                RealtimeEvent.provider_time < end,
            )
            if source is not None:
                statement = statement.where(RealtimeEvent.source == source.value)
            if after is not None:
                statement = statement.where(
                    or_(
                        RealtimeEvent.provider_time > after.provider_time,
                        and_(
                            RealtimeEvent.provider_time == after.provider_time,
                            RealtimeEvent.observed_time > after.observed_time,
                        ),
                        and_(
                            RealtimeEvent.provider_time == after.provider_time,
                            RealtimeEvent.observed_time == after.observed_time,
                            RealtimeEvent.evidence_id > after.evidence_id,
                        ),
                    )
                )
            rows: Sequence[RealtimeEvent] = session.scalars(
                statement.order_by(
                    RealtimeEvent.provider_time,
                    RealtimeEvent.observed_time,
                    RealtimeEvent.evidence_id,
                ).limit(limit + 1)
            ).all()
            visible = rows[:limit]
            events = tuple(deserialize_event(row.payload) for row in visible)
            cursor = None
            if len(rows) > limit and visible:
                last = visible[-1]
                cursor = Checkpoint(
                    consumer="query",
                    partition_key="query",
                    evidence_id=last.evidence_id,
                    provider_time=_aware(last.provider_time),
                    observed_time=_aware(last.observed_time),
                )
            return EventPage(events=events, next_cursor=cursor)

        return self._read(read)

    def _save_checkpoint(self, consumer: str, event: NormalizedMarketEvent) -> Checkpoint:
        if not consumer or len(consumer) > 64:
            raise ValueError("invalid realtime checkpoint consumer")
        metadata = event.metadata
        key = partition_key(event)
        candidate = Checkpoint(
            consumer=consumer,
            partition_key=key,
            evidence_id=metadata.evidence_id,
            provider_time=metadata.provider_time.astimezone(UTC),
            observed_time=metadata.observed_time.astimezone(UTC),
        )

        def write(session: Session) -> Checkpoint:
            row = session.get(RealtimeCheckpoint, (consumer, key))
            if row is not None:
                current = _checkpoint_from_row(row)
                if candidate.order_key <= current.order_key:
                    return current
                row.evidence_id = candidate.evidence_id
                row.provider_time = candidate.provider_time
                row.observed_time = candidate.observed_time
            else:
                session.add(
                    RealtimeCheckpoint(
                        consumer=consumer,
                        partition_key=key,
                        evidence_id=candidate.evidence_id,
                        provider_time=candidate.provider_time,
                        observed_time=candidate.observed_time,
                    )
                )
            session.flush()
            return candidate

        try:
            return self._write(write)
        except IntegrityError:
            # Another process created this partition checkpoint between the
            # read and insert. Re-read and apply the same monotonic comparison.
            return self._write(write)

    def _load_checkpoint(self, consumer: str, key: str) -> Checkpoint | None:
        return self._read(
            lambda session: (
                _checkpoint_from_row(row)
                if (row := session.get(RealtimeCheckpoint, (consumer, key))) is not None
                else None
            )
        )

    def _spill(self, event: NormalizedMarketEvent, reason: str) -> bool:
        if not reason or len(reason) > 32:
            raise ValueError("invalid realtime spill reason")
        metadata = event.metadata

        def write(session: Session) -> bool:
            existing = session.scalar(
                select(RealtimeSpill.id).where(
                    RealtimeSpill.evidence_id == metadata.evidence_id
                )
            )
            if existing is not None:
                return False
            session.add(
                RealtimeSpill(
                    evidence_id=metadata.evidence_id,
                    trading_day=metadata.trading_day,
                    event_family=metadata.event_family.value,
                    payload=serialize_event(event),
                    reason=reason,
                )
            )
            session.flush()
            return True

        try:
            return self._write(write)
        except IntegrityError:
            return False

    def _pending_spills(self, limit: int) -> tuple[SpillRecord, ...]:
        def read(session: Session) -> tuple[SpillRecord, ...]:
            rows = session.scalars(
                select(RealtimeSpill)
                .where(RealtimeSpill.recovered_at.is_(None))
                .order_by(RealtimeSpill.created_at, RealtimeSpill.id)
                .limit(limit)
            ).all()
            return tuple(
                SpillRecord(row.id, deserialize_event(row.payload), row.reason)
                for row in rows
            )

        return self._read(read)

    def _mark_spill_recovered(self, spill_id: int) -> None:
        def write(session: Session) -> None:
            row = session.get(RealtimeSpill, spill_id)
            if row is None:
                raise LookupError("realtime spill does not exist")
            row.recovered_at = datetime.now(UTC)

        self._write(write)

    def _save_health(self, snapshot: HealthSnapshot) -> None:
        def write(session: Session) -> None:
            row = session.get(RealtimeHealth, snapshot.scope)
            payload = snapshot.model_dump(mode="json")
            if row is None:
                session.add(
                    RealtimeHealth(
                        scope=snapshot.scope,
                        status=snapshot.status,
                        reason=snapshot.reason,
                        observed_at=snapshot.observed_at,
                        payload=payload,
                    )
                )
            elif snapshot.observed_at >= _aware(row.observed_at):
                row.status = snapshot.status
                row.reason = snapshot.reason
                row.observed_at = snapshot.observed_at
                row.payload = payload

        try:
            self._write(write)
        except IntegrityError:
            # Concurrent first health write: the winner now exists, so the same
            # monotonic update path is safe to retry once.
            self._write(write)

    def _read_health(self, scope: str) -> HealthSnapshot | None:
        return self._read(
            lambda session: (
                HealthSnapshot.model_validate(row.payload)
                if (row := session.get(RealtimeHealth, scope)) is not None
                else None
            )
        )

    def _purge_expired(self, now: datetime) -> RetentionPurge:
        event_cutoff = now - timedelta(
            days=retention_rule(RetentionClass.NORMALIZED_EVENT).days
        )
        operational_cutoff = now - timedelta(
            days=retention_rule(RetentionClass.OPERATIONAL_METADATA).days
        )

        def write(session: Session) -> RetentionPurge:
            events = session.execute(
                delete(RealtimeEvent).where(
                    RealtimeEvent.trading_day < event_cutoff.date()
                )
            ).rowcount
            spills = session.execute(
                delete(RealtimeSpill).where(
                    RealtimeSpill.recovered_at.is_not(None),
                    RealtimeSpill.recovered_at < event_cutoff,
                )
            ).rowcount
            checkpoints = session.execute(
                delete(RealtimeCheckpoint).where(
                    RealtimeCheckpoint.updated_at < operational_cutoff
                )
            ).rowcount
            health = session.execute(
                delete(RealtimeHealth).where(
                    RealtimeHealth.updated_at < operational_cutoff
                )
            ).rowcount
            return RetentionPurge(
                events=events or 0,
                recovered_spills=spills or 0,
                checkpoints=checkpoints or 0,
                health_records=health or 0,
            )

        return self._write(write)


def _checkpoint_from_row(row: RealtimeCheckpoint) -> Checkpoint:
    return Checkpoint(
        consumer=row.consumer,
        partition_key=row.partition_key,
        evidence_id=row.evidence_id,
        provider_time=_aware(row.provider_time),
        observed_time=_aware(row.observed_time),
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
