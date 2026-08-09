"""Reshape the provider's ratio frame into one record per reporting period.

The provider returns ratios transposed: one row per metric, one column per
period, plus `item`/`item_id` label columns. Callers want the opposite — the
most recent periods, each a dict of named metrics — so the whole frame is
pivoted here rather than in every consumer.

Metrics are keyed by the provider's stable `item_id` (`pe_ratio`, `roe`, ...)
rather than its display label, which is Vietnamese prose and varies by whether
the company is a bank.
"""
import re
from typing import Any, Optional

import pandas as pd

# "2026-Q2", "2026", and the "2025-Q4_1" form the provider emits when a period
# appears twice in one frame.
_PERIOD_PATTERN = re.compile(r"^(?P<year>\d{4})(?:-Q(?P<quarter>[1-4]))?(?:_\d+)?$")

_LABEL_COLUMNS = ("item", "item_en", "item_id")


def _parse_period(column: Any) -> Optional[tuple[int, int]]:
    """Return (year, quarter) for a period column, or None if it isn't one."""
    match = _PERIOD_PATTERN.match(str(column))
    if match is None:
        return None
    quarter = match.group("quarter")
    # Annual frames sort after every quarter of the same year.
    return int(match.group("year")), int(quarter) if quarter else 0


def _metric_key(row: pd.Series) -> Optional[str]:
    """Prefer the stable id; fall back to a label only if the id is missing."""
    for column in ("item_id", "item_en", "item"):
        value = row.get(column)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def is_wide_ratio_frame(df: pd.DataFrame) -> bool:
    """True when the frame is metrics-by-period rather than period-by-metric."""
    return any(column in df.columns for column in _LABEL_COLUMNS)


def wide_ratio_frame_to_records(df: pd.DataFrame, periods: int) -> list[dict]:
    """Pivot a metrics-by-period frame into the newest `periods` records.

    Each record carries the parsed `period`, `year`, and `quarter` alongside the
    metrics, so callers can label a data point without re-reading the frame.
    """
    if df is None or df.empty or periods <= 0:
        return []

    seen: set[tuple[int, int]] = set()
    columns: list[tuple[tuple[int, int], Any]] = []
    for column in df.columns:
        parsed = _parse_period(column)
        if parsed is None or parsed in seen:
            # A repeated period is the same quarter restated; the first
            # occurrence is the provider's primary column for it.
            continue
        seen.add(parsed)
        columns.append((parsed, column))

    columns.sort(key=lambda item: item[0], reverse=True)

    records = []
    for (year, quarter), column in columns[:periods]:
        record: dict[str, Any] = {
            "period": str(column),
            "year": year,
            "quarter": quarter or None,
        }
        for _, row in df.iterrows():
            key = _metric_key(row)
            if key is None or key in record:
                continue
            value = row[column]
            record[key] = None if pd.isna(value) else value
        records.append(record)

    return records
