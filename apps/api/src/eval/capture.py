"""Freezing one ``trading_day`` of the real store into a seed.

The requirement is not "produce a fixture" — it is that *someone re-freezing
next quarter follows a documented procedure and gets a fixture with the same
guaranteed properties*. Two consequences shape this module.

**Symbols are selected by property, never named.** A hand-written list of
tickers is a list that stops being true: the symbol that was limit-locked in
August is liquid by November, and a re-freeze against the same list produces a
fixture that has quietly lost category E. So the store is scanned and the first
symbol satisfying each probe of ``roles.py`` is seated — the same probes that
verify the fixture at load, so a seat cannot be earned under one definition and
kept under another.

**The scan is deterministic.** Candidates are considered in sorted order, roles
are filled in a fixed order, and a symbol seated once is not considered again.
The same store at the same ``trading_day`` therefore yields the same seats, the
same rows and the same ``fixture_version`` — which is what makes capture
idempotent rather than merely repeatable.

The hard seats are filled first, and that ordering is load-bearing. A symbol
below ``min_sessions`` is rare and is very often also a bank; filling the bank
seat first would take the only candidate the data-gap category has.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.alpha.models import Analysis
from src.stocks.market_index import MARKET_INDEX_SYMBOL
from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import Capability
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.cross_sectional import RELATIVE_STRENGTH_MIN_SESSIONS
from src.stocks.trading_day import latest_trading_day, trading_days_before
from src.stocks.universe import Universe, build_universe

from .fixture import FixtureManifest, FixtureSeed
from .roles import (
    REQUIRED_ROLES,
    ROLE_PROBES,
    UNIVERSE_ROLES,
    FixtureRole,
    RoleContext,
)
from .tables import CAPTURED_TABLE_BY_NAME, CAPTURED_TABLES, encode_row
from .versions import running_versions

logger = logging.getLogger(__name__)

#: How far back a capture reaches, in trading sessions. The widest window any
#: registered field asks for, plus a margin — a fixture one session short of
#: ``relative_strength``'s floor would refuse it for the fixture's own reason
#: rather than for the symbol's, and category E would be measuring the capture.
CAPTURE_HISTORY_SESSIONS = RELATIVE_STRENGTH_MIN_SESSIONS + 25

#: How many healthy Universe members ride along beyond the seated roles.
#: Category B asks legitimate questions of healthy symbols across four
#: industries; the seats already cover those, and a handful of neighbours keeps
#: the cross-sectional fields from ranking a sample of seven.
CAPTURE_UNIVERSE_PADDING = 8

#: How many listed non-members the fixture keeps. The scope category expects a
#: refusal *plus up to three same-industry Universe suggestions*, so one
#: outsider is the seat and the rest are what the suggestion list is drawn from.
CAPTURE_OUTSIDER_PADDING = 3


class FixtureCaptureFailed(RuntimeError):
    """The store cannot produce a fixture with the guaranteed properties.

    Loud, and specific about which seat could not be filled. The alternative —
    a fixture missing its limit-locked symbol — is a battery that reports a
    category E score over cases that were never exercised.
    """


@dataclass(frozen=True)
class CapturePlan:
    """What the scan decided, before a single row is read."""

    trading_day: date
    window_start: date
    roles: dict[FixtureRole, str]
    universe_symbols: tuple[str, ...]
    outsiders: tuple[str, ...]

    @property
    def symbols(self) -> tuple[str, ...]:
        seen = dict.fromkeys(self.universe_symbols)
        seen.update(dict.fromkeys(self.outsiders))
        return tuple(seen)


def plan_capture(
    session: Session,
    *,
    trading_day: date | None = None,
    history_sessions: int = CAPTURE_HISTORY_SESSIONS,
    universe: Universe | None = None,
) -> CapturePlan:
    """Scan the store and seat every role, or refuse and say which one failed.

    ``universe`` defaults to the source store's own — the declared symbols plus
    the active cohort, resolved by the same reader the serving path uses. It is
    a parameter so that a capture can be planned against a stated Universe
    rather than against whatever the environment happened to declare, which is
    what makes the procedure reproducible from a written-down input.
    """
    day = trading_day or latest_trading_day(session)
    if day is None:
        raise FixtureCaptureFailed(
            "the store holds no market Snapshot, so there is no Trading Day to "
            "freeze a fixture at"
        )

    earlier = trading_days_before(session, day, history_sessions)
    window_start = earlier[-1] if earlier else day

    resolved_universe = universe if universe is not None else build_universe(session)
    members = tuple(sorted(resolved_universe.symbols))
    if not members:
        raise FixtureCaptureFailed(
            "the Universe is empty, so there is nothing for the battery to ask "
            "legitimate questions about"
        )
    outsiders = _listed_outside(session, members)
    context = RoleContext(trading_day=day, universe=frozenset(members))

    seated: dict[FixtureRole, str] = {}
    for role in REQUIRED_ROLES:
        pool = members if role in UNIVERSE_ROLES else outsiders
        probe = ROLE_PROBES[role]
        chosen = next(
            (
                symbol
                for symbol in pool
                if symbol not in seated.values() and probe.holds(session, symbol, context)
            ),
            None,
        )
        if chosen is None:
            raise FixtureCaptureFailed(
                f"no symbol in the store at {day} satisfies the {role.value} "
                f"seat ({probe.description}). The fixture's deliberate bad cases "
                "are not optional: capture at a different Trading Day, or widen "
                "the Universe, rather than freezing a fixture without them."
            )
        seated[role] = chosen

    seated_members = tuple(
        symbol for role, symbol in seated.items() if role in UNIVERSE_ROLES
    )
    padding = tuple(
        symbol for symbol in members if symbol not in seated_members
    )[:CAPTURE_UNIVERSE_PADDING]
    kept_outsiders = (seated[FixtureRole.OUTSIDE_UNIVERSE],) + tuple(
        symbol
        for symbol in outsiders
        if symbol != seated[FixtureRole.OUTSIDE_UNIVERSE]
    )[:CAPTURE_OUTSIDER_PADDING]

    return CapturePlan(
        trading_day=day,
        window_start=window_start,
        roles=seated,
        universe_symbols=tuple(sorted({*seated_members, *padding})),
        outsiders=kept_outsiders,
    )


def capture_fixture(
    session: Session,
    *,
    trading_day: date | None = None,
    history_sessions: int = CAPTURE_HISTORY_SESSIONS,
    universe: Universe | None = None,
    plan: CapturePlan | None = None,
) -> FixtureSeed:
    """Read the planned rows out of the real store and freeze them."""
    resolved = plan or plan_capture(
        session,
        trading_day=trading_day,
        history_sessions=history_sessions,
        universe=universe,
    )
    symbols = resolved.symbols

    tables = {
        ListingRoster.__tablename__: _roster_rows(session, symbols),
        ProviderSnapshot.__tablename__: _snapshot_rows(session, resolved),
        CorporateAction.__tablename__: _action_rows(session, resolved),
        Analysis.__tablename__: _analysis_rows(session, resolved),
    }
    for table in CAPTURED_TABLES:
        tables.setdefault(table.name, ())

    manifest = FixtureManifest(
        trading_day=resolved.trading_day,
        versions=running_versions(),
        universe_symbols=resolved.universe_symbols,
        roles=resolved.roles,
        # Everything in the Universe. The watchlist tool has to answer something
        # for the battery to be able to ask it anything, and a fixture whose
        # watchlist is a subset would make ``get_watchlist`` a second, quieter
        # Universe.
        watchlist=resolved.universe_symbols,
        history_sessions=history_sessions,
    )
    seed = FixtureSeed(manifest=manifest, tables=tables)
    logger.info(
        "Captured Eval Fixture %s at %s: %d symbols, %d snapshot rows",
        seed.fixture_version,
        resolved.trading_day,
        len(symbols),
        len(tables[ProviderSnapshot.__tablename__]),
    )
    return seed


def _listed_outside(session: Session, members: Sequence[str]) -> tuple[str, ...]:
    rows = session.execute(
        select(ListingRoster.symbol)
        .where(
            ListingRoster.is_listed.is_(True),
            ListingRoster.symbol.not_in(list(members)),
        )
        .order_by(ListingRoster.symbol)
    ).scalars()
    return tuple(rows)


def _sorted_rows(table_name: str, rows) -> tuple[dict, ...]:
    table = CAPTURED_TABLE_BY_NAME[table_name]
    encoded = [encode_row(table, row) for row in rows]
    # Sorted by their own canonical encoding, so two captures of the same store
    # produce byte-identical files whatever order the database returned. By the
    # whole row rather than by a key: the surrogate id is not captured, so there
    # is no other column set guaranteed to be unique.
    return tuple(
        sorted(
            encoded,
            key=lambda payload: json.dumps(
                payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            ),
        )
    )


def _roster_rows(session: Session, symbols: Sequence[str]) -> tuple[dict, ...]:
    rows = session.execute(
        select(ListingRoster).where(ListingRoster.symbol.in_(list(symbols)))
    ).scalars()
    return _sorted_rows(ListingRoster.__tablename__, rows)


def _snapshot_rows(session: Session, plan: CapturePlan) -> tuple[dict, ...]:
    """Every Snapshot for the fixture's symbols inside the window, plus the index.

    The benchmark travels with them and is not optional: ``relative_strength``
    and ``drawdown_versus_benchmark`` regress against it, and a fixture holding
    equities alone would refuse both for a reason that is about the fixture.
    """
    wanted = [*plan.symbols, MARKET_INDEX_SYMBOL]
    rows = session.execute(
        select(ProviderSnapshot).where(
            ProviderSnapshot.symbol.in_(wanted),
            ProviderSnapshot.effective_at >= _day_start(plan.window_start),
            ProviderSnapshot.effective_at < _day_start(plan.trading_day + timedelta(days=1)),
        )
    ).scalars()
    kept = [
        row
        for row in rows
        if row.symbol != MARKET_INDEX_SYMBOL
        or row.capability == Capability.MARKET_INDEX.value
    ]
    return _sorted_rows(ProviderSnapshot.__tablename__, kept)


def _action_rows(session: Session, plan: CapturePlan) -> tuple[dict, ...]:
    rows = session.execute(
        select(CorporateAction).where(CorporateAction.symbol.in_(list(plan.symbols)))
    ).scalars()
    return _sorted_rows(CorporateAction.__tablename__, rows)


def _analysis_rows(session: Session, plan: CapturePlan) -> tuple[dict, ...]:
    rows = session.execute(
        select(Analysis).where(
            Analysis.symbol.in_(list(plan.symbols)),
            Analysis.trading_day <= plan.trading_day,
            Analysis.trading_day >= plan.window_start,
        )
    ).scalars()
    return _sorted_rows(Analysis.__tablename__, rows)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


__all__ = [
    "CAPTURE_HISTORY_SESSIONS",
    "CAPTURE_OUTSIDER_PADDING",
    "CAPTURE_UNIVERSE_PADDING",
    "CapturePlan",
    "FixtureCaptureFailed",
    "capture_fixture",
    "plan_capture",
]
