"""Data conversion utilities for DataFrame to Pydantic models."""

from typing import Any, Optional

import pandas as pd


def safe_float(value: Any) -> Optional[float]:
    """Convert value to float, returning None for NaN/invalid values.

    Args:
        value: Value to convert

    Returns:
        Float value or None if conversion fails
    """
    if value is None:
        return None
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_float_millions(value: Any) -> Optional[float]:
    """Convert a raw VND figure to millions, or None when unusable.

    Financial statements come through in plain VND; the UI labels its tables
    "Triệu đồng", so the scaling belongs here rather than in each converter.
    """
    raw = safe_float(value)
    return None if raw is None else raw / 1_000_000
