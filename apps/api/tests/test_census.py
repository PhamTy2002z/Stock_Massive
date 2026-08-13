"""What the market-wide profit census counts, and what it refuses to count.

Two questions run through all of this and they are deliberately not the same
one. Coverage asks "do we know this company's profit at this period" and counts
a company that lost money. Eligibility asks "can this company be ranked" and
does not. A test suite that conflated them would pass while the system crowned
whoever filed first.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.stocks.census import (
    Census,
    CensusUnavailable,
    RANKABLE_PERIOD_COVERAGE,
    newest_rankable_period,
    period_coverage,
    rank_profit_leaders,
)
from src.stocks.listing_roster import ListingRosterStore
from src.stocks.models import (
    ListingRoster,
    ProfitRankingCensusRun,
    ProviderSnapshot,
)
from src.stocks.providers import (
    Capability,
    Exchange,
    ListingEntry,
    ProviderSource,
    RANKED_EXCHANGES,
    SnapshotStore,
)
from src.stocks.providers.contracts import FundamentalSnapshot, SnapshotMetadata
from src.stocks.providers.normalize import VN_TZ

PERIOD = date(2026, 6, 30)
EARLIER_PERIOD = date(2026, 3, 31)
NOW = datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc)


def open_session() -> Session:
    engine = create_engine("sqlite://")
    for table in (
        ProviderSnapshot.__table__,
        ListingRoster.__table__,
        ProfitRankingCensusRun.__table__,
    ):
        table.create(engine)
    return Session(engine)


def list_symbols(
    session: Session,
    symbols: dict[str, Exchange],
    listed: bool = True,
) -> None:
    for symbol, exchange in symbols.items():
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
    session.flush()


def fundamental(symbol: str, profit: float | None, period: date = PERIOD):
    return FundamentalSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=datetime.combine(period, datetime.min.time(), tzinfo=VN_TZ),
            observed_at=NOW,
        ),
        period_end=period,
        trailing_12_month_net_income_vnd=profit,
    )


def record_profit(
    session: Session,
    symbol: str,
    profit: float | None,
    period: date = PERIOD,
) -> None:
    SnapshotStore(session, redis=None).save(
        Capability.FUNDAMENTAL, fundamental(symbol, profit, period)
    )


class FakeFundamentalProvider:
    """Answer with whatever the test decided this company reported."""

    source = ProviderSource.VNSTOCK

    def __init__(self, profits: dict[str, float | None], period: date = PERIOD):
        self.profits = profits
        self.period = period
        self.asked: list[str] = []

    def fetch_fundamentals(self, symbols):
        self.asked.extend(symbols)
        return tuple(
            fundamental(symbol, self.profits[symbol], self.period)
            for symbol in symbols
            if symbol in self.profits
        )


class RefusingFundamentalProvider:
    """Stand in for an account the provider has cut off."""

    source = ProviderSource.VNSTOCK

    def __init__(self):
        self.asked: list[str] = []

    def fetch_fundamentals(self, symbols):
        from src.core.vnstock_client import VnstockUnavailable

        self.asked.extend(symbols)
        raise VnstockUnavailable("quota exhausted")


class FakeRosterProvider:
    source = ProviderSource.VNSTOCK

    def __init__(self, entries):
        self.entries = entries

    def fetch_listing_roster(self):
        return self.entries


def census(session: Session, provider, roster=None, **overrides) -> Census:
    return Census(
        session=session,
        store=SnapshotStore(session, redis=None),
        fundamental=provider,
        roster=roster,
        now=lambda: NOW,
        sleep=lambda _: None,
        **overrides,
    )


class TestCoverage:
    """A period is rankable or it is not, and the threshold is exact."""

    def test_coverage_below_the_threshold_leaves_the_period_unrankable(self):
        session = open_session()
        list_symbols(session, {f"S{index:02d}": Exchange.HOSE for index in range(20)})
        for index in range(18):  # 18/20 = 90%
            record_profit(session, f"S{index:02d}", 1_000 + index)

        coverage = period_coverage(
            session, PERIOD, ListingRosterStore(session).listed_symbols(RANKED_EXCHANGES)
        )

        assert coverage.covered == 18
        assert coverage.eligible == 20
        assert coverage.ratio == pytest.approx(0.9)
        assert not coverage.rankable

    def test_coverage_exactly_at_the_threshold_makes_the_period_rankable(self):
        """The boundary is inclusive, and it is the one that decides everything."""
        session = open_session()
        list_symbols(session, {f"S{index:02d}": Exchange.HOSE for index in range(20)})
        for index in range(19):  # 19/20 = 95%
            record_profit(session, f"S{index:02d}", 1_000 + index)

        coverage = period_coverage(
            session, PERIOD, ListingRosterStore(session).listed_symbols(RANKED_EXCHANGES)
        )

        assert coverage.ratio == pytest.approx(RANKABLE_PERIOD_COVERAGE)
        assert coverage.rankable

    def test_upcom_and_delisted_symbols_leave_both_counts_alone(self):
        """They are in neither the numerator nor the denominator.

        In the denominator, UPCOM would hold every period below the threshold
        forever. In the numerator, a delisted company would prop up a period the
        listed market has not reported.
        """
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE, "BBB": Exchange.HNX})
        list_symbols(session, {"CCC": Exchange.UPCOM})
        list_symbols(session, {"DDD": Exchange.HOSE}, listed=False)
        for symbol in ("AAA", "BBB", "CCC", "DDD"):
            record_profit(session, symbol, 5_000)

        coverage = period_coverage(
            session, PERIOD, ListingRosterStore(session).listed_symbols(RANKED_EXCHANGES)
        )

        assert coverage.eligible == 2
        assert coverage.covered == 2

    def test_a_company_reporting_no_usable_profit_is_not_covered(self):
        """A filing the adapter could not read a trailing year out of is a gap.

        It is not the same as a company with no filing — that one still costs two
        requests to ask again — but for coverage it counts the same way: we do not
        know this company's profit at this period.
        """
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE, "BBB": Exchange.HOSE})
        record_profit(session, "AAA", 1_000)
        record_profit(session, "BBB", None)

        coverage = period_coverage(
            session, PERIOD, ListingRosterStore(session).listed_symbols(RANKED_EXCHANGES)
        )

        assert coverage.covered == 1
        assert coverage.eligible == 2

    def test_an_empty_market_never_clears_the_threshold(self):
        """Nothing divided by nothing is not full coverage."""
        session = open_session()

        coverage = period_coverage(session, PERIOD, ())

        assert coverage.ratio == 0.0
        assert not coverage.rankable

    def test_the_newest_rankable_period_is_not_the_newest_period(self):
        """A quarter half the market has not filed leaves the ranking where it was."""
        session = open_session()
        list_symbols(session, {f"S{index:02d}": Exchange.HOSE for index in range(20)})
        for index in range(20):
            record_profit(session, f"S{index:02d}", 1_000 + index, EARLIER_PERIOD)
        for index in range(3):
            record_profit(session, f"S{index:02d}", 2_000 + index, PERIOD)

        eligible = ListingRosterStore(session).listed_symbols(RANKED_EXCHANGES)
        coverage = newest_rankable_period(session, eligible)

        assert coverage is not None
        assert coverage.period == EARLIER_PERIOD


class TestRanking:
    """Who gets a seat, in what order, and when nobody does."""

    def test_null_and_non_positive_profit_are_not_eligible(self):
        session = open_session()
        list_symbols(
            session,
            {
                "AAA": Exchange.HOSE,
                "LOSS": Exchange.HOSE,
                "FLAT": Exchange.HNX,
                "NONE": Exchange.HNX,
            },
        )
        record_profit(session, "AAA", 9_000)
        record_profit(session, "LOSS", -5_000)
        record_profit(session, "FLAT", 0)
        record_profit(session, "NONE", None)

        ranking = rank_profit_leaders(session, PERIOD, size=50)

        assert [company.symbol for company in ranking] == ["AAA"]

    def test_upcom_and_delisted_companies_are_not_eligible(self):
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE})
        list_symbols(session, {"BIG": Exchange.UPCOM})
        list_symbols(session, {"GONE": Exchange.HOSE}, listed=False)
        record_profit(session, "AAA", 1_000)
        record_profit(session, "BIG", 900_000)
        record_profit(session, "GONE", 800_000)

        ranking = rank_profit_leaders(session, PERIOD, size=50)

        assert [company.symbol for company in ranking] == ["AAA"]

    def test_a_tie_at_the_last_seat_resolves_by_symbol(self):
        """Otherwise the fiftieth seat depends on row order.

        Two runs over identical data would seat different companies, and the
        cohort would appear to change for no reason anyone could point at.
        """
        session = open_session()
        list_symbols(session, {f"S{index:02d}": Exchange.HOSE for index in range(4)})
        record_profit(session, "S00", 5_000)
        record_profit(session, "S01", 4_000)
        record_profit(session, "S02", 3_000)
        record_profit(session, "S03", 3_000)

        ranking = rank_profit_leaders(session, PERIOD, size=3)

        assert [company.symbol for company in ranking] == ["S00", "S01", "S02"]
        assert [company.rank for company in ranking] == [1, 2, 3]

    def test_a_company_reporting_an_older_period_is_not_ranked_at_this_one(self):
        """Ranking at a common period is the whole point of the threshold."""
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE, "LATE": Exchange.HOSE})
        record_profit(session, "AAA", 1_000, PERIOD)
        record_profit(session, "LATE", 900_000, EARLIER_PERIOD)

        ranking = rank_profit_leaders(session, PERIOD, size=50)

        assert [company.symbol for company in ranking] == ["AAA"]

    def test_ranking_is_by_profit_descending(self):
        session = open_session()
        list_symbols(session, {f"S{index:02d}": Exchange.HOSE for index in range(3)})
        record_profit(session, "S00", 1_000)
        record_profit(session, "S01", 3_000)
        record_profit(session, "S02", 2_000)

        ranking = rank_profit_leaders(session, PERIOD, size=50)

        assert [company.symbol for company in ranking] == ["S01", "S02", "S00"]


class TestReadingTheMarket:
    """What a run asks the provider for, and what it writes down."""

    def test_it_reads_every_eligible_symbol_and_records_coverage(self):
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE, "BBB": Exchange.HNX})
        provider = FakeFundamentalProvider({"AAA": 2_000, "BBB": 1_000})

        outcome = census(session, provider).run(refresh_roster=False)

        assert outcome.status == "complete"
        assert sorted(provider.asked) == ["AAA", "BBB"]
        assert outcome.target_period == PERIOD
        assert outcome.eligible_symbols == 2
        assert outcome.covered_symbols == 2
        assert outcome.rankable

    def test_it_writes_fundamental_snapshots_and_no_market_snapshots(self):
        """A censused company outside the Universe gets its filing stored, only.

        ADR-0004 keeps the filing as a raw observation with its own source and
        effective time. What it must not do is start collecting sessions for 1,600
        companies the system never promised to serve.
        """
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE})

        census(session, FakeFundamentalProvider({"AAA": 2_000})).run(
            refresh_roster=False
        )

        capabilities = session.execute(
            select(ProviderSnapshot.capability, ProviderSnapshot.symbol)
        ).all()
        assert capabilities == [(Capability.FUNDAMENTAL.value, "AAA")]

    def test_it_skips_symbols_already_covered_at_the_target_period(self):
        """This is what resuming means: never spend two requests twice.

        Resuming by position would re-read the market from the top as soon as the
        roster changed length, and the roster changes every week.
        """
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE, "BBB": Exchange.HOSE})
        record_profit(session, "AAA", 2_000)
        provider = FakeFundamentalProvider({"BBB": 1_000})

        census(session, provider).run(refresh_roster=False)

        assert provider.asked == ["BBB"]

    def test_a_symbol_the_provider_has_nothing_for_costs_only_itself(self):
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE, "SILENT": Exchange.HOSE})
        provider = FakeFundamentalProvider({"AAA": 2_000})

        outcome = census(session, provider).run(refresh_roster=False)

        assert outcome.status == "complete"
        assert sorted(provider.asked) == ["AAA", "SILENT"]
        assert outcome.covered_symbols == 1

    def test_an_exhausted_quota_stops_the_run_rather_than_the_symbol(self):
        """It would refuse the next 1,500 symbols too, at two requests each."""
        session = open_session()
        list_symbols(session, {f"S{index:02d}": Exchange.HOSE for index in range(5)})
        provider = RefusingFundamentalProvider()

        outcome = census(session, provider).run(refresh_roster=False)

        assert outcome.status == "failed"
        assert "quota" in (outcome.error or "")
        assert len(provider.asked) == 1

    def test_a_failed_run_is_recorded_rather_than_lost(self):
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE})

        census(session, RefusingFundamentalProvider()).run(refresh_roster=False)

        run = session.execute(select(ProfitRankingCensusRun)).scalar_one()
        assert run.status == "failed"
        assert run.finished_at is not None
        assert run.last_error is not None

    def test_a_market_with_no_listed_equities_completes_without_reading(self):
        """A fresh environment reads exactly like this, and it is not a failure."""
        session = open_session()
        provider = FakeFundamentalProvider({})

        outcome = census(session, provider).run(refresh_roster=False)

        assert outcome.status == "complete"
        assert outcome.eligible_symbols == 0
        assert not outcome.rankable
        assert provider.asked == []

    def test_refreshing_the_roster_seats_newly_listed_companies(self):
        session = open_session()
        roster = FakeRosterProvider(
            (
                ListingEntry(symbol="AAA", exchange=Exchange.HOSE, is_listed=True),
                ListingEntry(symbol="BBB", exchange=Exchange.HNX, is_listed=True),
            )
        )
        provider = FakeFundamentalProvider({"AAA": 2_000, "BBB": 1_000})

        outcome = census(session, provider, roster=roster).run(refresh_roster=True)

        assert outcome.roster is not None
        assert outcome.roster.newly_listed == ("AAA", "BBB")
        assert outcome.eligible_symbols == 2

    def test_the_retry_shape_of_the_run_leaves_the_roster_alone(self):
        """The daily pass must not be able to delist anyone.

        A provider hiccup on a run whose only job was to pick up two late filings
        would otherwise mark cohort members as gone.
        """
        session = open_session()
        list_symbols(session, {"AAA": Exchange.HOSE})
        roster = FakeRosterProvider(())

        outcome = census(
            session, FakeFundamentalProvider({"AAA": 1_000}), roster=roster
        ).run(refresh_roster=False)

        assert outcome.status == "complete"
        assert outcome.roster is None
        assert ListingRosterStore(session).listed_symbols(RANKED_EXCHANGES) == ("AAA",)


class TestRosterRefresh:
    """The register is how a delisting becomes visible at all."""

    def test_a_symbol_missing_from_a_refresh_is_delisted_not_deleted(self):
        session = open_session()
        store = ListingRosterStore(session)
        store.refresh(
            (
                ListingEntry(symbol="AAA", exchange=Exchange.HOSE, is_listed=True),
                ListingEntry(symbol="GONE", exchange=Exchange.HOSE, is_listed=True),
            ),
            source=ProviderSource.VNSTOCK,
            observed_at=NOW,
        )

        refresh = store.refresh(
            (ListingEntry(symbol="AAA", exchange=Exchange.HOSE, is_listed=True),),
            source=ProviderSource.VNSTOCK,
            observed_at=NOW,
        )

        assert refresh.newly_delisted == ("GONE",)
        assert store.listed_symbols(RANKED_EXCHANGES) == ("AAA",)
        assert store.delisted_among(["AAA", "GONE"]) == ("GONE",)

    def test_a_delisting_is_reported_once_rather_than_every_week(self):
        session = open_session()
        store = ListingRosterStore(session)
        entries = (ListingEntry(symbol="AAA", exchange=Exchange.HOSE, is_listed=True),)
        store.refresh(
            entries + (ListingEntry(symbol="GONE", exchange=Exchange.HOSE, is_listed=True),),
            source=ProviderSource.VNSTOCK,
        )
        store.refresh(entries, source=ProviderSource.VNSTOCK)

        again = store.refresh(entries, source=ProviderSource.VNSTOCK)

        assert again.newly_delisted == ()

    def test_an_empty_refresh_is_refused(self):
        """It looks exactly like a closed exchange, and it would delist everyone."""
        session = open_session()
        store = ListingRosterStore(session)

        with pytest.raises(ValueError, match="whole market"):
            store.refresh((), source=ProviderSource.VNSTOCK)

    def test_a_relisted_company_is_reported_as_newly_listed(self):
        session = open_session()
        store = ListingRosterStore(session)
        listed = (ListingEntry(symbol="AAA", exchange=Exchange.HOSE, is_listed=True),)
        other = (ListingEntry(symbol="BBB", exchange=Exchange.HOSE, is_listed=True),)
        store.refresh(listed + other, source=ProviderSource.VNSTOCK)
        store.refresh(other, source=ProviderSource.VNSTOCK)

        back = store.refresh(listed + other, source=ProviderSource.VNSTOCK)

        assert back.newly_listed == ("AAA",)
        assert store.exchange_of("AAA") is Exchange.HOSE


class TestExchangeSpelling:
    """One board, one spelling, decided at the boundary."""

    def test_hsx_is_read_as_hose(self):
        """The alias is in use elsewhere in this codebase.

        Left as free text it would drop every HOSE company out of a ranking that
        filters on the board name.
        """
        entry = ListingEntry(symbol="AAA", exchange="hsx", is_listed=True)

        assert entry.exchange is Exchange.HOSE

    def test_a_board_this_system_does_not_rank_is_refused_outright(self):
        with pytest.raises(ValueError):
            ListingEntry(symbol="AAA", exchange="NASDAQ", is_listed=True)


def test_census_unavailable_is_its_own_failure():
    """Quota exhaustion is not low coverage, and must not be recorded as it."""
    assert issubclass(CensusUnavailable, RuntimeError)
