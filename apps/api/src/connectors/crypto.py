"""Connector secrets at rest: MultiFernet over the configured key list.

The first key encrypts and every key decrypts, so rotating is: put the new key
first, keep the old one after it, re-encrypt with :func:`rotate`, then drop the
old key. A token nobody can decrypt is an error, never an empty credential.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from src.core.config import get_settings


class ConnectorKeyMissing(RuntimeError):
    """Connectors are on but no encryption key is configured."""


class ConnectorSecretUnreadable(ValueError):
    """A stored secret no configured key can open."""


def _cipher(keys: str | None = None) -> MultiFernet:
    raw = get_settings().connectors_encryption_keys if keys is None else keys
    parsed = [item.strip() for item in raw.split(",") if item.strip()]
    if not parsed:
        raise ConnectorKeyMissing("CONNECTORS_ENCRYPTION_KEYS is empty")
    return MultiFernet([Fernet(item.encode()) for item in parsed])


def encrypt(secret: Mapping[str, Any], *, keys: str | None = None) -> str:
    payload = json.dumps(dict(secret), separators=(",", ":"), sort_keys=True)
    return _cipher(keys).encrypt(payload.encode()).decode()


def decrypt(token: str | None, *, keys: str | None = None) -> dict[str, Any]:
    if not token:
        return {}
    try:
        return json.loads(_cipher(keys).decrypt(token.encode()))
    except InvalidToken as exc:
        raise ConnectorSecretUnreadable("no configured key opens this secret") from exc


def rotate(token: str, *, keys: str | None = None) -> str:
    """The same secret, re-encrypted under the first key."""
    return _cipher(keys).rotate(token.encode()).decode()


def new_key() -> str:
    return Fernet.generate_key().decode()


__all__ = [
    "ConnectorKeyMissing",
    "ConnectorSecretUnreadable",
    "decrypt",
    "encrypt",
    "new_key",
    "rotate",
]
