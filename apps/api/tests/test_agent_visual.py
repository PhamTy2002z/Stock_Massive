"""What the host will draw, and everything it refuses to draw.

The assembler is deterministic and free — no clock, no model, no network — so
every case here is exact. Two properties are what the file exists to hold:

**No value the host did not read.** Every number in an assembly is a field of a
successful ``get_market_data`` call, and every series names the evidence row and
the call id it came from. There is no path by which a model-written figure could
arrive, because there is no model-written payload.

**A refusal is the absence of the part.** Flint validates nothing (the web
contract test proves it), so every input that would draw a wrong chart has to be
refused here. It is refused by returning ``None``: the reason a Turn has no
chart is already in the ledger's gaps, and a part carrying a status would be the
same explanation written twice.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from src.agent import visual
from src.agent.evidence.contracts import (
    ClaimKind,
    ClaimLedger,
    VerificationVerdict,
    VerifiedClaim,
    VerifierOutcome,
)
from src.agent.evidence.pipeline import LEDGER_VERSION, evidence_from_calls
from src.agent.evidence.source_policy import POLICY_VERSION
from src.agent.messages import ToolCallStatus, TurnToolCall
from src.agent.registry import ToolContext
from src.agent.tools import market_data

from .test_agent_market_data import daily, read, tools_returning

NOW = datetime(2026, 9, 4, 17, 0, tzinfo=market_data.ICT)
CONTEXT = ToolContext(user_id=11, now=NOW)


def call(result: Any, *, call_id: str = "call_1") -> TurnToolCall:
    return TurnToolCall(
        id=call_id,
        name="get_market_data",
        arguments={},
        status=ToolCallStatus.OK,
        result_text=json.dumps(result, ensure_ascii=False),
    )


def market_read(symbol: str = "FPT", **kwargs: Any) -> Any:
    return read(
        tools_returning(daily(24, 25, 26)),
        symbol=symbol,
        context=CONTEXT,
        **kwargs,
    )


def ledger_over(
    calls: list[TurnToolCall],
    *,
    verdict: VerificationVerdict = VerificationVerdict.SINGLE_SOURCE,
    cite: bool = True,
) -> ClaimLedger:
    """One material claim resting on every market row these calls produced."""
    evidence = evidence_from_calls(calls)
    ids = tuple(item.evidence_id for item in evidence) if cite else ()
    return ClaimLedger(
        version=LEDGER_VERSION,
        policy_version=POLICY_VERSION,
        as_of=NOW,
        evidence=evidence,
        claims=(
            VerifiedClaim(
                claim_id="c1",
                text="FPT đóng cửa ở 71.400 đồng.",
                kind=ClaimKind.FACT,
                material=True,
                unit="đồng",
                currency="VND",
                verdict=verdict,
                supporting_evidence_ids=ids,
            ),
        ),
        gaps=(),
        assumptions=("Không phải khuyến nghị cá nhân hóa.",),
        verifier_outcome=VerifierOutcome.VERIFIED,
    )


def build(calls: list[TurnToolCall], ledger: ClaimLedger | None) -> Any:
    return visual.build_visual(calls=calls, ledger=ledger, as_of=NOW)


# -- the shapes the calls add up to ---------------------------------------


def test_one_market_call_becomes_candles_over_volume():
    """The candlestick template has no volume channel, so this is two charts.

    Asserted rather than commented, because the alternative — one chart with a
    second axis — could only be reached by editing what Flint compiled.
    """
    calls = [call(market_read())]

    part = build(calls, ledger_over(calls))

    assert part is not None
    assert [item["chart_spec"]["chartType"] for item in part["assemblies"]] == [
        visual.CANDLESTICK,
        visual.BAR,
    ]
    assert part["version"] == visual.VERSION
    assert part["renderer"] == visual.RENDERER
    # The columns are the words the axes are titled with, so they are written
    # the way the pane is read rather than the way the payload is keyed.
    assert part["assemblies"][0]["chart_spec"]["encodings"] == {
        "x": "Phiên",
        "open": "Mở",
        "high": "Cao",
        "low": "Thấp",
        "close": "Đóng",
    }


def test_every_value_in_the_assembly_is_a_field_of_the_call():
    result = market_read()
    calls = [call(result)]

    part = build(calls, ledger_over(calls))

    rows = part["assemblies"][0]["data"]["values"]
    assert len(rows) == result["row_count"]
    for drawn, source in zip(rows, result["rows"], strict=True):
        # The label is the bar close written short, and nothing else on the row
        # is derived at all.
        assert drawn["Phiên"] == datetime.fromisoformat(
            source["bar_closed_at"]
        ).strftime("%d/%m")
        assert drawn["Mở"] == source["open"]
        assert drawn["Đóng"] == source["close"]
        assert drawn["Khối lượng"] == source["volume"]
    # Whole dong, as the tool normalised them — not the provider's thousands.
    assert rows[0]["Mở"] == 72_500


def test_the_part_names_the_call_and_the_evidence_behind_it():
    calls = [call(market_read())]
    ledger = ledger_over(calls)

    part = build(calls, ledger)

    assert part["sourceCallIds"] == ["call_1"]
    assert part["evidenceIds"] == [ledger.evidence[0].evidence_id]
    assert part["asOf"] == NOW.isoformat()


def test_two_comparable_calls_become_one_multi_series_line():
    calls = [
        call(market_read("FPT"), call_id="call_1"),
        call(market_read("VNM"), call_id="call_2"),
    ]

    part = build(calls, ledger_over(calls))

    assert len(part["assemblies"]) == 1
    spec = part["assemblies"][0]["chart_spec"]
    assert spec["chartType"] == visual.LINE
    assert spec["encodings"] == {"x": "Phiên", "y": "Đóng", "color": "Mã"}
    # Series order follows call order, so the same two calls always draw the
    # same chart.
    assert [row["Mã"] for row in part["assemblies"][0]["data"]["values"]][0] == "FPT"
    assert part["sourceCallIds"] == ["call_1", "call_2"]


def test_the_same_read_made_twice_still_draws_one_symbol():
    """A repeated read is the same series. Counted twice it would look like two
    symbols with one name and the comparability rule would withhold the chart."""
    payload = market_read("FPT")
    calls = [
        call(payload, call_id="call_1"),
        call(payload, call_id="call_2"),
    ]

    part = build(calls, ledger_over(calls))

    assert [spec["chart_spec"]["chartType"] for spec in part["assemblies"]] == [
        visual.CANDLESTICK,
        visual.BAR,
    ]
    assert part["sourceCallIds"] == ["call_1"]


def test_a_partial_reread_of_the_same_symbol_keeps_the_widest_series():
    """A follow-up for missing recent bars must not turn one symbol into two."""
    full = market_read("FPT")
    partial = read(
        tools_returning(daily(25, 26)),
        symbol="FPT",
        start="2026-08-25",
        context=CONTEXT,
    )
    calls = [call(full, call_id="full"), call(partial, call_id="partial")]

    part = build(calls, ledger_over(calls))

    assert part is not None
    assert part["sourceCallIds"] == ["full"]
    assert len(part["assemblies"][0]["data"]["values"]) == full["row_count"]


def test_two_calls_on_different_intervals_draw_nothing():
    """Two scales on one axis is an argument the data does not make."""
    intraday = read(
        tools_returning(daily(24, 25, 26)),
        symbol="VNM",
        interval="15m",
        context=CONTEXT,
    )
    calls = [call(market_read("FPT")), call(intraday, call_id="call_2")]

    assert build(calls, ledger_over(calls)) is None


# -- what is refused ------------------------------------------------------


def test_no_market_call_means_no_part():
    web = TurnToolCall(
        id="call_1", name="fetch_url", status=ToolCallStatus.OK, result_text="{}"
    )

    assert build([web], ledger_over([])) is None


def test_a_failed_market_call_is_not_evidence_of_a_price():
    failed = TurnToolCall(
        id="call_1",
        name="get_market_data",
        status=ToolCallStatus.ERROR,
        result_text=json.dumps(market_read()),
    )

    assert build([failed], ledger_over([failed])) is None


def test_an_unsupported_ledger_draws_nothing():
    calls = [call(market_read())]

    part = build(
        calls, ledger_over(calls, verdict=VerificationVerdict.UNSUPPORTED, cite=False)
    )

    assert part is None


def test_a_temporally_invalid_ledger_draws_nothing():
    calls = [call(market_read())]

    part = build(
        calls,
        ledger_over(
            calls, verdict=VerificationVerdict.TEMPORALLY_INVALID, cite=False
        ),
    )

    assert part is None


def test_figures_no_surviving_claim_cites_draw_nothing():
    """Present in the ledger is not the same as admitted into the answer."""
    calls = [call(market_read())]

    assert build(calls, ledger_over(calls, cite=False)) is None


def test_no_ledger_at_all_draws_nothing():
    assert build([call(market_read())], None) is None


def test_a_call_with_no_id_draws_nothing():
    anonymous = call(market_read())
    anonymous = TurnToolCall(
        id="",
        name="get_market_data",
        status=ToolCallStatus.OK,
        result_text=anonymous.result_text,
    )

    assert build([anonymous], ledger_over([anonymous])) is None


def test_more_series_than_the_cap_draws_nothing():
    calls = [
        call(market_read(symbol), call_id=f"call_{index}")
        for index, symbol in enumerate(("FPT", "VNM", "HPG", "MWG", "VCB"))
    ]

    assert len(calls) > visual.MAX_SERIES
    assert build(calls, ledger_over(calls)) is None


def test_more_rows_than_the_cap_draws_nothing():
    result = market_read()
    result["rows"] = result["rows"] * (visual.MAX_ROWS_PER_SERIES // 3 + 1)
    calls = [call(result)]

    assert len(result["rows"]) > visual.MAX_ROWS_PER_SERIES
    assert build(calls, ledger_over(calls)) is None


def test_a_row_missing_a_price_draws_nothing():
    result = market_read()
    del result["rows"][1]["close"]
    calls = [call(result)]

    assert build(calls, ledger_over(calls)) is None


def test_the_pinned_flint_version_matches_the_web_package():
    """One pin, read from both sides, so a bump cannot land on one of them."""
    from pathlib import Path

    package = json.loads(
        (Path(__file__).resolve().parents[3] / "apps/web/package.json").read_text()
    )

    assert package["dependencies"]["flint-chart"] == visual.FLINT_VERSION


def test_the_assembled_part_is_json_and_stays_that_way():
    """Replay determinism is the payload compared with itself, so it must round-trip."""
    calls = [call(market_read())]

    part = build(calls, ledger_over(calls))
    again = build(calls, ledger_over(calls))

    assert json.loads(json.dumps(part)) == part
    assert again == part
