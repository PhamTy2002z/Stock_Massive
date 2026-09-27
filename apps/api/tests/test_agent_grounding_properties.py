"""Invariants of the figure check, over generated answers rather than written ones.

No golden answers: each case is built so the right verdict follows from how it
was built — a figure copied from the source is grounded and dated, a figure
moved away from every source value is not, and labelling never changes the
words it labels. Seeded, so a failure names a case that reproduces.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from src.agent.evidence import grounding
from src.agent.evidence.grounding import FigureStatus
from src.agent.evidence.source_policy import stale_year, years_in_scope

from .test_agent_grounding import TODAY, market_call, page_call

CASES = 200


def _dotted(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _session(rng: random.Random) -> tuple[list[tuple[str, int, int]], int]:
    """Two sessions ending on the last one before TODAY, and the latest close."""
    closes = [rng.randrange(10_000, 200_000, 100) for _ in range(2)]
    rows = [
        ("2026-09-24", closes[0], rng.randrange(100_000, 9_000_000)),
        ("2026-09-25", closes[1], rng.randrange(100_000, 9_000_000)),
    ]
    return rows, closes[1]


def _check(answer: str, calls) -> grounding.GroundingReport:
    return grounding.check_answer(
        answer, grounding.collect_sources(calls), today=TODAY
    )


@pytest.mark.parametrize("seed", range(CASES))
def test_the_latest_close_copied_in_any_spelling_is_grounded_on_its_session(seed):
    rng = random.Random(seed)
    rows, close = _session(rng)
    spelled = rng.choice(
        [f"{_dotted(close)} đồng", f"{_dotted(close)}đ", f"{close / 1000:.1f}".replace(".", ",") + " nghìn đồng"]
    )
    if close % 100 and "nghìn" in spelled:
        pytest.skip("one decimal of nghìn cannot spell this close")

    report = _check(f"Giá hiện tại của STB là {spelled}.", [market_call(rows, call_id=f"m{seed}")])

    [figure] = report.figures
    assert figure.status is FigureStatus.GROUNDED, (spelled, figure)
    assert figure.source_date == date(2026, 9, 25)


@pytest.mark.parametrize("seed", range(CASES))
def test_a_price_no_source_printed_is_never_grounded(seed):
    rng = random.Random(seed)
    rows, _ = _session(rng)
    printed = {close for _, close, _ in rows}
    invented = rng.randrange(10_000, 200_000, 100)
    while any(abs(invented - value) <= 1_000 for value in printed):
        invented = rng.randrange(10_000, 200_000, 100)

    report = _check(
        f"Giá hiện tại của STB là {_dotted(invented)} đồng.",
        [market_call(rows, call_id=f"m{seed}")],
    )

    assert [figure.status for figure in report.figures] == [FigureStatus.UNVERIFIED]


@pytest.mark.parametrize("seed", range(CASES))
def test_a_page_figure_is_grounded_as_written_and_unverified_when_shifted(seed):
    rng = random.Random(seed)
    profit = rng.randrange(100, 50_000)
    published = date(2026, 9, 26) - timedelta(days=rng.randrange(1, 90))
    page = page_call(
        f"Sacombank báo lãi trước thuế {_dotted(profit)} tỷ đồng trong 6 tháng đầu năm.",
        published=published.isoformat() + "T08:00:00+07:00",
    )
    shifted = profit + rng.choice([-1, 1]) * max(2, profit // 10)

    same = _check(f"STB lãi trước thuế {_dotted(profit)} tỷ đồng.", [page])
    moved = _check(f"STB lãi trước thuế {_dotted(shifted)} tỷ đồng.", [page])

    assert [f.status for f in same.figures] == [FigureStatus.GROUNDED]
    assert same.figures[0].source_date == published
    assert [f.status for f in moved.figures] == [FigureStatus.UNVERIFIED]


FILLER = (
    "Thị trường có nhiều biến động.",
    "Nhà đầu tư nên theo dõi thêm.",
    "Đây là thông tin tham khảo.",
)


@pytest.mark.parametrize("seed", range(CASES))
def test_surrounding_prose_changes_no_verdict_and_labels_change_no_words(seed):
    """Metamorphic: the same claims among other sentences get the same verdicts.

    And the labelled answer, labels removed, is the answer: a label that lands
    inside a word or duplicates text would break a reader's copy of it.
    """
    rng = random.Random(seed)
    rows, close = _session(rng)
    invented = close + rng.choice([-1, 1]) * rng.randrange(5_000, 9_000, 100)
    calls = [market_call(rows, call_id=f"m{seed}")]
    claims = [
        f"Giá hiện tại là {_dotted(close)} đồng.",
        f"Mục tiêu ngắn hạn {_dotted(invented)} đồng.",
    ]
    plain = " ".join(claims)
    padded = []
    for claim in claims:
        padded.extend(rng.sample(FILLER, rng.randrange(0, 3)))
        padded.append(claim)
    padded_answer = "\n".join(padded)

    verdicts = [f.status for f in _check(plain, calls).figures]
    padded_report = _check(padded_answer, calls)

    assert [f.status for f in padded_report.figures] == verdicts
    labelled = grounding.annotate(padded_report).split("\n\n---\n\n")[0]
    assert grounding.normalise(labelled) == padded_answer.rstrip()


WEEKDAYS = ("thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ nhật")


@pytest.mark.parametrize("seed", range(CASES))
def test_a_weekday_is_flagged_exactly_when_the_calendar_disagrees(seed):
    rng = random.Random(seed)
    when = date(2020, 1, 1) + timedelta(days=rng.randrange(0, 4000))
    written = rng.randrange(7)
    spelled = when.strftime("%d/%m/%Y")
    answer = rng.choice(
        [f"Ngày {spelled} là {WEEKDAYS[written]}.", f"{WEEKDAYS[written]}, {spelled} có phiên."]
    )

    report = grounding.check_answer(answer, grounding.collect_sources([]), today=TODAY)
    flagged = [f.reason for f in report.figures if f.reason and f.reason.startswith("wrong_weekday")]

    if written == when.weekday():
        assert flagged == []
    else:
        assert flagged == [f"wrong_weekday:{WEEKDAYS[when.weekday()]}"]


@pytest.mark.parametrize("seed", range(CASES))
def test_a_dated_search_in_last_year_is_refused_unless_the_question_names_it(seed):
    rng = random.Random(seed)
    today = date(2026, 9, 27)
    when = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 365))
    query = rng.choice(
        [
            f"giá STB ngày {when.day}/{when.month}/{when.year}",
            f"chứng khoán tháng {when.month} {when.year}",
        ]
    )

    def refused(question: str) -> int | None:
        return stale_year(
            "web_search", {"query": query}, today=today, in_scope=years_in_scope(question, today=today)
        )

    assert refused("Giá STB hôm nay thế nào?") == 2025
    assert refused(f"So với năm {when.year} thì sao?") is None
    assert refused("So với cùng kỳ năm ngoái?") is None
    current = query.replace(str(when.year), str(today.year))
    assert stale_year("web_search", {"query": current}, today=today, in_scope=frozenset({today.year})) is None
