"""Whether a number the model wrote is actually printed on the page it cites.

A question outside this deployment's store still deserves a picture: an interest
rate, a competitor that never listed, a figure inside a news story. The only
honest way to draw one is to copy the number off a page — and the moment a model
is allowed to copy a number, it is allowed to make one up, because from the far
side of the wire those two look identical.

So this module answers exactly one question, mechanically: **is this number on
that page**. Not "could it be derived from that page", which is the trap C1
measured and abandoned — a page of two hundred numbers supports almost any
number under four arithmetic operations, so a derivation check accepts
fabrications at nearly the rate it accepts facts. Here the test is the literal
one. The number is on the page as written, or it is refused by name.

Two things make the literal test harder than a substring search, and both are
about how Vietnamese pages actually write numbers.

**The separators are the other way round.** ``1.234,5`` is one thousand two
hundred thirty four and a half, and ``1,234.5`` is the same figure written the
English way. Both appear, sometimes on the same page, so the parse decides per
token: when both marks are present the *last* one is the decimal point, and when
only one is present it is a group separator exactly when it is followed by three
digits.

**A magnitude is a word, not a suffix.** A page says ``3,2 nghìn tỷ`` and never
``3200000000000``, so a match is looked for against both the number as written
and the number the following word scales it to. A scaled match is safe on its
own, because the scaling word had to be standing right there for it to happen.

**And a small round number matches by accident.** ``5`` and ``10`` appear on
every page ever published, so a value with fewer than three significant digits
is accepted only where the row's own unit is printed beside it. With no unit to
check, such a row is refused as ambiguous rather than accepted — a false accept
here is a fabricated figure wearing a citation, which is worse than no picture.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

#: How many significant digits make a number specific enough that finding it on
#: a page is evidence rather than coincidence. Three: a page of market prose
#: holds most one- and two-digit numbers by chance and almost no three-digit
#: ones by chance.
SIGNIFICANT_DIGITS_FLOOR = 3

#: How far past a number to look for its unit. Long enough for ``12,5 nghìn tỷ
#: đồng`` and short enough that the next sentence's words are not read as this
#: number's unit.
UNIT_WINDOW = 28

#: The words that scale a number, and by how much. Both spellings of the
#: Vietnamese billion are here because both are printed; the English ones because
#: half the sources a question like this reaches are in English.
MAGNITUDES: tuple[tuple[str, Decimal], ...] = (
    ("nghin ty", Decimal(10) ** 12),
    ("ngan ty", Decimal(10) ** 12),
    ("trillion", Decimal(10) ** 12),
    ("ty", Decimal(10) ** 9),
    ("ti", Decimal(10) ** 9),
    ("billion", Decimal(10) ** 9),
    ("bn", Decimal(10) ** 9),
    ("trieu", Decimal(10) ** 6),
    ("million", Decimal(10) ** 6),
    ("mn", Decimal(10) ** 6),
    ("nghin", Decimal(10) ** 3),
    ("ngan", Decimal(10) ** 3),
    ("thousand", Decimal(10) ** 3),
)

#: One number as a page writes it. Grouped thousands first, so ``1.234`` is read
#: whole rather than as ``1`` followed by ``234``.
_NUMBER = re.compile(
    r"(?<![\w.,])"
    r"(?:\d{1,3}(?:[.,    ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"(?![\d])"
)

_GROUP_SPACES = (" ", " ", " ", " ")


#: How a page writes a minus. The hyphen-minus a keyboard produces and the true
#: minus sign a typesetter produces; the en dash is deliberately absent, because
#: a page writing ``100\u2013200 tỷ`` means a range, and reading its second number
#: as negative would invent a loss out of a forecast.
_MINUS = ("-", "\u2212")

#: How a financial statement writes a minus. Parentheses around the figure are
#: the accounting convention, and the Vietnamese filings this reads use it — so a
#: cell reading ``(1.234)`` is a number below zero rather than a cross-reference.
_OPEN_BRACKET = "("
_CLOSE_BRACKET = ")"


class Verdict(str, Enum):
    """What looking for one number on one page found."""

    #: Printed on the page, specifically enough to be that number.
    MATCHED = "matched"
    #: Not printed on the page in any form this reads.
    NOT_ON_PAGE = "not_on_page"
    #: Printed, but too round to be told apart from a coincidence, and the row
    #: named no unit to confirm it by.
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Occurrence:
    """One number found on a page, as written and as any word beside it scales it.

    ``written`` and ``scaled`` carry the sign the page printed. They did not, for
    a while, and the consequence was the worst false accept this module can
    produce: a page reporting a profit of 1.234 tỷ confirmed a claim of a *loss*
    of 1.234 tỷ, because both sides were compared as magnitudes. Sign is the
    highest-consequence digit in a financial figure — lãi against lỗ, tăng
    against giảm — and it is the one a reader cannot recover from the rest of
    the sentence.
    """

    written: Decimal
    scaled: Decimal | None
    start: int
    end: int
    trailing: str

    @property
    def values(self) -> tuple[Decimal, ...]:
        return (self.written,) if self.scaled is None else (self.written, self.scaled)


def fold(text: str) -> str:
    """Lowercase and without diacritics, for comparing a unit to what a page prints.

    Vietnamese ``đ`` is handled by hand because it is a letter rather than a
    letter with a mark on it, so decomposition leaves it alone — and ``đồng`` is
    the single most common unit a page here will carry.
    """
    lowered = text.replace("đ", "d").replace("Đ", "D").lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def parse(token: str) -> Decimal | None:
    """One written number as a Decimal, deciding which mark is the decimal point.

    Both marks present: the last one is the decimal point and the other groups
    thousands, which reads ``1.234,5`` and ``1,234.5`` alike and correctly. One
    mark present: it groups thousands exactly when three digits follow it, so
    ``12,5`` is twelve and a half and ``1,500`` is fifteen hundred.
    """
    cleaned = token
    for space in _GROUP_SPACES:
        cleaned = cleaned.replace(space, "")
    if not cleaned:
        return None

    has_dot = "." in cleaned
    has_comma = "," in cleaned
    if has_dot and has_comma:
        decimal_mark = "." if cleaned.rfind(".") > cleaned.rfind(",") else ","
        group_mark = "," if decimal_mark == "." else "."
        cleaned = cleaned.replace(group_mark, "").replace(decimal_mark, ".")
    elif has_dot or has_comma:
        mark = "." if has_dot else ","
        head, _, tail = cleaned.rpartition(mark)
        groups = cleaned.count(mark) > 1
        cleaned = (
            (head + tail).replace(mark, "")
            if groups or len(tail) == 3
            else f"{head.replace(mark, '')}.{tail}"
        )
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def occurrences(page: str) -> tuple[Occurrence, ...]:
    """Every number printed on this page, signed, with what follows each one."""
    text = page or ""
    found: list[Occurrence] = []
    for match in _NUMBER.finditer(text):
        written = parse(match.group())
        if written is None:
            continue
        if _is_negative(text, match.start(), match.end()):
            written = -written
        trailing = text[match.end() : match.end() + UNIT_WINDOW]
        factor = _magnitude(trailing)
        found.append(
            Occurrence(
                written=written,
                scaled=None if factor is None else written * factor,
                start=match.start(),
                end=match.end(),
                trailing=trailing,
            )
        )
    return tuple(found)


def _is_negative(page: str, start: int, end: int) -> bool:
    """Whether the page wrote this number below zero.

    Two notations, and one guard against a third thing that looks like one.

    A minus binds to the number only when what precedes *it* is not a digit:
    ``lãi -12,4%`` is a fall and ``100-200 tỷ`` is a range, and the two are the
    same character. Reading the range as a sign would turn a forecast band into
    a loss.

    Parentheses count only when they wrap the number — an opening bracket
    immediately before and a closing bracket immediately after — so ``(xem
    1.234)`` in prose is not a negative number.
    """
    if start > 0 and page[start - 1] in _MINUS:
        return start < 2 or not page[start - 2].isdigit()
    return (
        start > 0
        and page[start - 1] == _OPEN_BRACKET
        and end < len(page)
        and page[end] == _CLOSE_BRACKET
    )


def significant_digits(value: Decimal) -> int:
    """How many digits of this number carry information.

    Trailing zeros are dropped only from a whole number: ``1200`` says two digits
    and ``12.50`` says four, because a page that printed the second one chose to
    print that last zero.
    """
    normalised = value.copy_abs()
    digits = "".join(str(digit) for digit in normalised.as_tuple().digits)
    digits = digits.lstrip("0")
    if normalised.as_tuple().exponent >= 0:
        digits = digits.rstrip("0")
    return len(digits) or 1


def contains(page: str, value: object, unit: str | None = None) -> Verdict:
    """Whether this number, with this unit, is printed on this page.

    Three answers rather than two, because "not there" and "there but it could be
    any 5 on the page" are different facts and lead to different refusals.
    """
    target = _decimal(value)
    if target is None:
        return Verdict.NOT_ON_PAGE
    magnitude = target.copy_abs()
    unit_key = fold(unit).strip() if unit else ""
    saw_the_digits = False

    for occurrence in occurrences(page):
        if occurrence.scaled is not None:
            if _same(occurrence.scaled, target):
                # A scaling word had to be standing beside the number for this
                # to be reachable at all, so the word is the unit and there is
                # nothing left to confirm.
                return Verdict.MATCHED
            if _same(occurrence.scaled.copy_abs(), magnitude):
                saw_the_digits = True
                continue
        if not _same(occurrence.written.copy_abs(), magnitude):
            continue
        saw_the_digits = True
        if not _same(occurrence.written, target):
            # The digits are on the page and the sign is not. A page reporting a
            # profit does not support a claim of a loss, so this falls through to
            # ``AMBIGUOUS``: the reader is told the figure could not be
            # confirmed, which is true, rather than shown a number wearing a
            # citation that contradicts it.
            continue
        if significant_digits(occurrence.written) >= SIGNIFICANT_DIGITS_FLOOR:
            return Verdict.MATCHED
        if unit_key and _unit_beside(occurrence, unit_key):
            return Verdict.MATCHED

    if not saw_the_digits:
        return Verdict.NOT_ON_PAGE
    return Verdict.AMBIGUOUS


def _unit_beside(occurrence: Occurrence, unit_key: str) -> bool:
    """Whether the row's unit is printed right after the number it belongs to."""
    trailing = fold(occurrence.trailing)
    if unit_key in ("%", "phan tram"):
        return trailing.lstrip().startswith("%") or "phan tram" in trailing
    return unit_key in trailing


def _magnitude(trailing: str) -> Decimal | None:
    """The factor the word after a number scales it by, if there is one."""
    folded = fold(trailing).lstrip()
    for word, factor in MAGNITUDES:
        if folded.startswith(word):
            # A word boundary, so ``tin`` does not read as ``ti``.
            rest = folded[len(word) :]
            if not rest or not rest[0].isalnum():
                return factor
    return None


def _same(left: Decimal, right: Decimal) -> bool:
    return left.compare(right) == 0


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        return parse(value.strip())
    return None


__all__ = [
    "MAGNITUDES",
    "SIGNIFICANT_DIGITS_FLOOR",
    "UNIT_WINDOW",
    "Occurrence",
    "Verdict",
    "contains",
    "fold",
    "occurrences",
    "parse",
    "significant_digits",
]
