"""DNSE REST and WebSocket HMAC authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
from types import MappingProxyType
from typing import Callable, Mapping
from urllib.parse import quote
from uuid import uuid4
from threading import Lock


@dataclass(frozen=True, slots=True, repr=False)
class DnseCredentials:
    api_key: str
    api_secret: str

    def __post_init__(self) -> None:
        if not self.api_key.strip() or not self.api_secret.strip():
            raise ValueError("DNSE API key and secret are required")

    def __repr__(self) -> str:
        return "DnseCredentials(api_key=<redacted>, api_secret=<redacted>)"


class RestSigner:
    """Create a fresh official HTTP Signature header for one request."""

    def __init__(
        self,
        credentials: DnseCredentials,
        *,
        api_version: str = "2026-07-23",
        clock: Callable[[], datetime] | None = None,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        self._credentials = credentials
        self._api_version = api_version
        self._clock = clock or (lambda: datetime.now(UTC))
        self._nonce_factory = nonce_factory or (lambda: uuid4().hex)
        self._nonce_lock = Lock()
        self._last_nonce: str | None = None

    def headers(self, method: str, path: str) -> Mapping[str, str]:
        if not path.startswith("/") or "?" in path:
            raise ValueError("signature path must be an absolute path without query")
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("signing clock must return a timezone-aware datetime")
        date_value = format_datetime(now.astimezone(UTC))
        with self._nonce_lock:
            nonce = self._nonce_factory()
            if nonce == self._last_nonce:
                raise ValueError("REST nonce must not be reused")
            self._last_nonce = nonce
        if len(nonce) != 32 or any(char not in "0123456789abcdef" for char in nonce):
            raise ValueError("REST nonce must be 32 lowercase hexadecimal characters")
        signing = (
            f"(request-target): {method.lower()} {path}\n"
            f"date: {date_value}\nnonce: {nonce}"
        )
        digest = hmac.new(
            self._credentials.api_secret.encode(), signing.encode(), hashlib.sha256
        ).digest()
        encoded = quote(base64.b64encode(digest).decode(), safe="")
        signature = (
            f'Signature keyId="{self._credentials.api_key}",'
            'algorithm="hmac-sha256",headers="(request-target) date",'
            f'signature="{encoded}",nonce="{nonce}"'
        )
        return MappingProxyType(
            {
                "X-Api-Key": self._credentials.api_key,
                "X-Signature": signature,
                "Date": date_value,
                "version": self._api_version,
            }
        )


class WebSocketSigner:
    """Create DNSE's JSON WebSocket authentication message."""

    def __init__(
        self,
        credentials: DnseCredentials,
        *,
        timestamp: Callable[[], float] | None = None,
    ) -> None:
        import time

        self._credentials = credentials
        self._timestamp = timestamp or time.time
        self._nonce_lock = Lock()
        self._last_nonce = 0

    def message(self) -> dict[str, str | int]:
        now = self._timestamp()
        seconds = int(now)
        candidate = int(now * 1_000_000)
        with self._nonce_lock:
            candidate = max(candidate, self._last_nonce + 1)
            self._last_nonce = candidate
        nonce = str(candidate)
        material = f"{self._credentials.api_key}:{seconds}:{nonce}"
        signature = hmac.new(
            self._credentials.api_secret.encode(), material.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "action": "auth",
            "api_key": self._credentials.api_key,
            "signature": signature,
            "timestamp": seconds,
            "nonce": nonce,
        }
