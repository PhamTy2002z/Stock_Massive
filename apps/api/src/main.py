"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.stocks.router import router as stocks_router

app = FastAPI(
    title="Stock Massive API",
    description="Stock analysis platform API with Vietnamese market data",
    version="0.1.0",
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
