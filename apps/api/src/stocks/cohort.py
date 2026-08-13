"""The Profit Leaders Cohort, held as versions rather than as a current list.

ADR-0003 reserves fifty of the Universe's hundred places for the fifty most
profitable listed companies. The hard part is not choosing them — the census does
that — it is changing them without breaking anything that was already said.

Three properties fall out of that, and they are why this is not a table of fifty
rows being updated:

*A signal keeps its cohort.* A Volume Spike served on a Tuesday was computed
against the fifty companies that were the cohort on Tuesday. Asked again next
month, it has to resolve to the same fifty, so a ranking change writes a new
version and supersedes the old one instead of editing it. Resolution is by
activation window, never "today's members projected backwards".

*A new member cannot produce a signal on its first day.* A twenty-day baseline
needs twenty-one sessions of stored history, and a company that just entered the
ranking has none. So a new ranking is staged as a ``candidate``, its members are
warmed up, and it takes over only when enough of them can actually be evaluated.

*A bad week must not cost the last good answer.* A failed census, a failed
Warm-up or a failed collection cycle leaves the active version exactly where it
was. Nothing here can deactivate a version except another version taking over,
and that swap happens in one transaction.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.stocks.models import CohortMember, CohortVersion, ProviderSnapshot

from .census import (
    COHORT_SIZE,
    RANKABLE_PERIOD_COVERAGE,
    RankedCompany,
    eligible_symbols,
    newest_rankable_period,
    rank_profit_leaders,
)
from .providers import Capability, SnapshotStore
from .providers.normalize import VN_TZ
from .trading_day import latest_trading_day, trading_days_before
from .universe import UNIVERSE_MAX_SYMBOLS, forget_cohort_cache

logger = logging.getLogger(__name__)

# How many candidate members have to be evaluable before a version may take over.
# Below fifty on purpose: holding out for all fifty would let one company with a
# provider problem keep a whole quarter's ranking off the air.
COHORT_ACTIVATION_MIN_MEMBERS = 45

# Twenty preceding sessions plus the target one. This is the definition of
# evaluable for a Volume Spike, and it is market-wide: the twenty-one days are
# the same twenty-one for every symbol (see ``trading_day``).
BASELINE_TRADING_DAYS = 21

_MARKET = Capability.MARKET.value

CohortState = Literal["candidate", "active", "superseded"]


@dataclass(frozen=True)
class CohortRefresh:
    """What one attempt to move the cohort forward did.

    Every field can be empty on a healthy run. A quarter where the ranking has
    not changed stages nothing, and a candidate whose members are still warming
    up activates nothing — neither is a failure, and the record has to be able to
    say "nothing to do" without looking like "nothing worked".
    """

    reporting_period: date | None = None
    staged_version_id: int | None = None
    activated_version_id: int | None = None
    superseded_version_id: int | None = None
    warmed: tuple[str, ...] = ()
    evaluable_members: int = 0
    reason: str | None = None

    def as_result(self) -> dict:
        return {
            "reporting_period": (
                self.reporting_period.isoformat() if self.reporting_period else None
            ),
            "staged_version_id": self.staged_version_id,
            "activated_version_id": self.activated_version_id,
            "superseded_version_id": self.superseded_version_id,
            "warmed": list(self.warmed),
            "evaluable_members": self.evaluable_members,
            "reason": self.reason,
        }


def _day_start(day: date) -> datetime:
    """Midnight in Vietnam, which is how a session is stamped."""
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


class CohortStore:
    """Read and advance the stored Cohort Versions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def active(self) -> CohortVersion | None:
        return self.session.execute(
            select(CohortVersion).where(CohortVersion.state == "active")
        ).scalar_one_or_none()

    def newest_candidate(self) -> CohortVersion | None:
        """The candidate waiting to take over, if there is one.

        Newest wins when several exist: an earlier candidate that never reached
        the activation floor has been overtaken by a fresher ranking, and
        promoting it would seat a cohort the census no longer believes in.
        """
        return self.session.execute(
            select(CohortVersion)
            .where(CohortVersion.state == "candidate")
            .order_by(CohortVersion.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def members(self, version_id: int) -> tuple[CohortMember, ...]:
        rows = self.session.execute(
            select(CohortMember)
            .where(CohortMember.cohort_version_id == version_id)
            .order_by(CohortMember.rank.asc())
        ).scalars()
        return tuple(rows)

    def symbols(self, version_id: int) -> tuple[str, ...]:
        """This version's members in rank order."""
        rows = self.session.execute(
            select(CohortMember.symbol)
            .where(CohortMember.cohort_version_id == version_id)
            .order_by(CohortMember.rank.asc())
        ).scalars()
        return tuple(rows)

    def stage(
        self,
        ranking: Sequence[RankedCompany],
        reporting_period: date,
        census_run_id: int,
        now: datetime,
    ) -> CohortVersion:
        """Write a new candidate version and its members.

        The members are written once, here, and never touched again. A
        restatement or a delisting produces another version — which is what makes
        "the cohort as it was in August" a question with an answer.
        """
        version = CohortVersion(
            reporting_period=reporting_period,
            census_run_id=census_run_id,
            state="candidate",
            created_at=now,
        )
        self.session.add(version)
        self.session.flush()

        for company in ranking:
            self.session.add(
                CohortMember(
                    cohort_version_id=version.id,
                    symbol=company.symbol,
                    rank=company.rank,
                    # Stored as a decimal because it is money: a net income in the
                    # tens of trillions of dong exceeds what a float carries
                    # exactly, and a ranking that reorders itself on rounding is
                    # not reproducible.
                    net_income_vnd=Decimal(str(company.net_income_vnd)),
                    exchange=company.exchange.value,
                )
            )
        self.session.flush()

        logger.info(
            "Staged cohort version %d for %s with %d members",
            version.id,
            reporting_period,
            len(ranking),
        )
        return version

    def activate(
        self,
        candidate: CohortVersion,
        now: datetime,
        evaluable_members: int,
    ) -> CohortVersion | None:
        """Promote a candidate and retire the version it replaces, atomically.

        One transaction covers both halves. Half of this applied is a state the
        rest of the system has no reading for: two active versions serve two
        different cohorts, and none serves nothing at all.

        The superseded row is stamped before the candidate is promoted rather than
        after, because the database enforces "at most one active" with a partial
        unique index — promoting first would collide with the version still
        holding the seat.
        """
        previous = self.active()
        with self.session.begin_nested():
            if previous is not None:
                previous.state = "superseded"
                previous.superseded_at = now
                self.session.flush()

            candidate.state = "active"
            candidate.activated_at = now
            candidate.coverage_at_activation = evaluable_members
            self.session.flush()

        # The Universe memoizes cohort membership per version id, and this is the
        # moment that id changes. Dropped here rather than left to the caller
        # because a promotion nobody told the Universe about is a promotion the
        # collector goes on ignoring.
        forget_cohort_cache()

        logger.info(
            "Cohort version %d active with %d evaluable members (replacing %s)",
            candidate.id,
            evaluable_members,
            previous.id if previous else "nothing",
        )
        return previous


def evaluable_symbols(
    session: Session,
    symbols: Sequence[str],
    day: date | None = None,
    baseline_days: int = BASELINE_TRADING_DAYS,
) -> tuple[str, ...]:
    """Which of these symbols has a full baseline stored at the newest session.

    Market-wide by construction: the twenty-one Trading Days are resolved once,
    across the whole store, and a symbol has to hold a market Snapshot on every
    one of them. Resolved per symbol instead, a symbol with gaps would reach
    further back, average a different stretch of market, and be presented as
    comparable with the symbol beside it.

    An empty answer when the store holds fewer than ``baseline_days`` sessions is
    the honest one: nothing is evaluable against a baseline that does not exist
    yet, and padding it with calendar days would invent sessions.
    """
    if not symbols:
        return ()

    target = day or latest_trading_day(session)
    if target is None:
        return ()

    window = (target,) + trading_days_before(session, target, baseline_days - 1)
    if len(window) < baseline_days:
        return ()

    stamps = [_day_start(item) for item in window]
    wanted = [symbol.upper() for symbol in symbols]
    rows = session.execute(
        select(
            ProviderSnapshot.symbol,
            func.count(func.distinct(ProviderSnapshot.effective_at)),
        )
        .where(
            ProviderSnapshot.capability == _MARKET,
            ProviderSnapshot.symbol.in_(wanted),
            ProviderSnapshot.effective_at.in_(stamps),
        )
        .group_by(ProviderSnapshot.symbol)
    ).all()

    covered = {str(symbol) for symbol, sessions in rows if sessions >= baseline_days}
    return tuple(symbol for symbol in wanted if symbol in covered)


def cohort_version_active_on(session: Session, day: date) -> CohortVersion | None:
    """The version that was active on this day, not the newest one.

    This is the query a historical signal resolves through. A cohort membership
    read as "the fifty companies that are the cohort now" would silently
    re-explain August's signal with October's companies, and the two answers
    would both look right.

    The window is inclusive of the whole day: a version activated at 11:00 counts
    for that day, and one superseded at 11:00 does not.
    """
    end_of_day = _day_start(day + timedelta(days=1))
    return session.execute(
        select(CohortVersion)
        .where(
            CohortVersion.activated_at.is_not(None),
            CohortVersion.activated_at < end_of_day,
            (CohortVersion.superseded_at.is_(None))
            | (CohortVersion.superseded_at >= end_of_day),
        )
        .order_by(CohortVersion.activated_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def active_cohort_symbols(session: Session) -> tuple[str, ...]:
    """The members of the active version, in rank order, or nothing."""
    store = CohortStore(session)
    version = store.active()
    return () if version is None else store.symbols(version.id)


def cohort_symbols_on(session: Session, day: date) -> tuple[str, ...]:
    """The members of whichever version was active on this day."""
    version = cohort_version_active_on(session, day)
    return () if version is None else CohortStore(session).symbols(version.id)


def refresh_cohort(
    session: Session,
    census_run_id: int,
    warm: Callable[[Sequence[str]], Any] | None = None,
    cohort_size: int = COHORT_SIZE,
    min_members: int = COHORT_ACTIVATION_MIN_MEMBERS,
    coverage_threshold: float = RANKABLE_PERIOD_COVERAGE,
    universe_cap: int = UNIVERSE_MAX_SYMBOLS,
    explicit_symbols: Sequence[str] = (),
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> CohortRefresh:
    """Move the cohort forward by one step, or explain why it did not.

    One path serves both reasons a cohort changes. A newer period becoming
    rankable is the obvious one. A delisting is the other, and it needs no special
    case: a ranking recomputed at the *active* version's own period drops the
    company that left the exchange and pulls in the next one down, which is
    exactly what ADR-0003 asks for.

    Nothing here can retire the active version on its own. If the ranking cannot
    be computed, or the candidate cannot be made evaluable, the previous version
    keeps serving — a stale cohort still answers honestly, and no cohort answers
    nothing at all.
    """
    stamped = now()
    store = CohortStore(session)
    active = store.active()
    eligible = eligible_symbols(session)

    period = _period_to_rank(session, active, eligible, coverage_threshold)
    if period is None:
        return CohortRefresh(reason="no rankable reporting period yet")

    ranking = rank_profit_leaders(session, period, size=cohort_size)
    if len(ranking) < cohort_size:
        # Fewer than fifty companies with a positive profit at a rankable period
        # is a market this system does not understand well enough to reseat the
        # cohort from. The previous version stays exactly as it is.
        return CohortRefresh(
            reporting_period=period,
            reason=(
                f"only {len(ranking)} eligible companies at {period}, "
                f"{cohort_size} required"
            ),
        )

    candidate = store.newest_candidate()
    staged = _stage_if_changed(
        store,
        ranking=ranking,
        period=period,
        census_run_id=census_run_id,
        active=active,
        candidate=candidate,
        now=stamped,
    )
    pending = staged or candidate
    if pending is None:
        return CohortRefresh(
            reporting_period=period,
            reason="the active cohort already matches this ranking",
        )

    refused = _universe_overflow(
        explicit_symbols, store.symbols(pending.id), universe_cap
    )
    if refused:
        # ADR-0003 gives the explicit half of the Universe priority: an operator's
        # declared symbols are a commitment, and a cohort is a derived list. So the
        # activation is refused rather than the configuration trimmed — and it is
        # refused here, before a Warm-up spends the allowance on symbols that
        # cannot be seated.
        logger.error(
            "Refusing to activate cohort version %d: it would put the Universe "
            "at %d symbols, over the cap of %d",
            pending.id,
            refused,
            universe_cap,
        )
        return CohortRefresh(
            reporting_period=period,
            staged_version_id=staged.id if staged else None,
            reason=(
                f"activation refused: the Universe would hold {refused} "
                f"symbols, over the cap of {universe_cap}"
            ),
        )

    members = store.symbols(pending.id)
    warmed = _warm_up(session, members, warm)
    evaluable = evaluable_symbols(session, members)

    if len(evaluable) < min_members:
        logger.info(
            "Cohort version %d stays a candidate: %d of %d members evaluable, "
            "%d required",
            pending.id,
            len(evaluable),
            len(members),
            min_members,
        )
        return CohortRefresh(
            reporting_period=period,
            staged_version_id=staged.id if staged else None,
            warmed=warmed,
            evaluable_members=len(evaluable),
            reason=(
                f"{len(evaluable)} of {len(members)} members evaluable, "
                f"{min_members} required"
            ),
        )

    previous = store.activate(pending, stamped, len(evaluable))
    return CohortRefresh(
        reporting_period=period,
        staged_version_id=staged.id if staged else None,
        activated_version_id=pending.id,
        superseded_version_id=previous.id if previous else None,
        warmed=warmed,
        evaluable_members=len(evaluable),
    )


def _period_to_rank(
    session: Session,
    active: CohortVersion | None,
    eligible: Sequence[str],
    coverage_threshold: float,
) -> date | None:
    """Which reporting period this refresh should rank at.

    The newest rankable period when there is one. When there is not — a market
    that has not yet reported the current quarter widely enough — the active
    version's own period, so a delisting among its members can still be answered.
    Never a period the market has not reported: that would crown whoever filed
    first.
    """
    coverage = newest_rankable_period(session, eligible, coverage_threshold)
    if coverage is not None:
        return coverage.period
    return active.reporting_period if active is not None else None


def _stage_if_changed(
    store: CohortStore,
    ranking: Sequence[RankedCompany],
    period: date,
    census_run_id: int,
    active: CohortVersion | None,
    candidate: CohortVersion | None,
    now: datetime,
) -> CohortVersion | None:
    """Stage this ranking unless a version already holds exactly it.

    Compared against both the active version and the waiting candidate, in rank
    order. A weekly census over an unchanged quarter produces an identical
    ranking, and staging it every week would fill the table with versions that
    say nothing and re-warm fifty symbols for no reason.
    """
    wanted = tuple(company.symbol for company in ranking)

    for version in (candidate, active):
        if version is None:
            continue
        if (
            version.reporting_period == period
            and store.symbols(version.id) == wanted
        ):
            return None

    return store.stage(ranking, period, census_run_id, now)


def _universe_overflow(
    explicit: Sequence[str],
    cohort: Sequence[str],
    cap: int,
) -> int:
    """How many symbols the Universe would hold, if that is over the cap.

    Zero when it fits. Deduplicated first, because a symbol declared explicitly
    *and* ranked into the cohort occupies one place, not two — refusing an
    activation over a symbol counted twice would be refusing it over nothing.
    """
    union = dict.fromkeys([symbol.upper() for symbol in explicit])
    union.update(dict.fromkeys([symbol.upper() for symbol in cohort]))
    return len(union) if len(union) > cap else 0


def _warm_up(
    session: Session,
    members: Sequence[str],
    warm: Callable[[Sequence[str]], Any] | None,
) -> tuple[str, ...]:
    """Load the recent signal window for members that cannot be evaluated yet.

    Only the ones that need it. A member already carrying its baseline costs a
    window of provider allowance to re-read and gains nothing, and the allowance
    is what stops the other members from becoming evaluable today.

    A Warm-up that fails is logged and not raised: the candidate simply stays a
    candidate, which is the state the system is designed to sit in.
    """
    ready = set(evaluable_symbols(session, members))
    cold = tuple(symbol for symbol in members if symbol not in ready)
    if not cold:
        return ()

    warm = warm or _default_warm(session)
    try:
        warm(cold)
    except Exception as exc:
        logger.warning("Warm-up for the cohort candidate failed: %s", exc)
        return ()
    return cold


def run_cohort_refresh(census_run_id: int, settings: Any | None = None) -> CohortRefresh:
    """Move the cohort forward once, against the configured account.

    Opens its own session and commits, like the runs it follows: a Warm-up inside
    it can take minutes per symbol, and holding the census's transaction open
    across that would keep the whole pass invisible until it ended.
    """
    from src.core.config import get_settings
    from src.core.database import get_sync_db

    from .universe import Universe

    settings = settings or get_settings()
    declared = Universe.from_settings(settings)

    with get_sync_db() as session:
        return refresh_cohort(
            session,
            census_run_id=census_run_id,
            cohort_size=settings.cohort_size,
            min_members=settings.cohort_activation_min_members,
            coverage_threshold=settings.rankable_period_coverage,
            explicit_symbols=declared.explicit,
        )


def _default_warm(session: Session) -> Callable[[Sequence[str]], Any]:
    """Warm through the Main Source, on the session this refresh is running in."""

    def warm(symbols: Sequence[str]) -> Any:
        from .warmup import build_warmup

        return build_warmup(SnapshotStore(session)).run(symbols)

    return warm
