"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from apscheduler import AsyncScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agent.router import router as alpha_desk_router
from src.agent.service import close_alpha_desk
from src.agent.turns import sweep_interrupted_turns
from src.alpha.analysis_router import router as analysis_router
from src.alpha.router import router as watchlist_router
from src.alpha.refusals import AlphaRefusal
from src.alpha.widget_router import router as widget_router
from src.auth.router import router as auth_router
from src.core.config import get_settings
from src.core.cache import CacheRefreshUnavailable
from src.core.database import engine
from src.core.llm import (
    CapabilityProbe,
    Workload,
    build_client,
    enforce_budget_validation,
    enforce_capability_probe,
    llm_config_from_settings,
)
from src.core.quota import QuotaRefused
from src.core.scheduler import setup_scheduler
from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported
from src.stocks.router import router as stocks_router
from src.stocks.jobs_router import router as jobs_router
from src.stocks.signals.router import router as signals_router
from src.stocks.shared import StockServiceError
from src.stocks.universe import Universe

# Configure logging at module level - ensures INFO logs are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def run_capability_probe_at_startup(config) -> None:
    """Run paid route checks only behind the explicit configuration flag."""
    if not get_settings().llm_capability_probe_enabled:
        logger.info("Capability Probe skipped by explicit configuration")
        return

    client = build_client(config)
    try:
        result = await CapabilityProbe(
            client,
            model=config.model_for(Workload.SESSION),
        ).run()
    finally:
        await client.aclose()
    enforce_capability_probe(result, alpha_desk_enabled=config.enabled)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    # Before anything else starts: a Universe that cannot be honoured is a
    # configuration mistake, and the operator should meet it here rather than
    # hours later inside a collector run nobody is watching.
    #
    # Only the declared half is checked here. The cohort half is seated from the
    # database by whoever collects or serves, and a startup that refused to boot
    # over it would take the API down for a data problem it cannot fix.
    universe = Universe.from_settings(get_settings())
    logger.info(f"Universe declares {len(universe)} symbols")

    # Immediately after the Universe and before the scheduler starts, for the
    # same reason and at zero cost: Budget Validation is arithmetic over the
    # configured models and prices (docs/adr/0014). A route that cannot fund
    # one Analysis or one Turn fails here rather than midway through the first
    # real Turn — and with Alpha Desk off it only logs, because there is
    # nothing to protect.
    llm_config = llm_config_from_settings(get_settings())
    enforce_budget_validation(llm_config)

    # The paid route contract comes after the local Universe and budget checks
    # and before the scheduler can create any workload that depends on it.
    await run_capability_probe_at_startup(llm_config)

    # Any Turn a crash or a deploy left active is frozen here, from its own
    # checkpoint, and marked incomplete (docs/adr/0013). V1 never resumes model
    # or tool execution after a restart: replaying a non-deterministic model
    # against a store that has moved overnight would produce a plausible
    # continuation rather than the answer that was interrupted. Unconditional,
    # and not behind `alpha_desk_enabled` — a deployment that switched Alpha
    # Desk off is exactly the one that would otherwise leave Turns stuck active
    # for good.
    await sweep_interrupted_turns()

    if settings.scheduler_enabled:
        async with AsyncScheduler() as scheduler:
            await setup_scheduler(scheduler)
            await scheduler.start_in_background()

            # Log scheduler state for visibility
            schedules = await scheduler.get_schedules()
            logger.info(f"Scheduler started with {len(schedules)} schedules")
            for s in schedules:
                logger.info(f"  Schedule: {s.id} -> next_fire={s.next_fire_time}")

            # Store scheduler reference in app state for health checks
            app.state.scheduler = scheduler
            yield
    else:
        logger.info("Scheduler disabled by config")
        yield
    # Shutdown. Active Turns get their thirty seconds to reach a safe
    # checkpoint before the pool goes away, because the checkpoint that window
    # buys is written through it (docs/adr/0013). Whatever does not make it is
    # left for the startup sweep, which is the same honest `incomplete` a crash
    # would have produced.
    await close_alpha_desk()
    await engine.dispose()


app = FastAPI(
    title="Stock Massive API",
    description="Stock analysis platform API with Vietnamese market data",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - origins from config (comma-separated)
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(stocks_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
# Signals sit beside /stocks rather than inside it: a signal is an answer about
# a set of symbols, and mounting it under a path that reads as one symbol's data
# would misdescribe every route added here later.
app.include_router(signals_router, prefix="/api/v1")
# The Watchlist is one user's choice rather than market data, so it sits beside
# /stocks rather than under it.
app.include_router(watchlist_router, prefix="/api/v1")
# An Analysis is keyed by (symbol, trading_day) and shared system-wide, so it
# sits beside the Watchlist rather than under it: it never belonged to one
# user's list, which is why removing a symbol deletes nothing.
app.include_router(analysis_router, prefix="/api/v1")
# A Widget's data is read back through the message that stores its descriptor,
# so it belongs beside the transcript's own resources: the route answers "what
# did this answer draw", not "what is FPT worth".
app.include_router(widget_router, prefix="/api/v1")
# Threads and Turns, mounted beside the Watchlist for the same reason: they are
# one user's conversation rather than market data. The browser reaches them at
# `/api/alpha-desk/threads/...` through the Next proxy, whose allowlist names
# `threads` and `turns` as two of the resources it will carry (docs/adr/0013).
app.include_router(alpha_desk_router, prefix="/api/v1")


@app.exception_handler(AlphaRefusal)
async def alpha_refusal_handler(request: Request, exc: AlphaRefusal):
    """An Alpha Desk request refused for a named reason (`src/alpha/refusals.py`).

    A refusal that knows when its allowance resets says so. `reset_at` is the
    actionable half of a 429 — a rule the caller can act on has a moment it
    stops applying — and the refusals that have no such moment simply omit the
    key rather than carry a guess: `docs/adr/0013` is deliberate that a capacity
    refusal carries no retry hint, because the only number that could go there
    would be a guess at when someone else's Turn ends.
    """
    detail = {"reason": exc.reason, "message": exc.message}
    reset_at = getattr(exc, "reset_at", None)
    if reset_at is not None:
        detail["reset_at"] = reset_at.isoformat()
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(StockServiceError)
async def stock_service_error_handler(request: Request, exc: StockServiceError):
    """Map upstream stock service failures to HTTP 502."""
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)},
    )


@app.exception_handler(VnstockUnavailable)
async def vnstock_unavailable_handler(request: Request, exc: VnstockUnavailable):
    """Upstream quota exhausted — a retryable condition, not a server fault."""
    logger.warning(f"vnstock unavailable on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
        headers={"Retry-After": "60"},
    )


@app.exception_handler(QuotaRefused)
async def quota_refused_handler(request: Request, exc: QuotaRefused):
    """The account allowance would not admit this call (`src/core/quota.py`).

    Retryable and not a server fault, like an exhausted upstream quota: the
    Collector is holding the provider, or Redis is down and a Provider Source
    call with no arbiter is one nothing is counting. Store-backed endpoints
    never reach this handler, and that is the point of failing closed here
    rather than falling back to a pace no other process can see.
    """
    logger.warning("vnstock allowance refused %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
        headers={"Retry-After": "60"},
    )


@app.exception_handler(VnstockUnsupported)
async def vnstock_unsupported_handler(request: Request, exc: VnstockUnsupported):
    """The provider has no such capability. Say so instead of returning empty."""
    logger.info(f"vnstock unsupported on {request.url.path}: {exc}")
    return JSONResponse(status_code=501, content={"detail": str(exc)})


@app.exception_handler(CacheRefreshUnavailable)
async def cache_refresh_unavailable_handler(
    request: Request,
    exc: CacheRefreshUnavailable,
):
    """Suppress duplicate cold-miss retries while an upstream is unavailable."""
    logger.warning("cache refresh suppressed on %s", request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
        headers={"Retry-After": "15"},
    )



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure CORS headers on errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Stock Massive API"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/scheduler/status")
async def scheduler_status():
    """Scheduler health check - shows registered schedules and their next fire times."""
    if not hasattr(app.state, "scheduler"):
        return {"enabled": False, "message": "Scheduler not initialized"}

    scheduler = app.state.scheduler
    schedules = await scheduler.get_schedules()

    return {
        "enabled": True,
        "state": scheduler.state.name,
        "schedule_count": len(schedules),
        "schedules": [
            {
                "id": s.id,
                "next_fire_time": s.next_fire_time.isoformat() if s.next_fire_time else None,
            }
            for s in schedules
        ],
    }
