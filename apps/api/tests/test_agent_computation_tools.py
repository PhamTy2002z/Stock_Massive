"""The computation clusters are thin projections over registered fields."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from src.agent.tools import ToolContext
from src.agent.tools.catalog import MAX_TOOL_RESULT_BYTES, serialized_size
from src.agent.tools.computations import ComputationTools
from src.stocks.providers import Exchange
from src.stocks.universe import Universe
from tests.test_indicator_pack import open_session, store_indicator_history
from tests.test_cross_sectional import a_sample, open_session as open_cross_session
from tests.test_price_band import list_on


DAY = date(2026, 8, 14)
SYMBOL = "AAA"


def context() -> ToolContext:
    return ToolContext(user_id=7, trading_day=DAY, active_symbol=SYMBOL)


def tools_for(session, members=(SYMBOL,)) -> ComputationTools:
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    return ComputationTools(
        session_factory=factory,
        universe_factory=lambda _session: Universe(explicit=tuple(members)),
    )


def test_the_cluster_names_and_unit_named_kelly_inputs_are_model_visible():
    session = open_session()
    tools = tools_for(session)
    catalog = tools.catalog(trace_writer=lambda _trace: None)

    assert catalog.names == (
        "risk_metrics",
        "price_zone",
        "market_behavior",
        "cross_sectional",
        "foreign_flow",
        "indicator_pack",
    )
    indicator = next(schema for schema in catalog.tool_schemas if schema.name == "indicator_pack")
    assert set(indicator.parameters["properties"]) == {
        "symbol",
        "edge_decimal",
        "variance_decimal_squared",
    }
    assert "false-positive rate" in next(
        schema for schema in catalog.tool_schemas if schema.name == "risk_metrics"
    ).description


@pytest.mark.asyncio
async def test_cluster_refusals_keep_metadata_and_report_window_health_once():
    session = open_session()
    list_on(session, SYMBOL, Exchange.HOSE)
    session.commit()
    catalog = tools_for(session).catalog(trace_writer=lambda _trace: None)

    result = await catalog.dispatch("risk_metrics", {"symbol": SYMBOL}, context())

    assert set(result["registered_fields"]) == {
        "price_zone.ordinary_range_pct",
        "realized_volatility.yang_zhang_annualized_pct",
        "drawdown_stats.mdd_over_expected",
        "risk_adjusted.sharpe_annualized",
        "risk_adjusted.sortino_annualized",
    }
    assert result["window_health"]["sessions_used"] == 0
    assert str(result).count("window_health") == 1
    for field in result["registered_fields"].values():
        assert field["value"] is None
        assert field["refusal"] == "insufficient_history"
        assert set(field) >= {
            "value",
            "unit",
            "sign",
            "interpretation",
            "kind",
            "claim",
            "source",
            "details",
            "refusal",
            "degraded_reason",
        }
    assert "null_fpr" not in str(result)
    assert serialized_size(result) <= MAX_TOOL_RESULT_BYTES


@pytest.mark.asyncio
async def test_indicator_pack_is_descriptive_and_kelly_echoes_only_user_assumptions():
    session = open_session()
    days = store_indicator_history(session)
    session.commit()
    catalog = tools_for(session).catalog(trace_writer=lambda _trace: None)
    tool_context = ToolContext(user_id=7, trading_day=days[-1], active_symbol=SYMBOL)

    result = await catalog.dispatch(
        "indicator_pack",
        {
            "symbol": SYMBOL,
            "edge_decimal": 0.02,
            "variance_decimal_squared": 0.08,
        },
        tool_context,
    )

    assert set(result["registered_fields"]) == {
        "indicator_pack.rsi_14",
        "indicator_pack.macd_12_26_vnd",
        "indicator_pack.bollinger_percent_b_20",
    }
    assert all(
        field["kind"] == "vocabulary" and field["claim"] == "descriptive"
        for field in result["registered_fields"].values()
    )
    assert result["fractional_kelly"] == {
        "provenance": "user_input",
        "scenario_only": True,
        "assumptions": {
            "edge_decimal": 0.02,
            "variance_decimal_squared": 0.08,
        },
        "quarter_kelly_fraction": pytest.approx(0.0625),
        "half_kelly_fraction": pytest.approx(0.125),
        "full_kelly_ceiling_fraction": pytest.approx(0.25),
        "half_kelly_sensitivity_fraction": pytest.approx((0.0625, 0.1875)),
    }
    assert "allocation" not in str(result).lower()
    assert str(result).count("window_health") == 1
    assert serialized_size(result) <= MAX_TOOL_RESULT_BYTES


@pytest.mark.asyncio
async def test_a_non_universe_symbol_gets_the_shared_structured_refusal():
    session = open_session()
    catalog = tools_for(session, members=("BBB",)).catalog(
        trace_writer=lambda _trace: None
    )

    result = await catalog.dispatch("market_behavior", {"symbol": SYMBOL}, context())

    assert result == {"reason": "not_in_universe", "suggestions": []}


@pytest.mark.asyncio
async def test_cross_sectional_refuses_ranked_fields_without_raising_for_a_small_universe():
    session = open_cross_session()
    members, days = a_sample(session, count=3, sessions=252, with_statements=True)
    session.commit()
    catalog = tools_for(session, members=members).catalog(
        trace_writer=lambda _trace: None
    )
    tool_context = ToolContext(
        user_id=7,
        trading_day=days[-1],
        active_symbol=members[-1],
    )

    result = await catalog.dispatch(
        "cross_sectional", {"symbol": members[-1]}, tool_context
    )

    ranked = {
        name: field
        for name, field in result["registered_fields"].items()
        if name != "price_trend.sma_50_over_200"
    }
    assert ranked
    assert all(field["value"] is None for field in ranked.values())
    assert all(field["refusal"] is not None for field in ranked.values())
    assert result["window_health"]["sessions_used"] == 252


@pytest.mark.asyncio
async def test_kelly_requires_both_user_inputs_and_never_estimates_an_edge():
    session = open_session()
    list_on(session, SYMBOL, Exchange.HOSE)
    session.commit()
    catalog = tools_for(session).catalog(trace_writer=lambda _trace: None)

    result = await catalog.dispatch(
        "indicator_pack", {"symbol": SYMBOL, "edge_decimal": 0.02}, context()
    )

    assert result["fractional_kelly"] == {
        "status": "refused",
        "reason": "edge_and_variance_required_together",
    }


@pytest.mark.asyncio
async def test_every_cluster_stays_in_budget_at_the_widest_registered_window():
    session = open_cross_session()
    members, days = a_sample(
        session,
        count=32,
        sessions=252,
        with_statements=True,
    )
    session.commit()
    catalog = tools_for(session, members=members).catalog(
        trace_writer=lambda _trace: None
    )
    tool_context = ToolContext(
        user_id=7,
        trading_day=days[-1],
        active_symbol=members[-1],
    )

    for tool_name in catalog.names:
        arguments = {"symbol": members[-1]}
        if tool_name == "indicator_pack":
            arguments.update(
                edge_decimal=0.02,
                variance_decimal_squared=0.08,
            )
        result = await catalog.dispatch(tool_name, arguments, tool_context)

        assert serialized_size(result) <= MAX_TOOL_RESULT_BYTES
        assert str(result).count("window_health") == 1


@pytest.mark.asyncio
async def test_the_price_zone_reaches_the_model_as_a_registered_reference_price():
    """The Gate's condition 3 needs a route to a registered zone, and this is it.

    Before this tool existed the only registered price-zone field was served by
    no tool at all, so no recommendation could name a zone computed in code and
    the Gate refused every one of them — the eval battery measured it as
    category B at 0/30. The assertions below are that route: a value, an anchor
    close to cite as the reference price, and the band around it.
    """
    session = open_session()
    days = store_indicator_history(session)
    session.commit()
    catalog = tools_for(session).catalog(trace_writer=lambda _trace: None)
    tool_context = ToolContext(user_id=7, trading_day=days[-1], active_symbol=SYMBOL)

    result = await catalog.dispatch("price_zone", {"symbol": SYMBOL}, tool_context)

    served = result["registered_fields"]["price_zone.ordinary_range_pct"]
    assert served["refusal"] is None
    assert served["value"] > 0
    assert served["details"]["anchor_close"] > 0
    assert (
        served["details"]["lower_price"]
        < served["details"]["anchor_close"]
        < served["details"]["upper_price"]
    )
    # Alone in its call, the shared Window Health is this field's own — so a
    # refusal here is the zone refusing, never a wider field in the same cluster.
    assert result["health_basis_field"] == "price_zone.ordinary_range_pct"
    assert result["window_health"]["refusal"] is None


@pytest.mark.asyncio
async def test_a_price_zone_citation_resolves_as_a_registered_field():
    """The zone and the reference price must survive the validator's resolution.

    Serving the field is only half the route: the Gate reads the *citation*, and
    conditions 3 and 7 both turn on the resolved source being a registered field
    rather than a stored figure or an external claim.
    """
    from src.agent.context import TranscriptToolCall
    from src.agent.grounding import EvidenceRef, EvidenceSource, TraceIndex

    session = open_session()
    days = store_indicator_history(session)
    session.commit()
    catalog = tools_for(session).catalog(trace_writer=lambda _trace: None)
    tool_context = ToolContext(user_id=7, trading_day=days[-1], active_symbol=SYMBOL)
    result = await catalog.dispatch("price_zone", {"symbol": SYMBOL}, tool_context)

    traces = TraceIndex(
        [
            TranscriptToolCall(
                call_id="c1",
                name="price_zone",
                arguments={"symbol": SYMBOL},
                result=result,
            )
        ]
    )
    base = "registered_fields.price_zone.ordinary_range_pct"
    anchor = traces.resolve(EvidenceRef.parse(f"c1#{base}.details.anchor_close"))
    upper = traces.resolve(EvidenceRef.parse(f"c1#{base}.details.upper_price"))

    assert anchor.source is EvidenceSource.REGISTERED_FIELD
    assert upper.source is EvidenceSource.REGISTERED_FIELD
    assert anchor.value == result["registered_fields"][
        "price_zone.ordinary_range_pct"
    ]["details"]["anchor_close"]
    assert anchor.window_health_refusal is None
    assert anchor.interpretation and anchor.unit
