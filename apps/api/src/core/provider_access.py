"""Runtime authority boundary for calls to a Provider Source."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_provider_sources_forbidden: ContextVar[bool] = ContextVar(
    "provider_sources_forbidden", default=False
)


class ProviderSourceAccessForbidden(RuntimeError):
    """A store-only execution path attempted a live provider call."""


@contextmanager
def store_only_execution() -> Iterator[None]:
    """Forbid Provider Source calls in this async task and copied threads."""

    token = _provider_sources_forbidden.set(True)
    try:
        yield
    finally:
        _provider_sources_forbidden.reset(token)


def ensure_provider_source_allowed() -> None:
    """Fail before quota, credentials, or a network connection are touched."""

    if _provider_sources_forbidden.get():
        raise ProviderSourceAccessForbidden(
            "a store-only Tool Catalog call cannot reach a Provider Source"
        )
