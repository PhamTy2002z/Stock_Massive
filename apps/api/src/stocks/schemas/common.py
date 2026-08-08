"""Schemas shared across stock domains."""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for the stock response schemas.

    Pydantic defaults to dropping unknown keyword arguments, so a builder that
    passes a field name the schema never declared produces a model full of
    Nones and an endpoint that answers 200 with empty data. Rejecting unknown
    fields turns that into an error at the point of construction.
    """

    model_config = ConfigDict(extra="forbid")


class MessageResponse(StrictModel):
    """Generic acknowledgement returned by action endpoints."""

    message: str
    status: Optional[str] = None
