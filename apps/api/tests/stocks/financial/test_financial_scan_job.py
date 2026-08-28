"""The job: what it skips, what it retries, and what one bad symbol costs.

The scope is stubbed to invented tickers. A run over the real declared list with
a stubbed provider would write statement figures nothing verified under real
company names, so the scope selection is proved read-only, on its own, and the
run is proved on symbols nothing else reads.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, func, select

from src.core.config import get_settings
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.stocks import financial_scan_job as job
from src.stocks.financial import fetch
from src.stocks.models import (
    FinancialRatioSnapshot,
    FinancialStatementLine,
    ListingRoster,
)

from . import fixtures

FIRST = "ZZSCAN1"
SECOND = "ZZSCAN2"
SYMBOLS = (FIRST, SECOND)
OBSERVED_AT = datetime(2026, 8, 27, 22, 0, tzinfo=timezone.utc)
STATEMENTS_ONLY = fetch.STATEMENTS


@contextmanager
def rollback_session():
    """A session for the read-only scope cases, never committed."""
    session = sync_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def no_leftover_rows():
    yield
    with get_sync_db() as session:
        session.execute(
            delete(FinancialStatementLine).where(
                FinancialStatementLine.symbol.in_(SYMBOLS)
            )
        )
        session.execute(
            delete(FinancialRatioSnapshot).where(
                FinancialRatioSnapshot.symbol.in_(SYMBOLS)
            )
        )


@pytest.fixture
def two_symbols(monkeypatch):
    monkeypatch.setattr(job, "scope_symbols", lambda session, scope: SYMBOLS)


def a_statement(symbol, statement):
    """A captured response for whatever statement is asked for."""
    if statement == fetch.STATEMENT_INCOME:
        return fixtures.stb_income()
    return fixtures.stb_balance()


def a_ratio(symbol):
    return fixtures.stb_ratio()


def scan(parts=STATEMENTS_ONLY, statement=a_statement, ratio=a_ratio):
    return job.run(
        scope="market",
        parts=parts,
        fetch_statement=statement,
        fetch_ratio=ratio,
        observed_at=OBSERVED_AT,
    )


def lines_for(symbol: str) -> int:
    with get_sync_db() as session:
        return session.execute(
            select(func.count(FinancialStatementLine.symbol)).where(
                FinancialStatementLine.symbol == symbol
            )
        ).scalar_one()


def ratios_for(symbol: str) -> int:
    with get_sync_db() as session:
        return session.execute(
            select(func.count(FinancialRatioSnapshot.symbol)).where(
                FinancialRatioSnapshot.symbol == symbol
            )
        ).scalar_one()


class TestScope:
    def test_the_declared_scope_is_the_declared_universe(self, monkeypatch):
        monkeypatch.setenv("UNIVERSE_SYMBOLS", "VCB,FPT")
        get_settings.cache_clear()
        try:
            with rollback_session() as session:
                assert job.scope_symbols(session, "declared") == ("VCB", "FPT")
        finally:
            get_settings.cache_clear()

    def test_the_market_scope_is_the_registers_listed_shares(self):
        """The whole market, whatever the declared list says, minus who left."""
        with rollback_session() as session:
            session.add_all(
                [
                    ListingRoster(
                        symbol=FIRST,
                        exchange="HOSE",
                        is_listed=True,
                        source="vnstock",
                        observed_at=OBSERVED_AT,
                    ),
                    ListingRoster(
                        symbol=SECOND,
                        exchange="HNX",
                        is_listed=False,
                        source="vnstock",
                        observed_at=OBSERVED_AT,
                    ),
                ]
            )
            session.flush()

            market = job.scope_symbols(session, "market")

        assert FIRST in market
        assert SECOND not in market

    def test_a_scope_that_is_not_a_scope_is_refused(self):
        with rollback_session() as session:
            with pytest.raises(ValueError, match="not a scope"):
                job.scope_symbols(session, "everything")


@pytest.mark.usefixtures("two_symbols")
class TestIsCurrent:
    """The skip rule, with the reference quarter given rather than derived.

    The reference is market-wide by design — the first symbol to answer with a
    new quarter un-skips everyone behind it — so it is passed in here instead of
    read from a database other tests are also writing to.
    """

    def test_a_symbol_holding_every_part_at_the_reference_is_current(self):
        scan(parts=fetch.PARTS)

        with get_sync_db() as session:
            assert job.is_current(
                session,
                FIRST,
                parts=fetch.PARTS,
                statement_reference="2026-Q2",
                ratio_reference="2026-Q2",
            )

    def test_a_symbol_behind_the_reference_quarter_is_not_current(self):
        scan(parts=STATEMENTS_ONLY)

        with get_sync_db() as session:
            assert not job.is_current(
                session,
                FIRST,
                parts=STATEMENTS_ONLY,
                statement_reference="2026-Q3",
                ratio_reference=None,
            )

    def test_a_symbol_missing_one_requested_statement_is_not_current(self):
        scan(parts=(fetch.STATEMENT_INCOME,))

        with get_sync_db() as session:
            assert job.is_current(
                session,
                FIRST,
                parts=(fetch.STATEMENT_INCOME,),
                statement_reference="2026-Q2",
                ratio_reference=None,
            )
            assert not job.is_current(
                session,
                FIRST,
                parts=STATEMENTS_ONLY,
                statement_reference="2026-Q2",
                ratio_reference=None,
            )

    def test_the_ratio_table_is_judged_against_its_own_reference(self):
        """The two sources publish a quarter on their own schedule."""
        scan(parts=STATEMENTS_ONLY)

        with get_sync_db() as session:
            assert not job.is_current(
                session,
                FIRST,
                parts=fetch.PARTS,
                statement_reference="2026-Q2",
                ratio_reference="2026-Q2",
            )

    def test_an_empty_store_makes_nothing_current(self):
        with get_sync_db() as session:
            assert not job.is_current(
                session,
                FIRST,
                parts=fetch.PARTS,
                statement_reference=None,
                ratio_reference=None,
            )

    def test_the_reference_quarters_are_the_newest_each_table_holds(self):
        scan(parts=fetch.PARTS)

        with get_sync_db() as session:
            statements, ratios = job.newest_stored_periods(session)

        assert statements >= "2026-Q2"
        assert ratios >= "2026-Q2"


class TestRun:
    def test_every_symbol_in_the_scope_is_written(self, two_symbols):
        report = scan()

        assert report.attempted == 2
        assert report.skipped == 0
        assert lines_for(FIRST) == 40
        assert lines_for(SECOND) == 40

    def test_a_second_run_writes_nothing_and_skips_what_is_stored(self, two_symbols):
        """Resume comes from the store, and there is no ledger to disagree."""
        scan()
        report = scan()

        assert report.skipped == 2
        assert report.rows_written == 0
        assert lines_for(FIRST) == 40

    def test_a_symbol_missing_a_requested_part_is_fetched_again(self, two_symbols):
        """Currency alone would leave a symbol permanently without its ratios."""
        scan(parts=STATEMENTS_ONLY)
        report = scan(parts=fetch.PARTS)

        assert report.skipped == 0
        assert ratios_for(FIRST) == 21

    def test_one_failing_symbol_does_not_end_the_run(self, two_symbols):
        """Six thousand requests against a provider with no SLA cannot stop at one."""

        def statement(symbol, part):
            if symbol == FIRST:
                raise fetch.FinancialFetchError("the provider hung up")
            return a_statement(symbol, part)

        report = scan(statement=statement)

        assert report.failures == (FIRST,)
        assert lines_for(FIRST) == 0
        assert lines_for(SECOND) == 40

    def test_a_failing_symbol_does_not_roll_back_the_symbols_before_it(
        self, two_symbols
    ):
        """Each symbol has its own transaction, so an abort costs one symbol."""

        def statement(symbol, part):
            if symbol == SECOND:
                raise fetch.FinancialFetchError("the provider hung up")
            return a_statement(symbol, part)

        scan(statement=statement)

        assert lines_for(FIRST) == 40
        assert lines_for(SECOND) == 0

    def test_a_part_that_fails_keeps_the_parts_before_it(self, two_symbols):
        """The cash flow timing out must not cost the income statement."""

        def statement(symbol, part):
            if part == fetch.STATEMENT_CASHFLOW:
                raise fetch.FinancialFetchError("the provider hung up")
            return a_statement(symbol, part)

        report = scan(statement=statement)

        assert report.failures == SYMBOLS
        assert lines_for(FIRST) == 32

    def test_an_empty_scope_is_a_warning_rather_than_a_crash(self, monkeypatch):
        monkeypatch.setattr(job, "scope_symbols", lambda session, scope: ())

        report = scan()

        assert report.symbols == []
        assert report.rows_written == 0

    def test_a_scope_the_cli_does_not_offer_is_refused(self):
        with pytest.raises(ValueError, match="not a scope"):
            job.run(scope="everything")

    def test_a_part_that_is_not_a_part_is_refused(self):
        with pytest.raises(ValueError, match="not parts"):
            job.run(scope="market", parts=("income", "equity"))


class TestCli:
    def test_the_scope_is_required_and_checked(self):
        with pytest.raises(SystemExit):
            job._parse_args([])
        with pytest.raises(SystemExit):
            job._parse_args(["--scope", "everything"])

    def test_the_parts_default_to_every_part(self):
        args = job._parse_args(["--scope", "declared"])

        assert args.scope == "declared"
        assert tuple(args.statements) == fetch.PARTS

    def test_a_subset_of_parts_can_be_asked_for(self):
        args = job._parse_args(
            ["--scope", "market", "--statements", "income", "balance"]
        )

        assert args.statements == ["income", "balance"]

    def test_a_part_the_cli_does_not_offer_is_refused(self):
        with pytest.raises(SystemExit):
            job._parse_args(["--scope", "market", "--statements", "equity"])

    def test_a_run_with_failures_exits_non_zero(self, monkeypatch):
        monkeypatch.setattr(
            job,
            "run",
            lambda **kwargs: job.ScanReport(
                scope="declared",
                parts=fetch.PARTS,
                symbols=[
                    job.SymbolReport(symbol=FIRST, error="the provider hung up")
                ],
            ),
        )

        assert job.main(["--scope", "declared"]) == 1

    def test_a_clean_run_exits_zero(self, monkeypatch):
        monkeypatch.setattr(
            job,
            "run",
            lambda **kwargs: job.ScanReport(scope="declared", parts=fetch.PARTS),
        )

        assert job.main(["--scope", "declared"]) == 0
