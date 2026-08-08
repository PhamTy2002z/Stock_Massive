"""Unit tests for password hashing and JWT handling (no DB, no app)."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.auth.security import (
    MAX_PASSWORD_BYTES,
    TokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from src.core.config import get_settings

settings = get_settings()


class TestPasswordHashing:
    """bcrypt hashing behaviour."""

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"
        assert hashed.startswith("$2")

    def test_verify_accepts_correct_password(self):
        assert verify_password("s3cret-pass", hash_password("s3cret-pass"))

    def test_verify_rejects_wrong_password(self):
        assert not verify_password("wrong-pass", hash_password("s3cret-pass"))

    def test_same_password_hashes_differently(self):
        """Distinct salts, so identical passwords must not share a hash."""
        assert hash_password("same-pass") != hash_password("same-pass")

    def test_max_password_length_matches_bcrypt_limit(self):
        """Schemas cap input here because bcrypt ignores bytes past 72."""
        assert MAX_PASSWORD_BYTES == 72

    def test_accepts_password_at_the_byte_limit(self):
        at_limit = "a" * MAX_PASSWORD_BYTES
        assert verify_password(at_limit, hash_password(at_limit))

    def test_verify_rejects_malformed_hash_instead_of_raising(self):
        """A corrupt hash in the column must read as a failed login, not a 500."""
        assert not verify_password("any-password", "not-a-bcrypt-hash")

    def test_verifies_hash_produced_by_passlib(self):
        """Hashes written before the passlib removal must still authenticate."""
        # $2b$ bcrypt hash of "sup3r-secret-pw", generated via passlib 1.7.4.
        legacy = "$2b$12$mK9QdZ6dVpHH0M5EqhBagux4agM2fiS/eocrmOqOwIgq0RxJldGHi"
        assert verify_password("sup3r-secret-pw", legacy)
        assert not verify_password("wrong-password", legacy)


class TestAccessToken:
    """Access token minting and validation."""

    def test_roundtrip_carries_user_id(self):
        payload = decode_access_token(create_access_token(42))
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_rejects_token_signed_with_other_secret(self):
        forged = jwt.encode(
            {"sub": "1", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            "not-the-real-secret",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(TokenError):
            decode_access_token(forged)

    def test_rejects_expired_token(self):
        expired = jwt.encode(
            {
                "sub": "1",
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            settings.auth_secret,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(TokenError):
            decode_access_token(expired)

    def test_rejects_refresh_typed_token(self):
        """A token of the wrong type must not authenticate a request."""
        wrong_type = jwt.encode(
            {
                "sub": "1",
                "type": "refresh",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            settings.auth_secret,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(TokenError):
            decode_access_token(wrong_type)

    def test_rejects_garbage(self):
        with pytest.raises(TokenError):
            decode_access_token("not-a-jwt")


class TestRefreshToken:
    """Opaque refresh token generation and hashing."""

    def test_tokens_are_unique(self):
        assert generate_refresh_token() != generate_refresh_token()

    def test_hash_is_stable_and_fits_column(self):
        token = generate_refresh_token()
        digest = hash_refresh_token(token)
        assert digest == hash_refresh_token(token)
        assert len(digest) == 64  # matches String(64) on refresh_tokens.token_hash

    def test_hash_differs_per_token(self):
        assert hash_refresh_token(generate_refresh_token()) != hash_refresh_token(
            generate_refresh_token()
        )
