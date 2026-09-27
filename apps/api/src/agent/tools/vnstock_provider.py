"""The one door every vnstock call goes through.

Three tools read the same provider — prices, reported ratios, company events and
news — and each of them used to import it, call it and classify its failures on
its own. Two facts measured on 2026-09-26 make that unsafe, and both are fixed
here once instead of in every caller:

**The package enforces a request quota inside the process, and on breach it
exits.** Guest use allows 20 requests a minute; past that ``vnai`` raises
``RateLimitExceeded`` and its error context calls ``sys.exit``. In a server that
is a ``SystemExit`` raised in a worker thread — a ``BaseException`` no tool
handler catches — carried up into the Turn. So every call here passes a limiter
that stops short of the quota and refuses with ``rate_limited`` while there is
still headroom, and ``SystemExit`` / ``RateLimitExceeded`` from the package are
turned into that same refusal if they happen anyway.

**Importing it phones home.** The import took 26 s while that host was timing
out, which is why ``market_data`` warms it on a start-up thread.

**The same read is asked for again and again.** A Thread about one ticker reads
its bars, ratios and news on nearly every Turn, and each repeat spent quota.
:func:`cached` answers a repeat from memory for a TTL the caller chooses, and
says when the data was actually fetched so the payload's ``retrieved_at`` stays
the truth. In process on purpose: the API runs one process and ``vnai`` counts
its quota per process, so a shared store would add serialisation of provider
frames for no quota gained.

What this is not: a scheduler. A refused call is refused; the model is told to
try later or to answer without the figure.
"""

from __future__ import annotations

import contextlib
import copy
import importlib
import io
import logging
import math
import os
import threading
import time
from collections import deque
from collections.abc import Callable, Hashable
from datetime import datetime, timezone
from typing import Any, TypeVar

PROVIDER = "vnstock"

logger = logging.getLogger(__name__)

#: Stable failure vocabulary. The provider's own message is never passed through
#: as if it were trustworthy prose — it is third-party text, and a model reading
#: "rate limited, upgrade your plan" as an instruction is exactly the boundary
#: ``untrusted.py`` exists to hold.
INVALID_REQUEST = "invalid_request"
NO_DATA = "no_data"
PROVIDER_UNAVAILABLE = "provider_unavailable"
RATE_LIMITED = "rate_limited"
SCHEMA_DRIFT = "schema_drift"
AMBIGUOUS_TIME = "ambiguous_time"

#: Requests this process lets itself make per window: 80% of the package's
#: quota, which leaves room for the requests it makes on its own behalf (a
#: session handshake counts) that this module cannot see. Guest use is 20 a
#: minute; with a community key in ``VNSTOCK_API_KEY`` (read by ``vnai`` itself)
#: it is 60.
# ponytail: key means community tier; a sponsor tier needs its own number here.
REQUESTS_PER_WINDOW = 48 if os.getenv("VNSTOCK_API_KEY", "").strip() else 16
WINDOW_SECONDS = 60.0

#: How long a call waits for room before it is refused. Short on purpose: a
#: tool call has a 20 s budget, and a wait that ate it would fail as a timeout
#: instead of saying what actually happened.
MAX_WAIT_SECONDS = 6.0

#: How long a read waits for another caller's load of the same key: the 20 s a
#: provider tool call is allowed, plus a margin, so a waiter behind a hung
#: leader is released once no tool call could still be waiting for it.
FLIGHT_WAIT_SECONDS = 25.0

#: Room a background fill (the screener) leaves for the reads a model asks for
#: next. Without it one screen spends the whole window and the price reads of
#: the following round are refused.
BACKGROUND_KEEP_FREE = max(1, REQUESTS_PER_WINDOW // 3)

T = TypeVar("T")


class MarketDataError(ValueError):
    """A refusal with a code the loop can act on and a reason a reader can read."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def import_vnstock() -> Any:
    """Import the provider package, catching what its start-up prints.

    The package announces a sponsorship programme when it loads. This catches
    the part written through ``sys.stdout``; the banner drawn by its own console
    holds the real stream, so a line may still reach the log once per process.
    Not redirected at the file descriptor: swapping fd 1 under a running server
    races every other thread writing a log line.

    Every read calls this, and ``redirect_stdout`` swaps a process-global: two
    threads entering and leaving it out of order leave ``sys.stdout`` pointing at
    a dead buffer. So the swap happens once, for the one import that loads the
    package, under a lock; every later call returns the loaded module untouched.
    """
    module = _vnstock_module
    if module is not None:
        return module
    return _first_import()


_vnstock_module: Any = None
_import_lock = threading.Lock()


def _first_import() -> Any:
    global _vnstock_module
    with _import_lock:
        if _vnstock_module is None:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                _vnstock_module = importlib.import_module(PROVIDER)
        return _vnstock_module


class RequestGate:
    """A sliding-window limiter shared by every caller in the process."""

    def __init__(
        self,
        *,
        limit: int = REQUESTS_PER_WINDOW,
        window: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._limit = limit
        self._window = window
        self._clock = clock
        self._sleep = sleep
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(
        self, weight: int = 1, *, max_wait: float = MAX_WAIT_SECONDS, keep_free: int = 0
    ) -> None:
        """Take ``weight`` requests of room, waiting briefly, or refuse.

        ``keep_free`` is room this caller may not take: a background fill passes
        it so the window is never spent to the last request.
        """
        limit = self._limit - keep_free
        deadline = self._clock() + max_wait
        while True:
            with self._lock:
                now = self._clock()
                while self._stamps and now - self._stamps[0] >= self._window:
                    self._stamps.popleft()
                if len(self._stamps) + weight <= limit:
                    self._stamps.extend([now] * weight)
                    return
                free_at = self._stamps[max(0, len(self._stamps) + weight - limit - 1)] + self._window
            wait = free_at - now
            if now + wait > deadline:
                raise MarketDataError(
                    RATE_LIMITED,
                    f"the provider's request quota is spent; room again in about {math.ceil(wait)}s",
                )
            self._sleep(max(wait, 0.0))


GATE = RequestGate()


class TtlCache:
    """A small time-bounded memo, safe across the worker threads tools run on.

    Each entry keeps its own TTL and the wall-clock time it was stored, so a
    hit can say how old it is. Bounded: the model chooses date ranges freely,
    so keys are open-ended, and past ``max_items`` the oldest entry goes.
    """

    def __init__(
        self,
        ttl: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
        *,
        max_items: int = 2048,
    ) -> None:
        self._ttl = ttl
        self._clock = clock
        self._max_items = max_items
        self._items: dict[Hashable, tuple[float, float, datetime, Any]] = {}
        self._lock = threading.Lock()

    def entry(self, key: Hashable) -> tuple[Any, datetime] | None:
        """The value and when it was stored, or ``None`` when absent or expired."""
        with self._lock:
            hit = self._items.get(key)
            if hit is None:
                return None
            stored, ttl, at, value = hit
            if self._clock() - stored > ttl:
                del self._items[key]
                return None
            return value, at

    def get(self, key: Hashable) -> Any | None:
        found = self.entry(key)
        return None if found is None else found[0]

    def put(
        self, key: Hashable, value: Any, *, ttl: float | None = None, at: datetime | None = None
    ) -> datetime:
        at = at or datetime.now(timezone.utc)
        with self._lock:
            self._items.pop(key, None)
            while len(self._items) >= self._max_items:
                del self._items[next(iter(self._items))]
            self._items[key] = (self._clock(), self._ttl if ttl is None else ttl, at, value)
        return at

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


#: Provider reads, shared by every tool in the process.
READS = TtlCache()


def cached(
    key: Hashable, ttl: float, load: Callable[[], T], *, now: datetime
) -> tuple[T, datetime]:
    """``load()``, answered from :data:`READS` while a stored result is fresh.

    ``load`` is a read that already goes through :func:`call`; this only
    remembers what it returned. Returns the value and when the provider actually
    sent it: ``now`` — the caller's clock — for a fresh read, the stored instant
    for a hit. A hit is a copy, so no caller can change what the next one reads.
    Only successes are kept: a refusal is asked again next time.

    Single-flight per key: concurrent misses for one key make one provider call,
    and the rest wait for it and read what it stored. Were they each to load, a
    Thread's parallel reads of one ticker would spend the quota once per caller.
    If the leader's load fails, the next waiter loads in its turn.

    A waiter gives up after :data:`FLIGHT_WAIT_SECONDS` with the refusal a
    silent provider gets, rather than loading beside a leader that hangs: a
    second call would spend quota on the source that is not answering, and an
    unbounded wait would hold a worker thread long after its tool call ended.
    """
    hit = READS.entry(key)
    if hit is not None:
        return copy.deepcopy(hit[0]), hit[1]
    with _flight_lock:
        flight = _flights.setdefault(key, [threading.Lock(), 0])
        flight[1] += 1
    try:
        if not flight[0].acquire(timeout=FLIGHT_WAIT_SECONDS):
            raise MarketDataError(
                PROVIDER_UNAVAILABLE, "the market data provider did not answer this call"
            )
        try:
            hit = READS.entry(key)
            if hit is not None:
                return copy.deepcopy(hit[0]), hit[1]
            value = load()
            return value, READS.put(key, copy.deepcopy(value), ttl=ttl, at=now)
        finally:
            flight[0].release()
    finally:
        with _flight_lock:
            # The last caller out removes the key, so the table only ever holds
            # keys with a load in progress or callers waiting on one.
            flight[1] -= 1
            if flight[1] == 0:
                del _flights[key]


#: Per key: the lock one load holds, and how many callers hold or wait on it.
_flights: dict[Hashable, list[Any]] = {}
_flight_lock = threading.Lock()


def call(
    operation: Callable[[], T],
    *,
    symbol: str,
    weight: int = 1,
    max_wait: float = MAX_WAIT_SECONDS,
    keep_free: int = 0,
) -> T:
    """Run one provider operation under the gate, with its failures classified.

    ``weight`` is how many requests the operation makes: a Vietcap read opens a
    session and then asks, which is two. ``max_wait=0`` takes room only if it is
    there now — how a caller filling a cache stops before the quota does.
    """
    GATE.acquire(weight, max_wait=max_wait, keep_free=keep_free)
    try:
        return operation()
    except MarketDataError:
        raise
    except SystemExit as exc:
        # The package's own quota guard exits the process on breach. Here that
        # is one refused call, not a stopped server.
        raise MarketDataError(RATE_LIMITED, "the provider refused: request quota reached") from exc
    except Exception as exc:  # noqa: BLE001 - provider failures are classified
        refused = classify(exc, symbol)
        # The provider's own words stay in the log, where an operator looks;
        # the model is given only the stable code.
        logger.warning(
            "vnstock call for %s failed as %s: %s: %s",
            symbol, refused.code, type(exc).__name__, str(exc)[:300],
        )
        raise refused from exc


def classify(exc: BaseException, symbol: str) -> MarketDataError:
    """A provider exception as one of this module's own codes.

    The provider wraps a weekend, a bad ticker and an outage in whichever
    exception its retry decorator happened to raise, so the text is read for a
    signal and everything unrecognised becomes ``provider_unavailable`` — the
    answer that is true when nothing more specific is known.
    """
    if type(exc).__name__ == "RateLimitExceeded":
        return MarketDataError(RATE_LIMITED, "the provider refused: request quota reached")
    text = str(exc).casefold()
    if "429" in text or "rate" in text and "limit" in text:
        return MarketDataError(RATE_LIMITED, "the provider is rate limiting this host")
    if "not found" in text or "invalid symbol" in text or "symbol" in text:
        return MarketDataError(INVALID_REQUEST, f"the provider does not recognise {symbol}")
    if "no data" in text or "empty" in text:
        return MarketDataError(NO_DATA, f"the provider returned no rows for {symbol}")
    return MarketDataError(PROVIDER_UNAVAILABLE, "the market data provider did not answer this call")


__all__ = [
    "AMBIGUOUS_TIME",
    "BACKGROUND_KEEP_FREE",
    "GATE",
    "INVALID_REQUEST",
    "MarketDataError",
    "NO_DATA",
    "PROVIDER",
    "PROVIDER_UNAVAILABLE",
    "RATE_LIMITED",
    "RequestGate",
    "READS",
    "SCHEMA_DRIFT",
    "TtlCache",
    "cached",
    "call",
    "classify",
    "import_vnstock",
]
