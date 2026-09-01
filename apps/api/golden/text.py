"""The primitives every grader compares with: numbers, markers, URLs, instants.

They live in their own module because two files now need them and a copy in the
second one is a copy that drifts. Nothing here decides anything — each function
answers one question about one string, and the graders decide.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

#: A bare integer at or below this is a count, a rank or a month far more often
#: than it is a claim about the world, and treating it as a claim buries the
#: real findings in noise.
SMALL_INTEGER_CEILING = 12

#: A bare four-digit integer in this range is read as a year, not as a figure.
YEAR_RANGE = range(1900, 2100)

_NUMBER = re.compile(r"\d[\d.,]*")
_TRAILING_SEPARATORS = re.compile(r"[.,]+$")
_URL = re.compile(r"https?://[^\s<>\)\]\"'，、。]+", re.IGNORECASE)
_URL_TAIL = re.compile(r"[.,;:!?]+$")


# -- numbers ---------------------------------------------------------------


def parse_number(token: str) -> Decimal | None:
    """One numeric token as a value, or ``None`` when it is not one."""
    cleaned = _TRAILING_SEPARATORS.sub("", token.strip())
    if not cleaned or not cleaned[0].isdigit():
        return None
    dots = cleaned.count(".")
    commas = cleaned.count(",")
    if dots and commas:
        # Whichever separator comes last is the decimal point.
        decimal_sep = "." if cleaned.rfind(".") > cleaned.rfind(",") else ","
    elif dots or commas:
        sep = "." if dots else ","
        groups = cleaned.split(sep)
        # ``1.234`` groups as thousands, ``1.23`` cannot: a thousands group is
        # always exactly three digits and never the first one.
        thousands = len(groups) > 1 and all(len(g) == 3 for g in groups[1:])
        decimal_sep = None if thousands else sep
    else:
        decimal_sep = None

    if decimal_sep is None:
        digits = cleaned.replace(".", "").replace(",", "")
    else:
        other = "," if decimal_sep == "." else "."
        digits = cleaned.replace(other, "").replace(decimal_sep, ".")
    try:
        return Decimal(digits).normalize()
    except (InvalidOperation, ValueError):
        return None


def canonical_numbers(text: str) -> set[Decimal]:
    """Every number in ``text``, as one canonical value each.

    Vietnamese and English number formats share the same two separators with
    opposite meanings — ``1.234,5`` and ``1,234.5`` are the same quantity — so a
    string comparison would call an answer uncited purely because the page that
    supports it writes numbers the other way round.
    """
    found: set[Decimal] = set()
    for match in _NUMBER.finditer(text or ""):
        value = parse_number(match.group(0))
        if value is not None:
            found.add(value)
    return found


def is_claim(value: Decimal) -> bool:
    """Whether a number is worth asking for a source for."""
    if value != value.to_integral_value():
        return True
    integral = int(value)
    if abs(integral) <= SMALL_INTEGER_CEILING:
        return False
    if integral in YEAR_RANGE and len(str(abs(integral))) == 4:
        return False
    return True


def covered(value: Decimal, evidence: Iterable[Decimal]) -> bool:
    """Whether one answer number is supported by one of the evidence numbers.

    Exact first, then rounding: an answer saying ``12,3`` where the page says
    ``12,34`` has rounded rather than invented.
    """
    places = -value.as_tuple().exponent
    for candidate in evidence:
        if candidate == value:
            return True
        if places >= 0:
            try:
                if round(candidate, places) == value:
                    return True
            except (InvalidOperation, ValueError):
                continue
    return False


def within_tolerance(stated: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    """Whether a stated figure matches a frozen one inside a relative tolerance.

    Relative rather than absolute, because the ground truth of this corpus runs
    from a policy rate of ``4.5`` to a share count in the billions, and one
    absolute window cannot serve both. A tolerance of zero means exact.
    """
    if tolerance <= 0:
        return stated == expected
    if expected == 0:
        return abs(stated) <= tolerance
    return abs(stated - expected) <= abs(expected) * tolerance


# -- text ------------------------------------------------------------------


def fold(text: str) -> str:
    """Case-folded, whitespace-collapsed text for marker matching.

    Diacritics are **kept**. Stripping them would make ``không`` match ``khong``
    and also make unrelated Vietnamese words collide, and the markers this
    compares are written the way the prompt writes them.
    """
    normalised = unicodedata.normalize("NFC", text or "")
    return re.sub(r"\s+", " ", normalised).casefold()


def matched_markers(text: str, markers: Sequence[str]) -> tuple[str, ...]:
    """Which of ``markers`` appear in ``text``, in the order they were declared.

    Returns the markers rather than a boolean so that a finding can say *which*
    phrase it matched. A marker grader whose detail line reads only "matched" is
    a grader nobody can audit.
    """
    folded = fold(text)
    return tuple(marker for marker in markers if fold(marker) in folded)


# -- URLs ------------------------------------------------------------------


def urls_in(text: str) -> tuple[str, ...]:
    """Every URL printed in ``text``, trailing punctuation removed."""
    return tuple(_URL_TAIL.sub("", match.group(0)) for match in _URL.finditer(text or ""))


def canonical_url(url: str) -> str:
    """Host and path, lowercased, without scheme, query, fragment or trailing slash.

    Two links to the same page differ by ``www``, by ``http`` versus ``https``,
    and by whatever tracking parameters the referrer added. Comparing those raw
    would report a fabricated citation for a link the Turn genuinely read.
    """
    trimmed = (url or "").strip()
    trimmed = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", trimmed)
    trimmed = trimmed.split("#", 1)[0].split("?", 1)[0]
    if trimmed.lower().startswith("www."):
        trimmed = trimmed[4:]
    return trimmed.rstrip("/").casefold()


# -- instants --------------------------------------------------------------


def as_date(value: object) -> date | None:
    """A date out of whatever the artifact or the corpus carried, or ``None``.

    Accepts an ISO date, an ISO instant with or without a zone, and a trailing
    ``Z``. Returns ``None`` rather than raising: a source with an unreadable
    date is a source the temporal grader declines to judge, and that is a
    different outcome from a violation.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def epoch_to_iso(stamp: float) -> str:
    return datetime.fromtimestamp(float(stamp), tz=timezone.utc).isoformat()


__all__ = [
    "SMALL_INTEGER_CEILING",
    "YEAR_RANGE",
    "as_date",
    "canonical_numbers",
    "canonical_url",
    "covered",
    "epoch_to_iso",
    "fold",
    "is_claim",
    "matched_markers",
    "parse_number",
    "urls_in",
    "within_tolerance",
]
