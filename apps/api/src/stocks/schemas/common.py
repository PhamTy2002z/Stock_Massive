"""Schemas shared across stock domains."""

from typing import Optional

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic acknowledgement returned by action endpoints."""

    message: str
    status: Optional[str] = None
