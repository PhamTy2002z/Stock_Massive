"""Company events, news and the screener: what they print, and how the figure
check reads it. Records have the shapes Vietcap and KB returned on 2026-09-26,
with invented values."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pytest

from src.agent.evidence import grounding
from src.agent.evidence.grounding import FigureStatus
from src.agent.messages import ToolCallStatus, TurnToolCall
from src.agent.registry import ToolContext
from src.agent.tools import company, financials, screener
from src.agent.tools.market_data import ICT, INTERNAL_PROFILE
from src.agent.tools.vnstock_provider import MarketDataError
from src.core.config import Settings

NOW = datetime(2026, 9, 26, 14, 0, tzinfo=ICT)
CONTEXT = ToolContext(user_id=1, now=NOW)

EVENTS = [
    {
        "event_title_vi": "Trả cổ tức bằng tiền mặt - Cả năm 2025 - 450 VND",
        "public_date": "2026-07-14T00:00:00",
        "exright_date": "2026-07-23",
        "record_date": "2026-07-24",
        "payout_date": "2026-08-27T00:00:00",
        "value_per_share": 450.0,
        "exercise_ratio": 0.045,
    },
    {
        "event_title_vi": "VCB - Tổ chức ĐHĐCĐ thường niên 2026",
        "display_date1": "2026-04-22T00:00:00",
        "public_date": "2026-02-26",
    },
    {"event_title_vi": "Không có ngày"},
]

NEWS = [
    {"news_title": "VCB: Thông báo thay đổi nhân sự", "public_date": "2026-09-23T17:40:53"},
    {"news_title": "VCB: Lợi nhuận quý 2 đạt 17.420 tỷ đồng", "public_date": "2026-07-30T08:00:00"},
]


def settings(**overrides: Any) -> Settings:
    return Settings(**{"deployment_profile": INTERNAL_PROFILE, "market_data_enabled": True, **overrides})


def company_tools(monkeypatch, records: list[dict[str, Any]]) -> company.CompanyTools:
    tools = company.CompanyTools(settings=settings())
    monkeypatch.setattr(tools, "_read", lambda symbol, method: records)
    return tools


def as_call(call_id: str, name: str, payload: Any) -> TurnToolCall:
    return TurnToolCall(id=call_id, name=name, status=ToolCallStatus.OK, result_text=json.dumps(dict(payload), ensure_ascii=False))


def check(answer: str, calls: list[TurnToolCall]) -> grounding.GroundingReport:
    return grounding.check_answer(answer, grounding.collect_sources(calls), today=NOW.date())


# -- events and news --------------------------------------------------------


def test_an_event_line_leads_with_the_date_it_is_about(monkeypatch):
    result = company_tools(monkeypatch, EVENTS).get_company_events(CONTEXT, {"symbol": "VCB"})

    lines = result["excerpt"].splitlines()
    assert lines[1].startswith("2026-07-23: Trả cổ tức bằng tiền mặt")
    assert "450 đồng/cổ phiếu (tỷ lệ 4,5%)" in lines[1]
    assert "ngày GDKHQ 23/07/2026" in lines[1] and "ngày thanh toán 27/08/2026" in lines[1]
    assert lines[2].startswith("2026-04-22: VCB - Tổ chức ĐHĐCĐ")
    assert result["item_count"] == 2  # an undated event is dropped, not guessed


def test_a_dividend_figure_is_grounded_to_its_ex_right_date(monkeypatch):
    result = company_tools(monkeypatch, EVENTS).get_company_events(CONTEXT, {"symbol": "VCB"})

    report = check("VCB trả cổ tức 450 đồng/cổ phiếu, GDKHQ ngày 23/07/2026.", [as_call("e1", "get_company_events", result)])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]
    assert "ngày 23/07/2026" in grounding.annotate(report)


def test_news_is_dated_by_publication_and_an_old_item_is_stale(monkeypatch):
    result = company_tools(monkeypatch, NEWS).get_company_news(CONTEXT, {"symbol": "VCB"})
    call = as_call("n1", "get_company_news", result)

    assert result["excerpt"].splitlines()[1].startswith("2026-09-23: VCB: Thông báo thay đổi nhân sự")
    report = check("Lợi nhuận quý 2 của VCB đạt 17.420 tỷ đồng.", [call])
    [figure] = report.figures
    assert figure.status is FigureStatus.STALE  # 58 days old, past the 30-day window
    dated = check("Lợi nhuận quý 2/2026 của VCB đạt 17.420 tỷ đồng.", [call])
    assert [f.status for f in dated.figures] == [FigureStatus.GROUNDED]


def test_company_tools_refuse_an_index_and_an_empty_feed(monkeypatch):
    with pytest.raises(MarketDataError):
        company_tools(monkeypatch, EVENTS).get_company_events(CONTEXT, {"symbol": "VNINDEX"})
    with pytest.raises(MarketDataError):
        company_tools(monkeypatch, []).get_company_news(CONTEXT, {"symbol": "VCB"})


# -- the screener -----------------------------------------------------------

BOARD = {
    "STB": {"close_price": 76500, "percent_change": -0.52, "volume_accumulated": 1606900, "total_value": 123950000000, "foreign_buy_volume": 165000, "foreign_sell_volume": 321805},
    "VCB": {"close_price": 58000, "percent_change": 0.87, "volume_accumulated": 2000000, "total_value": 116000000000, "foreign_buy_volume": 500000, "foreign_sell_volume": 100000},
    "TCB": {"close_price": 33250, "percent_change": 1.2, "volume_accumulated": 5000000, "total_value": 166250000000, "foreign_buy_volume": 0, "foreign_sell_volume": 0},
}
SESSION_MS = datetime(2026, 9, 25, 14, 45, tzinfo=ICT).timestamp() * 1000
PB = {"STB": 2.30, "VCB": 1.95, "TCB": 1.25}


class FakeVci:
    def __init__(self, covered: set[str]) -> None:
        self.covered = covered
        self.calls = 0

    def ratios(self, symbol: str, *, quarterly: bool, periods: int) -> financials.Statement:
        self.calls += 1
        if symbol not in self.covered:
            raise MarketDataError("rate_limited", "quota")
        period = financials.Period(
            year=2026, quarter=2, ended=date(2026, 6, 30), published=None,
            figures=(financials.Figure("P/B", PB[symbol], "lần"), financials.Figure("Tỷ lệ nợ xấu (NPL)", 1.0, "%")),
        )
        return financials.Statement(symbol=symbol, publisher="Vietcap", source="vci", periods=(period,))


LISTINGS = {"ngân hàng": ["STB", "VCB", "TCB"], "vn30": ["FPT", "TCB", "VCB", "STB"]}


def screen(covered: set[str], **arguments: Any) -> tuple[dict[str, Any], FakeVci]:
    fake = FakeVci(covered)
    tools = screener.ScreenerTools(
        settings=settings(),
        ratios=fake,
        quality=fake,
        board=lambda symbols: [{"symbol": s, "time": SESSION_MS, **BOARD[s]} for s in symbols if s in BOARD],
        listing=lambda name: LISTINGS[name.casefold()],
    )
    return dict(tools.screen_stocks(CONTEXT, arguments)), fake


def test_market_filters_rank_from_one_board_read():
    result, fake = screen(set(), universe="Ngân hàng", filters=[{"field": "change_pct", "op": ">", "value": 0}], sort_by="change_pct")

    assert result["symbols"] == ["TCB", "VCB"]
    assert fake.calls == 0  # no reported field asked for, no per-ticker read
    assert "2026-09-25: TCB · giá 33.250 đồng · thay đổi +1,20%" in result["excerpt"]


def test_reported_filters_name_the_tickers_not_yet_covered():
    result, _ = screen({"VCB", "TCB"}, universe="Ngân hàng", filters=[{"field": "pb", "op": "<", "value": 2}], sort_by="pb", descending=False)

    assert result["symbols"] == ["TCB", "VCB"]
    assert result["not_covered"] == ["STB"]
    assert "Chưa đọc được số liệu báo cáo" in result["excerpt"] and "STB" in result["excerpt"].splitlines()[-1]
    assert "2026-06-30: TCB · quý 2/2026 · P/B 1,25 lần" in result["excerpt"]


def test_screener_figures_are_grounded_per_part_and_per_ticker():
    result, _ = screen({"VCB", "TCB", "STB"}, symbols=["TCB", "VCB"], filters=[{"field": "pb", "op": "<", "value": 2}])
    call = as_call("s1", "screen_stocks", result)

    ok = check("TCB có P/B 1,25 lần (quý 2/2026), giá hiện tại 33.250 đồng.", [call])
    assert [f.status for f in ok.figures] == [FigureStatus.GROUNDED, FigureStatus.GROUNDED]
    text = grounding.annotate(ok)
    assert "kỳ đến 30/06/2026" in text and "phiên 25/09/2026" in text
    # VCB's P/B is on the same result, but not TCB's.
    wrong = check("TCB có P/B 1,95 lần.", [call])
    assert [f.status for f in wrong.figures] == [FigureStatus.UNVERIFIED]


def test_the_screener_refuses_what_it_cannot_run():
    with pytest.raises(MarketDataError):
        screen(set())
    with pytest.raises(MarketDataError):
        screen(set(), universe="Ngân hàng", filters=[{"field": "dividend", "op": ">", "value": 1}])


def test_a_universe_is_narrowed_by_industry():
    result, _ = screen(set(), universe="VN30", industry="Ngân hàng", sort_by="price")

    assert result["universe"] == "VN30 · Ngân hàng"
    assert result["symbols"] == ["STB", "VCB", "TCB"]  # FPT is not a bank


def test_a_slow_source_is_cut_off_and_its_tickers_named(monkeypatch):
    import time as _time

    monkeypatch.setattr(screener, "FUNDAMENTALS_BUDGET_SECONDS", 0.05)

    class Slow(FakeVci):
        def ratios(self, symbol: str, **kwargs: Any) -> financials.Statement:
            _time.sleep(0.3)
            return super().ratios(symbol, **kwargs)

    slow = Slow({"STB", "VCB", "TCB"})
    tools = screener.ScreenerTools(
        settings=settings(), ratios=slow, quality=slow,
        board=lambda symbols: [{"symbol": s, "time": SESSION_MS, **BOARD[s]} for s in symbols if s in BOARD],
        listing=lambda name: LISTINGS[name.casefold()],
    )

    result = dict(tools.screen_stocks(CONTEXT, {"universe": "Ngân hàng", "filters": [{"field": "pb", "op": "<", "value": 5}]}))

    assert result["symbols"] == []
    assert sorted(result["not_covered"]) == ["STB", "TCB", "VCB"]
