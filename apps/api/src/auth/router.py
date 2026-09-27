"""Auth endpoints: register, login, refresh, logout, me, and account settings."""
import asyncio
import hashlib
import logging
import threading
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.config import get_settings
from src.core.database import DbSession
from src.core.ratelimit import credential_rate_limit
from src.core.redis import get_redis

from .dependencies import CurrentUser
from .schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UpdateMeRequest,
    UserResponse,
)
from .service import (
    EmailAlreadyRegistered,
    IncorrectPassword,
    InvalidCredentials,
    InvalidRefreshToken,
    _normalize_email,
    access_token_for,
    authenticate_user,
    change_password,
    issue_refresh_token,
    register_user,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
    update_me,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = DbSession

# Credential endpoints get their own fail-closed allowance per client address,
# to blunt brute forcing even while Redis is down.
_CREDENTIAL_LIMIT = [Depends(credential_rate_limit)]


class _FailedLoginLimit:
    """Failed sign-ins charged to the account tried, not to the caller.

    The address limiter alone lets guesses at one account be spread across many
    addresses. Only a *failed* attempt is counted, and the allowance is checked
    before the password is: counting every attempt would let anyone who knows
    an email lock its owner out by signing in as them, correctly or not. The
    key is a hash of the email, so no address book ends up in Redis keys or in
    a log line.

    Fail-closed like the credential limiter: without Redis the count is kept in
    process, which is still a limit where failing open is none.
    """

    MAX_KEYS = 10_000

    def __init__(self, max_failures: int, window: int, prefix: str) -> None:
        self.max_failures = max_failures
        self.window = window
        self.prefix = prefix
        self._local: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _redis_count(self, account: str, record: bool) -> int | None:
        redis = get_redis()
        if not redis:
            return None
        key = f"stock_massive:ratelimit:{self.prefix}:{account}:{int(time.time()) // self.window}"
        if not record:
            return int(redis.get(key) or 0)
        current = int(redis.incr(key))
        if current == 1:
            redis.expire(key, self.window + 1)
        return current

    def _local_count(self, account: str, record: bool) -> int:
        now = time.monotonic()
        with self._lock:
            hits = self._local.pop(account, None) or deque()
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if record:
                hits.append(now)
            if hits:
                # Re-inserted, so the dict's order is least recently touched
                # first and the eviction below drops the stalest account.
                self._local[account] = hits
            while len(self._local) > self.MAX_KEYS:
                del self._local[next(iter(self._local))]
            return len(hits)

    async def _count(self, account: str, *, record: bool) -> int:
        try:
            # Off the event loop: the Redis clients are synchronous.
            counted = await asyncio.to_thread(self._redis_count, account, record)
        except Exception as exc:  # noqa: BLE001 - an outage falls back, never opens
            logger.warning("Failed-login count unavailable (%s): %s", self.prefix, exc)
            counted = None
        return self._local_count(account, record) if counted is None else counted

    async def check(self, account: str) -> None:
        """Refuse with 429 while this account is over its failure allowance."""
        if not get_settings().rate_limit_enabled:
            return
        if await self._count(account, record=False) < self.max_failures:
            return
        reset = (int(time.time()) // self.window + 1) * self.window
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Rate limit exceeded. Try again later.",
                "limit": self.max_failures,
                "remaining": 0,
                "reset": reset,
            },
            headers={"Retry-After": str(max(reset - int(time.time()), 1))},
        )

    async def record_failure(self, account: str) -> None:
        if get_settings().rate_limit_enabled:
            await self._count(account, record=True)


#: Higher than the per-address allowance: this one is shared by everyone who
#: types the account's email, including its owner.
_login_account_limit = _FailedLoginLimit(
    max_failures=50, window=10 * 60, prefix="credential-account-failures"
)


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
    account = hashlib.sha256(_normalize_email(payload.email).encode()).hexdigest()
    await _login_account_limit.check(account)
    try:
        user = await authenticate_user(session, payload.email, payload.password)
    except InvalidCredentials:
        await _login_account_limit.record_failure(account)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    refresh_token = await issue_refresh_token(session, user.id)
    return _token_pair(user, refresh_token)


@router.post("/refresh", response_model=TokenPair, dependencies=_CREDENTIAL_LIMIT)
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


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    payload: UpdateMeRequest, current_user: CurrentUser, session: SessionDep
) -> UserResponse:
    """Update the account's name and preferences; only keys sent are written."""
    return UserResponse.model_validate(await update_me(session, current_user, payload))


@router.post("/password", response_model=TokenPair, dependencies=_CREDENTIAL_LIMIT)
async def change_current_password(
    payload: ChangePasswordRequest, current_user: CurrentUser, session: SessionDep
) -> TokenPair:
    """Change the password, sign out every session, and keep this one signed in.

    A wrong current password is 400, not 401: the caller *is* authenticated,
    and the web client reads any 401 as an expired session and signs out.
    """
    try:
        refresh_token = await change_password(
            session, current_user, payload.current_password, payload.new_password
        )
    except IncorrectPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    return _token_pair(current_user, refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(current_user: CurrentUser, session: SessionDep) -> None:
    """Revoke every refresh token of this account, this browser's included."""
    await revoke_all_refresh_tokens(session, current_user.id)
