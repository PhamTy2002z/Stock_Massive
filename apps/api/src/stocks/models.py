"""SQLAlchemy models for stocks module."""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
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


class StockDailyOHLCV(Base):
    """Daily OHLCV data for stocks."""
    __tablename__ = "stock_daily_ohlcv"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    trade_date = Column(Date, nullable=False)
    open_price = Column(Numeric(12, 2))
    high_price = Column(Numeric(12, 2))
    low_price = Column(Numeric(12, 2))
    close_price = Column(Numeric(12, 2))
    volume = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_daily_symbol_date"),
        Index("idx_daily_symbol_date", "symbol", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StockDailyOHLCV {self.symbol} {self.trade_date}>"


class StockIntradayBar(Base):
    """5-minute OHLCV bar for intraday trading data."""
    __tablename__ = "stock_intraday_bars"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    bar_time = Column(DateTime, nullable=False)
    open_price = Column(Numeric(12, 2))
    high_price = Column(Numeric(12, 2))
    low_price = Column(Numeric(12, 2))
    close_price = Column(Numeric(12, 2))
    volume = Column(BigInteger, nullable=False)
    trade_value = Column(Numeric(18, 2))
    trade_count = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "bar_time", name="uq_symbol_bar_time"),
        Index("idx_intraday_symbol_date", "symbol", func.date(bar_time)),
    )

    def __repr__(self) -> str:
        return f"<StockIntradayBar {self.symbol} {self.bar_time}>"


class SymbolBackfill(Base):
    """How far the one-time history load has got for one symbol.

    Durable because the load is the most expensive thing this system asks of
    vnstock and must happen once. Held in the database rather than in memory so
    a restart mid-load resumes where it stopped instead of starting the whole
    stretch of history again — and so a symbol dropped from the Universe and
    added back only fetches what it is still missing.
    """

    __tablename__ = "symbol_backfills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True)
    status = Column(String(16), nullable=False)
    # The newest session already loaded. The next run starts the day after it.
    covered_through = Column(Date, nullable=True)
    last_error = Column(String(500), nullable=True)
    # How many times in a row this symbol has failed, and the soonest a run may
    # take it on again. A run only has a handful of slots and the Universe has a
    # hundred symbols: without a backoff, the same few permanent failures take
    # every slot every night and the symbols behind them are never reached.
    attempts = Column(Integer, nullable=False, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<SymbolBackfill {self.symbol} {self.status} through {self.covered_through}>"


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


class ProfitRankingCensusRun(Base):
    """One pass of the market-wide profit census, and how far it got.

    Durable because the run is long and quota-bound: ~1,600 symbols against 20
    requests a minute cannot finish in one sitting, so a later run resumes from
    ``covered_symbols`` rather than starting the market again. It is also the
    record that decides whether a reporting period may be ranked at all —
    ``covered_symbols / eligible_symbols`` is the Signal Coverage of the census
    itself.
    """

    __tablename__ = "profit_ranking_census_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False)  # running | complete | failed
    # The period being assessed, which is not known until the market has been
    # read: it is the newest period companies are actually reporting.
    target_period = Column(Date, nullable=True)
    eligible_symbols = Column(Integer, nullable=False, server_default="0")
    covered_symbols = Column(Integer, nullable=False, server_default="0")
    last_error = Column(String(500), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ProfitRankingCensusRun {self.id} {self.status} "
            f"{self.covered_symbols}/{self.eligible_symbols}>"
        )


class CohortVersion(Base):
    """One immutable ranking of the Profit Leaders Cohort.

    Versioned rather than updated in place because a signal served last Tuesday
    has to stay explainable: the answer to "which 50 companies was this about"
    is the version that was active then, not the one active now. A ranking change
    therefore writes a new version and supersedes the old one, and no row is ever
    rewritten (``docs/adr/0003``).

    The states are a queue, not a status field: a ``candidate`` is a ranking whose
    members are still being made evaluable, ``active`` is the one being served —
    at most one, enforced by a partial unique index — and ``superseded`` is
    history kept for exactly the question above.
    """

    __tablename__ = "cohort_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reporting_period = Column(Date, nullable=False)
    census_run_id = Column(
        Integer,
        ForeignKey("profit_ranking_census_runs.id"),
        nullable=False,
    )
    state = Column(String(16), nullable=False)  # candidate | active | superseded
    created_at = Column(DateTime(timezone=True), nullable=False)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    # How many members were evaluable when this version took over. Kept because
    # a cohort activated at the 45-member floor and one activated with all 50
    # serve differently honest signals, and the difference is invisible later.
    coverage_at_activation = Column(Integer, nullable=True)

    __table_args__ = (
        # At most one active version, enforced by the database rather than by the
        # activation code: activation is the one place two concurrent runs would
        # both believe they were promoting the newest ranking, and the loser has
        # to fail rather than leave two cohorts being served at once.
        Index(
            "uq_cohort_version_single_active",
            "state",
            unique=True,
            postgresql_where=text("state = 'active'"),
            sqlite_where=text("state = 'active'"),
        ),
        # Resolving which version was active on a past day scans the activation
        # window, never the newest row.
        Index("ix_cohort_version_activation_window", "activated_at", "superseded_at"),
    )

    def __repr__(self) -> str:
        return f"<CohortVersion {self.id} {self.state} {self.reporting_period}>"


class CohortMember(Base):
    """One company's seat in one Cohort Version, at the rank it earned.

    ``net_income_vnd`` is copied here rather than read back from the fundamental
    Snapshot it came from. The ranking has to stay reproducible: a restatement
    that changes the figure must produce a new version, not silently reorder an
    old one.
    """

    __tablename__ = "cohort_members"

    cohort_version_id = Column(
        Integer,
        ForeignKey("cohort_versions.id"),
        primary_key=True,
    )
    symbol = Column(String(20), primary_key=True)
    rank = Column(Integer, nullable=False)
    net_income_vnd = Column(Numeric(24, 2), nullable=False)
    exchange = Column(String(10), nullable=False)

    __table_args__ = (
        # Two companies at rank 12 is a ranking that cannot be read back in
        # order, so it is refused at write time rather than sorted around later.
        UniqueConstraint(
            "cohort_version_id",
            "rank",
            name="uq_cohort_member_rank",
        ),
    )

    def __repr__(self) -> str:
        return f"<CohortMember {self.symbol} #{self.rank} of v{self.cohort_version_id}>"
