"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from apscheduler import AsyncScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.core.database import engine
from src.core.scheduler import setup_scheduler
from src.stocks.router import router as stocks_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    if settings.scheduler_enabled:
        async with AsyncScheduler() as scheduler:
            await setup_scheduler(scheduler)
            await scheduler.start_in_background()
            logger.info("Scheduler started")
            yield
    else:
        yield
    # Shutdown: dispose database engine
    await engine.dispose()


app = FastAPI(
    title="Stock Massive API",
    description="Stock analysis platform API with Vietnamese market data",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stocks_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Stock Massive API"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
