"""The benchmark's stored session series: what it is, and what it is kept out of.

Three claims are tested here and they are the whole of `docs/adr/0017`:

*The index is a session series like any other.* It is written to the store, it is
read back through the same reader a symbol's sessions come through, and it is
served by the same gateway — so the beta that will one day be computed from it
takes the path every other computation takes.

*The index is not an equity.* It has no band, no Corporate Action series and no
place in a liquidity cross-section, and the gateway states each of those rather
than discovering them: a 9% index session is the market, not a wrong anchor.

*The index does not define the market.* A **Trading Day** is derived from the
`market` Capability, so an index session must never move it. That is the failure
that decided the storage question, and it is the test that would fail first if
somebody moved the series back under `market` with a reserved symbol.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.core.config import Settings
from src.stocks.market_index import (
    MARKET_INDEX_SYMBOL,
    MARKET_INDEX_WINDOW_TRADING_DAYS,
    MarketIndexLoader,
    MarketIndexUnavailable,
    build_market_index_loader,
)
from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import (
    MARKET_SCHEMA_VERSION,
    Capability,
    CorporateActionEvent,
    MarketIndexSnapshot,
    MarketSnapshot,
    PriceBasis,
    ProviderSource,
    SnapshotMetadata,
    SnapshotStore,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.bars import BarSeries, prepare_bars, prepare_bars_context
from src.stocks.signals.cross_sectional import (
    RELATIVE_STRENGTH_BENCHMARK,
    RELATIVE_STRENGTH_MIN_SESSIONS,
)
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.price_band import LimitLock
from src.stocks.signals.sessions import sessions_in_range, sessions_on_days
from src.stocks.trading_day import latest_trading_day

from .test_corporate_actions import save
from .test_price_band import write_session

NOW = datetime(2026, 8, 13, 11, 0, tzinfo=timezone.utc)


def open_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        ProviderSnapshot.__table__,
        ListingRoster.__table__,
        CorporateAction.__table__,
    ):
        table.create(engine)
    return Session(engine)


def _stamp(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


def index_snapshot(
    day: date,
    *,
    close: float = 1_280.0,
    high: float | None = None,
    low: float | None = None,
    index: str = MARKET_INDEX_SYMBOL,
    source: ProviderSource = ProviderSource.FIINQUANT,
    basis: PriceBasis = PriceBasis.RAW,
) -> MarketIndexSnapshot:
    return MarketIndexSnapshot(
        symbol=index,
        metadata=SnapshotMetadata(
            source=source,
            effective_at=_stamp(day),
            observed_at=NOW,
            schema_version=MARKET_SCHEMA_VERSION,
        ),
        price_basis=basis,
        open_price=close,
        high_price=high if high is not None else close,
        low_price=low if low is not None else close,
        last_price=close,
        volume=800_000_000,
        total_value_vnd=21_000_000_000_000.0,
    )


def write_index_session(session: Session, day: date, **fields) -> None:
    """Store one index session, the way the loader would have."""
    snapshot = index_snapshot(day, **fields)
    session.add(
        ProviderSnapshot(
            capability=Capability.MARKET_INDEX.value,
            symbol=snapshot.symbol,
            source=snapshot.metadata.source.value,
            effective_at=_stamp(day),
            observed_at=NOW,
            schema_version=MARKET_SCHEMA_VERSION,
            payload=snapshot.model_dump(mode="json"),
        )
    )
    session.flush()


def weekdays(first: date, last: date) -> tuple[date, ...]:
    days: list[date] = []
    cursor = first
    while cursor <= last:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return tuple(days)


def open_store() -> tuple[SnapshotStore, Session]:
    session = open_session()
    return SnapshotStore(session, redis=None), session


class RecordingIndexHistory:
    """A Main Source that answers with the sessions it was given."""

    source = ProviderSource.FIINQUANT

    def __init__(self, sessions: list[date], index: str = MARKET_INDEX_SYMBOL):
        self._sessions = sessions
        self._index = index
        self.windows: list[tuple[str, date, date]] = []

    def fetch_index_history(self, index, from_date, to_date):
        self.windows.append((index, from_date, to_date))
        if index != self._index:
            return ()
        return tuple(index_snapshot(day, index=index) for day in self._sessions)


class BrokenIndexHistory:
    source = ProviderSource.FIINQUANT

    def fetch_index_history(self, index, from_date, to_date):
        raise ConnectionError("gateway unavailable")


class CoverIndexHistory:
    source = ProviderSource.VNSTOCK

    def fetch_index_history(self, index, from_date, to_date):  # pragma: no cover
        raise AssertionError("the index series is written from one source only")


def build(history, window: int = 25) -> tuple[MarketIndexLoader, Session]:
    store, session = open_store()
    return (
        MarketIndexLoader(
            store=store,
            history=history,
            now=lambda: NOW,
            window_trading_days=window,
        ),
        session,
    )


def stored_index_sessions(session: Session) -> list[date]:
    rows = session.execute(
        select(ProviderSnapshot.effective_at)
        .where(
            ProviderSnapshot.capability == Capability.MARKET_INDEX.value,
            ProviderSnapshot.symbol == MARKET_INDEX_SYMBOL,
        )
        .order_by(ProviderSnapshot.effective_at.asc())
    ).scalars()
    return [stamp.date() for stamp in rows]


class TestTheDepthFollowsTheFieldThatReadsIt:
    def test_the_window_clears_the_declared_floor_of_the_field_it_feeds(self):
        """A series one session short would leave `relative_strength` refusing
        under `insufficient_history` — the same unavailability wearing a reason
        that points at the wrong fix."""
        assert MARKET_INDEX_WINDOW_TRADING_DAYS > RELATIVE_STRENGTH_MIN_SESSIONS

    def test_the_configured_default_matches_the_derived_depth(self):
        """The setting exists so an operator can shorten the load deliberately.
        Its default must not shorten it by accident."""
        assert (
            Settings().market_index_window_trading_days
            == MARKET_INDEX_WINDOW_TRADING_DAYS
        )

    def test_a_configured_depth_below_the_fields_floor_is_refused(self):
        """Writing the default as the field's floor plus a margin does not
        enforce anything: production runs on the configured value, and a
        constant nothing checks is a comment. The wiring is where the floor
        bites, and it names both numbers so an operator sees a misconfiguration
        instead of a field refusing weeks later for a reason pointing at
        collection."""
        store, _ = open_store()
        settings = Settings(
            fiinquant_username="operator",
            fiinquant_password="password",
            market_index_window_trading_days=RELATIVE_STRENGTH_MIN_SESSIONS - 1,
        )

        with pytest.raises(MarketIndexUnavailable) as refused:
            build_market_index_loader(store, settings=settings)

        assert str(RELATIVE_STRENGTH_MIN_SESSIONS) in str(refused.value)

    def test_no_fiinquant_account_is_refused_rather_than_degraded(self):
        store, _ = open_store()

        with pytest.raises(MarketIndexUnavailable, match="FiinQuant"):
            build_market_index_loader(store, settings=Settings())

    def test_the_index_loaded_is_the_benchmark_the_field_names(self):
        assert MARKET_INDEX_SYMBOL == RELATIVE_STRENGTH_BENCHMARK

    def test_the_calendar_reach_covers_the_holidays_a_year_of_sessions_hides(self):
        """Five sessions a week is seven calendar days, and Vietnam then closes
        for about eleven more days a year — Tet is nine of them running. A
        reach-back that only multiplied by 7/5 would come back short."""
        history = RecordingIndexHistory([])
        warmup, _ = build(history, window=250)

        warmup.run()

        _, from_date, to_date = history.windows[0]
        assert to_date == date(2026, 8, 13)
        assert (to_date - from_date).days > round(250 * 7 / 5)


class TestTheLoad:
    def test_it_writes_every_session_in_the_window(self):
        days = list(weekdays(date(2026, 8, 3), date(2026, 8, 7)))
        warmup, session = build(RecordingIndexHistory(days))

        summary = warmup.run()

        assert summary.completed == (MARKET_INDEX_SYMBOL,)
        assert summary.sessions_written == len(days)
        assert stored_index_sessions(session) == days

    def test_re_running_the_same_window_writes_no_duplicates(self):
        """Repeatable is the point: the run that first fills the series is the
        run that tops it up tomorrow and repairs a week that was missed."""
        days = list(weekdays(date(2026, 8, 3), date(2026, 8, 7)))
        warmup, session = build(RecordingIndexHistory(days))

        warmup.run()
        warmup.run()

        total = session.execute(
            select(func.count()).select_from(ProviderSnapshot)
        ).scalar_one()
        assert total == len(days)

    def test_it_keeps_only_the_newest_sessions_in_the_window(self):
        """The calendar span reaches past the window so the holidays cannot make
        it fall short, so a quiet stretch comes back long. Bounded has to be a
        property of what is written."""
        days = list(weekdays(date(2026, 7, 1), date(2026, 7, 31)))
        warmup, session = build(RecordingIndexHistory(days), window=4)

        warmup.run()

        assert stored_index_sessions(session) == days[-4:]

    def test_it_writes_only_the_market_index_capability(self):
        warmup, session = build(RecordingIndexHistory([date(2026, 8, 10)]))

        warmup.run()

        capabilities = set(
            session.execute(select(ProviderSnapshot.capability)).scalars()
        )
        assert capabilities == {Capability.MARKET_INDEX.value}

    def test_it_refuses_a_source_that_does_not_own_the_capability(self):
        """One owner, no cover (docs/adr/0017): the Cover Source's history is
        adjusted_at_source and an index is adjusted for nothing, so a series
        filled from there would assert a rescaling nobody performed."""
        store, _ = open_store()

        with pytest.raises(MarketIndexUnavailable):
            MarketIndexLoader(store=store, history=CoverIndexHistory())

    def test_the_store_refuses_each_contract_under_the_other_capability(self):
        """The two contracts are siblings rather than one subclassing the other,
        so the store's own type check is what keeps an equity out of the index
        series and a level out of the equity one — in both directions, and
        without either of them having to test a symbol name."""
        store, _ = open_store()
        index = index_snapshot(date(2026, 8, 10))
        equity = MarketSnapshot(
            symbol="VCB",
            metadata=SnapshotMetadata(
                source=ProviderSource.FIINQUANT,
                effective_at=_stamp(date(2026, 8, 10)),
                observed_at=NOW,
                schema_version=MARKET_SCHEMA_VERSION,
            ),
            price_basis=PriceBasis.RAW,
            last_price=59_700.0,
        )

        with pytest.raises(TypeError):
            store.save(Capability.MARKET, index)
        with pytest.raises(TypeError):
            store.save(Capability.MARKET_INDEX, equity)

    def test_a_provider_outage_is_reported_rather_than_raised(self):
        warmup, _ = build(BrokenIndexHistory())

        summary = warmup.run()

        assert summary.completed == ()
        assert summary.sessions_written == 0
        assert len(summary.failed) == 1
        assert "ConnectionError" in summary.failed[0].reason

    def test_a_run_that_stored_nothing_is_a_failed_run(self):
        """The index publishes a level on every session the exchange opens, and
        re-storing one already held still counts — so a run that wrote nothing
        is the silent-empty failure this codebase refuses elsewhere, not a
        healthy run with nothing to do."""
        warmup, _ = build(RecordingIndexHistory([]))

        summary = warmup.run()

        assert summary.completed == ()
        assert [item.index for item in summary.failed] == [MARKET_INDEX_SYMBOL]
        assert "no sessions" in summary.failed[0].reason

    def test_a_store_that_refuses_every_session_is_a_failed_run_too(self):
        """The other way to write nothing, and it must not read as success
        either — the count of what was refused is on the reason."""
        days = list(weekdays(date(2026, 8, 3), date(2026, 8, 7)))

        class RefusingStore:
            def save(self, capability, snapshot):
                raise RuntimeError("the database is read only")

        loader = MarketIndexLoader(
            store=RefusingStore(),
            history=RecordingIndexHistory(days),
            now=lambda: NOW,
            window_trading_days=25,
        )

        summary = loader.run()

        assert summary.sessions_written == 0
        assert [item.index for item in summary.failed] == [MARKET_INDEX_SYMBOL]
        assert f"refused all {len(days)}" in summary.failed[0].reason


class TestTheIndexDoesNotDefineTheMarket:
    def test_an_index_session_is_not_a_trading_day(self):
        """The reason the series is a Capability of its own. `latest_trading_day`
        is max(effective_at) over the `market` Capability, so an index session
        stored there would move the window every equity is measured against —
        and an index row landing before the Universe's would refuse every symbol
        for one session of missing history."""
        with open_session() as session:
            for day in weekdays(date(2026, 8, 3), date(2026, 8, 7)):
                write_session(session, "VCB", day, close=59_700.0)
            # The index has already published a session the Universe has not
            # been collected for.
            write_index_session(session, date(2026, 8, 10))

            assert latest_trading_day(session) == date(2026, 8, 7)

    def test_the_equity_reader_never_sees_an_index_session(self):
        with open_session() as session:
            write_index_session(session, date(2026, 8, 10))

            held = sessions_in_range(
                session, MARKET_INDEX_SYMBOL, date(2026, 8, 3), date(2026, 8, 12)
            )

            assert held == {}


class TestReadingItBack:
    def test_the_shared_session_reader_returns_the_index_series(self):
        days = weekdays(date(2026, 8, 3), date(2026, 8, 7))
        with open_session() as session:
            for offset, day in enumerate(days):
                write_index_session(session, day, close=1_280.0 + offset)

            held = sessions_in_range(
                session,
                MARKET_INDEX_SYMBOL,
                days[0],
                days[-1],
                capability=Capability.MARKET_INDEX,
            )

        assert sorted(held) == list(days)
        assert held[days[-1]].last_price == 1_284.0

    def test_the_multi_symbol_reader_returns_it_on_named_days(self):
        days = weekdays(date(2026, 8, 3), date(2026, 8, 7))
        with open_session() as session:
            for day in days:
                write_index_session(session, day)

            held = sessions_on_days(
                session,
                [MARKET_INDEX_SYMBOL],
                days[:3],
                capability=Capability.MARKET_INDEX,
            )

        assert sorted(held[MARKET_INDEX_SYMBOL]) == list(days[:3])

    def test_a_capability_that_is_not_a_session_series_is_refused(self):
        """Named where it is written rather than answered with a quarterly
        statement keyed by a date that means something else."""
        with open_session() as session:
            with pytest.raises(ValueError, match="not a session series"):
                sessions_in_range(
                    session,
                    "VCB",
                    date(2026, 8, 3),
                    date(2026, 8, 7),
                    capability=Capability.FUNDAMENTAL,
                )


class TestTheGatewayServesIt:
    def _stored(self, session: Session, days) -> None:
        """The Universe's Trading Days, and the index on every one of them."""
        for day in days:
            write_session(session, "VCB", day, close=59_700.0)
            write_index_session(session, day)

    def test_the_index_reaches_bars_through_prepare_bars(self):
        days = weekdays(date(2026, 7, 27), date(2026, 8, 12))
        with open_session() as session:
            self._stored(session, days)

            frame, health = prepare_bars(
                session,
                MARKET_INDEX_SYMBOL,
                len(days),
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert health.refusal is None
        assert frame is not None
        assert frame.sessions == days
        assert frame.bars[-1].close == 1_280.0

    def test_every_index_bar_says_it_has_no_band_rather_than_no_verdict(self):
        """A `Bar` promises either its band or the reason it has none. An index
        has none *at all* — no board, so no reference price to take a percentage
        of — and that is a different fact from a band nobody could decide."""
        days = weekdays(date(2026, 7, 27), date(2026, 8, 12))
        with open_session() as session:
            self._stored(session, days)

            frame, health = prepare_bars(
                session,
                MARKET_INDEX_SYMBOL,
                len(days),
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert frame is not None
        assert all(bar.band is None for bar in frame.bars)
        assert {bar.band_undecided_reason for bar in frame.bars} == {
            SignalIssue.BAND_NOT_APPLICABLE
        }
        # Not `indeterminate`. That one is the store admitting it could not
        # judge a session which does have a band, and it would leave an equity's
        # word on the one bar that most needs not to carry one.
        assert all(bar.limit_lock is LimitLock.NOT_APPLICABLE for bar in frame.bars)
        assert all(not bar.limit_locked for bar in frame.bars)
        assert health.limit_lock_days == 0
        assert health.band_regime is None
        # Counted at zero on purpose: nothing was left undecided, because there
        # was nothing to decide.
        assert health.band_undecided_days == 0
        assert health.band_undecided_reasons == ()

    def test_a_move_no_band_would_permit_is_served_rather_than_refused(self):
        """`unexplained_price_gap` reads a break of the band as evidence of a
        wrong anchor. With no band there is no break to read, and a 9% index
        session is the market moving — the store has nothing to say against it."""
        days = weekdays(date(2026, 7, 27), date(2026, 8, 12))
        with open_session() as session:
            for day in days:
                write_session(session, "VCB", day, close=59_700.0)
            for day in days[:-1]:
                write_index_session(session, day, close=1_280.0)
            write_index_session(session, days[-1], close=1_164.0)

            frame, health = prepare_bars(
                session,
                MARKET_INDEX_SYMBOL,
                len(days),
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert health.refusal is None
        assert frame is not None
        assert frame.bars[-1].close == 1_164.0

    def test_no_corporate_action_series_is_read_for_the_index(self):
        """The exchange absorbs member entitlements into the index divisor, so
        the published series is already continuous. An action stored against the
        index's code — which nothing should ever write — must not rebase it."""
        days = weekdays(date(2026, 7, 27), date(2026, 8, 12))
        with open_session() as session:
            self._stored(session, days)
            save(
                session,
                CorporateActionEvent(
                    symbol=MARKET_INDEX_SYMBOL,
                    event_code="ISS",
                    title="Share Issue - Stock dividend ratio 100.0%",
                    ex_date=days[-2],
                    exercise_ratio=1.0,
                ),
            )

            frame, health = prepare_bars(
                session,
                MARKET_INDEX_SYMBOL,
                len(days),
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert frame is not None
        assert health.adjustment.applied is False
        assert health.adjustment.actions_in_window == 0
        assert health.degradations == ()
        assert health.quantities_comparable
        assert all(bar.adjustment_factor == 1 for bar in frame.bars)
        # Untouched: the level the exchange published is the level served.
        assert all(bar.close == 1_280.0 for bar in frame.bars)

    def test_the_index_carries_no_liquidity_standing_and_no_company_figures(self):
        """There is no peer set an index trades among, so ranking its turnover
        would rank a composite against its own members."""
        days = weekdays(date(2026, 7, 27), date(2026, 8, 12))
        with open_session() as session:
            self._stored(session, days)

            frame, health = prepare_bars(
                session,
                MARKET_INDEX_SYMBOL,
                len(days),
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert health.adtv is None
        assert frame is not None
        assert all(bar.market_cap_vnd is None for bar in frame.bars)
        assert all(bar.foreign_net_value_vnd is None for bar in frame.bars)

    def test_the_window_is_cut_from_the_markets_own_trading_days(self):
        """Why a beta is computable at all: the benchmark is read on exactly the
        sessions the symbol was. An index session on a day no equity traded is
        outside the window rather than an extra bar in it."""
        days = weekdays(date(2026, 7, 27), date(2026, 8, 12))
        with open_session() as session:
            self._stored(session, days)
            # A Saturday inside the window's span: the index has a stored row
            # and the market has no Trading Day.
            write_index_session(session, date(2026, 8, 8))

            frame, _ = prepare_bars(
                session,
                MARKET_INDEX_SYMBOL,
                len(days),
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert frame is not None
        assert frame.sessions == days

    def test_a_context_loaded_for_one_series_refuses_the_other(self):
        """Two series live under different Capabilities, so a context loaded for
        one holds nothing for the other. Answered with an error rather than an
        empty window, which would read as a symbol with no history."""
        days = weekdays(date(2026, 7, 27), date(2026, 8, 12))
        with open_session() as session:
            self._stored(session, days)
            context = prepare_bars_context(
                session,
                [MARKET_INDEX_SYMBOL],
                len(days),
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

            with pytest.raises(ValueError, match="series"):
                prepare_bars(
                    session,
                    MARKET_INDEX_SYMBOL,
                    len(days),
                    end=days[-1],
                    context=context,
                )

    def test_a_mixed_basis_index_window_is_still_refused(self):
        """The Price Basis rule is not relaxed for the index. A series that
        somehow held two bases is as meaningless there as anywhere."""
        days = weekdays(date(2026, 7, 27), date(2026, 8, 12))
        with open_session() as session:
            for day in days:
                write_session(session, "VCB", day, close=59_700.0)
            for day in days[:-1]:
                write_index_session(session, day)
            write_index_session(
                session, days[-1], basis=PriceBasis.ADJUSTED_AT_SOURCE
            )

            frame, health = prepare_bars(
                session,
                MARKET_INDEX_SYMBOL,
                len(days),
                end=days[-1],
                series=BarSeries.MARKET_INDEX,
            )

        assert frame is None
        assert health.refusal is SignalIssue.MIXED_PRICE_BASIS
