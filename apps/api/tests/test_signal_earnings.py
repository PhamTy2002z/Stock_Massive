"""Three results figures, against the filings four industries actually filed.

Every number in this fixture was read out of the production statement store on
2026-08-28 and is written down here as it stands there, under the ticker that
filed it. That is deliberate and it is the only way this suite can do its job:
the risk these fields carry is not arithmetic, it is that a line one industry
files is a line another does not, and a synthetic market cannot be wrong about
that in the way a real one is.

**A refusal on every industry is a red test.** A global refusal is still a named
refusal, so a suite asserting "a number or a reason" would pass while all three
fields were dead — which is exactly how a field that reads a store nothing
populates ships. So the coverage test asserts a *number*, per industry, per
field, and the one industry that genuinely cannot answer is named with the code
it must answer with instead.

The industry facts asserted here, each measured rather than assumed:

* **A credit institution files no gross-profit line.** In 2026-Q2, thirty
  symbols file a net profit and no gross profit: twenty-eight banks and two
  finance companies filing the same form. So the bank rows below
  carry no ``gross_profit`` at all, and the trend field must say
  ``statement_line_missing`` for them rather than reach for a line that
  resembles one.
* **A bank's EPS is often filed as an exact zero beside a profit in
  trillions.** BID files a 2026-Q2 profit of 8.294 tỷ đồng and an EPS of
  ``0.0000``. Two fields over that one filing therefore have to disagree: the
  profit answers and the EPS refuses.
* **A newly filing company has no year-ago quarter.** V68 has exactly one
  quarter of income statement in the whole store. That is
  ``fundamental_not_stored`` and it is the right answer — widening the window
  until something is found would answer a different question.

The store here is the in-memory one the bar fixtures build, so nothing in this
file can reach or overwrite a collected row.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Mapping

import pytest
from sqlalchemy.orm import Session

from src.stocks.financial import STATEMENT_INCOME
from src.stocks.models import FinancialStatementLine
from src.stocks.providers import Exchange, PriceBasis
from src.stocks.signals.bars import prepare_bars
from src.stocks.signals.earnings import (
    EPS_BASIC_ITEM,
    GROSS_PROFIT_ITEM,
    NET_PROFIT_ITEM,
    TREND_QUARTERS,
    prior_year_period,
    quarterly_statements_for,
)
from src.stocks.signals.fields import (
    BarProjection,
    Claim,
    FieldKind,
    FieldSource,
    Unit,
)
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.registry import (
    EARNINGS_FIELDS,
    REGISTRY,
    registered_field,
    registry_version,
)
from src.stocks.signals.serving import serve_field

from .test_price_band import list_on, write_session
from .test_signal_registry import a_field, open_session as open_bar_store

OBSERVED_AT = datetime(2026, 8, 22, 3, 0, tzinfo=timezone.utc)
SOURCE = "vnstock"

#: The session a question is asked on, and the quarter that had ended by then.
CUTOFF = date(2026, 8, 21)
PERIOD = "2026-Q2"

#: A session two quarters earlier, for the rule that a window answered for an
#: old date may not see a filing nobody had then.
EARLIER_CUTOFF = date(2026, 5, 15)
EARLIER_PERIOD = "2026-Q1"

#: A session far enough past 2026-Q2 that narrating it as current is wrong.
LATE_CUTOFF = date(2027, 1, 15)

BANK = "bank"
MANUFACTURER = "manufacturer"
REAL_ESTATE = "real_estate"
BROKER = "broker"


@dataclass(frozen=True)
class Filed:
    """One symbol's income-statement lines, exactly as the store holds them.

    Three separate mappings rather than one nested table, because the absence of
    a whole line is the fact this fixture exists to carry: a bank's
    ``gross_profit`` is an empty mapping and reads as one.
    """

    symbol: str
    industry: str
    eps_basic_vnd: Mapping[str, float]
    net_profit_loss_after_tax: Mapping[str, float]
    gross_profit: Mapping[str, float] = dataclass_field(default_factory=dict)

    @property
    def lines(self) -> tuple[tuple[str, Mapping[str, float]], ...]:
        return (
            (EPS_BASIC_ITEM, self.eps_basic_vnd),
            (NET_PROFIT_ITEM, self.net_profit_loss_after_tax),
            (GROSS_PROFIT_ITEM, self.gross_profit),
        )


VCB = Filed(
    symbol="VCB",
    industry=BANK,
    eps_basic_vnd={
        "2026-Q2": 1740,
        "2026-Q1": 1132,
        "2025-Q4": 677,
        "2025-Q3": 1080,
        "2025-Q2": 1057,
    },
    net_profit_loss_after_tax={
        "2026-Q2": 14_550_959_000_000,
        "2026-Q1": 9_462_095_000_000,
        "2025-Q4": 8_633_290_000_000,
        "2025-Q3": 9_025_553_000_000,
        "2025-Q2": 8_837_371_000_000,
    },
)

#: The bank whose EPS the provider files as zero in four quarters of five.
BID = Filed(
    symbol="BID",
    industry=BANK,
    eps_basic_vnd={
        "2026-Q2": 0,
        "2026-Q1": 0,
        "2025-Q4": 3774,
        "2025-Q3": 0,
        "2025-Q2": 0,
    },
    net_profit_loss_after_tax={
        "2026-Q2": 8_294_916_000_000,
        "2026-Q1": 6_878_794_000_000,
        "2025-Q4": 11_489_771_000_000,
        "2025-Q3": 6_086_910_000_000,
        "2025-Q2": 6_898_187_000_000,
    },
)

VNM = Filed(
    symbol="VNM",
    industry=MANUFACTURER,
    eps_basic_vnd={
        "2026-Q2": 1369,
        "2026-Q1": 1051,
        "2025-Q4": 1224,
        "2025-Q3": 1084,
        "2025-Q2": 1046,
    },
    net_profit_loss_after_tax={
        "2026-Q2": 3_184_401_641_748,
        "2026-Q1": 2_458_221_002_532,
        "2025-Q4": 2_827_199_040_932,
        "2025-Q3": 2_510_532_743_203,
        "2025-Q2": 2_488_584_680_280,
    },
    gross_profit={
        "2026-Q2": 8_204_085_955_756,
        "2026-Q1": 6_895_926_044_077,
        "2025-Q4": 6_890_016_993_344,
        "2025-Q3": 7_087_296_836_168,
        "2025-Q2": 7_021_677_925_140,
    },
)

VHM = Filed(
    symbol="VHM",
    industry=REAL_ESTATE,
    eps_basic_vnd={
        "2026-Q2": 2749,
        "2026-Q1": 6221,
        "2025-Q4": 6697,
        # Filed as zero in a quarter whose profit was 4.435 tỷ đồng.
        "2025-Q3": 0,
        "2025-Q2": 1828,
    },
    net_profit_loss_after_tax={
        "2026-Q2": 26_466_595_000_000,
        "2026-Q1": 25_625_357_000_000,
        "2025-Q4": 28_021_703_000_000,
        "2025-Q3": 4_435_641_000_000,
        "2025-Q2": 8_225_398_000_000,
    },
    gross_profit={
        "2026-Q2": 34_732_371_000_000,
        "2026-Q1": 31_369_586_000_000,
        "2025-Q4": 34_533_262_000_000,
        "2025-Q3": 2_465_661_000_000,
        "2025-Q2": 4_185_719_000_000,
    },
)

VND = Filed(
    symbol="VND",
    industry=BROKER,
    eps_basic_vnd={
        "2026-Q2": 580,
        "2026-Q1": 358,
        "2025-Q4": 224,
        "2025-Q3": 610,
        "2025-Q2": 242,
    },
    net_profit_loss_after_tax={
        "2026-Q2": 882_551_882_480,
        "2026-Q1": 545_335_468_175,
        "2025-Q4": 341_996_405_383,
        "2025-Q3": 929_049_066_047,
        "2025-Q2": 368_509_571_219,
    },
    gross_profit={
        "2026-Q2": 1_537_317_559_644,
        "2026-Q1": 1_125_823_598_498,
        "2025-Q4": 884_662_703_036,
        "2025-Q3": 1_568_771_195_719,
        "2025-Q2": 828_306_142_252,
    },
)

#: The company with one filed quarter in the entire store.
V68 = Filed(
    symbol="V68",
    industry=MANUFACTURER,
    eps_basic_vnd={"2026-Q2": 106},
    net_profit_loss_after_tax={"2026-Q2": 3_489_231_052},
    gross_profit={"2026-Q2": 22_866_770_459},
)

MEASURED: tuple[Filed, ...] = (VCB, BID, VNM, VHM, VND, V68)

#: Which industries each field must answer with a number for, and it is a
#: number rather than "a number or a reason" on purpose.
REQUIRED_COVERAGE: Mapping[str, tuple[str, ...]] = {
    "earnings.eps_basic_yoy_pct": (BANK, MANUFACTURER, REAL_ESTATE, BROKER),
    "earnings.net_profit_yoy_pct": (BANK, MANUFACTURER, REAL_ESTATE, BROKER),
    # No bank: the line is not in a bank's filing, and the assertion about that
    # is its own test rather than a hole in this table.
    "earnings.gross_profit_trend": (MANUFACTURER, REAL_ESTATE, BROKER),
}


def open_store() -> Session:
    """The bar fixture's store, plus the statement table these fields read."""
    session = open_bar_store()
    FinancialStatementLine.__table__.create(session.get_bind())
    return session


def weekdays_ending(day: date, count: int) -> tuple[date, ...]:
    """``count`` weekdays up to and including ``day``, oldest first."""
    days: list[date] = []
    cursor = day
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(days))


#: Enough sessions for the window to have one, at each date a test asks about.
SESSION_RUNS = (
    weekdays_ending(EARLIER_CUTOFF, 5),
    weekdays_ending(CUTOFF, 5),
    weekdays_ending(LATE_CUTOFF, 5),
)


def plant_filings(session: Session, filed: Filed) -> None:
    for item_id, quarters in filed.lines:
        for period, value in quarters.items():
            session.add(
                FinancialStatementLine(
                    symbol=filed.symbol,
                    period=period,
                    statement=STATEMENT_INCOME,
                    item_id=item_id,
                    item_seq=0,
                    value=Decimal(str(value)),
                    source=SOURCE,
                    observed_at=OBSERVED_AT,
                )
            )
    session.flush()


def plant_market(session: Session) -> None:
    """Every measured symbol, with filings and with sessions to date them by.

    The sessions are flat and identical across symbols. They are not an input to
    any field here — they are what tells the serving path which day it is being
    asked about — and giving them shape would only invite a reader to look for
    one.
    """
    for filed in MEASURED:
        list_on(session, filed.symbol, Exchange.HOSE)
        for run in SESSION_RUNS:
            for day in run:
                write_session(
                    session,
                    filed.symbol,
                    day,
                    close=10_000,
                    volume=1_000_000,
                    basis=PriceBasis.ADJUSTED_AT_SOURCE,
                )
        plant_filings(session, filed)


def symbols_in(industry: str) -> tuple[Filed, ...]:
    return tuple(filed for filed in MEASURED if filed.industry == industry)


class TestTheResultsFieldsAnswerInEveryIndustryThatFilesTheLine:
    @pytest.mark.parametrize(
        "field_id,industries",
        tuple(REQUIRED_COVERAGE.items()),
        ids=tuple(REQUIRED_COVERAGE),
    )
    def test_at_least_one_symbol_per_industry_answers_with_a_number(
        self, field_id, industries
    ):
        """Per industry, and a number rather than an outcome.

        A field reading a store nothing populates refuses everywhere, and every
        one of those refusals has a name. Asserted this way, that state is red
        on the first industry instead of green on all four.
        """
        field = registered_field(field_id)
        with open_store() as session:
            plant_market(session)
            for industry in industries:
                answered = {
                    filed.symbol: serve_field(
                        session, filed.symbol, field, end=CUTOFF
                    )
                    for filed in symbols_in(industry)
                }
                numbers = {
                    symbol: value.value
                    for symbol, value in answered.items()
                    if value.value is not None
                }
                assert numbers, (
                    f"{field_id} answered with no number for any {industry}: "
                    + ", ".join(
                        f"{symbol}={value.refusal}"
                        for symbol, value in answered.items()
                    )
                )

    def test_a_bank_is_refused_the_gross_profit_line_it_does_not_file(self):
        """Thirty symbols file a net profit and no gross profit, every one a
        credit institution — twenty-eight banks and two finance companies.

        The refusal names the line rather than the store, because the store did
        collect this bank's statement — a reader sent to look for a missing
        filing would find one sitting there.
        """
        field = registered_field("earnings.gross_profit_trend")
        with open_store() as session:
            plant_market(session)
            for filed in symbols_in(BANK):
                value = serve_field(session, filed.symbol, field, end=CUTOFF)

                assert value.value is None, filed.symbol
                assert value.refusal is SignalIssue.STATEMENT_LINE_MISSING
                assert value.extras["statement_line"] == GROSS_PROFIT_ITEM

    def test_two_fields_over_one_filing_disagree_about_it(self):
        """BID's 2026-Q2: a profit of 8.294 tỷ đồng and an EPS of ``0.0000``.

        The store cannot tell an unreported line from a reported zero, so the
        two are read the same way and the reading is the conservative one. Read
        the other way, this filing would print an EPS unchanged year on year for
        a bank whose profit rose by a fifth.
        """
        with open_store() as session:
            plant_market(session)
            eps = serve_field(
                session,
                BID.symbol,
                registered_field("earnings.eps_basic_yoy_pct"),
                end=CUTOFF,
            )
            profit = serve_field(
                session,
                BID.symbol,
                registered_field("earnings.net_profit_yoy_pct"),
                end=CUTOFF,
            )

        assert eps.value is None
        assert eps.refusal is SignalIssue.STATEMENT_LINE_MISSING
        assert eps.extras["current_figure"] is None
        assert profit.value == pytest.approx(
            100.0
            * (
                BID.net_profit_loss_after_tax[PERIOD]
                - BID.net_profit_loss_after_tax[prior_year_period(PERIOD)]
            )
            / BID.net_profit_loss_after_tax[prior_year_period(PERIOD)]
        )


class TestWhatTheNumbersAre:
    def test_a_year_on_year_percentage_is_the_two_filings_and_nothing_else(self):
        """Pinned against the arithmetic rather than a recorded output."""
        with open_store() as session:
            plant_market(session)
            values = {
                filed.symbol: serve_field(
                    session,
                    filed.symbol,
                    registered_field("earnings.eps_basic_yoy_pct"),
                    end=CUTOFF,
                )
                for filed in (VCB, VNM, VHM, VND)
            }

        for filed in (VCB, VNM, VHM, VND):
            now = filed.eps_basic_vnd[PERIOD]
            year_ago = filed.eps_basic_vnd[prior_year_period(PERIOD)]
            answer = values[filed.symbol]

            assert answer.refusal is None, filed.symbol
            assert answer.value == pytest.approx(100.0 * (now - year_ago) / year_ago)
            assert answer.extras["period"] == PERIOD
            assert answer.extras["prior_period"] == prior_year_period(PERIOD)
            assert answer.extras["statement_line"] == EPS_BASIC_ITEM

    def test_the_trend_is_a_slope_over_four_quarters_against_their_own_level(self):
        """The slope, scaled by the level, so two sizes of company compare.

        Computed here from the four filings by the least-squares identity rather
        than copied from a run: over ``0, 1, 2, 3`` the denominator is five, and
        writing that out is what makes this an assertion about a formula.
        """
        with open_store() as session:
            plant_market(session)
            answer = serve_field(
                session,
                VNM.symbol,
                registered_field("earnings.gross_profit_trend"),
                end=CUTOFF,
            )

        quarters = ("2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2")
        series = [VNM.gross_profit[quarter] for quarter in quarters]
        level = sum(series) / len(series)
        slope = (
            sum(
                (index - 1.5) * (value - level)
                for index, value in enumerate(series)
            )
            / 5.0
        )

        assert answer.refusal is None
        assert answer.value == pytest.approx(100.0 * slope / level)
        assert answer.extras["periods"] == quarters
        assert answer.extras["average_level_vnd"] == pytest.approx(level)
        assert len(quarters) == TREND_QUARTERS

    def test_a_widening_and_a_narrowing_business_carry_opposite_signs(self):
        """The sign is the whole reading, so it is asserted as one.

        VHM's four quarters run 2.4 → 34.5 → 31.3 → 34.7 nghìn tỷ and VND's run
        1.568 → 0.884 → 1.125 → 1.537 nghìn tỷ: one rose off a weak quarter and
        the other ended roughly where it started, and the two must not both read
        as expansion.
        """
        with open_store() as session:
            plant_market(session)
            values = {
                filed.symbol: serve_field(
                    session,
                    filed.symbol,
                    registered_field("earnings.gross_profit_trend"),
                    end=CUTOFF,
                ).value
                for filed in (VHM, VND)
            }

        assert values[VHM.symbol] is not None and values[VHM.symbol] > 0
        assert values[VND.symbol] is not None
        assert values[VHM.symbol] > values[VND.symbol]


class TestWhatRefusesAndUnderWhichName:
    def test_a_company_with_one_filed_quarter_has_no_year_ago_quarter(self):
        """``fundamental_not_stored``, and that is the right answer.

        V68 has exactly one quarter of income statement in the store. The
        refusal names the quarter that is absent rather than the line, because
        the line is there — and widening the comparison until something is
        found would answer a question nobody asked.
        """
        with open_store() as session:
            plant_market(session)
            eps = serve_field(
                session,
                V68.symbol,
                registered_field("earnings.eps_basic_yoy_pct"),
                end=CUTOFF,
            )
            trend = serve_field(
                session,
                V68.symbol,
                registered_field("earnings.gross_profit_trend"),
                end=CUTOFF,
            )

        assert eps.refusal is SignalIssue.FUNDAMENTAL_NOT_STORED
        assert eps.extras["prior_period"] == prior_year_period(PERIOD)
        assert trend.refusal is SignalIssue.FUNDAMENTAL_NOT_STORED

    def test_a_symbol_with_no_filing_at_all_refuses_without_a_line_to_name(self):
        with open_store() as session:
            plant_market(session)
            list_on(session, "ZZZ", Exchange.HOSE)
            for day in SESSION_RUNS[1]:
                write_session(
                    session,
                    "ZZZ",
                    day,
                    close=10_000,
                    basis=PriceBasis.ADJUSTED_AT_SOURCE,
                )
            answer = serve_field(
                session,
                "ZZZ",
                registered_field("earnings.net_profit_yoy_pct"),
                end=CUTOFF,
            )

        assert answer.value is None
        assert answer.refusal is SignalIssue.FUNDAMENTAL_NOT_STORED
        assert answer.extras["statement_line"] == NET_PROFIT_ITEM

    def test_every_refusal_these_fields_can_raise_has_a_reader_sentence(self):
        """The codes are reused rather than invented, and this is why it matters.

        A refusal reaches a person as one Vietnamese sentence held per code. A
        field raising a code the sentence table does not hold reaches the screen
        as a blank, so the three codes these fields can raise are checked
        against the table rather than against a review.
        """
        from src.alpha.reasons import sentence_for

        for issue in (
            SignalIssue.FUNDAMENTAL_NOT_STORED,
            SignalIssue.STATEMENT_LINE_MISSING,
            SignalIssue.STALE_FUNDAMENTAL_PERIOD,
        ):
            assert sentence_for(issue).strip()


class TestWhichQuartersTheWindowMaySee:
    def test_a_window_answered_for_an_old_date_sees_only_the_older_quarters(self):
        """A filing nobody had then must not appear in an answer dated then.

        The same rule the snapshot store keeps, and the reason the cutoff is the
        window's newest session rather than today: a series recomputed backwards
        would otherwise walk the newest quarter into every point of its history.
        """
        with open_store() as session:
            plant_market(session)
            now = quarterly_statements_for(session, VNM.symbol, CUTOFF)
            earlier = quarterly_statements_for(session, VNM.symbol, EARLIER_CUTOFF)
            before_the_close = quarterly_statements_for(
                session, VNM.symbol, date(2026, 6, 29)
            )

        assert now is not None and now.newest == PERIOD
        assert earlier is not None and earlier.newest == EARLIER_PERIOD
        assert before_the_close is not None
        assert before_the_close.newest == EARLIER_PERIOD

    def test_the_field_moves_with_the_cutoff_rather_than_with_the_store(self):
        with open_store() as session:
            plant_market(session)
            field = registered_field("earnings.gross_profit_trend")
            now = serve_field(session, VNM.symbol, field, end=CUTOFF)
            earlier = serve_field(session, VNM.symbol, field, end=EARLIER_CUTOFF)

        assert now.refusal is None and earlier.refusal is None
        assert now.extras["period"] == PERIOD
        assert earlier.extras["period"] == EARLIER_PERIOD
        assert now.extras["periods"] != earlier.extras["periods"]

    def test_a_quarter_past_every_filing_deadline_degrades_the_answer(self):
        """Old and readable, which is a degradation and never a refusal.

        The number was true of its quarter. What changes is the reading of it,
        so the quarter and its age travel with the answer.
        """
        with open_store() as session:
            plant_market(session)
            answer = serve_field(
                session,
                VNM.symbol,
                registered_field("earnings.net_profit_yoy_pct"),
                end=LATE_CUTOFF,
            )

        assert answer.value is not None
        assert answer.degraded_reason is SignalIssue.STALE_FUNDAMENTAL_PERIOD
        assert answer.extras["period_age_days"] > 150


class TestHowTheResultsFieldsAreDeclared:
    def test_they_are_served_on_quantities_rather_than_prices(self):
        """No arithmetic here reads a price, so no price rule may refuse them.

        Asserted through the seam that still refuses: a window whose sessions do
        not share a price basis is meaningless for a close and says nothing at
        all about a filing.
        """
        with open_store() as session:
            plant_market(session)
            write_session(
                session,
                VNM.symbol,
                SESSION_RUNS[1][-1],
                close=10_000,
                basis=PriceBasis.RAW,
            )
            _, on_price = prepare_bars(
                session,
                VNM.symbol,
                5,
                end=CUTOFF,
                projection=BarProjection.PRICE,
            )
            answer = serve_field(
                session,
                VNM.symbol,
                registered_field("earnings.eps_basic_yoy_pct"),
                end=CUTOFF,
            )

        assert on_price.refusal is SignalIssue.MIXED_PRICE_BASIS
        assert answer.refusal is None
        assert answer.value is not None
        for field in EARNINGS_FIELDS:
            assert field.projection is BarProjection.VOLUME, field.name

    def test_each_one_is_a_stored_descriptive_percentage(self):
        """A figure read out of a filing, exact for the quarter it covers.

        ``stored`` rather than ``computed`` for the reason the factor ratios are:
        the caveat that belongs beside it is the age of the quarter and not a
        standard error, and that is the exemption ``FieldSource`` grants.
        """
        for field in EARNINGS_FIELDS:
            assert field.name.startswith("earnings."), field.name
            assert field.unit is Unit.PERCENT, field.name
            assert field.kind is FieldKind.VOCABULARY, field.name
            assert field.claim is Claim.DESCRIPTIVE, field.name
            assert field.source is FieldSource.STORED, field.name
            assert field.threshold is None and field.null_fpr is None, field.name
            assert field.requires_quarterly_statements, field.name
            assert REGISTRY[field.name] is field

    def test_a_ranked_field_may_not_ask_for_a_symbols_quarters(self):
        """The cross-sectional path loads one quarter for a whole sample.

        Declared there, these statements would never be loaded and the field
        would refuse for every member of every ranking — under a code naming the
        store rather than the declaration that caused it. So it is refused where
        it is written.
        """
        with pytest.raises(ValueError, match="ranked across a cross-section"):
            a_field(
                reading=None,
                ranked=lambda window: None,
                kind=FieldKind.PERCENTILE,
                requires_quarterly_statements=True,
            )

    def test_the_registry_digest_moves_when_these_fields_are_registered(
        self, monkeypatch
    ):
        """Derived from the declarations, never bumped by hand.

        A registry identity somebody has to remember to bump is one that
        eventually names the wrong registry, and it rides in the Evidence
        Manifest where being wrong is silent. So the assertion is that adding
        three fields moved it, made by taking them back out.
        """
        import src.stocks.signals.registry as registry_module

        with_them = registry_version()
        without = {
            name: entry
            for name, entry in REGISTRY.items()
            if not name.startswith("earnings.")
        }
        assert len(without) == len(REGISTRY) - len(EARNINGS_FIELDS)

        monkeypatch.setattr(registry_module, "REGISTRY", without)

        assert registry_version() != with_them
