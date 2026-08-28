"""The bounded set of symbols this system commits to collecting and serving.

One place answers "which symbols are we watching" for both the collector and
the serving path, so the two can never disagree about what the system has
promised to have data for.

The hundred places are split in half (``docs/adr/0003``). Fifty are declared by
an operator and fifty are earned: they belong to the active Profit Leaders
Cohort, which the census reseats as the market's profits change. The halves are
not symmetrical — the declared half is a commitment and the cohort half is
derived — so when the two together would breach the cap it is the cohort
activation that is refused, never the configuration.

The cap is a safety valve for the collector — its run has to fit in the window
after the session closes, and the gateway has to survive the batch — not a
quota sold to anyone. It never reaches the interface.
"""

import logging
from dataclasses import dataclass, field
from typing import Iterator

from sqlalchemy.orm import Session

from src.core.config import Settings, get_settings

from .shared import StockServiceError, validate_symbol

logger = logging.getLogger(__name__)

UNIVERSE_MAX_SYMBOLS = 100

# Half the Universe, reserved for the Profit Leaders Cohort. An operator may
# declare up to the other half; declaring more is refused at parse time rather
# than quietly evicting cohort members, because a cohort silently missing its
# lower ranks produces a ranking nobody asked for.
UNIVERSE_EXPLICIT_MAX = 50


class UniverseConfigurationError(RuntimeError):
    """The declared Universe cannot be honoured, so the app must not start.

    Raised while the operator is still watching the console. The alternative is
    discovering it hours later inside a collector run, from a list nobody is
    looking at any more.
    """


@dataclass(frozen=True)
class Universe:
    """The symbols the system has promised to collect and serve, in order.

    Two halves rather than one list, because they answer to different things: the
    explicit half comes from configuration and changes when an operator says so,
    the cohort half comes from the active Cohort Version and changes when the
    market's profits do. Kept apart, a reader can always tell which is which —
    flattened into one tuple, a symbol dropping out of the Universe would be
    indistinguishable from an operator removing it.

    Order is preserved only so logs and batches read predictably; nothing
    depends on it, and two declarations that differ only in order describe the
    same Universe.

    ``market`` is a third set and not a third half: the two halves above are
    places in a bounded promise, while the market is simply who is listed.
    """

    explicit: tuple[str, ...]
    cohort: tuple[str, ...] = field(default=())
    #: Every share the listing register currently lists — about 1,500 of them,
    #: which is why it is not part of ``symbols`` and never counts against the
    #: cap. The declared half is a promise to have data for a symbol; this is
    #: only the market a market-wide job walks, and a screener reading the daily
    #: spine needs the whole market to rank one company within it.
    #:
    #: Kept out of ``symbols`` deliberately. ``symbols`` is what ``contains``
    #: answers, and ``contains`` is what the chat lane's ``get_field`` gates on:
    #: a Signal Field is computed from stored Snapshots the collector never took
    #: for the market half, so a symbol admitted from here would produce a
    #: refusal that reads like a broken pipeline instead of an honest "outside
    #: the Universe".
    market: tuple[str, ...] = field(default=())

    @property
    def symbols(self) -> tuple[str, ...]:
        """The declared and cohort halves as one list, explicit first, deduped.

        A symbol in both halves holds one place, not two, and it is the explicit
        entry that survives — the two are the same ticker, so which wins matters
        only in that the answer has to be stable.

        The market half is not in here. It is not a promise to serve a symbol,
        and everything that gates on membership is gating on the promise.
        """
        merged = dict.fromkeys(self.explicit)
        merged.update(dict.fromkeys(self.cohort))
        return tuple(merged)

    @classmethod
    def from_settings(cls, settings: Settings) -> "Universe":
        """The declared half alone, with no cohort seated.

        Used where there is no database session to read a Cohort Version from —
        startup validation, and callers that only need to know what was
        configured. Everything that collects or serves builds through
        ``build_universe`` instead.
        """
        return parse_universe(settings.universe_symbols)

    def with_cohort(self, cohort: tuple[str, ...]) -> "Universe":
        """Seat a cohort, or refuse to and keep the configuration whole.

        The cap is checked after deduplication and the refusal is total: a cohort
        trimmed to fit would be the top forty-something companies presented as
        the top fifty. An explicitly declared symbol is never evicted to make
        room.
        """
        merged = dict.fromkeys(self.explicit)
        merged.update(dict.fromkeys(cohort))
        if len(merged) > UNIVERSE_MAX_SYMBOLS:
            logger.error(
                "Refusing to seat the cohort: %d declared symbols and %d cohort "
                "members would put the Universe at %d, over the cap of %d",
                len(self.explicit),
                len(cohort),
                len(merged),
                UNIVERSE_MAX_SYMBOLS,
            )
            return self
        return Universe(explicit=self.explicit, cohort=cohort, market=self.market)

    def with_market(self, market: tuple[str, ...]) -> "Universe":
        """Attach the listed market, without it counting against anything.

        No cap check: the cap bounds what the system promised to collect, and
        this half promises nothing. It is the list a market-wide job walks.
        """
        return Universe(
            explicit=self.explicit,
            cohort=self.cohort,
            market=tuple(dict.fromkeys(market)),
        )

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
    if len(unique) > UNIVERSE_EXPLICIT_MAX:
        raise UniverseConfigurationError(
            f"Universe declarations are capped at {UNIVERSE_EXPLICIT_MAX} symbols "
            f"but {len(written)} are declared ({len(unique)} of them distinct). "
            f"The other {UNIVERSE_MAX_SYMBOLS - UNIVERSE_EXPLICIT_MAX} of the "
            f"{UNIVERSE_MAX_SYMBOLS} places are reserved for the Profit Leaders "
            f"Cohort (docs/adr/0003)"
        )

    return Universe(explicit=unique)


# The cohort half changes while the process runs, so it cannot be memoized for
# the life of the process the way the configured half was. Keyed on the active
# Cohort Version's id instead: a new version means a new key, and there is no
# window where a promoted cohort is being served by one caller and not another.
_cohort_cache: dict[int | None, tuple[str, ...]] = {}


def build_universe(
    session: Session,
    settings: Settings | None = None,
    *,
    with_market: bool = False,
) -> Universe:
    """The Universe as it stands.

    Post-rip-out (2026-08-25): the Profit Leaders Cohort seating path was
    removed with the collector, so this call returns only the declared half.
    The ``session`` argument stays in the signature because both the chat lane
    and its tests reach for it that way.

    ``with_market`` reads the listing register and attaches the market half. Off
    by default because the serving path calls this on every ``get_field`` and
    has no use for 1,500 tickers it does not serve; a market-wide job asks for
    it explicitly.

    Legacy docstring below for the shape callers still expect.

    Reads the active Cohort Version rather than a stored symbol list, so the
    Universe and the cohort can never drift apart. The result is cached per
    version id — the query is cheap but it runs on the serving path, and the
    answer only changes when a version is promoted.
    """
    settings = settings or get_settings()
    universe = Universe.from_settings(settings)
    if not with_market:
        return universe

    # Imported inside the branch that uses it: this module is imported at
    # startup to validate the declared list, and that path has no business
    # pulling in the register and its provider contracts.
    from .listing_roster import ListingRosterStore

    return universe.with_market(ListingRosterStore(session).listed_symbols())


def forget_cohort_cache() -> None:
    """Drop the memoized cohort membership.

    Called after an activation so the next read sees the new version, and by
    tests. Clearing rather than invalidating one key: there is only ever one
    active version, so anything already in here is by definition stale.
    """
    _cohort_cache.clear()
