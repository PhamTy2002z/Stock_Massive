# Phase 1: Extract Shared Utilities

**Date:** 2024-12-19
**Priority:** P2
**Status:** done
**Effort:** 1h
**Completed:** 2025-12-19

## Context

- [Plan Overview](plan.md)
- [Service Domain Analysis](research/researcher-01-service-domain-analysis.md)

## Overview

Extract shared utilities from monolithic `service.py` into `stocks/shared/` module. These utilities are used across all domains and must be centralized before domain splitting.

## Related Files

- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/service.py` (lines 42-67, 1455-1464)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas.py` (line 206-210)

## Requirements

1. Create `stocks/shared/` directory structure
2. Extract exception classes
3. Extract validation utilities
4. Extract data converters (prepare for Phase 3)
5. Maintain backward compatibility

## Implementation Steps

### Step 1: Create Directory Structure

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks
mkdir -p shared
touch shared/__init__.py
touch shared/exceptions.py
touch shared/validators.py
touch shared/converters.py
```

### Step 2: Extract Exceptions

**File:** `stocks/shared/exceptions.py`

Extract from `service.py` lines 42-45:

```python
"""Shared exception classes for stocks module."""


class StockServiceError(Exception):
    """Base exception for stock service errors."""
    pass
```

### Step 3: Extract Validators

**File:** `stocks/shared/validators.py`

Extract from `service.py` lines 49-67:

```python
"""Validation utilities for stock symbols and parameters."""

import re
from .exceptions import StockServiceError


SYMBOL_PATTERN = re.compile(r"^[A-Z]{3}$")


def validate_symbol(symbol: str) -> str:
    """Validate and normalize stock symbol.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Uppercase normalized symbol

    Raises:
        StockServiceError: If symbol format is invalid
    """
    symbol = symbol.upper().strip()
    if not SYMBOL_PATTERN.match(symbol):
        raise StockServiceError(
            f"Invalid symbol format: {symbol}. Must be 3 uppercase letters."
        )
    return symbol
```

### Step 4: Prepare Converters Module

**File:** `stocks/shared/converters.py`

Create placeholder with `_safe_float` utility (lines 1455-1464 from service.py):

```python
"""Data conversion utilities for DataFrame to Pydantic models."""

from typing import Any, Optional


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float, return None if invalid.

    Args:
        value: Value to convert

    Returns:
        Float value or None if conversion fails
    """
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None
```

**Note:** Domain-specific converters will be moved here in Phase 3.

### Step 5: Setup Re-exports

**File:** `stocks/shared/__init__.py`

```python
"""Shared utilities for stocks module."""

from .exceptions import StockServiceError
from .validators import validate_symbol, SYMBOL_PATTERN
from .converters import _safe_float

__all__ = [
    "StockServiceError",
    "validate_symbol",
    "SYMBOL_PATTERN",
    "_safe_float",
]
```

### Step 6: Update service.py Imports

Replace lines 42-67 in `service.py` with:

```python
from .shared import StockServiceError, validate_symbol, _safe_float
```

Update all converter methods to use `from .shared.converters import _safe_float`.

### Step 7: Update Test Imports

Update test files to import from new location:

```python
# Before
from src.stocks.service import StockServiceError

# After
from src.stocks.shared import StockServiceError
```

Files to update:
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/tests/test_stocks_service.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/tests/test_stocks_router.py`

## Success Criteria

- [x] `stocks/shared/` module created with 3 files
- [x] All utilities extracted and functional
- [x] `service.py` imports from `shared/`
- [x] All tests pass without modification
- [x] No breaking changes to external imports

## Testing

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api
pytest tests/test_stocks_service.py -v
pytest tests/test_stocks_router.py -v
```

## Risk Assessment

**Low Risk:**
- Simple extraction with no logic changes
- Backward compatibility via imports
- Isolated utilities with no dependencies

**Mitigation:**
- Keep original code until tests pass
- Verify imports in all test files
- Run full test suite before proceeding to Phase 2
