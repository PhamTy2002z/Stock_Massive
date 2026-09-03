"""Persistence models for the retained chat agent and its spend ledger."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Computed,
    DDL,
    DateTime,
    ForeignKey,
    Index,
    Identity,
    Integer,
    LargeBinary,
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

    ``content`` is JSONB because a message carries structured attachments and
    settled tool-call projections beside prose.

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
    # Legacy local-analysis classification. Runtime no longer writes or exposes
    # it; the column remains until schema retention is decided separately.
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


class AgentQuestion(Base):
    """One question the harness asked a reader, and what became of it.

    Its own table for the reason ``agent_turn`` has one: ``agent_message`` is
    canonical and immutable, and this state changes *after* the terminal
    transaction that wrote the message. The question itself is on the message,
    inside the assistant content, where every other typed part lives; what moves
    is the outcome, and a mutable column on an immutable row is the contradiction
    both of these tables exist to avoid.

    ``id`` is the part's own ``question_id``, so the card a client was handed and
    the row it posts an answer against are addressed by one identifier.

    ``user_id`` is a column here and not a join, unlike every other row in this
    schema. The two endpoints that resolve a question are reached by id alone —
    there is no Thread in the path to scope them — so ownership is the *first*
    predicate of the query rather than a join it could be written without.

    ``message_id`` is ``SET NULL`` rather than ``CASCADE``: the outcome of an
    asking is a fact about the conversation, and it outliving the row it was
    drawn on is better than a reader's answer disappearing with a message.
    """

    __tablename__ = "agent_question"

    id = Column(Uuid, primary_key=True)
    thread_id = Column(
        Uuid,
        ForeignKey("agent_thread.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_id = Column(
        Uuid,
        ForeignKey("agent_turn.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id = Column(
        BigInteger,
        ForeignKey("agent_message.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The part exactly as it was published and written into the message: prompt,
    # options, the multi-select flag, the skip label. Stored beside the outcome so
    # that validating an answer — is this an option this question offered — reads
    # one row instead of parsing a transcript.
    payload = Column(JSONB, nullable=False)
    # pending | answered | skipped | superseded
    state = Column(String(16), nullable=False)
    # The ids the reader chose, and null for every state that is not an answer:
    # an empty list would read as "chose nothing", which is what skipping is.
    selected_option_ids = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Both reads this table has: the pending question of a Thread, and the
        # supersede the next Turn's transaction runs over exactly that set.
        Index("ix_agent_question_thread_state", "thread_id", "state"),
    )

    def __repr__(self) -> str:
        return f"<AgentQuestion {self.id} {self.state}>"


class AgentEvidenceCache(Base):
    """A shareable copy of public web evidence, never a Turn or user artifact."""

    __tablename__ = "agent_evidence_cache"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    canonical_url = Column(Text, nullable=False)
    content_sha256 = Column(String(64), nullable=False)
    as_of_bucket = Column(String(64), nullable=False)
    policy_version = Column(String(32), nullable=False)
    cache_kind = Column(String(32), nullable=False)
    source_class = Column(String(32), nullable=False)
    title = Column(Text, nullable=False)
    publisher = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    publication = Column(JSONB, nullable=False)
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "canonical_url",
            "content_sha256",
            "as_of_bucket",
            "policy_version",
            name="uq_agent_evidence_cache_identity",
        ),
        CheckConstraint("char_length(content_sha256) = 64", name="ck_agent_evidence_cache_sha256"),
        Index("ix_agent_evidence_cache_lookup", "canonical_url", "as_of_bucket"),
        Index("ix_agent_evidence_cache_expires", "expires_at"),
    )


class AgentEvidenceTrajectory(Base):
    """Private, expiring research-pass material scoped directly to its owner."""

    __tablename__ = "agent_evidence_trajectory"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    turn_id = Column(
        Uuid,
        ForeignKey("agent_turn.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage = Column(String(32), nullable=False)
    payload = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_agent_evidence_trajectory_owner_turn", "user_id", "turn_id"),
        Index("ix_agent_evidence_trajectory_expires", "expires_at"),
    )


class AgentClaimLedger(Base):
    """The exact checked evidence contract behind one assistant message."""

    __tablename__ = "agent_claim_ledger"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    turn_id = Column(
        Uuid,
        ForeignKey("agent_turn.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    thread_id = Column(
        Uuid,
        ForeignKey("agent_thread.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id = Column(
        BigInteger,
        ForeignKey("agent_message.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    policy_version = Column(String(32), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_agent_claim_ledger_owner_message", "user_id", "message_id"),
        Index("ix_agent_claim_ledger_thread", "thread_id"),
    )


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



class AgentAttachment(Base):
    """One file a reader attached, held whole.

    **Why the bytes live in Postgres.** Not because a directory would not
    survive — ``docker compose restart`` keeps the writable layer, and compose
    already has a named volume. Three reasons that do hold:

    * ownership is a column here, read by the same owner-scoped join every other
      row in this schema is read through, rather than a second scheme invented
      for the filesystem;
    * ``pg_dump`` is already the backup procedure, so an attachment is backed up
      by something that already runs;
    * a Turn and the attachments it names commit or roll back together.

    ``attached_turn_id`` is what makes the sweep possible: a row still holding
    ``NULL`` past the grace period is an upload whose Turn was never sent, and
    nothing will ever read it again.
    """

    __tablename__ = "agent_attachment"

    id = Column(Uuid, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Set when the Turn that carries this attachment is created. Until then the
    # row is an upload in flight, and the sweep is allowed to take it.
    attached_turn_id = Column(
        Uuid,
        ForeignKey("agent_turn.id", ondelete="SET NULL"),
        nullable=True,
    )
    # What the bytes actually are, decided by reading them where that is
    # possible — never the client's word for it.
    media_type = Column(String(64), nullable=False)
    # The name is for the reader; it is sanitised on the way in and is never a
    # path, so nothing downstream may treat it as one.
    filename = Column(String(255), nullable=False)
    byte_size = Column(Integer, nullable=False)
    # Pixel dimensions for images, NULL for anything else. They are read from
    # the file header rather than measured, and they are what the token estimate
    # is computed from — an image's cost scales with its area, so a stored size
    # is the difference between an honest ceiling and a decorative one.
    pixel_width = Column(Integer, nullable=True)
    pixel_height = Column(Integer, nullable=True)
    content = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # The quota question — how many rows and how many bytes does this user
        # already hold — is asked on every upload.
        Index("ix_agent_attachment_user_created", "user_id", created_at.desc()),
        # The sweep asks for orphans by age.
        Index("ix_agent_attachment_orphans", "attached_turn_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AgentAttachment {self.id} {self.media_type} {self.byte_size}B>"
