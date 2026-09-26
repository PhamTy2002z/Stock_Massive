"""The figure check: what an answer may state, and what it is labelled when it may not.

Built around the Turn that motivated it (2026-09-26): market bars that closed
at 56.500 đồng, and an answer calling "35.000–38.000 đồng" the current price.
Prices here are invented; the shapes are the tools' own.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

from src.agent.evidence import grounding
from src.agent.evidence.contracts import VerificationVerdict, VerifierOutcome
from src.agent.evidence.grounding import FigureStatus
from src.agent.messages import ToolCallStatus, TurnToolCall

TODAY = date(2026, 9, 26)
AS_OF = datetime(2026, 9, 26, 7, 0, tzinfo=timezone.utc)


def market_call(rows: list[tuple[str, int, int]], *, call_id: str = "m1", symbol: str = "STB") -> TurnToolCall:
    """A market read whose excerpt is written the way the tool writes it."""
    lines = [f"{symbol} · nến ngày · nguồn KB Securities · giá đã quy đổi sang VND đầy đủ"]
    last_day, last_close, last_volume = rows[-1]
    lines.append(
        f"{last_day}T15:00:00+07:00: PHIÊN GẦN NHẤT "
        f"{date.fromisoformat(last_day).strftime('%d/%m/%Y')} (hôm nay 26/09/2026 chưa có phiên đóng cửa)"
        f" · đóng {last_close:,} đồng · khối lượng {last_volume:,} cổ phiếu".replace(",", ".")
    )
    for day, close, volume in rows:
        lines.append(
            f"{day}T15:00:00+07:00: mở {close:,} đồng · cao {close:,} đồng · thấp {close:,} đồng"
            f" · đóng {close:,} đồng · khối lượng {volume:,} cổ phiếu".replace(",", ".")
        )
    payload = {
        "symbol": symbol,
        "interval": "1D",
        "interval_label": "nến ngày",
        "source": "kbs",
        "publisher": "KB Securities",
        "source_class": "store",
        "actual": {"start": f"{rows[0][0]}T15:00:00+07:00", "end": f"{last_day}T15:00:00+07:00"},
        "retrieved_at": "2026-09-26T14:00:00+07:00",
        "content_sha256": hashlib.sha256(call_id.encode()).hexdigest(),
        "excerpt": "\n".join(lines),
    }
    return TurnToolCall(
        id=call_id,
        name="get_market_data",
        status=ToolCallStatus.OK,
        result_text=json.dumps(payload, ensure_ascii=False),
    )


def page_call(content: str, *, published: str | None, url: str = "https://cafef.vn/stb-2025.chn") -> TurnToolCall:
    payload = {
        "url": url,
        "canonical_url": url,
        "title": "Sacombank năm 2025",
        "publisher": "cafef.vn",
        "source_class": "media",
        "content": content,
        "retrieved_at": "2026-09-26T14:00:00+07:00",
        "content_sha256": "b" * 64,
        "publication": {"publishedAt": published} if published else {},
    }
    return TurnToolCall(
        id="p1", name="fetch_url", status=ToolCallStatus.OK, result_text=json.dumps(payload, ensure_ascii=False)
    )


def check(answer: str, calls: list[TurnToolCall], *, user_text: str = "") -> grounding.GroundingReport:
    sources = grounding.collect_sources(calls, user_text=user_text)
    return grounding.check_answer(answer, sources, today=TODAY)


def statuses(report: grounding.GroundingReport) -> dict[str, FigureStatus]:
    return {figure.text: figure.status for figure in report.figures}


STB = market_call(
    [("2025-09-25", 56_900, 6_594_300), ("2025-09-26", 56_500, 6_010_100)], call_id="old"
)
STB_NOW = market_call(
    [("2026-09-24", 76_900, 2_073_800), ("2026-09-25", 76_500, 1_606_900)], call_id="now"
)


# -- the motivating Turn ---------------------------------------------------


def test_the_invented_current_price_is_labelled_unverified():
    report = check("Hiện tại (tháng 9/2025): giao dịch quanh 35.000-38.000 đồng.", [STB])

    assert statuses(report) == {
        "35.000": FigureStatus.UNVERIFIED,
        "38.000 đồng": FigureStatus.UNVERIFIED,
    }


def test_a_last_years_close_called_current_is_the_wrong_period():
    """The price is real — a year old. "Hiện tại" is what makes it wrong."""
    report = check("Giá hiện tại là 56.500 đồng.", [STB, STB_NOW])

    [figure] = report.figures
    assert figure.status is FigureStatus.UNVERIFIED
    assert figure.reason == "wrong_period"


def test_the_latest_session_quoted_as_current_is_grounded_and_dated():
    report = check("Giá hiện tại là 76.500 đồng.", [STB, STB_NOW])

    [figure] = report.figures
    assert figure.status is FigureStatus.GROUNDED
    assert figure.source_date == date(2026, 9, 25)
    assert "[1 · phiên 25/09/2026]" in grounding.annotate(report)


def test_a_historical_close_named_with_its_date_is_grounded():
    report = check("Ngày 26/09/2025 STB đóng cửa ở 56.500 đồng.", [STB, STB_NOW])

    [figure] = report.figures
    assert figure.status is FigureStatus.GROUNDED
    assert figure.source_date == date(2025, 9, 26)


# -- how a figure may be written -------------------------------------------


def test_the_same_price_in_every_way_a_sentence_writes_it():
    for written in ("76.500 đồng", "76,5 nghìn đồng", "76.5k", "76500 đồng"):
        report = check(f"Phiên gần nhất đóng cửa {written}.", [STB_NOW])
        assert [f.status for f in report.figures] == [FigureStatus.GROUNDED], written


def test_billions_and_rounding_to_the_precision_written():
    page = page_call(
        "Tổng tài sản đạt 909.084 tỷ đồng, vốn hóa 111.228 tỷ đồng, NPL 6,31%.",
        published="2026-08-20T08:00:00+07:00",
    )
    report = check(
        "Tổng tài sản 909.084 tỷ đồng, vốn hóa khoảng 111,2 nghìn tỷ, NPL 6,31%.", [page]
    )

    assert all(f.status is FigureStatus.GROUNDED for f in report.figures), statuses(report)
    # A rounding that went the wrong way is not a rounding.
    wrong = check("Vốn hóa khoảng 112,5 nghìn tỷ.", [page])
    assert [f.status for f in wrong.figures] == [FigureStatus.UNVERIFIED]


def test_a_fall_written_with_a_direction_word_matches_a_signed_source():
    page = page_call("Cổ phiếu thay đổi -0,65% trong phiên.", published="2026-09-25T16:00:00+07:00")

    report = check("STB giảm 0,65% trong phiên 25/09/2026.", [page])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]


def test_a_self_computed_growth_rate_is_unverified_before_a_calculator_exists():
    report = check("Từ đầu năm STB đã tăng khoảng 50-60%.", [STB_NOW])

    assert statuses(report) == {"60%": FigureStatus.UNVERIFIED}


# -- what is not a figure --------------------------------------------------


def test_dates_years_quarters_counts_and_list_markers_are_not_checked():
    answer = (
        "### 1. Tổng quan\n"
        "1. Trong 3 tháng qua, quý 2/2026 và năm 2025, top 10 ngân hàng.\n"
        "Kế hoạch đến 2030, phiên 14:30 ngày 25/09/2026."
    )

    assert check(answer, [STB_NOW]).figures == ()


def test_numbers_the_reader_wrote_are_theirs():
    report = check(
        "Với giá mua 50.000 đồng bạn đang lãi so với 76.500 đồng.",
        [STB_NOW],
        user_text="Tôi mua STB giá 50.000 đồng",
    )

    assert statuses(report) == {"76.500 đồng": FigureStatus.GROUNDED}


# -- time, for web sources -------------------------------------------------


def test_an_old_page_is_stale_and_says_so():
    page = page_call("Tỷ lệ nợ xấu 6,31%.", published="2026-01-07T08:00:00+07:00")

    report = check("Tỷ lệ nợ xấu 6,31%.", [page])

    [figure] = report.figures
    assert figure.status is FigureStatus.STALE
    assert "[1 · 07/01/2026 · nguồn cũ]" in grounding.annotate(report)


def test_a_page_published_after_the_period_it_reports_is_in_time():
    page = page_call("Tỷ lệ nợ xấu cuối năm 2025 là 6,31%.", published="2026-01-07T08:00:00+07:00")

    report = check("Cuối 2025, NPL 6,31%.", [page])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]


def test_a_page_published_before_the_period_cannot_report_it():
    page = page_call("NPL dự kiến 6,31%.", published="2024-06-01T08:00:00+07:00")

    report = check("Cuối 2025, NPL 6,31%.", [page])

    [figure] = report.figures
    assert figure.status is FigureStatus.UNVERIFIED
    assert figure.reason == "wrong_period"


def test_structured_data_wins_over_a_page_for_the_same_figure():
    page = page_call("STB đóng cửa 76.500 đồng.", published="2026-09-25T16:00:00+07:00")

    report = check("STB đóng cửa 76.500 đồng.", [page, STB_NOW])

    [figure] = report.figures
    assert figure.kind is grounding.SourceKind.STRUCTURED


# -- tools that failed -----------------------------------------------------


def test_a_failed_market_read_backs_nothing():
    failed = TurnToolCall(
        id="m1", name="get_market_data", status=ToolCallStatus.ERROR, result_text=STB_NOW.result_text
    )

    report = check("Giá hiện tại 76.500 đồng.", [failed])

    assert [f.status for f in report.figures] == [FigureStatus.UNVERIFIED]


# -- the periods a sentence names ------------------------------------------


def test_periods_read_the_ways_a_sentence_names_time():
    named, current = grounding.periods("Quý 2/2026 so với tháng 9/2025, hiện tại", TODAY)

    spans = {(p.start, p.end) for p in named}
    assert (date(2026, 4, 1), date(2026, 6, 30)) in spans
    assert (date(2025, 9, 1), date(2025, 9, 30)) in spans
    assert current is True
    # A day without a year is this year's, or last year's if it has not come yet.
    [(day)] = grounding.periods("phiên 25/09", TODAY)[0]
    assert day.start == date(2026, 9, 25)


# -- what is written back --------------------------------------------------


def test_annotation_labels_in_place_and_lists_dated_sources():
    page = page_call("NPL 6,31%.", published="2026-08-20T08:00:00+07:00")
    report = check("STB đóng 76.500 đồng hôm qua. NPL 6,31%. ROE 99,99%.", [STB_NOW, page])

    text = grounding.annotate(report)

    assert "76.500 đồng [1 · phiên 25/09/2026]" in text
    assert "6,31% [2 · 20/08/2026]" in text
    assert "99,99% [chưa kiểm chứng]" in text
    assert "**Nguồn số liệu**" in text
    assert "[2] cafef.vn — Sacombank năm 2025 — đăng 20/08/2026" in text


def test_without_citations_only_failures_are_labelled():
    report = check("STB đóng 76.500 đồng. ROE 99,99%.", [STB_NOW])

    text = grounding.annotate(report, cite=False)

    assert "[1 ·" not in text
    assert "99,99% [chưa kiểm chứng]" in text


def test_an_answer_without_figures_is_returned_untouched():
    report = check("Xin chào, tôi có thể giúp gì?", [])

    assert grounding.annotate(report) == "Xin chào, tôi có thể giúp gì?"


def test_the_repair_note_lists_the_figures_and_the_latest_session():
    report = check("Hiện tại 35.000 đồng.", [STB_NOW])

    note = grounding.repair_note(report)

    assert '"35.000 đồng"' in note
    assert "Hôm nay là 26/09/2026" in note
    assert "PHIÊN GẦN NHẤT 25/09/2026" in note
    assert "Hiện tại 35.000 đồng." in note


def test_the_ledger_has_one_claim_per_figure_and_cites_only_what_backed_one():
    report = check("Giá hiện tại 76.500 đồng. ROE 99,99%.", [STB_NOW, STB])

    ledger = grounding.to_ledger(report, as_of=AS_OF)

    verdicts = [claim.verdict for claim in ledger.claims]
    assert verdicts == [VerificationVerdict.SINGLE_SOURCE, VerificationVerdict.UNSUPPORTED]
    assert len(ledger.evidence) == 1
    assert ledger.verifier_outcome is VerifierOutcome.INSUFFICIENT_EVIDENCE
    assert ledger.to_payload()["version"] == grounding.LEDGER_VERSION
