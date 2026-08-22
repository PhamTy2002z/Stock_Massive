"""The nine tables Alpha Desk stands on, declared together.

Five of them stay empty until the agent loop lands. They are here anyway,
because they come into existence together: ``agent_message`` means nothing
without ``agent_thread``, and a trace anchored to a message that does not exist
is not a partial system, it is a broken one. Splitting them into nine
migrations would add nine places to rebase wrong on an Alembic chain that is
already long, and buy no partial rollback that is real — nobody ships half of a
transcript.

Postgres types throughout, deliberately. ``JSONB`` and ``text[]`` are load
bearing here: the Analysis payload is queried by key, and "which Threads
discussed FPT" is answered by a GIN index over an array rather than by a join
table that exists to answer one question.

Three invariants in this file are what every later milestone rests on, and each
is enforced by the database rather than by the code that writes it:

1. ``analysis`` is unique on ``(symbol, trading_day)`` and **excludes**
   ``schema_version`` — unlike ``provider_snapshots``. There is one author, at
   most one Analysis per pair, and every reader reads by exactly that pair. Two
   rows differing only by template version would force every reader to choose,
   and no choice rule is correct.
2. Transcript order is held by ``UNIQUE(thread_id, seq)``, never by timestamps.
   Two streamed messages can share a millisecond, and a timestamp cannot express
   inserting between two rows.
3. Traces anchor to the user's message (``request_message_id`` NOT NULL) — the
   one row that already exists before the first tool call. A nullable id patched
   in once the assistant message forms would orphan traces exactly when a Turn
   dies mid-flight and the trace matters most.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Computed,
    DDL,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.sql import func, text

from src.core.database import Base


class WatchlistEntry(Base):
    """One symbol a user asked to keep being analysed.

    Deliberately thin. There is no ``state`` column even though the interface
    shows one: a watched symbol is ``active`` while the **Universe** carries it
    and ``unsupported`` while it does not, so the state is a question about the
    Universe asked at read time. Stored, it would need a writer — and the writer
    would be the thing that has to notice a symbol coming back, which is exactly
    the revival the product wants to happen by itself.

    ``last_seen_analysis_date`` is per user per symbol because the unread badge
    is: it advances only when that specific Analysis is opened. Nothing writes
    or serves it yet — the milestone that opens an Analysis is the one that can
    advance it, and a field on the wire that never moves is worse than no field.
    """

    __tablename__ = "watchlist_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol = Column(String(20), nullable=False)
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_analysis_date = Column(Date, nullable=True)

    __table_args__ = (
        # One row per user per symbol, so re-adding a symbol already watched is
        # a no-op rather than a second slot quietly consumed.
        UniqueConstraint("user_id", "symbol", name="uq_watchlist_entry_user_symbol"),
        # Every read is one user's whole list, in the order they added.
        Index("ix_watchlist_entry_user_added", "user_id", "added_at"),
    )

    def __repr__(self) -> str:
        return f"<WatchlistEntry user={self.user_id} {self.symbol}>"


class Analysis(Base):
    """One published Analysis for one ``(symbol, trading_day)``, immutable.

    **A row here existing means it is complete.** In-flight state lives only in
    ``analysis_run``; what that buys is argued in ``src/alpha/analysis_run.py``,
    and it is the reason this table has no status column to filter on.

    The payload is a blob with ``symbol``, ``trading_day`` and ``verdict``
    lifted out of it. Not four normalised per-axis tables: the template is fixed
    but will change, and normalising the axes turns every template change into
    four migrations. Not a pure blob either — the rail shows one word for ten
    symbols and should not parse ten payloads to find it.
    """

    __tablename__ = "analysis"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    symbol = Column(String(20), nullable=False)
    trading_day = Column(Date, nullable=False)
    verdict = Column(String(16), nullable=False)
    payload = Column(JSONB, nullable=False)
    # Readers handle several values rather than choosing between two rows; that
    # is what this column is for, and why it is not in the key below.
    schema_version = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "trading_day", name="uq_analysis_symbol_trading_day"),
        # The rail asks one question of this table: the newest Analysis for a
        # symbol. Descending so the answer is the index's first row.
        Index("ix_analysis_symbol_day", "symbol", trading_day.desc()),
    )

    def __repr__(self) -> str:
        return f"<Analysis {self.symbol} {self.trading_day} {self.verdict}>"


class AnalysisRun(Base):
    """The production of one Analysis: mutable, updated in place.

    Split from ``analysis`` because the run changes while the content is written
    once. Merged, every ``attempts`` bump would make Postgres rewrite a row
    dragging a large JSONB payload along.

    One row per ``(symbol, trading_day)``, enforced below. That is what makes
    two users retrying the same symbol one run rather than two, and what lets
    the three-attempt ceiling be a column instead of a counter somewhere else.

    The error is two columns rather than one, for the reason every Alpha Desk
    refusal is two fields (``src/alpha/refusals.py``): the code is branched on,
    the sentence is read, and the sentence is the part allowed to change.
    """

    __tablename__ = "analysis_run"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    trading_day = Column(Date, nullable=False)
    # pending | producing | ready | failed
    status = Column(String(16), nullable=False)
    # nightly | on_demand | retry — what asked for this run, kept because a
    # symbol that only ever gets produced on demand is a different operational
    # story from one the nightly pass keeps missing.
    origin = Column(String(16), nullable=False)
    attempts = Column(Integer, nullable=False, server_default="0")
    # Who asked, when a person's request is what created the row. Null for the
    # nightly cohort, which is nobody's in particular, and null once the account
    # is gone — an Analysis is shared and outlives whoever triggered it.
    #
    # It exists because the on-demand allowance is per user per Trading Day and
    # there is nowhere else the pairing could live: the Analysis is keyed by
    # `(symbol, trading_day)` precisely so it belongs to no user, and counting
    # Watchlist additions instead would charge the second watcher of a symbol
    # for a run the first one caused.
    requested_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_code = Column(String(48), nullable=True)
    error_message = Column(String(500), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trading_day",
            name="uq_analysis_run_symbol_trading_day",
        ),
        # The sweep asks for every run left producing past a window, across all
        # symbols at once, so it cannot use an index leading with a symbol.
        Index("ix_analysis_run_status_started", "status", "started_at"),
        # The on-demand allowance is a count of one user's runs for one session,
        # asked on every Watchlist addition.
        Index("ix_analysis_run_requester_day", "requested_by_user_id", "trading_day"),
    )

    def __repr__(self) -> str:
        return f"<AnalysisRun {self.symbol} {self.trading_day} {self.status}>"


class AgentThread(Base):
    """One conversation between a user and the agent.

    ``symbols`` is an array with a GIN index rather than a join table because
    the question asked in practice is *which Threads discussed FPT*, and a join
    table exists to answer exactly that one question at the cost of a second
    write on every Turn.
    """

    __tablename__ = "agent_thread"

    id = Column(Uuid, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(255), nullable=True)
    symbols = Column(ARRAY(String(20)), nullable=False, server_default=text("'{}'"))
    # When the user pinned it, rather than whether they did. A boolean would
    # order every pinned Thread by `updated_at` and put the one pinned first at
    # the bottom the moment another is answered in; the stamp keeps the pinned
    # group in the order the user built it.
    pinned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_agent_thread_symbols", "symbols", postgresql_using="gin"),
        Index("ix_agent_thread_user_updated", "user_id", updated_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<AgentThread {self.id} user={self.user_id}>"


# The four reason labels a flag may carry (``docs/adr/0016``). Declared where
# the column is, for the same reason the Turn statuses are: the store, the
# transport and the Eval Report all read one vocabulary, and a fifth label
# invented in one of them would be a category nothing else can count.
FLAG_WRONG_FIGURE = "wrong_figure"
FLAG_OVERREACH = "overreach"
FLAG_WRONGLY_REFUSED = "wrongly_refused"
FLAG_OTHER = "other"

FLAG_REASONS = (
    FLAG_WRONG_FIGURE,
    FLAG_OVERREACH,
    FLAG_WRONGLY_REFUSED,
    FLAG_OTHER,
)


class AgentMessage(Base):
    """One canonical, immutable message in a Thread.

    ``content`` is JSONB because an assistant message carries more than prose:
    the validated **Widget** spec rides here, per the decision that a message
    stores the spec and never the chart data.

    ``flagged_reason`` and ``flagged_at`` are the whole of v1's dispute surface.
    They are a nullable pair on this row rather than a ``message_flag`` table
    because a message carries at most one reason — re-flagging is a correction
    and not a second opinion — and ``docs/adr/0016`` forbids a new table for
    observability. They are also the one thing about this row that changes; the
    message a flag is about is never rewritten by the flag.

    ``tsv`` makes the transcript searchable without a second copy of it. It
    reads ``content ->> 'text'`` — the one key both a user message and an
    assistant message carry — and it is generated rather than trigger-fed so
    there is no path by which a message exists and its index entry does not.
    The diacritic handling is ``agent_knowledge``'s, for the same reason: a
    reader who types *co phieu* is asking about *cổ phiếu*, and Postgres'
    default configuration answers that question with silence.
    """

    __tablename__ = "agent_message"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    thread_id = Column(
        Uuid,
        ForeignKey("agent_thread.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Allocated inside the writing transaction; a conflict retries. Order is
    # this column's job and never a timestamp's.
    seq = Column(Integer, nullable=False)
    # user | assistant | summary
    role = Column(String(16), nullable=False)
    content = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    flagged_reason = Column(String(48), nullable=True)
    flagged_at = Column(DateTime(timezone=True), nullable=True)
    tsv = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', immutable_unaccent(coalesce(content ->> 'text', '')))",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("thread_id", "seq", name="uq_agent_message_thread_seq"),
        Index("ix_agent_message_tsv", "tsv", postgresql_using="gin"),
        # The ops query counts flags by reason over a date range, and a flag is
        # rare against a table that holds every message ever written. Partial,
        # so the index is the size of the flags rather than of the transcript,
        # and it costs nothing on the write path of an unflagged message.
        Index(
            "ix_agent_message_flagged",
            "flagged_reason",
            "flagged_at",
            postgresql_where=text("flagged_reason IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<AgentMessage {self.thread_id}#{self.seq} {self.role}>"


class AgentToolCall(Base):
    """One **Tool Call Trace**: what the agent asked for and what it got back.

    Full results are stored. They are the first thing usually dropped for fear
    of bloat, but the catalog already caps a result at 4KB, and they are exactly
    what is needed to debug a wrong answer — what the model actually saw.

    Anchored to the *request* message, not the response: the user's message
    already exists before the first tool call, so the anchor can be NOT NULL and
    a Turn that dies mid-flight still leaves a readable chain.
    """

    __tablename__ = "agent_tool_call"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    thread_id = Column(
        Uuid,
        ForeignKey("agent_thread.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_message_id = Column(
        BigInteger,
        ForeignKey("agent_message.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name = Column(String(64), nullable=False)
    # The route's own id for this call, which is also the id the model cites in
    # an evidence reference. Nullable because it is additive: a row written
    # before this column existed has one and cannot be told what it was, and a
    # gateway that sent no id gives us nothing to store.
    tool_call_id = Column(String(128), nullable=True)
    arguments = Column(JSONB, nullable=False)
    result = Column(JSONB, nullable=True)
    # Set when the model was shown a preview of this result instead of the whole
    # of it (``agent/tools/spillover.py``), and holding the size of the whole —
    # which is the number a threshold is tuned against — the part the model did
    # not see is a difference nobody needs stored. It exists so the threshold can
    # be tuned against measured spills rather than guessed at: a Turn that
    # answered worse after a spill is only diagnosable if the spill left a record.
    spilled_bytes = Column(Integer, nullable=True)
    # ok | tool_error | timeout | unknown_tool
    status = Column(String(16), nullable=False)  # see TOOL_CALL_* below
    error = Column(String(500), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # Per-Turn tool cost is a SUM over this column.
        Index("ix_agent_tool_call_request_message", "request_message_id"),
        # These rows are kept 90 days, and the cleanup job scans by age alone.
        Index("ix_agent_tool_call_started", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<AgentToolCall {self.tool_name} {self.status}>"


# What a remembered row *is*, and where it came from. Declared beside the
# columns for the reason ``FLAG_REASONS`` is: the tool that writes these, the
# tool that filters on them and any report that groups by them must read one
# vocabulary, and a fourth label invented at a call site would be a category
# nothing else can count.
#
# ``kind`` separates the three things worth carrying between Turns. A
# ``preference`` (risk appetite, investment horizon) stays true until the reader
# says otherwise; a ``conclusion`` is an earlier reading of the data and ages
# with it; an ``observation`` is an event that happened once.
KNOWLEDGE_KIND_PREFERENCE = "preference"
KNOWLEDGE_KIND_CONCLUSION = "conclusion"
KNOWLEDGE_KIND_OBSERVATION = "observation"

KNOWLEDGE_KINDS = (
    KNOWLEDGE_KIND_PREFERENCE,
    KNOWLEDGE_KIND_CONCLUSION,
    KNOWLEDGE_KIND_OBSERVATION,
)

# ``origin`` is who said it, and it is the column that decides whether a source
# URL exists at all. A reader stating their own risk appetite has no URL to
# cite, and demanding one would either block the memory or invent a citation —
# the second being the failure this whole table is arranged against. It does not
# change the evidence class: a remembered row stays an external claim whoever
# authored it (``grounding.py::EvidenceSource``).
KNOWLEDGE_ORIGIN_USER_STATED = "user_stated"
KNOWLEDGE_ORIGIN_SYSTEM_DERIVED = "system_derived"
KNOWLEDGE_ORIGIN_EXTERNAL_SOURCE = "external_source"

KNOWLEDGE_ORIGINS = (
    KNOWLEDGE_ORIGIN_USER_STATED,
    KNOWLEDGE_ORIGIN_SYSTEM_DERIVED,
    KNOWLEDGE_ORIGIN_EXTERNAL_SOURCE,
)


class AgentKnowledge(Base):
    """One deliberately remembered external claim with its original source.

    ``expires_at`` is the answer to memory that outlives its truth. A recall
    filters on it in SQL rather than leaving the model to judge staleness from a
    date, because a fact that should no longer be quoted is better absent than
    present with a caveat the answer may drop.
    """

    __tablename__ = "agent_knowledge"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    symbol = Column(String(20), nullable=True)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    kind = Column(
        String(16),
        nullable=False,
        server_default=text(f"'{KNOWLEDGE_KIND_OBSERVATION}'"),
    )
    origin = Column(
        String(16),
        nullable=False,
        server_default=text(f"'{KNOWLEDGE_ORIGIN_EXTERNAL_SOURCE}'"),
    )
    # Nullable only for the origins that genuinely have no source; the CHECK
    # below keeps an externally sourced row from losing its citation.
    source_url = Column(Text, nullable=True)
    source_name = Column(Text, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    as_of = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    tsv = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', immutable_unaccent("
            "coalesce(title, '') || ' ' || coalesce(body, '')"
            "))",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_agent_knowledge_user", "user_id"),
        Index("ix_agent_knowledge_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_agent_knowledge_title_trgm",
            text("immutable_unaccent(lower(title)) gin_trgm_ops"),
            postgresql_using="gin",
        ),
        CheckConstraint(
            f"origin <> '{KNOWLEDGE_ORIGIN_EXTERNAL_SOURCE}' OR source_url IS NOT NULL",
            name="ck_agent_knowledge_external_source_url",
        ),
    )


# `Base.metadata.create_all` is a test-only schema path in this repository. It
# still has to create the same generated columns as Alembic, which requires the
# extensions and immutable wrapper to exist before those tables are compiled.
# Both tables carry the listeners because a test creates whichever subset it
# needs, and `create_all` gives no ordering promise between two tables that do
# not reference each other.
for _unaccenting_table in (AgentMessage.__table__, AgentKnowledge.__table__):
    event.listen(
        _unaccenting_table,
        "before_create",
        DDL("CREATE EXTENSION IF NOT EXISTS unaccent"),
    )
    event.listen(
        _unaccenting_table,
        "before_create",
        DDL("CREATE EXTENSION IF NOT EXISTS pg_trgm"),
    )
    event.listen(
        _unaccenting_table,
        "before_create",
        DDL(
            """
            CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
            RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
            AS $$ SELECT public.unaccent('public.unaccent', $1) $$
            """
        ),
    )

del _unaccenting_table


# The one value of ``agent_tool_call.status`` that something other than the
# catalog reads, named where the column is declared so the reader and the writer
# cannot spell it differently. It is also ``docs/adr/0011``'s demand trigger — a
# model reaching for a tool that does not exist is the evidence for whether
# sandboxed execution is ever needed — which is why the fixed ops query counts
# the currently enabled catalog lacks — which is why the fixed ops query counts
# it by tool name rather than only totalling it.
#
# The other three stay as the literals ``src/agent/tools/catalog.py`` writes.
# Naming them here would leave three constants with no reader, and adopting them
# in the catalog is an edit inside ``src/agent/tools/``, which ``docs/adr/0016``
# makes any pull request carry an Eval Report for.
TOOL_CALL_UNKNOWN_TOOL = "unknown_tool"


# The five states of ``agent_turn.status``, named where the column is declared so
# that the lifecycle, the transport and spend admission all read one vocabulary.
# Three modules spelling ``"running"`` by hand is how one of them ends up
# spelling it differently.
TURN_ADMITTED = "admitted"
TURN_RUNNING = "running"
TURN_COMPLETE = "complete"
TURN_INCOMPLETE = "incomplete"
TURN_CANCELLED = "cancelled"

# A Turn is *active* while it has not reached a terminal state. Admission counts
# these; the publisher keeps a stream open for these; the startup sweep freezes
# exactly these.
ACTIVE_TURN_STATUSES = (TURN_ADMITTED, TURN_RUNNING)


class AgentTurn(Base):
    """The lifecycle of one **Turn**, and the draft checkpointed inside it.

    Its own table because neither neighbour can hold it: ``agent_message`` is
    canonical and immutable, and ``agent_tool_call`` is anchored to a single
    call. The id is chosen by the client so a reconnecting browser can ask about
    the Turn it started rather than the one it hopes it started.
    """

    __tablename__ = "agent_turn"

    id = Column(Uuid, primary_key=True)
    thread_id = Column(
        Uuid,
        ForeignKey("agent_thread.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_message_id = Column(
        BigInteger,
        ForeignKey("agent_message.id", ondelete="CASCADE"),
        nullable=False,
    )
    response_message_id = Column(
        BigInteger,
        ForeignKey("agent_message.id", ondelete="SET NULL"),
        nullable=True,
    )
    retry_of_turn_id = Column(
        Uuid,
        ForeignKey("agent_turn.id", ondelete="SET NULL"),
        nullable=True,
    )
    # admitted | running | complete | incomplete | cancelled
    status = Column(String(16), nullable=False)
    terminal_reason = Column(String(48), nullable=True)
    cancel_requested_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    # Where the SSE stream got to, so a reconnect resumes rather than replays.
    last_event_seq = Column(Integer, nullable=False, server_default="0")
    draft_content = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_agent_turn_thread_started", "thread_id", started_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<AgentTurn {self.id} {self.status}>"


class LlmCallUsage(Base):
    """One reservation against the budget, and what it actually cost.

    Written before the network call and reconciled after it. A death after the
    provider accepted the request leaves ``usage_unknown`` with the full
    reservation charged, which is the honest reading: the money is gone whether
    or not the answer arrived.

    The four prices are copied onto the row rather than looked up later. A price
    change must not silently rewrite what last month cost.

    ``owner_id`` is text because the four owner kinds are keyed differently — a
    run by a bigint, a Turn's request message by a bigint, a probe by a run
    identifier, an eval by a UUID. One nullable column per kind would be four
    columns of which three are always null.
    """

    __tablename__ = "llm_call_usage"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    # analysis_run | turn_request_message | capability_probe | eval_run
    owner_type = Column(String(32), nullable=False)
    owner_id = Column(String(64), nullable=False)
    user_id = Column(Integer, nullable=True)
    # analysis | turn | emergency | eval
    lane = Column(String(16), nullable=False)
    route = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    reserved_input_tokens = Column(Integer, nullable=False, server_default="0")
    reserved_output_tokens = Column(Integer, nullable=False, server_default="0")
    input_tokens = Column(Integer, nullable=False, server_default="0")
    cached_read_tokens = Column(Integer, nullable=False, server_default="0")
    cache_write_tokens = Column(Integer, nullable=False, server_default="0")
    output_tokens = Column(Integer, nullable=False, server_default="0")
    # Billed at the output price, which is why there are five counters and four
    # prices rather than five of each.
    reasoning_tokens = Column(Integer, nullable=False, server_default="0")
    pricing_version = Column(String(32), nullable=False)
    input_token_price_usd = Column(Numeric(20, 12), nullable=False)
    cached_read_token_price_usd = Column(Numeric(20, 12), nullable=False)
    cache_write_token_price_usd = Column(Numeric(20, 12), nullable=False)
    output_token_price_usd = Column(Numeric(20, 12), nullable=False)
    reserved_micro_usd = Column(BigInteger, nullable=False)
    actual_micro_usd = Column(BigInteger, nullable=True)
    # reserved | reconciled | usage_unknown
    status = Column(String(16), nullable=False)
    provider_called_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reconciled_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Admission sums open reservations plus actual spend over a window.
        Index("ix_llm_call_usage_created", "created_at"),
        Index("ix_llm_call_usage_owner", "owner_type", "owner_id"),
        Index("ix_llm_call_usage_lane_called", "lane", "provider_called_at"),
        Index("ix_llm_call_usage_user_called", "user_id", "provider_called_at"),
    )

    def __repr__(self) -> str:
        return f"<LlmCallUsage {self.owner_type}:{self.owner_id} {self.status}>"


class EvalRun(Base):
    """One pass of the **Eval Battery**, and everything it was run against.

    Every version that could move the score is copied onto the row — prompt,
    tool catalog, registry, fixture — because a score without them is a number
    nobody can reproduce or argue with.
    """

    __tablename__ = "eval_run"

    id = Column(Uuid, primary_key=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    # smoke | gate (``src/eval/harness.py``). Only ``gate`` runs the production
    # route and models, and only a gate run may be attached to a pull request.
    mode = Column(String(16), nullable=False)
    route = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    prompt_version = Column(String(32), nullable=False)
    tool_catalog_version = Column(String(32), nullable=False)
    registry_version = Column(String(32), nullable=False)
    fixture_version = Column(String(32), nullable=False)
    # Per-category pass/fail totals. JSONB because the categories are the
    # battery's business and adding one must not be a migration.
    category_totals = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    report_path = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<EvalRun {self.id} {self.mode}>"
