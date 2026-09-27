"""The value index decides exactly what scanning every source line decided.

``Sources.lines_near`` narrows each figure to the lines whose values sit near
its magnitude; it may only ever skip lines on which no value could match. Each
case builds a Turn the way the tools write one — several tickers' bars, a
statement read, a page — and an answer whose figures sit on, beside and just
past the rounding boundary of what those sources print, in every period and
ticker context the check reads. Seeded, so a failure names a case that
reproduces.
"""

from __future__ import annotations

import random
import time
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.agent.evidence import grounding

from .test_agent_grounding import TODAY, decided, every_line, market_call, page_call, ratios_call

CASES = 60
SYMBOLS = ("STB", "TCB", "HPG", "FPT")


def _dotted(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _comma(value: Decimal, places: int) -> str:
    return f"{value:,.{places}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _bars(rng: random.Random, symbol: str, sessions: int) -> list[tuple[str, int, int]]:
    """Daily bars ending on the last session before TODAY, stepped by 50 đồng."""
    day, rows, close = TODAY, [], rng.randrange(10_000, 150_000, 50)
    while len(rows) < sessions:
        day -= timedelta(days=1)
        if day.weekday() < 5:
            close = max(1_000, close + rng.randrange(-1_500, 1_550, 50))
            rows.append((day.isoformat(), close, rng.randrange(100_000, 9_000_000, 10)))
    return rows[::-1]


def _spellings(rng: random.Random, close: int, volume: int) -> list[str]:
    """One close and one volume, written exactly, rounded and a step past rounding."""
    thousands = Decimal(close) / 1000
    nudge = rng.choice((-50, 50, -100, 100, 1, -1))
    return [
        f"{_dotted(close)} đồng",
        f"{_comma(thousands, 1)} nghìn đồng",
        f"{_comma(thousands, 2)} nghìn",
        f"{_dotted(close + nudge)} đồng",
        f"{_comma((Decimal(close) + nudge) / 1000, 1)} nghìn đồng",
        f"{_comma(Decimal(volume) / 1_000_000, 2)} triệu cổ phiếu",
        f"{_dotted(volume)} cổ phiếu",
        f"{_dotted(rng.randrange(10_000, 150_000, 100))} đồng",
    ]


def _case(seed: int) -> tuple[list, str]:
    rng = random.Random(seed)
    calls, bars = [], {}
    for symbol in SYMBOLS:
        bars[symbol] = _bars(rng, symbol, rng.randrange(20, 45))
        calls.append(market_call(bars[symbol], call_id=f"m-{symbol}-{seed}", symbol=symbol))
    roe, npl = Decimal(rng.randrange(500, 2500)) / 100, Decimal(rng.randrange(50, 400)) / 100
    calls.append(
        ratios_call(
            "STB",
            [
                f"2026-06-30: Quý 2/2026 · ROE {_comma(roe, 2)} % · NPL {_comma(npl, 2)} %",
                f"2025-12-31: Quý 4/2025 · ROE {_comma(roe - 1, 2)} % · NPL {_comma(npl + 1, 2)} %",
            ],
            call_id=f"r-{seed}",
        )
    )
    profit = rng.randrange(100, 50_000)
    published = TODAY - timedelta(days=rng.randrange(1, 200))
    calls.append(
        page_call(
            f"Lãi trước thuế {_dotted(profit)} tỷ đồng, cổ phiếu thay đổi -{_comma(npl, 2)}% "
            f"và vốn hóa {_dotted(profit * 7)} tỷ đồng.",
            published=published.isoformat() + "T08:00:00+07:00",
        )
    )

    lines = ["| Mã | Giá (đồng) | ROE (%) |", "| --- | --- | --- |"]
    for symbol in SYMBOLS:
        day, close, _ = rng.choice(bars[symbol])
        lines.append(f"| {symbol} | {_dotted(close)} | {_comma(roe, rng.choice((1, 2)))} |")
    for _ in range(rng.randrange(12, 20)):
        symbol = rng.choice(SYMBOLS)
        day, close, volume = rng.choice(bars[symbol][-5:] if rng.random() < 0.4 else bars[symbol])
        when = date.fromisoformat(day).strftime("%d/%m/%Y")
        figure = rng.choice(_spellings(rng, close, volume))
        subject = rng.choice((symbol, "", "VN-Index", rng.choice(SYMBOLS)))
        frame = rng.choice(
            (
                "Hiện tại {s} ở mức {f}.",
                "Ngày {d} {s} đóng cửa {f}.",
                "{s} từng chạm đỉnh {f}.",
                "{s} giao dịch {f}.",
                "Hôm qua {s} đóng {f}.",
                "Quý 2/2026 {s} có ROE {r}%.",
                "{s} giảm {n}% trong phiên {d}.",
                "{s} lãi {p} tỷ đồng, vốn hóa khoảng {c} nghìn tỷ.",
                "Theo giá hiện tại, P/E của {s} là {r}.",
            )
        )
        lines.append(
            frame.format(
                s=subject,
                f=figure,
                d=when,
                r=_comma(roe, rng.choice((1, 2))),
                n=_comma(npl + rng.choice((0, 0, Decimal("0.01"))), 2),
                p=_dotted(profit + rng.choice((0, 0, 1))),
                c=_comma(Decimal(profit * 7) / 1000, 1),
            )
        )
    return calls, "\n".join(lines)


def _both(calls, answer):
    report = grounding.check_answer(answer, grounding.collect_sources(calls), today=TODAY)
    with patch.object(grounding.Sources, "lines_near", every_line):
        scanned = grounding.check_answer(answer, grounding.collect_sources(calls), today=TODAY)
    return report, scanned


@pytest.mark.parametrize("seed", range(CASES))
def test_the_index_decides_every_figure_as_the_full_scan_does(seed):
    calls, answer = _case(seed)

    report, scanned = _both(calls, answer)

    assert decided(report) == decided(scanned)


def test_the_corpus_reaches_every_verdict_the_index_could_get_wrong():
    """Guard the generator itself: a corpus of only misses would prove nothing."""
    reasons, statuses = set(), set()
    for seed in range(CASES):
        report, _ = _both(*_case(seed))
        statuses |= {figure.status for figure in report.figures}
        reasons |= {figure.reason for figure in report.figures}

    assert statuses == set(grounding.FigureStatus)
    assert {"wrong_period", "not_in_sources", None} <= reasons


def test_a_long_turn_is_checked_in_well_under_a_second():
    """Eight tickers of a year's bars and a long answer: once took seconds.

    The bound is loose on purpose — a slow CI box must pass it — and still an
    order of magnitude under what scanning every line cost.
    """
    rng = random.Random(0)
    calls, lines = [], []
    for symbol in ("STB", "TCB", "VCB", "HPG", "FPT", "MWG", "VNM", "SSI"):
        rows = _bars(rng, symbol, 250)
        calls.append(market_call(rows, call_id=f"m-{symbol}", symbol=symbol))
        for _ in range(5):
            day, close, volume = rng.choice(rows)
            lines.append(
                f"- {symbol} ngày {date.fromisoformat(day).strftime('%d/%m/%Y')} đóng {_dotted(close)} đồng, "
                f"khối lượng {_dotted(volume)} cổ phiếu; hiện tại {_dotted(rows[-1][1])} đồng."
            )
    sources = grounding.collect_sources(calls)
    answer = "\n".join(lines)

    started = time.perf_counter()
    report = grounding.check_answer(answer, sources, today=TODAY)
    elapsed = time.perf_counter() - started

    assert len(report.figures) >= 100
    assert elapsed < 1.0, elapsed
