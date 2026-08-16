"""The dedicated eval database, and the one door into it.

``docs/adr/0016`` puts the fixture in *a dedicated eval database*, and the
acceptance criterion is stronger than that: **running the battery cannot write
to dev or production.** Nothing here consults ``src.core.database``'s engine, and
:func:`eval_engine` refuses outright when ``EVAL_DATABASE_URL`` resolves to the
same database the application serves from. A guard that only checked the string
would be satisfied by the same database spelled with a different driver.

Everything the battery writes lands here, the ledger included. That is the
reading this module commits to, and it is worth stating why: ``llm_call_usage``
and ``eval_run`` are the *same mechanism* as every other provider call
(``docs/adr/0014``'s atomic reservation) pointed at a different database, not a
different mechanism. Pointing them at the production ledger instead would satisfy
one sentence of ADR-0014 by breaking the criterion above, and the ceiling that
actually matters — $2.5 per gate run — is per-run and holds either way.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

# Imported for their side effect on ``Base.metadata``: the eval database is
# created from the models, so a model this module does not reach is a table the
# battery would discover missing halfway through a run.
from src.alpha import models as _alpha_models  # noqa: F401
from src.alpha.models import WatchlistEntry
from src.auth.models import User
from src.core.config import Settings, get_settings
from src.core.database import Base
from src.stocks import models as _stocks_models  # noqa: F401

from .fixture import FixtureSeed
from .roles import FixtureRole, RoleContext, verify_roles
from .tables import CAPTURED_TABLES, decode_row

logger = logging.getLogger(__name__)

#: The account every Eval Case is asked as. Deterministic, seated by the loader,
#: and never captured — see ``tables.py`` for why a real watchlist is not
#: fixture material.
EVAL_USER_EMAIL = "eval-fixture@stockmassive.invalid"


class EvalDatabaseMisconfigured(RuntimeError):
    """The battery has nowhere safe to run, so it does not run."""


def _identity(url: str) -> tuple[str, str, str]:
    """Host, port and database name, with driver and credentials discarded.

    Those three are what decide whether two URLs are the same database.
    ``postgresql+psycopg2://`` and ``postgresql://`` differ as strings and not as
    destinations, and a comparison that missed that would let the battery write
    to production through a spelling.
    """
    parts = urlsplit(url)
    return (
        (parts.hostname or "").lower(),
        str(parts.port or ""),
        parts.path.rstrip("/").lower(),
    )


def resolve_eval_database_url(settings: Settings | None = None) -> str:
    """The eval database's URL, or a refusal that says what to set."""
    settings = settings or get_settings()
    url = (settings.eval_database_url or "").strip()
    if not url:
        raise EvalDatabaseMisconfigured(
            "EVAL_DATABASE_URL is not set. The Eval Battery runs against a "
            "dedicated database so that it cannot write to dev or production."
        )
    if _identity(url) == _identity(settings.database_url):
        raise EvalDatabaseMisconfigured(
            "EVAL_DATABASE_URL points at the same database as DATABASE_URL. "
            "The battery would write its fixture over the store the API serves."
        )
    return url


def eval_engine(settings: Settings | None = None, *, url: str | None = None) -> Engine:
    """An engine for the eval database and for nothing else."""
    resolved = url or resolve_eval_database_url(settings)
    return create_engine(resolved, pool_pre_ping=True, future=True)


def eval_session_factory(engine: Engine) -> Callable[[], Session]:
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def create_schema(engine: Engine) -> None:
    """Every table the battery touches, in a database that may be empty.

    ``create_all`` rather than Alembic, deliberately. The eval database is
    disposable and is rebuilt from a seed on demand, so the migration chain buys
    nothing here — and the fixture already pins the shape it was captured
    against through ``schema_version``, which is the check that would actually
    catch a drift.
    """
    Base.metadata.create_all(engine, checkfirst=True)


@dataclass(frozen=True)
class LoadedFixture:
    """A loaded fixture, and the handles a run needs to ask anything of it."""

    seed: FixtureSeed
    user_id: int

    @property
    def fixture_version(self) -> str:
        return self.seed.fixture_version

    @property
    def trading_day(self) -> date:
        return self.seed.manifest.trading_day

    @property
    def universe(self) -> frozenset[str]:
        return frozenset(self.seed.manifest.universe_symbols)

    @property
    def roles(self) -> Mapping[FixtureRole, str]:
        return self.seed.manifest.roles

    def symbol_for(self, role: FixtureRole) -> str:
        return self.seed.manifest.roles[role]


def load_fixture(
    seed: FixtureSeed,
    session_factory: Callable[[], Session],
    *,
    verify: bool = True,
) -> LoadedFixture:
    """Replace the eval database's fixture state with this seed.

    Idempotent by construction: every captured table is emptied of the fixture's
    symbols and refilled, and the eval user's watchlist is rewritten whole.
    Loading twice yields the same state, which is the acceptance criterion — and
    it is a *replace* rather than an upsert because a fixture is a photograph:
    merging two of them produces a store that never existed.
    """
    seed.manifest.versions.assert_matches()

    session = session_factory()
    try:
        with session.begin():
            for table in CAPTURED_TABLES:
                session.execute(delete(table.model))
            user_id = _seat_user(session)
            session.execute(
                delete(WatchlistEntry).where(WatchlistEntry.user_id == user_id)
            )
            for table in CAPTURED_TABLES:
                rows = seed.rows(table.name)
                if not rows:
                    continue
                session.add_all([decode_row(table, payload) for payload in rows])
            session.flush()
            _seat_watchlist(session, user_id, seed.manifest.watchlist)
    finally:
        session.close()

    loaded = LoadedFixture(seed=seed, user_id=user_id)
    if verify:
        session = session_factory()
        try:
            verify_roles(
                session,
                seed.manifest.roles,
                RoleContext(
                    trading_day=seed.manifest.trading_day,
                    universe=loaded.universe,
                ),
            )
        finally:
            session.close()
    logger.info(
        "Loaded Eval Fixture %s at %s (%d symbols)",
        loaded.fixture_version,
        seed.manifest.trading_day,
        len(seed.manifest.symbols),
    )
    return loaded


def _seat_user(session: Session) -> int:
    user = session.scalar(select(User).where(User.email == EVAL_USER_EMAIL))
    if user is None:
        user = User(
            email=EVAL_USER_EMAIL,
            hashed_password="!eval-fixture-no-login",
            full_name="Eval Fixture",
            is_active=True,
            is_admin=False,
        )
        session.add(user)
        session.flush()
    return int(user.id)


def _seat_watchlist(session: Session, user_id: int, symbols: tuple[str, ...]) -> None:
    # A fixed timestamp rather than ``now()``: the watchlist read is ordered by
    # ``added_at``, and a clock would make two loads of the same seed serve the
    # same symbols in a different order.
    added_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    session.add_all(
        [
            WatchlistEntry(user_id=user_id, symbol=symbol, added_at=added_at)
            for symbol in symbols
        ]
    )


__all__ = [
    "EVAL_USER_EMAIL",
    "EvalDatabaseMisconfigured",
    "LoadedFixture",
    "create_schema",
    "eval_engine",
    "eval_session_factory",
    "load_fixture",
    "resolve_eval_database_url",
]
