"""FastAPI application entry point — post-rip-out, chat-lane baseline."""
import logging
import sys
from contextlib import asynccontextmanager

from apscheduler import AsyncScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agent.flag_router import router as message_flag_router
from src.agent.router import router as alpha_desk_router
from src.agent.service import close_alpha_desk
from src.agent.turns import sweep_interrupted_turns
from src.alpha.favicons import router as favicons_router
from src.alpha.refusals import AlphaRefusal
from src.auth.router import router as auth_router
from src.core.cache import CacheRefreshUnavailable
from src.core.config import get_settings
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
from src.stocks.shared import StockServiceError
from src.stocks.universe import Universe


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
            prompt_cache_control=config.route.prompt_cache_control,
        ).run()
    finally:
        await client.aclose()
    enforce_capability_probe(result, alpha_desk_enabled=config.enabled)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan.

    The market surfaces were ripped out on 2026-08-25; the lifespan block now
    only seats what the chat lane needs — Universe check, Budget Validation,
    Capability Probe, sweep of interrupted Turns, an empty scheduler seam.
    """
    universe = Universe.from_settings(get_settings())
    logger.info(f"Universe declares {len(universe)} symbols")

    llm_config = llm_config_from_settings(get_settings())
    enforce_budget_validation(llm_config)

    await run_capability_probe_at_startup(llm_config)

    await sweep_interrupted_turns()

    try:
        if settings.scheduler_enabled:
            async with AsyncScheduler() as scheduler:
                await setup_scheduler(scheduler)
                await scheduler.start_in_background()
                schedules = await scheduler.get_schedules()
                logger.info(f"Scheduler started with {len(schedules)} schedules")
                app.state.scheduler = scheduler
                yield
        else:
            logger.info("Scheduler disabled by config")
            yield
    finally:
        try:
            await close_alpha_desk()
        finally:
            await engine.dispose()


app = FastAPI(
    title="Stock Massive API",
    description="AI chat lane over Vietnamese equity signal store",
    version="0.2.0",
    lifespan=lifespan,
)

cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(alpha_desk_router, prefix="/api/v1")
app.include_router(message_flag_router, prefix="/api/v1")
app.include_router(favicons_router, prefix="/api/v1")


@app.exception_handler(AlphaRefusal)
async def alpha_refusal_handler(request: Request, exc: AlphaRefusal):
    detail = {"reason": exc.reason, "message": exc.message}
    reset_at = getattr(exc, "reset_at", None)
    if reset_at is not None:
        detail["reset_at"] = reset_at.isoformat()
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(StockServiceError)
async def stock_service_error_handler(request: Request, exc: StockServiceError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(QuotaRefused)
async def quota_refused_handler(request: Request, exc: QuotaRefused):
    logger.warning("account allowance refused %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
        headers={"Retry-After": "60"},
    )


@app.exception_handler(CacheRefreshUnavailable)
async def cache_refresh_unavailable_handler(request: Request, exc: CacheRefreshUnavailable):
    logger.warning("cache refresh suppressed on %s", request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
        headers={"Retry-After": "15"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
async def root():
    return {"status": "ok", "message": "Stock Massive API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/scheduler/status")
async def scheduler_status():
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
