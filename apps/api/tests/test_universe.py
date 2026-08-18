"""Tests for the configured Universe and its startup-time refusal to be wrong.

The cap is a safety valve for the collector, so every way of declaring a list
that would break it has to fail while the operator is still looking at the
console rather than hours later inside a collector run.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.config import Settings, get_settings
from src.main import app
from src.stocks.models import CohortMember, CohortVersion
from src.stocks.universe import (
    UNIVERSE_EXPLICIT_MAX,
    UNIVERSE_MAX_SYMBOLS,
    Universe,
    UniverseConfigurationError,
    build_universe,
    forget_cohort_cache,
    parse_universe,
)


@pytest.fixture
def declared_universe(monkeypatch):
    """Declare a Universe the way an operator does, through the environment.

    The settings are cached for the life of the process and the cohort half is
    memoized per version, so both are cleared on the way in and on the way out;
    leaving a test's Universe behind would silently reconfigure every test that
    runs after it.
    """

    def declare(value: str) -> None:
        monkeypatch.setenv("UNIVERSE_SYMBOLS", value)
        get_settings.cache_clear()
        forget_cohort_cache()

    yield declare
    monkeypatch.undo()
    get_settings.cache_clear()
    forget_cohort_cache()


def open_session() -> Session:
    engine = create_engine("sqlite://")
    CohortVersion.__table__.create(engine)
    CohortMember.__table__.create(engine)
    return Session(engine)


def seat_active_cohort(session: Session, symbols: tuple[str, ...]) -> CohortVersion:
    """Write an active version holding these members, in the order given."""
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    version = CohortVersion(
        reporting_period=datetime(2026, 6, 30).date(),
        census_run_id=1,
        state="active",
        created_at=now,
        activated_at=now,
    )
    session.add(version)
    session.flush()
    for rank, symbol in enumerate(symbols, start=1):
        session.add(
            CohortMember(
                cohort_version_id=version.id,
                symbol=symbol,
                rank=rank,
                net_income_vnd=1000 - rank,
                exchange="HOSE",
            )
        )
    session.flush()
    forget_cohort_cache()
    return version


class TestParsing:
    def test_reads_a_comma_separated_list(self):
        universe = parse_universe("VCB,FPT,HPG")

        assert tuple(universe) == ("VCB", "FPT", "HPG")

    def test_normalizes_case_and_surrounding_space(self):
        universe = parse_universe("  vcb , Fpt\n, hpg  ")

        assert tuple(universe) == ("VCB", "FPT", "HPG")

    def test_drops_duplicates_however_they_are_written(self):
        universe = parse_universe("VCB, vcb , FPT, VCB")

        assert tuple(universe) == ("VCB", "FPT")

    def test_ignores_empty_entries_left_by_stray_separators(self):
        universe = parse_universe("VCB,,FPT,")

        assert tuple(universe) == ("VCB", "FPT")

    def test_an_empty_declaration_is_a_valid_empty_universe(self):
        universe = parse_universe("")

        assert tuple(universe) == ()
        assert len(universe) == 0

    def test_a_declaration_of_only_separators_is_still_empty(self):
        universe = parse_universe("  , ,  ")

        assert len(universe) == 0


class TestRefusal:
    def test_a_malformed_symbol_names_itself_in_the_error(self):
        with pytest.raises(UniverseConfigurationError) as error:
            parse_universe("VCB,VN-INDEX,FPT")

        assert "VN-INDEX" in str(error.value)

    def test_a_symbol_too_long_for_the_market_is_refused(self):
        with pytest.raises(UniverseConfigurationError) as error:
            parse_universe("ABCDEFGHIJK")

        assert "ABCDEFGHIJK" in str(error.value)

    def test_declaring_more_than_half_the_universe_is_refused(self):
        """The other fifty places belong to the cohort, not to configuration.

        Refused at parse time rather than trimmed: a declaration silently cut to
        fifty is an operator watching symbols they did not ask for.
        """
        declared = [f"S{index:03d}" for index in range(UNIVERSE_EXPLICIT_MAX + 5)]

        with pytest.raises(UniverseConfigurationError) as error:
            parse_universe(",".join(declared))

        message = str(error.value)
        assert str(UNIVERSE_EXPLICIT_MAX) in message
        assert str(len(declared)) in message
        assert "Cohort" in message

    def test_exactly_the_declared_half_is_allowed(self):
        declared = [f"S{index:03d}" for index in range(UNIVERSE_EXPLICIT_MAX)]

        universe = parse_universe(",".join(declared))

        assert len(universe) == UNIVERSE_EXPLICIT_MAX

    def test_duplicates_are_removed_before_the_cap_is_applied(self):
        """A list that only exceeds the cap by repeating itself still fits.

        The cap bounds what the collector actually calls for, and it never
        calls for the same symbol twice.
        """
        declared = [f"S{index:03d}" for index in range(UNIVERSE_EXPLICIT_MAX)]

        universe = parse_universe(",".join(declared + declared))

        assert len(universe) == UNIVERSE_EXPLICIT_MAX


class TestMembership:
    def test_a_declared_symbol_is_a_member_however_it_is_written(self):
        universe = parse_universe("VCB,FPT")

        assert universe.contains("vcb")
        assert " fpt " in universe

    def test_an_undeclared_symbol_is_not_a_member(self):
        universe = parse_universe("VCB,FPT")

        assert not universe.contains("HPG")

    def test_a_malformed_symbol_is_simply_not_a_member(self):
        """The serving path asks this about whatever a user typed.

        Membership answers a question; it is not a second validation gate, so
        nonsense has to come back False rather than raise into a request.
        """
        universe = parse_universe("VCB")

        assert not universe.contains("VN-INDEX")
        assert not universe.contains("")

    def test_an_empty_universe_contains_nothing(self):
        universe = parse_universe("")

        assert not universe.contains("VCB")


class TestSettingsBinding:
    def test_the_universe_is_read_from_the_configured_list(self, monkeypatch):
        monkeypatch.setenv("UNIVERSE_SYMBOLS", "VCB, FPT")
        from src.core.config import Settings

        universe = Universe.from_settings(Settings())

        assert tuple(universe) == ("VCB", "FPT")

    def test_a_bad_configured_list_refuses_to_produce_a_universe(self, monkeypatch):
        monkeypatch.setenv("UNIVERSE_SYMBOLS", "VCB,VN-INDEX")
        from src.core.config import Settings

        with pytest.raises(UniverseConfigurationError):
            Universe.from_settings(Settings())


class TestCohortSeating:
    """The earned half of the Universe, and what happens when it will not fit."""

    def test_the_two_halves_are_served_together(self):
        universe = parse_universe("VCB,FPT").with_cohort(("HPG", "MWG"))

        assert tuple(universe) == ("VCB", "FPT", "HPG", "MWG")
        assert universe.contains("mwg")

    def test_a_symbol_in_both_halves_holds_one_place(self):
        universe = parse_universe("VCB,FPT").with_cohort(("FPT", "HPG"))

        assert tuple(universe) == ("VCB", "FPT", "HPG")
        assert len(universe) == 3

    def test_seating_a_cohort_that_would_breach_the_cap_is_refused(self):
        """The declared half survives; the cohort is what does not get seated.

        A cohort trimmed to fit would be the top forty-something companies
        presented as the top fifty, so the whole activation is refused instead.
        """
        declared = parse_universe(
            ",".join(f"S{index:03d}" for index in range(UNIVERSE_EXPLICIT_MAX))
        )
        cohort = tuple(
            f"C{index:03d}"
            for index in range(UNIVERSE_MAX_SYMBOLS - UNIVERSE_EXPLICIT_MAX + 1)
        )

        universe = declared.with_cohort(cohort)

        assert universe.cohort == ()
        assert universe.explicit == declared.explicit
        assert len(universe) == UNIVERSE_EXPLICIT_MAX

    def test_a_cohort_filling_the_reserved_half_exactly_fits(self):
        declared = parse_universe(
            ",".join(f"S{index:03d}" for index in range(UNIVERSE_EXPLICIT_MAX))
        )
        cohort = tuple(
            f"C{index:03d}"
            for index in range(UNIVERSE_MAX_SYMBOLS - UNIVERSE_EXPLICIT_MAX)
        )

        universe = declared.with_cohort(cohort)

        assert len(universe) == UNIVERSE_MAX_SYMBOLS

    def test_built_from_the_database_it_seats_the_active_version(
        self, declared_universe
    ):
        declared_universe("VCB,FPT")
        session = open_session()
        seat_active_cohort(session, ("HPG", "MWG"))

        universe = build_universe(session, Settings(universe_symbols="VCB,FPT"))

        assert tuple(universe) == ("VCB", "FPT", "HPG", "MWG")

    def test_with_no_active_version_only_the_declared_half_is_served(
        self, declared_universe
    ):
        declared_universe("VCB,FPT")
        session = open_session()

        universe = build_universe(session, Settings(universe_symbols="VCB,FPT"))

        assert tuple(universe) == ("VCB", "FPT")
        assert universe.cohort == ()


class TestStartup:
    """The refusal has to happen at startup, not at the first collector run."""

    def test_a_malformed_symbol_stops_the_application_coming_up(
        self, declared_universe
    ):
        declared_universe("VCB,VN-INDEX")

        with pytest.raises(UniverseConfigurationError) as error:
            with TestClient(app):
                pass

        assert "VN-INDEX" in str(error.value)

    def test_going_over_the_declared_half_stops_the_application_coming_up(
        self, declared_universe
    ):
        declared_universe(
            ",".join(f"S{index:03d}" for index in range(UNIVERSE_EXPLICIT_MAX + 1))
        )

        with pytest.raises(UniverseConfigurationError) as error:
            with TestClient(app):
                pass

        assert str(UNIVERSE_EXPLICIT_MAX) in str(error.value)

    def test_an_empty_universe_lets_the_application_come_up(self, declared_universe):
        declared_universe("")

        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
