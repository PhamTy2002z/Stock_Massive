"""Response handling every adapter needs before it can read a provider.

Providers disagree about capitalization, about how they spell absence, and
about nothing else worth sharing. What is left over once those two are settled
lives here, so a third adapter starts from the same floor as the first two
rather than copying it.
"""

from collections.abc import Sequence
from typing import Any

import pandas as pd
from zoneinfo import ZoneInfo

from ..shared import validate_symbol

# Every provider in scope reports Vietnamese sessions, and several of them
# stamp timestamps with no zone at all.
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def normalized_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    """Validate, upper-case and deduplicate, keeping the order asked for.

    A malformed symbol raises here, before a request is spent on it: it is the
    caller's mistake, and finding it in a response would make it look like the
    provider's.
    """
    return tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))


def lower_cased_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the frame with its column names lower-cased.

    Providers are not consistent with each other, and FiinQuant is not
    consistent with itself — its two statistics calls disagree on capitalization
    with each other and with the candle frame — so case is settled once, before
    anything reads a field.
    """
    columns = {str(column).lower(): column for column in frame.columns}
    return frame.rename(columns={value: key for key, value in columns.items()})


def missing_fields(
    frame: pd.DataFrame,
    required_fields: Sequence[str],
) -> tuple[str, ...]:
    """Name the required fields this response did not bring, in a stable order.

    Returned rather than raised: each adapter reports a missing field as its own
    kind of error, and this has no business choosing between them.
    """
    present = {str(column) for column in frame.columns}
    return tuple(sorted(set(required_fields) - present))


def optional_float(value: Any) -> float | None:
    """Read a number, treating every way a provider spells absence as None."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
