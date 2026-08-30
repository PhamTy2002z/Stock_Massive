"""Reading a number the way a page wrote it, and refusing the ones that are not there.

The rule this table enforces is the narrow one, and the narrowness is the point.
C1 measured what happens when a checker is allowed to *derive*: a page of two
hundred numbers supports almost any number under four arithmetic operations, so
a derivation check accepts fabrications at very nearly the rate it accepts
facts (``plans/260829-1945-c1-evidence-graduation``). So here nothing is
derived. A figure is on the page as written — including as the magnitude word
beside it scales it — or it is refused.

Two families of case, and they fail differently.

**Parsing** is about the separators. Vietnamese writes ``1.234,5`` and English
writes ``1,234.5``, both appear on the pages this reaches, and a parser that
picked one convention would silently read a thousand as a decimal on half the
web.

**Matching** is about coincidence. ``5`` is on every page ever published, so a
value that round is only accepted where its own unit is printed beside it, and
refused as ambiguous rather than accepted when there is no unit to check.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.agent.evidence import numbers
from src.agent.evidence.numbers import Verdict


# -- parsing: which mark is the decimal point ---------------------------------


@pytest.mark.parametrize(
    "token, expected",
    [
        # Vietnamese: dot groups thousands, comma is the decimal point.
        ("1.234,5", "1234.5"),
        ("12.345.678", "12345678"),
        ("302.528", "302528"),
        ("1.000", "1000"),
        ("12,5", "12.5"),
        ("0,75", "0.75"),
        ("99,99", "99.99"),
        # English: the other way round, and read correctly by the same rule.
        ("1,234.5", "1234.5"),
        ("12,345,678", "12345678"),
        ("1,500", "1500"),
        ("0.75", "0.75"),
        ("3.14159", "3.14159"),
        # No separator at all.
        ("5", "5"),
        ("42", "42"),
        ("1000000", "1000000"),
        # A group separator written as a space, which some tables do.
        ("1 234", "1234"),
        ("12 345 678", "12345678"),
        # Three digits after the mark means the mark grouped them, whichever
        # mark it was: ``1,500`` is fifteen hundred in both conventions.
        ("2,000", "2000"),
        ("2.000", "2000"),
        # Fewer or more than three means it is the decimal point.
        ("2,05", "2.05"),
        ("2.0512", "2.0512"),
    ],
)
def test_a_written_number_is_read_the_way_its_page_meant_it(token, expected):
    assert numbers.parse(token) == Decimal(expected)


def test_something_that_is_not_a_number_reads_as_nothing():
    assert numbers.parse("") is None
    assert numbers.parse("abc") is None


# -- parsing: how many digits carry information -------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("12.5", 3),
        ("1234", 4),
        ("100", 1),
        ("1200", 2),
        ("0.045", 2),
        ("3.2", 2),
        ("5", 1),
        ("10", 1),
        ("0", 1),
        ("302528", 6),
        # A trailing zero after the decimal point was printed on purpose.
        ("12.50", 4),
    ],
)
def test_significant_digits_counts_what_a_page_chose_to_print(value, expected):
    assert numbers.significant_digits(Decimal(value)) == expected


# -- reading a page ------------------------------------------------------------


def test_every_number_on_a_page_is_found_with_what_follows_it():
    found = numbers.occurrences("Doanh thu 3,2 nghìn tỷ, biên 12,5%, 5 chi nhánh.")

    assert [str(entry.written) for entry in found] == ["3.2", "12.5", "5"]


@pytest.mark.parametrize(
    "text, scaled",
    [
        ("3,2 nghìn tỷ", "3200000000000"),
        ("3,2 ngàn tỷ", "3200000000000"),
        ("4,5 tỷ", "4500000000"),
        ("4,5 tỉ", "4500000000"),
        ("120 triệu", "120000000"),
        ("12 nghìn", "12000"),
        ("2.5 billion", "2500000000"),
        ("300 million", "300000000"),
    ],
)
def test_a_magnitude_word_beside_a_number_scales_it(text, scaled):
    found = numbers.occurrences(f"Con số là {text} đồng.")

    assert found[0].scaled == Decimal(scaled)


def test_a_word_that_merely_starts_like_a_magnitude_is_not_one():
    """``tin`` must not read as ``tỉ``; a prefix match without a boundary would."""
    found = numbers.occurrences("Có 12 tin bài trong ngày.")

    assert found[0].scaled is None


# -- matching: the three verdicts ---------------------------------------------

PAGE = (
    "Lợi nhuận quý II đạt 3,2 nghìn tỷ đồng, tăng 12,5% so với cùng kỳ. "
    "Ngân hàng mở thêm 5 chi nhánh và giữ tỷ lệ nợ xấu ở 1,02%. "
    "Tổng tài sản 1.234.567 tỷ đồng."
)


def test_a_number_with_three_significant_digits_is_evidence_on_its_own():
    assert numbers.contains(PAGE, 12.5, "%") is Verdict.MATCHED
    assert numbers.contains(PAGE, 1.02, "%") is Verdict.MATCHED
    assert numbers.contains(PAGE, 1_234_567) is Verdict.MATCHED


def test_a_scaled_match_needs_no_unit_because_the_word_was_standing_there():
    assert numbers.contains(PAGE, 3_200_000_000_000) is Verdict.MATCHED


def test_a_number_written_as_the_page_writes_it_matches_with_its_unit():
    assert numbers.contains(PAGE, 3.2, "nghìn tỷ") is Verdict.MATCHED


def test_a_small_round_number_with_its_unit_beside_it_is_accepted():
    assert numbers.contains(PAGE, 5, "chi nhánh") is Verdict.MATCHED


def test_a_small_round_number_with_no_unit_is_refused_as_ambiguous():
    """The failure mode this whole gate exists for.

    ``5`` is on the page — and on every page — so accepting it would be
    accepting a coincidence as a citation. Refused, and refused under its own
    name so the model is told to bring the unit rather than told the number is
    absent.
    """
    assert numbers.contains(PAGE, 5) is Verdict.AMBIGUOUS


def test_a_small_number_whose_unit_is_somewhere_else_on_the_page_is_still_ambiguous():
    assert numbers.contains(PAGE, 5, "%") is Verdict.AMBIGUOUS


def test_a_number_that_is_not_printed_is_refused_as_absent():
    assert numbers.contains(PAGE, 13, "%") is Verdict.NOT_ON_PAGE
    assert numbers.contains(PAGE, 999.75) is Verdict.NOT_ON_PAGE


def test_a_scaled_figure_the_page_never_scaled_is_absent():
    """``12,5%`` is on the page; twelve and a half billion is not."""
    assert numbers.contains(PAGE, 12_500_000_000) is Verdict.NOT_ON_PAGE


def test_a_percentage_matches_whether_the_unit_is_the_sign_or_the_words():
    page = "Lãi suất điều hành giữ ở 4,5 phần trăm."

    assert numbers.contains(page, 4.5, "%") is Verdict.MATCHED
    assert numbers.contains(page, 4.5, "phần trăm") is Verdict.MATCHED


def test_a_unit_matches_without_its_diacritics_or_its_case():
    page = "Vốn điều lệ 45 nghìn tỷ Đồng."

    assert numbers.contains(page, 45, "đồng") is Verdict.MATCHED
    assert numbers.contains(page, 45, "NGHÌN TỶ") is Verdict.MATCHED


def test_a_year_is_not_a_value_unless_the_row_says_it_is():
    """A page is full of years, and a year has four significant digits.

    So ``2025`` *does* match — which is correct and is why the row's label
    matters: the check is that the number is printed there, not that it means
    what the model says it means. What must not happen is the opposite error, a
    year on the page passing for a figure that is not on it.
    """
    page = "Kết quả năm 2025 của ngân hàng."

    assert numbers.contains(page, 2025) is Verdict.MATCHED
    assert numbers.contains(page, 2026) is Verdict.NOT_ON_PAGE


def test_a_negative_value_matches_the_number_the_page_printed():
    page = "Lợi nhuận giảm -12,4% trong quý."

    assert numbers.contains(page, -12.4, "%") is Verdict.MATCHED


def test_a_page_that_printed_a_profit_does_not_confirm_a_loss():
    """The false accept this module could produce, and the worst one available.

    The assertion above passed for a year while the sign was being thrown away
    on both sides, because it cannot tell the two readings apart: a page
    printing ``-12,4`` and a claim of ``-12.4`` match whether or not anybody
    looked at the minus. This is the pair that can only pass one way.

    Sign is the highest-consequence digit in a financial figure. A board saying
    VIC lost 1.234 tỷ, sourced to a page reporting that it *earned* 1.234 tỷ, is
    a fabricated claim wearing a real citation — which is precisely the outcome
    the whole evidence path exists to make impossible.
    """
    profit = "Lợi nhuận sau thuế quý 3 đạt 1.234 tỷ đồng."

    assert numbers.contains(profit, 1234, "tỷ đồng") is Verdict.MATCHED
    assert numbers.contains(profit, -1234, "tỷ đồng") is not Verdict.MATCHED

    # And the other way round, which is the same mistake read backwards.
    loss = "Lỗ ròng -1.234 tỷ đồng trong quý."

    assert numbers.contains(loss, -1234, "tỷ đồng") is Verdict.MATCHED
    assert numbers.contains(loss, 1234, "tỷ đồng") is not Verdict.MATCHED


def test_the_digits_being_there_without_the_sign_is_ambiguous_rather_than_absent():
    """Three answers stay three answers, and the middle one earns its keep.

    "The page does not print this number" and "the page prints these digits and
    not this sign" are different facts, and a reader who is told the second can
    check the page. Told the first, they would look for something that is
    plainly there.
    """
    page = "Biên lợi nhuận tăng 12,4% so với cùng kỳ."

    assert numbers.contains(page, -12.4, "%") is Verdict.AMBIGUOUS
    assert numbers.contains(page, 99.9, "%") is Verdict.NOT_ON_PAGE


def test_a_filing_writes_a_minus_with_brackets():
    """The accounting convention, and it is the one the source documents use."""
    assert numbers.contains("Lợi nhuận (1.234) tỷ đồng.", -1234, "tỷ đồng") is (
        Verdict.MATCHED
    )
    # A bracket that is punctuation rather than a minus stays punctuation.
    assert numbers.contains("Xem thêm (mục 1.234) trong báo cáo.", -1234, "") is not (
        Verdict.MATCHED
    )


def test_a_range_is_not_a_negative_number():
    """``100-200`` is a band, and the hyphen in it is not a sign.

    The guard is what precedes the hyphen: a digit means the two numbers are a
    range, anything else means the hyphen belongs to the number after it.
    """
    page = "Dự báo doanh thu 100-200 tỷ đồng."

    assert numbers.contains(page, 200, "tỷ đồng") is Verdict.MATCHED
    assert numbers.contains(page, -200, "tỷ đồng") is not Verdict.MATCHED


def test_a_scaling_word_carries_the_sign_with_it():
    """The scaled reading is signed too, or the fix would hold on one path only."""
    page = "Lỗ ròng -1,2 nghìn tỷ đồng."

    assert numbers.contains(page, -1_200_000_000_000, "đồng") is Verdict.MATCHED
    assert numbers.contains(page, 1_200_000_000_000, "đồng") is not Verdict.MATCHED


def test_a_value_that_is_not_a_number_at_all_is_absent_rather_than_an_error():
    assert numbers.contains(PAGE, None) is Verdict.NOT_ON_PAGE
    assert numbers.contains(PAGE, True) is Verdict.NOT_ON_PAGE


def test_an_empty_page_holds_nothing():
    assert numbers.occurrences("") == ()
    assert numbers.contains("", 12.5, "%") is Verdict.NOT_ON_PAGE


def test_a_number_inside_a_longer_token_is_not_a_number_on_its_own():
    """``VN30`` is an index name, and ``30`` is not a figure the page reported."""
    page = "Rổ VN30 và mã ABC123 trong phiên."

    assert numbers.contains(page, 30, "mã") is Verdict.NOT_ON_PAGE
