"""The two tools that let a model ask this system what it knows.

Everything here is about a boundary rather than about arithmetic. The figures
themselves are ``alpha/envelope.py``'s and are tested there; what is under test
is who may ask for one, what they are allowed to name when they ask, and what
comes back when the store cannot answer.

*A conversation cannot reach them.* The chat lane selects two bundles and this
is not one of them, which is the whole of the boundary ``1e7b936`` drew.

*The model names a field and nothing else.* No symbol, no Trading Day, no peer
list — all three are trusted facts, and an argument for any of them is a route
to reading something this call was not opened for.

*A refusal is an answer.* A field the store cannot compute comes back with its
``reasonCode``, the sentence beside it, and a null value. That is the shape the
loop steers on: a refusal that arrived as an exception would be a dead round.

*The catalog is the map, and it is deliberately not the territory.* It carries
what a field costs in history and omits its sanctioned reading, because thirty
readings would be most of what the model reads before it has asked anything.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest

from src.agent import registry
from src.agent.executor import ToolExecutor
from src.agent.executor import ToolCall as ExecutorToolCall
from src.agent.tools.signals import (
    CATALOG_AXES,
    MAX_RESULT_CHARS,
    TOOLSET,
    SignalTools,
    axis_of,
    catalog,
    namespace_of,
)
from src.agent.toolsets import CHAT_TOOLSETS, TOOLSETS, resolve_toolset
from src.alpha.field_profile import (
    PRICE_ZONE_FIELD_ID,
    AnalysisIndustry,
    Axis,
    profile_for,
)
from src.stocks.signals.registry import REGISTRY

from .test_envelope import (
    PEERS,
    SYMBOL,
    TRADING_DAY,
    open_session,
    store_peers,
    store_window,
)

# A registered field the Analysis Field Profile has never named, and therefore
# one no Analysis has ever carried. Reaching these is what the pair exists for.
UNNAMED_FIELD = "risk_adjusted.sharpe_annualized"
# One the profile does name, so a fetched figure can be compared with a seeded
# one.
NAMED_FIELD = "indicator_pack.rsi_14"
# Deepest window in the catalog, refused against a store holding less than it.
DEEP_FIELD = "drawdown_stats.current_drawdown_pct"


def a_context(*, symbol: str = SYMBOL, day: date | None = TRADING_DAY):
    return registry.ToolContext(symbol=symbol, trading_day=day)


def tools_over(session) -> SignalTools:
    """Both tools reading one open session, which the test owns and closes."""

    class _Opener:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    return SignalTools(session_opener=_Opener)


class TestWhoMayReachThem:
    def test_the_chat_lane_does_not_select_the_signals_bundle(self):
        assert "signals" not in CHAT_TOOLSETS
        assert "list_fields" not in resolve_toolset(CHAT_TOOLSETS)
        assert "get_field" not in resolve_toolset(CHAT_TOOLSETS)

    def test_the_bundle_holds_the_two_store_reads_and_the_price_check(self):
        expected = ("list_fields", "get_field", "check_price_claim")
        assert TOOLSETS["signals"]["tools"] == expected
        assert resolve_toolset("signals") == expected

    def test_the_agent_loop_defaults_to_the_chat_selection(self):
        """Not to "every registered bundle", which would hand chat the store."""
        import inspect

        from src.agent.loop import AgentLoop

        source = inspect.getsource(AgentLoop.__init__)
        assert "CHAT_TOOLSETS if toolsets is None" in source

    def test_a_chat_selection_naming_signals_fails_at_import(self):
        from src.agent import toolsets as module

        original = module.CHAT_TOOLSETS
        module.CHAT_TOOLSETS = ("web", "memory", "signals")
        try:
            with pytest.raises(ValueError, match="Analysis lane"):
                module._check_the_chat_selection_holds()
        finally:
            module.CHAT_TOOLSETS = original

    def test_both_tools_belong_to_one_toolset(self):
        entries = tools_over(None).entries()
        assert {entry.toolset for entry in entries} == {TOOLSET}


class TestWhatTheModelMayName:
    def test_neither_schema_admits_a_symbol_a_day_or_a_peer_list(self):
        forbidden = {"symbol", "trading_day", "tradingDay", "peers", "end", "date"}
        for entry in tools_over(None).entries():
            named = set(entry.schema["properties"])
            assert not named & forbidden, entry.name

    def test_get_field_takes_one_required_argument_and_no_others(self):
        entry = next(
            item for item in tools_over(None).entries() if item.name == "get_field"
        )
        assert set(entry.schema["properties"]) == {"field_id"}
        assert entry.schema["required"] == ["field_id"]
        assert entry.schema["additionalProperties"] is False

    def test_list_fields_axis_is_optional_and_closed_to_the_four(self):
        entry = next(
            item for item in tools_over(None).entries() if item.name == "list_fields"
        )
        assert entry.schema["required"] == []
        assert entry.schema["properties"]["axis"]["enum"] == [
            axis.value for axis in Axis
        ]

    def test_a_context_naming_neither_symbol_nor_day_is_refused(self):
        tools = tools_over(None)
        with pytest.raises(ValueError, match="Trading Day"):
            tools.get_field(registry.ToolContext(user_id=3), {"field_id": NAMED_FIELD})

    def test_a_context_with_a_symbol_and_no_day_is_still_refused(self):
        tools = tools_over(None)
        with pytest.raises(ValueError, match="Trading Day"):
            tools.get_field(a_context(day=None), {"field_id": NAMED_FIELD})


class TestTheCatalog:
    def test_it_lists_every_registered_field(self):
        assert {row["fieldId"] for row in catalog()} == set(REGISTRY)

    def test_it_never_carries_a_sanctioned_reading(self):
        """Sixty percent of a figure's weight, thirty times over, for nothing."""
        for row in catalog():
            assert "interpretation" not in row
            assert "reason" not in row
            assert "value" not in row

    def test_every_row_says_what_history_the_field_costs(self):
        for row in catalog():
            assert row["minSessions"] == REGISTRY[row["fieldId"]].min_sessions
            assert row["minSessions"] >= 1

    def test_an_axis_filter_returns_that_axis_and_nothing_else(self):
        money = catalog(Axis.MONEY_FLOW)
        assert money
        assert {row["axis"] for row in money} == {"money_flow"}
        assert len(money) < len(catalog())

    def test_the_four_axes_partition_the_catalog(self):
        counted = sum(len(catalog(axis)) for axis in Axis)
        assert counted == len(catalog()) == len(REGISTRY)

    def test_the_axis_table_agrees_with_the_profile_it_cannot_derive(self):
        for industry in AnalysisIndustry:
            for axis, fields in profile_for(industry).items():
                for entry in fields:
                    if entry.field_id in REGISTRY:
                        assert axis_of(entry.field_id) is axis, entry.field_id

    def test_core_evidence_reads_on_the_technical_axis(self):
        """The profile keeps it out of a slot, which is not the same statement."""
        assert axis_of(PRICE_ZONE_FIELD_ID) is Axis.TECHNICAL
        assert PRICE_ZONE_FIELD_ID not in {
            entry.field_id
            for fields in profile_for(AnalysisIndustry.OTHER).values()
            for entry in fields
        }

    def test_every_registered_namespace_has_an_axis(self):
        assert {namespace_of(name) for name in REGISTRY} == set(CATALOG_AXES)

    def test_the_whole_catalog_fits_far_inside_the_result_cap(self):
        payload = json.dumps(list(catalog()), ensure_ascii=False)
        assert len(payload) < MAX_RESULT_CHARS // 4

    def test_it_reaches_the_fields_no_analysis_has_ever_carried(self):
        named = {
            entry.field_id
            for industry in AnalysisIndustry
            for fields in profile_for(industry).values()
            for entry in fields
        } | {PRICE_ZONE_FIELD_ID}
        unnamed = {row["fieldId"] for row in catalog()} - named
        # Sixteen of thirty, measured on the real store; the exact figure is
        # allowed to move when the profile does, the gap is not allowed to close
        # silently to nothing.
        assert UNNAMED_FIELD in unnamed
        assert len(unnamed) >= 10

    def test_an_axis_nobody_named_is_a_readable_refusal(self):
        tools = tools_over(None)
        with pytest.raises(ValueError, match="is not an axis"):
            tools.list_fields(a_context(), {"axis": "sentiment"})

    def test_an_absent_axis_is_the_whole_catalog(self):
        tools = tools_over(None)
        answered = tools.list_fields(a_context(), {})
        assert answered["axis"] is None
        assert answered["count"] == len(REGISTRY)


class TestReadingOneField:
    def test_a_field_the_profile_never_named_is_answerable(self):
        with open_session() as session:
            store_window(session)
            figure = tools_over(session).get_field(
                a_context(), {"field_id": UNNAMED_FIELD}
            )

        assert figure["fieldId"] == UNNAMED_FIELD
        assert figure["health"] in {"ok", "degraded", "refused"}
        assert figure["interpretation"]

    def test_the_wire_shape_is_the_envelope_s_own(self):
        from src.alpha.envelope import EvidenceFigure

        with open_session() as session:
            store_window(session)
            figure = tools_over(session).get_field(
                a_context(), {"field_id": NAMED_FIELD}
            )

        assert set(figure) == set(EvidenceFigure.__dataclass_fields__) - {
            "field_id",
            "reason_code",
            "as_of",
            "sessions_used",
            "window_days",
        } | {
            "fieldId",
            "reasonCode",
            "asOf",
            "sessionsUsed",
            "windowDays",
        }

    def test_a_named_field_keeps_the_label_the_profile_gave_it(self):
        with open_session() as session:
            store_window(session)
            figure = tools_over(session).get_field(
                a_context(), {"field_id": NAMED_FIELD}
            )
        assert figure["label"] == "RSI (14)"

    def test_a_field_the_profile_never_named_labels_itself_by_its_id(self):
        with open_session() as session:
            store_window(session)
            figure = tools_over(session).get_field(
                a_context(), {"field_id": UNNAMED_FIELD}
            )
        assert figure["label"] == UNNAMED_FIELD

    def test_a_refusal_carries_its_code_its_sentence_and_no_number(self):
        """The shape the loop steers on: a named reason, not an exception."""
        with open_session() as session:
            # Far less history than the deepest window declares.
            store_window(session, count=30)
            figure = tools_over(session).get_field(
                a_context(), {"field_id": DEEP_FIELD}
            )

        assert figure["health"] == "refused"
        assert figure["value"] is None
        assert figure["reasonCode"]
        assert figure["reason"] and figure["reason"] != figure["reasonCode"]
        assert figure["asOf"] is None

    def test_a_percentile_is_ranked_against_the_universe_the_backend_resolved(self):
        with open_session() as session:
            store_window(session)
            store_peers(session)
            figure = tools_over(session).get_field(
                a_context(), {"field_id": "factor_percentiles.size_percentile"}
            )

        # Ranked or refused for a named reason — never an exception, and never a
        # ranking the model chose the members of.
        assert figure["fieldId"] == "factor_percentiles.size_percentile"
        if figure["health"] != "refused":
            assert figure["extras"]["n"] >= len(PEERS)

    def test_an_unregistered_id_says_so_and_says_where_the_names_are(self):
        tools = tools_over(None)
        with pytest.raises(ValueError) as raised:
            tools.get_field(a_context(), {"field_id": "made_up.metric"})

        message = str(raised.value)
        assert "made_up.metric" in message
        assert "list_fields" in message

    def test_a_blank_id_is_refused_before_the_store_is_opened(self):
        tools = tools_over(None)
        with pytest.raises(ValueError, match="must name a registered field"):
            tools.get_field(a_context(), {"field_id": "   "})


class TestThroughTheExecutor:
    """What the model actually receives, which is a result and never a traceback."""

    @staticmethod
    def _run(session, calls):
        entries = {entry.name: entry for entry in tools_over(session).entries()}
        executor = ToolExecutor(
            context=a_context(),
            lookup=entries.get,
            availability=lambda name: name in entries,
        )
        return asyncio.run(executor.run(calls))

    def test_an_unregistered_field_comes_back_as_a_failed_result(self):
        outcome = self._run(
            None,
            [
                ExecutorToolCall(
                    id="c1", name="get_field", arguments={"field_id": "nope.nope"}
                )
            ],
        )

        assert len(outcome.results) == 1
        result = outcome.results[0]
        assert result.ok is False
        assert "nope.nope" in result.text
        assert "list_fields" in result.text
        assert outcome.halted is False

    def test_the_catalog_and_a_figure_come_back_in_the_issued_order(self):
        with open_session() as session:
            store_window(session)
            outcome = self._run(
                session,
                [
                    ExecutorToolCall(id="a", name="get_field", arguments={
                        "field_id": NAMED_FIELD
                    }),
                    ExecutorToolCall(id="b", name="list_fields", arguments={}),
                ],
            )

        assert [result.call_id for result in outcome.results] == ["a", "b"]
        assert all(result.ok for result in outcome.results)
        assert json.loads(outcome.results[0].text)["fieldId"] == NAMED_FIELD
        assert json.loads(outcome.results[1].text)["count"] == len(REGISTRY)

    def test_both_declare_a_result_cap_that_stops_a_bug(self):
        for entry in tools_over(None).entries():
            assert entry.max_result_size_chars == MAX_RESULT_CHARS
