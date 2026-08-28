"""The upsert and the two reads, against the database, on invented tickers.

The numbers are captured real responses; the symbols are not. A suite that wrote
statements for real companies from a stubbed provider would leave figures nothing
verified sitting under a name a reader trusts, so the shapes are proved on
tickers nothing else reads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select

from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.financial import fetch, reads, store
from src.stocks.financial.templates import Concept
from src.stocks.models import FinancialRatioSnapshot, FinancialStatementLine

from . import fixtures

BANK = "ZZFIN1"
BROKER = "ZZFIN2"
SYMBOLS = (BANK, BROKER)
PERIOD = fixtures.GOLDEN_PERIOD
OBSERVED_AT = datetime(2026, 8, 27, 22, 0, tzinfo=timezone.utc)


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


def statement_frame(symbol, statement):
    """A captured response per (invented) symbol and statement."""
    frames = {
        (BANK, fetch.STATEMENT_INCOME): fixtures.stb_income,
        (BANK, fetch.STATEMENT_BALANCE): fixtures.stb_balance,
        (BANK, fetch.STATEMENT_CASHFLOW): fixtures.stb_balance,
        (BROKER, fetch.STATEMENT_INCOME): fixtures.ssi_income,
        (BROKER, fetch.STATEMENT_BALANCE): fixtures.ssi_balance,
        (BROKER, fetch.STATEMENT_CASHFLOW): fixtures.ssi_balance,
    }
    return frames[(symbol, statement)]()


def ratio_frame(symbol):
    return fixtures.stb_ratio()


def ingest(symbol, parts=fetch.PARTS):
    with get_sync_db() as session:
        return store.ingest_symbol(
            session,
            symbol,
            parts=parts,
            fetch_statement=statement_frame,
            fetch_ratio=ratio_frame,
            observed_at=OBSERVED_AT,
        )


def stored_lines(symbol=BANK) -> int:
    with get_sync_db() as session:
        return session.execute(
            select(func.count(FinancialStatementLine.symbol)).where(
                FinancialStatementLine.symbol == symbol
            )
        ).scalar_one()


def stored_ratios(symbol=BANK) -> int:
    with get_sync_db() as session:
        return session.execute(
            select(func.count(FinancialRatioSnapshot.symbol)).where(
                FinancialRatioSnapshot.symbol == symbol
            )
        ).scalar_one()


class TestUpsert:
    def test_a_symbols_parts_are_written_once_each(self):
        outcome = ingest(BANK)

        assert outcome.calls == 4
        assert outcome.periods == ("2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3")
        # 6 income lines + 2 balance + 2 "cashflow" over four quarters, and the
        # three real quarters of the ratio response times seven ratios.
        assert stored_lines() == 40
        assert stored_ratios() == 21

    def test_a_second_ingest_writes_no_new_rows(self):
        """Resume comes from the store, so the write has to be idempotent."""
        ingest(BANK)
        before = stored_lines(), stored_ratios()
        ingest(BANK)

        assert (stored_lines(), stored_ratios()) == before

    def test_a_restated_figure_replaces_the_row_rather_than_joining_it(self):
        ingest(BANK, parts=(fetch.STATEMENT_INCOME,))
        restated = fixtures.stb_income()
        restated.loc[
            restated["item_id"] == "net_profit_loss_after_tax", "2026-Q2"
        ] = 1_400_000_000_000.0

        with get_sync_db() as session:
            store.write_statement_lines(
                session,
                fetch.statement_rows(
                    BANK, fetch.STATEMENT_INCOME, restated, observed_at=OBSERVED_AT
                ),
            )
            value = session.execute(
                select(FinancialStatementLine.value).where(
                    FinancialStatementLine.symbol == BANK,
                    FinancialStatementLine.period == PERIOD,
                    FinancialStatementLine.item_id == "net_profit_loss_after_tax",
                    FinancialStatementLine.item_seq == 0,
                )
            ).scalar_one()

        assert value == Decimal("1400000000000.0000")
        assert stored_lines() == 24

    def test_a_repeated_item_id_lands_as_two_rows_with_both_values(self):
        ingest(BROKER, parts=(fetch.STATEMENT_INCOME,))

        with get_sync_db() as session:
            rows = session.execute(
                select(
                    FinancialStatementLine.item_seq, FinancialStatementLine.value
                )
                .where(
                    FinancialStatementLine.symbol == BROKER,
                    FinancialStatementLine.period == PERIOD,
                    FinancialStatementLine.item_id
                    == "business_income_tax_deferred",
                )
                .order_by(FinancialStatementLine.item_seq)
            ).all()

        assert rows == [
            (0, Decimal("4585945424.0000")),
            (1, Decimal("758786600.0000")),
        ]

    def test_a_part_that_is_not_a_part_is_refused(self):
        with pytest.raises(fetch.FinancialFetchError, match="not parts of a scan"):
            ingest(BANK, parts=("income", "equity"))

    def test_an_empty_write_is_not_a_statement_at_all(self):
        with get_sync_db() as session:
            assert store.write_statement_lines(session, []) == 0
            assert store.write_ratio_lines(session, []) == 0


class TestReads:
    def test_the_quarters_come_back_newest_first(self):
        ingest(BANK, parts=(fetch.STATEMENT_INCOME,))

        with get_sync_db() as session:
            assert reads.periods_for(session, BANK) == (
                "2026-Q2",
                "2026-Q1",
                "2025-Q4",
                "2025-Q3",
            )
            assert reads.latest_period(session, BANK) == "2026-Q2"

    def test_one_quarters_lines_are_the_first_occurrence_only(self):
        ingest(BROKER, parts=(fetch.STATEMENT_INCOME,))

        with get_sync_db() as session:
            lines = reads.lines_for(session, BROKER, PERIOD)

        assert lines[("income", "business_income_tax_deferred")] == Decimal(
            "4585945424.0000"
        )

    def test_concepts_resolve_from_the_store(self):
        ingest(BANK, parts=(fetch.STATEMENT_INCOME, fetch.STATEMENT_BALANCE))

        with get_sync_db() as session:
            concepts = reads.concepts_for(session, BANK, PERIOD)

        assert concepts[Concept.NET_PROFIT].value == Decimal("1346691000000")
        assert concepts[Concept.EQUITY].value == Decimal(
            fixtures.STB_OWNERS_EQUITY_2026Q2
        )

    def test_one_quarter_across_the_market_answers_per_symbol(self):
        ingest(BANK, parts=(fetch.STATEMENT_INCOME, fetch.STATEMENT_BALANCE))
        ingest(BROKER, parts=(fetch.STATEMENT_INCOME, fetch.STATEMENT_BALANCE))

        with get_sync_db() as session:
            market = reads.concepts_for_period(session, PERIOD, symbols=SYMBOLS)

        assert set(market) == set(SYMBOLS)
        assert market[BANK][Concept.NET_PROFIT].value == Decimal("1346691000000")
        assert market[BROKER][Concept.PRETAX_PROFIT].value == Decimal(
            "1528966041130"
        )

    def test_a_symbol_without_the_balance_sheet_is_unknown_not_absent(self):
        """The screener has to tell "not scanned" from "scanned and missing"."""
        ingest(BANK, parts=(fetch.STATEMENT_INCOME,))

        with get_sync_db() as session:
            market = reads.concepts_for_period(session, PERIOD, symbols=SYMBOLS)

        assert BANK in market
        assert BROKER not in market
        assert market[BANK][Concept.EQUITY].is_unknown

    def test_an_empty_symbol_list_reads_nothing(self):
        with get_sync_db() as session:
            assert reads.concepts_for_period(session, PERIOD, symbols=[]) == {}

    def test_the_ratios_come_back_keyed_by_item_id(self):
        ingest(BANK, parts=(fetch.PART_RATIO,))

        with get_sync_db() as session:
            ratios = reads.ratios_for(session, BANK, PERIOD)

        assert ratios["pe_ratio"] == Decimal("8.7300")
        # KBS's convention: a percent, not a fraction.
        assert ratios["roe"] == Decimal("4.7400")
