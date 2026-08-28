"""The Signal Desk mode: a switch the backend keeps rather than a layout.

One property is asserted here from every angle it can fail at. A Turn asked with
``mode="signal_desk"`` ends in exactly one of two states — a Signal Desk was
announced, or the completion carries a named code saying why none could be. An
ordinary answer with nothing said about the picture is the failure, and it is
the failure precisely because it looks fine: the reader threw a switch and the
surface has nothing to show for it.

The codes are the ones the rest of the harness already writes. A Study that
refused for data reasons reports its **Signal Issue** through the same
``outcome`` the Tool Call Trace stores; a call that never ran reports the
executor's own error code; only "the model never reached for a picture" needed a
name of its own.

Built on ``test_agent_loop``'s scaffolding — the same fake route, the same stub
registry — because what changes under this mode is the loop's behaviour and
nothing about how a tool is declared.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.agent import registry
from src.agent.executor import TOOL_FAILED
from src.agent.loop import (
    NO_SIGNAL_DESK_TOOL_CALLED,
    SIGNAL_DESK_MODE,
    SIGNAL_DESK_NOTE,
    TOOL_TIMEOUT,
    ToolCallStatus,
    TurnStatus,
)
from src.core.llm import Completion, ToolCall, Usage

from .agent_tool_world import isolated_registry
from .test_agent_loop import (
    SESSION_MODEL,
    FakeClient,
    RecordingPublisher,
    answer,
    entry,
    install,
    loop,
    turn_request,
)

#: The id the stub Study hands back. Any UUID does: the loop never opens the row.
ARTIFACT = "3f7c1f0e-0000-4000-8000-000000000001"


class DeskPublisher(RecordingPublisher):
    """The recording publisher, plus the announcement Studies added.

    Its own subclass rather than a change to the shared one: ``signal_desk_ready`` is
    reached through ``getattr`` precisely so a transport that predates Studies
    still streams a Turn, and the shared double is what proves that.
    """

    def __init__(self) -> None:
        super().__init__()
        self.signal_desks: list[dict[str, Any]] = []

    def signal_desk_ready(self, payload) -> None:
        self.signal_desks.append(dict(payload))
        self.order.append(("signal_desk", dict(payload)))


def a_signal_desk(_context, _arguments) -> Any:
    """What ``run_study`` answers with when it drew something."""
    return {
        "studyName": "intraday_liquidity",
        "studyVersion": 1,
        "artifactId": ARTIFACT,
        "title": "Thanh khoản trong phiên",
        "blockCount": 1,
        "headline": {"peakWindow": "14:45"},
    }


def a_refusal(_context, _arguments) -> Any:
    """What it answers with when the store was too thin to draw from."""
    return {
        "studyName": "intraday_liquidity",
        "studyVersion": 1,
        "issue": "insufficient_sessions",
        "detail": "4 closed sessions stored, 10 needed",
    }


def a_declined_question(_context, _arguments) -> Any:
    return {"error": "cannot_read", "detail": "no block could be drawn"}


def a_broken_study(_context, _arguments) -> Any:
    raise RuntimeError("the study module is unreachable")


async def never_answers(_context, _arguments) -> Any:
    await asyncio.sleep(10)


def a_study(handler) -> None:
    """Put one stub ``run_study`` in the lane's ``studies`` bundle."""
    registry.register(entry("run_study", handler, toolset="studies"), override=True)


def wants_a_study(call_id: str = "s1") -> Completion:
    return Completion(
        model=SESSION_MODEL,
        text="Để tôi vẽ.",
        tool_calls=(
            ToolCall(
                id=call_id,
                name="run_study",
                arguments={"query": "STB"},
                output_index=0,
            ),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


@pytest.fixture(autouse=True)
def _world():
    """A registry of this file's own, holding the lane's stubs and a Study.

    ``test_agent_loop``'s own fixture is not inherited by an import, so the
    world is built here as well. The production ``studies`` bundle is left
    exactly as it is and only ``run_study`` is registered into it: the two names
    beside it resolve as missing, which is what an unregistered tool already
    does everywhere else.
    """
    with isolated_registry():
        install()
        yield


def desk_request(**overrides: Any):
    return turn_request(mode=SIGNAL_DESK_MODE, **overrides)


# -- the default is untouched ------------------------------------------------


@pytest.mark.asyncio
async def test_a_turn_that_names_no_mode_is_the_turn_it_always_was() -> None:
    """Acceptance for every client written before the switch existed.

    Two things have to be true, and the second is the one a default can quietly
    break: the model is told nothing extra, and the Turn owes no account of a
    picture nobody asked for.
    """
    client = FakeClient([answer("Lãi suất quanh 5%.")])

    outcome = await loop(client).run(turn_request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.signal_desk_absence is None
    sent = client.requests[0].messages
    assert all(message.content != SIGNAL_DESK_NOTE for message in sent)


@pytest.mark.asyncio
async def test_a_chat_turn_that_drew_nothing_still_reports_nothing() -> None:
    # The account is owed by the mode, not by the absence of a Signal Desk: an
    # ordinary conversation that never wanted a picture must not grow a reason
    # for not having one.
    a_study(a_refusal)
    client = FakeClient([wants_a_study(), answer("Không đủ phiên.")])

    outcome = await loop(client).run(turn_request())

    assert outcome.signal_desks == ()
    assert outcome.signal_desk_absence is None


# -- what the mode tells the model -------------------------------------------


@pytest.mark.asyncio
async def test_the_mode_travels_on_every_call_of_the_turn() -> None:
    """Once is not enough, and that is the reason it is not ``state.note``.

    A mode holds for the whole Turn. Told only in round one, it would be three
    rounds of tool results behind by the time the answering call is made.
    """
    a_study(a_refusal)
    client = FakeClient([wants_a_study(), answer("Không đủ phiên.")])

    await loop(client).run(desk_request())

    assert len(client.requests) == 2
    for request in client.requests:
        assert any(message.content == SIGNAL_DESK_NOTE for message in request.messages)


@pytest.mark.asyncio
async def test_the_mode_asks_for_a_signal_desk_and_never_forces_one() -> None:
    """The model still decides. What changes is that it has to account for it.

    Asserted against the request rather than the prose: a mode that forced a
    tool would show up here as ``tool_choice`` naming one, and the whole design
    is that it does not.
    """
    client = FakeClient([answer("Câu này không có gì để vẽ.")])

    outcome = await loop(client).run(desk_request())

    assert client.requests[0].tool_choice == "auto"
    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.text == "Câu này không có gì để vẽ."


# -- the two ways a Signal Desk Turn may end ---------------------------------


@pytest.mark.asyncio
async def test_a_desk_turn_that_drew_a_signal_desk_owes_no_reason() -> None:
    a_study(a_signal_desk)
    publisher = DeskPublisher()
    client = FakeClient([wants_a_study(), answer("Đỉnh thanh khoản ở 14:45.")])

    outcome = await loop(client, publisher=publisher).run(desk_request())

    assert [signal_desk["artifactId"] for signal_desk in publisher.signal_desks] == [ARTIFACT]
    assert [signal_desk["artifactId"] for signal_desk in outcome.signal_desks] == [ARTIFACT]
    assert outcome.signal_desk_absence is None


@pytest.mark.asyncio
async def test_a_desk_turn_that_reached_for_no_picture_says_so() -> None:
    publisher = DeskPublisher()
    client = FakeClient([answer("Lãi suất quanh 5%.")])

    outcome = await loop(client, publisher=publisher).run(desk_request())

    # An ordinary, plausible, complete answer — and the one shape this mode must
    # never leave unaccounted for.
    assert outcome.status is TurnStatus.COMPLETE
    assert publisher.signal_desks == []
    assert outcome.signal_desk_absence == NO_SIGNAL_DESK_TOOL_CALLED


@pytest.mark.asyncio
async def test_a_study_that_refused_carries_its_own_signal_issue_up() -> None:
    """The specific issue reaches the completion, not a flat "nothing".

    ``insufficient_sessions`` and ``market_cap_absent`` are different
    operational facts with different fixes, and folding them into one word here
    would rebuild the blind spot one level up.
    """
    a_study(a_refusal)
    client = FakeClient([wants_a_study(), answer("Chưa đủ phiên để vẽ.")])

    outcome = await loop(client).run(desk_request())

    assert outcome.tool_calls[0].status is ToolCallStatus.OK
    assert outcome.signal_desk_absence == "no_value:insufficient_sessions"


@pytest.mark.asyncio
async def test_a_study_that_declined_the_question_is_told_apart_from_one_that_ran() -> None:
    a_study(a_declined_question)
    client = FakeClient([wants_a_study(), answer("Không vẽ được khối nào.")])

    outcome = await loop(client).run(desk_request())

    assert outcome.signal_desk_absence == "cannot_read"


@pytest.mark.asyncio
async def test_a_study_call_that_failed_reports_the_executors_own_code() -> None:
    a_study(a_broken_study)
    client = FakeClient([wants_a_study(), answer("Công cụ hỏng.")])

    outcome = await loop(client).run(desk_request())

    assert outcome.tool_calls[0].status is ToolCallStatus.ERROR
    # Not a code of this mode's own: the surface already holds a sentence for
    # this one, because it draws it beside the failed call itself.
    assert outcome.signal_desk_absence == outcome.tool_calls[0].error == TOOL_FAILED


@pytest.mark.asyncio
async def test_the_last_attempt_is_the_one_reported() -> None:
    """Two tries, and the reader is told about the one the model gave up on."""
    a_study(a_refusal)
    client = FakeClient(
        [
            wants_a_study("s1"),
            wants_a_study("s2"),
            answer("Chưa đủ phiên để vẽ."),
        ]
    )

    outcome = await loop(client).run(desk_request())

    assert [call.id for call in outcome.tool_calls] == ["s1", "s2"]
    assert outcome.signal_desk_absence == "no_value:insufficient_sessions"


@pytest.mark.asyncio
async def test_a_desk_turn_that_ended_badly_still_accounts_for_the_picture() -> None:
    """The paths where a missing reason is likeliest are the ones that fail.

    A Turn whose tools never answered ends ``incomplete`` under its own reason,
    and the reader who threw the switch is still owed the other half of the
    story.
    """

    a_study(never_answers)
    client = FakeClient([wants_a_study()])

    outcome = await loop(client, tool_timeout_seconds=0.02).run(desk_request())

    assert outcome.status is TurnStatus.INCOMPLETE
    assert outcome.terminal_reason == TOOL_TIMEOUT
    assert outcome.signal_desk_absence == TOOL_TIMEOUT
