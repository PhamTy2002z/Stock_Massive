"""Widget selection, server-side validation, and data_ref replay (#89).

``docs/adr/0012`` puts validation on both sides of persistence. This file is the
first side: what the backend refuses to store, and what a stored descriptor
resolves back to.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.agent.context import TranscriptToolCall
from src.agent.grounding import TraceIndex
from src.agent.prompt import PROMPT_VERSION, MarketState, RuntimeContext, render
from src.agent.tools.fields import serialize_registered_field
from src.agent.widgets import (
    WIDGET_REGISTRY,
    BindingKind,
    WidgetDataResolver,
    WidgetRejected,
    WidgetValidator,
    descriptor_id,
    extract_selections,
    user_requested_multiple,
    user_requested_visual,
)

TRADING_DAY = date(2026, 8, 14)
MOMENTUM = "momentum_rank.percentile_12_2"
RSI = "indicator_pack.rsi_14"


def registered(name: str, value: float | None) -> dict:
    """One registered field exactly as the Tool Catalog serializes it."""
    return {
        **serialize_registered_field(name, value=value),
        "degraded_reason": None,
        "window_health": {"refusal": None, "last_session": TRADING_DAY.isoformat()},
    }


def cluster(symbol: str, *, as_of: str = TRADING_DAY.isoformat(), **fields) -> dict:
    return {
        "symbol": symbol,
        "as_of": as_of,
        "registered_fields": dict(fields),
    }


def call(call_id: str, name: str, result: dict, **arguments) -> TranscriptToolCall:
    return TranscriptToolCall(
        call_id=call_id, name=name, arguments=dict(arguments), result=result
    )


def comparison_traces() -> TraceIndex:
    return TraceIndex(
        [
            call("c1", "cross_sectional", cluster("FPT", **{MOMENTUM: registered(MOMENTUM, 82.0)}), symbol="FPT"),
            call("c2", "cross_sectional", cluster("VCB", **{MOMENTUM: registered(MOMENTUM, 41.5)}), symbol="VCB"),
        ]
    )


def selection(body: str):
    _text, selections = extract_selections(f"Kết luận.\n\n[widget:{body}]")
    assert len(selections) == 1
    return selections[0]


def validator(*, allow_second: bool = False) -> WidgetValidator:
    return WidgetValidator(trading_day=TRADING_DAY, allow_second=allow_second)


REF = f"c1#registered_fields.{MOMENTUM}.value,c2#registered_fields.{MOMENTUM}.value"


# -- the contract the selection arrives through ---------------------------


def test_the_contract_gained_its_widget_section_and_the_catalog_did_not_move():
    rendered = render(
        RuntimeContext(
            user_id=7, trading_day=TRADING_DAY, market_state=MarketState.POST_CLOSE
        )
    )

    assert PROMPT_VERSION == "1.2.0"
    assert "## 7. Visual evidence" in rendered
    for name in WIDGET_REGISTRY:
        assert name.replace("_", " ") in rendered
    # The registry is described, and the twelve-tool catalog is not touched by
    # describing it: the selection rides the output contract, not a thirteenth
    # tool, precisely so that ``tool_catalog_version`` does not move.
    assert "you name one of the visuals this system already owns" in rendered.casefold()


def test_a_selection_is_lifted_out_of_the_answer_before_it_is_split():
    text, selections = extract_selections(
        "Kết luận đầu tiên.\n\n"
        f"[widget:metric_comparison|{REF}|So sánh động lượng]\n"
    )

    assert "[widget:" not in text
    assert text.strip() == "Kết luận đầu tiên."
    assert selections[0].name == "metric_comparison"
    assert selections[0].title == "So sánh động lượng"
    assert [ref.call_id for ref in selections[0].refs] == ["c1", "c2"]


@pytest.mark.parametrize(
    "body",
    ["metric_comparison", "metric_comparison|", "metric_comparison|not-a-ref|Tiêu đề"],
)
def test_a_selection_that_does_not_parse_leaves_the_answer_readable(body: str):
    text, selections = extract_selections(f"Kết luận.\n\n[widget:{body}]")

    assert selections == ()
    assert "[widget:" not in text
    assert text.strip() == "Kết luận."


def test_a_title_cannot_impersonate_a_marker_and_is_bounded():
    parsed = selection(f"metric_comparison|{REF}|[rec:FPT@2026-08-14] " + "dài" * 200)

    assert "[" not in parsed.title and "]" not in parsed.title
    assert len(parsed.title) <= 80


# -- what validation refuses ----------------------------------------------


def test_a_valid_comparison_becomes_a_dated_descriptor_and_not_a_series():
    spec = validator().validate(selection(f"metric_comparison|{REF}|Động lượng"), comparison_traces())

    assert (spec.name, spec.version) == ("metric_comparison", 1)
    assert spec.fields == (MOMENTUM,)
    assert spec.as_of == TRADING_DAY.isoformat()
    assert spec.descriptor == {
        "kind": BindingKind.CROSS_SYMBOL.value,
        "field": MOMENTUM,
        "symbols": ["FPT", "VCB"],
        "as_of": TRADING_DAY.isoformat(),
    }
    # The point of the descriptor: no series anywhere in what is stored.
    assert "series" not in spec.as_wire()["descriptor"]
    assert spec.as_wire()["descriptor_id"] == descriptor_id(spec.descriptor)


def test_there_is_no_widgets_table_for_a_spec_to_live_in():
    from src.core.database import Base

    # ``docs/specs/0003`` §10: the names supersede an earlier draft that had one,
    # and a message stores the validated spec instead. A table would invite the
    # series in beside it.
    assert "widgets" not in Base.metadata.tables


def test_an_unknown_widget_is_rejected():
    with pytest.raises(WidgetRejected) as raised:
        validator().validate(selection(f"candlestick|{REF}|Nến"), comparison_traces())

    assert raised.value.code == "unknown_widget"


def test_an_unsupported_name_and_version_pair_is_not_reachable_from_a_selection():
    # The version is the server's, and there is no route by which the model
    # supplies one: a selection carries a name, and the registry answers with
    # the version it pins.
    assert all(
        definition.version == WIDGET_REGISTRY[name].version
        for name, definition in WIDGET_REGISTRY.items()
    )
    spec = validator().validate(selection(f"metric_comparison|{REF}|X"), comparison_traces())

    assert spec.version == WIDGET_REGISTRY["metric_comparison"].version
    assert f"{spec.name}@{spec.version}" in {
        f"{name}@{item.version}" for name, item in WIDGET_REGISTRY.items()
    }


def test_a_binding_resolving_to_another_turns_trace_is_rejected():
    other_turn = TraceIndex(
        [call("z9", "cross_sectional", cluster("FPT", **{MOMENTUM: registered(MOMENTUM, 82.0)}))]
    )

    with pytest.raises(WidgetRejected) as raised:
        validator().validate(selection(f"metric_comparison|{REF}|X"), other_turn)

    assert raised.value.code == "unresolvable_binding"


def test_an_unregistered_field_is_rejected():
    traces = TraceIndex(
        [
            call("c1", "get_company_profile", {"symbol": "FPT", "as_of": TRADING_DAY.isoformat(), "company_name": "FPT"}),
            call("c2", "get_company_profile", {"symbol": "VCB", "as_of": TRADING_DAY.isoformat(), "company_name": "VCB"}),
        ]
    )

    with pytest.raises(WidgetRejected) as raised:
        validator().validate(
            selection("metric_comparison|c1#company_name,c2#company_name|X"), traces
        )

    assert raised.value.code == "unregistered_field"


def test_a_unit_that_is_not_the_registrys_is_rejected():
    tampered = cluster("VCB", **{MOMENTUM: registered(MOMENTUM, 41.5)})
    tampered["registered_fields"][MOMENTUM]["unit"] = "vnd"
    traces = TraceIndex(
        [
            call("c1", "cross_sectional", cluster("FPT", **{MOMENTUM: registered(MOMENTUM, 82.0)})),
            call("c2", "cross_sectional", tampered),
        ]
    )

    with pytest.raises(WidgetRejected) as raised:
        validator().validate(selection(f"metric_comparison|{REF}|X"), traces)

    assert raised.value.code == "unresolvable_binding"


def test_two_dates_on_one_axis_are_rejected():
    traces = TraceIndex(
        [
            call("c1", "cross_sectional", cluster("FPT", **{MOMENTUM: registered(MOMENTUM, 82.0)})),
            call(
                "c2",
                "cross_sectional",
                cluster("VCB", as_of="2026-08-07", **{MOMENTUM: registered(MOMENTUM, 41.5)}),
            ),
        ]
    )

    with pytest.raises(WidgetRejected) as raised:
        validator().validate(selection(f"metric_comparison|{REF}|X"), traces)

    assert raised.value.code == "mixed_dates"


def test_one_field_across_symbols_and_not_two_fields():
    traces = TraceIndex(
        [
            call("c1", "cross_sectional", cluster("FPT", **{MOMENTUM: registered(MOMENTUM, 82.0)})),
            call("c2", "indicator_pack", cluster("VCB", **{RSI: registered(RSI, 61.0)})),
        ]
    )

    with pytest.raises(WidgetRejected) as raised:
        validator().validate(
            selection(
                f"metric_comparison|c1#registered_fields.{MOMENTUM}.value,"
                f"c2#registered_fields.{RSI}.value|X"
            ),
            traces,
        )

    assert raised.value.code == "mixed_fields"


# -- the one-per-answer ceiling -------------------------------------------


def test_a_second_widget_is_rejected_unless_the_user_asked_for_one():
    _text, selections = extract_selections(
        f"Kết luận.\n\n[widget:metric_comparison|{REF}|Một]\n"
        f"[widget:metric_comparison|{REF}|Hai]\n"
    )

    specs, rejections = validator().validate_all(selections, comparison_traces())

    assert len(specs) == 1
    assert [rejection.code for rejection in rejections] == ["widget_ceiling"]

    allowed, none_rejected = validator(allow_second=True).validate_all(
        selections, comparison_traces()
    )

    assert len(allowed) == 2
    assert none_rejected == ()


def test_whether_the_user_asked_for_a_picture_rides_on_the_spec():
    # ``docs/adr/0012`` makes failure asymmetric on the web side, and only the
    # backend holds the user's text, so only the backend can answer this.
    assert user_requested_visual("vẽ giúp tôi biểu đồ động lượng")
    assert user_requested_visual("plot the momentum for me")
    assert not user_requested_visual("FPT đang ở vùng nào?")

    asked = WidgetValidator(trading_day=TRADING_DAY, requested=True).validate(
        selection(f"metric_comparison|{REF}|X"), comparison_traces()
    )
    offered = validator().validate(
        selection(f"metric_comparison|{REF}|X"), comparison_traces()
    )

    assert asked.as_wire()["requested"] is True
    assert offered.as_wire()["requested"] is False


def test_the_second_widget_allowance_is_read_off_the_users_own_words():
    assert user_requested_multiple("cho tôi hai biểu đồ so sánh")
    assert user_requested_multiple("show me two charts please")
    assert not user_requested_multiple("vẽ biểu đồ so sánh FPT và VCB")
    # There is no field the model could set instead.
    assert not user_requested_multiple("")


def test_a_negation_withdraws_the_request_rather_than_matching_it():
    # Substring matching cannot tell a request from a refusal, and of the two
    # readings the expensive one is treating a refusal as a request.
    assert not user_requested_visual("đừng vẽ biểu đồ, chỉ cần chữ")
    assert not user_requested_visual("không cần chart")
    assert not user_requested_multiple("đừng cho tôi hai biểu đồ")
    assert not user_requested_visual("answer without a chart")


def test_a_slice_dated_past_the_turn_is_refused():
    tomorrow = TraceIndex(
        [
            call("c1", "cross_sectional", cluster("FPT", as_of="2026-08-15", **{MOMENTUM: registered(MOMENTUM, 82.0)})),
            call("c2", "cross_sectional", cluster("VCB", as_of="2026-08-15", **{MOMENTUM: registered(MOMENTUM, 41.5)})),
        ]
    )

    with pytest.raises(WidgetRejected) as raised:
        validator().validate(selection(f"metric_comparison|{REF}|X"), tomorrow)

    assert raised.value.code == "future_slice"


# -- what Stock 360 already owns -------------------------------------------


def price_series_traces() -> TraceIndex:
    return TraceIndex(
        [
            call(
                "p1",
                "get_price_series",
                {
                    "symbol": "FPT",
                    "summary": {"sessions": 3},
                    "sample": [],
                    "data_ref": {
                        "id": "abc",
                        "symbol": "FPT",
                        "start": "2026-08-01",
                        "end": TRADING_DAY.isoformat(),
                        "field": "ohlcv",
                    },
                },
            )
        ]
    )


@pytest.mark.parametrize("path", ["data_ref", "sample", "summary.sessions"])
def test_a_chart_stock_360_owns_is_refused_with_a_deep_link(path: str):
    with pytest.raises(WidgetRejected) as raised:
        validator().validate(selection(f"metric_trend|p1#{path}|Giá FPT"), price_series_traces())

    assert raised.value.code == "owned_by_stock_360"
    assert raised.value.deep_link == "/analytics/deep-dive?symbol=FPT"


def test_only_a_deep_linked_refusal_is_worth_showing_the_reader():
    refused = WidgetRejected("unknown_widget", "no", deep_link=None)
    linked = WidgetRejected("owned_by_stock_360", "no", deep_link="/analytics/deep-dive")

    assert refused.deep_link is None
    assert linked.as_wire() == {
        "code": "owned_by_stock_360",
        "deep_link": "/analytics/deep-dive",
    }


# -- ranked symbols, which replays a question rather than an answer --------


def screen_traces() -> TraceIndex:
    return TraceIndex(
        [
            call(
                "s1",
                "screen_universe",
                {
                    "matched_count": 30,
                    "returned_count": 2,
                    "truncated": True,
                    "sort_by": "adtv_vnd",
                    "order": "desc",
                    "as_of": TRADING_DAY.isoformat(),
                    "symbols": [{"symbol": "FPT"}, {"symbol": "VCB"}],
                },
                criteria={"min_adtv_vnd": 1_000},
                sort_by="adtv_vnd",
                order="desc",
                limit=10,
            )
        ]
    )


def test_a_ranking_stores_the_screen_rather_than_its_rows():
    spec = validator().validate(selection("ranked_symbols|s1#symbols|Thanh khoản"), screen_traces())

    assert spec.descriptor == {
        "kind": BindingKind.RANKING.value,
        "criteria": {"min_adtv_vnd": 1_000},
        "sort_by": "adtv_vnd",
        "order": "desc",
        "limit": 10,
        "as_of": TRADING_DAY.isoformat(),
    }
    assert "symbols" not in spec.descriptor or spec.descriptor["symbols"] == []


def test_a_ranking_bound_to_something_other_than_a_screen_is_rejected():
    with pytest.raises(WidgetRejected) as raised:
        validator().validate(
            selection(f"ranked_symbols|c1#registered_fields.{MOMENTUM}.value|X"),
            comparison_traces(),
        )

    assert raised.value.code == "wrong_binding"


# -- replay ----------------------------------------------------------------


class _Tools:
    """The two store seams a resolver reaches through, and a call counter."""

    def __init__(self, *, points=None, rows=None) -> None:
        self.points = points
        self.rows = rows
        self.field_calls: list[tuple] = []
        self.screen_calls: list[dict] = []

    async def replay_field(self, *, symbols, field_name, as_of):
        self.field_calls.append((tuple(symbols), field_name, as_of))
        points = self.points if self.points is not None else [
            {"symbol": symbol, "value": 10.0, "details": {}, "refusal": None}
            for symbol in symbols
        ]
        present = any(point["value"] is not None for point in points)
        return {
            "field": field_name,
            "unit": "percent",
            "as_of": as_of.isoformat(),
            "points": points,
            "available": present,
            "unavailable_reason": None if present else "slice_unavailable",
        }

    async def replay_screen(self, *, criteria, sort_by, order, limit, as_of):
        self.screen_calls.append({"sort_by": sort_by, "as_of": as_of})
        return {
            "symbols": self.rows if self.rows is not None else [{"symbol": "FPT"}],
            "sort_by": sort_by,
            "order": order,
            "matched_count": 30,
        }


class _Redis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value


@pytest.mark.asyncio
async def test_a_descriptor_resolves_from_the_cache_and_rebuilds_after_it_expires():
    tools = _Tools()
    redis = _Redis()
    resolver = WidgetDataResolver(tools=tools, redis=redis)
    descriptor = {
        "kind": BindingKind.CROSS_SYMBOL.value,
        "field": MOMENTUM,
        "symbols": ["FPT", "VCB"],
        "as_of": TRADING_DAY.isoformat(),
    }

    first = await resolver.resolve(descriptor)
    cached = await resolver.resolve(descriptor)
    redis.store.clear()
    rebuilt = await resolver.resolve(descriptor)

    assert first == cached == rebuilt
    # One reconstruction per cache miss, and none for the hit in between.
    assert len(tools.field_calls) == 2
    assert tools.field_calls[0] == (("FPT", "VCB"), MOMENTUM, TRADING_DAY)


@pytest.mark.asyncio
async def test_reopening_resolves_the_day_the_descriptor_carries_and_never_today():
    tools = _Tools()
    resolver = WidgetDataResolver(tools=tools, redis=None)
    descriptor = {
        "kind": BindingKind.CROSS_SYMBOL.value,
        "field": MOMENTUM,
        "symbols": ["FPT"],
        "as_of": "2025-01-06",
    }

    resolved = await resolver.resolve(descriptor)

    assert resolved["as_of"] == "2025-01-06"
    assert tools.field_calls[0][2] == date(2025, 1, 6)


@pytest.mark.asyncio
async def test_a_slice_that_cannot_be_rebuilt_resolves_to_an_explicit_unavailable_state():
    tools = _Tools(points=[{"symbol": "FPT", "value": None, "details": {}, "refusal": "window_too_short"}])
    resolver = WidgetDataResolver(tools=tools, redis=None)

    resolved = await resolver.resolve(
        {
            "kind": BindingKind.CROSS_SYMBOL.value,
            "field": MOMENTUM,
            "symbols": ["FPT"],
            "as_of": TRADING_DAY.isoformat(),
        }
    )

    assert resolved["available"] is False
    assert resolved["unavailable_reason"] == "slice_unavailable"
    # Still dated: a reader told a slice is missing is told which slice.
    assert resolved["as_of"] == TRADING_DAY.isoformat()


@pytest.mark.asyncio
async def test_a_store_that_raises_becomes_the_unavailable_state_rather_than_an_error():
    class _Broken(_Tools):
        async def replay_field(self, **_kwargs):
            raise RuntimeError("the snapshot table is gone")

    resolver = WidgetDataResolver(tools=_Broken(), redis=None)

    resolved = await resolver.resolve(
        {
            "kind": BindingKind.CROSS_SYMBOL.value,
            "field": MOMENTUM,
            "symbols": ["FPT"],
            "as_of": TRADING_DAY.isoformat(),
        }
    )

    assert resolved["available"] is False


@pytest.mark.asyncio
async def test_a_series_descriptor_is_named_into_one_column_before_it_is_returned():
    class _Series(_Tools):
        async def resolve_data_ref(self, reference):
            return {
                **dict(reference),
                "series": [
                    {"date": "2026-08-13", "close_price": 95_400, "volume": 1},
                    {"date": "2026-08-14", "close_price": 96_100, "volume": 2},
                ],
                "available": True,
                "unavailable_reason": None,
            }

    resolver = WidgetDataResolver(tools=_Series(), redis=None)

    resolved = await resolver.resolve(
        {
            "kind": BindingKind.SERIES.value,
            "as_of": TRADING_DAY.isoformat(),
            "data_ref": {
                "id": "ref-1",
                "symbol": "FPT",
                "start": "2026-08-13",
                "end": TRADING_DAY.isoformat(),
                "field": "ohlcv",
            },
        }
    )

    # A Data Reference is a store shape with five columns; a trend takes one
    # series, and which column that is stays the server's decision.
    assert resolved["series"] == [
        {"date": "2026-08-13", "value": 95_400},
        {"date": "2026-08-14", "value": 96_100},
    ]
    assert resolved["unit"] == "vnd"
    assert resolved["available"] is True


@pytest.mark.asyncio
async def test_a_ranking_descriptor_replays_the_screen_at_its_own_day():
    tools = _Tools(rows=[{"symbol": "FPT"}, {"symbol": "VCB"}])
    resolver = WidgetDataResolver(tools=tools, redis=None)

    resolved = await resolver.resolve(
        {
            "kind": BindingKind.RANKING.value,
            "criteria": {},
            "sort_by": "adtv_vnd",
            "order": "desc",
            "limit": 10,
            "as_of": TRADING_DAY.isoformat(),
        }
    )

    assert resolved["available"] is True
    assert [row["symbol"] for row in resolved["rows"]] == ["FPT", "VCB"]
    assert tools.screen_calls[0]["as_of"] == TRADING_DAY
