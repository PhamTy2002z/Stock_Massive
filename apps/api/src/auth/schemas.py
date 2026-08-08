"""Pydantic schemas for auth endpoints."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .security import MAX_PASSWORD_BYTES


class RegisterRequest(BaseModel):
    """Payload for creating an account."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)
    full_name: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """Payload for exchanging credentials for tokens."""
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_BYTES)


class RefreshRequest(BaseModel):
    """Payload carrying a refresh token."""
    refresh_token: str


class TokenPair(BaseModel):
    """Access + refresh token pair returned by login/register/refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token lifetime in seconds


class UserResponse(BaseModel):
    """Public view of a user."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
