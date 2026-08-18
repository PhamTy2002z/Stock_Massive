"""What the Analysis Field Profile is allowed to name, and what it may not.

The profile exists because the model does not get to choose freely from the
**Signal Registry**: the input bundle has to be stable, reviewable and bounded
(``CONTEXT.md``, spec 0003 §8.4). So the tests here are almost all about bounds
rather than about content — the cap per axis, the fixed axis order, the price
zone sitting outside the Technical slots, and the rule that a field the profile
names is emitted whether or not anything computes it yet.

That last one is the one worth stating: a profile field silently dropped would
make two Analyses carrying the same ``fieldProfileVersion`` mean two different
things, and nothing downstream could tell.
"""

from src.alpha.field_profile import (
    AXIS_ORDER,
    FIELD_PROFILE_VERSION,
    MAX_FIELDS_PER_AXIS,
    NEWS_FIELDS,
    PRICE_ZONE_FIELD_ID,
    AnalysisIndustry,
    Axis,
    industry_for_icb,
    profile_for,
)
from src.stocks.signals.registry import REGISTRY


class TestTheAxes:
    def test_the_order_is_the_invariant_one(self):
        assert AXIS_ORDER == (
            Axis.TECHNICAL,
            Axis.FUNDAMENTAL,
            Axis.MONEY_FLOW,
            Axis.NEWS,
        )

    def test_every_industry_gets_all_four_axes_in_that_order(self):
        for industry in AnalysisIndustry:
            assert tuple(profile_for(industry)) == AXIS_ORDER

    def test_no_axis_exceeds_the_cap_for_any_industry(self):
        for industry in AnalysisIndustry:
            for axis, fields in profile_for(industry).items():
                assert len(fields) <= MAX_FIELDS_PER_AXIS, (industry, axis)

    def test_no_axis_names_a_field_twice(self):
        for industry in AnalysisIndustry:
            named = [
                entry.field_id
                for fields in profile_for(industry).values()
                for entry in fields
            ]
            assert len(named) == len(set(named)), industry


class TestThePriceZone:
    def test_it_is_registered(self):
        assert PRICE_ZONE_FIELD_ID in REGISTRY

    def test_it_never_consumes_a_technical_slot(self):
        for industry in AnalysisIndustry:
            technical = profile_for(industry)[Axis.TECHNICAL]
            assert PRICE_ZONE_FIELD_ID not in {entry.field_id for entry in technical}


class TestWhatTheIndustriesAdd:
    def test_banks_add_their_three_metrics_to_the_shared_fundamentals(self):
        fundamental = _ids(AnalysisIndustry.BANKS, Axis.FUNDAMENTAL)
        assert fundamental == (
            "factor_percentiles.roe_percentile",
            "factor_percentiles.earnings_yield_percentile",
            "factor_percentiles.book_yield_percentile",
            "bank_metrics.nim_pct",
            "bank_metrics.npl_ratio_pct",
            "bank_metrics.llr_coverage_pct",
        )

    def test_real_estate_adds_two(self):
        assert _ids(AnalysisIndustry.REAL_ESTATE, Axis.FUNDAMENTAL)[3:] == (
            "developer_metrics.net_debt_to_ebitda",
            "developer_metrics.inventory_share_of_assets_pct",
        )

    def test_retail_adds_three(self):
        assert _ids(AnalysisIndustry.RETAIL, Axis.FUNDAMENTAL)[3:] == (
            "retail_metrics.gross_margin_pct",
            "retail_metrics.inventory_turnover_x",
            "retail_metrics.store_count",
        )

    def test_an_unclassified_symbol_gets_the_shared_fundamentals_and_nothing_else(self):
        assert len(_ids(AnalysisIndustry.UNCLASSIFIED, Axis.FUNDAMENTAL)) == 3
        assert len(_ids(AnalysisIndustry.OTHER, Axis.FUNDAMENTAL)) == 3


class TestWhatAnIcbCodeSelects:
    """Which fundamentals block a stored classification reaches for.

    Level 2 and no other level: the profile's three industries are ICB
    supersectors, and a level-3 or level-4 code read as one would select a block
    the code does not name.
    """

    def test_the_three_supersectors_the_profile_carries_metrics_for(self):
        assert industry_for_icb("8300") is AnalysisIndustry.BANKS
        assert industry_for_icb("8600") is AnalysisIndustry.REAL_ESTATE
        assert industry_for_icb("5300") is AnalysisIndustry.RETAIL

    def test_a_classified_code_with_no_block_of_its_own_is_other(self):
        assert industry_for_icb("1700") is AnalysisIndustry.OTHER

    def test_no_stored_code_is_unclassified_rather_than_other(self):
        """The store not knowing is a different fact from nothing extra to add."""
        assert industry_for_icb(None) is AnalysisIndustry.UNCLASSIFIED
        assert industry_for_icb("") is AnalysisIndustry.UNCLASSIFIED
        assert industry_for_icb("  ") is AnalysisIndustry.UNCLASSIFIED

    def test_a_code_stored_with_whitespace_still_selects_its_block(self):
        assert industry_for_icb(" 8300 ") is AnalysisIndustry.BANKS

    def test_a_deeper_icb_level_selects_no_block_of_its_own(self):
        """8355 is the level-4 code for banks, and the register stores level 2."""
        assert industry_for_icb("8355") is AnalysisIndustry.OTHER


class TestWhatIsRegisteredAndWhatIsNot:
    def test_every_technical_and_money_flow_field_has_a_computation_behind_it(self):
        for axis in (Axis.TECHNICAL, Axis.MONEY_FLOW):
            for entry in profile_for(AnalysisIndustry.OTHER)[axis]:
                assert entry.registered, entry.field_id
                assert entry.field_id in REGISTRY

    def test_the_shared_fundamentals_are_registered(self):
        for entry in profile_for(AnalysisIndustry.OTHER)[Axis.FUNDAMENTAL]:
            assert entry.registered, entry.field_id

    def test_the_industry_fundamentals_have_no_registered_computation_in_v1(self):
        for industry in (
            AnalysisIndustry.BANKS,
            AnalysisIndustry.REAL_ESTATE,
            AnalysisIndustry.RETAIL,
        ):
            for entry in profile_for(industry)[Axis.FUNDAMENTAL][3:]:
                assert not entry.registered, entry.field_id
                assert entry.field_id not in REGISTRY

    def test_neither_news_count_is_registered_in_v1(self):
        assert len(NEWS_FIELDS) == 2
        for entry in NEWS_FIELDS:
            assert not entry.registered, entry.field_id

    def test_an_unregistered_entry_still_declares_what_it_would_be(self):
        for industry in AnalysisIndustry:
            for fields in profile_for(industry).values():
                for entry in fields:
                    assert entry.label.strip()
                    assert entry.description.strip()


class TestTheVersion:
    def test_it_is_stated_rather_than_derived(self):
        assert FIELD_PROFILE_VERSION == "v1"


def _ids(industry: AnalysisIndustry, axis: Axis) -> tuple[str, ...]:
    return tuple(entry.field_id for entry in profile_for(industry)[axis])
