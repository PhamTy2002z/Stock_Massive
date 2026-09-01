"""One injected fault at a time, and the four properties every one of them holds.

Each test here breaks a Turn on purpose — the route stops answering, the route
repeats a tool-call id, a tool outlives its declared bound, the reader presses
stop in the middle of a model call or of a tool round, the tab stops reading, the
process goes away mid-write — and then asks the same four questions of what is
left behind:

**It settled, and it said why.** Every Turn reaches one of the three terminal
statuses with a reason from the vocabulary this deployment writes. A fault that
ended a Turn under nothing, or under a sentence, is a fault an operator cannot
count.

**Nothing is left waiting.** No persisted view of a finished Turn — the
checkpoint column, the canonical assistant message, the snapshot a reconnecting
reader is answered from — holds a call that is still ``pending`` or ``running``.
A spinner that outlives its Turn is drawn for as long as the Thread exists.

**Nothing outside this process happened twice.** A call that changes durable
state and is crossed by a stop runs to its end, exactly once, and the calls
behind it are answered rather than dispatched into a Turn that has ended.

**A reader who lost the stream loses nothing.** What a fresh snapshot restates is
what was published: the answer as the concatenation of its deltas, the
narration, the tool calls, the trail of what the loop did — and a card the Turn
ended by asking, whose outcome is then read back off the transcript.

The faults are injected through the scripted route and the tool world the other
agent tests use, so what is exercised is the shipped loop and the shipped
lifecycle rather than a copy of them.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress

import pytest

from src.agent.events import (
    ANSWER,
    SUBSCRIBER_QUEUE_SIZE,
    THOUGHT,
    EventType,
    TurnEvent,
    snapshot_from_draft,
)
from src.agent.executor import CANCELLED_CALL, INVALID_ARGUMENTS, TOOL_CALL_TIMEOUT
from src.agent.loop import (
    ADMISSION_STATUS,
    ANSWER_TRUNCATED,
    AUTH_UNAVAILABLE,
    CANCELLED_BY_USER,
    CONTENT_POLICY_BLOCKED,
    CONTEXT_OVERFLOW,
    DEADLINE_EXPIRED,
    EMPTY_ANSWER,
    GATEWAY_TIMEOUT,
    LLM_CALL_TIMEOUT,
    MAX_CONTEXT_COMPRESSIONS,
    MAX_EMPTY_NUDGES,
    MAX_OUTPUT_TOKENS_REDUCTIONS,
    MODEL_REFUSAL,
    MODEL_UNAVAILABLE,
    OUTPUT_CAP_EXCEEDED,
    ROUTE_ERROR,
    ROUTE_RATE_LIMITED,
    SCHEMA_REJECTED,
    TOOL_TIMEOUT,
    TURN_DEADLINE,
    TurnStatus,
)
from src.agent.messages import CALL_INTERRUPTED, UNSETTLED_STATUSES
from src.agent.parts import (
    ATTEMPT_CANCELLED,
    ATTEMPT_ERROR,
    QUESTION_ANSWERED,
    QUESTION_PENDING,
    QUESTION_SKIPPED,
    QUESTION_SUPERSEDED,
    RECOVERY_COMPRESS,
    RECOVERY_EMPTY_NUDGE,
    RECOVERY_LOWER_OUTPUT_CAP,
    ProgressKind,
)
from src.agent.persistence import INTERRUPTED_REASON, TURN_COMPLETE, TURN_INCOMPLETE
from src.core.llm import (
    Completion,
    ContextOverflow,
    OutputCapExceeded,
    RouteRateLimited,
    ToolCall,
    Usage,
)

from .test_agent_loop import (
    FakeClient,
    StallingClient,
    _answers_one_call_short,
    entry,
    install,
    long_history,
)
from .test_agent_turn_lifecycle import (  # noqa: F401 - the fixtures are used by name
    _tools,
    answer,
    card,
    committed_turn,
    messages_of,
    narrating,
    owner,
    runtime,
    schema,
    service,
    store,
    thread_for,
)

# What a Turn is allowed to end under. Assembled from the modules that write
# these strings rather than copied, so a reason added to the loop or to the
# lifecycle is a reason this gate accepts without being edited — and a reason
# invented at a call site is one it refuses.
TERMINAL_REASONS = (
    frozenset(
        {
            ANSWER_TRUNCATED,
            AUTH_UNAVAILABLE,
            CANCELLED_BY_USER,
            CONTENT_POLICY_BLOCKED,
            CONTEXT_OVERFLOW,
            DEADLINE_EXPIRED,
            EMPTY_ANSWER,
            GATEWAY_TIMEOUT,
            LLM_CALL_TIMEOUT,
            MODEL_REFUSAL,
            MODEL_UNAVAILABLE,
            OUTPUT_CAP_EXCEEDED,
            ROUTE_ERROR,
            ROUTE_RATE_LIMITED,
            SCHEMA_REJECTED,
            TOOL_TIMEOUT,
            TURN_DEADLINE,
        }
    )
    # The three the lifecycle owns rather than the loop: a container stopping, a
    # restart freezing what it found, and a failure the loop never named.
    | frozenset({"shutdown", "turn_failed", INTERRUPTED_REASON})
    | frozenset(ADMISSION_STATUS)
)

TERMINAL_STATUSES = frozenset(status.value for status in TurnStatus)

#: The wire spellings of a call somebody is still waiting on.
WAITING = frozenset(status.value for status in UNSETTLED_STATUSES)


# -- what every row asks of a finished Turn ----------------------------------


def waiting_calls(calls: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """The calls in one view that are still drawn as in flight."""
    return [call for call in calls if call.get("status") in WAITING]


async def settled_turn(
    owner_id: int, turn_id: uuid.UUID, thread_id: uuid.UUID
) -> tuple[object, Mapping[str, object] | None, Mapping[str, object]]:
    """Every persisted view of a finished Turn, checked before it is handed back.

    The two properties asserted here are the ones that hold whatever the fault
    was, which is why they live in one function every row calls rather than in
    each row's own tail: a Turn ends typed, and no view of it is left owing
    anybody a result. What comes back is the three views themselves, for the
    assertions only the row that injected the fault can make.
    """
    record = await store().read_turn(owner_id, turn_id)
    assert record is not None
    assert record.status in TERMINAL_STATUSES
    assert record.terminal_reason is None or record.terminal_reason in TERMINAL_REASONS
    assert record.finished_at is not None

    written = [row.content for row in messages_of(thread_id) if row.role == "assistant"]
    message = written[-1] if written else None
    # The third view: what a browser reconnecting after this process stopped
    # holding the Turn is answered from.
    replay = snapshot_from_draft(
        record.id,
        record.draft_content,
        status=record.status,
        terminal_reason=record.terminal_reason,
        through_seq=record.last_event_seq,
    ).data
    for view in (record.draft_content or {}, message or {}, replay):
        assert waiting_calls(tuple(view.get("tool_calls") or ())) == []
    return record, message, replay


def parts_of(view: Mapping[str, object], kind: ProgressKind) -> list[Mapping[str, object]]:
    """The payloads of one kind of part in a persisted trail, in order."""
    return [
        part["payload"]
        for part in tuple(view.get("progress") or ())
        if part["kind"] == kind.value
    ]


def recoveries(view: Mapping[str, object], action: str) -> list[Mapping[str, object]]:
    """Every recovery of one action the trail says actually ran."""
    return [
        payload
        for payload in parts_of(view, ProgressKind.RECOVERY)
        if payload["action"] == action
    ]


#: What a snapshot restates, and what :func:`restated` rebuilds from the events
#: to compare it against. Named once so the two sides cannot drift.
RESTATED_FIELDS = ("text", "thoughts", "tool_calls", "progress")


def restated(
    events: Sequence[TurnEvent], *, through: int | None = None
) -> dict[str, object]:
    """What a snapshot has to say, assembled from the events that were published.

    The four things a reader rebuilds a Turn from: the answer as the
    concatenation of its own deltas, the narration joined per round, the current
    state of each call in the order it was first announced, and the trail in the
    order it happened. ``through`` is the sequence a snapshot claims to cover, so
    a mid-Turn reconnection is compared against exactly what had been said by
    then.
    """
    covered = [
        event for event in events if through is None or event.seq <= through
    ]
    text = ""
    narration: dict[int, str] = {}
    calls: dict[str, dict[str, object]] = {}
    progress: list[dict[str, object]] = []
    for event in covered:
        if event.type is EventType.CONTENT_DELTA:
            piece = str(event.data["text"])
            if event.data["kind"] == THOUGHT:
                index = int(event.data["round"])
                narration[index] = narration.get(index, "") + piece
            else:
                assert event.data["kind"] == ANSWER
                text += piece
        elif event.type is EventType.TOOL_CALL:
            calls[str(event.data["id"])] = dict(event.data)
        elif event.type is EventType.PART_PROGRESS:
            progress.append(dict(event.data))
    return {
        "text": text,
        "thoughts": [
            {"round": index, "text": said} for index, said in sorted(narration.items())
        ],
        "tool_calls": list(calls.values()),
        "progress": progress,
    }


def taken(snapshot: TurnEvent) -> dict[str, object]:
    """The same four things, as one snapshot restates them."""
    return {key: snapshot.data[key] for key in RESTATED_FIELDS}


def narrated_batch(*names: str, text: str = "Đang tra.") -> Completion:
    """One round that says what it is about to do and then asks for several calls.

    The sentence matters to these tests and not only to the reader: a Turn that
    produced no prose at all writes no canonical message, so a fault injected
    into a silent round could only be read back off the checkpoint. The Contract
    asks the model for that sentence before every tool call anyway.
    """
    return Completion(
        model="gpt-5.6-terra",
        text=text,
        tool_calls=tuple(
            ToolCall(
                id=f"c{index}",
                name=name,
                arguments={"query": f"q{index}"},
                output_index=index,
            )
            for index, name in enumerate(names)
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def gated_tool(started: asyncio.Event, release: asyncio.Event):
    """A handler that announces it is running and then waits to be let go.

    An event rather than a sleep: what these tests need is the fault landing
    while the call is genuinely in flight, and a duration would make that a race
    against the machine they run on.
    """

    async def gated(_context, arguments):
        started.set()
        await release.wait()
        return {"found": arguments.get("query"), "ok": True}

    return gated


async def start(turns, owner_id: int, thread_id: uuid.UUID, text: str = "FPT thế nào?"):
    """Commit one Turn and hand back its id and its handle."""
    turn_id = uuid.uuid4()
    handle = await turns.create(
        user_id=owner_id,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text=text,
        runtime=runtime(owner_id),
    )
    return turn_id, handle


# -- the route stops answering ------------------------------------------------


@pytest.mark.asyncio
async def test_a_route_that_stops_answering_ends_on_our_own_call_ceiling(owner):
    """The ceiling on one call fires, and the round that had run is kept."""
    thread_id = await thread_for(owner)
    asked = asyncio.Event()
    # The first ask is answered, the second is held open for far longer than the
    # ceiling this Turn gives one call.
    client = StallingClient(narrating("web_search", "Đang tra."), asked=asked, stall=5.0)
    turns = service(client, loop={"call_timeout_seconds": 0.05})

    turn_id, _handle = await start(turns, owner, thread_id)
    await turns.running(turn_id).task

    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (TURN_INCOMPLETE, LLM_CALL_TIMEOUT)
    # The ask was torn down rather than left running behind a Turn that ended.
    assert client.answered == 0
    # What the first round produced is still the reader's, and the trail says
    # which asking of the model failed and why.
    assert message["text"] == "Đang tra."
    assert parts_of(message, ProgressKind.MODEL_ATTEMPT)[-1] == {
        "status": ATTEMPT_ERROR,
        "terminal_reason": LLM_CALL_TIMEOUT,
    }


@pytest.mark.asyncio
async def test_a_rate_limited_route_ends_the_turn_under_the_routes_own_reason(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([RouteRateLimited("not now")]))

    turn_id, _handle = await start(turns, owner, thread_id)
    await turns.running(turn_id).task

    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (
        TURN_INCOMPLETE,
        ROUTE_RATE_LIMITED,
    )
    # Nothing was said, so there is no message to keep — and the reason is on the
    # Turn either way, which is what an operator counts.
    assert message is None


# -- the route violates its own contract --------------------------------------


@pytest.mark.asyncio
async def test_a_route_that_repeats_a_call_id_fails_and_leaves_nothing_running(
    owner, monkeypatch
):
    """A repeated id is the failure that pairs a result with the wrong call.

    The Turn fails typed rather than answering from results nobody can attribute.
    What this row is also about is the settle on that path: the loop raised, so
    it never settled anything itself, and the last checkpoint is what becomes
    permanent — here holding a call that never got its result, because the round
    was made to come back one short.
    """
    thread_id = await thread_for(owner)
    _answers_one_call_short(monkeypatch)
    repeated = Completion(
        model="gpt-5.6-terra",
        tool_calls=(
            ToolCall(id="same", name="web_search", arguments={"query": "a"}),
            ToolCall(id="same", name="web_search", arguments={"query": "b"}),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )
    client = FakeClient([narrated_batch("web_search", "session_search"), repeated])
    turns = service(client)

    turn_id, _handle = await start(turns, owner, thread_id)
    await turns.running(turn_id).task

    record, message, replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (TURN_INCOMPLETE, "turn_failed")
    # The call the round answered keeps its own state; the one it did not is
    # settled in every view, and neither is left drawn as in flight.
    assert [call["status"] for call in message["tool_calls"]] == ["ok", "error"]
    assert [call.get("error") for call in message["tool_calls"]] == [
        None,
        CALL_INTERRUPTED,
    ]
    assert [call["status"] for call in record.draft_content["tool_calls"]] == [
        "ok",
        "error",
    ]
    assert [call["status"] for call in replay["tool_calls"]] == ["ok", "error"]


@pytest.mark.asyncio
async def test_arguments_that_are_not_json_settle_one_call_and_spare_its_sibling(owner):
    """A malformed argument object is a result, not the end of the Turn."""
    thread_id = await thread_for(owner)
    client = FakeClient(
        [
            Completion(
                model="gpt-5.6-terra",
                tool_calls=(
                    ToolCall(id="garbled", name="web_search", arguments="{not json"),
                    ToolCall(
                        id="fine", name="session_search", arguments={"query": "FPT"}
                    ),
                ),
                usage=Usage(input_tokens=10, output_tokens=5),
            ),
            answer("Kết luận cuối cùng."),
        ]
    )
    turns = service(client)

    turn_id, _handle = await start(turns, owner, thread_id)
    await turns.running(turn_id).task

    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (TURN_COMPLETE, None)
    assert [(call["id"], call["status"], call["error"]) for call in message["tool_calls"]] == [
        ("garbled", "error", INVALID_ARGUMENTS),
        ("fine", "ok", None),
    ]
    # The Turn went on and answered: the model was told what was wrong with the
    # one call and read the other one's result.
    assert message["answer"] == "Kết luận cuối cùng."
    assert len(client.requests) == 2


# -- the route answers and says nothing ---------------------------------------


@pytest.mark.asyncio
async def test_a_round_of_tools_with_no_reply_is_nudged_once_and_then_admits_it(owner):
    thread_id = await thread_for(owner)
    client = FakeClient(
        [
            narrating("web_search", "Đang tra."),
            Completion(model="gpt-5.6-terra", text=None),
            Completion(model="gpt-5.6-terra", text=None),
        ]
    )
    turns = service(client)

    turn_id, _handle = await start(turns, owner, thread_id)
    await turns.running(turn_id).task

    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (TURN_INCOMPLETE, EMPTY_ANSWER)
    # Three calls: the round, the round that answered nothing, and the one the
    # single nudge bought. A second nudge would pay again for what the first one
    # established.
    assert len(client.requests) == 3
    assert recoveries(message, RECOVERY_EMPTY_NUDGE) == [
        {"action": RECOVERY_EMPTY_NUDGE, "attempt": 1, "bound": MAX_EMPTY_NUDGES}
    ]
    # The narration is still the reader's, and the evidence the Turn paid for is
    # still attached to it.
    assert message["text"] == "Đang tra."
    assert [call["status"] for call in message["tool_calls"]] == ["ok"]


# -- the two recoveries that give ground and run out --------------------------


@pytest.mark.asyncio
async def test_a_transcript_that_never_fits_ends_after_the_compressions_it_ran(owner):
    """Two compressions, each reported once, and then the route's own reason."""
    thread_id = await thread_for(owner)
    client = FakeClient([ContextOverflow("the input did not fit")] * 3)
    turns = service(client)

    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
        # Deep enough that every rung still has an older Turn to give up, which
        # is what makes a second attempt worth paying for.
        history=long_history(turns=40),
    )
    await turns.running(turn_id).task

    record, _message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (TURN_INCOMPLETE, CONTEXT_OVERFLOW)
    assert len(client.requests) == MAX_CONTEXT_COMPRESSIONS + 1
    # Nothing was said, so the trail survives on the checkpoint rather than on a
    # message — and it says both compressions ran, with the bound they ran under.
    assert recoveries(record.draft_content, RECOVERY_COMPRESS) == [
        {
            "action": RECOVERY_COMPRESS,
            "attempt": attempt,
            "bound": MAX_CONTEXT_COMPRESSIONS,
        }
        for attempt in (1, 2)
    ]
    # Each attempt gave up transcript, which is what a reported compression
    # means — and the output ceiling was left alone, because this was never the
    # output's problem.
    sent = [
        sum(len(str(message.content or "")) for message in request.messages)
        for request in client.requests
    ]
    assert sent[0] > sent[1] > sent[2]
    assert len({request.max_output_tokens for request in client.requests}) == 1


@pytest.mark.asyncio
async def test_an_output_ceiling_that_never_fits_ends_after_the_reductions_it_ran(owner):
    thread_id = await thread_for(owner)
    client = FakeClient([OutputCapExceeded("no room for the reservation")] * 3)
    turns = service(client)

    turn_id, _handle = await start(turns, owner, thread_id)
    await turns.running(turn_id).task

    record, _message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (
        TURN_INCOMPLETE,
        OUTPUT_CAP_EXCEEDED,
    )
    assert len(client.requests) == MAX_OUTPUT_TOKENS_REDUCTIONS + 1
    assert recoveries(record.draft_content, RECOVERY_LOWER_OUTPUT_CAP) == [
        {
            "action": RECOVERY_LOWER_OUTPUT_CAP,
            "attempt": attempt,
            "bound": MAX_OUTPUT_TOKENS_REDUCTIONS,
        }
        for attempt in (1, 2)
    ]
    # Each attempt asked for strictly less output, and never for the same amount
    # twice: a second identical request would be paying to be refused again.
    ceilings = [request.max_output_tokens for request in client.requests]
    assert ceilings[0] > ceilings[1] > ceilings[2]
    # The transcript was left alone, because it was not what did not fit.
    sent = {
        sum(len(str(message.content or "")) for message in request.messages)
        for request in client.requests
    }
    assert len(sent) == 1


# -- a tool that outlives its declaration -------------------------------------


@pytest.mark.asyncio
async def test_a_tool_past_its_declared_bound_is_one_result_and_the_turn_answers(owner):
    """The bound on the call fires, not the backstop on the round.

    A tool that does not answer is a bound that has been reached rather than a
    Turn that has to end: the model is told what happened to that one call, and
    the answer is written from whatever else the round returned.
    """
    thread_id = await thread_for(owner)

    async def never_answers(_context, _arguments):
        await asyncio.sleep(5)
        return {"ok": True}

    install(entry("slow", never_answers, timeout_seconds=0.05))
    client = FakeClient([narrating("slow", "Đang tra."), answer("Kết luận cuối cùng.")])
    turns = service(client)

    turn_id, _handle = await start(turns, owner, thread_id)
    running = turns.running(turn_id)
    await running.task

    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (TURN_COMPLETE, None)
    assert message["answer"] == "Kết luận cuối cùng."
    assert [(call["status"], call["error"]) for call in message["tool_calls"]] == [
        ("error", TOOL_CALL_TIMEOUT)
    ]
    # The one fact about the call that is not on the wire, off the loop's own
    # record of it: the call was sent, and giving up on the answer does not make
    # it unsent.
    assert [call.dispatched for call in running.draft.tool_calls] == [True]


# -- the reader presses stop --------------------------------------------------


@pytest.mark.asyncio
async def test_a_stop_mid_model_call_settles_promptly_and_keeps_what_was_said(owner):
    """The stop reaches the call in flight, not the round boundary behind it.

    Asserting the wall clock and not only the status: polling a flag between
    rounds reaches the same terminal state minutes later, while the reader
    watches a spinner they have already dismissed.
    """
    thread_id = await thread_for(owner)
    asked = asyncio.Event()
    client = StallingClient(narrating("web_search", "Đang tra."), asked=asked, stall=5.0)
    turns = service(client)

    turn_id, _handle = await start(turns, owner, thread_id)
    running = turns.running(turn_id)
    await asked.wait()

    pressed = time.monotonic()
    await turns.cancel(owner, turn_id)
    await running.task
    elapsed = time.monotonic() - pressed

    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (
        TurnStatus.CANCELLED.value,
        CANCELLED_BY_USER,
    )
    assert elapsed < 2.5, "the stop waited the route out instead of ending the call"
    assert client.answered == 0
    # What the Turn had already said is kept, and the trail says the asking was
    # stopped rather than that it failed.
    assert message["text"] == "Đang tra."
    assert parts_of(message, ProgressKind.MODEL_ATTEMPT)[-1] == {
        "status": ATTEMPT_CANCELLED,
        "terminal_reason": CANCELLED_BY_USER,
    }
    assert [
        call for call in running.draft.tool_calls if call.status in UNSETTLED_STATUSES
    ] == []


@pytest.mark.asyncio
async def test_a_stop_mid_round_gives_up_the_reads_that_were_in_flight(owner):
    """Two reads overlapping, both given up on, both honest about being sent."""
    thread_id = await thread_for(owner)
    started, release = asyncio.Event(), asyncio.Event()
    gated = gated_tool(started, release)
    install(entry("web_search", gated), entry("session_search", gated))
    client = FakeClient(
        [narrated_batch("web_search", "session_search"), answer("Không tới đây.")]
    )
    turns = service(client)

    turn_id, _handle = await start(turns, owner, thread_id)
    running = turns.running(turn_id)
    await started.wait()

    # The stop lands while both reads are still out. Neither is waited out:
    # nothing is coming back that anybody will read.
    await turns.cancel(owner, turn_id)
    await running.task

    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (
        TurnStatus.CANCELLED.value,
        CANCELLED_BY_USER,
    )
    assert [(call["status"], call["error"]) for call in message["tool_calls"]] == [
        ("error", CANCELLED_CALL),
        ("error", CANCELLED_CALL),
    ]
    # Each of them left this deployment, and a record claiming otherwise is the
    # record that hides whatever the read did on the way.
    assert [call.dispatched for call in running.draft.tool_calls] == [True, True]
    # No further call was bought after the stop.
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_a_write_crossing_the_stop_happens_once_and_a_second_stop_adds_nothing(
    owner,
):
    """The one place duplicate external effects are prevented.

    A call that changes durable state and has already started is never torn
    down: it runs to its end, exactly once, and the calls queued behind it are
    answered by the boundary check when it returns rather than dispatched into a
    Turn that has ended.
    """
    thread_id = await thread_for(owner)
    started, release = asyncio.Event(), asyncio.Event()
    effects: list[str] = []

    async def remembers(_context, _arguments):
        started.set()
        await release.wait()
        effects.append("written")
        return {"ok": True}

    # Only the barrier is gated. The read behind it keeps the ordinary handler,
    # so a boundary check that dispatched it anyway fails this test rather than
    # hanging the suite.
    install(entry("remember_fact", remembers))
    client = FakeClient(
        [
            narrated_batch("remember_fact", "web_search", text="Đang ghi lại."),
            answer("Không tới đây."),
        ]
    )
    turns = service(client)

    turn_id, _handle = await start(turns, owner, thread_id, "Ghi nhớ giúp tôi.")
    running = turns.running(turn_id)
    await started.wait()

    first = await turns.cancel(owner, turn_id)
    second = await turns.cancel(owner, turn_id)
    release.set()
    await running.task

    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (
        TurnStatus.CANCELLED.value,
        CANCELLED_BY_USER,
    )
    # Once. Not zero, because the barrier had started; not twice, because
    # nothing retried it.
    assert effects == ["written"]
    # A second stop is the same stop: no further state, and no second effect.
    assert first.cancel_requested_at == second.cancel_requested_at
    assert [(call["status"], call["error"]) for call in message["tool_calls"]] == [
        ("ok", None),
        ("error", CANCELLED_CALL),
    ]
    # The read behind the barrier never left, and says so.
    assert [call.dispatched for call in running.draft.tool_calls] == [True, False]


# -- the tab stops reading ----------------------------------------------------


@pytest.mark.asyncio
async def test_a_dropped_tab_rebuilds_the_whole_turn_from_a_fresh_snapshot(owner):
    """A subscriber that missed events resubscribes and has missed nothing.

    Dropping a tab that stopped reading is what keeps a Turn from being slowed
    by one browser. What makes that safe is this: the snapshot a reconnecting
    reader is handed restates exactly what was published — the answer as the
    concatenation of its deltas, the narration, the calls and the trail — and
    after the terminal the same is true of a reader answered from the checkpoint.
    """
    thread_id = await thread_for(owner)
    started, release = asyncio.Event(), asyncio.Event()
    install(entry("web_search", gated_tool(started, release)))
    client = FakeClient(
        [narrating("web_search", "Đang tra."), answer("Kết luận cuối cùng.")]
    )
    turns = service(client)

    turn_id, handle = await start(turns, owner, thread_id)
    published = handle.publisher
    # Subscribed off the handle rather than through the service: it is
    # synchronous, so this happens before the Turn's first event and the two tabs
    # below see the whole of it.
    #
    # Two events deep rather than the transport's own ceiling: a test that filled
    # 256 would be measuring the constant instead of the drop.
    published._queue_size = 2  # noqa: SLF001 - the drop is what is under test
    gone = published.subscribe()
    published._queue_size = SUBSCRIBER_QUEUE_SIZE  # noqa: SLF001
    watching = published.subscribe()
    seen: list[TurnEvent] = []

    async def follow() -> None:
        async for event in watching.events():
            seen.append(event)

    reader = asyncio.create_task(follow())
    running = turns.running(turn_id)
    await started.wait()
    # The tab that stopped reading is gone by now, and the Turn was not held up
    # waiting for it.
    assert gone.dropped is True
    rejoined = published.subscribe().snapshot

    release.set()
    await running.task
    await reader

    # The mid-Turn reconnection, against what had been published to the tab that
    # never left, up to the sequence the snapshot says it covers.
    assert restated(seen, through=rejoined.data["through_seq"]) == taken(rejoined)
    # A tool round had run by then, so this is not an empty comparison.
    assert rejoined.data["tool_calls"] and rejoined.data["progress"]

    # The same, after the end: this is the snapshot carrying the answer, so it is
    # where "the text is exactly the concatenation of its deltas" is a claim about
    # something.
    ended = published.subscribe()
    assert restated(seen) == taken(ended.snapshot)
    assert ended.snapshot.data["text"] == "Kết luận cuối cùng."
    assert ended.snapshot.data["status"] == TURN_COMPLETE
    # The stream is already over for a reader who arrives now.
    assert [event async for event in ended.events()] == []

    # And once this process stops holding the Turn, the same reader is answered
    # from the checkpoint instead — with the sequence the publisher stopped at.
    record, message, replay = await settled_turn(owner, turn_id, thread_id)
    assert seen[-1].type is EventType.COMPLETED
    assert record.last_event_seq == seen[-1].seq
    late = await turns.subscribe(owner, turn_id)
    assert late.snapshot.data["through_seq"] == seen[-1].seq
    assert late.snapshot.data["status"] == TURN_COMPLETE
    # The checkpoint carries every piece of prose the Turn produced, which is
    # what the canonical message stores and what the next Turn is built from.
    assert late.snapshot.data["text"] == message["text"]
    assert message["answer"] == ended.snapshot.data["text"]
    assert late.snapshot.data["progress"] == message["progress"]
    assert late.snapshot.data["tool_calls"] == replay["tool_calls"]
    assert late.snapshot.data["message_id"] == record.response_message_id
    assert [event async for event in late.events()] == []


# -- the process goes away ----------------------------------------------------


@pytest.mark.asyncio
async def test_a_turn_a_restart_caught_mid_write_is_frozen_with_nothing_running(owner):
    """The intent survives the restart, and it does not survive as a spinner.

    A call that changes durable state is written down before it is dispatched, so
    a build that disappears mid-write leaves a record saying the effect may have
    landed. What that record must not do is stay ``pending`` for ever: the freeze
    settles it in the transcript and in the checkpoint both, and carries the
    trail the dead build had written.
    """
    thread_id = await thread_for(owner)
    started, release = asyncio.Event(), asyncio.Event()
    install(entry("remember_fact", gated_tool(started, release)))
    turns = service(
        FakeClient([narrating("remember_fact", "Đang ghi lại."), answer("Không tới đây.")])
    )

    turn_id, _handle = await start(turns, owner, thread_id, "Ghi nhớ giúp tôi.")
    running = turns.running(turn_id)
    await started.wait()

    # The intent is durable before the effect runs, which is the record the
    # freeze then has something to settle.
    mid = await store().read_turn(owner, turn_id)
    assert [call["status"] for call in mid.draft_content["tool_calls"]] == ["pending"]
    interrupted = mid.draft_content["progress"]
    assert interrupted, "the dead build's trail is what the freeze has to carry"

    # The process answering this Turn goes away between the dispatch and the
    # result, leaving the row active and the checkpoint as it stood.
    running.task.cancel()
    with suppress(asyncio.CancelledError):
        await running.task
    release.set()

    frozen = await service(FakeClient([])).sweep()

    assert [item.id for item in frozen] == [turn_id]
    record, message, _replay = await settled_turn(owner, turn_id, thread_id)
    assert (record.status, record.terminal_reason) == (
        TURN_INCOMPLETE,
        INTERRUPTED_REASON,
    )
    assert [(call["status"], call["error"]) for call in message["tool_calls"]] == [
        ("error", CALL_INTERRUPTED)
    ]
    # Everything but the status and the reason comes from the build that was
    # answering, the trail included.
    assert message["text"] == "Đang ghi lại."
    assert message["progress"] == interrupted


# -- a Turn that ended by asking ---------------------------------------------


def drawn_card(owner_id: int, thread_id: uuid.UUID, view) -> Mapping[str, object]:
    """The card as a reopened Thread draws it, live outcome merged in."""
    return next(
        row.content["question"]
        for row in view.messages
        if row.role == "assistant" and row.content.get("question")
    )


@pytest.mark.asyncio
async def test_a_card_survives_the_publisher_the_terminal_and_a_reopened_thread(owner):
    """The three outcomes of one asking, each read back where a reader reads it.

    A question is a terminal like any other, so the same two properties are
    asked of it — it settled typed, and nothing is left waiting. What it adds is
    the card: published before the terminal so a live reader needs no refetch,
    restated on the snapshot so a reader who reconnected in that gap is not the
    one who never sees it, and merged into the transcript afterwards, which is
    the only view a reopened Thread has of what became of it.
    """
    turns = service(FakeClient([answer("Xong.")]))
    thread_id = await thread_for(owner)
    running = await committed_turn(owner, thread_id)
    watching = running.publisher.subscribe()
    part = card()

    await turns.settle_with_question(
        running, text="Cần một dữ kiện.", question_part=part
    )

    seen = [event async for event in watching.events()]
    assert [event.type for event in seen] == [
        EventType.PART_QUESTION,
        EventType.COMPLETED,
    ]
    assert seen[0].data["question_id"] == part.question_id
    assert seen[0].data["state"] == QUESTION_PENDING
    # A reader who arrives after the terminal is handed the same card off the
    # snapshot, still pending, without refetching the Thread.
    late = running.publisher.subscribe().snapshot
    assert late.data["question"]["question_id"] == part.question_id
    assert late.data["question"]["state"] == QUESTION_PENDING

    record, message, replay = await settled_turn(owner, running.turn.id, thread_id)
    assert (record.status, record.terminal_reason) == (TURN_COMPLETE, None)
    assert message["question"]["question_id"] == part.question_id
    # The one view that never carries the outcome: a checkpoint is written before
    # the reader answers, so a state read out of it could only be a stale one.
    assert replay["question"] is None

    # Answered, in the transcript, with the choice that was made.
    await store().answer_question(owner, part.question_id, ["average"])
    answered = drawn_card(owner, thread_id, await store().read_thread(owner, thread_id))
    assert (answered["state"], answered["selected_option_ids"]) == (
        QUESTION_ANSWERED,
        ["average"],
    )

    # Skipped: a second Thread, because a card is resolved once.
    skipped_thread = await thread_for(owner)
    skipped_running = await committed_turn(owner, skipped_thread)
    skipped_part = card()
    await turns.settle_with_question(
        skipped_running, text="Cần một dữ kiện.", question_part=skipped_part
    )
    await store().skip_question(owner, skipped_part.question_id)
    skipped = drawn_card(
        owner, skipped_thread, await store().read_thread(owner, skipped_thread)
    )
    assert (skipped["state"], skipped["selected_option_ids"]) == (
        QUESTION_SKIPPED,
        None,
    )

    # Superseded: the reader typed into the composer instead of tapping, which is
    # the next Turn, and it resolves the card in the transaction that creates it.
    moved_thread = await thread_for(owner)
    moved_running = await committed_turn(owner, moved_thread)
    moved_part = card()
    await turns.settle_with_question(
        moved_running, text="Cần một dữ kiện.", question_part=moved_part
    )
    await start(turns, owner, moved_thread, "Thôi, hỏi kiểu khác.")
    superseded = drawn_card(
        owner, moved_thread, await store().read_thread(owner, moved_thread)
    )
    assert superseded["state"] == QUESTION_SUPERSEDED
    # And the card itself is unchanged in all three: the transcript holds what
    # was asked, and only the outcome moves.
    for outcome in (answered, skipped, superseded):
        assert outcome["prompt"] == part.prompt
        assert len(outcome["options"]) == len(part.options)
