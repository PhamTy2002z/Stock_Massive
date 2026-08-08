"""Password hashing and JWT encoding/decoding.

Kept free of database and FastAPI imports so it can be unit-tested standalone.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from src.core.config import get_settings

settings = get_settings()

# bcrypt silently truncates at 72 bytes; reject longer input instead of
# accepting a password whose tail is ignored at both signup and login.
MAX_PASSWORD_BYTES = 72


class TokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    Calls bcrypt directly rather than through passlib: passlib's last release
    was 2020 and it does not support bcrypt 5.x, so depending on it would pin
    this project to an unmaintained pair of libraries.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a plaintext password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    except ValueError:
        # Malformed or non-bcrypt hash in the column — treat as a failed login
        # rather than a 500.
        return False


def create_access_token(user_id: int) -> str:
    """Mint a short-lived access token for `user_id`."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token, raising `TokenError` if unusable."""
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("type") != "access":
        raise TokenError("Not an access token")
    return payload


def generate_refresh_token() -> str:
    """Generate an opaque refresh token.

    Refresh tokens are random rather than JWTs so revocation is authoritative:
    validity is decided by the database row, never by a self-contained claim.
    """
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage.

    Plain SHA-256 is deliberate: the token is 48 random bytes, so it has no
    guessable structure for bcrypt's work factor to protect, and refresh
    happens on a hot path.
    """
    return hashlib.sha256(token.encode()).hexdigest()
