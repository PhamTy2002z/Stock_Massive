"""The context engine's gates, asserted where a whole system holds them.

Every rule here is one the unit suites cannot state on their own, because each
of them is a property of two or more parts agreeing: the ladder and the renderer,
the loop and the route's own token count, the tool that reads a page and the
trace that outlives the Turn it was read in, the specialist that writes a summary
and the constructor that applies one. A gate that could be proved inside a single
module belongs in that module's file, and is deliberately not repeated here.

What lives here
---------------

* **No call is ever separated from its result.** Walked over *every* rung of the
  ladder and every ageing set it starts from, rather than over a few chosen
  ceilings.
* **The ladder only ever comes down**, and the one overflow it cannot absorb
  still settles the Turn under a reason with the partial answer intact.
* **A page read in one Turn is reused in the next with no request at all**, over
  the real store, the real tool and two real Turns, with the cache taken away.
* **Nothing a Turn cited stops being reachable when its results collapse**, and
  a summary never reaches into the protected tail.
* **The route's own count is what decides**, and an estimate that is wrong does
  not drag the decision wrong with it.
* **No failure of the summary specialist can change a byte of the next Turn's
  context.**
* **The playbook is carried on intent**, and the two prompts that produces are
  told apart by the cache key and share their core byte for byte.

What lives elsewhere, and is not repeated
-----------------------------------------

``tests/test_agent_loop.py``
    The ageing rung's own arithmetic, the layer breakdown, the two bounded
    recoveries (``compress`` and ``lower_output_cap``), the progress trail, the
    route-failure taxonomy, and the per-question playbook decision.
``tests/test_agent_messages`` — folded into ``test_agent_loop.py``
    ``build_messages`` rung by rung: what collapses, what drops, what a handle
    keeps.
``tests/test_agent_compaction.py``
    The span rules, the cooldown, and each failure path of the specialist one at
    a time.
``tests/test_agent_web_tools.py``
    Serving a page from the Thread's record at the tool boundary: the freshness
    window, the excerpt rule, the denylist, the store that is down.
``tests/test_agent_persistence_paths.py``
    ``recorded_result``: thread scope, containment matching, a trimmed body.
``tests/test_agent_domain_pack.py``
    Which words put a question inside the domain.
``tests/golden/test_context_replay.py``
    That the replay is pure and that its layers add up.
"""

from __future__ import annotations

import json
import os.path
import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from typing import Any

import pytest
from sqlalchemy import delete

from src.agent.compaction import (
    COMPACTION_INPUT_TOKENS,
    MAX_SOURCE_CHARS,
    _estimated_input_tokens,
    plan_compaction,
)
from src.agent.loop import (
    CONTEXT_OVERFLOW,
    AgentLoop,
    ContextBudget,
    Transcript,
    TranscriptTurn,
    TurnRequest,
    TurnStatus,
    ToolCallStatus,
    TurnToolCall,
    build_messages,
    estimate_tokens,
)
from src.agent.messages import (
    _reductions,
    _render_messages,
    aged_results,
    worth_collapsing,
)
from src.agent.parts import ATTEMPT_ERROR, ProgressKind
from src.agent.persistence import AgentPersistence, SummaryRecord
from src.agent.prompt import RuntimeContext, prefix as prompt_prefix, render
from src.agent.tools import web
from src.alpha.models import AgentThread
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.core.llm import Completion, Message, Role, ToolCall, Usage

from .agent_tool_world import isolated_registry
from .test_agent_compaction import FakeStore, compactor, constructed, conversation
from .test_agent_loop import (
    FakeClient,
    RecordingPublisher,
    config,
    entry,
    install,
    long_history,
    loop,
    only,
    turn_request,
)
from .test_agent_web_tools import resolver_for, settings


@pytest.fixture(autouse=True)
def _catalog():
    """The shipped catalog's five names, registered per test.

    The registry is process-wide, so a file that runs a loop borrows it rather
    than adding to it. The one test that needs the *real* web tools opens its
    own nested borrowing, which is what makes it the real path rather than these
    stubs.
    """
    with isolated_registry():
        install(
            entry("web_search"),
            entry("fetch_url"),
            entry("session_search"),
            entry("recall_facts"),
            entry("remember_fact"),
        )
        yield


# -- the transcripts every ladder assertion is walked over -------------------


def _call(
    identifier: str,
    name: str,
    *,
    round_index: int,
    url: str,
    body: str,
) -> TurnToolCall:
    """One finished call whose result names its own URL, as a real one does."""
    return TurnToolCall(
        id=identifier,
        name=name,
        arguments={"url": url} if name == "fetch_url" else {"query": identifier},
        status=ToolCallStatus.OK,
        result_text=json.dumps({"url": url, "text": body}, ensure_ascii=False),
        results=({"url": url, "source": "news.example"},),
        round=round_index,
    )


def _turn(index: int, *, calls: int, body_chars: int) -> TranscriptTurn:
    return TranscriptTurn(
        user_text=f"Câu hỏi số {index} " + "x" * 120,
        tool_calls=tuple(
            _call(
                f"t{index}c{round_index}",
                "web_search" if round_index % 2 == 0 else "fetch_url",
                round_index=round_index,
                url=f"https://news.example/{index}-{round_index}",
                body="nội dung " * body_chars,
            )
            for round_index in range(calls)
        ),
        assistant_text=f"Trả lời số {index} " + "z" * 120,
    )


#: Four transcripts, chosen so that the ageing set the ladder starts from is a
#: different set in each: no calls at all, one round, three rounds of two tools,
#: and results too short to be worth a handle. The last one is the shape that
#: used to make the ladder climb upward.
SHAPES: dict[str, tuple[TranscriptTurn, ...]] = {
    "no_calls": tuple(
        TranscriptTurn(user_text=f"Câu {index}", assistant_text="Vâng.")
        for index in range(5)
    ),
    "one_round": tuple(_turn(index, calls=1, body_chars=80) for index in range(5)),
    "many_rounds": tuple(_turn(index, calls=3, body_chars=60) for index in range(4)),
    "tiny_results": tuple(_turn(index, calls=2, body_chars=1) for index in range(4)),
}


def _transcript(turns: Sequence[TranscriptTurn]) -> Transcript:
    return Transcript(
        system_prompt=render(RuntimeContext(today=date(2026, 8, 29), user_name="Ty")),
        system_prefix=prompt_prefix(),
        turns=tuple(turns),
    )


def _rungs(
    turns: Sequence[TranscriptTurn],
) -> list[tuple[int, int, frozenset[str], tuple[Message, ...]]]:
    """Every rung of the ladder for one transcript, rendered.

    The two filters ``build_messages`` applies before it starts climbing —
    what the newest Turn has stopped reading, and what collapsing would actually
    buy — are applied here as well, because a rung asserted without them is a
    rung nothing constructs.
    """
    transcript = _transcript(turns)
    aged = aged_results(turns[-1]) if turns else frozenset()
    worth = worth_collapsing(turns)
    rendered = []
    for rung, (dropped, collapsed) in enumerate(_reductions(turns, ContextBudget())):
        applied = (collapsed | aged) & worth
        tagged = _render_messages(transcript, turns, dropped, applied)
        rendered.append(
            (rung, dropped, applied, tuple(piece.message for piece in tagged))
        )
    return rendered


def _assert_paired(messages: Sequence[Message]) -> None:
    """Every ask is followed by its own results, and every result by nothing else.

    Walked rather than counted. A context can hold the right *number* of calls
    and results and still be unusable — a route rejects a tool result whose ask
    is not the message in front of it — so the walk asserts adjacency and order,
    and the tally at the end asserts that nothing was quietly left out.
    """
    asked: list[str] = []
    answered: list[str] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.tool_calls:
            identifiers = [call.id for call in message.tool_calls]
            following = messages[index + 1 : index + 1 + len(identifiers)]
            assert [item.role for item in following] == [Role.TOOL] * len(identifiers)
            assert [item.tool_call_id for item in following] == identifiers
            asked.extend(identifiers)
            answered.extend(str(item.tool_call_id) for item in following)
            index += 1 + len(identifiers)
            continue
        assert message.role is not Role.TOOL, "a result with no ask in front of it"
        index += 1
    assert asked == answered


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_no_rung_of_the_ladder_separates_a_call_from_its_result(shape: str) -> None:
    """The invariant a route enforces and a harness has to guarantee.

    Every rung, not a sample of them: the rungs that drop Turns and the rungs
    that collapse results reach the message list by different code, and the one
    that is wrong is the one nobody chose to test.
    """
    rungs = _rungs(SHAPES[shape])

    assert len(rungs) > 1
    for _rung, _dropped, _collapsed, messages in rungs:
        _assert_paired(messages)


def test_the_ageing_the_ladder_starts_from_is_not_the_same_set_every_time() -> None:
    """Otherwise the sweep above is one ageing set asserted four times."""
    aged = {
        shape: aged_results(turns[-1]) for shape, turns in SHAPES.items() if turns
    }

    assert len({frozenset(value) for value in aged.values()}) > 1
    assert aged["no_calls"] == frozenset()
    assert aged["many_rounds"]


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_url_a_shown_turn_found_survives_its_results_collapsing(
    shape: str,
) -> None:
    """A collapse sheds the prose and keeps the address it came from.

    Asserted against the Turns still in the context, because a Turn the ladder
    dropped is a Turn the reader can still scroll to and the model is honestly
    told nothing about. What would be a defect is a Turn that is *present* and
    can no longer say where its figures came from.
    """
    for _rung, dropped, _collapsed, messages in _rungs(SHAPES[shape]):
        body = "\n".join(message.content or "" for message in messages)
        for turn in SHAPES[shape][dropped:]:
            for call in turn.completed_calls:
                for item in call.results:
                    assert str(item["url"]) in body


# -- the ladder only ever comes down -----------------------------------------


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_no_rung_of_the_ladder_costs_more_than_the_rung_above_it(shape: str) -> None:
    """A concession that made the context bigger would be a ladder that climbs.

    It is not a theoretical failure: the handle that replaces a result is a
    sentence, and a result short enough — a rate, an empty search — is shorter
    than the sentence. The constructor now refuses that trade, and this is where
    the refusal is held.
    """
    costs = [
        sum(estimate_tokens(message) for message in messages)
        for _rung, _dropped, _collapsed, messages in _rungs(SHAPES[shape])
    ]

    assert costs == sorted(costs, reverse=True)
    assert costs[-1] <= costs[0]


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_a_ceiling_that_falls_never_hands_back_a_larger_context(shape: str) -> None:
    """The same property seen through the public door, and the one that matters.

    ``build_messages`` returns the first rung that fits, so a ladder that is
    monotone gives a caller lowering its ceiling a context that never grows and
    a rung that never walks back up.
    """
    transcript = _transcript(SHAPES[shape])
    whole = build_messages(transcript, ContextBudget(max_tokens=1_000_000))

    previous = whole
    for ceiling in range(whole.estimated_tokens, 0, -max(1, whole.estimated_tokens // 12)):
        try:
            context = build_messages(transcript, ContextBudget(max_tokens=ceiling))
        except Exception as refused:  # noqa: BLE001 - the ladder's own last word
            assert type(refused).__name__ == "ConstructedContextTooLarge"
            break
        assert context.estimated_tokens <= ceiling
        assert context.estimated_tokens <= previous.estimated_tokens
        assert context.rung >= previous.rung
        _assert_paired(context.messages)
        previous = context


@pytest.mark.asyncio
async def test_a_turn_the_ladder_cannot_fit_settles_and_keeps_what_it_said() -> None:
    """The overflow that never reaches the route still ends the Turn honestly.

    The condition is the one real usage feedback made reachable: the route
    charges far more than the characters suggested, so the next construction is
    projected past the ceiling at every rung and the ladder runs out. That is
    the same fact the route calls ``context_overflow``, and it must arrive as a
    settled Turn carrying the prose already produced — an exception leaving the
    loop would take the reader's half-answer with it.
    """
    publisher = RecordingPublisher()
    client = FakeClient(
        [
            Completion(
                model="gpt-5.6-luna",
                text="Để tôi tra đã.",
                tool_calls=(
                    ToolCall(id="c1", name="web_search", arguments={"query": "lãi suất"}),
                ),
                # Fifty times what the characters said. Nothing else about the
                # Turn changes: the transcript, the ceiling and the script are
                # what they were.
                usage=Usage(input_tokens=500_000, output_tokens=5),
            ),
            Completion(model="gpt-5.6-luna", text="Không bao giờ đọc tới đây."),
        ]
    )

    outcome = await loop(
        client, publisher=publisher, budget=ContextBudget(max_tokens=12_000)
    ).run(turn_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == CONTEXT_OVERFLOW
    # The narration the first round produced is still the reader's.
    assert "Để tôi tra đã." in (outcome.text or "")
    # And the second call was never bought.
    assert len(client.requests) == 1
    closing = only(publisher, ProgressKind.MODEL_ATTEMPT)[-1]
    assert closing["status"] == ATTEMPT_ERROR
    assert closing["terminal_reason"] == CONTEXT_OVERFLOW


# -- the route's own count is what decides ------------------------------------


def _pruned_parts(publisher: RecordingPublisher) -> list[Mapping[str, Any]]:
    return only(publisher, ProgressKind.CONTEXT_PRUNED)


@pytest.mark.asyncio
async def test_only_what_the_route_charged_decides_whether_ground_is_given() -> None:
    """Two Turns, one script, one transcript, one ceiling; two bills.

    The characters are identical in both runs, so a loop deciding on characters
    decides identically in both — and one of the two would then send a request
    the route is about to refuse. What separates them here is the number the
    route returned for the call before, which is the whole of this gate: the
    estimate is a preflight guess and stops being consulted the moment a real
    count exists.
    """
    request = turn_request(history=long_history())
    ceiling = ContextBudget(max_tokens=12_000)

    async def run(charged: int) -> RecordingPublisher:
        publisher = RecordingPublisher()
        client = FakeClient(
            [
                Completion(
                    model="gpt-5.6-luna",
                    text="Đang tra.",
                    tool_calls=(
                        ToolCall(
                            id="c1", name="web_search", arguments={"query": "lãi suất"}
                        ),
                    ),
                    usage=Usage(input_tokens=charged, output_tokens=5),
                ),
                Completion(
                    model="gpt-5.6-luna",
                    text="Xong.",
                    usage=Usage(input_tokens=charged, output_tokens=5),
                ),
            ]
        )
        await loop(client, publisher=publisher, budget=ceiling).run(request)
        return publisher

    # Roughly what the characters said, and twice it.
    honest = _pruned_parts(await run(9_800))
    doubled = _pruned_parts(await run(19_600))

    assert honest == []
    assert doubled
    assert doubled[-1]["turns_dropped"] > 0
    # And the ceiling was met against the route's number, not the estimate: the
    # projection is inside it while the characters alone are not.
    for part in doubled:
        assert part["projected"] <= ceiling.max_tokens


# -- a page read once is not read again --------------------------------------


THREAD_PAGE = "https://news.example/rates"
PAGE_HTML = (
    "<html><head><title>Rates hold</title></head>"
    "<body><p>Lãi suất điều hành giữ nguyên ở 4,5%.</p></body></html>"
)


class EvictingLane:
    """A cache that answers the first read of a URL and has lost it by the next.

    What Redis looks like a day later, or on a deployment that has none. It is
    the condition the whole path exists for: without it the second Turn would be
    served by the cache and the record would never be asked.
    """

    def __init__(self) -> None:
        self.served: list[str] = []

    def read(self, _kind: str, key: str, fetch: Any) -> Any:
        from src.core.web_lane import WebRead, WebUnavailable

        if key in self.served:
            raise WebUnavailable("the cache no longer holds this key")
        self.served.append(key)
        return WebRead(fetch(), 0.0, 0.0, False)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def reader():
    email = f"context-engine-{uuid.uuid4().hex}@example.com"
    with get_sync_db() as session:
        user = User(email=email, hashed_password="x")
        session.add(user)
        session.flush()
        user_id = user.id
    yield user_id
    with get_sync_db() as session:
        session.execute(delete(AgentThread).where(AgentThread.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))


def _reads(url: str) -> Completion:
    return Completion(
        model="gpt-5.6-luna",
        tool_calls=(ToolCall(id=f"read_{uuid.uuid4().hex[:6]}", name="fetch_url", arguments={"url": url}),),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def _served_page(outcome: Any) -> Mapping[str, Any]:
    (call,) = [item for item in outcome.tool_calls if item.name == "fetch_url"]
    return json.loads(call.result_text)


@pytest.mark.asyncio
async def test_a_page_one_turn_read_is_reused_by_the_next_with_no_request(
    reader: int,
) -> None:
    """The gate this phase's evidence work exists for, end to end.

    Two real Turns of one Thread, the real ``fetch_url``, the real store, and a
    cache that has forgotten the page in between. The second Turn must answer
    from the Thread's own trace: no download, and the instant of the *first*
    read still attached to the content — a page re-served under today's
    timestamp would be this system telling a reader that yesterday's figure is
    current.
    """
    downloads: list[str] = []

    def download(url: str, max_bytes: int, timeout: float):
        downloads.append(url)
        return 200, {"content-type": "text/html"}, PAGE_HTML.encode("utf-8")

    store = AgentPersistence(session_factory=sync_session_factory)
    thread = await store.create_thread(reader)

    async def turn(question: str) -> Any:
        message = await store.append_message(
            thread.id, role="user", content={"text": question}
        )
        client = FakeClient([_reads(THREAD_PAGE), Completion(model="gpt-5.6-luna", text="Xong.")])
        return await AgentLoop(
            client=client,
            config=config(),
            toolsets=("web",),
            trace=store.record_tool_call,
            clock=lambda: datetime(2026, 8, 22, tzinfo=timezone.utc),
        ).run(
            TurnRequest(
                thread_id=str(thread.id),
                request_message_id=message.id,
                user_id=reader,
                user_text=question,
                runtime=RuntimeContext(today=date(2026, 8, 22), user_name="Ty"),
            )
        )

    with isolated_registry():
        web.register_web_tools(
            settings=settings(),
            lane=EvictingLane(),
            download=download,
            resolver=resolver_for("93.184.216.34"),
        )
        first = await turn("Lãi suất điều hành đang bao nhiêu?")
        second = await turn("Nguồn của con số đó là trang nào?")

    read_once = _served_page(first)
    read_again = _served_page(second)

    # One download for two Turns that both read the page.
    assert downloads == [THREAD_PAGE]
    assert read_once["from_record"] is False
    assert read_again["from_record"] is True
    assert read_again["retrieved_at"] == read_once["retrieved_at"]
    assert "4,5%" in read_again["content"]


# -- the summary, and the two ends of it that have to agree ------------------


def _turns_of(count: int) -> tuple[TranscriptTurn, ...]:
    return tuple(
        TranscriptTurn(
            user_text=f"Câu hỏi số {index} " + "x" * 200,
            assistant_text=f"Trả lời số {index} " + "z" * 200,
        )
        for index in range(count)
    )


def test_a_span_the_specialist_would_write_never_reaches_the_protected_tail() -> None:
    """The producer's span and the consumer's protection, checked against each
    other.

    Each side is tested on its own elsewhere. What neither can say alone is that
    they agree: ``plan_compaction`` counts Turns off message rows and
    ``build_messages`` counts them off a transcript, and a summary claiming one
    Turn more than it should would be a question the next reader asks that the
    context can no longer answer.
    """
    budget = ContextBudget()
    for count in range(budget.keep_intact_turns + 1, 12):
        plan = plan_compaction(
            conversation(count),
            keep_intact_turns=budget.keep_intact_turns,
            previous=None,
        )
        assert plan is not None
        live = _turns_of(count)[plan.summarised_turns :]

        assert len(live) >= budget.keep_intact_turns
        context = build_messages(
            Transcript(
                system_prompt="p",
                turns=_turns_of(count),
                summary="Bối cảnh trước đó.",
                summarised_turns=plan.summarised_turns,
            ),
            ContextBudget(max_tokens=1_000_000),
        )
        prose = "".join(message.content or "" for message in context.messages)
        for index in range(count - budget.keep_intact_turns, count):
            assert f"Câu hỏi số {index}" in prose


@pytest.mark.parametrize(
    "script",
    [
        [RuntimeError("the route fell over")],
        [Completion(model="batch-model", text="")],
        [Completion(model="batch-model", text="   ")],
    ],
    ids=["provider_error", "empty_reply", "blank_reply"],
)
@pytest.mark.asyncio
async def test_no_failed_summary_changes_a_byte_of_the_next_turns_context(
    script: list[Any],
) -> None:
    """Fail-open, stated as the only thing that makes it worth having.

    Not "the next Turn still works" — that is weak enough to pass on a context
    that quietly lost a Turn. The next Turn's messages must be the *same bytes*
    they were before the specialist was asked, because the promise this module
    is allowed to make is that a summary can only ever be an improvement.
    """
    store = FakeStore(conversation(6))
    before = constructed(store.messages)[1].messages

    written = await compactor(FakeClient(script), store).compact(
        thread_id=uuid.UUID("22222222-2222-2222-2222-222222222222"), user_id=7
    )

    assert written is None
    assert store.writes == []
    assert constructed(store.messages)[1].messages == before


def test_no_pass_is_ever_built_larger_than_the_ceiling_it_is_admitted_under() -> None:
    """A compaction the ledger refuses is the quietest failure this system has.

    It writes nothing, raises nothing at its caller, and leaves a thread that is
    never compacted — so the size of the call is decided here, against the same
    constant admission decides with, rather than discovered by being refused.
    """
    for count in (4, 12, 40):
        for words in (6, 600, 4_000):
            plan = plan_compaction(
                conversation(count, words=words), keep_intact_turns=2, previous=None
            )
            if plan is None:
                continue
            assert _estimated_input_tokens(plan.body) <= COMPACTION_INPUT_TOKENS


def test_a_summary_too_long_to_carry_is_abridged_rather_than_abandoned() -> None:
    """The one piece of prose this module did not write is the one that gives way.

    A summary row is read back from the store, so its length is not this
    module's to guarantee. Faced with one that would not fit beside the Turn it
    has to carry, the pass narrows what it *reads* and never what it *claims*:
    the span still ends where the last Turn it was given ends.
    """
    messages = conversation(4, words=2_000)
    enormous = SummaryRecord(
        message_id=99,
        seq=0,
        text="cũ " * 40_000,
        covers_from_seq=1,
        covers_to_seq=2,
        summarised_turns=1,
    )

    plan = plan_compaction(messages, keep_intact_turns=2, previous=enormous)

    assert plan is not None
    assert _estimated_input_tokens(plan.body) <= COMPACTION_INPUT_TOKENS
    # It still reads the Turn it says it covers, and the anchor still moves.
    assert plan.summarised_turns == 2
    assert plan.covers_to_seq == 4
    assert plan.covers_from_seq == enormous.covers_from_seq
    assert "Câu hỏi số 1" in plan.body
    # And it is the head that was cut, not the Turn.
    assert plan.body.count("cũ") < 40_000


def test_the_preferred_reading_budget_is_under_the_ceiling_it_is_bounded_by() -> None:
    """Two numbers, and the smaller one has to be the chosen one.

    If the budget a pass aims for ever rose above the ceiling it is admitted
    under, every long thread would be cut by a refusal instead of by a decision.
    """
    assert _estimated_input_tokens("x" * MAX_SOURCE_CHARS) <= COMPACTION_INPUT_TOKENS


# -- one pack, two prompts ---------------------------------------------------


ABOUT_THE_ASSISTANT = "Bạn là ai và bạn hoạt động thế nào?"
ABOUT_THE_MARKET = "VCB có gì mới trong quý này?"


async def _head_of(question: str) -> tuple[str, str]:
    """The system message and the cache identity one question produces."""
    client = FakeClient([Completion(model="gpt-5.6-luna", text="Xong.")])
    await loop(client).run(turn_request(user_text=question))
    request = client.requests[0]
    return str(request.messages[0].content or ""), str(
        request.metadata.get("cache_identity") or ""
    )


@pytest.mark.asyncio
async def test_the_two_prompts_one_pack_produces_are_told_apart_by_their_key() -> None:
    """The key names the prompt that went out, not the pack it came from.

    Prompt caching is off today and the key never reaches the route, so nothing
    here is load-bearing yet — which is exactly why it is worth pinning now. A
    key shared by two different prefixes is a wrong cache hit on the day the
    flag is turned on, and by then the two Turns look identical in every record.
    """
    with_body, keyed_with = await _head_of(ABOUT_THE_MARKET)
    without_body, keyed_without = await _head_of(ABOUT_THE_ASSISTANT)

    assert len(with_body) > len(without_body)
    assert keyed_with != keyed_without
    # The difference is the shape of the prompt and nothing about the question.
    for leak in ("VCB", "Bạn là ai", "Ty", "2026-08-22"):
        assert leak not in keyed_with and leak not in keyed_without


@pytest.mark.asyncio
async def test_the_prompt_the_two_share_is_shared_byte_for_byte() -> None:
    """The cacheable head is a prefix, so the shorter prompt has to be one.

    A Turn that goes without the playbook still opens with the same core as a
    Turn that carries it, which is what makes the decision free: a route caching
    by prefix keeps its hit on both.
    """
    with_body, _ = await _head_of(ABOUT_THE_MARKET)
    without_body, _ = await _head_of(ABOUT_THE_ASSISTANT)

    shared = os.path.commonprefix([with_body, without_body])

    assert len(shared) >= len(prompt_prefix())
    assert shared.startswith(prompt_prefix())
