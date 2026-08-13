"""Who the fifty most profitable listed companies actually are.

The question ADR-0004 asks is market-wide: not "which of the hundred symbols we
already follow earn the most", which answers itself, but "which fifty companies
on HOSE and HNX earn the most" — out of roughly 1,600. That is the whole reason
this exists as a census rather than as a query.

Three things make it awkward, and the shape of this module is what they leave
behind:

*Quota.* Statements have no batched form, so the market costs two vnstock
requests per symbol against an allowance of 20 a minute. A full pass cannot
finish in one sitting, so a run resumes: a symbol already covered at the period
being assessed is skipped rather than re-read, and progress is committed as it
goes so an interrupted run leaves what it earned behind.

*Companies report at different times.* There is no moment when the market has
one common reporting period. A period becomes rankable only once ``0.95`` of the
listed market has reported it, and until then the previous period keeps being
the one ranked — ranking a period that half the market has not reported would
crown whoever filed early.

*A profit figure is not an opinion.* Coverage counts companies whose profit is
*known* at the period, including the ones that lost money. Eligibility for the
ranking is stricter: profit has to be there and positive. Conflating the two
would let a market full of losses look uncovered, or a company with no filing
look like a company that broke even.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from time import sleep as _sleep
from typing import Any, Literal

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported
from src.stocks.models import ListingRoster, ProfitRankingCensusRun, ProviderSnapshot

from .listing_roster import ListingRosterStore, RosterRefresh
from .providers import (
    Capability,
    Exchange,
    FundamentalDataProvider,
    ListingRosterProvider,
    RANKED_EXCHANGES,
    SnapshotStore,
    main_source,
)
from .providers.contracts import FundamentalSnapshot
from .providers.normalize import VN_TZ, day_in_vn

logger = logging.getLogger(__name__)

# The share of the listed market that has to have reported a period before that
# period may be ranked. Below it, the ranking stays on the period before.
RANKABLE_PERIOD_COVERAGE = 0.95

# How many seats ADR-0003 reserves for the Profit Leaders Cohort.
COHORT_SIZE = 50

# How often a long run hands what it has read to the database. A full census runs
# for over an hour; without this, a process killed at minute fifty has read fifty
# minutes of quota and stored none of it.
COMMIT_EVERY_SYMBOLS = 25

_FUNDAMENTAL = Capability.FUNDAMENTAL.value

CensusStatus = Literal["running", "complete", "failed"]


class CensusUnavailable(RuntimeError):
    """The census cannot run because an upstream refused the account.

    Distinct from a census that ran and covered little: quota exhaustion says
    nothing about how much of the market has reported, and recording it as low
    coverage would make the next period look unrankable for a reason that has
    nothing to do with the market.
    """


@dataclass(frozen=True)
class RankedCompany:
    """One company's place in the profit ranking at one reporting period."""

    rank: int
    symbol: str
    net_income_vnd: float
    exchange: Exchange


@dataclass(frozen=True)
class PeriodCoverage:
    """How much of the listed market has reported one period.

    Both counts are carried rather than just the ratio: "covered 1,481 of 1,559"
    is answerable and "covered 95%" is not, and an operator looking at a period
    that failed to become rankable needs to know which of the two numbers moved.
    """

    period: date
    eligible: int
    covered: int
    threshold: float = RANKABLE_PERIOD_COVERAGE

    @property
    def ratio(self) -> float:
        """The share reported, or zero when there is no market to report.

        Zero rather than an error: an empty roster is a system that has not
        censused yet, and it must not be able to clear a threshold by dividing
        nothing by nothing.
        """
        if self.eligible <= 0:
            return 0.0
        return self.covered / self.eligible

    @property
    def rankable(self) -> bool:
        return self.eligible > 0 and self.ratio >= self.threshold


@dataclass(frozen=True)
class CensusOutcome:
    """How one census run ended, in the terms the next decision needs.

    ``rankable`` is the one that matters downstream: a run can complete cleanly,
    read the whole market, and still leave the newest period unrankable because
    the companies simply have not filed yet. That is a normal outcome, not a
    failure, and the two have to be distinguishable here or the cohort refresh
    cannot tell "nothing to do yet" from "something broke".
    """

    status: Literal["complete", "failed", "skipped"]
    run_id: int | None = None
    target_period: date | None = None
    eligible_symbols: int = 0
    covered_symbols: int = 0
    rankable: bool = False
    symbols_read: int = 0
    roster: RosterRefresh | None = None
    error: str | None = None

    def as_result(self) -> dict:
        return {
            "status": self.status,
            "run_id": self.run_id,
            "target_period": (
                self.target_period.isoformat() if self.target_period else None
            ),
            "eligible_symbols": self.eligible_symbols,
            "covered_symbols": self.covered_symbols,
            "rankable": self.rankable,
            "symbols_read": self.symbols_read,
            "roster": self.roster.as_result() if self.roster else None,
            "error": self.error,
        }


class CensusRunStore:
    """The durable record of a census pass."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def start(self, now: datetime) -> ProfitRankingCensusRun:
        run = ProfitRankingCensusRun(
            started_at=now,
            status="running",
            eligible_symbols=0,
            covered_symbols=0,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def record(
        self,
        run: ProfitRankingCensusRun,
        target_period: date | None,
        eligible: int,
        covered: int,
    ) -> None:
        run.target_period = target_period
        run.eligible_symbols = eligible
        run.covered_symbols = covered
        self.session.flush()

    def finish(
        self,
        run: ProfitRankingCensusRun,
        status: CensusStatus,
        now: datetime,
        error: str | None = None,
    ) -> None:
        run.status = status
        run.finished_at = now
        # Truncated to the column rather than allowed to fail the write: the run
        # record exists to explain a failure, and losing it to a long traceback
        # is the one way it cannot do that.
        run.last_error = error[:500] if error else None
        self.session.flush()

    def latest_complete(self) -> ProfitRankingCensusRun | None:
        return self.session.execute(
            select(ProfitRankingCensusRun)
            .where(ProfitRankingCensusRun.status == "complete")
            .order_by(ProfitRankingCensusRun.id.desc())
            .limit(1)
        ).scalar_one_or_none()


def _period_start(period: date) -> datetime:
    """Midnight in Vietnam, which is how a reporting period is stamped."""
    return datetime.combine(period, time.min, tzinfo=VN_TZ)


def _profit_of(payload: Any) -> float | None:
    """Read the trailing-twelve-month parent profit out of a stored snapshot.

    Read off the payload rather than through ``SnapshotStore.latest``, which
    answers one symbol at a time: the census asks about the whole market at once,
    and 1,600 round trips to answer one question is the thing this module exists
    to avoid.
    """
    if not isinstance(payload, dict):
        return None
    value = payload.get("trailing_12_month_net_income_vnd")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def observed_periods(session: Session) -> tuple[date, ...]:
    """Every reporting period the store holds a fundamental Snapshot for.

    Newest first. Read off ``effective_at`` rather than out of the payload
    because every adapter stamps a fundamental Snapshot at midnight in Vietnam on
    the period end, which makes the period an indexed column rather than a JSON
    field.
    """
    rows = session.execute(
        select(distinct(ProviderSnapshot.effective_at))
        .where(ProviderSnapshot.capability == _FUNDAMENTAL)
        .order_by(ProviderSnapshot.effective_at.desc())
    ).scalars()
    return tuple(day_in_vn(stamp) for stamp in rows)


def reported_profits(session: Session, period: date) -> dict[str, float | None]:
    """Every symbol with a fundamental Snapshot at this period, and its profit.

    A symbol present with ``None`` reported the period without a usable profit
    figure — four quarters of parent profit is what the adapter needs and a young
    company does not have that. It counts as neither covered nor rankable, and
    the difference from a symbol that is simply absent is worth keeping: one has
    been asked and answered, the other still costs two requests.
    """
    rows = session.execute(
        select(ProviderSnapshot.symbol, ProviderSnapshot.payload).where(
            ProviderSnapshot.capability == _FUNDAMENTAL,
            ProviderSnapshot.source == main_source(Capability.FUNDAMENTAL).value,
            ProviderSnapshot.effective_at >= _period_start(period),
            ProviderSnapshot.effective_at < _period_start(period + timedelta(days=1)),
        )
    ).all()
    return {str(symbol): _profit_of(payload) for symbol, payload in rows}


def period_coverage(
    session: Session,
    period: date,
    eligible: Sequence[str],
    threshold: float = RANKABLE_PERIOD_COVERAGE,
) -> PeriodCoverage:
    """Measure one period against the listed market.

    The denominator is the currently listed HOSE and HNX equities and nothing
    else. Counting UPCOM in it would hold every period below the threshold
    forever — a third of that board never files on this cadence — and counting
    delisted companies in it would make coverage fall as the market changed
    rather than as reporting did.
    """
    reported = reported_profits(session, period)
    covered = sum(
        1 for symbol in eligible if reported.get(symbol) is not None
    )
    return PeriodCoverage(
        period=period,
        eligible=len(eligible),
        covered=covered,
        threshold=threshold,
    )


def newest_rankable_period(
    session: Session,
    eligible: Sequence[str],
    threshold: float = RANKABLE_PERIOD_COVERAGE,
) -> PeriodCoverage | None:
    """The newest period the market has reported well enough to rank.

    Walks back from the newest period rather than trusting the newest one: the
    quarter that just ended is normally the one below threshold, and the ranking
    has to stay on the last period that cleared it. Returns None when no period
    has ever cleared it, which is what a system censusing for the first time
    looks like.
    """
    for period in observed_periods(session):
        coverage = period_coverage(session, period, eligible, threshold)
        if coverage.rankable:
            return coverage
    return None


def rank_profit_leaders(
    session: Session,
    period: date,
    size: int = COHORT_SIZE,
) -> tuple[RankedCompany, ...]:
    """The top ``size`` listed HOSE/HNX companies by profit at this period.

    Eligible means all four of: currently listed, on a ranked board, a profit
    figure at *this* period, and that figure strictly positive. A company still
    reporting the quarter before is not ranked at this one — that is the whole
    point of ranking at a common period.

    Ordered by profit descending, then symbol ascending. The tiebreak is not
    decoration: two companies reporting the same profit at rank 50 would
    otherwise make the cohort's fiftieth seat depend on row order, and the cohort
    would differ between two runs over identical data.
    """
    rows = session.execute(
        select(ListingRoster.symbol, ListingRoster.exchange).where(
            ListingRoster.is_listed.is_(True),
            ListingRoster.exchange.in_([item.value for item in RANKED_EXCHANGES]),
        )
    ).all()
    reported = reported_profits(session, period)

    candidates: list[tuple[float, str, Exchange]] = []
    for symbol, exchange in rows:
        profit = reported.get(str(symbol))
        if profit is None or profit <= 0:
            continue
        candidates.append((profit, str(symbol), Exchange(exchange)))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return tuple(
        RankedCompany(
            rank=index,
            symbol=symbol,
            net_income_vnd=profit,
            exchange=exchange,
        )
        for index, (profit, symbol, exchange) in enumerate(candidates[:size], start=1)
    )


class Census:
    """Read the market's profit figures, storing each one as it arrives."""

    def __init__(
        self,
        session: Session,
        store: SnapshotStore,
        fundamental: FundamentalDataProvider,
        roster: ListingRosterProvider | None = None,
        request_delay: float = 0.0,
        coverage_threshold: float = RANKABLE_PERIOD_COVERAGE,
        commit_every: int = COMMIT_EVERY_SYMBOLS,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], None] = _sleep,
    ) -> None:
        self._session = session
        self._store = store
        self._fundamental = fundamental
        self._roster_provider = roster
        self._roster = ListingRosterStore(session)
        self._runs = CensusRunStore(session)
        self._delay = request_delay
        self._threshold = coverage_threshold
        self._commit_every = max(1, commit_every)
        self._now = now
        self._sleep = sleep

    def run(self, refresh_roster: bool = True) -> CensusOutcome:
        """Census the market once, and report whether a period became rankable.

        ``refresh_roster`` is what separates ADR-0004's two cadences. The weekly
        pass re-reads the listing register first, because that is when a new
        listing or a delisting should be noticed. The daily retry does not: it
        exists to chase the handful of companies that have not filed the newest
        period yet, and re-reading the register would let a provider hiccup
        delist a cohort member on a run whose job was to fill in two filings.
        """
        started = self._now()
        run = self._runs.start(started)
        self._session.commit()

        try:
            refresh = self._refresh_roster() if refresh_roster else None
            eligible = self._roster.listed_symbols(RANKED_EXCHANGES)
            if not eligible:
                # Nothing to census is not a failure — a fresh environment with
                # no roster reads exactly like this — but it is not a rankable
                # market either.
                logger.info("Census found no listed HOSE/HNX equities to read")
                self._runs.record(run, None, 0, 0)
                self._runs.finish(run, "complete", self._now())
                run_id = run.id
                self._session.commit()
                return CensusOutcome(
                    status="complete", run_id=run_id, roster=refresh
                )

            target = self._target_period()
            self._runs.record(run, target, len(eligible), 0)
            self._session.commit()

            read = self._read_market(run, eligible, target)
            coverage = self._settle(run, eligible)
            self._runs.finish(run, "complete", self._now())
            run_id = run.id
            self._session.commit()

            logger.info(
                "Census complete: %d/%d symbols reported %s (%.1f%%), rankable=%s",
                coverage.covered,
                coverage.eligible,
                coverage.period,
                coverage.ratio * 100,
                coverage.rankable,
            )
            return CensusOutcome(
                status="complete",
                run_id=run_id,
                target_period=coverage.period,
                eligible_symbols=coverage.eligible,
                covered_symbols=coverage.covered,
                rankable=coverage.rankable,
                symbols_read=read,
                roster=refresh,
            )

        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            logger.error("Census failed: %s", reason, exc_info=True)
            # Rolled back before the record is written: whatever failed may have
            # left the session unusable, and the run record is the one write that
            # must survive the failure.
            self._session.rollback()
            self._runs.finish(run, "failed", self._now(), reason)
            run_id = run.id
            self._session.commit()
            return CensusOutcome(status="failed", run_id=run_id, error=reason)

    def _refresh_roster(self) -> RosterRefresh | None:
        if self._roster_provider is None:
            logger.info("Census has no listing roster provider; using the stored roster")
            return None
        entries = self._roster_provider.fetch_listing_roster()
        refresh = self._roster.refresh(
            entries,
            source=self._roster_provider.source,
            observed_at=self._now(),
        )
        self._session.commit()
        return refresh

    def _target_period(self) -> date | None:
        """The period this run is trying to cover.

        The newest period anyone has reported, not the newest rankable one: the
        job of a run is to move the newest period *towards* rankable, so that is
        the period whose gaps it chases. None before the first symbol has been
        read at all, when there is no period to speak of yet.
        """
        periods = observed_periods(self._session)
        return periods[0] if periods else None

    def _read_market(
        self,
        run: ProfitRankingCensusRun,
        eligible: Sequence[str],
        target: date | None,
    ) -> int:
        """Read every eligible symbol not already covered at the target period.

        This is what "resumes from ``covered_symbols``" means in practice, and it
        is stronger than resuming by position: what a run must not do twice is
        spend two requests on a company whose figure it already holds, and the
        store already knows which those are. Resuming by count would re-read the
        market from the top whenever the roster changed length.
        """
        reported = reported_profits(self._session, target) if target else {}
        outstanding = [
            symbol for symbol in eligible if reported.get(symbol) is None
        ]
        if not outstanding:
            logger.info("Census has nothing outstanding at %s", target)
            return 0

        logger.info(
            "Census reading %d of %d eligible symbols for %s",
            len(outstanding),
            len(eligible),
            target,
        )

        read = 0
        for index, symbol in enumerate(outstanding, start=1):
            self._read_symbol(symbol)
            read += 1

            if index % self._commit_every == 0:
                self._runs.record(
                    run,
                    target,
                    len(eligible),
                    self._covered_count(eligible, target),
                )
                self._session.commit()
                logger.info("Census progress: %d/%d read", index, len(outstanding))

            if self._delay > 0 and index < len(outstanding):
                self._sleep(self._delay)

        return read

    def _read_symbol(self, symbol: str) -> None:
        """Fetch and store one company's statements, or let it go.

        A refusal about the account — quota exhausted, capability unimplemented —
        stops the run: it will refuse the next 1,500 symbols too, at the price of
        two requests each. A refusal about this company does not, because a
        delisted-but-still-registered ticker or an unreadable filing is ordinary
        and the rest of the market is fine.
        """
        try:
            snapshots = self._fundamental.fetch_fundamentals([symbol])
        except (VnstockUnavailable, VnstockUnsupported) as exc:
            raise CensusUnavailable(str(exc)) from exc

        for snapshot in snapshots:
            if not isinstance(snapshot, FundamentalSnapshot):
                continue
            try:
                # Stored as a raw observation carrying its own source and
                # effective time, exactly like a Universe member's statements
                # (``docs/adr/0004``). Nothing about being outside the Universe
                # changes what a filing is — only that no market Snapshot is
                # collected alongside it.
                self._store.save(Capability.FUNDAMENTAL, snapshot)
            except Exception as exc:
                logger.warning(
                    "Census could not store the %s filing for %s: %s",
                    snapshot.period_end,
                    symbol,
                    exc,
                )

    def _covered_count(self, eligible: Sequence[str], target: date | None) -> int:
        if target is None:
            return 0
        return period_coverage(
            self._session, target, eligible, self._threshold
        ).covered

    def _settle(
        self,
        run: ProfitRankingCensusRun,
        eligible: Sequence[str],
    ) -> PeriodCoverage:
        """Record the period this run leaves behind as the one being assessed.

        Re-read after the market pass rather than taken from before it: a run
        that discovers a new quarter mid-pass has changed which period is the
        newest, and the record has to name the period the coverage figures
        actually describe.
        """
        periods = observed_periods(self._session)
        if not periods:
            coverage = PeriodCoverage(
                period=day_in_vn(self._now()),
                eligible=len(eligible),
                covered=0,
                threshold=self._threshold,
            )
            self._runs.record(run, None, coverage.eligible, 0)
            return coverage

        coverage = period_coverage(
            self._session, periods[0], eligible, self._threshold
        )
        self._runs.record(run, coverage.period, coverage.eligible, coverage.covered)
        return coverage


def build_census(
    session: Session,
    settings: Any | None = None,
    with_roster: bool = True,
) -> Census:
    """Wire the census against the configured vnstock account."""
    from src.core.config import get_settings

    from .providers.vnstock_provider import (
        VnstockFundamentalProvider,
        VnstockListingRosterProvider,
    )

    settings = settings or get_settings()
    return Census(
        session=session,
        store=SnapshotStore(session),
        fundamental=VnstockFundamentalProvider(vnstock_source=settings.vnstock_source),
        roster=(
            VnstockListingRosterProvider(vnstock_source=settings.vnstock_source)
            if with_roster
            else None
        ),
        request_delay=settings.profit_census_request_delay,
        coverage_threshold=settings.rankable_period_coverage,
    )


def run_census(
    settings: Any | None = None,
    refresh_roster: bool = True,
) -> CensusOutcome:
    """Census the market once against the configured account.

    Synchronous throughout, like the Collector: the store is, and vnstock is, so
    a caller on an event loop hands this to a thread. It opens its own session
    because it commits as it goes — a run this long that held one transaction
    open would keep an hour of writes invisible and then lose them together.
    """
    from src.core.database import get_sync_db

    with get_sync_db() as session:
        census = build_census(session, settings=settings, with_roster=refresh_roster)
        return census.run(refresh_roster=refresh_roster)


def eligible_symbols(session: Session) -> tuple[str, ...]:
    """The listed HOSE/HNX equities a ranking may draw from."""
    return ListingRosterStore(session).listed_symbols(RANKED_EXCHANGES)


def rankable_coverage(
    session: Session,
    threshold: float = RANKABLE_PERIOD_COVERAGE,
) -> PeriodCoverage | None:
    """The newest rankable period measured against today's listed market."""
    return newest_rankable_period(session, eligible_symbols(session), threshold)
