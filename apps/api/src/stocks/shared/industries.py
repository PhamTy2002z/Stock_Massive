"""Industry (ICB) classification lookup, normalised across vnstock versions.

vnstock 4.x split what 3.x returned from a single call: `symbols_by_industries()`
now yields only (symbol, industry_code, industry_name), while company name and
exchange moved to `symbols_by_exchange()`. The 3.x column names (icb_code2,
icb_name2) are gone entirely.

The previous code read the 3.x names with `row.get(...)`, so under 4.x every
lookup silently returned None and sector features degraded to empty results
instead of failing. This module validates the shape up front and raises, so a
future upstream rename surfaces as an error rather than blank dashboards.
"""
import logging
from typing import Optional

import pandas as pd

from .exceptions import StockServiceError
from .validators import SYMBOL_PATTERN

logger = logging.getLogger(__name__)

# Bounds mirror the DB columns these values eventually land in.
_MAX_CODE_LEN = 4
_MAX_NAME_LEN = 100
_MAX_COMPANY_LEN = 255
_MAX_EXCHANGE_LEN = 10


def _require_columns(df: Optional[pd.DataFrame], columns: set[str], source: str) -> None:
    """Raise unless `df` is non-empty and carries every column in `columns`."""
    if df is None or df.empty:
        raise StockServiceError(f"{source} returned no rows")

    missing = columns - set(df.columns)
    if missing:
        raise StockServiceError(
            f"{source} is missing expected columns {sorted(missing)}; "
            f"got {sorted(df.columns)}. The vnstock schema likely changed."
        )


def _truncate(value: object, limit: int) -> Optional[str]:
    """Coerce to a bounded string, or None when there is nothing usable."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def fetch_industry_mapping(listing) -> dict[str, dict]:
    """Return `{symbol: {icb_code, icb_name, company_name, exchange}}`.

    `listing` is a vnstock `Listing` instance, passed in so callers keep control
    of retry and rate-limit wrapping.

    Company name and exchange come from a second call and are best-effort: a
    failure there leaves those fields None rather than losing the industry
    mapping, which is what the sector features actually need.
    """
    industries = listing.symbols_by_industries()
    _require_columns(
        industries, {"symbol", "industry_code", "industry_name"}, "symbols_by_industries()"
    )

    profiles = _fetch_symbol_profiles(listing)

    mapping: dict[str, dict] = {}
    for row in industries.to_dict("records"):
        symbol = str(row.get("symbol") or "").upper()
        if not SYMBOL_PATTERN.match(symbol):
            continue

        profile = profiles.get(symbol, {})
        mapping[symbol] = {
            "icb_code": _truncate(row.get("industry_code"), _MAX_CODE_LEN),
            "icb_name": _truncate(row.get("industry_name"), _MAX_NAME_LEN),
            "company_name": profile.get("company_name"),
            "exchange": profile.get("exchange") or "",
        }

    if not mapping:
        raise StockServiceError("No valid industry classifications after filtering symbols")

    logger.info("Industry mapping built for %d symbols", len(mapping))
    return mapping


def _fetch_symbol_profiles(listing) -> dict[str, dict]:
    """Best-effort company name and exchange per symbol."""
    try:
        exchanges = listing.symbols_by_exchange()
        _require_columns(exchanges, {"symbol"}, "symbols_by_exchange()")
    except Exception as exc:
        logger.warning("Company/exchange lookup unavailable, continuing without: %s", exc)
        return {}

    profiles: dict[str, dict] = {}
    for row in exchanges.to_dict("records"):
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        profiles[symbol] = {
            "company_name": _truncate(
                row.get("organ_name") or row.get("en_organ_name"), _MAX_COMPANY_LEN
            ),
            "exchange": _truncate(row.get("exchange"), _MAX_EXCHANGE_LEN),
        }
    return profiles
