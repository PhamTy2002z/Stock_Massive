"""A throwaway Postgres beside the dev store, so no test counts another's rows.

A count is the one thing a shared test database cannot give: another module's
leftover row would move every rate and nobody would know which test was wrong.
Nor can SQLite stand in — ``analysis.payload`` is ``JSONB``. So a suite that
needs exact counts creates its own database next to whatever ``DATABASE_URL``
points at, and drops it afterwards.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

from src.core.config import get_settings

def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{name}"))


def database_url(name: str) -> str:
    return _with_database(get_settings().database_url, name)


def _admin_engine():
    # ``postgres`` is the maintenance database every server has; CREATE DATABASE
    # cannot run inside a transaction, hence AUTOCOMMIT.
    return create_engine(
        database_url("postgres"), isolation_level="AUTOCOMMIT", future=True
    )


def create_database(name: str) -> str:
    """Make the database if it is not there, and hand back its URL."""
    with _admin_engine().connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    return database_url(name)


def drop_database(name: str) -> None:
    with _admin_engine().connect() as connection:
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": name},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))


__all__ = ["create_database", "database_url", "drop_database"]
