"""Pydantic schemas for auth endpoints."""
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, Optional

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from src.agent.prompt.contract import MAX_INSTRUCTIONS_CHARS, MAX_NAME_CHARS

from .security import MAX_PASSWORD_BYTES

#: The codes the Settings form offers. Must equal
#: ``agent.prompt.contract.INVESTING_STYLES``, which is what decides whether a
#: code reaches the prompt; a test holds the two together.
InvestingStyle = Literal["long_term", "growth", "dividend", "swing", "learning"]


def _stripped(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _stripped_or_none(value: Any) -> Any:
    """A blank optional string is no value, not an empty one."""
    value = _stripped(value)
    return value or None if isinstance(value, str) else value


def _within_bcrypt_limit(value: str) -> str:
    """bcrypt refuses past 72 *bytes*, and one Vietnamese letter can take three."""
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password should be at most {MAX_PASSWORD_BYTES} bytes in UTF-8")
    return value


# ``max_length`` counts characters and stays as the cheap first bound; the
# validator is the one that matches what bcrypt counts.
Password = Annotated[str, AfterValidator(_within_bcrypt_limit)]


# The length bound sits on the ``str`` inside the ``Optional``: on the union it
# would be applied to ``None`` too.
Nickname = Annotated[
    Optional[Annotated[str, Field(max_length=MAX_NAME_CHARS)]],
    BeforeValidator(_stripped_or_none),
]
Instructions = Annotated[
    Optional[Annotated[str, Field(max_length=MAX_INSTRUCTIONS_CHARS)]],
    BeforeValidator(_stripped_or_none),
]


class RegisterRequest(BaseModel):
    """Payload for creating an account."""
    email: EmailStr
    password: Password = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)
    full_name: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """Payload for exchanging credentials for tokens."""
    email: EmailStr
    password: Password = Field(min_length=1, max_length=MAX_PASSWORD_BYTES)


class RefreshRequest(BaseModel):
    """Payload carrying a refresh token."""
    refresh_token: str


class TokenPair(BaseModel):
    """Access + refresh token pair returned by login/register/refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token lifetime in seconds


class UserPreferences(BaseModel):
    """What the reader set in Settings, as stored in ``users.preferences``.

    ``memory_enabled`` defaults on because that is how every account behaved
    before the switch existed.
    """
    model_config = ConfigDict(extra="forbid")

    nickname: Nickname = None
    investing_style: Optional[InvestingStyle] = None
    custom_instructions: Instructions = None
    memory_enabled: bool = True

    @classmethod
    def from_stored(cls, raw: Any) -> "UserPreferences":
        """Read a stored document without ever failing on it.

        The row is ours but it is not fixed: it may predate a key, carry one a
        later version dropped, or hold a value a looser version accepted. Each
        known key is validated on its own, so one bad value costs that value its
        default rather than costing the reader their account page.
        """
        if not isinstance(raw, Mapping):
            return cls()
        kept: dict[str, Any] = {}
        for key in cls.model_fields:
            if key not in raw:
                continue
            try:
                cls.model_validate({key: raw[key]})
            except ValidationError:
                continue
            kept[key] = raw[key]
        return cls.model_validate(kept)


class UserPreferencesPatch(BaseModel):
    """A partial update: only the keys the client sent are written.

    An explicit null clears a nullable preference. ``memory_enabled`` is a
    switch with no third state, so a null there means the same as leaving it
    out — the rule ``PATCH /threads/{id}`` applies to ``pinned``.
    """
    model_config = ConfigDict(extra="forbid")

    nickname: Nickname = None
    investing_style: Optional[InvestingStyle] = None
    custom_instructions: Instructions = None
    memory_enabled: Optional[bool] = None


class UpdateMeRequest(BaseModel):
    """``PATCH /auth/me``: the name on the account and the preferences behind it."""
    model_config = ConfigDict(extra="forbid")

    full_name: Annotated[
        Optional[Annotated[str, Field(min_length=1, max_length=255)]],
        BeforeValidator(_stripped),
    ] = None
    preferences: Optional[UserPreferencesPatch] = None


class ChangePasswordRequest(BaseModel):
    """``POST /auth/password``."""
    current_password: Password = Field(min_length=1, max_length=MAX_PASSWORD_BYTES)
    new_password: Password = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)

    @model_validator(mode="after")
    def _new_differs(self) -> "ChangePasswordRequest":
        if self.new_password == self.current_password:
            raise ValueError("new_password must differ from current_password")
        return self


class UserResponse(BaseModel):
    """Public view of a user."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)

    @field_validator("preferences", mode="before")
    @classmethod
    def _lenient_preferences(cls, value: Any) -> Any:
        return value if isinstance(value, UserPreferences) else UserPreferences.from_stored(value)
