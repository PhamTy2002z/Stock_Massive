"""The bounded set of symbols this system commits to collecting and serving.

One place answers "which symbols are we watching" for both the collector and
the serving path, so the two can never disagree about what the system has
promised to have data for.

The cap is a safety valve for the collector — its run has to fit in the window
after the session closes, and the gateway has to survive the batch — not a
quota sold to anyone. It never reaches the interface.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from src.core.config import Settings, get_settings

from .shared import StockServiceError, validate_symbol

UNIVERSE_MAX_SYMBOLS = 100


class UniverseConfigurationError(RuntimeError):
    """The declared Universe cannot be honoured, so the app must not start.

    Raised while the operator is still watching the console. The alternative is
    discovering it hours later inside a collector run, from a list nobody is
    looking at any more.
    """


@dataclass(frozen=True)
class Universe:
    """The symbols the system has promised to collect and serve, in order.

    Order is preserved only so logs and batches read predictably; nothing
    depends on it, and two declarations that differ only in order describe the
    same Universe.
    """

    symbols: tuple[str, ...]

    @classmethod
    def from_settings(cls, settings: Settings) -> "Universe":
        return parse_universe(settings.universe_symbols)

    def contains(self, symbol: str) -> bool:
        """Answer membership for arbitrary text without raising.

        The serving path asks this about whatever a user typed, so a malformed
        symbol is a plain "no" rather than a validation error escaping into a
        request. Declaring a malformed symbol is caught at startup instead,
        where it is a configuration mistake rather than a user's typo.
        """
        try:
            return validate_symbol(symbol) in self.symbols
        except StockServiceError:
            return False

    def __contains__(self, symbol: object) -> bool:
        return isinstance(symbol, str) and self.contains(symbol)

    def __iter__(self) -> Iterator[str]:
        return iter(self.symbols)

    def __len__(self) -> int:
        return len(self.symbols)


def parse_universe(declared: str) -> Universe:
    """Turn a configured list into a Universe, or refuse to produce one.

    An empty declaration is a legitimate Universe: the app runs and the
    collector has nothing to do. That is the state a fresh environment starts
    in, and it must not look like a misconfiguration.
    """
    entries = [entry.strip() for entry in declared.split(",")]
    written = [entry for entry in entries if entry]

    normalized: list[str] = []
    for entry in written:
        try:
            normalized.append(validate_symbol(entry))
        except StockServiceError as exc:
            raise UniverseConfigurationError(
                f"Universe contains an invalid symbol: {entry}"
            ) from exc

    # Deduplicated before the cap is applied: the cap bounds the work the
    # collector actually does, and it never asks for the same symbol twice.
    unique = tuple(dict.fromkeys(normalized))
    if len(unique) > UNIVERSE_MAX_SYMBOLS:
        raise UniverseConfigurationError(
            f"Universe is capped at {UNIVERSE_MAX_SYMBOLS} symbols "
            f"but {len(written)} are declared ({len(unique)} of them distinct)"
        )

    return Universe(symbols=unique)


@lru_cache
def get_universe() -> Universe:
    """Return the configured Universe, parsed once per process."""
    return Universe.from_settings(get_settings())
