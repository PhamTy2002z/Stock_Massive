"""Persistence models for the retained chat agent and its spend ledger."""

from sqlalchemy import (
    BigInteger,
    Column,
    Computed,
    DDL,
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



class AgentArtifact(Base):
    """One Study run, kept so the picture can be re-opened rather than re-run.

    Its own table rather than a column on ``agent_message``: the payload is
    numbers by the thousand and the message is text the browser needs
    immediately, so a join on the message would drag a heatmap into every
    transcript scroll. Split, the transcript loads at text weight and the canvas
    is fetched by whoever opens it.

    ``frames`` is the whole point of the row and the one part no model ever
    reads. It is served straight to the browser (``docs`` — the canvas panel),
    and the test that proves the separation reads the transcript for these keys.

    ``turn_id`` and ``thread_id`` are nullable because a Study also runs outside
    a Turn — the smoke script, and any later precompute. An artifact with
    neither is reachable by id alone, which is what such a run wants; one with
    both is what a reader re-opens.
    """

    __tablename__ = "agent_artifact"

    id = Column(Uuid, primary_key=True)
    turn_id = Column(
        Uuid,
        ForeignKey("agent_turn.id", ondelete="CASCADE"),
        nullable=True,
    )
    thread_id = Column(
        Uuid,
        ForeignKey("agent_thread.id", ondelete="CASCADE"),
        nullable=True,
    )
    study_name = Column(String(64), nullable=False)
    study_version = Column(Integer, nullable=False)
    # What the model asked for, after validation — not what it typed. A rejected
    # call never reaches this table, so these are always parameters that ran.
    params = Column(JSONB, nullable=False)
    frames = Column(JSONB, nullable=False)
    canvas_spec = Column(JSONB, nullable=False)
    provenance = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # Re-opening a thread asks for its artifacts newest first.
        Index("ix_agent_artifact_thread_created", "thread_id", created_at.desc()),
        Index("ix_agent_artifact_turn", "turn_id"),
    )

    def __repr__(self) -> str:
        return f"<AgentArtifact {self.id} {self.study_name} v{self.study_version}>"
