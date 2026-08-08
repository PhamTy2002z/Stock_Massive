"""Business logic for registration, login, and refresh-token rotation."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings

from .models import RefreshToken, User
from .security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

settings = get_settings()


class AuthError(Exception):
    """Base class for auth failures the router maps to HTTP responses."""


class EmailAlreadyRegistered(AuthError):
    """Signup used an email that already has an account."""


class InvalidCredentials(AuthError):
    """Email/password pair did not match an active user."""


class InvalidRefreshToken(AuthError):
    """Refresh token is unknown, expired, or already used."""


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _utcnow() -> datetime:
    """Naive UTC now, matching the DateTime columns (which are timezone-less)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """Look up a user by primary key."""
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Look up a user by email, case-insensitively."""
    result = await session.execute(select(User).where(User.email == _normalize_email(email)))
    return result.scalar_one_or_none()


async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    full_name: Optional[str] = None,
) -> User:
    """Create a new account, or raise `EmailAlreadyRegistered`."""
    if await get_user_by_email(session, email) is not None:
        raise EmailAlreadyRegistered(email)

    user = User(
        email=_normalize_email(email),
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, or raise `InvalidCredentials`."""
    user = await get_user_by_email(session, email)

    # Hash even when the user is missing, so a wrong email and a wrong password
    # take comparable time and cannot be distinguished by response latency.
    if user is None:
        hash_password(password)
        raise InvalidCredentials(email)

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentials(email)
    if not user.is_active:
        raise InvalidCredentials(email)
    return user


async def issue_refresh_token(session: AsyncSession, user_id: int) -> str:
    """Mint and persist a refresh token, returning the plaintext value."""
    token = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            expires_at=_utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await session.flush()
    return token


async def _revoke_all_for_user(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[User, str]:
    """Consume a refresh token and issue a replacement.

    Presenting an already-revoked token means the token leaked and is being
    replayed, so every session for that user is revoked rather than just this one.
    """
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    stored = result.scalar_one_or_none()

    if stored is None:
        raise InvalidRefreshToken("unknown token")

    if stored.revoked_at is not None:
        await _revoke_all_for_user(session, stored.user_id)
        # Commit before raising: get_db rolls back on exception, which would
        # otherwise discard the revocation we just performed.
        await session.commit()
        raise InvalidRefreshToken("token reuse detected")

    if stored.expires_at <= _utcnow():
        raise InvalidRefreshToken("expired token")

    user = await get_user_by_id(session, stored.user_id)
    if user is None or not user.is_active:
        raise InvalidRefreshToken("inactive user")

    stored.revoked_at = _utcnow()
    new_token = await issue_refresh_token(session, user.id)
    return user, new_token


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    """Revoke a single refresh token. Unknown tokens are a no-op."""
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )


def access_token_for(user: User) -> tuple[str, int]:
    """Return an access token for `user` and its lifetime in seconds."""
    return create_access_token(user.id), settings.access_token_expire_minutes * 60
