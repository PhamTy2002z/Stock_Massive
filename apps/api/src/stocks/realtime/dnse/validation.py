"""Local validation for DNSE market-data request contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...shared import StockServiceError, validate_symbol


RESOLUTIONS = frozenset({"1", "3", "5", "15", "30", "1H", "1D", "1W"})
ORDERS = frozenset({"asc", "desc"})
INSTRUMENT_TYPES = frozenset({"stock", "derivative", "index"})


def validated_symbol(value: str) -> str:
    try:
        return validate_symbol(value)
    except StockServiceError as exc:
        raise ValueError(str(exc)) from exc


def validated_board(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if not normalized or len(normalized) > 32 or not normalized.replace("_", "").isalnum():
        raise ValueError("invalid DNSE board identity")
    return normalized


@dataclass(frozen=True, slots=True)
class EventWindow:
    start: date
    end: date
    limit: int = 1000
    order: str = "desc"

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("event window start cannot follow end")
        if self.start != self.end:
            raise ValueError("DNSE event history accepts exactly one trading day")
        if not 1 <= self.limit <= 1000:
            raise ValueError("DNSE event page size must be between 1 and 1000")
        if self.order not in ORDERS:
            raise ValueError("DNSE order must be asc or desc")

    def query(self) -> dict[str, str | int]:
        return {
            "from": self.start.isoformat(),
            "to": self.end.isoformat(),
            "limit": self.limit,
            "order": self.order,
        }


@dataclass(frozen=True, slots=True)
class OhlcRequest:
    symbol: str
    resolution: str
    start: date
    end: date
    instrument_type: str = "stock"

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", validated_symbol(self.symbol))
        if self.resolution not in RESOLUTIONS:
            raise ValueError("unsupported DNSE OHLC resolution")
        if self.instrument_type not in INSTRUMENT_TYPES:
            raise ValueError("unsupported DNSE OHLC instrument type")
        if self.start > self.end:
            raise ValueError("OHLC start cannot follow end")

    def query(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "resolution": self.resolution,
            "from": self.start.isoformat(),
            "to": self.end.isoformat(),
            "type": self.instrument_type,
        }
