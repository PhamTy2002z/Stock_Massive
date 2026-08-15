"""What a Volume Spike says, and what it refuses to say.

The signal is arithmetic over stored sessions, so most of these tests are about
the cases where the arithmetic must not run: a session the store does not hold,
a baseline that is not twenty sessions long, a company that traded nothing.
Each of those has a different honest answer, and the failure this file guards
against is any of them being flattened into a ratio nobody can question.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import (
    CohortMember,
    CohortVersion,
    CorporateAction,
    ListingRoster,
    ProviderSnapshot,
)
from src.stocks.providers import (
    Capability,
    CorporateActionEvent,
    Exchange,
    ProviderSource,
)
from src.stocks.providers.contracts import (
    MARKET_SCHEMA_VERSION,
    MarketSnapshot,
    SnapshotMetadata,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.corporate_actions import (
    CorporateActionStore,
    corporate_action_generation,
)
from src.stocks.signals.volume_spike import (
    BASELINE_TRADING_DAYS,
    CoverageState,
    Freshness,
    SignalIssue,
    SignalScope,
    evaluate_symbols,
    signal_cache_key,
    volume_spike_signal,
)
from src.stocks.universe import Universe, forget_cohort_cache

from .conftest import basis_of

# A Thursday, so the sessions before it straddle two weekends and a baseline
# built from calendar days would reach a different stretch of market than one
# built from sessions.
TODAY = date(2026, 8, 13)
NOW = datetime(2026, 8, 13, 11, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clear_universe_cache():
    forget_cohort_cache()
    yield
    forget_cohort_cache()


def open_session() -> Session:
    """One in-memory database, reachable from FastAPI's threadpool as well.

    A synchronous handler runs off the test's own thread, and the default
    per-thread SQLite connection would hand it a second, empty database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        ProviderSnapshot.__table__,
        ListingRoster.__table__,
        CohortVersion.__table__,
        CohortMember.__table__,
        CorporateAction.__table__,
    ):
        table.create(engine)
    return Session(engine)


def trading_calendar(count: int, last: date = TODAY) -> tuple[date, ...]:
    """``count`` weekday sessions ending at ``last``, oldest first.

    Weekends are skipped so the calendar stretches wider than the number of
    sessions in it — which is the only way a test can tell "twenty sessions"
    apart from "twenty days".
    """
    days: list[date] = []
    cursor = last
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(days))


def _stamp(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


def write_sessions(
    session: Session,
    symbol: str,
    volumes: dict[date, int | None],
    close_price: float | None = 20000,
    change_pct: float | None = 1.5,
    source: ProviderSource = ProviderSource.FIINQUANT,
) -> None:
    """Give a symbol a market Snapshot on each of these days.

    A ``None`` volume writes a session with no traded quantity in it, which is
    what a provider answering without the field looks like. Leaving a day out of
    the mapping writes no session at all — the two are different, and telling
    them apart is most of what this signal does.
    """
    for day, volume in volumes.items():
        snapshot = MarketSnapshot(
            symbol=symbol,
            metadata=SnapshotMetadata(
                source=source,
                effective_at=_stamp(day),
                observed_at=NOW,
                schema_version=MARKET_SCHEMA_VERSION,
            ),
            price_basis=basis_of(source),
            last_price=close_price,
            change_pct=change_pct,
            volume=volume,
        )
        session.add(
            ProviderSnapshot(
                capability=Capability.MARKET.value,
                symbol=symbol,
                source=source.value,
                effective_at=_stamp(day),
                observed_at=NOW,
                schema_version=MARKET_SCHEMA_VERSION,
                payload=snapshot.model_dump(mode="json"),
            )
        )
    session.flush()


def list_on(
    session: Session,
    symbols: list[str],
    exchange: Exchange = Exchange.HOSE,
) -> None:
    for symbol in symbols:
        session.add(
            ListingRoster(
                symbol=symbol,
                exchange=exchange.value,
                is_listed=True,
                company_name=None,
                source=ProviderSource.VNSTOCK.value,
                observed_at=NOW,
            )
        )
    session.flush()


def seat_cohort(
    session: Session,
    symbols: list[str],
    activated_at: datetime = datetime(2026, 1, 2, 3, 0, tzinfo=timezone.utc),
    reporting_period: date = date(2026, 3, 31),
    state: str = "active",
    superseded_at: datetime | None = None,
) -> CohortVersion:
    version = CohortVersion(
        reporting_period=reporting_period,
        census_run_id=1,
        state=state,
        created_at=activated_at,
        activated_at=activated_at,
        superseded_at=superseded_at,
        coverage_at_activation=len(symbols),
    )
    session.add(version)
    session.flush()
    for rank, symbol in enumerate(symbols, start=1):
        session.add(
            CohortMember(
                cohort_version_id=version.id,
                symbol=symbol,
                rank=rank,
                net_income_vnd=1_000_000 - rank,
                exchange=Exchange.HOSE.value,
            )
        )
    session.flush()
    return version


def steady_market(
    session: Session,
    symbols: list[str],
    sessions: tuple[date, ...],
    volume: int = 1_000_000,
) -> None:
    """Every symbol trading the same quantity on every session in the window."""
    for symbol in symbols:
        write_sessions(session, symbol, {day: volume for day in sessions})


def reading_for(readings, symbol: str):
    return next(item for item in readings if item.symbol == symbol)


class TestComputation:
    """The ratio itself, and the four ways a symbol can fail to have one."""

    def test_baseline_is_twenty_sessions_not_twenty_calendar_days(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        # Twenty-one weekday sessions reach back across four weekends, so a
        # baseline built from calendar days would start inside the window and
        # average a different stretch of market.
        assert (sessions[-1] - sessions[0]).days > BASELINE_TRADING_DAYS

        # The oldest session is the loud one. It only lands in the baseline if
        # the window is counted in sessions.
        volumes = {day: 1_000_000 for day in sessions}
        volumes[sessions[0]] = 21_000_000
        write_sessions(session, "FPT", volumes)

        readings = evaluate_symbols(session, ["FPT"], sessions[-1])
        baseline = reading_for(readings, "FPT").baseline_average_volume

        assert baseline == pytest.approx(2_000_000)

    def test_missing_target_session_is_not_a_zero(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        steady_market(session, ["VCB"], sessions)
        write_sessions(session, "FPT", {day: 1_000_000 for day in sessions[:-1]})

        reading = reading_for(evaluate_symbols(session, ["FPT"], sessions[-1]), "FPT")

        assert not reading.evaluable
        assert reading.issues == (SignalIssue.MISSING_TARGET_SESSION,)
        assert reading.ratio is None
        assert reading.volume is None

    def test_nineteen_baseline_sessions_is_insufficient_history(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        steady_market(session, ["VCB"], sessions)
        # The target session plus nineteen before it: one short, and one short
        # is a different baseline rather than a slightly weaker one.
        held = (sessions[-1],) + sessions[-BASELINE_TRADING_DAYS:-1]
        write_sessions(session, "SSB", {day: 1_000_000 for day in held})

        reading = reading_for(evaluate_symbols(session, ["SSB"], sessions[-1]), "SSB")

        assert not reading.evaluable
        assert reading.issues == (SignalIssue.INSUFFICIENT_HISTORY,)

    def test_store_without_twenty_sessions_evaluates_nothing(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS)
        steady_market(session, ["FPT"], sessions)

        reading = reading_for(evaluate_symbols(session, ["FPT"], sessions[-1]), "FPT")

        assert not reading.evaluable
        assert reading.issues == (SignalIssue.INSUFFICIENT_HISTORY,)

    def test_explicit_zero_stays_in_the_baseline(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        volumes = {day: 1_000_000 for day in sessions}
        # Two suspended sessions. Dropped from the baseline the mean would be a
        # million; kept, it is nine hundred thousand, and the symbol says why.
        volumes[sessions[0]] = 0
        volumes[sessions[1]] = 0
        volumes[sessions[-1]] = 2_000_000
        write_sessions(session, "HAG", volumes)

        reading = reading_for(evaluate_symbols(session, ["HAG"], sessions[-1]), "HAG")

        assert reading.evaluable
        assert reading.baseline_average_volume == pytest.approx(900_000)
        assert reading.ratio == pytest.approx(2_000_000 / 900_000)
        assert SignalIssue.RECENTLY_INACTIVE in reading.issues

    def test_a_baseline_of_nothing_produces_no_ratio(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        volumes = {day: 0 for day in sessions[:-1]}
        volumes[sessions[-1]] = 500_000
        write_sessions(session, "HAG", volumes)

        reading = reading_for(evaluate_symbols(session, ["HAG"], sessions[-1]), "HAG")

        assert reading.ratio is None
        assert reading.issues == (SignalIssue.RECENTLY_INACTIVE,)

    def test_a_share_count_change_degrades_the_ratio_without_dropping_it(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        volumes = {day: 1_000_000 for day in sessions}
        volumes[sessions[-1]] = 2_000_000
        write_sessions(session, "FPT", volumes)
        CorporateActionStore(session).save(
            CorporateActionEvent(
                symbol="FPT",
                event_code="ISS",
                title="Share Issue - Stock dividend ratio 10.0%",
                ex_date=sessions[10],
                record_date=sessions[11],
                public_date=sessions[5],
                exercise_ratio=0.10,
                value_per_share=None,
            ),
            ProviderSource.VNSTOCK,
            NOW,
        )

        reading = reading_for(evaluate_symbols(session, ["FPT"], sessions[-1]), "FPT")

        assert reading.evaluable
        assert reading.ratio == pytest.approx(2.0)
        assert SignalIssue.VOLUME_BASIS_BREAK in reading.issues

    @pytest.mark.parametrize(
        ("source", "close_price"),
        [
            (ProviderSource.FIINQUANT, None),
            (ProviderSource.VNSTOCK, 20_000),
        ],
    )
    def test_price_constraints_do_not_change_a_volume_only_reading(
        self,
        source: ProviderSource,
        close_price: float | None,
    ):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        volumes = {day: 1_000_000 for day in sessions}
        volumes[sessions[-1]] = 2_000_000
        write_sessions(
            session,
            "FPT",
            volumes,
            close_price=close_price,
            source=source,
        )

        reading = reading_for(evaluate_symbols(session, ["FPT"], sessions[-1]), "FPT")

        assert reading.evaluable
        assert reading.ratio == pytest.approx(2.0)
        assert reading.issues == ()

    def test_a_cohort_is_prepared_in_a_bounded_number_of_queries(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        symbols = [f"S{index:02d}" for index in range(50)]
        for symbol in symbols:
            write_sessions(session, symbol, {day: 1_000_000 for day in sessions})
        session.flush()

        statements = 0

        def count_statement(*_args):
            nonlocal statements
            statements += 1

        bind = session.get_bind()
        event.listen(bind, "before_cursor_execute", count_statement)
        try:
            readings = evaluate_symbols(session, symbols, sessions[-1])
        finally:
            event.remove(bind, "before_cursor_execute", count_statement)

        assert len(readings) == len(symbols)
        assert statements <= 4

    def test_a_ratio_at_the_threshold_is_a_spike(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        seat_cohort(session, ["FPT"])
        list_on(session, ["FPT"])
        volumes = {day: 1_000_000 for day in sessions[:-1]}
        volumes[sessions[-1]] = 1_500_000
        write_sessions(session, "FPT", volumes)

        signal = volume_spike_signal(
            session,
            scope=SignalScope.PROFIT_LEADERS,
            threshold=1.5,
            min_members=1,
            now=NOW,
        )

        assert [spike.symbol for spike in signal.spikes] == ["FPT"]
        assert signal.spikes[0].ratio == pytest.approx(1.5)


class TestCoverage:
    """How much of the scope the answer actually covers, and what that is called."""

    def _cohort_market(
        self,
        members: int,
        evaluable: int,
        sessions: tuple[date, ...],
    ) -> tuple[Session, list[str]]:
        session = open_session()
        symbols = [f"C{index:02d}" for index in range(members)]
        seat_cohort(session, symbols)
        list_on(session, symbols)
        for index, symbol in enumerate(symbols):
            if index < evaluable:
                write_sessions(session, symbol, {day: 1_000_000 for day in sessions})
            else:
                # Everything but the session being asked about: enough to keep
                # the Trading Days themselves in the store, not enough to be
                # evaluated on the newest one.
                write_sessions(
                    session, symbol, {day: 1_000_000 for day in sessions[:-1]}
                )
        return session, symbols

    @pytest.mark.parametrize(
        "evaluable,state",
        [
            (50, CoverageState.READY),
            (45, CoverageState.PARTIAL),
            (44, CoverageState.INSUFFICIENT_DATA),
        ],
    )
    def test_profit_leaders_coverage(self, evaluable: int, state: CoverageState):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        session, _ = self._cohort_market(50, evaluable, sessions)

        signal = volume_spike_signal(
            session, scope=SignalScope.PROFIT_LEADERS, now=NOW
        )

        assert signal.coverage.state is state
        assert signal.coverage.total == 50
        # Reported even when the answer is refused: forty-four evaluable
        # companies and a cohort nothing is known about are different states,
        # and "0 of 50" would describe the second.
        assert signal.coverage.evaluated == evaluable

    def test_an_answer_it_refuses_to_serve_still_names_what_it_could_not_see(self):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        session, _ = self._cohort_market(50, 44, sessions)

        signal = volume_spike_signal(
            session, scope=SignalScope.PROFIT_LEADERS, now=NOW
        )

        assert signal.trading_day is None
        assert signal.spikes == ()
        assert len(signal.unevaluable) == 6
        assert all(
            SignalIssue.MISSING_TARGET_SESSION in reading.issues
            for reading in signal.unevaluable
        )

    @pytest.mark.parametrize(
        "evaluable,state",
        [
            (100, CoverageState.READY),
            (90, CoverageState.PARTIAL),
            (89, CoverageState.INSUFFICIENT_DATA),
        ],
    )
    def test_universe_coverage(self, evaluable: int, state: CoverageState):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        session, cohort = self._cohort_market(50, 50, sessions)
        declared = [f"E{index:02d}" for index in range(50)]
        list_on(session, declared)
        for index, symbol in enumerate(declared):
            # The cohort half is already whole, so the declared half carries the
            # shortfall: fifty plus this many is the Universe's evaluated count.
            days = sessions if index < evaluable - 50 else sessions[:-1]
            write_sessions(session, symbol, {day: 1_000_000 for day in days})

        signal = volume_spike_signal(
            session,
            scope=SignalScope.UNIVERSE,
            universe=Universe(explicit=tuple(declared), cohort=tuple(cohort)),
            now=NOW,
        )

        assert signal.coverage.total == 100
        assert signal.coverage.state is state

    def test_an_exchange_filter_narrows_the_denominator(self):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        session = open_session()
        hose = [f"H{index:02d}" for index in range(10)]
        hnx = [f"N{index:02d}" for index in range(10)]
        list_on(session, hose, Exchange.HOSE)
        list_on(session, hnx, Exchange.HNX)
        seat_cohort(session, hose + hnx)
        steady_market(session, hose + hnx, sessions)

        signal = volume_spike_signal(
            session,
            scope=SignalScope.UNIVERSE,
            universe=Universe(explicit=tuple(hose + hnx)),
            exchange=Exchange.HNX,
            min_members=1,
            now=NOW,
        )

        assert signal.coverage.total == 10
        assert signal.coverage.evaluated == 10
        assert {reading.symbol for reading in signal.readings} == set(hnx)

    def test_the_profit_leaders_scope_carries_its_cohort_version(self):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        session, _ = self._cohort_market(50, 50, sessions)

        signal = volume_spike_signal(
            session, scope=SignalScope.PROFIT_LEADERS, now=NOW
        )

        assert signal.cohort_version is not None
        assert signal.cohort_version.reporting_period == date(2026, 3, 31)

    def test_the_universe_scope_carries_no_cohort_version(self):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        session, cohort = self._cohort_market(50, 50, sessions)

        signal = volume_spike_signal(
            session,
            scope=SignalScope.UNIVERSE,
            universe=Universe(explicit=(), cohort=tuple(cohort)),
            now=NOW,
        )

        assert signal.cohort_version is None

    def test_no_ranking_at_all_is_said_apart_from_a_warming_one(self):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        session = open_session()
        steady_market(session, ["FPT"], sessions)

        signal = volume_spike_signal(
            session, scope=SignalScope.PROFIT_LEADERS, now=NOW
        )

        assert signal.coverage.state is CoverageState.INSUFFICIENT_DATA
        assert signal.issues == (SignalIssue.RANKING_UNAVAILABLE,)
        assert signal.trading_day is None

    def test_a_cohort_no_session_can_evaluate_is_warming(self):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        session, _ = self._cohort_market(50, 0, sessions)

        signal = volume_spike_signal(
            session, scope=SignalScope.PROFIT_LEADERS, now=NOW
        )

        assert signal.coverage.state is CoverageState.INSUFFICIENT_DATA
        assert signal.issues == (SignalIssue.COHORT_WARMING,)


class TestFreshnessAndHistory:
    """When the answer is from, which is a separate question from how complete."""

    def _market(
        self,
        sessions: tuple[date, ...],
        evaluable: int = 50,
        evaluable_on_newest: bool = True,
    ):
        """Fifty seated companies, of which ``evaluable`` can be evaluated.

        ``evaluable_on_newest`` decides whether the cohort reaches the newest
        session at all. False leaves a newer market session in the store that no
        cohort member holds, which is what a lagging signal is made of — the
        symbol outside the cohort is there to keep that session in the store.
        """
        session = open_session()
        symbols = [f"C{index:02d}" for index in range(50)]
        seat_cohort(session, symbols)
        list_on(session, symbols)
        steady_market(session, ["VCB"], sessions)
        window = sessions if evaluable_on_newest else sessions[:-1]
        steady_market(session, symbols[:evaluable], window)
        steady_market(session, symbols[evaluable:], window[:-1])
        return session

    @pytest.mark.parametrize("evaluable,coverage", [(50, CoverageState.READY), (47, CoverageState.PARTIAL)])
    @pytest.mark.parametrize(
        "evaluable_on_newest,newest_session_age_days,freshness",
        [
            (True, 0, Freshness.FRESH),
            (False, 0, Freshness.LAGGING),
            (True, 30, Freshness.STALE),
        ],
    )
    def test_freshness_is_computed_apart_from_coverage(
        self,
        evaluable: int,
        coverage: CoverageState,
        evaluable_on_newest: bool,
        newest_session_age_days: int,
        freshness: Freshness,
    ):
        """All six combinations, because neither answer implies the other.

        A signal can be whole and a week stale, or fresh and three companies
        short. Collapsed into one status, whichever of the two the collapse
        dropped is the one the reader needed.
        """
        last = TODAY - timedelta(days=newest_session_age_days)
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 2, last=last)
        session = self._market(sessions, evaluable, evaluable_on_newest)

        signal = volume_spike_signal(
            session, scope=SignalScope.PROFIT_LEADERS, now=NOW
        )

        assert signal.freshness is freshness
        assert signal.coverage.state is coverage
        assert signal.coverage.evaluated == evaluable

    def test_a_lagging_signal_says_so_in_its_issues(self):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 2)
        session = self._market(evaluable_on_newest=False, sessions=sessions)

        signal = volume_spike_signal(
            session, scope=SignalScope.PROFIT_LEADERS, now=NOW
        )

        assert signal.trading_day == sessions[-2]
        assert SignalIssue.LAGGING_MARKET_DATA in signal.issues

    def test_a_stale_signal_says_so_in_its_issues(self):
        sessions = trading_calendar(
            BASELINE_TRADING_DAYS + 2, last=TODAY - timedelta(days=30)
        )
        session = self._market(evaluable_on_newest=True, sessions=sessions)

        signal = volume_spike_signal(
            session, scope=SignalScope.PROFIT_LEADERS, now=NOW
        )

        assert SignalIssue.STALE_MARKET_DATA in signal.issues

    def test_a_historical_query_reads_the_cohort_of_that_day(self):
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 5)
        session = open_session()
        older = [f"O{index:02d}" for index in range(3)]
        newer = [f"N{index:02d}" for index in range(3)]
        list_on(session, older + newer)
        steady_market(session, older + newer, sessions)

        handover = datetime.combine(sessions[-2], time.min, tzinfo=VN_TZ)
        seat_cohort(
            session,
            older,
            activated_at=datetime(2026, 1, 2, 3, 0, tzinfo=timezone.utc),
            state="superseded",
            superseded_at=handover,
        )
        seat_cohort(session, newer, activated_at=handover)

        past = volume_spike_signal(
            session,
            scope=SignalScope.PROFIT_LEADERS,
            trading_day=sessions[-4],
            min_members=3,
            now=NOW,
        )

        assert {reading.symbol for reading in past.readings} == set(older)
        assert past.trading_day == sessions[-4]


class TestCacheKey:
    """Every stored dependency changes the cache identity (docs/adr/0005)."""

    BASE = dict(
        scope=SignalScope.PROFIT_LEADERS,
        trading_day=TODAY,
        threshold=1.5,
        exchange=None,
        cohort_version_id=12,
        market_generation=NOW,
        corporate_action_generation=NOW,
    )

    @pytest.mark.parametrize(
        "field,value",
        [
            ("scope", SignalScope.UNIVERSE),
            ("trading_day", TODAY - timedelta(days=1)),
            ("threshold", 2.0),
            ("exchange", Exchange.HNX),
            ("cohort_version_id", 13),
            ("market_generation", NOW + timedelta(seconds=1)),
            ("corporate_action_generation", NOW + timedelta(seconds=2)),
        ],
    )
    def test_each_input_produces_a_different_key(self, field: str, value):
        changed = dict(self.BASE)
        changed[field] = value

        assert signal_cache_key(**self.BASE) != signal_cache_key(**changed)

    def test_the_same_inputs_produce_the_same_key(self):
        assert signal_cache_key(**self.BASE) == signal_cache_key(**dict(self.BASE))

    def test_an_action_write_advances_the_action_generation(self):
        session = open_session()
        assert corporate_action_generation(session) is None

        CorporateActionStore(session).save(
            CorporateActionEvent(
                symbol="FPT",
                event_code="ISS",
                title="Share Issue - Stock dividend ratio 10.0%",
                ex_date=TODAY,
                record_date=None,
                public_date=TODAY - timedelta(days=10),
                exercise_ratio=0.10,
                value_per_share=None,
            ),
            ProviderSource.VNSTOCK,
            NOW,
        )

        assert corporate_action_generation(session) == NOW
