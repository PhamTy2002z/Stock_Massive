"""Where a symbol stands against the Universe, and what that ranking will not hide.

A cross-sectional field is the one place in this package where an answer about
one symbol depends on ninety-nine others, and almost everything that can go wrong
with it is a question of who was in the sample:

*A symbol with too little history is dropped with a reason, never hidden.* The
number ranked and the exclusions travel with every answer, because a ranking over
whoever happened to have data is a different ranking from one over the Universe
and nothing else on the wire would say so.

*Below thirty survivors the whole call refuses.* A percentile over eleven names
is a rank with a percent sign on it.

*The momentum window is 231 sessions of formation after skipping 21.* That is
French's prior (2-12) return, which the field is named for: a twelve-month
lookback with its most recent month left out. The inherited ``min_sessions`` of
273 described a thirteen-month lookback instead, so the two were never the same
window; the tests below pin the arithmetic to the constants so they cannot drift
apart again.

*Relative strength refuses rather than substituting.* There is no stored market
index, and the live price path's alias is not read to make the field look
available.

*A factor percentile carries the age of the quarter behind it*, and degrades
rather than being served flat once that quarter is old.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import (
    CohortMember,
    CohortVersion,
    CorporateAction,
    ListingRoster,
    ProviderSnapshot,
)
from src.stocks.providers import Exchange, ProviderSource
from src.stocks.providers.contracts import (
    Capability,
    FundamentalSnapshot,
    SnapshotMetadata,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.cross_sectional import (
    CROSS_SECTION_MIN_SYMBOLS,
    MOMENTUM_FORMATION_SESSIONS,
    MOMENTUM_MIN_FORMATION_SESSIONS,
    MOMENTUM_MIN_SESSIONS,
    MOMENTUM_SKIP_SESSIONS,
    TREND_YEAR_SESSIONS,
    momentum_return_pct,
    percentile_of,
    relative_strength_reading,
    trend_reading,
)
from src.stocks.signals.fields import Claim, FieldKind, Sign, Unit
from src.stocks.signals.fundamentals import (
    FUNDAMENTAL_STALE_DAYS,
    fundamentals_on_or_before,
)
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.registry import (
    BOOK_YIELD_PERCENTILE,
    CROSS_SECTIONAL_FIELDS,
    EARNINGS_YIELD_PERCENTILE,
    MOMENTUM_RANK,
    RELATIVE_STRENGTH,
    ROE_PERCENTILE,
    SIZE_PERCENTILE,
    TREND_SIGNAL,
)
from src.stocks.signals.serving import serve_cross_section, serve_field
from src.stocks.universe import forget_cohort_cache

from .signal_windows import window_of
from .test_market_behavior import frame_of, weekdays
from .test_price_band import list_on, write_session


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
        CohortVersion.__table__,
        CohortMember.__table__,
    ):
        table.create(engine)
    forget_cohort_cache()
    return Session(engine)


def store_flat(
    session: Session,
    symbol: str,
    days: list[date],
    *,
    close: float = 20_000.0,
    step: float = 0.0,
    market_cap: float | None = None,
) -> None:
    """One symbol trading at a fixed compounding step, every session inside its band.

    ``step`` is per session and stays far inside ±7%, so the gateway serves the
    window rather than refusing a move it cannot explain.
    """
    list_on(session, symbol, Exchange.HOSE)
    price = close
    for day in days:
        write_session(
            session,
            symbol,
            day,
            close=round(price, 2),
            high=round(price * 1.002, 2),
            low=round(price * 0.998, 2),
            open_price=round(price, 2),
            volume=800_000,
            total_value_vnd=16e9,
            market_cap_vnd=market_cap,
        )
        price *= 1.0 + step


def store_statement(
    session: Session,
    symbol: str,
    *,
    period_end: date,
    net_income: float | None,
    equity: float | None,
) -> None:
    snapshot = FundamentalSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=datetime.combine(period_end, time.min, tzinfo=VN_TZ),
            observed_at=datetime.combine(period_end, time.min, tzinfo=VN_TZ),
        ),
        period_end=period_end,
        trailing_12_month_net_income_vnd=net_income,
        parent_equity_vnd=equity,
    )
    session.add(
        ProviderSnapshot(
            capability=Capability.FUNDAMENTAL.value,
            symbol=symbol,
            source=ProviderSource.VNSTOCK.value,
            schema_version=1,
            effective_at=snapshot.metadata.effective_at,
            observed_at=snapshot.metadata.observed_at,
            payload=snapshot.model_dump(mode="json"),
        )
    )
    session.flush()


def a_sample(
    session: Session,
    *,
    count: int = 32,
    sessions: int,
    with_statements: bool = False,
    period_end: date | None = None,
) -> tuple[list[str], list[date]]:
    """A Universe-sized sample where every symbol moves at its own steady rate."""
    days = weekdays(sessions)
    names = [f"S{index:02d}" for index in range(count)]
    for index, name in enumerate(names):
        store_flat(
            session,
            name,
            days,
            step=0.0001 * index,
            market_cap=1e12 * (index + 1),
        )
        if with_statements:
            store_statement(
                session,
                name,
                period_end=period_end or (days[-1] - timedelta(days=40)),
                net_income=1e11 * (index + 1),
                equity=5e11 * (index + 1),
            )
    return names, days


class TestTheMomentumWindow:
    def test_the_formation_is_the_registered_sessions_after_the_registered_skip(self):
        """The lookback is the formation plus the skip, and both are pinned here.

        French's prior (2-12) return is a twelve-month lookback whose most
        recent month is skipped, so the formation is the eleven months inside
        it. Written as expressions of the trading year, the three constants
        cannot be edited apart — which is what the inherited 273 was.
        """
        assert MOMENTUM_MIN_SESSIONS == (
            MOMENTUM_FORMATION_SESSIONS + MOMENTUM_SKIP_SESSIONS
        )
        assert MOMENTUM_RANK.min_sessions == MOMENTUM_MIN_SESSIONS

        assert MOMENTUM_MIN_SESSIONS == TREND_YEAR_SESSIONS

        # A series that rises 1% a session for the formation and then falls for
        # the skipped month: the return read is the rise, never the fall.
        closes = [1000.0 * (1.01**index) for index in range(MOMENTUM_FORMATION_SESSIONS)]
        closes += [closes[-1] * (0.99**index) for index in range(1, MOMENTUM_SKIP_SESSIONS + 1)]

        value = momentum_return_pct(closes)

        expected = 100.0 * (1.01 ** (MOMENTUM_FORMATION_SESSIONS - 1) - 1.0)
        assert value == pytest.approx(expected, rel=1e-9)

    def test_the_most_recent_month_is_skipped_and_not_merely_shortened(self):
        """The skip steps around short-horizon reversal; it is not a rounding.

        A series that rose through its formation and gave some back over the
        last month: the skipped read sees only the rise, and a read of the same
        length ending today sees the giving back. Equal-length windows on a
        series that grew at one rate would not tell the two apart at all.
        """
        rising = [1000.0 * (1.005**index) for index in range(MOMENTUM_FORMATION_SESSIONS)]
        falling = [rising[-1] * (0.99**index) for index in range(1, MOMENTUM_SKIP_SESSIONS + 1)]
        series = rising + falling

        with_skip = momentum_return_pct(series)
        ending_today = momentum_return_pct(series, skip=0)

        assert with_skip is not None and ending_today is not None
        assert with_skip > ending_today

    def test_a_formation_under_a_month_is_refused_rather_than_ranked(self):
        """The documented refusal behind "never read a one-day rank".

        The band spreads one shock across consecutive limit sessions, so a short
        formation ranks a move that has not finished arriving.
        """
        closes = [1000.0 * (1.01**index) for index in range(60)]

        assert momentum_return_pct(closes, formation=1, skip=0) is None
        assert (
            momentum_return_pct(
                closes, formation=MOMENTUM_MIN_FORMATION_SESSIONS, skip=0
            )
            is not None
        )


class TestTheTrendSignal:
    def test_it_reports_a_sign_and_a_magnitude_for_each_window(self):
        closes = [1000.0 * (1.001**index) for index in range(TREND_YEAR_SESSIONS + 1)]

        reading = trend_reading(window_of(frame_of(closes)))

        assert reading.value is not None and reading.value > 0
        for label in ("3m", "6m", "12m"):
            assert reading.extras[f"sign_{label}"] == 1
            assert reading.extras[f"return_{label}_pct"] > 0

    def test_a_falling_symbol_reports_a_negative_sign(self):
        closes = [1000.0 * (0.999**index) for index in range(TREND_YEAR_SESSIONS + 1)]

        reading = trend_reading(window_of(frame_of(closes)))

        assert reading.extras["sign_12m"] == -1
        assert reading.value < 0

    def test_the_futures_caveat_is_in_the_field_contract_not_only_the_narration(self):
        """The model reads the contract before it decides to call at all."""
        assert "futures" in TREND_SIGNAL.interpretation.lower()
        assert "extrapolation" in TREND_SIGNAL.interpretation.lower()

    def test_the_estimator_ships_its_uncertainty(self):
        closes = [
            1000.0 * (1.001**index) * (1.0 + 0.01 * (index % 5))
            for index in range(TREND_YEAR_SESSIONS + 1)
        ]

        reading = trend_reading(window_of(frame_of(closes)))

        assert reading.extras["standard_error"] > 0


class TestRelativeStrength:
    def test_it_refuses_and_names_the_input_it_is_short_of(self):
        reading = relative_strength_reading(window_of(frame_of([1000.0] * 30)))

        assert reading.value is None
        assert reading.refusal is SignalIssue.UNAVAILABLE
        assert reading.extras["benchmark"] == "VNINDEX"
        assert "market index" in reading.extras["missing_input"]

    def test_the_refusal_survives_being_served(self):
        """A refusal that lost its reason on the way out would be a silent drop."""
        with open_session() as session:
            names, days = a_sample(session, count=1, sessions=5)

            value = serve_field(session, names[0], RELATIVE_STRENGTH, end=days[-1])

        assert value.value is None
        # The window is short of the benchmark field's own history, and that
        # refusal is the gateway's rather than the field's — both are honest and
        # neither invents a beta.
        assert value.refusal in (
            SignalIssue.UNAVAILABLE,
            SignalIssue.INSUFFICIENT_HISTORY,
        )

    def test_no_live_provider_read_is_substituted(self):
        """Named here because the failure it guards is a silent one.

        The VN-Index exists in this codebase only as an alias inside the live
        price service. Reading it here would make the field look available while
        answering from a path that touches a Provider Source, which is what the
        spec's prerequisite section forbids.
        """
        import src.stocks.signals.cross_sectional as module

        source = module.__file__
        with open(source, encoding="utf-8") as handle:
            text = handle.read()

        assert "PriceService" not in text
        assert "price.service" not in text


class TestServingACrossSection:
    def test_every_symbol_is_ranked_within_the_same_sample_on_the_same_date(self):
        with open_session() as session:
            names, days = a_sample(session, sessions=MOMENTUM_MIN_SESSIONS + 5)

            section = serve_cross_section(
                session, names, MOMENTUM_RANK, end=days[-1]
            )

        assert section.refusal is None
        assert section.ranked == len(names)
        assert section.as_of == days[-1]
        for name in names:
            assert section.values[name].extras["n"] == len(names)
            assert section.values[name].extras["as_of"] == days[-1].isoformat()

    def test_the_ranking_orders_the_sample_it_was_given(self):
        """S00 is flat and S31 rises fastest, so the percentiles run with them."""
        with open_session() as session:
            names, days = a_sample(session, sessions=MOMENTUM_MIN_SESSIONS + 5)

            section = serve_cross_section(
                session, names, MOMENTUM_RANK, end=days[-1]
            )

        assert section.values["S31"].value == pytest.approx(100.0)
        assert section.values["S00"].value < section.values["S31"].value

    def test_a_short_history_symbol_is_excluded_with_a_reason_and_counted(self):
        """Dropped, never hidden: the reason is what tells a warm-up apart."""
        with open_session() as session:
            names, days = a_sample(session, sessions=MOMENTUM_MIN_SESSIONS + 5)
            store_flat(session, "NEW", days[-20:])

            section = serve_cross_section(
                session, [*names, "NEW"], MOMENTUM_RANK, end=days[-1]
            )

        assert "NEW" not in section.values
        assert section.excluded["NEW"] is SignalIssue.INSUFFICIENT_HISTORY
        assert section.ranked == len(names)
        assert section.values["S00"].extras["excluded_symbols"] == 1

    def test_the_whole_call_refuses_below_thirty_survivors(self):
        """A percentile over eleven names is a rank with a percent sign on it."""
        with open_session() as session:
            names, days = a_sample(
                session, count=11, sessions=MOMENTUM_MIN_SESSIONS + 5
            )

            section = serve_cross_section(
                session, names, MOMENTUM_RANK, end=days[-1]
            )

        assert section.refusal is SignalIssue.INSUFFICIENT_CROSS_SECTION
        assert section.values == {}
        assert section.ranked == 11
        assert CROSS_SECTION_MIN_SYMBOLS == 30

    def test_the_refusal_counts_survivors_after_exclusion_and_not_before(self):
        """Thirty-two names of which most are too short is not a cross-section."""
        with open_session() as session:
            names, days = a_sample(session, sessions=MOMENTUM_MIN_SESSIONS + 5)
            short = [f"N{index:02d}" for index in range(10)]
            for name in short:
                store_flat(session, name, days[-20:])

            section = serve_cross_section(
                session, [*names[:20], *short], MOMENTUM_RANK, end=days[-1]
            )

        assert section.refusal is SignalIssue.INSUFFICIENT_CROSS_SECTION
        assert len(section.excluded) == 10

    def test_a_field_answered_for_one_symbol_is_not_served_as_a_cross_section(self):
        with open_session() as session:
            with pytest.raises(ValueError):
                serve_cross_section(session, ["AAA"], TREND_SIGNAL)


class TestTheFactorPercentiles:
    def test_each_factor_ranks_the_universe_and_stamps_its_quarter(self):
        with open_session() as session:
            # The quarter has to have closed before the sessions being ranked:
            # a cutoff cannot read a statement nobody had yet.
            period_end = date(2023, 12, 31)
            names, days = a_sample(
                session,
                sessions=30,
                with_statements=True,
                period_end=period_end,
            )

            sections = {
                field.name: serve_cross_section(session, names, field, end=days[-1])
                for field in (
                    EARNINGS_YIELD_PERCENTILE,
                    BOOK_YIELD_PERCENTILE,
                    ROE_PERCENTILE,
                    SIZE_PERCENTILE,
                )
            }

        for name, section in sections.items():
            assert section.refusal is None, name
            assert section.ranked == len(names), name

        stamped = sections["factor_percentiles.roe_percentile"].values["S00"]
        assert stamped.extras["period_end"] == period_end.isoformat()
        assert stamped.extras["period_age_days"] > 0

    def test_size_is_ranked_large_first(self):
        """A departure from the shortlist, and a deliberate one.

        The research declares "+ = smaller", which folds the small-cap premium
        into the sign. A premium is a claim about returns and a descriptive
        field does not make one, so the percentile means what it says.
        """
        with open_session() as session:
            names, days = a_sample(session, sessions=30, with_statements=True)

            section = serve_cross_section(
                session, names, SIZE_PERCENTILE, end=days[-1]
            )

        assert section.values["S31"].value == pytest.approx(100.0)
        assert section.values["S00"].value < section.values["S31"].value
        assert "higher means larger" in SIZE_PERCENTILE.interpretation.lower()

    def test_a_stale_quarter_is_degraded_rather_than_narrated_as_current(self):
        with open_session() as session:
            days = weekdays(30)
            stale = days[-1] - timedelta(days=FUNDAMENTAL_STALE_DAYS + 30)
            names, _ = a_sample(
                session, sessions=30, with_statements=True, period_end=stale
            )

            section = serve_cross_section(
                session, names, ROE_PERCENTILE, end=days[-1]
            )

        assert section.refusal is None
        for value in section.values.values():
            assert value.degraded_reason is SignalIssue.STALE_FUNDAMENTAL_PERIOD

    def test_a_symbol_with_no_stored_statement_is_excluded_with_its_own_reason(self):
        """Different from a short history, and stays different."""
        with open_session() as session:
            names, days = a_sample(session, sessions=30, with_statements=True)
            store_flat(session, "NOFIN", days, market_cap=1e12)

            section = serve_cross_section(
                session, [*names, "NOFIN"], ROE_PERCENTILE, end=days[-1]
            )

        assert section.excluded["NOFIN"] is SignalIssue.FUNDAMENTAL_NOT_STORED

    def test_the_statement_read_takes_the_newest_quarter_at_or_before_the_cutoff(self):
        """A cutoff in the past must not acquire a quarter nobody had yet."""
        with open_session() as session:
            store_statement(
                session,
                "AAA",
                period_end=date(2024, 3, 31),
                net_income=1.0,
                equity=2.0,
            )
            store_statement(
                session,
                "AAA",
                period_end=date(2024, 6, 30),
                net_income=3.0,
                equity=4.0,
            )

            early = fundamentals_on_or_before(session, ["AAA"], date(2024, 5, 1))
            late = fundamentals_on_or_before(session, ["AAA"], date(2024, 8, 1))

        assert early["AAA"].period_end == date(2024, 3, 31)
        assert late["AAA"].period_end == date(2024, 6, 30)
        assert late["AAA"].age_days == (date(2024, 8, 1) - date(2024, 6, 30)).days


class TestTheClusterContract:
    def test_every_field_is_descriptive_and_points_nowhere(self):
        for field in CROSS_SECTIONAL_FIELDS:
            assert field.claim is Claim.DESCRIPTIVE

    def test_no_field_in_the_cluster_fires(self):
        """A rank is self-calibrating and a refusal has nothing to fire on."""
        for field in CROSS_SECTIONAL_FIELDS:
            assert field.threshold is None
            assert field.null_fpr is None
            assert field.kind is not FieldKind.SIGNAL

    def test_a_ranked_field_answers_with_a_percentile_and_nothing_else(self):
        for field in CROSS_SECTIONAL_FIELDS:
            if field.ranked is None:
                continue
            assert field.kind is FieldKind.PERCENTILE
            assert field.unit is Unit.PERCENTILE
            assert field.sign is Sign.NON_NEGATIVE

    def test_a_percentile_counts_ties_as_below_it(self):
        assert percentile_of(5.0, [1.0, 5.0, 9.0]) == pytest.approx(200.0 / 3.0)
        assert percentile_of(9.0, [1.0, 5.0, 9.0]) == pytest.approx(100.0)
