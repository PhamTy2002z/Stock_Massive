"""Async database configuration using SQLAlchemy 2.0."""
import asyncio
from contextlib import contextmanager
from typing import AsyncGenerator, Callable, Generator, TypeVar
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


_T = TypeVar("_T")


async def in_sync_session(work: Callable[[Session], _T]) -> _T:
    """The one way an async request reaches synchronous store code.

    Half this codebase is synchronous because the store is: the Universe, the
    Snapshot reads, the Trading Day resolution and the signal window all take a
    plain ``Session``. The request path above them is async. Every route that
    needs both has the same problem, so it is answered once here rather than
    invented again per route — three routes each solving it differently is three
    ways to block the event loop, and only one of them will be found.

    Two properties are the whole point:

    *It runs off the event loop.* Calling sync SQLAlchemy inside a coroutine
    blocks every other request in the process for the length of the query.
    ``asyncio.to_thread`` is what the tool layer already owes the sync
    ``SnapshotStore``, so the same mechanism serves both.

    *It opens its own session and closes it.* Never the request's async session
    — that one belongs to a different driver and a different loop — and never a
    session held across anything long. The async pool is fifteen connections; a
    session held for the length of a streaming Turn would cap concurrency at
    fifteen and make the sixteenth caller wait thirty seconds to fail.

    Read-only by construction: nothing is committed here. Writes belong to the
    async session the request already has — or, where the work being written is
    itself synchronous, to `in_sync_write` below.
    """

    def run() -> _T:
        with sync_session_factory() as session:
            return work(session)

    return await asyncio.to_thread(run)


async def in_sync_write(work: Callable[[Session], _T]) -> _T:
    """The same seam as `in_sync_session`, for work that has to commit.

    Separate rather than a flag on the one above, because the read version's
    promise is worth keeping absolute: a caller reading that signature must not
    have to check an argument to know whether the query it is passing could
    write.

    Deliberately not the request's async session either. That one belongs to a
    different driver, and the work reaching this seam is synchronous library
    code — the on-demand lane, the retry queue — whose transaction boundaries
    are its own business.

    The caller's own act comes first, always. A handler that seats a row and
    then reaches here must commit the row before it does, so a failure in this
    transaction leaves the user's request standing rather than rolling it back.
    """

    def run() -> _T:
        with get_sync_db() as session:
            return work(session)

    return await asyncio.to_thread(run)


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
