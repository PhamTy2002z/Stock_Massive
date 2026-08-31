"""FastAPI entry point for the web-first AI agent harness."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

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


def warn_if_vision_was_measured_on_another_model(config) -> None:
    """Warn when the vision flag is reused for an unmeasured model."""
    current = get_settings()
    if not config.route.vision:
        return
    measured = (current.llm_vision_measured_model or "").strip()
    configured = config.model_for(Workload.SESSION)
    if measured != configured:
        logger.warning(
            "LLM_VISION_ENABLED is on for model %r, but image support was last "
            "measured on %r",
            configured,
            measured or "<nothing>",
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate the harness, recover interrupted turns, and close resources."""
    llm_config = llm_config_from_settings(get_settings())
    enforce_budget_validation(llm_config)
    await run_capability_probe_at_startup(llm_config)
    warn_if_vision_was_measured_on_another_model(llm_config)
    await sweep_interrupted_turns()
    try:
        yield
    finally:
        try:
            await close_alpha_desk()
        finally:
            await engine.dispose()


app = FastAPI(
    title="Stock Massive API",
    description="Web-first AI agent harness for Vietnamese equity research",
    version="0.3.0",
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
async def alpha_refusal_handler(_request: Request, exc: AlphaRefusal):
    detail = {"reason": exc.reason, "message": exc.message}
    reset_at = getattr(exc, "reset_at", None)
    if reset_at is not None:
        detail["reset_at"] = reset_at.isoformat()
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(CacheRefreshUnavailable)
async def cache_refresh_unavailable_handler(
    request: Request, exc: CacheRefreshUnavailable
):
    logger.warning("cache refresh suppressed on %s", request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
        headers={"Retry-After": "15"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
async def root():
    return {"status": "ok", "message": "Stock Massive API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
