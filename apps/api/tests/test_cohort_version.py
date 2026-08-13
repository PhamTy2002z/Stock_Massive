"""How the Profit Leaders Cohort changes without breaking what was already said.

The invariant every test here defends: the active version keeps serving unless
another version takes over, and that takeover is one transaction. A failed
census, a failed Warm-up or a market that has not filed yet all have to leave
the last good cohort exactly where it was.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.stocks.cohort import (
    BASELINE_TRADING_DAYS,
    CohortStore,
    active_cohort_symbols,
    cohort_symbols_on,
    cohort_version_active_on,
    evaluable_symbols,
    refresh_cohort,
)
from src.stocks.models import (
    CohortMember,
    CohortVersion,
    ListingRoster,
    ProfitRankingCensusRun,
    ProviderSnapshot,
)
from src.stocks.providers import (
    Capability,
    Exchange,
    ProviderSource,
    SnapshotStore,
)
from src.stocks.providers.contracts import FundamentalSnapshot, SnapshotMetadata
from src.stocks.providers.normalize import VN_TZ
from src.stocks.universe import forget_cohort_cache

# Both quarters have closed and both have been observed: a reporting period later
# than the moment it was read is refused by the snapshot contract, which is right —
# nobody observes next quarter's filing.
PERIOD = date(2026, 3, 31)
NEWER_PERIOD = date(2026, 6, 30)
TODAY = date(2026, 8, 13)
NOW = datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc)

COHORT_SIZE = 5
MIN_MEMBERS = 4


@pytest.fixture(autouse=True)
def clear_universe_cache():
    forget_cohort_cache()
    yield
    forget_cohort_cache()


def open_session() -> Session:
    engine = create_engine("sqlite://")
    for table in (
        ProviderSnapshot.__table__,
        ListingRoster.__table__,
        ProfitRankingCensusRun.__table__,
        CohortVersion.__table__,
        CohortMember.__table__,
    ):
        table.create(engine)
    session = Session(engine)
    session.add(
        ProfitRankingCensusRun(
            started_at=NOW,
            finished_at=NOW,
            status="complete",
            target_period=PERIOD,
            eligible_symbols=COHORT_SIZE,
            covered_symbols=COHORT_SIZE,
        )
    )
    session.flush()
    return session


def market_profits(
    session: Session,
    profits: dict[str, float],
    period: date = PERIOD,
    exchange: Exchange = Exchange.HOSE,
    listed: bool = True,
) -> None:
    """Put these companies on a board and give them a reported profit."""
    store = SnapshotStore(session, redis=None)
    for symbol, profit in profits.items():
        row = session.get(ListingRoster, symbol)
        if row is None:
            session.add(
                ListingRoster(
                    symbol=symbol,
                    exchange=exchange.value,
                    is_listed=listed,
                    company_name=None,
                    source=ProviderSource.VNSTOCK.value,
                    observed_at=NOW,
                )
            )
        else:
            row.exchange = exchange.value
            row.is_listed = listed
        store.save(
            Capability.FUNDAMENTAL,
            FundamentalSnapshot(
                symbol=symbol,
                metadata=SnapshotMetadata(
                    source=ProviderSource.VNSTOCK,
                    effective_at=datetime.combine(
                        period, datetime.min.time(), tzinfo=VN_TZ
                    ),
                    observed_at=NOW,
                ),
                period_end=period,
                trailing_12_month_net_income_vnd=profit,
            ),
        )
    session.flush()


def ranked_market(session: Session, count: int = COHORT_SIZE, **kwargs) -> list[str]:
    """A market of ``count`` companies, most profitable first by name."""
    symbols = [f"S{index:02d}" for index in range(count)]
    market_profits(
        session,
        {symbol: (count - index) * 1_000 for index, symbol in enumerate(symbols)},
        **kwargs,
    )
    return symbols


def give_history(
    session: Session,
    symbols,
    sessions: int = BASELINE_TRADING_DAYS,
    day: date = TODAY,
) -> None:
    """Store ``sessions`` consecutive market days ending on ``day``.

    Written directly rather than through a Warm-up: what is being tested is what
    counts as evaluable, not how the sessions got there.
    """
    for offset in range(sessions):
        stamp = datetime.combine(
            day - timedelta(days=offset), datetime.min.time(), tzinfo=VN_TZ
        )
        for symbol in symbols:
            session.add(
                ProviderSnapshot(
                    capability=Capability.MARKET.value,
                    symbol=symbol,
                    source=ProviderSource.FIINQUANT.value,
                    effective_at=stamp,
                    observed_at=stamp,
                    schema_version=1,
                    payload={},
                )
            )
    session.flush()


def refresh(session: Session, warm=None, **overrides):
    recorded: list[tuple[str, ...]] = []

    def record(symbols):
        recorded.append(tuple(symbols))
        return None

    outcome = refresh_cohort(
        session,
        census_run_id=1,
        warm=warm if warm is not None else record,
        cohort_size=overrides.pop("cohort_size", COHORT_SIZE),
        min_members=overrides.pop("min_members", MIN_MEMBERS),
        now=lambda: overrides.pop("now", NOW),
        **overrides,
    )
    return outcome, recorded


class TestStaging:
    """A ranking becomes a candidate, and never edits what is already active."""

    def test_a_new_ranking_stages_a_candidate_with_its_members_in_order(self):
        session = open_session()
        symbols = ranked_market(session)

        outcome, _ = refresh(session)

        version = CohortStore(session).newest_candidate()
        assert version is not None
        assert outcome.staged_version_id == version.id
        assert version.state == "candidate"
        assert CohortStore(session).symbols(version.id) == tuple(symbols)

    def test_staging_does_not_touch_the_active_version_or_its_members(self):
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols)
        refresh(session)  # stages and activates
        active = CohortStore(session).active()
        assert active is not None
        before = CohortStore(session).symbols(active.id)

        # A newcomer outearns everyone at a newer period the whole market filed.
        market_profits(session, {symbol: 500 for symbol in symbols}, period=NEWER_PERIOD)
        market_profits(session, {"NEW": 90_000}, period=NEWER_PERIOD)
        outcome, _ = refresh(session)

        assert outcome.staged_version_id is not None
        assert outcome.staged_version_id != active.id
        assert CohortStore(session).symbols(active.id) == before

    def test_an_unchanged_ranking_stages_nothing(self):
        """A weekly census over an unchanged quarter must not churn versions."""
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols)
        refresh(session)

        outcome, warmed = refresh(session)

        assert outcome.staged_version_id is None
        assert "already matches" in (outcome.reason or "")
        assert warmed == []

    def test_fewer_than_the_cohort_size_leaves_the_active_version_untouched(self):
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols)
        refresh(session)
        active = CohortStore(session).active()

        outcome, _ = refresh(session, cohort_size=COHORT_SIZE + 3)

        assert outcome.staged_version_id is None
        assert "eligible companies" in (outcome.reason or "")
        assert CohortStore(session).active().id == active.id

    def test_no_rankable_period_stages_nothing(self):
        session = open_session()

        outcome, _ = refresh(session)

        assert outcome.reason == "no rankable reporting period yet"
        assert outcome.staged_version_id is None
        assert CohortStore(session).active() is None


class TestActivation:
    """Taking over is atomic, and it waits for the members to be evaluable."""

    def test_below_the_floor_it_stays_a_candidate(self):
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols[:2])  # only 2 of 5 evaluable

        outcome, _ = refresh(session)

        assert outcome.activated_version_id is None
        assert outcome.evaluable_members == 2
        assert CohortStore(session).active() is None
        assert CohortStore(session).newest_candidate().state == "candidate"

    def test_at_the_floor_it_activates(self):
        """Forty-five of fifty is deliberate: one broken symbol cannot block a quarter."""
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols[:MIN_MEMBERS])

        outcome, _ = refresh(session)

        active = CohortStore(session).active()
        assert active is not None
        assert outcome.activated_version_id == active.id
        assert active.coverage_at_activation == MIN_MEMBERS
        assert active.activated_at is not None

    def test_activation_leaves_exactly_one_active_version(self):
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols)
        refresh(session)
        first = CohortStore(session).active()

        market_profits(session, {symbol: 500 for symbol in symbols}, period=NEWER_PERIOD)
        market_profits(session, {"NEW": 90_000}, period=NEWER_PERIOD)
        give_history(session, ["NEW"])
        outcome, _ = refresh(session)

        active = session.execute(
            select(CohortVersion).where(CohortVersion.state == "active")
        ).scalars().all()
        assert len(active) == 1
        assert active[0].id == outcome.activated_version_id
        superseded = session.get(CohortVersion, first.id)
        assert superseded.state == "superseded"
        assert superseded.superseded_at is not None
        assert outcome.superseded_version_id == first.id

    def test_the_database_refuses_a_second_active_version(self):
        """The guarantee is in the schema, not only in the activation code."""
        session = open_session()
        for _ in range(2):
            session.add(
                CohortVersion(
                    reporting_period=PERIOD,
                    census_run_id=1,
                    state="active",
                    created_at=NOW,
                    activated_at=NOW,
                )
            )

        with pytest.raises(IntegrityError):
            session.flush()

    def test_many_superseded_versions_are_allowed_alongside(self):
        """The uniqueness is on 'active' alone; history has to be able to pile up."""
        session = open_session()
        for _ in range(3):
            session.add(
                CohortVersion(
                    reporting_period=PERIOD,
                    census_run_id=1,
                    state="superseded",
                    created_at=NOW,
                    superseded_at=NOW,
                )
            )
        session.flush()

        rows = session.execute(select(CohortVersion)).scalars().all()
        assert len(rows) == 3


class TestEvaluability:
    """A member with a gap in the window is not evaluable, and says so."""

    def test_a_full_baseline_is_evaluable(self):
        session = open_session()
        give_history(session, ["AAA"])

        assert evaluable_symbols(session, ["AAA"]) == ("AAA",)

    def test_one_session_short_is_not_evaluable(self):
        session = open_session()
        give_history(session, ["AAA"], sessions=BASELINE_TRADING_DAYS - 1)

        assert evaluable_symbols(session, ["AAA"]) == ()

    def test_a_gap_inside_the_window_is_not_evaluable(self):
        """The twenty-one days are the same twenty-one for everyone.

        A symbol allowed to reach further back would average a different stretch
        of market and be presented as comparable with the symbol beside it.
        """
        session = open_session()
        give_history(session, ["AAA", "BBB"])
        # A session in the middle of BBB's window, not at either end: the count is
        # short by one either way, and the middle is the case a "reaches further
        # back" bug would sail through.
        gap = session.execute(
            select(ProviderSnapshot)
            .where(ProviderSnapshot.symbol == "BBB")
            .order_by(ProviderSnapshot.effective_at.desc())
            .offset(5)
            .limit(1)
        ).scalar_one()
        session.delete(gap)
        session.flush()

        assert evaluable_symbols(session, ["AAA", "BBB"]) == ("AAA",)

    def test_a_store_with_no_sessions_evaluates_nothing(self):
        session = open_session()

        assert evaluable_symbols(session, ["AAA"]) == ()


class TestWarmUp:
    """Only the members that need it, and a failure costs nothing but the wait."""

    def test_only_members_without_a_baseline_are_warmed(self):
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols[:2])

        _, warmed = refresh(session)

        assert warmed == [tuple(symbols[2:])]

    def test_a_failing_warm_up_leaves_the_candidate_waiting(self):
        session = open_session()
        ranked_market(session)

        def explode(_symbols):
            raise RuntimeError("FiinQuant is down")

        outcome, _ = refresh(session, warm=explode)

        assert outcome.activated_version_id is None
        assert outcome.staged_version_id is not None
        assert CohortStore(session).active() is None


class TestDelisting:
    """A member leaving the exchange replaces itself; it does not empty the cohort."""

    def test_a_delisted_member_stages_a_replacement_and_keeps_serving(self):
        session = open_session()
        symbols = ranked_market(session, count=COHORT_SIZE + 1)
        seated, spare = symbols[:COHORT_SIZE], symbols[COHORT_SIZE]
        give_history(session, seated)
        refresh(session)
        active = CohortStore(session).active()
        assert CohortStore(session).symbols(active.id) == tuple(seated)

        gone = seated[-1]
        session.get(ListingRoster, gone).is_listed = False
        session.flush()

        # Held to the full cohort here so the replacement has to be warmed before
        # it can take over: what is being tested is that the delisting alone does
        # not unseat the version already serving.
        outcome, warmed = refresh(session, min_members=COHORT_SIZE)

        assert outcome.staged_version_id is not None
        candidate = CohortStore(session).newest_candidate()
        assert gone not in CohortStore(session).symbols(candidate.id)
        assert spare in CohortStore(session).symbols(candidate.id)
        # The version that was serving is still serving.
        assert CohortStore(session).active().id == active.id
        assert warmed == [(spare,)]

    def test_the_replacement_takes_over_once_it_is_evaluable(self):
        session = open_session()
        symbols = ranked_market(session, count=COHORT_SIZE + 1)
        seated, spare = symbols[:COHORT_SIZE], symbols[COHORT_SIZE]
        give_history(session, seated)
        refresh(session)
        first = CohortStore(session).active()

        session.get(ListingRoster, seated[-1]).is_listed = False
        session.flush()
        give_history(session, [spare])
        refresh(session)  # stages the replacement
        outcome, _ = refresh(session)  # and promotes it

        active = CohortStore(session).active()
        assert active.id != first.id
        assert spare in CohortStore(session).symbols(active.id)


class TestHistoricalResolution:
    """A signal served in August keeps August's cohort."""

    def test_a_past_day_resolves_to_the_version_active_then(self):
        session = open_session()
        old = CohortVersion(
            reporting_period=PERIOD,
            census_run_id=1,
            state="superseded",
            created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            activated_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
            superseded_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        new = CohortVersion(
            reporting_period=NEWER_PERIOD,
            census_run_id=1,
            state="active",
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            activated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        session.add_all([old, new])
        session.flush()
        session.add(
            CohortMember(
                cohort_version_id=old.id,
                symbol="OLD",
                rank=1,
                net_income_vnd=1,
                exchange="HOSE",
            )
        )
        session.add(
            CohortMember(
                cohort_version_id=new.id,
                symbol="NEW",
                rank=1,
                net_income_vnd=1,
                exchange="HOSE",
            )
        )
        session.flush()

        assert cohort_version_active_on(session, date(2026, 6, 15)).id == old.id
        assert cohort_symbols_on(session, date(2026, 6, 15)) == ("OLD",)
        assert cohort_version_active_on(session, date(2026, 8, 10)).id == new.id
        assert cohort_symbols_on(session, date(2026, 8, 10)) == ("NEW",)
        assert active_cohort_symbols(session) == ("NEW",)

    def test_a_day_before_any_activation_resolves_to_nothing(self):
        session = open_session()
        session.add(
            CohortVersion(
                reporting_period=PERIOD,
                census_run_id=1,
                state="active",
                created_at=NOW,
                activated_at=NOW,
            )
        )
        session.flush()

        assert cohort_version_active_on(session, date(2026, 1, 1)) is None
        assert cohort_symbols_on(session, date(2026, 1, 1)) == ()

    def test_a_candidate_is_never_the_answer_for_any_day(self):
        """A candidate's members have no baseline yet; it has served nothing."""
        session = open_session()
        session.add(
            CohortVersion(
                reporting_period=PERIOD,
                census_run_id=1,
                state="candidate",
                created_at=NOW,
            )
        )
        session.flush()

        assert cohort_version_active_on(session, TODAY) is None
        assert active_cohort_symbols(session) == ()


class TestUniverseCap:
    """The declared half is a commitment; the cohort is what gets refused."""

    def test_an_activation_that_would_breach_the_cap_is_refused(self):
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols)

        outcome, warmed = refresh(
            session,
            universe_cap=COHORT_SIZE + 1,
            explicit_symbols=tuple(f"E{index:02d}" for index in range(2)),
        )

        assert outcome.activated_version_id is None
        assert "over the cap" in (outcome.reason or "")
        assert CohortStore(session).active() is None
        # Refused before the allowance is spent warming symbols that cannot be seated.
        assert warmed == []

    def test_a_symbol_in_both_halves_does_not_count_twice(self):
        """Otherwise an activation is refused over a place nothing occupies."""
        session = open_session()
        symbols = ranked_market(session)
        give_history(session, symbols)

        outcome, _ = refresh(
            session,
            universe_cap=COHORT_SIZE,
            explicit_symbols=(symbols[0],),
        )

        assert outcome.activated_version_id is not None
