"""The figure check: what an answer may state, and what it is labelled when it may not.

Built around the Turn that motivated it (2026-09-26): market bars that closed
at 56.500 đồng, and an answer calling "35.000–38.000 đồng" the current price.
Prices here are invented; the shapes are the tools' own.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from unittest.mock import patch

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


def every_line(sources: grounding.Sources, wanted: object) -> list[tuple[object, object]]:
    """``Sources.lines_near`` without the index: every line of every source, in order."""
    return [(source, line) for source in sources.items for line in source.lines]


def decided(report: grounding.GroundingReport) -> tuple[object, ...]:
    """Everything a report decides and everything a reader is shown from it."""
    return (
        report.figures,
        grounding.annotate(report),
        grounding.annotate(report, cite=False),
        grounding.repair_note(report),
        grounding.to_ledger(report, as_of=AS_OF).to_payload(),
    )


def check(answer: str, calls: list[TurnToolCall], *, user_text: str = "") -> grounding.GroundingReport:
    """The check, and proof that the value index changed none of it.

    Every hand-written case here is also decided by scanning every source line,
    the way the check did before lines were looked up by magnitude.
    """
    sources = grounding.collect_sources(calls, user_text=user_text)
    report = grounding.check_answer(answer, sources, today=TODAY)
    with patch.object(grounding.Sources, "lines_near", every_line):
        scanned = grounding.check_answer(
            answer, grounding.collect_sources(calls, user_text=user_text), today=TODAY
        )
    assert decided(report) == decided(scanned)
    return report


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

    # Both ends of the range are claims: the start takes the end's unit.
    assert statuses(report) == {"50": FigureStatus.UNVERIFIED, "60%": FigureStatus.UNVERIFIED}


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
    named, current = grounding.periods("Quý 2/2026 và tháng 9/2025, hiện tại", TODAY)

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


def test_a_dated_price_called_current_must_still_be_the_latest_session():
    """The live miss of 2026-09-26: a real close, correctly dated, a year old."""
    report = check("Giá hiện tại: 56.500 đồng (tính đến 26/09/2025).", [STB, STB_NOW])

    [figure] = report.figures
    assert figure.status is FigureStatus.UNVERIFIED
    assert figure.reason == "wrong_period"


def test_two_reads_of_one_symbol_are_told_apart_by_their_range():
    report = check("Phiên 25/09/2026 đóng 76.500 đồng; phiên 26/09/2025 đóng 56.500 đồng.", [STB, STB_NOW])

    text = grounding.annotate(report)

    assert "STB · nến ngày · 24/09/2026–25/09/2026" in text
    assert "STB · nến ngày · 25/09/2025–26/09/2025" in text


def test_a_snippet_and_its_page_are_one_citation():
    page = page_call("NPL 6,31%. CAR 12,50%.", published="2026-08-20T08:00:00+07:00")
    snippet = TurnToolCall(
        id="s1",
        name="web_search",
        status=ToolCallStatus.OK,
        result_text=json.dumps(
            {
                "results": [
                    {
                        "url": "https://cafef.vn/stb-2025.chn",
                        "canonical_url": "https://cafef.vn/stb-2025.chn",
                        "title": "Sacombank năm 2025",
                        "publisher": "cafef.vn",
                        "snippet": "CAR 12,50%",
                        "publication": {"publishedAt": "2026-08-20T08:00:00+07:00"},
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    report = check("NPL 6,31%, CAR 12,50%.", [snippet, page])

    text = grounding.annotate(report)

    assert "[2 ·" not in text
    assert text.count("cafef.vn — Sacombank năm 2025") == 1


def test_a_date_after_so_voi_is_a_comparison_not_the_figures_period():
    report = check("Giá: 76.500 đồng (so với phiên 24/09).", [STB_NOW])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]


def test_a_recent_peak_is_not_a_claim_about_now():
    peak = market_call(
        [("2026-09-11", 79_000, 3_000_000), ("2026-09-25", 76_500, 1_606_900)], call_id="peak"
    )

    report = check("Đỉnh gần nhất: 79.000 đồng (ngày 11/09).", [peak])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]


def test_a_volume_rounded_to_millions_is_the_volume():
    report = check("Khối lượng phiên 25/09 đạt 1,6 triệu cổ phiếu.", [STB_NOW])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]
    # Two digits still have to round correctly.
    wrong = check("Khối lượng phiên 25/09 đạt 1,8 triệu cổ phiếu.", [STB_NOW])
    assert [f.status for f in wrong.figures] == [FigureStatus.UNVERIFIED]


def test_a_page_cannot_price_a_session_the_market_feed_prices_differently():
    """The live miss: "22/9 | 1.775,09" backed by a weekly page, while 22/09 closed at 76.900."""
    page = page_call("Chỉ số đóng cửa 76.500 trong tuần.", published="2026-09-25T16:00:00+07:00")

    report = check("| 24/9 | 76.500 |", [STB_NOW, page])

    [figure] = report.figures
    assert figure.status is FigureStatus.UNVERIFIED
    assert figure.reason == "conflicts_with_market_data"
    # A figure no price feed could speak to is still the page's.
    other = check("Ngày 24/9 khối ngoại bán ròng 4.000 tỷ đồng.", [STB_NOW, page_call("Bán ròng 4.000 tỷ đồng.", published="2026-09-25T16:00:00+07:00")])
    assert [f.status for f in other.figures] == [FigureStatus.GROUNDED]


def test_a_bare_decimal_in_a_table_is_a_figure_not_a_count():
    """The live miss: "| LPB | 0.86 |" was skipped as if it were "top 10"."""
    report = check("| LPB | 0.86 |", [STB_NOW])

    assert [f.status for f in report.figures] == [FigureStatus.UNVERIFIED]
    assert check("Trong 3 tháng, top 10 mã.", [STB_NOW]).figures == ()


def test_the_readers_threshold_is_theirs_whatever_unit_the_answer_adds():
    report = check("Có 9 mã có P/B dưới 1,5 lần.", [STB_NOW], user_text="mã nào có P/B dưới 1,5?")

    assert report.figures == ()


def test_labels_the_model_wrote_are_removed_before_the_check() -> None:
    draft = (
        "Bổ nhiệm Phó TGĐ cuối 2025 [1 · tháng 5/2026]\n"
        "| Ông Đức | Tháng 5/2026 [1 · tháng 5/2026] | Cựu lãnh đạo LPBank [1 · tháng 5/2026] |\n"
        "ROE 9% [chưa kiểm chứng]"
    )
    assert grounding.normalise(draft) == (
        "Bổ nhiệm Phó TGĐ cuối 2025\n"
        "| Ông Đức | Tháng 5/2026 | Cựu lãnh đạo LPBank |\n"
        "ROE 9%"
    )
    # Links and plain brackets are prose, not labels.
    assert grounding.normalise("xem [báo cáo](https://a.vn) [1]") == "xem [báo cáo](https://a.vn) [1]"


def test_a_full_date_no_source_names_is_unverified():
    page = page_call(
        "Ông Loic Faussier chính thức giữ chức Tổng giám đốc từ ngày 10/7. "
        "Quyết định ký ngày 08-07-2026.",
        published="2026-07-11T08:00:00+07:00",
    )
    answer = (
        "Nhậm chức 13/07/2026, theo quyết định ký 08/07/2026, hiệu lực 10/07/2026. "
        "Tin đăng 11/07/2026; bạn hỏi về 01/01/2026; hôm nay 26/09/2026."
    )
    report = check(answer, [page], user_text="Từ 01/01/2026 STB đổi lãnh đạo thế nào?")

    assert [(item.text, item.reason) for item in report.unverified] == [
        ("13/07/2026", "date_not_in_sources")
    ]
    annotated = grounding.annotate(report)
    assert "Nhậm chức 13/07/2026 [chưa kiểm chứng]" in annotated
    assert "ngày này không có trong dữ liệu" in grounding.repair_note(report)


def test_a_month_a_year_and_a_link_are_not_dates_to_check():
    report = check("Bổ nhiệm tháng 5/2026, năm 2025, xem https://a.vn/tin-13/07/2026.", [])
    assert report.unverified == ()


def test_tr_is_millions_and_a_wrong_magnitude_still_fails():
    volume = market_call([("2026-09-25", 76_500, 14_512_300)], call_id="mv")
    right = check("Khối lượng phiên gần nhất 14,5tr cổ phiếu.", [volume])
    wrong = check("Khối lượng phiên gần nhất 14,5tr cổ phiếu, trang 3.", [market_call([("2026-09-25", 76_500, 14_512)], call_id="mw")])

    assert [f.status for f in right.figures] == [FigureStatus.GROUNDED]
    assert [f.status for f in wrong.figures] == [FigureStatus.UNVERIFIED]


def test_a_net_sell_written_as_a_word_matches_a_signed_net_buy():
    screen = TurnToolCall(
        id="s1",
        name="screen_stocks",
        status=ToolCallStatus.OK,
        result_text=json.dumps(
            {
                "publisher": "KB Securities",
                "source": "screener",
                "source_class": "store",
                "title": "Lọc cổ phiếu · Bất động sản",
                "retrieved_at": "2026-09-26T14:00:00+07:00",
                "content_sha256": "c" * 64,
                "excerpt": "2026-09-25: NVL · khối ngoại mua ròng -1.723.800 cổ phiếu",
            },
            ensure_ascii=False,
        ),
    )
    report = check("NVL phiên 25/09/2026: khối ngoại bán ròng 1,72tr cổ phiếu.", [screen])
    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]


# -- a table's column names the period ---------------------------------------


def ratios_call(symbol: str, lines: list[str], *, call_id: str = "r1") -> TurnToolCall:
    """A statements read written the way ``get_financial_ratios`` writes its excerpt."""
    payload = {
        "symbol": symbol,
        "publisher": "Vietcap",
        "source": "vci",
        "source_class": "store",
        "evidence_kind": "store_figure",
        "title": f"{symbol} · chỉ số tài chính · Quý 2/2026",
        "as_of": "2026-06-30T00:00:00+07:00",
        "retrieved_at": "2026-09-26T14:00:00+07:00",
        "content_sha256": hashlib.sha256(call_id.encode()).hexdigest(),
        "excerpt": "\n".join(
            [f"{symbol} · chỉ số tài chính · nguồn Vietcap · mỗi dòng bắt đầu bằng ngày kết thúc kỳ", *lines]
        ),
    }
    return TurnToolCall(
        id=call_id,
        name="get_financial_ratios",
        status=ToolCallStatus.OK,
        result_text=json.dumps(payload, ensure_ascii=False),
    )


HPG_RATIOS = ratios_call(
    "HPG",
    [
        "2026-06-30: Quý 2/2026 · Nợ/Vốn CSH 0,97 lần · ROE 17,38%",
        "2025-12-31: Quý 4/2025 · Nợ/Vốn CSH 0,91 lần · ROE 12,69%",
    ],
)


def test_a_cell_filled_from_another_quarter_than_its_column_is_the_wrong_period():
    """The live miss (2026-09-27): the Q4/2025 column held Q2/2026's 0,97, cited to 30/06/2026."""
    report = check(
        "| Chỉ số | Quý 4/2025 | Quý 2/2026 |\n|---|---|---|\n| Nợ/Vốn CSH | 0,97 lần | 0,97 lần |",
        [HPG_RATIOS],
    )

    first, second = report.figures
    assert (first.status, first.reason) == (FigureStatus.UNVERIFIED, "wrong_period")
    assert second.status is FigureStatus.GROUNDED
    assert second.source_date == date(2026, 6, 30)


def test_a_cell_matching_its_columns_quarter_is_grounded():
    report = check(
        "| Chỉ số | Q4/2025 | Q2/2026 |\n|:--|:-:|:-:|\n| ROE | 12,69% | 17,38% |",
        [HPG_RATIOS],
    )

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED] * 2
    assert [f.source_date for f in report.figures] == [date(2025, 12, 31), date(2026, 6, 30)]


def test_a_ticker_column_scopes_the_cell_to_that_tickers_statements():
    """Row periods, ticker columns: MWG's column cannot rest on PNJ's line."""
    mwg = ratios_call("MWG", ["2026-06-30: Quý 2/2026 · Biên lợi nhuận gộp 22,17%"], call_id="a")
    pnj = ratios_call("PNJ", ["2026-06-30: Quý 2/2026 · Biên lợi nhuận gộp 18,43%"], call_id="b")
    report = check("| Kỳ | MWG | PNJ |\n|---|---|---|\n| Q2/2026 | 18,43% | 18,43% |", [mwg, pnj])

    assert [f.status for f in report.figures] == [FigureStatus.UNVERIFIED, FigureStatus.GROUNDED]


def _calendar_checks(answer: str, *, market_closed: bool) -> list[tuple[str, str]]:
    report = grounding.check_answer(
        answer,
        grounding.collect_sources([]),
        today=date(2026, 9, 27),
        market_closed=market_closed,
    )
    return [
        (item.text, item.reason)
        for item in report.unverified
        if item.reason and ("weekday" in item.reason or item.reason == "no_session_today")
    ]


def test_a_weekday_the_calendar_contradicts_is_unverified_and_the_note_names_the_right_one():
    """kiro-glm-5, 2026-09-27: "Hôm nay 27/09/2026 là thứ Bảy" on a Sunday."""
    answer = "Hôm nay 27/09/2026 là **thứ Bảy**, thị trường nghỉ."
    assert _calendar_checks(answer, market_closed=True) == [("thứ Bảy", "wrong_weekday:Chủ nhật")]
    report = grounding.check_answer(
        answer, grounding.collect_sources([]), today=date(2026, 9, 27)
    )
    assert "ngày đó là Chủ nhật" in grounding.repair_note(report)

    for right in (
        "Hôm nay 27/09/2026 là Chủ nhật.",
        "Phiên thứ Sáu, 25/09/2026 VN-Index giảm.",
        "thứ 7 ngày 26/09/2026 không có phiên.",
    ):
        assert _calendar_checks(right, market_closed=True) == []


def test_a_session_narrated_as_today_on_a_closed_day_is_unverified():
    """kiro-glm-5, 2026-09-27 (Sunday): "Phiên hôm nay 27/09/2026 chưa có dữ liệu đóng cửa"."""
    answer = "Phiên hôm nay 27/09/2026 chưa có dữ liệu đóng cửa."
    assert _calendar_checks(answer, market_closed=True) == [
        ("Phiên hôm nay 27/09/2026 chưa có", "no_session_today")
    ]
    # On a trading day the same sentence is simply true.
    assert _calendar_checks(answer, market_closed=False) == []
    assert _calendar_checks("Phiên gần nhất 25/09/2026 giảm.", market_closed=True) == []


def test_a_market_figure_only_an_older_row_prints_is_the_wrong_period_on_an_undated_line():
    """kiro-glm-5, 2026-09-27: "Khối lượng: 1,99 triệu cổ phiếu" under the 25/09 close
    matched only the 16/07 row of a three-month window."""
    vnm = market_call(
        [("2026-07-16", 60_100, 1_990_000), ("2026-09-25", 59_800, 3_120_500)],
        call_id="vnm",
        symbol="VNM",
    )

    undated = check("Khối lượng: 1,99 triệu cổ phiếu.", [vnm])
    peak = check("Khối lượng cao nhất 3 tháng: 1,99 triệu cổ phiếu.", [vnm])
    latest = check("Khối lượng: 3,12 triệu cổ phiếu.", [vnm])

    assert [(f.status, f.reason) for f in undated.figures] == [(FigureStatus.UNVERIFIED, "wrong_period")]
    assert [f.source_date for f in peak.figures] == [date(2026, 7, 16)]
    assert [f.source_date for f in latest.figures] == [date(2026, 9, 25)]


def test_a_reported_ratio_said_to_be_priced_today_is_unverified_with_its_own_reason():
    """kiro-glm-5, 2026-09-27: "P/B 2,21 lần (tính theo giá đóng cửa gần nhất)" was P/B at 30/06."""
    msn = ratios_call("MSN", ["2026-06-30: Quý 2/2026 · P/B 2,21 lần"], call_id="msn")

    claimed = check("P/B 2,21 lần (tính theo giá đóng cửa gần nhất).", [msn])
    plain = check("P/B quý 2/2026 là 2,21 lần.", [msn])

    assert [(f.status, f.reason) for f in claimed.figures] == [
        (FigureStatus.UNVERIFIED, "priced_at_period_end")
    ]
    assert "calculate" in grounding.repair_note(claimed)
    assert [f.status for f in plain.figures] == [FigureStatus.GROUNDED]


FTSE_PAGE = page_call(
    "Tuần qua VN-Index lên 1.785,11 điểm. VN30 giảm 1,31%, xuống 1.938,50 điểm. "
    "FTSE Russell phân bổ theo 4 giai đoạn: 10% trong tháng 9/2026, 20% vào tháng 3/2027. "
    "GPBank chào 9,1-9,3%.",
    published="2026-09-26T08:00:00+07:00",
    url="https://thoibaotaichinhvietnam.vn/chung-khoan-tuan-cuoi-quy-iii-2026.html",
)
INDEX_ROWS = market_call(
    [("2026-09-24", 1_775, 900_000), ("2026-09-25", 1_785, 950_000)], call_id="vni", symbol="VNINDEX"
)


def test_what_a_live_turn_read_on_a_page_is_grounded_whatever_else_was_read():
    """Replayed from 2026-09-27 (Turn 5a0a911a): four page figures were labelled wrongly."""
    report = check(
        "| Chỉ số | Đóng cửa 25/9 | Biến động tuần |\n|---|---|---|\n"
        "| VN30-Index | 1.938,50 điểm | -1,31% |\n\n"
        "- Tháng 3/2027: 20%\n"
        "- GPBank chào 9,1-9,3%",
        [INDEX_ROWS, FTSE_PAGE],
    )

    # VN-Index's row cannot contradict VN30; "giảm 1,31%" is -1,31%; a planned
    # tranche is published before its month; a range's start carries its end's unit.
    assert [(f.text, f.status) for f in report.figures] == [
        ("1.938,50 điểm", FigureStatus.GROUNDED),
        ("1,31%", FigureStatus.GROUNDED),
        ("20%", FigureStatus.GROUNDED),
        ("9,1", FigureStatus.GROUNDED),
        ("9,3%", FigureStatus.GROUNDED),
    ]


def test_an_index_level_the_same_index_row_prices_otherwise_still_conflicts():
    report = check("VN-Index đóng cửa 25/9 ở 1.938,50 điểm.", [INDEX_ROWS, FTSE_PAGE])

    assert [(f.status, f.reason) for f in report.figures] == [
        (FigureStatus.UNVERIFIED, "conflicts_with_market_data")
    ]


def test_a_price_path_and_a_comparison_quarter_do_not_date_the_figure():
    """Replayed 2026-09-27: a path of earlier closes, and "so với Q3/2025" beside a Q2/2026 ratio."""
    ssi = market_call(
        [("2026-07-27", 17_600, 900_000), ("2026-09-18", 21_650, 950_000), ("2026-09-25", 20_700, 990_000)],
        call_id="ssi",
        symbol="SSI",
    )
    stb = ratios_call("STB", ["2026-06-30: Quý 2/2026 · Tỷ lệ nợ xấu 7,54%"], call_id="stb")

    path = check("Biến động mạnh: 17.600 → 21.650 → 20.700 đồng.", [ssi])
    compared = check("Nợ xấu tăng lên 7,54%, gấp 3 lần so với Q3/2025.", [stb])

    assert [f.status for f in path.figures] == [FigureStatus.GROUNDED] * 3
    assert [f.status for f in compared.figures if f.text == "7,54%"] == [FigureStatus.GROUNDED]


def test_an_english_page_grounds_vnd_figures_and_dates_written_its_way():
    """Replayed 2026-09-27 (NVL): "VND64.2 trillion" and "As of September 30" were unreadable."""
    page = page_call(
        "As of September 30, 2025, total borrowings stood at more than VND64.2 trillion "
        "($2.44 billion), including nearly VND29.6 trillion in bonds.",
        published="2025-11-17T08:00:00+07:00",
        url="https://theinvestor.vn/novaland-debt.html",
    )

    report = check("Tổng nợ vay (30/09/2025): VND 64,2 nghìn tỷ, trái phiếu 29,6 nghìn tỷ.", [page])

    assert [f.status for f in report.figures if f.status is FigureStatus.UNVERIFIED] == []


def test_a_cell_takes_the_unit_its_column_header_states():
    """kiro-glm-5, 2026-09-27: "| Quý | ROE (%) |" with bare "13,75" cells; Vietcap prints "13,75%"."""
    dgc = ratios_call(
        "DGC",
        ["2026-06-30: Quý 2/2026 · ROE 4 quý gần nhất 13,75% · Nợ/Vốn CSH 0,19 lần"],
        call_id="dgc",
    )

    report = check(
        "| Quý | ROE (%) | Nợ/Vốn chủ sở hữu (lần) |\n|---|---|---|\n| Quý 2/2026 | 13,75 | 0,19 |",
        [dgc],
    )

    assert [(f.text, f.status) for f in report.figures] == [
        ("13,75", FigureStatus.GROUNDED),
        ("0,19", FigureStatus.GROUNDED),
    ]


def test_a_twenty_session_average_through_the_calculator_is_grounded():
    """Measured 2026-09-27: asked for volume against its 20-session average, the model
    summed twenty rows in its head and divided the sum — no operation took the rows
    themselves, and the ceiling of twelve inputs could not hold them."""
    from src.agent.registry import ToolContext
    from src.agent.tools import calculator

    rows = [(f"2026-08-{day:02d}", 76_000, 1_000_000 + day * 10_000) for day in range(3, 23)]
    market = market_call(rows, call_id="m20")
    inputs = [{"label": f"KL {day}", "value": volume, "unit": "cổ phiếu"} for day, _, volume in rows]
    payload = calculator.CalculatorTools().calculate(ToolContext(user_id=1), {"operation": "average", "inputs": inputs})
    calc = TurnToolCall(
        id="c20", name="calculate", status=ToolCallStatus.OK, result_text=json.dumps(dict(payload), ensure_ascii=False)
    )

    assert payload["result_text"] == "1.125.000,00 cổ phiếu"
    report = check("Khối lượng trung bình 20 phiên là 1.125.000 cổ phiếu.", [market, calc])
    [figure] = report.figures
    assert figure.status is FigureStatus.GROUNDED


# -- an English answer is checked and labelled the same way ----------------
#
# The model answers in the language of the question (owner decision,
# 2026-09-27): these mirror the Vietnamese cases above with an English draft,
# to show the same figure check and the same labels, only in English.


def test_the_invented_current_price_is_labelled_unverified_in_english():
    report = check("Currently, trading around 35,000-38,000 dong.", [STB])

    assert statuses(report) == {
        "35,000": FigureStatus.UNVERIFIED,
        "38,000 dong": FigureStatus.UNVERIFIED,
    }


def test_the_latest_session_quoted_as_current_is_grounded_and_dated_in_english():
    report = check("The current price is 76,500 dong.", [STB, STB_NOW])

    [figure] = report.figures
    assert figure.status is FigureStatus.GROUNDED
    assert figure.source_date == date(2026, 9, 25)
    assert "[1 · session 25/09/2026]" in grounding.annotate(report)


def test_english_currency_units_match_a_vietnamese_source():
    """``76,500 VND`` in an English answer matches a tool's ``76.500 đồng``."""
    report = check("STB is trading at 76,500 VND.", [STB_NOW])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]


def test_a_fall_written_with_a_direction_word_matches_a_signed_source_in_english():
    page = page_call("The stock changed -1.31% during the session.", published="2026-09-25T16:00:00+07:00")

    report = check("VN30 is down 1.31% in the session on 25/09/2026.", [page])

    assert [f.status for f in report.figures] == [FigureStatus.GROUNDED]


def test_an_old_page_is_stale_and_says_so_in_english():
    page = page_call("The bad debt ratio is 6.31%.", published="2026-01-07T08:00:00+07:00")

    report = check("The bad debt ratio is 6.31%.", [page])

    [figure] = report.figures
    assert figure.status is FigureStatus.STALE
    assert "[1 · 07/01/2026 · stale source]" in grounding.annotate(report)


def test_annotation_labels_and_footer_notes_are_english_for_an_english_answer():
    page = page_call("NPL is 6.31%.", published="2026-08-20T08:00:00+07:00")
    report = check("STB closed at 76,500 dong yesterday. NPL 6.31%. ROE 99.99%.", [STB_NOW, page])

    text = grounding.annotate(report)

    assert "76,500 dong [1 · session 25/09/2026]" in text
    assert "6.31% [2 · 20/08/2026]" in text
    assert "99.99% [unverified]" in text
    assert "**Sources**" in text
    assert "[unverified] are not in this turn's tool data" in text


def test_a_weekday_the_calendar_contradicts_is_unverified_and_the_note_names_the_right_one_in_english():
    """The English mirror of the kiro-glm-5 miss: a wrong weekday beside a real date."""
    answer = "Today 27/09/2026 is **Saturday**, the market is closed."
    assert _calendar_checks(answer, market_closed=True) == [("Saturday", "wrong_weekday:Chủ nhật")]
    report = grounding.check_answer(
        answer, grounding.collect_sources([]), today=date(2026, 9, 27)
    )
    assert "that date is Sunday" in grounding.repair_note(report)

    for right in (
        "Today 27/09/2026 is Sunday.",
        "Session Friday, 25/09/2026 VN-Index fell.",
    ):
        assert _calendar_checks(right, market_closed=True) == []
