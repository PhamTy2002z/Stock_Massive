"""FastAPI dependencies for authenticating requests."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db

from .models import User
from .security import TokenError, decode_access_token
from .service import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the bearer token to an active user, or raise 401."""
    if credentials is None:
        raise _UNAUTHORIZED

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (TokenError, KeyError, TypeError, ValueError):
        raise _UNAUTHORIZED

    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    """Gate operational endpoints behind an admin account.

    These trigger privileged operations and cache eviction, so
    a rate limit is not sufficient — anonymous callers could still burn the API
    quota or wipe caches. 403 (not 404) because the route's existence is public
    in the OpenAPI schema anyway.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint này yêu cầu quyền quản trị.",
        )
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
