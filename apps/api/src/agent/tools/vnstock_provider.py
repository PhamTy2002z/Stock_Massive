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

What this is not: a cache or a scheduler. A refused call is refused; the model
is told to try later or to answer without the figure.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar

PROVIDER = "vnstock"

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

#: Requests this process lets itself make per window. The package's guest quota
#: is 20 a minute; stopping at 16 leaves room for the requests the package makes
#: on its own behalf (a session handshake counts) that this module cannot see.
REQUESTS_PER_WINDOW = 16
WINDOW_SECONDS = 60.0

#: How long a call waits for room before it is refused. Short on purpose: a
#: tool call has a 20 s budget, and a wait that ate it would fail as a timeout
#: instead of saying what actually happened.
MAX_WAIT_SECONDS = 4.0

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
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        return importlib.import_module(PROVIDER)


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

    def acquire(self, weight: int = 1, *, max_wait: float = MAX_WAIT_SECONDS) -> None:
        """Take ``weight`` requests of room, waiting briefly, or refuse."""
        deadline = self._clock() + max_wait
        while True:
            with self._lock:
                now = self._clock()
                while self._stamps and now - self._stamps[0] >= self._window:
                    self._stamps.popleft()
                if len(self._stamps) + weight <= self._limit:
                    self._stamps.extend([now] * weight)
                    return
                free_at = self._stamps[len(self._stamps) + weight - self._limit - 1] + self._window
            wait = free_at - now
            if now + wait > deadline:
                raise MarketDataError(
                    RATE_LIMITED,
                    f"the provider's request quota is spent; room again in about {math.ceil(wait)}s",
                )
            self._sleep(max(wait, 0.0))


GATE = RequestGate()


def call(
    operation: Callable[[], T],
    *,
    symbol: str,
    weight: int = 1,
    max_wait: float = MAX_WAIT_SECONDS,
) -> T:
    """Run one provider operation under the gate, with its failures classified.

    ``weight`` is how many requests the operation makes: a Vietcap read opens a
    session and then asks, which is two. ``max_wait=0`` takes room only if it is
    there now — how a caller filling a cache stops before the quota does.
    """
    GATE.acquire(weight, max_wait=max_wait)
    try:
        return operation()
    except MarketDataError:
        raise
    except SystemExit as exc:
        # The package's own quota guard exits the process on breach. Here that
        # is one refused call, not a stopped server.
        raise MarketDataError(RATE_LIMITED, "the provider refused: request quota reached") from exc
    except Exception as exc:  # noqa: BLE001 - provider failures are classified
        raise classify(exc, symbol) from exc


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
    "GATE",
    "INVALID_REQUEST",
    "MarketDataError",
    "NO_DATA",
    "PROVIDER",
    "PROVIDER_UNAVAILABLE",
    "RATE_LIMITED",
    "RequestGate",
    "SCHEMA_DRIFT",
    "call",
    "classify",
    "import_vnstock",
]
