"""The one question a deep Turn may ask, and every reason it may not.

Roadmap §1 gives elicitation four disciplines. Two of them are judgement the
planner makes — whether the unknown is really non-discoverable, whether the
answer really changes the conclusion — and two are arithmetic a backend can
hold: ask only after going and looking, and ask at most one round before a
memo. These tests hold the arithmetic, and they hold the rule that a refused
question is never an error: the Turn goes on and prints what it assumed.
"""

from __future__ import annotations

import json
import uuid

import pytest

from src.agent import registry
from src.agent.evidence.pipeline import (
    ELICITATION_ALREADY_ASKED,
    ELICITATION_ASKED,
    ELICITATION_MALFORMED,
    ELICITATION_NOT_PROPOSED,
    ELICITATION_NO_SCOUT,
    QuestionCandidate,
    elicitation_part,
    parse_research_draft,
)
from src.agent.lanes import DEEP
from src.agent.loop import AgentLoop, TurnStatus
from src.agent.messages import TranscriptTurn
from src.agent.parts import DEFAULT_SKIP_LABEL
from src.agent.toolsets import clear_memo

from .agent_tool_world import isolated_registry
from .test_agent_evidence_pipeline import (
    Publisher,
    PipelineClient,
    call,
    completion,
    config,
    counter_draft,
    entry,
    request,
    tools,  # noqa: F401 - the autouse registry fixture this module runs under
)

HORIZON = "Bạn giữ mã này trong bao lâu?"


@pytest.fixture
def failing_reads():
    """Every web read raises, so the Turn reaches its research pass having seen nothing."""

    async def broken(_context, _arguments):
        raise RuntimeError("route unavailable")

    async def memory(_context, _arguments):
        return {"results": []}

    with isolated_registry():
        for item in (
            entry("web_search", broken, network=True),
            entry("fetch_url", broken, network=True),
            entry("session_search", memory, network=False),
            entry("remember_fact", memory, network=False),
            entry("recall_facts", memory, network=False),
        ):
            registry.register(item)
        clear_memo()
        yield
        clear_memo()


def candidate(**overrides) -> QuestionCandidate:
    fields = {
        "prompt": HORIZON,
        "unknown": "Khung thời gian nắm giữ không có trên web.",
        "options": (
            {"id": "swing", "label": "Vài tuần", "impact": "Tập trung dòng tiền phiên."},
            {"id": "hold", "label": "Trên một năm", "impact": "Tập trung nền tảng kinh doanh."},
        ),
        "skip_label": DEFAULT_SKIP_LABEL,
        "default_assumption": "Khung thời gian trung hạn 6–12 tháng.",
    }
    fields.update(overrides)
    return QuestionCandidate(**fields)


def draft_asking(**overrides) -> str:
    """A research draft that ends by proposing a card instead of concluding."""
    return json.dumps(
        {
            "claims": [],
            "gaps": ["Chưa rõ khung thời gian của người hỏi."],
            "assumptions": [],
            "invalidations": [],
            "question": {
                "prompt": HORIZON,
                "unknown": "Khung thời gian nắm giữ không có trên web.",
                "options": [dict(item) for item in candidate(**overrides).options],
                "skip_label": DEFAULT_SKIP_LABEL,
                "default_assumption": "Khung thời gian trung hạn 6–12 tháng.",
            },
        },
        ensure_ascii=False,
    )


def new_id() -> str:
    return str(uuid.uuid4())


# --- the gate, on its own ---------------------------------------------------


def test_a_scouted_branching_question_becomes_a_single_select_card():
    part, reason = elicitation_part(
        candidate(), question_id=new_id(), scouted=True, already_asked=False
    )

    assert reason == ELICITATION_ASKED
    assert part is not None
    assert part.multi_select is False
    assert part.skip_label == DEFAULT_SKIP_LABEL
    assert part.option_ids == ("swing", "hold")
    # The impact is what the reader is shown under the label: it is the reason
    # the question is worth their tap.
    assert part.options[0].detail == "Tập trung dòng tiền phiên."


def test_a_question_asked_before_any_page_was_read_is_refused():
    """Scout-then-ask: a card raised before looking never tried to answer itself."""
    part, reason = elicitation_part(
        candidate(), question_id=new_id(), scouted=False, already_asked=False
    )

    assert part is None
    assert reason == ELICITATION_NO_SCOUT


def test_a_thread_that_already_asked_does_not_ask_again():
    """One round before a memo. The reply to a card is the next Turn, not a second card."""
    part, reason = elicitation_part(
        candidate(), question_id=new_id(), scouted=True, already_asked=True
    )

    assert part is None
    assert reason == ELICITATION_ALREADY_ASKED


def test_no_proposal_is_not_a_refusal():
    part, reason = elicitation_part(
        None, question_id=new_id(), scouted=True, already_asked=False
    )

    assert part is None
    assert reason == ELICITATION_NOT_PROPOSED


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        (
            {"options": ({"id": "only", "label": "Một lựa chọn", "impact": "x"},)},
            "one option is not a choice",
        ),
        (
            {
                "options": tuple(
                    {"id": f"o{index}", "label": f"L{index}", "impact": "x"}
                    for index in range(5)
                )
            },
            "five options is past the card's ceiling",
        ),
        (
            {
                "options": (
                    {"id": "a", "label": "A", "impact": ""},
                    {"id": "b", "label": "B", "impact": "khác"},
                )
            },
            "an option that changes nothing is a preference poll",
        ),
        (
            {
                "options": (
                    {"id": "same", "label": "A", "impact": "x"},
                    {"id": "same", "label": "B", "impact": "y"},
                )
            },
            "two options under one id make an answer ambiguous",
        ),
        ({"prompt": ""}, "a card with no question on it"),
        ({"default_assumption": ""}, "a skip that leads nowhere named"),
    ],
)
def test_a_proposal_that_is_not_a_card_is_refused(overrides, why):
    part, reason = elicitation_part(
        candidate(**overrides), question_id=new_id(), scouted=True, already_asked=False
    )

    assert part is None, why
    assert reason == ELICITATION_MALFORMED


def test_an_oversized_proposal_survives_parsing_so_the_gate_can_refuse_it():
    """The parser must not quietly cut a five-option card down to a legal four.

    Held end-to-end rather than on the gate alone: a parser that truncated would
    make every test above pass while production accepted a question the model
    never asked.
    """
    payload = json.loads(draft_asking())
    payload["question"]["options"] = [
        {"id": f"o{index}", "label": f"L{index}", "impact": f"nhánh {index}"}
        for index in range(5)
    ]
    draft = parse_research_draft(json.dumps(payload, ensure_ascii=False))

    assert draft.question is not None
    assert len(draft.question.options) == 5
    part, reason = elicitation_part(
        draft.question, question_id=new_id(), scouted=True, already_asked=False
    )
    assert part is None
    assert reason == ELICITATION_MALFORMED


# --- the gate, inside a deep Turn -------------------------------------------


class AskingClient(PipelineClient):
    """The research pass proposes a card instead of drafting claims."""

    async def complete(self, request, spend=None):
        if self.step == 2:
            self.requests.append(request)
            self.spends.append(spend)
            self.step += 1
            return completion(text=draft_asking())
        return await super().complete(request, spend)


class AskingWithoutEvidenceClient:
    """Every read failed, and the research pass still proposes a card.

    Written out rather than subclassed: with no page fetched there is no
    evidence for a verifier to check, and the passes after research are only
    here to prove the Turn reached them.
    """

    def __init__(self) -> None:
        self.step = 0

    async def complete(self, request, spend=None):
        self.step += 1
        if self.step == 1:
            return completion(
                calls=tuple(
                    call(f"plan-{index}", "web_search", query=f"HPG facet {index}")
                    for index in range(4)
                )
            )
        if self.step == 2:
            return completion(text=draft_asking())
        if self.step == 3:
            return completion(text=counter_draft())
        return completion(text=json.dumps({"claims": [], "gaps": ["Không đọc được nguồn nào."]}))


@pytest.mark.asyncio
async def test_a_deep_turn_that_earns_its_question_settles_on_the_card():
    """Asking is a terminal like answering: the Turn keeps everything it reached."""
    publisher = Publisher()

    outcome = await AgentLoop(
        client=AskingClient(),
        config=config(),
        lane=DEEP,
        publisher=publisher,
    ).run(request())

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.terminal_reason is None
    assert outcome.question is not None
    assert outcome.question["prompt"] == HORIZON
    assert outcome.question["multi_select"] is False
    assert len(outcome.question["options"]) == 2
    # What a skip will mean is written down before the reader decides, so the
    # transcript the next Turn reads carries it either way.
    assert "Khung thời gian trung hạn 6–12 tháng." in outcome.answer
    # The passes after research never ran: no ledger was verified, because
    # nothing was concluded.
    assert outcome.claim_ledger is None
    stages = [
        part["payload"]["stage"]
        for part in publisher.parts
        if part["kind"] == "pipeline_pass"
    ]
    assert stages == ["planning", "research"]
    asked = [
        part["payload"]
        for part in publisher.parts
        if part["kind"] == "pipeline_pass" and part["payload"]["stage"] == "research"
    ]
    assert asked[0]["outcome"] == "asked"


@pytest.mark.asyncio
async def test_a_thread_that_already_asked_writes_a_memo_and_says_why_it_did_not_ask():
    """A refused question is a printed assumption, never a blocked Turn."""
    publisher = Publisher()
    asked_before = request()
    asked_before = type(asked_before)(
        **{
            **asked_before.__dict__,
            "history": (
                TranscriptTurn(
                    user_text="HPG thế nào?",
                    assistant_text="Bạn giữ mã này trong bao lâu?",
                    asked=True,
                ),
            ),
        }
    )

    outcome = await AgentLoop(
        client=AskingClient(),
        config=config(),
        lane=DEEP,
        publisher=publisher,
    ).run(asked_before)

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.question is None
    # The Turn ran on to its verifier and produced a ledger, which is what a
    # refusal to ask has to cost: nothing.
    assert outcome.claim_ledger is not None
    assumptions = outcome.claim_ledger["assumptions"]
    assert any(ELICITATION_ALREADY_ASKED in item for item in assumptions)
    assert any("6–12 tháng" in item for item in assumptions)


@pytest.mark.asyncio
async def test_a_question_with_no_completed_read_behind_it_does_not_end_the_turn(
    failing_reads,
):
    """A search that errored is not a scout, so the card has nothing behind it."""
    publisher = Publisher()

    outcome = await AgentLoop(
        client=AskingWithoutEvidenceClient(),
        config=config(),
        lane=DEEP,
        publisher=publisher,
    ).run(request())

    assert outcome.question is None
    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.claim_ledger is not None
    assert any(
        ELICITATION_NO_SCOUT in item for item in outcome.claim_ledger["assumptions"]
    )
