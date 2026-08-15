"""Durable last-known-good storage for normalized provider snapshots."""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.redis import get_redis
from src.stocks.models import ProviderSnapshot

from .contracts import (
    Capability,
    FundamentalSnapshot,
    MarketIndexSnapshot,
    MarketSnapshot,
    ProviderSource,
    ReferenceSnapshot,
    SymbolSnapshot,
    ValuationSnapshot,
    cover_source,
    main_source,
    owns_capability,
)
from .normalize import VN_TZ

logger = logging.getLogger(__name__)
_DEFAULT_REDIS = object()

SNAPSHOT_MODEL_BY_CAPABILITY = {
    Capability.MARKET: MarketSnapshot,
    Capability.MARKET_INDEX: MarketIndexSnapshot,
    Capability.VALUATION: ValuationSnapshot,
    Capability.REFERENCE: ReferenceSnapshot,
    Capability.FUNDAMENTAL: FundamentalSnapshot,
}

_DAY = 24 * 60 * 60

# How old the data may be before the serving path calls it old. Age is measured
# from effective_at, so each threshold has to match how often that kind of data
# can possibly change — not how often the collector runs.
#
# A session series is fresh daily, but the newest close is Friday's all weekend,
# and FiinQuant appends the session that just closed to the daily series late in
# the evening: a cycle that runs before it lands comes away with the session
# before, which is legitimate rather than broken. An ordinary Monday evening can
# therefore sit three days out. Seven days absorbs that plus a public holiday,
# and still flags a collector that has been down a week. It cannot survive Tet,
# when nine days of no sessions read as stale — the alternative is a threshold so
# wide it stops meaning anything.
#
# Statements move on a completely different clock: a company reporting on time
# still leaves its latest quarter weeks old, which is the fastest this data can
# ever be. Judging it by the session cadence marked every healthy symbol stale.
SESSION_MAX_AGE_SECONDS = 7 * _DAY
STATEMENT_MAX_AGE_SECONDS = 150 * _DAY

MAX_AGE_SECONDS = {
    Capability.MARKET: SESSION_MAX_AGE_SECONDS,
    # The index closes on exactly the sessions the equities do, so it ages on
    # the same clock — and it has to, since a benchmark that went stale on a
    # different threshold from the symbols regressed against it would report a
    # fresh beta over a stale market.
    Capability.MARKET_INDEX: SESSION_MAX_AGE_SECONDS,
    Capability.VALUATION: SESSION_MAX_AGE_SECONDS,
    # Ownership and share counts change on corporate actions, but the adapter
    # dates them by the day it read them, so they age on the session clock.
    Capability.REFERENCE: SESSION_MAX_AGE_SECONDS,
    # One quarter plus the weeks a company has to publish it, plus room for a
    # late filing: past that, a report really is missing.
    Capability.FUNDAMENTAL: STATEMENT_MAX_AGE_SECONDS,
}


def _day_starts(day: date, after: int = 0) -> datetime:
    """Midnight in Vietnam on a session day, which is how sessions are dated.

    A window asked for as calendar dates has to be read in the market's own
    zone: built in UTC, "from 2026-08-10" would start seven hours into the
    session and drop it.
    """
    return datetime.combine(day + timedelta(days=after), time.min, tzinfo=VN_TZ)


def resolve_sessions(
    rows: Iterable[ProviderSnapshot],
    capability: Capability,
) -> dict[datetime, ProviderSnapshot]:
    """One row per session, out of rows that may hold two copies of one.

    The Backfill window and the daily cycle overlap, so a session can arrive
    from both sources. **The Main Source wins**: it answers with a richer
    session than a quote history carries, and — since ``docs/adr/0006`` — the
    two copies are on different **Price Basis** values, so which one is read
    decides whether a window can be computed on at all rather than only how
    detailed it is. Picking by write order instead would let a late Backfill run
    replace a collected session with the thinner, adjusted version of it.

    Rows must arrive ordered oldest-written first, which is how every caller
    queries them: among two rows from the same source the later write then wins
    by being seen last.

    Extracted rather than repeated. Three readers need this exact rule — the
    series a chart draws, the multi-symbol read the cross-sectional fields make,
    and the single-symbol window ``prepare_bars()`` serves — and a second
    spelling of it would be a second answer to "which of these two sessions is
    the session".
    """
    main = main_source(capability).value
    held: dict[datetime, ProviderSnapshot] = {}
    for row in rows:
        # Take this row unless a Main Source row is already holding the session.
        standing = held.get(row.effective_at)
        if standing is None or standing.source != main:
            held[row.effective_at] = row
    return held


@dataclass(frozen=True)
class SnapshotSeries:
    """A stretch of sessions for one capability, oldest first.

    Age and staleness are judged on the newest session alone. Every session
    before it is old by definition — that is what history is — so carrying a
    flag per point would turn a healthy decade into a decade of warnings, and
    the reader would learn to ignore the one that matters.

    An empty series is a real answer: a window the exchange was shut for holds
    no sessions, which is not the same as a symbol nothing is held for.
    """

    snapshots: tuple[SymbolSnapshot, ...]
    stale: bool
    age_seconds: int | None


@dataclass(frozen=True)
class SnapshotRead:
    """A stored snapshot together with how old the data in it is.

    ``age_seconds`` counts from ``effective_at`` — the moment the data speaks
    about — so it answers "how old is this number", not "how long ago did a job
    run".
    """

    snapshot: SymbolSnapshot
    stale: bool
    age_seconds: int


class SnapshotStore:
    """Write snapshots to PostgreSQL and use Redis as the fast current view."""

    def __init__(self, session: Session, redis: Any = _DEFAULT_REDIS):
        self.session = session
        self.redis = get_redis() if redis is _DEFAULT_REDIS else redis

    @staticmethod
    def _cache_key(
        capability: Capability,
        symbol: str,
        source: ProviderSource,
    ) -> str:
        return f"stock:snapshot:{capability.value}:{source.value}:{symbol.upper()}"

    @staticmethod
    def _require_owning_source(
        capability: Capability,
        source: ProviderSource,
    ) -> ProviderSource:
        """Reject a source the Main/Cover table does not grant this capability.

        Without this the store answers a misrouted read with ``None``, which is
        indistinguishable from a capability that simply has not been collected
        yet.
        """
        if not owns_capability(capability, source):
            raise ValueError(
                f"{source.value} does not own the {capability.value} capability"
            )
        return source

    def save(self, capability: Capability, snapshot: SymbolSnapshot) -> None:
        """Idempotently persist one observed snapshot and refresh Redis.

        The write takes a savepoint of its own so that a snapshot the database
        refuses costs only itself. A failed flush otherwise leaves the session
        unusable until someone rolls it back, which would turn one halted
        symbol into a whole collection cycle's worth of lost writes.
        """
        if not isinstance(snapshot, SNAPSHOT_MODEL_BY_CAPABILITY[capability]):
            raise TypeError(f"snapshot does not match {capability.value} capability")

        metadata = snapshot.metadata
        self._require_owning_source(capability, metadata.source)

        with self.session.begin_nested():
            existing = self.session.execute(
                select(ProviderSnapshot).where(
                    ProviderSnapshot.capability == capability.value,
                    ProviderSnapshot.symbol == snapshot.symbol,
                    ProviderSnapshot.source == metadata.source.value,
                    ProviderSnapshot.effective_at == metadata.effective_at,
                    ProviderSnapshot.schema_version == metadata.schema_version,
                )
            ).scalar_one_or_none()

            payload = snapshot.model_dump(mode="json")
            if existing is None:
                self.session.add(
                    ProviderSnapshot(
                        capability=capability.value,
                        symbol=snapshot.symbol,
                        source=metadata.source.value,
                        effective_at=metadata.effective_at,
                        observed_at=metadata.observed_at,
                        schema_version=metadata.schema_version,
                        payload=payload,
                    )
                )
            else:
                existing.observed_at = metadata.observed_at
                existing.payload = payload
            self.session.flush()

        self._cache_snapshot(capability, snapshot)

    def latest(
        self,
        capability: Capability,
        symbol: str,
        source: ProviderSource | None = None,
        now: datetime | None = None,
    ) -> SnapshotRead | None:
        """Read Redis first, then PostgreSQL without calling an upstream.

        Defaults to the main source and stays there. A caller wanting what the
        cover source backfilled must name that source, because the two disagree
        on units and a silent swap would go unnoticed (``docs/adr/0002``).
        """
        source = self._require_owning_source(
            capability,
            source or main_source(capability),
        )
        cache_key = self._cache_key(capability, symbol, source)
        snapshot = self._read_cache(capability, cache_key)

        if snapshot is None:
            row = self.session.execute(
                select(ProviderSnapshot)
                .where(
                    ProviderSnapshot.capability == capability.value,
                    ProviderSnapshot.symbol == symbol.upper(),
                    ProviderSnapshot.source == source.value,
                )
                # Newest session first, not newest write: a re-run over an
                # older session writes a later observed_at, and ordering by
                # that would hand the reader last week's close.
                .order_by(
                    ProviderSnapshot.effective_at.desc(),
                    ProviderSnapshot.observed_at.desc(),
                )
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            snapshot = SNAPSHOT_MODEL_BY_CAPABILITY[capability].model_validate(row.payload)
            self._cache_snapshot(capability, snapshot)

        # Age belongs to the data, not to the job that fetched it. Measured
        # from observed_at, a collector re-reading a week-old session would
        # report it as seconds old and switch the stale flag off on precisely
        # the day it is needed.
        current = now or datetime.now(timezone.utc)
        effective_at = snapshot.metadata.effective_at
        age_seconds = max(0, int((current - effective_at).total_seconds()))
        return SnapshotRead(
            snapshot=snapshot,
            stale=age_seconds > MAX_AGE_SECONDS[capability],
            age_seconds=age_seconds,
        )

    def series(
        self,
        capability: Capability,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        now: datetime | None = None,
    ) -> SnapshotSeries:
        """Read a stretch of sessions, oldest first, touching no Provider Source.

        Unlike ``latest``, this spans both sources that own the capability.
        History is written by two of them — the Cover Source loaded the deep
        years once, the Main Source writes each session as it closes — and a
        reader asking for a decade wants the decade, not the half of it one
        provider happens to have. ADR 0002 bars swapping sources *silently*;
        here every session carries the source that produced it, so the seam is
        on the wire rather than hidden behind it.

        Redis is not consulted. It holds the current view of one session, and
        filling it with ranges would evict exactly that.
        """
        sources = [
            source.value
            for source in (main_source(capability), cover_source(capability))
            if source is not None
        ]
        conditions = [
            ProviderSnapshot.capability == capability.value,
            ProviderSnapshot.symbol == symbol.upper(),
            ProviderSnapshot.source.in_(sources),
        ]
        if start is not None:
            conditions.append(ProviderSnapshot.effective_at >= _day_starts(start))
        if end is not None:
            conditions.append(ProviderSnapshot.effective_at < _day_starts(end, after=1))

        rows = self.session.execute(
            select(ProviderSnapshot)
            .where(*conditions)
            .order_by(
                ProviderSnapshot.effective_at.asc(),
                ProviderSnapshot.observed_at.asc(),
            )
        ).scalars()

        model = SNAPSHOT_MODEL_BY_CAPABILITY[capability]
        # One session is one point, and which of two copies is that point is
        # decided in one place for every reader of the store.
        by_session = resolve_sessions(rows, capability)

        snapshots = tuple(
            model.model_validate(row.payload)
            for _, row in sorted(by_session.items(), key=lambda item: item[0])
        )
        if not snapshots:
            return SnapshotSeries(snapshots=(), stale=False, age_seconds=None)

        current = now or datetime.now(timezone.utc)
        newest = snapshots[-1].metadata.effective_at
        age_seconds = max(0, int((current - newest).total_seconds()))
        return SnapshotSeries(
            snapshots=snapshots,
            stale=age_seconds > MAX_AGE_SECONDS[capability],
            age_seconds=age_seconds,
        )

    def _read_cache(
        self,
        capability: Capability,
        cache_key: str,
    ) -> SymbolSnapshot | None:
        if self.redis is None:
            return None
        try:
            payload = self.redis.get(cache_key)
            if payload is None:
                return None
            if isinstance(payload, str):
                payload = json.loads(payload)
            return SNAPSHOT_MODEL_BY_CAPABILITY[capability].model_validate(payload)
        except Exception as exc:
            logger.warning("Snapshot Redis read failed for %s: %s", cache_key, exc)
            return None

    def _cache_snapshot(
        self,
        capability: Capability,
        snapshot: SymbolSnapshot,
    ) -> None:
        if self.redis is None:
            return
        cache_key = self._cache_key(
            capability,
            snapshot.symbol,
            snapshot.metadata.source,
        )
        try:
            self.redis.set(cache_key, snapshot.model_dump_json())
        except Exception as exc:
            logger.warning("Snapshot Redis write failed for %s: %s", cache_key, exc)
