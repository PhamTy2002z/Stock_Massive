"""The properties an Eval Fixture must contain **by construction**.

``docs/adr/0016`` names three deliberate bad cases and four industry seats, and
the word that matters is *deliberate*: a fixture that happens to contain a short
history because the capture picked a recent listing has the property today and
loses it at the next re-freeze, silently, taking category E with it.

So each property is a **probe** rather than a note, and the same probe runs
twice. It **selects** the symbol during capture — the store is scanned and the
first symbol that satisfies it is seated in that role — and it **verifies** the
loaded fixture before any battery runs. One function, so the fixture cannot pass
selection under one definition and verification under another.

Every probe is answered by the real code. ``insufficient_history``,
``mixed_price_basis`` and the limit-lock share are ``prepare_bars()``'s verdicts,
not re-derived here; the industry seats are ``industry_for_icb`` over the stored
ICB level-2 code. A probe that re-implemented any of them would be asserting
that the fixture satisfies a second opinion.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.alpha.field_profile import AnalysisIndustry, industry_for_icb
from src.stocks.models import ListingRoster
from src.stocks.signals import PRICE_ZONE_MIN_SESSIONS, prepare_bars
from src.stocks.signals.fields import DEGRADED_LIMIT_LOCK_SHARE
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.risk import PRICE_ZONE_SESSIONS

# The window every price probe is asked over. The price-zone field's own, and
# named rather than invented: it is the field the nightly artifact is built
# around and a refused one fails the run (spec 0003 §8.4), so "below
# ``min_sessions``" means something a reader can point at rather than a
# threshold this module chose.
PROBE_WINDOW_SESSIONS = PRICE_ZONE_SESSIONS + 1
PROBE_MIN_SESSIONS = PRICE_ZONE_MIN_SESSIONS

# Wide enough to cross the seam ``docs/adr/0006`` settles. A symbol's raw era
# starts when this system began collecting it; a window that only covers the
# collected era is uniform by construction and would report every symbol as
# clean, which is the probe answering a question nobody asked.
SEAM_PROBE_SESSIONS = 250


class FixtureRole(str, Enum):
    """One seat in the fixture, and what the battery needs it for."""

    # --- the three deliberate bad cases ---------------------------------
    BELOW_MIN_SESSIONS = "below_min_sessions"
    PRICE_BASIS_SEAM = "price_basis_seam"
    LIMIT_LOCK_DENSE = "limit_lock_dense"

    # --- the four industry seats categories B and D run across ----------
    BANK = "bank"
    REAL_ESTATE = "real_estate"
    RETAIL = "retail"
    ORDINARY = "ordinary"

    # --- the one seat the scope category needs --------------------------
    # Listed, and outside the Universe. Category C asks for the refusal plus
    # same-industry Universe suggestions, and neither half of that is provable
    # against a symbol the market does not list.
    OUTSIDE_UNIVERSE = "outside_universe"


#: The roles a fixture is refused without. ``OUTSIDE_UNIVERSE`` is included:
#: without it the scope category has nothing to ask about.
REQUIRED_ROLES: tuple[FixtureRole, ...] = tuple(FixtureRole)

#: The roles whose symbols belong to the Universe. ``OUTSIDE_UNIVERSE`` is the
#: one that must not, and saying so here keeps the two facts from drifting.
UNIVERSE_ROLES: tuple[FixtureRole, ...] = tuple(
    role for role in FixtureRole if role is not FixtureRole.OUTSIDE_UNIVERSE
)


@dataclass(frozen=True)
class RoleContext:
    """What a probe may read besides the store: the pinned Universe."""

    trading_day: date
    universe: frozenset[str]


ProbeFn = Callable[[Session, str, RoleContext], bool]


def _below_min_sessions(session: Session, symbol: str, context: RoleContext) -> bool:
    _, health = prepare_bars(
        session,
        symbol,
        PROBE_WINDOW_SESSIONS,
        min_sessions=PROBE_MIN_SESSIONS,
        end=context.trading_day,
        peers=(symbol,),
    )
    return health.refusal is SignalIssue.INSUFFICIENT_HISTORY


def _price_basis_seam(session: Session, symbol: str, context: RoleContext) -> bool:
    _, health = prepare_bars(
        session,
        symbol,
        SEAM_PROBE_SESSIONS,
        min_sessions=1,
        end=context.trading_day,
        peers=(symbol,),
    )
    return health.refusal is SignalIssue.MIXED_PRICE_BASIS


def _limit_lock_dense(session: Session, symbol: str, context: RoleContext) -> bool:
    """Locked often enough that the window is degraded rather than merely odd.

    The share is the registry's own (``DEGRADED_LIMIT_LOCK_SHARE``), so this
    seat is exactly the condition that makes a real field report ``degraded``
    with a reason — which is what category E asks the model to expose.
    """
    _, health = prepare_bars(
        session,
        symbol,
        PROBE_WINDOW_SESSIONS,
        min_sessions=PROBE_MIN_SESSIONS,
        end=context.trading_day,
        peers=(symbol,),
    )
    if health.refusal is not None or health.sessions_used <= 0:
        return False
    return health.limit_lock_days / health.sessions_used >= DEGRADED_LIMIT_LOCK_SHARE


def _industry(wanted: AnalysisIndustry) -> ProbeFn:
    def probe(session: Session, symbol: str, context: RoleContext) -> bool:
        code = session.scalar(
            select(ListingRoster.icb_code).where(ListingRoster.symbol == symbol)
        )
        return industry_for_icb(code) is wanted

    return probe


def _outside_universe(session: Session, symbol: str, context: RoleContext) -> bool:
    listed = session.scalar(
        select(ListingRoster.is_listed).where(ListingRoster.symbol == symbol)
    )
    return bool(listed) and symbol not in context.universe


@dataclass(frozen=True)
class RoleProbe:
    """One seat, the sentence that describes it, and the test that decides it."""

    role: FixtureRole
    description: str
    holds: ProbeFn


ROLE_PROBES: Mapping[FixtureRole, RoleProbe] = {
    probe.role: probe
    for probe in (
        RoleProbe(
            role=FixtureRole.BELOW_MIN_SESSIONS,
            description=(
                "prepare_bars() refuses insufficient_history at the price-zone "
                "field's own floor"
            ),
            holds=_below_min_sessions,
        ),
        RoleProbe(
            role=FixtureRole.PRICE_BASIS_SEAM,
            description=(
                "prepare_bars() refuses mixed_price_basis over a 250-session "
                "window, so the window crosses the ADR-0006 seam"
            ),
            holds=_price_basis_seam,
        ),
        RoleProbe(
            role=FixtureRole.LIMIT_LOCK_DENSE,
            description=(
                "at least a fifth of the served window is limit-locked, which is "
                "the registry's own degradation share"
            ),
            holds=_limit_lock_dense,
        ),
        RoleProbe(
            role=FixtureRole.BANK,
            description="the stored ICB level-2 code selects the banks profile",
            holds=_industry(AnalysisIndustry.BANKS),
        ),
        RoleProbe(
            role=FixtureRole.REAL_ESTATE,
            description="the stored ICB level-2 code selects the real-estate profile",
            holds=_industry(AnalysisIndustry.REAL_ESTATE),
        ),
        RoleProbe(
            role=FixtureRole.RETAIL,
            description="the stored ICB level-2 code selects the retail profile",
            holds=_industry(AnalysisIndustry.RETAIL),
        ),
        RoleProbe(
            role=FixtureRole.ORDINARY,
            # ``OTHER`` and not ``UNCLASSIFIED``: the fourth seat exists because
            # emphasis differs by industry, and an unclassified symbol tests the
            # store's ignorance rather than the ordinary case.
            description=(
                "the store has classified it, and into none of the three "
                "industries the Field Profile has metrics for"
            ),
            holds=_industry(AnalysisIndustry.OTHER),
        ),
        RoleProbe(
            role=FixtureRole.OUTSIDE_UNIVERSE,
            description="listed by an exchange and outside the pinned Universe",
            holds=_outside_universe,
        ),
    )
}


class FixturePropertyFailure(AssertionError):
    """A fixture that does not hold what it claims to hold.

    An ``AssertionError`` because that is what it is — the fixture's own promise
    about itself, checked. Raised at load time and again from the test suite, so
    a re-freeze that quietly lost the limit-locked symbol cannot reach a gate run.
    """

    def __init__(self, failures: tuple[str, ...]) -> None:
        self.failures = failures
        super().__init__(
            "the Eval Fixture no longer holds the properties it was captured "
            "for: " + "; ".join(failures)
        )


def verify_roles(
    session: Session,
    assignments: Mapping[FixtureRole, str],
    context: RoleContext,
) -> None:
    """Refuse a fixture whose seats no longer hold their own properties."""
    failures: list[str] = []
    for role in REQUIRED_ROLES:
        symbol = assignments.get(role)
        if not symbol:
            failures.append(f"{role.value}: no symbol is seated")
            continue
        probe = ROLE_PROBES[role]
        if not probe.holds(session, symbol, context):
            failures.append(f"{role.value}: {symbol} no longer {probe.description}")
    if failures:
        raise FixturePropertyFailure(tuple(failures))


__all__ = [
    "PROBE_MIN_SESSIONS",
    "PROBE_WINDOW_SESSIONS",
    "REQUIRED_ROLES",
    "ROLE_PROBES",
    "SEAM_PROBE_SESSIONS",
    "UNIVERSE_ROLES",
    "FixturePropertyFailure",
    "FixtureRole",
    "RoleContext",
    "RoleProbe",
    "verify_roles",
]
