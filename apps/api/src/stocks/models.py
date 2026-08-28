"""SQLAlchemy models for stocks module."""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
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


class BarIntraday15m(Base):
    """One fifteen-minute bucket of one session, session hours only.

    The primary key is ``(symbol, bucket_start)`` because that is the identity of
    the thing: a bucket is the interval, and re-fetching a day has to land on the
    same rows rather than beside them. Ingest upserts on it — the provider does
    revise a session's last bucket after the close, and a second row for the same
    quarter hour would double the volume that a liquidity profile is built from.

    ``trading_day`` is stored rather than derived because every read groups by it
    and deriving it needs the Vietnamese zone: ``bucket_start`` comes back from
    PostgreSQL in UTC, where a 09:15 Vietnamese bucket is 02:15 the same day but a
    hypothetical late one would not be.

    Prices are **VND**, matching ``provider_snapshots.payload.price_unit``. The
    provider answers intraday quotes in thousands (74.5 for a 74,500đ share), and
    the scaling happens once, at ingest, so nothing downstream has to remember
    which store it is reading.
    """

    __tablename__ = "bar_intraday_15m"

    symbol = Column(String(20), primary_key=True)
    bucket_start = Column(DateTime(timezone=True), primary_key=True)
    trading_day = Column(Date, nullable=False)
    # ato | am | pm | atc — src/stocks/intraday/session_window.py owns the set.
    phase = Column(String(4), nullable=False)
    open = Column(Numeric(20, 4), nullable=False)
    high = Column(Numeric(20, 4), nullable=False)
    low = Column(Numeric(20, 4), nullable=False)
    close = Column(Numeric(20, 4), nullable=False)
    volume = Column(BigInteger, nullable=False)
    source = Column(String(32), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Every read asks for the last N sessions of one symbol.
        Index("ix_bar_intraday_15m_symbol_day", "symbol", trading_day.desc()),
    )

    def __repr__(self) -> str:
        return f"<BarIntraday15m {self.symbol} {self.bucket_start} {self.phase}>"


class BarDaily(Base):
    """One closed session of one series, market-wide, prices in VND.

    The primary key is ``(symbol, trading_day)`` and ingest upserts on it. The
    provider re-states a session whenever a corporate action changes the
    adjustment factor behind it, so the same day arriving twice has to land on
    the same row rather than beside it.

    ``series`` carries ``equity`` or ``index`` in one table rather than giving
    the index a table of its own. VNINDEX has the same shape as a share, and a
    screener asking "which symbols beat the index over 52 weeks" reads both
    sides of that comparison through one path. This is the opposite decision
    from ``provider_snapshots``, where MARKET_INDEX is a separate Capability
    because a Trading Day is derived from MARKET and an index session landing
    there would help define the window every equity is measured against; here
    nothing is derived from the table, so the distinction is a column.

    ``price_basis`` is a column and not a constant. Every row written today says
    ``adjusted_at_source`` — the provider offers no unadjusted daily history for
    this market — but a stored window whose basis is only implied is exactly how
    the market plane ended up with two sources whose prices could not be
    compared. A reader can ask this table what its numbers mean.

    Prices are VND: the provider answers equity history in thousands (74.5 for a
    74,500đ share) and index history in points (1,821.32), so the scaling is
    decided by ``series`` once, at ingest.

    There is no traded-value column. The provider does not report one, and
    ``close * volume`` is a derivation a caller can make explicit rather than a
    number this table should imply it measured.
    """

    __tablename__ = "bar_daily"

    symbol = Column(String(20), primary_key=True)
    trading_day = Column(Date, primary_key=True)
    # equity | index — src/stocks/providers/vnstock_daily.py owns the set.
    series = Column(String(8), nullable=False)
    open = Column(Numeric(20, 4), nullable=False)
    high = Column(Numeric(20, 4), nullable=False)
    low = Column(Numeric(20, 4), nullable=False)
    close = Column(Numeric(20, 4), nullable=False)
    volume = Column(BigInteger, nullable=False)
    price_basis = Column(String(20), nullable=False)
    source = Column(String(32), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # One symbol's last N sessions: every per-symbol read.
        Index("ix_bar_daily_symbol_day", "symbol", trading_day.desc()),
        # One session across the market: what a screener asks for.
        Index("ix_bar_daily_day_series", "trading_day", "series"),
    )

    def __repr__(self) -> str:
        return f"<BarDaily {self.symbol} {self.trading_day} {self.series}>"


class FinancialStatementLine(Base):
    """One line of one quarterly statement, in the provider's own vocabulary.

    Long format, and deliberately not a typed column per line item: the three
    templates this market reports under share almost nothing. A bank's income
    statement is 26 lines, a securities house's 79 and a steelmaker's 25
    (measured 2026-08-27), so a wide table would be mostly nulls and would have
    to be migrated every time the provider adds a line.

    ``item_seq`` is in the primary key because **the provider's own response
    holds one ``item_id`` twice**, with different numbers under it. SSI's income
    statement carries two ``business_income_tax_deferred`` rows for 2026-Q2 —
    4,585,945,424 and 758,786,600 — and the second one's Vietnamese label is
    "Lợi nhuận thuần phân bổ cho lợi ích của cổ đông không kiểm soát", i.e. the
    minority interest line arriving under the wrong id. Its balance sheet
    carries ``accumulated_depreciation`` four times, one per class of asset. A
    key without the occurrence index would make the provider's response
    unstorable, and "last row wins" would silently drop numbers that differ.
    Readers resolving a named concept take ``item_seq = 0``.

    ``item_id`` is stored raw rather than mapped at ingest. A mapping that turns
    out to be wrong is then a patch to one resolver rather than a market-wide
    re-fetch.

    Values are as the provider reports them: VND for statement lines, signed the
    way the statement signs them (a tax expense is negative, and a bank's
    interest expense too).
    """

    __tablename__ = "financial_statement_line"

    symbol = Column(String(20), primary_key=True)
    # "2026-Q2". Text rather than (year, quarter) because it is what the
    # provider labels its columns with and what every read asks for.
    period = Column(String(7), primary_key=True)
    # income | balance | cashflow — src/stocks/financial/fetch.py owns the set.
    statement = Column(String(8), primary_key=True)
    # 101 characters is the longest id measured across the three templates.
    item_id = Column(String(128), primary_key=True)
    item_seq = Column(SmallInteger, primary_key=True)
    # 15 integer digits carry the largest measured number (STB's total assets,
    # 917,119,803,000,000) with room to spare; the provider reports two decimals
    # for the non-bank templates.
    value = Column(Numeric(28, 4), nullable=False)
    source = Column(String(32), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # One line across the market for one quarter: what the earnings screener
        # asks for. The primary key already leads with the symbol, so it cannot
        # answer this one.
        Index(
            "ix_financial_statement_line_period_item",
            "period",
            "statement",
            "item_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialStatementLine {self.symbol} {self.period} "
            f"{self.statement} {self.item_id}#{self.item_seq}>"
        )


class FinancialRatioSnapshot(Base):
    """One reported ratio for one quarter, long format, from one source.

    Separate from ``financial_statement_line`` because these are not statement
    lines: they are the provider's own derived indicators, they come from a
    different provider source, and their units follow that source's convention.

    ``source`` is a column and not a constant for that last reason. Measured
    2026-08-27: KBS reports ROE as a percent (4.74) where VCI reports the same
    thing as a fraction (0.0589), so a stored ratio whose source is only implied
    cannot be compared with anything. Only KBS is written today — VCI's ratio
    endpoint answers 2018 quarters for a request made in 2026 — and the column
    is what lets a second source be added without re-reading the first as if it
    shared the convention.

    ``item_seq`` mirrors the statement table's key. No duplicated ``item_id``
    has been measured in a ratio response, but the shape is the same shape and a
    reader that resolves both tables the same way is worth more than a column
    saved.
    """

    __tablename__ = "financial_ratio_snapshot"

    symbol = Column(String(20), primary_key=True)
    period = Column(String(7), primary_key=True)
    item_id = Column(String(128), primary_key=True)
    item_seq = Column(SmallInteger, primary_key=True)
    value = Column(Numeric(28, 4), nullable=False)
    source = Column(String(32), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # One ratio across the market for one quarter, same read as above.
        Index(
            "ix_financial_ratio_snapshot_period_item",
            "period",
            "item_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialRatioSnapshot {self.symbol} {self.period} "
            f"{self.item_id}#{self.item_seq}>"
        )
