"""The three templates, resolved from real responses and checked by arithmetic.

The gate here is deliberately not "the provider labelled this line pretax
profit". SSI's ``business_income_tax_expenses`` is +1,528,966,041,130 for
2026-Q2 — a positive tax expense the size of its operating profit — so a test
that trusted labels would pass while storing nonsense. What is checked instead is
the identity every one of these responses satisfies:

    net_profit_loss_after_tax == pretax + tax_current + tax_deferred

and, for equity, agreement with a number that arrived by another path entirely:
``parent_equity_vnd`` in ``provider_snapshots``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.stocks.financial import fetch, templates
from src.stocks.financial.templates import Concept

from . import fixtures

PERIOD = fixtures.GOLDEN_PERIOD
QUARTERS = ("2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3")


def lines_for(symbol: str, period: str = PERIOD) -> dict[tuple[str, str], Decimal]:
    """One symbol's quarter as ``templates`` sees it: ``item_seq = 0`` only."""
    income, balance = {
        "STB": (fixtures.stb_income, fixtures.stb_balance),
        "SSI": (fixtures.ssi_income, fixtures.ssi_balance),
        "HPG": (fixtures.hpg_income, fixtures.hpg_balance),
    }[symbol]
    rows = fetch.statement_rows(
        symbol, fetch.STATEMENT_INCOME, income()
    ) + fetch.statement_rows(symbol, fetch.STATEMENT_BALANCE, balance())
    return {
        (row["statement"], row["item_id"]): row["value"]
        for row in rows
        if row["period"] == period and row["item_seq"] == 0
    }


class TestGoldenNetProfit:
    """Universal across the three templates, which is why phase 10 needs no map."""

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("STB", Decimal("1346691000000")),
            ("SSI", Decimal("1231884874326")),
            ("HPG", Decimal("6424474267094")),
        ],
    )
    def test_net_profit_is_the_reported_figure(self, symbol, expected):
        resolved = templates.resolve(Concept.NET_PROFIT, lines_for(symbol))

        assert resolved.value == expected
        assert resolved.item_id == "net_profit_loss_after_tax"
        assert resolved.basis == templates.BASIS_LABELLED


class TestGoldenPretaxProfit:
    def test_a_bank_reports_a_labelled_pretax_line(self):
        resolved = templates.resolve(Concept.PRETAX_PROFIT, lines_for("STB"))

        assert resolved.value == Decimal("2029891000000")
        assert resolved.item_id == "net_accounting_profit_loss_before_tax"
        assert resolved.basis == templates.BASIS_LABELLED

    def test_a_non_financial_company_reports_the_same_labelled_line(self):
        resolved = templates.resolve(Concept.PRETAX_PROFIT, lines_for("HPG"))

        assert resolved.value == Decimal("7184684207426")
        assert resolved.basis == templates.BASIS_LABELLED

    def test_a_securities_house_pretax_is_found_by_identity_not_by_label(self):
        """SSI has no labelled pretax line; its pretax arrives as a "tax expense".

        Accepted only because 1,528,966,041,130 − 301,667,112,228 +
        4,585,945,424 is 1,231,884,874,326 — the reported net profit to the dong.
        """
        resolved = templates.resolve(Concept.PRETAX_PROFIT, lines_for("SSI"))

        assert resolved.value == Decimal("1528966041130")
        assert resolved.item_id == "business_income_tax_expenses"
        assert resolved.basis == templates.BASIS_TAX_IDENTITY

    @pytest.mark.parametrize("symbol", ["STB", "SSI", "HPG"])
    @pytest.mark.parametrize("period", QUARTERS)
    def test_the_tax_identity_holds_for_every_resolved_quarter(self, symbol, period):
        lines = lines_for(symbol, period)
        pretax = templates.resolve(Concept.PRETAX_PROFIT, lines)
        net = templates.resolve(Concept.NET_PROFIT, lines)
        current = lines[templates.TAX_CURRENT_ITEM]
        deferred = lines[templates.TAX_DEFERRED_ITEM]

        assert not pretax.is_unknown
        assert not net.is_unknown
        assert net.value == pretax.value + current + deferred

    def test_a_real_tax_expense_is_not_mistaken_for_a_pretax_profit(self):
        """The identity gate is what keeps the fallback from lying.

        STB carries the same ``business_income_tax_expenses`` id, and there it
        really is the tax (−683,200,000,000). With the labelled pretax line
        removed the concept has to be unknown, not the tax figure.
        """
        lines = dict(lines_for("STB"))
        del lines[templates.PRETAX_ITEM]

        resolved = templates.resolve(Concept.PRETAX_PROFIT, lines)

        assert resolved.is_unknown
        assert resolved.basis == templates.BASIS_UNKNOWN

    def test_the_identity_is_not_tried_when_a_tax_line_is_missing(self):
        """A missing tax line read as zero would let the identity pass by luck."""
        lines = dict(lines_for("SSI"))
        del lines[templates.TAX_DEFERRED_ITEM]

        assert templates.resolve(Concept.PRETAX_PROFIT, lines).is_unknown


class TestGoldenEquity:
    def test_a_banks_equity_matches_the_number_stored_by_another_path(self):
        """The balance sheet and the ``fundamental`` snapshot agree to the dong."""
        resolved = templates.resolve(Concept.EQUITY, lines_for("STB"))

        assert resolved.value == Decimal(fixtures.STB_OWNERS_EQUITY_2026Q2)
        assert resolved.item_id == "owners_equity"

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("SSI", Decimal("40723958711514")),
            ("HPG", Decimal("141516026558331")),
        ],
    )
    def test_the_other_two_templates_report_the_same_line(self, symbol, expected):
        resolved = templates.resolve(Concept.EQUITY, lines_for(symbol))

        assert resolved.value == expected

    def test_the_shareholders_equity_line_is_not_the_one_taken(self):
        """SSI reports both, and they differ by ten trillion dong."""
        resolved = templates.resolve(Concept.EQUITY, lines_for("SSI"))

        assert resolved.value != Decimal("30396503767268")


class TestUnknown:
    @pytest.mark.parametrize(
        "concept,item",
        [
            (Concept.NET_PROFIT, templates.NET_PROFIT_ITEM),
            (Concept.PRETAX_PROFIT, templates.PRETAX_ITEM),
            (Concept.EQUITY, templates.EQUITY_ITEM),
        ],
    )
    def test_a_missing_line_resolves_to_unknown_and_never_to_a_substitute(
        self, concept, item
    ):
        lines = dict(lines_for("HPG"))
        del lines[item]

        resolved = templates.resolve(concept, lines)

        assert resolved.is_unknown
        assert resolved.value is None
        assert resolved.item_id is None
        assert resolved.basis == templates.BASIS_UNKNOWN

    def test_a_symbol_with_nothing_stored_is_three_unknowns(self):
        resolved = templates.resolve_all({})

        assert set(resolved) == set(templates.CONCEPTS)
        assert all(value.is_unknown for value in resolved.values())

    def test_a_concept_that_is_not_a_concept_is_refused(self):
        with pytest.raises(ValueError, match="not a concept"):
            templates.resolve("core_operating_result", lines_for("HPG"))
