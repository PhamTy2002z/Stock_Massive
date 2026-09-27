"""A bounded worker pool for blocking tool work, kept apart from the default one.

``asyncio.to_thread`` runs on the event loop's default executor, which is also
where every synchronous database session, checkpoint and LLM reservation runs.
A blocking tool — a provider read pacing itself under a rate gate, a page that
drips one byte at a time — holds its worker until its own internal limit ends
it, and ``wait_for`` giving up on the call does not give the thread back. Put on
the shared pool, a handful of slow sources is enough to starve the work that
settles Turns.

So blocking tool work gets its own pool. When it is saturated, what waits is
the next tool call, which is already bounded by its declared timeout and is
answered as one; the database work behind it never notices.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import ParamSpec, TypeVar

#: One round dispatches at most sixteen calls that leave the deployment
#: (``executor.MAX_EXTERNAL_CALLS_PER_ROUND``), so one round's fan-out fits
#: without queueing. Concurrent Turns share it and queue behind each other,
#: which is the point: they queue here instead of in the database's pool.
MAX_WORKERS = 16

P = ParamSpec("P")
R = TypeVar("R")

_pool: ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()


def blocking_pool() -> ThreadPoolExecutor:
    """The process-wide pool, created on first use."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadPoolExecutor(
                    max_workers=MAX_WORKERS, thread_name_prefix="blocking-tool"
                )
    return _pool


async def run_blocking(
    func: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs
) -> R:
    """``asyncio.to_thread`` on :func:`blocking_pool` instead of the default pool.

    The caller's context variables travel with the call, exactly as
    ``to_thread`` carries them, so request-scoped state read inside the worker
    is the state of the call that sent it there.
    """
    loop = asyncio.get_running_loop()
    context = contextvars.copy_context()
    call = functools.partial(context.run, func, *args, **kwargs)
    return await loop.run_in_executor(blocking_pool(), call)


__all__ = ["MAX_WORKERS", "blocking_pool", "run_blocking"]
