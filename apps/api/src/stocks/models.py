"""SQLAlchemy models for stocks module."""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from src.core.database import Base


class ProviderSnapshot(Base):
    """Append-only normalized provider data used for last-known-good reads."""

    __tablename__ = "provider_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    capability = Column(String(32), nullable=False)
    symbol = Column(String(20), nullable=False)
    source = Column(String(32), nullable=False)
    effective_at = Column(DateTime(timezone=True), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    schema_version = Column(Integer, nullable=False, default=1)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "capability",
            "symbol",
            "source",
            "effective_at",
            "schema_version",
            name="uq_provider_snapshot_identity",
        ),
        Index(
            "ix_provider_snapshot_latest",
            "capability",
            "symbol",
            "source",
            "observed_at",
        ),
        # Resolving a Trading Day asks which sessions exist across every symbol
        # at once, so it cannot use the index above — that one leads with a
        # symbol. See src/stocks/trading_day.py.
        Index(
            "ix_provider_snapshot_capability_effective",
            "capability",
            effective_at.desc(),
        ),
    )


class RealtimeEvent(Base):
    """Append-only normalized realtime evidence, separate from EOD snapshots."""

    __tablename__ = "realtime_events"

    evidence_id = Column(String(68), primary_key=True)
    trading_day = Column(Date, nullable=False)
    event_family = Column(String(32), nullable=False)
    symbol = Column(String(32), nullable=False)
    source = Column(String(32), nullable=False)
    provider_time = Column(DateTime(timezone=True), nullable=False)
    observed_time = Column(DateTime(timezone=True), nullable=False)
    schema_version = Column(Integer, nullable=False)
    normalization_version = Column(Integer, nullable=False)
    retention_policy_version = Column(Integer, nullable=False)
    quality_state = Column(String(16), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_realtime_event_replay",
            "trading_day",
            "event_family",
            "provider_time",
            "observed_time",
            "evidence_id",
        ),
        Index(
            "ix_realtime_event_symbol_latest",
            "event_family",
            "symbol",
            "provider_time",
        ),
    )


class RealtimeCheckpoint(Base):
    """At-least-once resume position for one ingestion partition."""

    __tablename__ = "realtime_checkpoints"

    consumer = Column(String(64), primary_key=True)
    partition_key = Column(String(96), primary_key=True)
    evidence_id = Column(String(68), nullable=False)
    provider_time = Column(DateTime(timezone=True), nullable=False)
    observed_time = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RealtimeSpill(Base):
    """Durable overflow awaiting normal ingestion after queue pressure."""

    __tablename__ = "realtime_spills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evidence_id = Column(String(68), nullable=False, unique=True)
    trading_day = Column(Date, nullable=False)
    event_family = Column(String(32), nullable=False)
    payload = Column(JSON, nullable=False)
    reason = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    recovered_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_realtime_spill_pending", "recovered_at", "created_at", "id"),
    )


class RealtimeHealth(Base):
    """Durable feed and data health visible across process restarts."""

    __tablename__ = "realtime_health"

    scope = Column(String(64), primary_key=True)
    status = Column(String(32), nullable=False)
    reason = Column(String(64), nullable=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RealtimeReconciliationAudit(Base):
    """Append-only evidence comparison emitted by shadow reconciliation."""

    __tablename__ = "realtime_reconciliation_audits"

    audit_id = Column(String(68), primary_key=True)
    trading_day = Column(Date, nullable=False)
    scope = Column(String(32), nullable=False)
    symbol = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)
    quality_state = Column(String(16), nullable=False)
    left_evidence_id = Column(String(68), nullable=False)
    right_evidence_id = Column(String(68), nullable=False)
    left_source = Column(String(32), nullable=False)
    right_source = Column(String(32), nullable=False)
    profile_version = Column(Integer, nullable=False)
    enforcement_mode = Column(String(16), nullable=False)
    checked_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_realtime_reconciliation_session",
            "trading_day",
            "symbol",
            "scope",
            "checked_at",
        ),
        Index(
            "ix_realtime_reconciliation_status",
            "status",
            "quality_state",
            "checked_at",
        ),
    )


class ListingRoster(Base):
    """Which symbols the exchanges list, and on which board, market-wide.

    Not a Snapshot, and deliberately not in ``provider_snapshots``: that table
    holds per-symbol observations for symbols the system has promised to follow,
    while this is one row per listed company on the whole market — roughly 1,600
    of them — and exists so the Profit Ranking Census knows what to rank before
    any of it is in the Universe (``docs/adr/0004``).

    One row per symbol rather than a history of listings. What a census needs is
    the market as it stands now; a company that leaves has to be *seen* to have
    left, which is why a symbol that disappears from a roster refresh is kept
    with ``is_listed`` false instead of deleted. Deleted, a delisted cohort
    member would simply stop matching and the cohort would quietly serve a
    company that no longer trades.
    """

    __tablename__ = "listing_roster"

    symbol = Column(String(20), primary_key=True)
    exchange = Column(String(10), nullable=False)  # HOSE | HNX | UPCOM
    is_listed = Column(Boolean, nullable=False)
    company_name = Column(String(255), nullable=True)
    # The ICB level-2 classification, here rather than in its own table because
    # it is the same kind of fact as the board: reference data about a listed
    # company, arriving from the same market-wide register read, one row per
    # company. It is what tells the nightly Analysis pipeline which per-industry
    # fundamentals a symbol's Field Profile carries (spec 0003 §8.4) without
    # calling a Provider Source to ask. ADR-0004 assigned it to a Reference
    # Snapshot, which covers Universe members; the census needs it for the
    # market, which is why it sits beside the board and the company name.
    #
    # Nullable, and it stays that way: the register's classification read is
    # best-effort, so a symbol the market lists and nothing has classified is a
    # normal row rather than a broken one.
    icb_code = Column(String(4), nullable=True)
    icb_name = Column(String(100), nullable=True)
    source = Column(String(32), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # The census asks for one exchange pair's listed equities and nothing
        # else, every run.
        Index("ix_listing_roster_exchange_listed", "exchange", "is_listed"),
    )

    def __repr__(self) -> str:
        state = "listed" if self.is_listed else "delisted"
        return f"<ListingRoster {self.symbol} {self.exchange} {state}>"


class CorporateAction(Base):
    """One declared corporate action, and whether it may drive arithmetic.

    The input read-time adjustment has and no other (``docs/adr/0006``). A raw
    price store is only comparable across a split, a bonus or a dividend if the
    series of actions is held durably, so this table is a prerequisite for the
    signal window rather than a refinement of it.

    Its own table rather than a Snapshot: ``provider_snapshots`` holds one
    observation of a symbol at one moment, while an action is an event with its
    own date that is re-read and re-confirmed as the price history around it
    arrives. Two of the columns exist because the provider's feed is not
    self-describing:

    ``kind`` and ``changes_share_count`` are derived once, at write time, from
    free text the feed puts the kind of a share issue in. They are stored rather
    than recomputed on read because ADR-0006 makes a downstream field depend on
    the distinction — a share-count change breaks every ``*_volume`` field while
    a cash dividend leaves them alone — and the requirement is that the answer be
    derivable from a stored row without re-reading the provider.

    ``confirmation`` is the gate. Only a confirmed action may drive arithmetic;
    an unconfirmed one leaves a window that contains it degraded rather than
    adjusted, and ``confirmation_reason`` says which of the several ways that
    happened, since "no ex-date at all" and "an ex-date the prices contradict"
    are different problems with different fixes.
    """

    __tablename__ = "corporate_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    # Nullable because the feed leaves it null on real rows: TCB's 2026 bonus
    # issue at ratio 0.6 arrives with a public date and nothing else. That row
    # has to be stored — an action nobody knows the date of is exactly what makes
    # a window unadjustable — so the null is carried rather than refused.
    ex_date = Column(Date, nullable=True)
    event_code = Column(String(16), nullable=False)
    # The provider's own wording, kept verbatim. It is where the kind of a share
    # issue lives, so a `kind` that looks wrong can be checked against what was
    # actually said rather than argued about.
    title = Column(String(255), nullable=False)
    record_date = Column(Date, nullable=True)
    # The fallback half of this row's identity, and the only date a null-ex-date
    # action has.
    public_date = Column(Date, nullable=True)
    kind = Column(String(24), nullable=False)
    # As declared. On a share issue this is the share ratio; on a cash dividend
    # the feed puts the payment as a fraction of par here, which is not a share
    # ratio at all — so it is stored as given and read by kind, never by name.
    exercise_ratio = Column(Numeric(18, 8), nullable=True)
    value_per_share = Column(Numeric(18, 2), nullable=True)
    changes_share_count = Column(Boolean, nullable=False)
    confirmation = Column(String(16), nullable=False)
    confirmation_reason = Column(String(48), nullable=True)
    source = Column(String(32), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        # Identity is (symbol, ex-date, event code) **plus the kind**, enforced by
        # the database rather than by the collector: the load re-reads a
        # company's whole history every run, so without this a year of runs is a
        # year of duplicate rows that read as a year of corporate actions.
        #
        # The kind is in the key because the three columns the ticket names do
        # not identify a row in the feed as it actually arrives. MBB's
        # 2026-08-11 ex-date carries two ``ISS`` rows — a 15% stock dividend and
        # a 10% rights issue — and keying without the kind would let the second
        # overwrite the first, losing half of an adjustment that has to be
        # computed from both at once.
        #
        # It has a cost, and it is the reason the choice is written down rather
        # than assumed: the kind is parsed from a title the provider controls, so
        # a rewording that reclassifies a row forks a duplicate instead of
        # updating the row it is a re-read of. That is the lesser failure — a
        # duplicate is visible in the series, a silently halved ex-date is not.
        #
        # Two indexes because one cannot cover both cases. A NULL ex-date does
        # not collide with another NULL under a plain unique constraint, which
        # would let every run insert TCB's undated bonus issue again — so those
        # rows are keyed on their public date instead, which is the only other
        # date they carry.
        Index(
            "uq_corporate_action_dated",
            "symbol",
            "ex_date",
            "event_code",
            "kind",
            unique=True,
            postgresql_where=text("ex_date IS NOT NULL"),
            sqlite_where=text("ex_date IS NOT NULL"),
        ),
        Index(
            "uq_corporate_action_undated",
            "symbol",
            "public_date",
            "event_code",
            "kind",
            unique=True,
            postgresql_where=text("ex_date IS NULL"),
            sqlite_where=text("ex_date IS NULL"),
        ),
        # Adjusting a window asks for one symbol's actions across a date range,
        # every time.
        Index("ix_corporate_action_symbol_ex_date", "symbol", "ex_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<CorporateAction {self.symbol} {self.event_code} "
            f"{self.ex_date} {self.confirmation}>"
        )
