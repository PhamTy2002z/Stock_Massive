"""Validation utilities for stock symbols and parameters."""

import re

from .exceptions import StockServiceError


# Symbol validation pattern: 1-10 uppercase alphanumeric characters
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{1,10}$")


def validate_symbol(symbol: str) -> str:
    """Validate and normalize stock symbol.

    Args:
        symbol: Stock symbol to validate

    Returns:
        Normalized uppercase symbol

    Raises:
        StockServiceError: If symbol is invalid
    """
    normalized = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(normalized):
        raise StockServiceError(f"Invalid symbol format: {symbol}")
    return normalized
