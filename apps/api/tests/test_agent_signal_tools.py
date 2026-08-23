"""The two tools that let a model ask this system what it knows.

Everything here is about a boundary rather than about arithmetic. The figures
themselves are ``alpha/envelope.py``'s and are tested there; what is under test
is who may ask for one, what they are allowed to name when they ask, and what
comes back when the store cannot answer.

*Both lanes reach them, and they get two signatures out of one registration.*
An Analysis is keyed by ``(symbol, trading_day)`` and the symbol arrives through
the context; a conversation is keyed by nothing, so there the symbol is the
user's own request and arrives as an argument. Where the context names one it
wins, and an argument disagreeing with it is refused — the Analysis lane's
boundary is enforced rather than merely unmentioned in a schema.

*Nobody names a Trading Day or a peer list.* A day is a route to a session that
has not closed; a peer list is the sample a percentile is a position within, and
a model choosing its own comparison group chooses its own answer.

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
    DISPLAY_NAMES,
    MAX_RESULT_CHARS,
    TOOLSET,
    SignalTools,
    axis_of,
    catalog,
    display_name_of,
    namespace_of,
    summarise_get_field,
    summarise_list_fields,
)
from src.agent.toolsets import CHAT_TOOLSETS, TOOLSETS, resolve_toolset
from src.alpha.field_profile import (
    PRICE_ZONE_FIELD_ID,
    AnalysisIndustry,
    Axis,
    profile_for,
)
from src.stocks.signals.registry import REGISTRY
from src.stocks.universe import forget_cohort_cache

from .test_envelope import (
    PEERS,
    SYMBOL,
    TRADING_DAY,
    open_session,
    store_peers,
    store_window,
)
from .test_volume_spike import seat_cohort

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
    def test_the_chat_lane_selects_the_signals_bundle(self):
        """The reversal of ``1e7b936``, asserted where it is easiest to notice."""
        assert "signals" in CHAT_TOOLSETS
        assert "list_fields" in resolve_toolset(CHAT_TOOLSETS)
        assert "get_field" in resolve_toolset(CHAT_TOOLSETS)

    def test_the_bundle_holds_the_two_store_reads_and_the_price_check(self):
        expected = ("list_fields", "get_field", "check_price_claim")
        assert TOOLSETS["signals"]["tools"] == expected
        assert resolve_toolset("signals") == expected

    def test_the_agent_loop_defaults_to_the_chat_selection(self):
        """Not to "every registered bundle", which is still not the same thing.

        The selection now includes ``signals``, so the difference is no longer
        about this bundle — it is that a fourth bundle added tomorrow does not
        reach a conversation until ``CHAT_TOOLSETS`` names it.
        """
        import inspect

        from src.agent.loop import AgentLoop

        source = inspect.getsource(AgentLoop.__init__)
        assert "CHAT_TOOLSETS if toolsets is None" in source

    def test_a_chat_selection_naming_a_bundle_nobody_has_fails_at_import(self):
        from src.agent import toolsets as module

        original = module.CHAT_TOOLSETS
        module.CHAT_TOOLSETS = ("web", "memory", "signls")
        try:
            with pytest.raises(KeyError):
                module._check_the_chat_selection_holds()
        finally:
            module.CHAT_TOOLSETS = original

    def test_both_tools_belong_to_one_toolset(self):
        entries = tools_over(None).entries()
        assert {entry.toolset for entry in entries} == {TOOLSET}


class TestWhatTheModelMayName:
    def test_neither_schema_admits_a_day_or_a_peer_list(self):
        forbidden = {"trading_day", "tradingDay", "peers", "end", "date"}
        for entry in tools_over(None).entries():
            named = set(entry.schema["properties"])
            assert not named & forbidden, entry.name

    def test_get_field_takes_a_field_and_optionally_a_symbol(self):
        entry = next(
            item for item in tools_over(None).entries() if item.name == "get_field"
        )
        assert set(entry.schema["properties"]) == {"field_id", "symbol"}
        # Only the field is required: an Analysis is already opened for a symbol
        # and naming one there is refused.
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

    def test_a_context_with_a_symbol_and_no_day_has_no_session_to_read(self):
        result = tools_over(None).get_field(
            a_context(day=None), {"field_id": NAMED_FIELD}
        )

        assert result["error"] == "cannot_read"
        assert "no session" in result["detail"]


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


class TestTheChatLaneSignature:
    """A conversation is keyed by nothing, so there the symbol is an argument.

    This is the half of the reversal that had to be designed rather than
    switched on: the Analysis lane knows its symbol because a Run is keyed by
    one, and a conversation knows it because the user typed it. Two facts of
    different standing, so two ways in — and the handler keeps them apart rather
    than merging them into one field that means either.
    """

    @staticmethod
    def _seated(session):
        """A store holding one symbol that is genuinely in the Universe."""
        store_window(session)
        seat_cohort(session, [SYMBOL])
        forget_cohort_cache()

    def test_a_symbol_argument_reads_that_symbol_with_no_context(self):
        with open_session() as session:
            self._seated(session)
            figure = tools_over(session).get_field(
                registry.ToolContext(user_id=7),
                {"field_id": NAMED_FIELD, "symbol": SYMBOL.lower()},
            )

        assert figure["fieldId"] == NAMED_FIELD
        # The newest closed session the store holds, which is what the chat lane
        # resolves rather than accepting a day from the model.
        assert figure["asOf"] is not None

    def test_a_symbol_outside_the_universe_is_a_sentence_and_not_a_raise(self):
        """And the sentence says it is about collection, not about the company."""
        with open_session() as session:
            self._seated(session)
            result = tools_over(session).get_field(
                registry.ToolContext(user_id=7),
                {"field_id": NAMED_FIELD, "symbol": "ZZZQQQ"},
            )

        assert result["error"] == "cannot_read"
        assert "Universe" in result["detail"]
        assert "not a statement" in result["detail"]

    def test_a_ticker_of_the_wrong_shape_is_a_sentence_and_not_a_raise(self):
        with open_session() as session:
            self._seated(session)
            result = tools_over(session).get_field(
                registry.ToolContext(user_id=7),
                {"field_id": NAMED_FIELD, "symbol": "not a ticker"},
            )

        assert result["error"] == "cannot_read"

    def test_no_symbol_and_no_context_says_which_one_is_missing(self):
        with open_session() as session:
            self._seated(session)
            result = tools_over(session).get_field(
                registry.ToolContext(user_id=7), {"field_id": NAMED_FIELD}
            )

        assert result["error"] == "cannot_read"
        assert "none was named" in result["detail"]

    def test_a_store_with_no_closed_session_has_no_day_to_read_on(self):
        with open_session() as session:
            seat_cohort(session, [SYMBOL])
            forget_cohort_cache()
            result = tools_over(session).get_field(
                registry.ToolContext(user_id=7),
                {"field_id": NAMED_FIELD, "symbol": SYMBOL},
            )

        assert result["error"] == "cannot_read"
        assert "no closed session" in result["detail"]


class TestTheAnalysisLaneBoundaryIsEnforced:
    """The context wins, and a disagreeing argument is refused.

    Before the chat signature existed the boundary was the *absence* of a symbol
    field from the schema, which is a statement about what the model was told. A
    schema is not an enforcement, and now that the field exists the handler has
    to be.
    """

    def test_an_argument_naming_another_symbol_is_refused(self):
        with open_session() as session:
            store_window(session)
            result = tools_over(session).get_field(
                a_context(), {"field_id": NAMED_FIELD, "symbol": "OTHER"}
            )

        assert result["error"] == "cannot_read"
        assert SYMBOL in result["detail"]
        assert "OTHER" in result["detail"]

    def test_an_argument_naming_the_same_symbol_is_not_a_request_for_anything_else(
        self,
    ):
        with open_session() as session:
            store_window(session)
            figure = tools_over(session).get_field(
                a_context(), {"field_id": NAMED_FIELD, "symbol": SYMBOL.lower()}
            )

        assert figure["fieldId"] == NAMED_FIELD

    def test_the_analysis_lane_never_consults_the_universe(self):
        """An Analysis Run is opened by the pipeline, which decided that already.

        Re-asking here would make an Analysis fail on a symbol that left the
        Universe after its Run was created, which is a different failure from the
        one the Universe rule exists for.
        """
        with open_session() as session:
            store_window(session)
            figure = tools_over(session).get_field(
                a_context(), {"field_id": NAMED_FIELD}
            )

        assert figure["fieldId"] == NAMED_FIELD

    def test_a_refusal_carries_no_field_id_so_the_loop_cannot_bank_it(self):
        """``alpha/analysis_loop._figure_in`` folds a payload with a fieldId into
        the envelope. A refusal wearing one would become evidence."""
        with open_session() as session:
            store_window(session)
            result = tools_over(session).get_field(
                a_context(), {"field_id": NAMED_FIELD, "symbol": "OTHER"}
            )

        assert "fieldId" not in result


class TestWhatAReaderIsShown:
    """The second of a tool's two names, and the one a real Turn got wrong.

    A Turn analysing SSI put fourteen rows reading ``get_field`` on screen. Two
    causes: the rail had no reader-facing name for the tool, and sixteen of the
    thirty registered fields have no label at all — ``profile_entry_for`` hands
    back the field's own id for any field the **Analysis Field Profile** never
    names, and those sixteen are exactly the ones these tools exist to reach.

    So the labels are curated here, and they are checked both ways at import: a
    field added to the **Signal Registry** without one fails the build rather
    than reaching a screen as its id.
    """

    def test_every_registered_field_has_a_name_a_person_can_read(self):
        assert set(DISPLAY_NAMES) == set(REGISTRY)
        for field_id, shown in DISPLAY_NAMES.items():
            assert shown.strip()
            assert shown != field_id

    def test_the_sixteen_the_profile_never_names_are_covered(self):
        """The half of the catalog that had no label is the half that matters.

        These are the fields the loop exists to reach, so they are the ones a
        reader sees most often on the rail.
        """
        from src.alpha.envelope import profile_entry_for

        unlabelled = [
            field_id
            for field_id in REGISTRY
            if profile_entry_for(field_id).label == field_id
        ]

        assert unlabelled, "the gap this table fills has to still exist"
        for field_id in unlabelled:
            assert display_name_of(field_id) != field_id

    def test_the_figure_s_own_label_is_left_alone(self):
        """This table is a rail row, not a second interpretation of a number.

        ``envelope.py`` refuses to invent labels beside a figure and gives its
        reason; nothing here reaches a payload, a figure, or the model.
        """
        from src.alpha.envelope import profile_entry_for

        assert profile_entry_for(NAMED_FIELD).label == "RSI (14)"
        assert profile_entry_for(UNNAMED_FIELD).label == UNNAMED_FIELD
        assert display_name_of(UNNAMED_FIELD) == "Sharpe (năm hoá)"

    def test_the_catalog_the_model_reads_is_unchanged(self):
        """The model picks a field by id and reads the Registry's own wording."""
        rows = {row["fieldId"]: row for row in catalog()}

        assert rows[NAMED_FIELD]["label"] == "RSI (14)"
        assert rows[UNNAMED_FIELD]["label"] == UNNAMED_FIELD
        assert all("displayName" not in row for row in rows.values())

    def test_a_field_read_names_the_figure_and_the_company(self):
        """One argument cannot say it: the field alone reads the same for every
        symbol in a Turn that compared two."""
        assert (
            summarise_get_field({"field_id": NAMED_FIELD, "symbol": "ssi"})
            == "Đọc chỉ báo: RSI (14) — SSI"
        )

    def test_without_a_symbol_the_row_is_the_field_alone(self):
        """The Analysis lane, where every row is about the one company anyway."""
        assert (
            summarise_get_field({"field_id": "liquidity_profile.adtv_vnd"})
            == "Đọc chỉ báo: Giá trị giao dịch bình quân"
        )

    def test_a_field_id_nothing_holds_still_produces_a_row(self):
        """The model may put anything in that argument, and the rail still draws."""
        assert summarise_get_field({"field_id": "made_up.metric"}) == (
            "Đọc chỉ báo: made_up.metric"
        )
        assert summarise_get_field({}) == "Đọc chỉ báo: chỉ báo"

    def test_a_catalog_read_names_the_axis_when_one_was_asked_for(self):
        assert summarise_list_fields({}) == "Xem danh mục chỉ báo"
        assert summarise_list_fields({"axis": "money_flow"}) == (
            "Xem danh mục chỉ báo: dòng tiền"
        )
        assert summarise_list_fields({"axis": "nonsense"}) == "Xem danh mục chỉ báo"

    def test_the_registrations_carry_the_row_builders(self):
        """So ``summarise_call`` needs no table of its own to consult."""
        entries = {item.name: item for item in tools_over(None).entries()}

        assert entries["get_field"].display_name == "Đọc chỉ báo"
        assert entries["get_field"].summarise is summarise_get_field
        assert entries["list_fields"].summarise is summarise_list_fields
