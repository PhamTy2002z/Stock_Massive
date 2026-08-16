"""Where a Widget is released inside a Turn, and what a rejection costs (#89).

``docs/adr/0012`` fixes an ordering — validate, checkpoint, *then* announce —
and a degradation — a rejected selection leaves the text answer complete. Both
are properties of the loop rather than of the validator, so both are tested
here, against the real publisher and the real Tool Catalog.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.agent.events import Activity, TurnPublisher
from src.agent.loop import AgentLoop, TurnRequest, TurnStatus
from src.agent.prompt import MarketState, RuntimeContext
from src.agent.tools.catalog import ToolCatalog, ToolContext, ToolSpec
from src.core.llm import Completion, ToolCall, Usage, Workload
from src.core.llm.config import (
    BudgetLanes,
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
)
from types import MappingProxyType

SESSION_MODEL = "gpt-5.6-luna"
TRADING_DAY = date(2026, 8, 14)
TURN = uuid.UUID("11111111-2222-3333-4444-555555555555")


def config() -> LLMConfig:
    prices = TokenPrices(input=1.0, cached_input=0.5, cache_write=1.5, output=8.0)
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://route.example", api_key="k"),
        models=MappingProxyType(
            {Workload.BATCH: "gpt-5.6-terra", Workload.SESSION: SESSION_MODEL}
        ),
        pricing=PricingTable(
            version="2026-08", effective_from=None, batch=prices, session=prices
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=100.0,
            analysis_usd=40.0,
            turn_usd=40.0,
            emergency_usd=10.0,
            eval_usd=10.0,
        ),
    )


class ScriptedClient:
    def __init__(self, script) -> None:
        self.script = list(script)

    async def complete(self, request, spend=None):
        return self.script.pop(0)


class RecordingPublisher(TurnPublisher):
    """The real publisher, with an ordered log of what it was asked to emit."""

    def __init__(self, log: list) -> None:
        super().__init__(TURN)
        self.log = log

    def widget_ready(self, widget):
        self.log.append(("widget.ready", widget["name"]))
        return super().widget_ready(widget)

    def content_block(self, block):
        self.log.append(("content.block", block["text"][:12]))
        return super().content_block(block)

    def activity(self, activity):
        self.log.append(("turn.activity", activity.value))
        return super().activity(activity)


async def screen(_context: ToolContext, _arguments: dict) -> dict:
    return {
        "matched_count": 2,
        "returned_count": 2,
        "truncated": False,
        "sort_by": "adtv_vnd",
        "order": "desc",
        "as_of": TRADING_DAY.isoformat(),
        "symbols": [{"symbol": "FPT"}, {"symbol": "VCB"}],
    }


async def price_series(_context: ToolContext, _arguments: dict) -> dict:
    return {
        "symbol": "FPT",
        "summary": {"sessions": 3},
        "sample": [],
        "data_ref": {
            "id": "ref-1",
            "symbol": "FPT",
            "start": "2026-08-12",
            "end": TRADING_DAY.isoformat(),
            "field": "ohlcv",
        },
    }


def _empty_schema() -> dict:
    return {"type": "object", "properties": {}, "additionalProperties": False}


def catalog() -> ToolCatalog:
    return ToolCatalog(
        (
            ToolSpec(
                name="screen_universe",
                description="Filter and rank Universe symbols.",
                parameters=_empty_schema(),
                callable=screen,
            ),
            ToolSpec(
                name="get_price_series",
                description="Summarize stored daily OHLCV.",
                parameters=_empty_schema(),
                callable=price_series,
            ),
        ),
        trace_writer=lambda _trace: None,
    )


def wants_screen() -> Completion:
    return Completion(
        model=SESSION_MODEL,
        tool_calls=(
            ToolCall(id="s1", name="screen_universe", arguments={}, output_index=0),
            ToolCall(id="p1", name="get_price_series", arguments={}, output_index=1),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def answers(text: str) -> Completion:
    return Completion(
        model=SESSION_MODEL, text=text, usage=Usage(input_tokens=10, output_tokens=5)
    )


def request(user_text: str = "Lọc giúp tôi các mã thanh khoản nhất.") -> TurnRequest:
    return TurnRequest(
        thread_id="11111111-1111-1111-1111-111111111111",
        request_message_id=42,
        user_id=7,
        user_text=user_text,
        runtime=RuntimeContext(
            user_id=7,
            trading_day=TRADING_DAY,
            market_state=MarketState.POST_CLOSE,
        ),
    )


async def run(answer_text: str, *, user_text: str | None = None):
    """One Turn that screens, then answers with the given text.

    Returns the outcome, the ordered emission log, and the checkpoints taken.
    """
    log: list = []
    checkpoints: list = []
    published = RecordingPublisher(log)

    def checkpoint(draft):
        log.append(("checkpoint", tuple(w.name for w in draft.widgets)))
        checkpoints.append(draft)

    agent = AgentLoop(
        client=ScriptedClient([wants_screen(), answers(answer_text)]),
        catalog=catalog(),
        config=config(),
        checkpoint=checkpoint,
        publisher=published,
    )
    outcome = await agent.run(
        request(user_text) if user_text else request()
    )
    return outcome, log, checkpoints, published


VALID = "[widget:ranked_symbols|s1#symbols|Thanh khoản dẫn đầu]"


@pytest.mark.asyncio
async def test_a_widget_is_announced_only_after_it_is_validated_and_checkpointed():
    outcome, log, _checkpoints, published = await run(
        f"Hai mã dẫn đầu thanh khoản.\n\n{VALID}"
    )

    assert outcome.status is TurnStatus.COMPLETE
    assert [spec.name for spec in outcome.widgets] == ["ranked_symbols"]

    announced = log.index(("widget.ready", "ranked_symbols"))
    # The last checkpoint before the announcement already carries the spec, so
    # a subscriber that reconnects on the event finds it rather than racing it.
    carrying = [
        index
        for index, entry in enumerate(log)
        if entry == ("checkpoint", ("ranked_symbols",))
    ]
    assert carrying and min(carrying) < announced
    # And the text was released first, so the transcript never reorders itself.
    assert log.index(("content.block", "Hai mã dẫn đ")) < announced


@pytest.mark.asyncio
async def test_preparing_a_visual_is_the_only_thing_the_activity_line_says():
    _outcome, log, _checkpoints, _published = await run(
        f"Hai mã dẫn đầu thanh khoản.\n\n{VALID}"
    )
    phases = [entry[1] for entry in log if entry[0] == "turn.activity"]

    assert Activity.PREPARING_VISUAL.value in phases
    # No Widget name, no field, no symbol: the phase is generic by construction,
    # because ``Activity`` is a closed enum.
    assert set(phases) <= {activity.value for activity in Activity}


@pytest.mark.asyncio
async def test_a_rejected_selection_leaves_the_text_answer_complete_and_unmarked():
    outcome, log, _checkpoints, _published = await run(
        "Hai mã dẫn đầu thanh khoản.\n\n[widget:candlestick|s1#symbols|Nến FPT]"
    )

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.widgets == ()
    assert ("widget.ready", "candlestick") not in log
    assert not any(entry[0] == "widget.ready" for entry in log)
    # The answer survives whole, and carries no trace of the marker.
    assert [block.text for block in outcome.blocks] == ["Hai mã dẫn đầu thanh khoản."]


@pytest.mark.asyncio
async def test_a_second_widget_is_dropped_unless_the_user_asked_for_two():
    outcome, _log, _checkpoints, _published = await run(
        f"Hai mã dẫn đầu thanh khoản.\n\n{VALID}\n{VALID}"
    )

    assert len(outcome.widgets) == 1

    asked, _log, _checkpoints, _published = await run(
        f"Hai mã dẫn đầu thanh khoản.\n\n{VALID}\n{VALID}",
        user_text="Cho tôi hai biểu đồ: thanh khoản và động lượng.",
    )

    assert len(asked.widgets) == 2


@pytest.mark.asyncio
async def test_a_chart_stock_360_owns_is_refused_and_deep_linked_instead():
    outcome, log, _checkpoints, _published = await run(
        "Giá FPT trong ba phiên.\n\n[widget:metric_trend|p1#data_ref|Giá FPT]"
    )

    assert outcome.widgets == ()
    assert not any(entry[0] == "widget.ready" for entry in log)
    assert [refusal["deep_link"] for refusal in outcome.widget_refusals] == [
        "/analytics/deep-dive?symbol=FPT"
    ]
    assert [block.text for block in outcome.blocks] == ["Giá FPT trong ba phiên."]


@pytest.mark.asyncio
async def test_a_rejection_with_nowhere_better_to_send_the_reader_is_silent():
    outcome, log, _checkpoints, _published = await run(
        "Hai mã dẫn đầu thanh khoản.\n\n[widget:metric_trend|s1#symbols|Sai ràng buộc]"
    )

    assert outcome.widgets == ()
    # No deep link, so nothing is recorded on the message at all: a broken box
    # teaches the reader nothing about a picture they never asked for.
    assert outcome.widget_refusals == ()
    assert not any(entry[0] == "widget.ready" for entry in log)


@pytest.mark.asyncio
async def test_the_stored_message_carries_the_descriptor_and_not_the_rows():
    outcome, _log, _checkpoints, _published = await run(
        f"Hai mã dẫn đầu thanh khoản.\n\n{VALID}"
    )
    stored = outcome.widgets[0].as_wire()

    assert stored["descriptor"]["kind"] == "ranking"
    assert "symbols" not in stored["descriptor"]
    assert "rows" not in stored
    # The whole spec is small enough to live beside a message forever, which is
    # the argument for a descriptor over the series.
    assert set(stored) == {
        "name",
        "version",
        "title",
        "fields",
        "unit",
        "as_of",
        "descriptor",
        "descriptor_id",
        "tool_call_ids",
    }
