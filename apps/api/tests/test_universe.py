"""Tests for the configured Universe and its startup-time refusal to be wrong.

The cap is a safety valve for the collector, so every way of declaring a list
that would break it has to fail while the operator is still looking at the
console rather than hours later inside a collector run.
"""

import pytest

from src.core.config import Settings, get_settings
from src.stocks.universe import (
    UNIVERSE_EXPLICIT_MAX,
    UNIVERSE_MAX_SYMBOLS,
    Universe,
    UniverseConfigurationError,
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


