"""Async database configuration using SQLAlchemy 2.0."""
from contextlib import contextmanager
from typing import AsyncGenerator, Generator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.config import get_settings

settings = get_settings()

# asyncpg rejects `sslmode` in the URL and takes an `ssl` connect_arg instead.
# Any managed Postgres (Neon, RDS, ...) signals TLS the same way, so read the
# requirement off the URL rather than matching on a provider hostname.
_SSL_REQUIRED_MODES = {"require", "verify-ca", "verify-full"}


def to_asyncpg_url(url: str) -> str:
    """Rewrite a libpq URL for the asyncpg driver, dropping `sslmode`."""
    parts = urlsplit(url.replace("postgresql://", "postgresql+asyncpg://"))
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "sslmode"]
    return urlunsplit(parts._replace(query=urlencode(query)))


def asyncpg_connect_args(url: str) -> dict:
    """Return asyncpg connect_args carrying the URL's TLS requirement, if any."""
    sslmode = dict(parse_qsl(urlsplit(url).query)).get("sslmode", "").lower()
    return {"ssl": "require"} if sslmode in _SSL_REQUIRED_MODES else {}


DATABASE_URL = to_asyncpg_url(settings.database_url)
connect_args = asyncpg_connect_args(settings.database_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=30,
    pool_recycle=3600,
    connect_args=connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine for Alembic migrations and sync database operations.
# psycopg2 reads `sslmode` straight from the URL, so no connect_args needed.
sync_engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=30,
    pool_recycle=3600,
)

sync_session_factory = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
)


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """Context manager for sync database session (background jobs)."""
    session = sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_sync_session() -> Generator[Session, None, None]:
    """FastAPI dependency for a read-only synchronous session.

    The snapshot-first read paths are synchronous because the store is, and a
    handler declaring a plain `def` already runs in the threadpool. Nothing is
    committed here: the routes that use it only read.
    """
    session = sync_session_factory()
    try:
        yield session
    finally:
        session.close()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
