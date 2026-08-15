"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from apscheduler import AsyncScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.alpha.analysis_router import router as analysis_router
from src.alpha.router import router as watchlist_router
from src.alpha.refusals import AlphaRefusal
from src.auth.router import router as auth_router
from src.core.config import get_settings
from src.core.cache import CacheRefreshUnavailable
from src.core.database import engine
from src.core.llm import enforce_budget_validation, llm_config_from_settings
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
    enforce_budget_validation(llm_config_from_settings(get_settings()))

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
    # Shutdown: dispose database engine
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


@app.exception_handler(AlphaRefusal)
async def alpha_refusal_handler(request: Request, exc: AlphaRefusal):
    """An Alpha Desk request refused for a named reason (`src/alpha/refusals.py`)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"reason": exc.reason, "message": exc.message}},
    )


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
