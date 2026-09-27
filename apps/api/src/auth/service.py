"""Business logic for registration, login, and refresh-token rotation."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings

from .models import RefreshToken, User
from .schemas import UpdateMeRequest, UserPreferences
from .security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

settings = get_settings()

# What an unknown email is checked against, so it pays the same bcrypt cost as a
# wrong password without a hash of its own. Computed once, at import.
_DUMMY_HASH = hash_password("dummy-password-for-timing")

# A token row is kept past its expiry so a replay is still recognised as reuse;
# past this long after expiry it is pruned when its user is next issued one.
_PRUNE_EXPIRED_AFTER = timedelta(days=7)


class AuthError(Exception):
    """Base class for auth failures the router maps to HTTP responses."""


class EmailAlreadyRegistered(AuthError):
    """Signup used an email that already has an account."""


class InvalidCredentials(AuthError):
    """Email/password pair did not match an active user."""


class InvalidRefreshToken(AuthError):
    """Refresh token is unknown, expired, or already used."""


class IncorrectPassword(AuthError):
    """A signed-in user's password change named the wrong current password."""


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
    try:
        await session.flush()
    except IntegrityError as exc:
        # Two signups for one email raced past the lookup above; the unique
        # index decided, and the loser is told what a later signup is told.
        raise EmailAlreadyRegistered(email) from exc
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, or raise `InvalidCredentials`."""
    user = await get_user_by_email(session, email)

    # Check against a dummy hash when the user is missing, so a wrong email and
    # a wrong password take comparable time and fail the same way.
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentials(email)

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentials(email)
    if not user.is_active:
        raise InvalidCredentials(email)
    return user


async def issue_refresh_token(session: AsyncSession, user_id: int) -> str:
    """Mint and persist a refresh token, returning the plaintext value.

    Also prunes this user's rows long past expiry, so the table does not grow
    with every sign-in forever. Bounded by the user and served by the
    ``(user_id, expires_at)`` index.
    """
    now = _utcnow()
    await session.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.expires_at < now - _PRUNE_EXPIRED_AFTER,
        )
    )
    token = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await session.flush()
    return token


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: int) -> None:
    """Revoke every live refresh token of one user: each session they have."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[User, str]:
    """Consume a refresh token and issue a replacement.

    Presenting an already-revoked token means the token leaked and is being
    replayed, so every session for that user is revoked rather than just this one.

    The token is consumed by one conditional ``UPDATE``, so of two requests
    presenting the same live token exactly one wins; the row lock makes the
    other re-read it as revoked, and it is answered as a replay.
    """
    token_hash = hash_refresh_token(token)
    now = _utcnow()
    consumed = await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(revoked_at=now)
        .returning(RefreshToken.user_id)
    )
    user_id = consumed.scalar_one_or_none()

    if user_id is None:
        stored = (
            await session.execute(
                select(RefreshToken.user_id, RefreshToken.revoked_at).where(
                    RefreshToken.token_hash == token_hash
                )
            )
        ).one_or_none()
        if stored is None:
            raise InvalidRefreshToken("unknown token")
        if stored.revoked_at is not None:
            await revoke_all_refresh_tokens(session, stored.user_id)
            # Commit before raising: get_db rolls back on exception, which would
            # otherwise discard the revocation we just performed.
            await session.commit()
            raise InvalidRefreshToken("token reuse detected")
        raise InvalidRefreshToken("expired token")

    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        # Raising rolls the consumption back with the rest of the transaction.
        raise InvalidRefreshToken("inactive user")

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


async def change_password(
    session: AsyncSession, user: User, current_password: str, new_password: str
) -> str:
    """Replace the password, end every other session, and return a fresh token.

    Every refresh token is revoked, the caller's own included, because a
    password change is what a reader does when they think somebody else is
    signed in. The replacement issued afterwards keeps the browser that made the
    change signed in. Access tokens already issued live out their few minutes:
    they are self-contained and there is nothing to revoke.
    """
    if not verify_password(current_password, user.hashed_password):
        raise IncorrectPassword(user.id)
    user.hashed_password = hash_password(new_password)
    await revoke_all_refresh_tokens(session, user.id)
    return await issue_refresh_token(session, user.id)


async def update_me(session: AsyncSession, user: User, payload: UpdateMeRequest) -> User:
    """Write what the request sent, and only that.

    Presence decides, not value: a key the client left out keeps its stored
    value, and a key sent as null clears it. Preferences are merged onto the
    stored document read leniently, and written back whole as a new object —
    the column is plain JSONB with no mutation tracking, so an in-place edit of
    the dict would never be flushed.
    """
    sent = payload.model_fields_set
    if "full_name" in sent:
        user.full_name = payload.full_name
    patch = payload.preferences
    if "preferences" in sent and patch is not None:
        merged = UserPreferences.from_stored(user.preferences).model_dump()
        for key in patch.model_fields_set:
            value = getattr(patch, key)
            if key == "memory_enabled" and value is None:
                continue
            merged[key] = value
        user.preferences = UserPreferences.model_validate(merged).model_dump()
    await session.flush()
    # ``updated_at`` is set by the database on flush, which expires it; an
    # async session cannot lazy-load it later, so the row is re-read here.
    await session.refresh(user)
    return user


def access_token_for(user: User) -> tuple[str, int]:
    """Return an access token for `user` and its lifetime in seconds."""
    return create_access_token(user.id), settings.access_token_expire_minutes * 60
