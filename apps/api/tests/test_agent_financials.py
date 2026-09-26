"""Reported ratios through the adapter, arithmetic through the calculator, and how
the figure check treats both.

The KB payload below has the shape probed on 2026-09-26 — headers whose ``ID``
repeats, a quarter listed twice, values keyed ``Value{i}`` in header order — with
invented numbers.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pytest

from src.agent.evidence import grounding
from src.agent.evidence.grounding import FigureStatus
from src.agent.messages import ToolCallStatus, TurnToolCall
from src.agent.registry import ToolContext
from src.agent.tools import calculator, financials
from src.agent.tools.market_data import ICT, INTERNAL_PROFILE, MarketDataError
from src.core.config import Settings

NOW = datetime(2026, 9, 26, 14, 0, tzinfo=ICT)
TODAY = NOW.date()

RAW = {
    "Head": [
        {"ID": 1, "YearPeriod": 2026, "TermCode": "Q2", "DatePubDepartment": "2026-07-31T00:00:00"},
        {"ID": 2, "YearPeriod": 2026, "TermCode": "Q1", "DatePubDepartment": "2026-04-29T00:00:00"},
        {"ID": 1, "YearPeriod": 2025, "TermCode": "Q4", "DatePubDepartment": "2026-01-30T00:00:00"},
        {"ID": 2, "YearPeriod": 2025, "TermCode": "Q4", "DatePubDepartment": "2026-01-30T00:00:00"},
        {"ID": 3, "YearPeriod": 2025, "TermCode": "Q3", "DatePubDepartment": "2025-10-28T00:00:00"},
    ],
    "Content": {
        "Nhóm chỉ số Định giá": [
            {"Name": "P/B", "Unit": "Lần", "Value1": 2.22, "Value2": 1.91, "Value3": 1.71, "Value4": 1.25, "Value5": 1.40},
            {"Name": "Giá trị sổ sách của cổ phiếu (BVPS)", "Unit": "VNĐ", "Value1": 33315.68, "Value2": 32609.85, "Value3": 1, "Value4": 2, "Value5": 30000},
        ],
        "Nhóm chỉ số Sinh lợi": [
            {"Name": "ROE", "Unit": "%", "Value1": 2.17, "Value2": 2.61, "Value3": 4.74, "Value4": 5.13, "Value5": 4.0},
        ],
    },
}


class FakeProvider:
    publisher = "KB Securities"
    source = "kbs"
    not_carried = financials.NOT_IN_KBS

    def ratios(self, symbol: str, *, quarterly: bool, periods: int) -> financials.Statement:
        paired, dropped = financials.pair_periods(RAW, quarterly=quarterly)
        return financials.Statement(
            symbol=symbol,
            publisher=self.publisher,
            source=self.source,
            periods=tuple(paired[:periods]),
            dropped=tuple(dropped),
            not_carried=self.not_carried,
            raw_sha256="d" * 64,
        )


def settings(**overrides: Any) -> Settings:
    return Settings(**{"deployment_profile": INTERNAL_PROFILE, "market_data_enabled": True, **overrides})


def tool(**overrides: Any) -> financials.FinancialsTools:
    return financials.FinancialsTools(settings=settings(**overrides), provider=FakeProvider())


# -- the adapter -----------------------------------------------------------


def test_values_follow_the_headers_as_sent_and_a_doubled_quarter_is_dropped():
    periods, dropped = financials.pair_periods(RAW, quarterly=True)

    assert [p.label for p in periods] == ["Quý 2/2026", "Quý 1/2026", "Quý 3/2025"]
    assert dropped == ["Quý 4/2025"]
    q2 = {f.name: f.value for f in periods[0].figures}
    assert q2["P/B"] == 2.22 and q2["ROE"] == 2.17
    # Value5 belongs to the fifth header, 2025 Q3 — not to a re-sorted slot.
    q3 = {f.name: f.value for f in periods[2].figures}
    assert q3["P/B"] == 1.40
    assert periods[0].ended == date(2026, 6, 30)
    assert periods[0].published == date(2026, 7, 31)


def test_the_tool_renders_dated_lines_and_names_what_the_source_lacks():
    result = tool().get_financial_ratios(ToolContext(user_id=1, now=NOW), {"symbol": "STB"})

    lines = result["excerpt"].splitlines()
    assert lines[1].startswith("2026-06-30: Quý 2/2026 (công bố 31/07/2026)")
    assert "P/B 2,22 lần" in lines[1]
    assert "ROE 2,17%" in lines[1]
    assert "Giá trị sổ sách của cổ phiếu (BVPS) 33.315,68 đồng" in lines[1]
    assert "Quý 4/2025" in result["excerpt"].split("Bỏ qua", 1)[1]
    assert "tỷ lệ nợ xấu (NPL)" in result["excerpt"]
    assert result["not_carried"] == list(financials.NOT_IN_KBS)


def test_the_tool_refuses_outside_the_internal_profile_and_for_an_index():
    with pytest.raises(MarketDataError):
        tool(deployment_profile="production").get_financial_ratios(
            ToolContext(user_id=1, now=NOW), {"symbol": "STB"}
        )
    with pytest.raises(MarketDataError):
        tool().get_financial_ratios(ToolContext(user_id=1, now=NOW), {"symbol": "VNINDEX"})


# -- the calculator --------------------------------------------------------


def test_every_operation_prints_its_formula_and_rounds_the_result():
    pb = calculator.compute(
        "divide",
        [{"label": "giá", "value": 76500, "unit": "đồng"}, {"label": "BVPS", "value": 33315.68, "unit": "đồng"}],
    )
    assert pb["result"] == "2.30" and pb["unit"] == "lần"
    assert pb["result_text"] == "2,30 lần"
    assert pb["formula"] == "giá 76.500 đồng / BVPS 33.315,68 đồng"

    growth = calculator.compute(
        "percent_change",
        [{"label": "giá 25/09", "value": 76500, "unit": "đồng"}, {"label": "giá 02/01", "value": 50100, "unit": "đồng"}],
    )
    assert growth["result_text"] == "52,69%"

    assert calculator.compute("difference", [{"label": "a", "value": 5, "unit": "%"}, {"label": "b", "value": 3.5, "unit": "%"}])["result"] == "1.50"
    assert calculator.compute("sum", [{"label": "a", "value": 1, "unit": "tỷ"}, {"label": "b", "value": 2, "unit": "tỷ"}])["result_text"] == "3,00 tỷ"


def test_the_calculator_refuses_what_it_cannot_do():
    with pytest.raises(calculator.CalculationError):
        calculator.compute("divide", [{"label": "a", "value": 1, "unit": ""}, {"label": "b", "value": 0, "unit": ""}])
    with pytest.raises(calculator.CalculationError):
        calculator.compute("eval", [{"label": "a", "value": 1, "unit": ""}])
    with pytest.raises(calculator.CalculationError):
        calculator.compute("divide", [{"label": "a", "value": 1, "unit": ""}])


# -- the figure check over both --------------------------------------------


def _call(call_id: str, name: str, payload: dict[str, Any]) -> TurnToolCall:
    return TurnToolCall(id=call_id, name=name, status=ToolCallStatus.OK, result_text=json.dumps(payload, ensure_ascii=False))


def _market() -> TurnToolCall:
    excerpt = "\n".join(
        [
            "STB · nến ngày · nguồn KB Securities · giá đã quy đổi sang VND đầy đủ",
            "2026-09-25T15:00:00+07:00: PHIÊN GẦN NHẤT 25/09/2026 · đóng 76.500 đồng · khối lượng 1.606.900 cổ phiếu",
            "2026-01-02T15:00:00+07:00: mở 50.100 đồng · cao 50.100 đồng · thấp 50.100 đồng · đóng 50.100 đồng · khối lượng 1.000.000 cổ phiếu",
            "2026-09-25T15:00:00+07:00: mở 76.500 đồng · cao 76.500 đồng · thấp 76.500 đồng · đóng 76.500 đồng · khối lượng 1.606.900 cổ phiếu",
        ]
    )
    return _call(
        "m1",
        "get_market_data",
        {
            "symbol": "STB", "interval": "1D", "interval_label": "nến ngày", "publisher": "KB Securities",
            "source": "kbs", "source_class": "store",
            "actual": {"start": "2026-01-02T15:00:00+07:00", "end": "2026-09-25T15:00:00+07:00"},
            "retrieved_at": NOW.isoformat(), "content_sha256": "e" * 64, "excerpt": excerpt,
        },
    )


def _ratios() -> TurnToolCall:
    return _call("f1", "get_financial_ratios", dict(tool().get_financial_ratios(ToolContext(user_id=1, now=NOW), {"symbol": "STB"})))


def _calc(call_id: str, operation: str, inputs: list[dict[str, Any]]) -> TurnToolCall:
    return _call(call_id, "calculate", dict(calculator.CalculatorTools().calculate(ToolContext(user_id=1, now=NOW), {"operation": operation, "inputs": inputs})))


def check(answer: str, calls: list[TurnToolCall]) -> grounding.GroundingReport:
    return grounding.check_answer(answer, grounding.collect_sources(calls), today=TODAY)


def test_a_reported_ratio_is_grounded_to_its_period():
    report = check("ROE quý 2/2026 là 2,17%, P/B cuối quý 2/2026 là 2,22 lần.", [_ratios()])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED] * 2
    assert "[1 · kỳ đến 30/06/2026]" in grounding.annotate(report)


def test_the_latest_reported_quarter_may_be_called_current():
    report = check("P/B hiện tại theo báo cáo là 2,22 lần.", [_ratios()])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]


def test_a_calculation_over_figures_this_turn_read_is_grounded_and_dated():
    pb = _calc(
        "c1",
        "divide",
        [{"label": "giá", "value": 76500, "unit": "đồng"}, {"label": "BVPS", "value": 33315.68, "unit": "đồng"}],
    )
    growth = _calc(
        "c2",
        "percent_change",
        [{"label": "giá 25/09", "value": 76500, "unit": "đồng"}, {"label": "giá 02/01", "value": 50100, "unit": "đồng"}],
    )

    report = check(
        "P/B theo giá hiện tại là 2,30 lần. Từ đầu năm 2026 STB tăng 52,69%.",
        [_market(), _ratios(), pb, growth],
    )

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED] * 2
    text = grounding.annotate(report)
    assert "2,30 lần [" in text and "tính từ số liệu đến 25/09/2026" in text
    assert "Máy tính của hệ thống — Phép tính: giá 76.500 đồng / BVPS 33.315,68 đồng" in text


def test_a_calculation_over_an_input_no_tool_returned_is_unverified():
    invented = _calc(
        "c3",
        "percent_change",
        [{"label": "giá", "value": 76500, "unit": "đồng"}, {"label": "giá cũ", "value": 40000, "unit": "đồng"}],
    )

    report = check("STB tăng 91,25% từ đầu năm.", [_market(), invented])

    [figure] = report.figures
    assert figure.status is FigureStatus.UNVERIFIED
    assert figure.reason == "calculation_inputs_unsupported"


def test_a_calculators_inputs_do_not_ground_themselves():
    """Only the result is offered: an input must stand on its own source."""
    calc = _calc(
        "c4",
        "divide",
        [{"label": "giá", "value": 99999, "unit": "đồng"}, {"label": "BVPS", "value": 33315.68, "unit": "đồng"}],
    )

    report = check("Giá 99.999 đồng.", [calc])

    assert [f.status for f in report.figures] == [FigureStatus.UNVERIFIED]
