"""Wide to long: the occurrence index, the repeated period, and what is refused.

Every frame here is a captured response, never the network. Their awkward shapes
— one ``item_id`` twice, one period twice — are the reason this code exists, so a
tidied fixture would test nothing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest

from src.stocks.financial import fetch

from . import fixtures

OBSERVED_AT = datetime(2026, 8, 27, 22, 0, tzinfo=timezone.utc)


def rows_for(frame, statement=fetch.STATEMENT_INCOME, symbol="STB"):
    return fetch.statement_rows(symbol, statement, frame, observed_at=OBSERVED_AT)


def by_key(rows):
    return {
        (row["period"], row["item_id"], row["item_seq"]): row["value"] for row in rows
    }


class TestStatementNormalisation:
    def test_every_line_of_every_quarter_becomes_a_row(self):
        rows = rows_for(fixtures.stb_income())

        # Six lines across the four quarters the community tier answers with.
        assert len(rows) == 24
        assert {row["period"] for row in rows} == {
            "2026-Q2",
            "2026-Q1",
            "2025-Q4",
            "2025-Q3",
        }
        assert {row["statement"] for row in rows} == {fetch.STATEMENT_INCOME}
        assert {row["source"] for row in rows} == {fetch.SOURCE_STATEMENT}
        assert {row["observed_at"] for row in rows} == {OBSERVED_AT}

    def test_a_value_keeps_the_number_the_provider_reported(self):
        values = by_key(rows_for(fixtures.stb_income()))

        assert values[("2026-Q2", "net_profit_loss_after_tax", 0)] == Decimal(
            "1346691000000.0000"
        )
        # A loss stays a loss: the quarter the bank wrote off credit.
        assert values[("2025-Q4", "net_profit_loss_after_tax", 0)] == Decimal(
            "-2752462000000.0000"
        )

    def test_the_symbol_is_upper_cased(self):
        rows = rows_for(fixtures.hpg_income(), symbol="hpg")

        assert {row["symbol"] for row in rows} == {"HPG"}

    def test_a_repeated_item_id_keeps_both_numbers(self):
        """The provider's own response holds one id twice, with different values.

        SSI's second ``business_income_tax_deferred`` row is the minority
        interest line arriving under another line's id. "Last row wins" would
        drop 4,585,945,424 and store 758,786,600 as the deferred tax.
        """
        values = by_key(rows_for(fixtures.ssi_income(), symbol="SSI"))

        assert values[("2026-Q2", "business_income_tax_deferred", 0)] == Decimal(
            "4585945424.0000"
        )
        assert values[("2026-Q2", "business_income_tax_deferred", 1)] == Decimal(
            "758786600.0000"
        )

    def test_the_occurrence_index_is_per_response_not_per_quarter(self):
        """The same line holds the same sequence in every quarter's column.

        Otherwise a reader asking for ``item_seq = 0`` would follow a different
        line from quarter to quarter.
        """
        values = by_key(rows_for(fixtures.ssi_income(), symbol="SSI"))

        for period in ("2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3"):
            assert ("business_income_tax_deferred", 0) in {
                (item_id, seq)
                for stored_period, item_id, seq in values
                if stored_period == period
            }
        assert values[("2025-Q3", "business_income_tax_deferred", 1)] == Decimal(
            "470785705.0000"
        )

    def test_four_repeats_of_one_line_are_four_rows(self):
        rows = rows_for(
            fixtures.ssi_balance(), statement=fetch.STATEMENT_BALANCE, symbol="SSI"
        )
        depreciation = [
            row
            for row in rows
            if row["item_id"] == "accumulated_depreciation"
            and row["period"] == "2026-Q2"
        ]

        assert sorted(row["item_seq"] for row in depreciation) == [0, 1, 2, 3]
        assert [row["value"] for row in depreciation] == [
            Decimal("-337183966640.0000"),
            Decimal("0.0000"),
            Decimal("-244903394361.0000"),
            Decimal("-104659706736.0000"),
        ]

    def test_an_empty_cell_is_left_out_rather_than_stored_as_zero(self):
        frame = fixtures.hpg_income()
        frame.loc[frame["item_id"] == "net_sales", "2025-Q3"] = None

        values = by_key(rows_for(frame, symbol="HPG"))

        assert ("2025-Q3", "net_sales", 0) not in values
        assert ("2026-Q2", "net_sales", 0) in values


class TestPeriodColumns:
    def test_a_repeated_period_keeps_only_the_first_column(self):
        """Measured: the ``2025-Q4_1`` column repeats 2026-Q2's values exactly.

        One of the two labels is wrong and there is no way to tell which, so the
        later column is dropped and only three quarters of ratios are real.
        """
        rows = fetch.ratio_rows("STB", fixtures.stb_ratio(), observed_at=OBSERVED_AT)
        values = by_key(rows)

        assert {row["period"] for row in rows} == {"2026-Q2", "2026-Q1", "2025-Q4"}
        assert values[("2025-Q4", "pe_ratio", 0)] == Decimal("6.6400")
        assert values[("2026-Q2", "pe_ratio", 0)] == Decimal("8.7300")

    def test_ratio_rows_record_the_source_whose_units_they_follow(self):
        """KBS reports ROE as a percent where VCI reports the same as a fraction."""
        rows = fetch.ratio_rows("STB", fixtures.stb_ratio(), observed_at=OBSERVED_AT)
        values = by_key(rows)

        assert {row["source"] for row in rows} == {fetch.SOURCE_RATIO}
        assert values[("2026-Q2", "roe", 0)] == Decimal("4.7400")

    def test_a_column_that_is_not_a_quarter_is_ignored(self):
        frame = fixtures.stb_balance()
        frame["ticker"] = "STB"

        rows = rows_for(frame, statement=fetch.STATEMENT_BALANCE)

        assert {row["period"] for row in rows} == {
            "2026-Q2",
            "2026-Q1",
            "2025-Q4",
            "2025-Q3",
        }

    def test_a_response_with_no_quarter_at_all_is_refused(self):
        frame = pd.DataFrame({"item": ["x"], "item_en": ["x"], "item_id": ["x"]})

        with pytest.raises(fetch.FinancialFetchError, match="no quarter column"):
            rows_for(frame)

    def test_a_response_without_item_id_is_refused(self):
        frame = fixtures.stb_income().drop(columns=["item_id"])

        with pytest.raises(fetch.FinancialFetchError, match="without item_id"):
            rows_for(frame)

    def test_a_statement_that_is_not_a_statement_is_refused(self):
        with pytest.raises(fetch.FinancialFetchError, match="not a statement"):
            rows_for(fixtures.stb_income(), statement="equity")


class TestProviderClient:
    def test_a_client_the_provider_will_not_open_raises(self, monkeypatch):
        """A constructor that exits the process must not end a market-wide scan.

        vnstock calls ``sys.exit()`` when it decides it has had enough, from the
        constructor as well as from the call, and ``SystemExit`` is a
        ``BaseException`` that the job's per-symbol ``except Exception`` cannot
        see. Built through the wrapper, the exit becomes a retry and then an
        ordinary failure that costs one symbol.
        """
        monkeypatch.setattr(fetch, "safe_vnstock_call", lambda *args, **kwargs: None)

        with pytest.raises(fetch.FinancialFetchError, match="would not open"):
            fetch.fetch_statement("STB", fetch.STATEMENT_INCOME)

        with pytest.raises(fetch.FinancialFetchError, match="would not open"):
            fetch.fetch_ratio("STB")
