"""Two throwaway Postgres databases, so no eval test touches the dev store.

The Eval Fixture is defined by a separation — a capture reads one database and
the battery runs against another, and ``src/eval/store.py`` refuses when the two
are the same. Testing that with SQLite is not possible (``analysis.payload`` is
``JSONB``) and testing it against the dev database would be testing the one
arrangement the code exists to forbid. So the suite creates its own pair beside
whatever ``DATABASE_URL`` points at, and drops them afterwards.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

from src.core.config import get_settings

SOURCE_DB = "stockmassive_eval_source_test"
TARGET_DB = "stockmassive_eval_target_test"


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


__all__ = ["SOURCE_DB", "TARGET_DB", "create_database", "database_url", "drop_database"]
