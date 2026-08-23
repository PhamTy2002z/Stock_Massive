"""The ten tables Alpha Desk stands on.

Nine of them were declared together and arrived in one revision. The tenth,
``analysis_tool_call``, came later and alone: it is the audit trail an Analysis
produced by a loop leaves behind, and nothing in the original nine depends on
it. Amending a revision other worktrees have already run is worse than adding
one.

Five of the nine stay empty until the agent loop lands. They are here anyway,
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
3. Traces anchor to the row that already exists before the first tool call, and
   the anchor is NOT NULL: a chat trace to the user's message
   (``request_message_id``), an Analysis trace to the run (``run_id``), never to
   the ``analysis`` row that only exists once production succeeded. A nullable
   anchor patched in later would orphan traces exactly when a Turn or a run dies
   mid-flight and the trace matters most.
"""

from sqlalchemy import (
    BigInteger,
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


class AnalysisToolCall(Base):
    """One tool call an Analysis made while it was being produced.

    An Analysis produced by a loop is no longer rebuildable from the store —
    ``src/alpha/envelope.py`` states the property this gives up, and this table
    is what is bought back with it. Reproducibility is replaced by audit: what
    was asked, what came back, in what order.

    **Anchored to the run, not to the Analysis.** A run exists before an
    Analysis does (``src/alpha/analysis_run.py``: a row in ``analysis`` existing
    means it is complete), so ``analysis.id`` is not available when the first
    tool call is made. Anchoring there would orphan the trace exactly when a run
    dies mid-flight and the trace is the most valuable thing left.

    **``round_index`` does not reset between attempts.** One run row serves all
    three attempts of a ``(symbol, trading_day)`` pair, so the trace of every
    attempt lands under the same run and the counter keeps climbing across them.
    A reader looking for "the second round" finds one row per attempt, not one
    row. This is the assumption most likely to be made wrong, which is why it is
    written here rather than left to the reader.

    Not a widened ``agent_tool_call``: that table's anchors are NOT NULL foreign
    keys to a Thread and a message, and an Analysis Run has neither. Nullable-ing
    them would teach every existing reader that two columns it relies on can now
    be null, and would put two retention policies — the chat trace is swept at 90
    days, an Analysis trace should live as long as its Analysis — on one
    ``started_at``.
    """

    __tablename__ = "analysis_tool_call"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(
        BigInteger,
        ForeignKey("analysis_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_index = Column(Integer, nullable=False)
    seq = Column(Integer, nullable=False)
    tool_name = Column(String(64), nullable=False)
    # The route's own id for this call. Nullable for the same reason as the chat
    # table's: a gateway that sent no id gives us nothing to store.
    tool_call_id = Column(String(128), nullable=True)
    arguments = Column(JSONB, nullable=False)
    result = Column(JSONB, nullable=True)
    # ok | tool_error | timeout | unknown_tool | blocked
    status = Column(String(16), nullable=False)
    error = Column(String(500), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # Order is a pair of columns, never a clock: two calls dispatched
        # together in one round share a millisecond, and a timestamp cannot
        # express inserting between two rows. Reading a run's whole trace in
        # order is the only query this table has, and this constraint's index
        # serves it — which is why there is no second index here, and none on
        # ``started_at``: nothing sweeps this table by age.
        UniqueConstraint(
            "run_id",
            "round_index",
            "seq",
            name="uq_analysis_tool_call_run_round_seq",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisToolCall run={self.run_id} "
            f"r{self.round_index}.{self.seq} {self.tool_name} {self.status}>"
        )


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


# The four reason labels a flag may carry. Declared where the column is, for the
# same reason the Turn statuses are: the store, the transport and the ops query
# all read one vocabulary, and a fifth label invented in one of them would be a
# category nothing else can count.
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
    and not a second opinion — and a new table for observability is not worth
    it. They are also the one thing about this row that changes; the message a
    flag is about is never rewritten by the flag.

    ``helpful_at`` is the opposite mark and carries no reason, because there is
    nothing to categorise about an answer that worked. It is a single stamp
    rather than a pair for exactly that reason, and it lives beside the flag
    rather than in a third column encoding both: the two marks are mutually
    exclusive in the UI but not in the store, and a reader who marks an answer
    helpful and then disputes one figure in it has said two true things.
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
    helpful_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("thread_id", "seq", name="uq_agent_message_thread_seq"),
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
    status = Column(String(16), nullable=False)  # one of TOOL_CALL_STATUSES below
    error = Column(String(500), nullable=True)
    # What the call *yielded*, where that is a different question from whether it
    # ran. ``status`` answers which kind of outcome the call had and ``error``
    # names the failure; neither can say that a successful store read came back
    # with no figure, which is what a third of ``get_field`` calls did while
    # every one of them was stored as ``ok``.
    #
    # Nullable because it is additive and because most tools have nothing to
    # classify: a web search either failed or returned results, and a row from
    # before this column existed cannot be told what it was.
    #
    # Holds the refusal's own **Signal Issue** rather than a flat "nothing" —
    # ``no_value:market_cap_absent`` and ``no_value:insufficient_cross_section``
    # are different operational facts, and one word for both would rebuild the
    # blind spot this column exists to close. The vocabulary is
    # ``agent/messages.py``.
    outcome = Column(String(64), nullable=True)
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


class AgentKnowledge(Base):
    """One deliberately remembered external claim with its original source."""

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
    source_url = Column(Text, nullable=False)
    source_name = Column(Text, nullable=False)
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    as_of = Column(DateTime(timezone=True), nullable=True)
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
    )


# `Base.metadata.create_all` is a test-only schema path in this repository. It
# still has to create the same generated column as Alembic, which requires the
# extensions and immutable wrapper to exist before this table is compiled.
event.listen(
    AgentKnowledge.__table__,
    "before_create",
    DDL("CREATE EXTENSION IF NOT EXISTS unaccent"),
)
event.listen(
    AgentKnowledge.__table__,
    "before_create",
    DDL("CREATE EXTENSION IF NOT EXISTS pg_trgm"),
)
event.listen(
    AgentKnowledge.__table__,
    "before_create",
    DDL(
        """
        CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
        RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT public.unaccent('public.unaccent', $1) $$
        """
    ),
)


# The four values of ``agent_tool_call.status``, named where the column is
# declared so the one writer (the trace adapter in ``src/agent/loop.py``) and the
# readers cannot spell them differently. Four constants because the column was
# declared with four values and written with two: a status nobody writes is a
# signal that reads zero forever.
#
# ``status`` answers *which kind of outcome*, in four groups. The ``error``
# column beside it keeps the specific reason — ``blocked_call``, ``halted_turn``,
# ``dispatch_failed``, ``round_fanout_exceeded`` — so neither column has to carry
# two questions.
#
# ``unknown_tool`` is the one value something other than the trace reads: a model
# reaching for a tool that does not exist is the evidence for whether sandboxed
# execution is ever worth building, which is why the fixed ops query counts it by
# tool name rather than only totalling it.
TOOL_CALL_OK = "ok"
TOOL_CALL_TOOL_ERROR = "tool_error"
TOOL_CALL_TIMEOUT = "timeout"
TOOL_CALL_UNKNOWN_TOOL = "unknown_tool"

#: Every value the column may hold, so a writer can be held to the vocabulary
#: instead of being trusted with it.
TOOL_CALL_STATUSES = (
    TOOL_CALL_OK,
    TOOL_CALL_TOOL_ERROR,
    TOOL_CALL_TIMEOUT,
    TOOL_CALL_UNKNOWN_TOOL,
)


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

    ``owner_id`` is text because the three owner kinds are keyed differently —
    a run by a bigint, a Turn's request message by a bigint, a probe by a run
    identifier. One nullable column per kind would be three columns of which
    two are always null.
    """

    __tablename__ = "llm_call_usage"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    # analysis_run | turn_request_message | capability_probe
    owner_type = Column(String(32), nullable=False)
    owner_id = Column(String(64), nullable=False)
    user_id = Column(Integer, nullable=True)
    # analysis | turn | emergency
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


