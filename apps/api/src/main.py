"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from apscheduler import AsyncScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.auth.router import router as auth_router
from src.core.config import get_settings
from src.core.database import engine
from src.core.scheduler import setup_scheduler
from src.stocks.router import router as stocks_router
from src.stocks.jobs_router import router as jobs_router
from src.stocks.shared import StockServiceError

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


@app.exception_handler(StockServiceError)
async def stock_service_error_handler(request: Request, exc: StockServiceError):
    """Map upstream stock service failures to HTTP 502."""
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)},
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
