"""The Eval Fixture: captured by property, frozen by digest, refused when stale.

``docs/adr/0016`` asks for one thing from this file and it is not "a fixture
exists". It is that the fixture **cannot quietly stop being the exam it claims
to be** — so every test here is about a way that could happen:

*Selection by property, not by name.* The capture is scanned, and a store whose
limit-locked symbol has gone liquid produces a refusal rather than a fixture
without category E.

*The seed is not editable.* ``fixture_version`` is a digest of the contents, so
a hand-edited row is caught on the next read.

*Stale is louder than wrong.* A fixture frozen against a different Signal
Registry refuses to load, and names the version that moved.

*Loading is a replace.* Twice yields the same state, because merging two
photographs of a store produces a store that never existed.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.alpha.models import Analysis, WatchlistEntry
from src.eval.capture import FixtureCaptureFailed, capture_fixture, plan_capture
from src.eval.fixture import (
    FixtureSeed,
    FixtureSeedInvalid,
    read_seed,
    write_seed,
)
from src.eval.roles import FixtureRole, RoleContext, verify_roles
from src.eval.store import (
    EVAL_USER_EMAIL,
    EvalDatabaseMisconfigured,
    create_schema,
    eval_engine,
    load_fixture,
    resolve_eval_database_url,
)
from src.eval.tables import store_schema_version
from src.eval.versions import (
    FixtureVersionMismatch,
    PinnedVersions,
    running_versions,
)
from src.stocks.models import ProviderSnapshot
from src.stocks.universe import Universe

from . import eval_world as world
from .eval_store import SOURCE_DB, TARGET_DB, create_database, drop_database


@pytest.fixture(scope="module")
def source_factory():
    url = create_database(SOURCE_DB)
    engine = eval_engine(url=url)
    create_schema(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    session = factory()
    with session.begin():
        world.clear_store(session)
        world.build_source_store(session)
    session.close()
    yield factory
    engine.dispose()
    drop_database(SOURCE_DB)


@pytest.fixture(scope="module")
def target_factory():
    url = create_database(TARGET_DB)
    engine = eval_engine(url=url)
    create_schema(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    yield factory
    engine.dispose()
    drop_database(TARGET_DB)


@pytest.fixture(scope="module")
def seed(source_factory) -> FixtureSeed:
    session = source_factory()
    try:
        return capture_fixture(
            session,
            trading_day=world.TRADING_DAY,
            history_sessions=world.SESSIONS,
            universe=world.UNIVERSE,
        )
    finally:
        session.close()


class TestTheCaptureSeatsEveryRole:
    def test_the_three_deliberate_bad_cases_are_found_by_probe(self, seed):
        """Not "a fixture was produced" — the three ADR-0016 names, by name."""
        roles = seed.manifest.roles
        assert roles[FixtureRole.BELOW_MIN_SESSIONS] == world.SHORT
        assert roles[FixtureRole.PRICE_BASIS_SEAM] == world.MIXED
        assert roles[FixtureRole.LIMIT_LOCK_DENSE] == world.LOCKED

    def test_the_four_industries_each_take_their_own_seat(self, seed):
        roles = seed.manifest.roles
        assert roles[FixtureRole.BANK] == world.BANK
        assert roles[FixtureRole.REAL_ESTATE] == world.DEVELOPER
        assert roles[FixtureRole.RETAIL] == world.RETAILER
        assert roles[FixtureRole.ORDINARY] == world.ORDINARY

    def test_no_symbol_holds_two_seats(self, seed):
        symbols = list(seed.manifest.roles.values())
        assert len(symbols) == len(set(symbols))

    def test_the_scope_seat_is_listed_and_outside_the_universe(self, seed):
        outsider = seed.manifest.roles[FixtureRole.OUTSIDE_UNIVERSE]
        assert outsider in world.OUTSIDERS
        assert outsider not in seed.manifest.universe_symbols

    def test_a_store_without_a_bad_case_refuses_rather_than_freezing(
        self, source_factory
    ):
        """The failure mode being designed out is a fixture that scores anyway.

        A Universe with no short-history symbol has no category E, and a capture
        that produced one regardless would report a data-gap score over cases
        that were never exercised.
        """
        session = source_factory()
        try:
            with pytest.raises(FixtureCaptureFailed) as raised:
                plan_capture(
                    session,
                    trading_day=world.TRADING_DAY,
                    history_sessions=world.SESSIONS,
                    universe=Universe(explicit=(world.BANK, world.DEVELOPER)),
                )
        finally:
            session.close()
        assert FixtureRole.BELOW_MIN_SESSIONS.value in str(raised.value)


class TestTheSeedIsFrozen:
    def test_capturing_twice_yields_the_same_version(self, source_factory, seed):
        session = source_factory()
        try:
            again = capture_fixture(
                session,
                trading_day=world.TRADING_DAY,
                history_sessions=world.SESSIONS,
                universe=world.UNIVERSE,
            )
        finally:
            session.close()
        assert again.fixture_version == seed.fixture_version
        assert again.as_wire() == seed.as_wire()

    def test_the_file_round_trips_byte_for_byte(self, tmp_path, seed):
        first = write_seed(tmp_path / "a.json", seed)
        second = write_seed(tmp_path / "b.json", read_seed(first))
        assert first.read_bytes() == second.read_bytes()

    def test_an_edited_seed_is_refused_on_read(self, tmp_path, seed):
        path = write_seed(tmp_path / "edited.json", seed)
        payload = json.loads(path.read_text())
        payload["tables"]["listing_roster"][0]["company_name"] = "edited by hand"
        path.write_text(json.dumps(payload))

        with pytest.raises(FixtureSeedInvalid) as raised:
            read_seed(path)
        assert "captured, never edited" in str(raised.value)

    def test_the_version_carries_the_trading_day_in_front(self, seed):
        assert seed.fixture_version.startswith(world.TRADING_DAY.isoformat())


class TestVersionsAreCheckedBeforeAnythingRuns:
    def test_a_fixture_records_all_four(self, seed):
        assert seed.manifest.versions == running_versions()

    def test_a_moved_registry_version_refuses_and_names_itself(self):
        frozen = replace(running_versions(), registry_version="0000000000000000")
        with pytest.raises(FixtureVersionMismatch) as raised:
            frozen.assert_matches()
        assert [item.name for item in raised.value.mismatches] == ["registry_version"]
        assert "registry_version" in str(raised.value)

    def test_every_pin_is_compared_not_just_the_first(self):
        frozen = PinnedVersions(
            registry_version="x",
            profile_version="y",
            tool_catalog_version="z",
            schema_version="w",
        )
        names = {item.name for item in frozen.mismatches_against(running_versions())}
        assert names == {
            "registry_version",
            "profile_version",
            "tool_catalog_version",
            "schema_version",
        }

    def test_the_schema_version_is_about_the_captured_tables(self):
        """Stable across a run, and derived — not a constant someone bumps."""
        assert store_schema_version() == store_schema_version()
        assert len(store_schema_version()) == 16

    def test_loading_a_stale_fixture_refuses_before_it_writes_anything(
        self, target_factory, seed
    ):
        stale = FixtureSeed(
            manifest=replace(
                seed.manifest,
                versions=replace(seed.manifest.versions, profile_version="v0"),
            ),
            tables=seed.tables,
        )
        with pytest.raises(FixtureVersionMismatch):
            load_fixture(stale, target_factory)


class TestLoadingIntoTheEvalDatabase:
    def test_the_loaded_store_holds_what_was_captured(self, target_factory, seed):
        loaded = load_fixture(seed, target_factory)
        session = target_factory()
        try:
            snapshots = session.scalar(select(func.count(ProviderSnapshot.id)))
            analyses = session.scalar(select(func.count(Analysis.id)))
        finally:
            session.close()
        assert snapshots == len(seed.rows("provider_snapshots"))
        assert analyses == len(seed.rows("analysis"))
        assert loaded.fixture_version == seed.fixture_version

    def test_loading_twice_yields_the_same_state(self, target_factory, seed):
        load_fixture(seed, target_factory)
        session = target_factory()
        try:
            first = session.scalar(select(func.count(ProviderSnapshot.id)))
            watchlist_first = session.scalar(select(func.count(WatchlistEntry.id)))
        finally:
            session.close()

        load_fixture(seed, target_factory)
        session = target_factory()
        try:
            second = session.scalar(select(func.count(ProviderSnapshot.id)))
            watchlist_second = session.scalar(select(func.count(WatchlistEntry.id)))
        finally:
            session.close()

        assert first == second
        assert watchlist_first == watchlist_second == len(
            seed.manifest.universe_symbols
        )

    def test_the_eval_user_is_seated_rather_than_captured(self, target_factory, seed):
        """A real account's watchlist is not fixture material."""
        loaded = load_fixture(seed, target_factory)
        session = target_factory()
        try:
            symbols = session.execute(
                select(WatchlistEntry.symbol).where(
                    WatchlistEntry.user_id == loaded.user_id
                )
            ).scalars().all()
        finally:
            session.close()
        assert sorted(symbols) == sorted(seed.manifest.universe_symbols)
        assert EVAL_USER_EMAIL.endswith(".invalid")

    def test_the_roles_still_hold_over_the_loaded_store(self, target_factory, seed):
        """The same probes that selected, run again over the eval database.

        This is the acceptance criterion's *asserted by a test rather than
        assumed*: the fixture's own claim, re-decided by ``prepare_bars()`` on
        the far side of the round trip.
        """
        loaded = load_fixture(seed, target_factory)
        session = target_factory()
        try:
            verify_roles(
                session,
                seed.manifest.roles,
                RoleContext(
                    trading_day=loaded.trading_day, universe=loaded.universe
                ),
            )
        finally:
            session.close()


class TestTheDatabaseSeparationIsEnforced:
    def test_an_unset_eval_url_refuses(self, monkeypatch):
        from src.core.config import Settings

        settings = Settings(eval_database_url="")
        with pytest.raises(EvalDatabaseMisconfigured) as raised:
            resolve_eval_database_url(settings)
        assert "EVAL_DATABASE_URL" in str(raised.value)

    def test_the_application_database_is_refused_even_spelled_differently(self):
        from src.core.config import Settings

        settings = Settings(
            database_url="postgresql://a:b@localhost:5432/stockmassive",
            eval_database_url="postgresql+psycopg2://other:pw@LOCALHOST:5432/stockmassive",
        )
        with pytest.raises(EvalDatabaseMisconfigured) as raised:
            resolve_eval_database_url(settings)
        assert "same database" in str(raised.value)

    def test_a_distinct_database_is_accepted(self):
        from src.core.config import Settings

        settings = Settings(
            database_url="postgresql://a:b@localhost:5432/stockmassive",
            eval_database_url="postgresql://a:b@localhost:5432/stockmassive_eval",
        )
        assert resolve_eval_database_url(settings).endswith("/stockmassive_eval")
