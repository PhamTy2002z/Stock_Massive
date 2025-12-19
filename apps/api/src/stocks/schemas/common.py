"""Common schemas shared across domains."""

from datetime import date

from pydantic import BaseModel, Field


class HistoryParams(BaseModel):
    """Query parameters for history endpoint."""

    start: date = Field(..., description="Start date (YYYY-MM-DD)")
    end: date = Field(..., description="End date (YYYY-MM-DD)")
    interval: str = Field("1D", description="Interval: 1D, 1W, 1M")


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str = "error"
