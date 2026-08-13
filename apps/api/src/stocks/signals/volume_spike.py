"""A session that traded unlike the twenty before it, and how sure we are.

The ratio is the easy half. The hard half is everything the ratio cannot be
computed from, because each of those has a different honest answer:

*A session the store does not hold is not a session of no trading.* A missing
row is the absence of data; an explicit zero is data saying nothing traded. Fold
them together and a suspended company either invents a baseline or discards a
real suspension.

*A baseline shorter than twenty sessions is a different baseline.* Not a weaker
one — a different one. So a symbol that cannot fill the window is unevaluable
and says which of the two reasons it is, rather than being averaged over
whatever it happens to have.

*How complete an answer is and how old it is are two questions.* A result can be
whole and a week stale, or fresh and missing five companies. Collapsed into one
status, the reader loses whichever of the two the collapse dropped.

Both Signal Scopes resolve to the same Signal Trading Day — the newest session
the cohort can actually be evaluated on — so the two screens are never talking
about different days while showing the same date range.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster, ProviderSnapshot

from ..cohort import (
    COHORT_ACTIVATION_MIN_MEMBERS,
    CohortStore,
    cohort_version_active_on,
)
from ..providers.contracts import (
    Capability,
    Exchange,
    MarketSnapshot,
    main_source,
)
from ..providers.normalize import VN_TZ
from ..trading_day import latest_trading_day, trading_days_before
from ..universe import Universe, build_universe

logger = logging.getLogger(__name__)

# The window a session is compared against. Twenty sessions rather than a month:
# it is the length the market itself is read in, and it survives Tet without
# reaching into the quarter before.
BASELINE_TRADING_DAYS = 20

# How far back the resolver may walk looking for a session the cohort can be
# evaluated on. Ten sessions is two weeks of trading — long enough to cover a
# holiday plus a collector outage, short enough that what comes back is still
# recognisable as recent. Past it the honest answer is that there is none.
SIGNAL_LOOKBACK_TRADING_DAYS = 10

DEFAULT_THRESHOLD = 1.5
MIN_THRESHOLD = 1.0

# Past this the signal is old regardless of how complete it is. Counted in
# calendar days because that is what the reader is measuring against — a chart
# a week out of date is a week out of date whether or not the exchange was open.
STALE_SIGNAL_AGE_DAYS = 7

# The share of the Universe that has to be evaluable before a partial answer is
# worth showing. Below it the sample says more about the collector than about
# the market.
UNIVERSE_PARTIAL_COVERAGE = 0.90

_MARKET = Capability.MARKET.value


class SignalScope(str, Enum):
    """Which set of symbols a signal was computed over.

    ``universe`` is labelled **All Universe** everywhere it is rendered, never
    "All Market": this system watches a hundred symbols and saying otherwise
    would claim a market-wide answer it does not have (``docs/adr/0001``).
    """

    PROFIT_LEADERS = "profit_leaders"
    UNIVERSE = "universe"


class CoverageState(str, Enum):
    """How much of the scope the answer actually covers."""

    READY = "ready"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class Freshness(str, Enum):
    """How the session answered for relates to the newest one in the store."""

    FRESH = "fresh"
    LAGGING = "lagging"
    STALE = "stale"


class SignalIssue(str, Enum):
    """Why an answer is less than whole. A closed set, by design.

    These are domain provenance, not transport failures: they travel in the body
    of a 200 response, never as an HTTP status and never as prose. A closed set
    is what lets the web app hold one Vietnamese sentence per code instead of
    rendering whatever the API happened to say.
    """

    MISSING_TARGET_SESSION = "missing_target_session"
    INSUFFICIENT_HISTORY = "insufficient_history"
    RECENTLY_INACTIVE = "recently_inactive"
    COHORT_WARMING = "cohort_warming"
    LAGGING_MARKET_DATA = "lagging_market_data"
    STALE_MARKET_DATA = "stale_market_data"
    RANKING_UNAVAILABLE = "ranking_unavailable"


@dataclass(frozen=True)
class SymbolReading:
    """One symbol as of the Signal Trading Day.

    Carries its own issues rather than being dropped from the answer. A symbol
    that could not be evaluated is a fact about the signal's completeness, and a
    list that quietly omits it presents a partial answer as a whole one.
    """

    symbol: str
    exchange: str | None = None
    volume: int | None = None
    baseline_average_volume: float | None = None
    ratio: float | None = None
    close_price: float | None = None
    change_pct: float | None = None
    issues: tuple[SignalIssue, ...] = ()

    @property
    def evaluable(self) -> bool:
        """Whether the twenty-one sessions this needs were all in the store.

        A company that traded nothing is still evaluable: zero volume against a
        zero baseline is an answer about a dormant company, not a gap in what
        was collected.
        """
        return not {
            SignalIssue.MISSING_TARGET_SESSION,
            SignalIssue.INSUFFICIENT_HISTORY,
        } & set(self.issues)


@dataclass(frozen=True)
class Coverage:
    """How many of the scope's symbols the answer could be computed for."""

    state: CoverageState
    evaluated: int
    total: int


@dataclass(frozen=True)
class CohortVersionRef:
    """Which Cohort Version the profit-leaders answer was computed against."""

    id: int
    reporting_period: date


@dataclass(frozen=True)
class VolumeSpikeSignal:
    """One answer, with everything needed to judge how much to trust it."""

    scope: SignalScope
    trading_day: date | None
    threshold: float
    coverage: Coverage
    freshness: Freshness
    cohort_version: CohortVersionRef | None
    issues: tuple[SignalIssue, ...]
    readings: tuple[SymbolReading, ...]

    @property
    def spikes(self) -> tuple[SymbolReading, ...]:
        """The symbols that cleared the threshold, loudest first.

        Empty whenever no Signal Trading Day was settled on. The readings behind
        an unresolved answer are what the newest session *would* have said if
        enough of the cohort could be evaluated on it, and they are kept so the
        answer can state its coverage honestly — but a spike drawn from a
        session the signal refused to stand behind is not a finding.
        """
        if self.trading_day is None:
            return ()
        return tuple(
            sorted(
                (
                    reading
                    for reading in self.readings
                    if reading.ratio is not None and reading.ratio >= self.threshold
                ),
                key=lambda reading: reading.ratio or 0,
                reverse=True,
            )
        )

    @property
    def unevaluable(self) -> tuple[SymbolReading, ...]:
        """The symbols the store could not answer for, alphabetically."""
        return tuple(
            sorted(
                (reading for reading in self.readings if not reading.evaluable),
                key=lambda reading: reading.symbol,
            )
        )


def _day_start(day: date) -> datetime:
    """Midnight in Vietnam, which is how a session is stamped."""
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


def _sessions_by_symbol(
    session: Session,
    symbols: Sequence[str],
    days: Sequence[date],
) -> dict[str, dict[date, MarketSnapshot]]:
    """Read these symbols' sessions for exactly these days, in one query.

    Where two sources hold the same session the Main Source wins, the way
    ``SnapshotStore.series`` resolves it: the Cover Source's history is a quote
    series and carries a thinner session, so letting a late backfill overwrite a
    collected one would change the number without changing anything visible.
    """
    if not symbols or not days:
        return {}

    stamps = [_day_start(day) for day in days]
    wanted = [symbol.upper() for symbol in symbols]
    rows = session.execute(
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.capability == _MARKET,
            ProviderSnapshot.symbol.in_(wanted),
            ProviderSnapshot.effective_at.in_(stamps),
        )
        .order_by(
            ProviderSnapshot.effective_at.asc(),
            ProviderSnapshot.observed_at.asc(),
        )
    ).scalars()

    main = main_source(Capability.MARKET).value
    held: dict[str, dict[date, ProviderSnapshot]] = {}
    for row in rows:
        day = row.effective_at.astimezone(VN_TZ).date()
        by_day = held.setdefault(row.symbol, {})
        existing = by_day.get(day)
        if existing is None or existing.source != main:
            by_day[day] = row

    return {
        symbol: {
            day: MarketSnapshot.model_validate(row.payload)
            for day, row in by_day.items()
        }
        for symbol, by_day in held.items()
    }


def _exchanges_of(session: Session, symbols: Sequence[str]) -> dict[str, str]:
    """Which board each symbol is listed on, from the listing register.

    Read here rather than from the Cohort Version's own ``exchange`` column,
    because the declared half of the Universe was never in a cohort and would
    otherwise have no board at all. A symbol the register has never carried
    simply has none, and an exchange filter drops it from both halves of the
    coverage fraction rather than counting it as a failure to evaluate.
    """
    if not symbols:
        return {}
    rows = session.execute(
        select(ListingRoster.symbol, ListingRoster.exchange).where(
            ListingRoster.symbol.in_([symbol.upper() for symbol in symbols])
        )
    ).all()
    return {str(symbol): str(exchange) for symbol, exchange in rows}


def evaluate_symbols(
    session: Session,
    symbols: Sequence[str],
    day: date,
    baseline_days: int = BASELINE_TRADING_DAYS,
) -> tuple[SymbolReading, ...]:
    """Evaluate each symbol against the ``baseline_days`` sessions before ``day``.

    The window is resolved once, market-wide, and every symbol is measured
    against the same one. Resolved per symbol, a company with gaps would reach
    further back, average a different stretch of market, and be presented beside
    the others as if the two numbers were comparable.
    """
    wanted = [symbol.upper() for symbol in symbols]
    if not wanted:
        return ()

    exchanges = _exchanges_of(session, wanted)
    baseline_window = trading_days_before(session, day, baseline_days)
    if len(baseline_window) < baseline_days:
        # The store does not hold twenty sessions before this one. Padding the
        # window with calendar days would invent sessions the market never had.
        return tuple(
            SymbolReading(
                symbol=symbol,
                exchange=exchanges.get(symbol),
                issues=(SignalIssue.INSUFFICIENT_HISTORY,),
            )
            for symbol in wanted
        )

    sessions = _sessions_by_symbol(
        session, wanted, (day,) + tuple(baseline_window)
    )
    return tuple(
        _read_symbol(symbol, sessions.get(symbol, {}), day, baseline_window, exchanges)
        for symbol in wanted
    )


def _read_symbol(
    symbol: str,
    held: dict[date, MarketSnapshot],
    day: date,
    baseline_window: Sequence[date],
    exchanges: dict[str, str],
) -> SymbolReading:
    """Turn one symbol's stored sessions into its reading for the day."""
    exchange = exchanges.get(symbol)
    target = held.get(day)
    # A session held without a traded quantity in it is not a session that
    # traded nothing: the field is absent, so there is no number to compare.
    if target is None or target.volume is None:
        return SymbolReading(
            symbol=symbol,
            exchange=exchange,
            issues=(SignalIssue.MISSING_TARGET_SESSION,),
        )

    baseline = [held.get(item) for item in baseline_window]
    volumes = [
        snapshot.volume
        for snapshot in baseline
        if snapshot is not None and snapshot.volume is not None
    ]
    if len(volumes) < len(baseline_window):
        return SymbolReading(
            symbol=symbol,
            exchange=exchange,
            issues=(SignalIssue.INSUFFICIENT_HISTORY,),
        )

    # An explicit zero belongs in the baseline — it is the market saying this
    # company did not trade — and a company carrying one is worth flagging,
    # because a ratio drawn from a stretch of dormancy exaggerates a return to
    # ordinary volume.
    issues = (SignalIssue.RECENTLY_INACTIVE,) if any(v == 0 for v in volumes) else ()

    average = sum(volumes) / len(volumes)
    reading = SymbolReading(
        symbol=symbol,
        exchange=exchange,
        volume=target.volume,
        baseline_average_volume=average,
        close_price=target.last_price,
        change_pct=target.change_pct,
        issues=issues,
    )
    if average == 0:
        # Nothing traded across the whole window, so there is no ratio to state:
        # anything divided by nothing would report the first active session as an
        # infinite spike.
        return reading

    return replace(reading, ratio=target.volume / average)


@dataclass(frozen=True)
class _Resolution:
    """The session a signal settled on, and the cohort that was current then.

    ``day`` is None when no session in the window could be evaluated, and the
    readings are kept anyway: they are what the newest session with a cohort
    behind it did say, which is how the answer can report "44 of 50" instead of
    "0 of 50" while still refusing to serve a signal. Reporting zero would
    describe a cohort nothing is known about, and the reader would have no way
    to tell that from one that is two symbols short.
    """

    day: date | None
    version_id: int | None
    reporting_period: date | None
    members: tuple[str, ...]
    readings: tuple[SymbolReading, ...]
    issue: SignalIssue | None = None

    @classmethod
    def unresolved(
        cls,
        issue: SignalIssue,
        members: tuple[str, ...] = (),
        readings: tuple[SymbolReading, ...] = (),
    ) -> "_Resolution":
        """No session to answer for, and the reason why."""
        return cls(
            day=None,
            version_id=None,
            reporting_period=None,
            members=members,
            readings=readings,
            issue=issue,
        )


def _resolve(
    session: Session,
    day: date | None,
    min_members: int,
    lookback: int,
    newest: date | None,
) -> _Resolution:
    """Find the newest session the active cohort can actually be evaluated on.

    A named day is taken as asked — a historical query is a question about that
    session, and answering it with a different one would be answering a
    different question. Otherwise the walk goes back from the newest Trading Day
    and stops at the first session where enough of the cohort is evaluable.

    Both scopes go through here. Anchoring the Universe screen to the same
    session keeps the two from disagreeing about which day "today" is while
    showing the same date.
    """
    store = CohortStore(session)

    if day is not None:
        version = cohort_version_active_on(session, day)
        if version is None:
            return _Resolution.unresolved(SignalIssue.RANKING_UNAVAILABLE)
        members = store.symbols(version.id)
        return _Resolution(
            day=day,
            version_id=version.id,
            reporting_period=version.reporting_period,
            members=members,
            readings=evaluate_symbols(session, members, day),
        )

    if newest is None:
        return _Resolution.unresolved(SignalIssue.RANKING_UNAVAILABLE)

    candidates = (newest,) + trading_days_before(session, newest, lookback - 1)
    # What the newest session with a cohort behind it managed to evaluate. Held
    # on to so a walk that ends without a usable session can still say how close
    # it came.
    best_members: tuple[str, ...] = ()
    best_readings: tuple[SymbolReading, ...] = ()
    for candidate in candidates:
        version = cohort_version_active_on(session, candidate)
        if version is None:
            continue
        members = store.symbols(version.id)
        readings = evaluate_symbols(session, members, candidate)
        evaluable = sum(1 for reading in readings if reading.evaluable)
        if evaluable >= min_members:
            return _Resolution(
                day=candidate,
                version_id=version.id,
                reporting_period=version.reporting_period,
                members=members,
                readings=readings,
            )
        if not best_members:
            best_members, best_readings = members, readings

    logger.info(
        "No session in the last %d has %d evaluable cohort members",
        lookback,
        min_members,
    )
    return _Resolution.unresolved(
        issue=(
            SignalIssue.COHORT_WARMING
            if best_members
            else SignalIssue.RANKING_UNAVAILABLE
        ),
        members=best_members,
        readings=best_readings,
    )


def _coverage(
    scope: SignalScope,
    evaluated: int,
    total: int,
    min_members: int,
) -> Coverage:
    """Name how complete this answer is, per scope.

    The two scopes are counted differently because they promise different
    things. The cohort promises fifty specific companies, so the floor is a
    count: forty-five of the fifty asked for. The Universe promises whatever is
    configured plus whatever the census seated, so the floor is a share of it.
    """
    if total == 0:
        return Coverage(state=CoverageState.INSUFFICIENT_DATA, evaluated=0, total=0)

    if evaluated >= total:
        state = CoverageState.READY
    elif scope is SignalScope.PROFIT_LEADERS:
        state = (
            CoverageState.PARTIAL
            if evaluated >= min_members
            else CoverageState.INSUFFICIENT_DATA
        )
    else:
        state = (
            CoverageState.PARTIAL
            if evaluated / total >= UNIVERSE_PARTIAL_COVERAGE
            else CoverageState.INSUFFICIENT_DATA
        )

    return Coverage(state=state, evaluated=evaluated, total=total)


def _freshness(
    day: date | None,
    newest: date | None,
    now: datetime,
) -> Freshness:
    """How old the answered session is, judged apart from how complete it is.

    Age wins over lag: a signal computed on the newest session in the store is
    still stale if that session is from last month, and calling it fresh because
    nothing newer exists would report a dead collector as a healthy one.
    """
    if day is None:
        return Freshness.STALE

    if (now.astimezone(VN_TZ).date() - day).days > STALE_SIGNAL_AGE_DAYS:
        return Freshness.STALE
    if newest is not None and newest > day:
        return Freshness.LAGGING
    return Freshness.FRESH


def signal_cache_key(
    scope: SignalScope,
    trading_day: date | None,
    threshold: float,
    exchange: Exchange | None,
    cohort_version_id: int | None,
    market_generation: datetime | None,
) -> str:
    """The six inputs an answer depends on, as one key (``docs/adr/0005``).

    Every input that can change the answer is in the key, so a changed input
    lands on a different entry and no invalidation call has to be made or
    remembered. Market generation is what closes the loop: it moves whenever
    stored market data does, which makes an entry computed before a write
    unreachable afterwards rather than merely unlikely to be read.
    """
    return ":".join(
        [
            scope.value,
            trading_day.isoformat() if trading_day else "none",
            f"{threshold:g}",
            exchange.value if exchange else "all",
            str(cohort_version_id) if cohort_version_id is not None else "none",
            market_generation.isoformat() if market_generation else "none",
        ]
    )


def volume_spike_signal(
    session: Session,
    scope: SignalScope,
    threshold: float = DEFAULT_THRESHOLD,
    exchange: Exchange | None = None,
    trading_day: date | None = None,
    universe: Universe | None = None,
    min_members: int = COHORT_ACTIVATION_MIN_MEMBERS,
    lookback: int = SIGNAL_LOOKBACK_TRADING_DAYS,
    now: datetime | None = None,
) -> VolumeSpikeSignal:
    """Serve the Volume Spike signal for one scope, out of the store alone.

    What comes back is never only the spikes. Coverage says how much of the
    scope was evaluable, freshness says how old the session is, and the
    unevaluable symbols are named — because a list of five spikes drawn from
    twelve companies and one drawn from fifty look identical until the answer
    says which it is.
    """
    stamped = now or datetime.now(timezone.utc)
    newest = latest_trading_day(session)
    resolution = _resolve(session, trading_day, min_members, lookback, newest)

    if resolution.day is None:
        # The cohort's own readings, even for the Universe scope: they are the
        # only measured thing here, and they say how far the ranking is from
        # being servable. The Universe was never evaluated — no session was
        # settled on to evaluate it against — so its scope reports nothing
        # rather than borrowing the cohort's fraction.
        readings = (
            resolution.readings if scope is SignalScope.PROFIT_LEADERS else ()
        )
        evaluated = sum(1 for reading in readings if reading.evaluable)
        return VolumeSpikeSignal(
            scope=scope,
            trading_day=None,
            threshold=threshold,
            coverage=_coverage(scope, evaluated, len(readings), min_members),
            freshness=_freshness(None, newest, stamped),
            cohort_version=None,
            issues=(resolution.issue,) if resolution.issue else (),
            readings=readings,
        )

    if scope is SignalScope.PROFIT_LEADERS:
        # The exchange filter belongs to the Universe screen. The cohort is
        # ranked across HOSE and HNX together, so narrowing it by board would
        # answer with part of a ranking while still calling it the ranking.
        readings = resolution.readings
    else:
        symbols = (universe or build_universe(session)).symbols
        readings = evaluate_symbols(session, symbols, resolution.day)
        if exchange is not None:
            readings = tuple(
                reading
                for reading in readings
                if reading.exchange == exchange.value
            )

    evaluated = sum(1 for reading in readings if reading.evaluable)
    freshness = _freshness(resolution.day, newest, stamped)
    issues: list[SignalIssue] = []
    if freshness is Freshness.LAGGING:
        issues.append(SignalIssue.LAGGING_MARKET_DATA)
    elif freshness is Freshness.STALE:
        issues.append(SignalIssue.STALE_MARKET_DATA)

    return VolumeSpikeSignal(
        scope=scope,
        trading_day=resolution.day,
        threshold=threshold,
        coverage=_coverage(scope, evaluated, len(readings), min_members),
        freshness=freshness,
        cohort_version=(
            CohortVersionRef(
                id=resolution.version_id,
                reporting_period=resolution.reporting_period,
            )
            if scope is SignalScope.PROFIT_LEADERS
            and resolution.version_id is not None
            and resolution.reporting_period is not None
            else None
        ),
        issues=tuple(issues),
        readings=readings,
    )
