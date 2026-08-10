"""Durable last-known-good storage for normalized provider snapshots."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.redis import get_redis
from src.stocks.models import ProviderSnapshot

from .contracts import (
    Capability,
    FundamentalSnapshot,
    MarketSnapshot,
    ProviderSource,
    ReferenceSnapshot,
    SymbolSnapshot,
    ValuationSnapshot,
    main_source,
    owns_capability,
)

logger = logging.getLogger(__name__)
_DEFAULT_REDIS = object()

SNAPSHOT_MODEL_BY_CAPABILITY = {
    Capability.MARKET: MarketSnapshot,
    Capability.VALUATION: ValuationSnapshot,
    Capability.REFERENCE: ReferenceSnapshot,
    Capability.FUNDAMENTAL: FundamentalSnapshot,
}

# How long a snapshot stands before the serving path calls it old.
#
# The collector runs once a session, so the shortest honest threshold is longer
# than the longest ordinary gap between two runs: a Friday close is still the
# latest close on Monday, and a public holiday stretches that further. Four days
# clears a long weekend and still raises the flag once the collector has missed
# several sessions on end. Anything tighter — the 300 seconds this held while
# requests went straight to a live feed — would flag every evening the app is
# used, and a warning that is always on is one nobody reads.
EOD_MAX_AGE_SECONDS = 4 * 24 * 60 * 60

MAX_AGE_SECONDS = {
    Capability.MARKET: EOD_MAX_AGE_SECONDS,
    Capability.VALUATION: EOD_MAX_AGE_SECONDS,
    # Ownership and share counts change on corporate actions, not on sessions,
    # so this one keeps its own, slower threshold.
    Capability.REFERENCE: 7 * 24 * 60 * 60,
    Capability.FUNDAMENTAL: EOD_MAX_AGE_SECONDS,
}


@dataclass(frozen=True)
class SnapshotRead:
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
                .order_by(ProviderSnapshot.observed_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            snapshot = SNAPSHOT_MODEL_BY_CAPABILITY[capability].model_validate(row.payload)
            self._cache_snapshot(capability, snapshot)

        current = now or datetime.now(timezone.utc)
        observed_at = snapshot.metadata.observed_at
        age_seconds = max(0, int((current - observed_at).total_seconds()))
        return SnapshotRead(
            snapshot=snapshot,
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
