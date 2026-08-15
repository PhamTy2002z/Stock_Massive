"""Guarded access to the vnstock library.

vnstock calls `sys.exit()` when its quota is exhausted (vnai/beam/quota.py).
`SystemExit` derives from BaseException, so it sails past every `except
Exception` in the app and past Starlette's handlers, surfacing as a bare 500
with no body — and, before this module existed, taking whichever request
happened to trigger it down with no way to distinguish quota from a real bug.

Rather than wrap ~30 service methods, this wraps the vnstock entry points
themselves. Services import `Listing`, `Trading`, ... from here instead of from
`vnstock`, and every method call is routed through the same guard.

The guard converts:
    SystemExit                -> VnstockUnavailable  (routers map to 503)
    upstream NotImplementedError -> VnstockUnsupported (routers map to 501)

Both are ordinary exceptions, so normal error handling applies.

Being the one place every live vnstock call passes through, this is also where
the account allowance is spent: each call takes a slot from the Redis arbiter
in `src/core/quota.py` on whichever lane the caller declared. That replaced a
`BoundedSemaphore` here, which bounded concurrency and not rate, and which was
one of three uncoordinated guards over a single account quota (`docs/adr/0014`).
"""
import functools
import logging
from typing import Any, Callable

import vnstock as _vnstock
from tenacity import RetryError

from src.core.quota import active_lane, quota_arbiter

logger = logging.getLogger(__name__)

# Calls that only walk vnstock's object graph — `Vnstock().stock(...)` hands
# back a component holder rather than a response. Guarded like everything else
# and deliberately not paced: spending an account slot on a call that reaches no
# provider would make the allowance smaller than it actually is.
_NAVIGATION_LABELS = frozenset({"Vnstock.stock"})


class VnstockUnavailable(Exception):
    """Upstream refused the call — quota exhausted or provider down."""


class VnstockUnsupported(Exception):
    """The configured provider does not implement this call at all."""


def _unwrap(exc: BaseException) -> BaseException:
    """Peel tenacity's RetryError to reach the failure that actually happened.

    vnstock decorates its own calls with tenacity, so a quota exit or an
    unimplemented provider method reaches us as `RetryError[<Future ...>]` —
    which is why these used to surface as opaque 502s.
    """
    seen = set()
    while isinstance(exc, RetryError) and id(exc) not in seen:
        seen.add(id(exc))
        attempt = getattr(exc, "last_attempt", None)
        if attempt is None or not attempt.failed:
            break
        inner = attempt.exception()
        if inner is None:
            break
        exc = inner
    return exc


def _guard(
    func: Callable[..., Any],
    label: str,
    paced: bool = True,
) -> Callable[..., Any]:
    """Wrap a bound vnstock method so upstream failures stay catchable.

    Paced by default: the arbiter is asked for a slot before the call, on the
    lane the caller declared, and a refusal — the Collector holding its lease,
    or no Redis at all — propagates as a `QuotaRefused` rather than becoming a
    call made outside the allowance.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if paced:
            quota_arbiter().acquire(active_lane())
        try:
            return func(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - SystemExit must be caught
            root = _unwrap(exc)

            if isinstance(root, SystemExit):
                logger.warning("vnstock quota exhausted during %s", label)
                raise VnstockUnavailable(
                    "Nguồn dữ liệu vnstock đang giới hạn truy cập, thử lại sau ít phút."
                ) from exc

            if isinstance(root, NotImplementedError):
                logger.info("vnstock provider does not implement %s", label)
                raise VnstockUnsupported(
                    f"Nguồn dữ liệu hiện tại không hỗ trợ {label}."
                ) from exc

            if root is not exc and isinstance(root, Exception):
                # Surface the real error rather than an opaque RetryError.
                raise root from exc
            raise

    return wrapper


class _GuardedProxy:
    """Attribute proxy that guards every callable it hands back.

    Nested objects (e.g. `Vnstock().stock(...).company`) are proxied too, so the
    guard survives the whole chain rather than only the first hop.
    """

    __slots__ = ("_target", "_label")

    def __init__(self, target: Any, label: str):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_label", label)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(object.__getattribute__(self, "_target"), name)
        label = f"{object.__getattribute__(self, '_label')}.{name}"

        if callable(attr):
            guarded = _guard(attr, label, paced=label not in _NAVIGATION_LABELS)

            @functools.wraps(attr)
            def maybe_proxy(*args, **kwargs):
                result = guarded(*args, **kwargs)
                # Only proxy vnstock's own composite objects; DataFrames and
                # plain values must come back untouched.
                if type(result).__module__.startswith("vnstock"):
                    return _GuardedProxy(result, label)
                return result

            return maybe_proxy

        if type(attr).__module__.startswith("vnstock"):
            return _GuardedProxy(attr, label)
        return attr

    def __repr__(self) -> str:
        return f"<guarded {object.__getattribute__(self, '_target')!r}>"


def _guarded_class(cls: type, name: str) -> Callable[..., _GuardedProxy]:
    """Return a factory producing guarded instances of `cls`."""

    @functools.wraps(cls, updated=())
    def factory(*args, **kwargs) -> _GuardedProxy:
        # Construction itself can hit vnstock's own quota check, so it stays
        # guarded — but it reaches no provider, so it is not paced. Charging the
        # account for building an object would let the number of objects a
        # caller happens to build decide how much data it may read.
        instance = _guard(cls, name, paced=False)(*args, **kwargs)
        return _GuardedProxy(instance, name)

    return factory


Listing = _guarded_class(_vnstock.Listing, "Listing")
Trading = _guarded_class(_vnstock.Trading, "Trading")
Quote = _guarded_class(_vnstock.Quote, "Quote")
Company = _guarded_class(_vnstock.Company, "Company")
Finance = _guarded_class(_vnstock.Finance, "Finance")
Market = _guarded_class(_vnstock.Market, "Market")
Vnstock = _guarded_class(_vnstock.Vnstock, "Vnstock")

__all__ = [
    "Company",
    "Finance",
    "Listing",
    "Market",
    "Quote",
    "Trading",
    "Vnstock",
    "VnstockUnavailable",
    "VnstockUnsupported",
]
