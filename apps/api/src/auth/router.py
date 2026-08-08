"""Auth endpoints: register, login, refresh, logout, me."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.ratelimit import heavy_rate_limit

from .dependencies import CurrentUser
from .schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from .service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
    access_token_for,
    authenticate_user,
    issue_refresh_token,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]

# Credential endpoints use the heavy limiter (20/60s) to blunt brute forcing.
_CREDENTIAL_LIMIT = [Depends(heavy_rate_limit)]


def _token_pair(user, refresh_token: str) -> TokenPair:
    access_token, expires_in = access_token_for(user)
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    dependencies=_CREDENTIAL_LIMIT,
)
async def register(payload: RegisterRequest, session: SessionDep) -> TokenPair:
    """Create an account and return a token pair."""
    try:
        user = await register_user(
            session,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    except EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    refresh_token = await issue_refresh_token(session, user.id)
    return _token_pair(user, refresh_token)


@router.post("/login", response_model=TokenPair, dependencies=_CREDENTIAL_LIMIT)
async def login(payload: LoginRequest, session: SessionDep) -> TokenPair:
    """Exchange credentials for a token pair."""
    try:
        user = await authenticate_user(session, payload.email, payload.password)
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    refresh_token = await issue_refresh_token(session, user.id)
    return _token_pair(user, refresh_token)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: SessionDep) -> TokenPair:
    """Rotate a refresh token for a fresh token pair."""
    try:
        user, new_refresh_token = await rotate_refresh_token(session, payload.refresh_token)
    except InvalidRefreshToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    return _token_pair(user, new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, session: SessionDep) -> None:
    """Revoke a refresh token. Idempotent — unknown tokens still return 204."""
    await revoke_refresh_token(session, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the authenticated user."""
    return UserResponse.model_validate(current_user)
