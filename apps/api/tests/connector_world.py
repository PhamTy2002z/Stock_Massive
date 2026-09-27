"""A throwaway database, two accounts and a fake MCP server, for connector tests.

The service gets its own async engine per test (``NullPool``), because every
async test runs on its own event loop and an asyncpg connection belongs to the
loop that opened it.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from src.auth.models import User
from src.connectors import netguard
from src.connectors.crypto import new_key
from src.connectors.models import (
    ConnectorCatalog,
    ConnectorOAuthState,
    UserConnector,
    UserConnectorPreference,
)
from src.connectors.service import ConnectorService
from src.core.config import Settings
from src.core.database import Base, to_asyncpg_url

from .fake_mcp import FakeMCP
from .throwaway_db import create_database, drop_database

TABLES = [
    User.__table__,
    ConnectorCatalog.__table__,
    UserConnector.__table__,
    ConnectorOAuthState.__table__,
    UserConnectorPreference.__table__,
]


@dataclass
class World:
    url: str
    alice: int
    bob: int
    keys: str
    server: FakeMCP

    def settings(self, **overrides) -> Settings:
        values = {
            "deployment_profile": "personal_internal",
            "connectors_enabled": True,
            "connectors_encryption_keys": self.keys,
            "connectors_custom_url": True,
            "connectors_custom_url_users": f"{self.alice},{self.bob}",
            "connectors_call_timeout_seconds": 5.0,
            **overrides,
        }
        return Settings(**values)

    def service(self, **overrides) -> ConnectorService:
        engine = create_async_engine(to_asyncpg_url(self.url), poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return ConnectorService(session_factory=factory, settings=self.settings(**overrides))

    def sync_session(self):
        return sessionmaker(bind=create_engine(self.url, future=True), future=True)()


@contextlib.contextmanager
def connector_world(name: str) -> Iterator[World]:
    url = create_database(name)
    engine = create_engine(url, future=True)
    Base.metadata.drop_all(engine, tables=list(reversed(TABLES)))
    Base.metadata.create_all(engine, tables=TABLES)
    with sessionmaker(bind=engine, expire_on_commit=False, future=True)() as session:
        alice = User(email="alice@example.com", hashed_password="x")
        bob = User(email="bob@example.com", hashed_password="x")
        session.add_all([alice, bob])
        session.commit()
        ids = alice.id, bob.id
    server = FakeMCP().start()
    try:
        with netguard.allow_private_hosts_for_tests(Settings(deployment_profile="test")):
            yield World(url=url, alice=ids[0], bob=ids[1], keys=new_key(), server=server)
    finally:
        server.stop()
        engine.dispose()
        drop_database(name)


__all__ = ["World", "connector_world"]
