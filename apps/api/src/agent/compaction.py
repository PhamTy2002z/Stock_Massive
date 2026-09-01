"""The hidden specialist that rewrites a long conversation's opening turns.

**It runs after a Turn has settled, never inside one.** The deterministic ladder
in ``messages.py`` already rescues the Turn in flight — it collapses old results
and drops old Turns until the context fits, and it does so without asking
anybody anything. What it cannot rescue is a conversation that was already long
when the question arrived: every later Turn pays the same climb down again, and
the reader's answer is assembled from a transcript that has been trimmed rather
than understood. So the summary is written *for the next Turn*, and the extra
model call is spent while nobody is waiting for an answer.

**Everything here fails open.** A provider error, a timeout, an empty reply, a
span that does not hold together, a store that refuses the write — each of them
ends with no summary row at all. The next Turn then builds exactly the context
it builds today, off the ladder, which is a context this system already runs on
every day. There is deliberately no path from this module back into a Turn: it
raises nothing at its caller, holds no lock a Turn waits on, and writes one
append-only row after the Turn's terminal transaction has committed.

**A summary is a claim about a span, and it carries its evidence.** The row says
which sequence numbers it covers, how many Turns that is, which messages it was
built from, which model wrote it and when. A summary whose span cannot be read
is unusable — ``build_messages`` refuses to apply one, because applying it would
mean guessing which Turns it replaced — so this module never writes one.

**Nothing is deleted.** The turns behind a summary stay in ``agent_message``
word for word, which is what makes ``session_search`` the recovery path for
whatever the compression dropped. The summary message says so to the model in
one line (``SUMMARY_LABEL``); no sixth tool is involved.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.core.llm import (
    BudgetLane,
    CallOwner,
    CompletionRequest,
    LLMClient,
    LLMConfig,
    Message,
    OwnerType,
    Role,
    SpendRequest,
    Workload,
)
from src.core.llm.admission import ANALYSIS_INPUT_PER_CALL

from .messages import CHARS_PER_TOKEN, ContextBudget
from .persistence import AgentPersistence, MessageRecord, SummaryRecord, latest_summary

logger = logging.getLogger(__name__)

#: The transcript role a summary is written under. Already accepted by
#: ``AgentPersistence.append_message``; no schema moves for this.
SUMMARY_ROLE = "summary"

#: What one summary may be worth in output tokens — a couple of paragraphs.
#:
#: Well inside the 3k an analysis call may generate, and small enough that one
#: pass costs about a fifth of a cent at batch prices. The *input* side of the
#: same ceilings is :data:`COMPACTION_INPUT_TOKENS`, which is derived rather
#: than chosen because that is the side a long conversation grows.
COMPACTION_OUTPUT_TOKENS = 700

#: How much transcript prose one pass would *like* to read. At the estimator's
#: three characters per token this is about five thousand tokens: several long
#: Turns, and cheap enough that compacting a thread is not an event anybody
#: budgets for. It is a preference, not a guarantee — the guarantee is
#: :data:`COMPACTION_INPUT_TOKENS` below.
MAX_SOURCE_CHARS = 15_000

#: What the envelope of two messages costs on top of their prose, in the same
#: pessimistic estimate the reservation is made with.
_ENVELOPE_TOKENS = 64

#: What one pass may reserve, derived rather than chosen.
#:
#: Admission refuses an analysis call reserved above ``ANALYSIS_INPUT_PER_CALL``,
#: and a refused compaction is the quietest failure this module has: it writes
#: nothing, raises nothing, and leaves a log line saying a ceiling was met. So
#: the pass is cut to fit *before* the money is asked for, and the number it is
#: cut to comes from the ceiling itself — a constant picked by hand here would
#: be a constant that drifts from the one that does the refusing.
#:
#: Four fifths of it. The remaining fifth is the margin between the estimate the
#: reservation is made on and a Vietnamese transcript, which tokenizes worse
#: than three characters to the token.
COMPACTION_INPUT_TOKENS = ANALYSIS_INPUT_PER_CALL * 4 // 5

#: The ceiling on one message's prose inside that budget, so a single enormous
#: answer cannot crowd out every other Turn in the span.
MAX_MESSAGE_CHARS = 3_000

#: The ceiling on what is stored. The route is asked for less than this, so it
#: is a backstop against a model that ignores the ask — a summary is charged to
#: the history layer of every later Turn, and an unbounded one would cost more
#: than the Turns it replaced.
MAX_SUMMARY_TEXT_CHARS = 4_000

#: The wall clock for the one call. Generous, because nobody is waiting on it,
#: and finite because an abandoned call still holds a connection.
CALL_TIMEOUT_SECONDS = 120.0

#: How long a thread that failed is left alone. Long enough that a route having
#: a bad minute is not asked again on the next Turn, short enough that a
#: conversation still gets compacted the same afternoon.
COOLDOWN_SECONDS = 900.0

SYSTEM = """\
Bạn viết bản tóm tắt nội bộ cho phần đầu của một cuộc hội thoại nghiên cứu tài
chính, để những lượt sau vẫn hiểu bối cảnh mà không phải đọc lại toàn bộ.

Giữ lại, theo đúng thứ tự quan trọng:
- ý định của người dùng và câu hỏi họ thực sự đang theo đuổi;
- mã cổ phiếu, doanh nghiệp, con số và mốc thời gian đã được nêu, kèm kỳ báo cáo
  hoặc ngày nếu bản gốc có;
- kết luận đã đạt được, và bằng chứng nào đứng sau kết luận đó;
- điều còn bỏ ngỏ, điều đã bị từ chối trả lời, và mâu thuẫn chưa giải quyết.

Ba điều tuyệt đối không làm:
1. Không thêm bất kỳ dữ kiện, con số hay nhận định nào không có trong bản gốc.
2. Không đưa ra khuyến nghị mua bán và không kết luận thay người dùng.
3. Không viết lời dẫn kiểu "đây là bản tóm tắt"; vào thẳng nội dung.

Viết bằng ngôn ngữ của cuộc hội thoại, dạng gạch đầu dòng ngắn, tối đa khoảng
250 từ. Nếu một chi tiết đã bị lược bỏ, người đọc sau vẫn tìm lại được bản gốc
trong hội thoại, nên hãy ưu tiên bức tranh chung hơn là trích dẫn dài.
"""


@dataclass(frozen=True)
class _Turn:
    """One user message and the answer that closed it, with its row numbers."""

    first_seq: int
    last_seq: int
    message_ids: tuple[int, ...]
    prose: str


@dataclass(frozen=True)
class CompactionPlan:
    """The span a pass would cover, decided before any money is spent.

    Built and checked first because every reason not to compact is cheaper to
    find here than after a call: nothing new outside the protected tail, a span
    that would not move the anchor forward, a thread with nothing in it.
    """

    covers_from_seq: int
    covers_to_seq: int
    summarised_turns: int
    source_message_ids: tuple[int, ...]
    previous_summary_message_id: int | None
    body: str


def _prose(record: MessageRecord) -> str:
    text = str(record.content.get("text") or "").strip()
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    return f"{text[:MAX_MESSAGE_CHARS].rstrip()}…"


def thread_turns(messages: Sequence[MessageRecord]) -> tuple[_Turn, ...]:
    """The Thread as Turns, paired the way the context constructor pairs it.

    Deliberately the same rule as ``router.history_of``: a user message opens a
    Turn and the assistant message after it closes one, and any other row —
    a summary written by an earlier pass — belongs to no Turn at all. The two
    have to agree, because one decides what ``summarised_turns`` counts and the
    other decides what that number is subtracted from.

    It pairs over records rather than over ``TranscriptTurn`` because a span is
    made of ``seq`` and message ids, and the transcript type drops both: it is
    built for the model, and the model has no use for a row number.
    """
    turns: list[_Turn] = []
    for record in messages:
        if record.role == "user":
            turns.append(
                _Turn(
                    first_seq=record.seq,
                    last_seq=record.seq,
                    message_ids=(record.id,),
                    prose=f"Người dùng: {_prose(record)}",
                )
            )
            continue
        if record.role != "assistant" or not turns:
            continue
        last = turns[-1]
        if last.last_seq != last.first_seq:
            # A second answer to one question: the Turn already closed, so this
            # is a row the pairing has no place for, exactly as the constructor
            # has none.
            continue
        turns[-1] = _Turn(
            first_seq=last.first_seq,
            last_seq=record.seq,
            message_ids=(*last.message_ids, record.id),
            prose=f"{last.prose}\nTrợ lý: {_prose(record)}",
        )
    return tuple(turns)


def plan_compaction(
    messages: Sequence[MessageRecord],
    *,
    keep_intact_turns: int,
    previous: SummaryRecord | None,
) -> CompactionPlan | None:
    """What this pass would cover, or ``None`` when there is nothing to do.

    Two rules decide the span, and both are boundaries the next Turn depends on.

    **The protected tail is never touched.** The last ``keep_intact_turns`` Turns
    are the ones the constructor refuses to drop, so summarising them would
    compress exactly the context the next question is about.

    **The anchor only moves forward.** A pass that would cover no more than the
    summary already on the row writes nothing: a later summary covering fewer
    Turns than an earlier one would silently uncover Turns whose prose the next
    context no longer carries, and the reader would watch the conversation lose
    its own beginning.

    **The pass fits the call before the call is made.** A body that would be
    reserved above :data:`COMPACTION_INPUT_TOKENS` is cut here, and what is cut
    is chosen so the span stays true: first the *span* narrows — covering fewer
    Turns is a smaller claim, not a false one — and only when a single Turn is
    left does the summary being carried forward get abridged. A span that
    claimed Turns nobody read would be worse than no summary, and no summary is
    what this returns when even that is not enough.
    """
    turns = thread_turns(messages)
    covered_before = previous.summarised_turns if previous else 0
    end = len(turns) - max(keep_intact_turns, 0)
    if end <= covered_before or end <= 0:
        return None

    fresh = list(turns[covered_before:end])
    head = previous.text if previous else ""
    while fresh and _body_length(head, fresh) > MAX_SOURCE_CHARS and len(fresh) > 1:
        # Too much prose for one pass: cover fewer Turns rather than read fewer
        # of the ones being claimed. A span narrower than asked for is still a
        # true span, and the next settled Turn moves the anchor the rest of the
        # way.
        fresh.pop()
    if not fresh:
        return None

    body = _body(head, fresh)
    if len(body) > _SOURCE_CEILING_CHARS:
        # One Turn left, and the pass is still above what admission will fund.
        # What is oversized here is the one piece of prose this module did not
        # write — a summary row read back from the store — so that is what
        # gives way. An abridged head still summarises the span it says it
        # summarises; the alternative is a call the ledger refuses, and a thread
        # that is never compacted again because the same refusal happens every
        # time.
        room = _head_room(fresh)
        if room <= 0:
            # The Turns alone are past the ceiling. Nothing here may claim a
            # span it did not read, so this pass writes nothing at all and the
            # next Turn builds its context off the ladder, as it does today.
            return None
        head = f"{head[:room].rstrip()}{_ELLIPSIS}"
        body = _body(head, fresh)

    covers_to_seq = fresh[-1].last_seq
    if previous is not None and covers_to_seq <= previous.covers_to_seq:
        return None
    covers_from_seq = previous.covers_from_seq if previous else turns[0].first_seq
    if covers_from_seq > covers_to_seq:
        return None

    return CompactionPlan(
        covers_from_seq=covers_from_seq,
        covers_to_seq=covers_to_seq,
        summarised_turns=covered_before + len(fresh),
        source_message_ids=tuple(
            message_id for turn in fresh for message_id in turn.message_ids
        ),
        previous_summary_message_id=previous.message_id if previous else None,
        body=body,
    )


#: The three fixed strings the pass's prose is assembled from. Named rather
#: than written inline because :func:`_head_room` has to subtract them: the
#: room left for a summary being carried forward is the ceiling minus the Turns
#: minus exactly these.
_HEAD_LABEL = "Tóm tắt đã có của phần trước hội thoại:\n"
_HEAD_JOIN = "\n\nCác lượt tiếp theo cần gộp vào bản tóm tắt đó:\n"
_OPENING_LABEL = "Các lượt đầu của hội thoại:\n"

#: What an abridged head ends on, so the model reads a summary that was cut
#: rather than one that stopped making sense.
_ELLIPSIS = "…"


def _body(head: str, turns: Sequence[_Turn]) -> str:
    blocks = "\n\n".join(turn.prose for turn in turns)
    if head:
        return f"{_HEAD_LABEL}{head}{_HEAD_JOIN}{blocks}"
    return f"{_OPENING_LABEL}{blocks}"


def _body_length(head: str, turns: Sequence[_Turn]) -> int:
    return len(_body(head, turns))


def _estimated_input_tokens(body: str) -> int:
    """The worst case this call asks admission to fund.

    Estimated from the text rather than fixed at the per-call ceiling, because
    the reservation is what the lane is charged until the route reconciles it,
    and reserving four times the real cost of every compaction would spend the
    analysis lane on calls that never happened. The estimator is the same
    pessimistic one the context ceiling is met with, plus the overhead of two
    message envelopes.
    """
    return (len(SYSTEM) + len(body)) // CHARS_PER_TOKEN + _ENVELOPE_TOKENS


#: The longest body whose reservation still lands under
#: :data:`COMPACTION_INPUT_TOKENS`. The arithmetic of
#: :func:`_estimated_input_tokens`, run backwards.
_SOURCE_CEILING_CHARS = (
    COMPACTION_INPUT_TOKENS - _ENVELOPE_TOKENS
) * CHARS_PER_TOKEN - len(SYSTEM)


def _head_room(turns: Sequence[_Turn]) -> int:
    """How much of an existing summary this pass can still carry with it."""
    return (
        _SOURCE_CEILING_CHARS
        - len(_HEAD_LABEL)
        - len(_HEAD_JOIN)
        - len("\n\n".join(turn.prose for turn in turns))
        - len(_ELLIPSIS)
    )


class ThreadCompactor:
    """One model call per thread, spent after a Turn rather than during one.

    The cooldown is process-local on purpose. It exists to stop a route having a
    bad minute from being asked again on every settled Turn, and that is a
    question about *this* process's last few minutes. Losing it to a restart
    loses it in the safe direction — the next settled Turn tries once more,
    which is the behaviour a fresh deployment should have anyway — and keeping
    it in a table would mean a durable write on the failure path of a component
    whose whole contract is that its failures cost nothing.
    """

    def __init__(
        self,
        *,
        client: LLMClient,
        config: LLMConfig,
        store: AgentPersistence,
        budget: ContextBudget | None = None,
        cooldown_seconds: float = COOLDOWN_SECONDS,
        timeout_seconds: float = CALL_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._config = config
        self._store = store
        self._budget = budget or ContextBudget()
        self._cooldown = cooldown_seconds
        self._timeout = timeout_seconds
        self._clock = clock
        self._cooling: dict[str, float] = {}

    @property
    def model(self) -> str:
        return self._config.model_for(Workload.BATCH)

    async def compact(
        self, *, thread_id: uuid.UUID | str, user_id: int
    ) -> MessageRecord | None:
        """Summarise this thread's opening Turns, or leave it exactly as it is.

        Returns the row it wrote, or ``None`` for every other outcome — nothing
        to summarise, a thread still in cooldown, or any failure at all. The
        caller is a settled Turn, and there is no answer it could give this
        method that would be worth interrupting a reader for.
        """
        key = str(thread_id)
        if self._cold(key):
            return None
        try:
            view = await self._store.read_thread(user_id, thread_id)
            if view is None:
                return None
            plan = plan_compaction(
                view.messages,
                keep_intact_turns=self._budget.keep_intact_turns,
                previous=latest_summary(view.messages),
            )
            if plan is None:
                return None
            text = await self._write(plan, thread_id=key, user_id=user_id)
            return await self._store.append_message(
                thread_id,
                role=SUMMARY_ROLE,
                content=self._content(plan, text),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a failed summary is not a fault
            # Every failure lands here and stops here. Whatever went wrong —
            # the route, the ceiling, the reply, the write — the conversation
            # keeps the context it already had.
            self._cooling[key] = self._clock() + self._cooldown
            logger.warning(
                "Compaction of thread %s wrote nothing (%s: %s)",
                key,
                type(exc).__name__,
                exc,
            )
            return None

    def _cold(self, key: str) -> bool:
        until = self._cooling.get(key)
        if until is None:
            return False
        if self._clock() < until:
            return True
        del self._cooling[key]
        return False

    async def _write(
        self, plan: CompactionPlan, *, thread_id: str, user_id: int
    ) -> str:
        """The one call, and the only reading of its reply.

        An empty reply raises rather than being stored: a summary message whose
        text says nothing would still displace the Turns it claims to cover, so
        the honest outcome of a route that answered with nothing is no summary.
        """
        request = CompletionRequest(
            model=self.model,
            messages=(
                Message(role=Role.SYSTEM, content=SYSTEM),
                Message(role=Role.USER, content=plan.body),
            ),
            # No tools, and none may be added: a specialist that could search
            # would be a second agent, and this one's whole contract is to
            # rewrite what it was given.
            tools=(),
            tool_choice="none",
            max_output_tokens=COMPACTION_OUTPUT_TOKENS,
            stream=False,
            metadata={"compaction": f"{thread_id}:{plan.covers_to_seq}"},
        )
        spend = SpendRequest(
            # Out-of-band batch work, so it rides the analysis lane rather than
            # the one serving readers or the one held back for provider
            # recovery. The owner id is unique per attempt because the owner
            # ceiling counts a reservation whether or not the call answered:
            # sharing an id across retries would let one failed attempt close
            # the door on the span it failed to summarise.
            owner=CallOwner(
                OwnerType.ANALYSIS_RUN,
                f"thread-compaction:{thread_id}:{uuid.uuid4().hex}",
                user_id=user_id,
            ),
            lane=BudgetLane.ANALYSIS,
            workload=Workload.BATCH,
            input_tokens=_estimated_input_tokens(plan.body),
            output_tokens=COMPACTION_OUTPUT_TOKENS,
        )
        completion = await asyncio.wait_for(
            self._client.complete(request, spend), self._timeout
        )
        text = (completion.text or "").strip()
        if not text:
            raise ValueError("the route returned no summary text")
        if len(text) > MAX_SUMMARY_TEXT_CHARS:
            text = f"{text[:MAX_SUMMARY_TEXT_CHARS].rstrip()}…"
        return text

    def _content(self, plan: CompactionPlan, text: str) -> dict[str, Any]:
        """The row, with everything a later Turn needs to apply it.

        The prose is stored under ``summary`` and not under ``text``, and that
        is the recovery path rather than a naming preference: ``session_search``
        reads ``content->>'text'``, so a summary filed under that key would come
        back as a match for the very words it compressed and push the original
        Turns down the list. What the reader's search has to reach is the Turn
        that said it.
        """
        return {
            "summary": text,
            "covers_from_seq": plan.covers_from_seq,
            "covers_to_seq": plan.covers_to_seq,
            "summarised_turns": plan.summarised_turns,
            "source_message_ids": list(plan.source_message_ids),
            "previous_summary_message_id": plan.previous_summary_message_id,
            "model": self.model,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


__all__ = [
    "COMPACTION_INPUT_TOKENS",
    "COOLDOWN_SECONDS",
    "MAX_SOURCE_CHARS",
    "MAX_SUMMARY_TEXT_CHARS",
    "SUMMARY_ROLE",
    "CompactionPlan",
    "ThreadCompactor",
    "plan_compaction",
    "thread_turns",
]
