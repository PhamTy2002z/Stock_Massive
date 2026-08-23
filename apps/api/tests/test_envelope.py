"""What the evidence envelope owns, and what it refuses to invent.

The envelope is the whole reason an Analysis can be argued with: every number a
reader sees came out of it, and it was built from stored rows and registered
**Signal Field**s alone. So the tests here are almost all about honesty rather
than about arithmetic —

*A field nothing computes is emitted refused, never dropped.* Two Analyses
carrying the same ``fieldProfileVersion`` have to mean the same thing, and a
silently missing field is exactly how they stop meaning it.

*Section health is derived, never supplied.* It is a property of the figures, so
"the model does not choose section health" is a fact about the type rather than a
rule somebody has to remember.

*The nightly lane does not touch a live service.* Proven twice — statically, by
reading what this module is allowed to import, and dynamically, by making every
live seam explode if it is reached.

*A wrong-day Snapshot is a failure, not a degradation.* Relabelling yesterday is
the one thing the availability deadline may never buy.

Run against SQLite in memory: nothing here needs what Postgres refuses, and the
store is the three tables the gateway reads.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.alpha.envelope import (
    EvidenceFigure,
    EvidenceSection,
    Health,
    build_envelope,
    measure_cross_sections,
    price_zone_entry,
    ranked_field_ids,
    stored_industry,
)
from src.alpha.field_profile import (
    AXIS_ORDER,
    FIELD_PROFILE_VERSION,
    PRICE_ZONE_FIELD_ID,
    AnalysisIndustry,
    Axis,
    profile_for,
)
from src.alpha.producer import ProductionFailure
from src.alpha.reasons import SIGNAL_ISSUE_SENTENCES
from src.stocks.models import (
    CohortMember,
    CohortVersion,
    CorporateAction,
    ListingRoster,
    ProviderSnapshot,
)
from src.stocks.providers import Exchange, PriceBasis, ProviderSource
from src.stocks.providers.contracts import (
    Capability,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SnapshotMetadata,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.fields import min_sample_for
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.reference import REFERENCE_STALE_DAYS
from src.stocks.universe import forget_cohort_cache

from .test_cross_sectional import store_statement
from .test_price_band import list_on, write_session

SYMBOL = "ENVSYM"
# Before the clock `write_session` stamps an observation with: a session cannot
# have been effective after it was observed, and the shared helper is what makes
# these rows the same shape as every other test's.
TRADING_DAY = date(2026, 8, 12)

# Long enough for every single-symbol field the profile names: the deepest is
# `drawdown_stats.current_drawdown_pct` at 250 sessions. Written as weekdays,
# because the store's own definition of a Trading Day is a day it holds a
# session for.
SESSIONS = 320

# The sample a percentile needs to mean anything, plus enough headroom that one
# excluded member does not collapse the whole ranking. Solved rather than
# asserted: the floor is a share of the sample, so a size satisfying it is the
# smallest one where ``min_sample_for(size) <= size``.
PEER_COUNT = next(size for size in range(1, 200) if min_sample_for(size) <= size) + 2
PEERS = tuple(f"ENVP{index:02d}" for index in range(PEER_COUNT))

FOREIGN_ROOM_FIELD = "company_profile.foreign_room_pct"
MOMENTUM_FIELD = "momentum_rank.percentile_12_2"
ROE_FIELD = "factor_percentiles.roe_percentile"


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


def weekdays_back(last: date, count: int) -> tuple[date, ...]:
    """``count`` weekdays ending on ``last``, oldest first."""
    days: list[date] = []
    cursor = last
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(days))


def store_window(
    session: Session,
    symbol: str = SYMBOL,
    *,
    last: date = TRADING_DAY,
    count: int = SESSIONS,
    basis: PriceBasis | None = None,
) -> tuple[date, ...]:
    """A window that moves a little every session and never breaks its band.

    A flat series is not a usable fixture here: a range estimator over one is
    refused for a zero range, so the sessions drift by a few tenths of a percent
    — far inside the 7% HOSE band, and far enough that Yang-Zhang has something
    to measure.
    """
    list_on(session, symbol, Exchange.HOSE)
    days = weekdays_back(last, count)
    for index, day in enumerate(days):
        close = 20_000.0 + 40.0 * (index % 7)
        write_session(
            session,
            symbol,
            day,
            close=close,
            high=close * 1.004,
            low=close * 0.996,
            total_value_vnd=8_000_000_000.0,
            market_cap_vnd=2e12,
            basis=basis,
        )
    return days


def store_foreign_room(
    session: Session,
    symbol: str = SYMBOL,
    *,
    read_on: date = TRADING_DAY,
    current: int = 300_000,
    total: int = 1_000_000,
) -> None:
    """One reference reading of the foreign room, dated by the day it was read."""
    stamp = datetime.combine(read_on, time.min, tzinfo=VN_TZ)
    snapshot = ReferenceSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=stamp,
            observed_at=stamp,
        ),
        shares=(ShareCount(share_type=ShareType.OUTSTANDING, value=total),),
        current_foreign_room=current,
        total_foreign_room=total,
    )
    session.add(
        ProviderSnapshot(
            capability=Capability.REFERENCE.value,
            symbol=symbol,
            source=ProviderSource.VNSTOCK.value,
            schema_version=1,
            effective_at=stamp,
            observed_at=stamp,
            payload=snapshot.model_dump(mode="json"),
        )
    )
    session.flush()


def store_peers(session: Session, *, period_end: date | None = None) -> tuple[str, ...]:
    """A cross-section big enough to rank in, each member on its own numbers.

    Three sessions each, because the factor fields declare a one-session window:
    what a percentile over them needs is a market cap and a statement, not a
    history. A ranking of identical companies is a ranking nobody can read, so
    the profitability rises across the sample.
    """
    days = weekdays_back(TRADING_DAY, 3)
    for index, name in enumerate(PEERS):
        list_on(session, name, Exchange.HOSE)
        for day in days:
            write_session(
                session,
                name,
                day,
                close=15_000.0 + 10.0 * index,
                total_value_vnd=4_000_000_000.0,
                market_cap_vnd=1e12 * (index + 1),
            )
        store_statement(
            session,
            name,
            period_end=period_end or (TRADING_DAY - timedelta(days=40)),
            net_income=1e11 * (index + 1),
            equity=5e11 * (index + 1),
        )
    return PEERS


def classify(
    session: Session,
    symbol: str = SYMBOL,
    *,
    icb_code: str | None = None,
    icb_name: str | None = None,
) -> None:
    """Stamp the register's ICB classification onto an already listed symbol.

    The row itself rather than a roster refresh: a refresh is a picture of the
    whole market and would delist every peer this fixture just listed.
    """
    row = session.get(ListingRoster, symbol)
    row.icb_code = icb_code
    row.icb_name = icb_name
    session.flush()


def a_figure(health: Health, *, value: float | None = 1.0) -> EvidenceFigure:
    """One figure in a stated health, for the section-health rules alone."""
    return EvidenceFigure(
        field_id="x.y",
        label="X",
        value=None if health is Health.REFUSED else value,
        unit=None,
        kind=None,
        source=None,
        interpretation="…",
        health=health,
        reason_code=None if health is Health.OK else SignalIssue.UNAVAILABLE.value,
        reason=None if health is Health.OK else "…",
        as_of=None,
        sessions_used=None,
        window_days=None,
        extras={},
    )


def a_section(*healths: Health) -> EvidenceSection:
    return EvidenceSection(
        axis=Axis.TECHNICAL, figures=tuple(a_figure(health) for health in healths)
    )


@pytest.fixture
def stored():
    """A symbol with a full window and a fresh foreign room."""
    session = open_session()
    store_window(session)
    store_foreign_room(session)
    yield session
    session.close()


@pytest.fixture
def envelope(stored):
    return build_envelope(stored, SYMBOL, TRADING_DAY, cross_sections={})


class TestTheShape:
    def test_the_four_axes_arrive_in_the_invariant_order(self, envelope):
        assert tuple(section.axis for section in envelope.sections) == AXIS_ORDER

    def test_it_is_stamped_with_the_profile_version_it_was_built_from(self, envelope):
        assert envelope.field_profile_version == FIELD_PROFILE_VERSION

    def test_the_price_zone_travels_outside_the_technical_slots(self, envelope):
        assert envelope.price_zone.field_id == PRICE_ZONE_FIELD_ID
        technical = _section(envelope, Axis.TECHNICAL)
        assert PRICE_ZONE_FIELD_ID not in {
            figure.field_id for figure in technical.figures
        }

    def test_window_health_says_what_the_price_zone_was_read_over(self, envelope):
        health = envelope.window_health
        assert health["sessionsUsed"] > 0
        assert health["lastSession"] == TRADING_DAY.isoformat()
        assert health["refusal"] is None
        # The five named fields of Window Health, all present.
        assert health["limitLockDays"] == 0
        assert health["bandRegime"]["exchange"] == Exchange.HOSE.value
        assert health["adjustment"]["applied"] is False
        assert "adtvPercentile" in health

    def test_every_field_the_profile_names_appears(self, envelope):
        named = {
            entry.field_id
            for fields in profile_for(AnalysisIndustry.UNCLASSIFIED).values()
            for entry in fields
        }
        assert named | {PRICE_ZONE_FIELD_ID} == envelope.field_ids

    def test_a_figure_carries_its_unit_kind_source_and_sanctioned_reading(
        self, envelope
    ):
        assert envelope.price_zone.unit == "percent"
        assert envelope.price_zone.kind == "estimator"
        assert envelope.price_zone.source == "computed"
        assert "standard deviation" in envelope.price_zone.interpretation

    def test_the_identity_comes_from_the_stored_register(self, envelope):
        assert envelope.symbol == SYMBOL
        assert envelope.exchange == Exchange.HOSE.value
        assert envelope.trading_day == TRADING_DAY
        assert envelope.industry is AnalysisIndustry.UNCLASSIFIED


class TestTheIndustryBlock:
    def test_a_bank_carries_its_three_metrics_refused(self, stored):
        """The profile names them for a bank, so a bank's artifact names them."""
        built = build_envelope(
            stored,
            SYMBOL,
            TRADING_DAY,
            industry=lambda session, symbol: AnalysisIndustry.BANKS,
            cross_sections={},
        )

        assert built.industry is AnalysisIndustry.BANKS
        for field_id in (
            "bank_metrics.nim_pct",
            "bank_metrics.npl_ratio_pct",
            "bank_metrics.llr_coverage_pct",
        ):
            figure = built.figure(field_id)
            assert figure is not None, field_id
            assert figure.health is Health.REFUSED
            assert figure.value is None
            assert figure.reason_code == SignalIssue.UNAVAILABLE.value

    def test_an_unclassified_symbol_names_no_bank_metric_at_all(self, envelope):
        assert not any(
            field_id.startswith("bank_metrics.") for field_id in envelope.field_ids
        )

    def test_the_industry_is_stamped_on_the_wire(self, stored):
        built = build_envelope(
            stored,
            SYMBOL,
            TRADING_DAY,
            industry=lambda session, symbol: AnalysisIndustry.RETAIL,
            cross_sections={},
        )
        assert built.as_wire()["industry"] == "retail"


class TestTheStoredIndustry:
    """Which block a symbol selects is read off the register, never asked for.

    The resolver is the pipeline's only answer to "what business is this", and
    it has to come from a stored row: the classification a Provider Source could
    answer is exactly the live read the input boundary forbids (spec 0003 §8.1).
    """

    def test_a_bank_in_the_register_carries_the_bank_metrics(self, stored):
        classify(stored, icb_code="8300", icb_name="Ngân hàng")

        built = build_envelope(stored, SYMBOL, TRADING_DAY, cross_sections={})

        assert built.industry is AnalysisIndustry.BANKS
        assert built.as_wire()["industry"] == "banks"
        for field_id in (
            "bank_metrics.nim_pct",
            "bank_metrics.npl_ratio_pct",
            "bank_metrics.llr_coverage_pct",
        ):
            figure = built.figure(field_id)
            assert figure is not None, field_id
            assert figure.health is Health.REFUSED
            assert figure.value is None
            assert figure.reason_code == SignalIssue.UNAVAILABLE.value

    def test_the_profile_version_does_not_move_when_a_block_is_selected(
        self, stored
    ):
        """The profile did not change — only which of its blocks applies."""
        classify(stored, icb_code="8300", icb_name="Ngân hàng")

        built = build_envelope(stored, SYMBOL, TRADING_DAY, cross_sections={})

        assert built.field_profile_version == FIELD_PROFILE_VERSION

    def test_a_classified_symbol_with_no_block_of_its_own_is_other(self, stored):
        classify(stored, icb_code="1700", icb_name="Tài nguyên cơ bản")

        assert stored_industry(stored, SYMBOL) is AnalysisIndustry.OTHER

    def test_a_symbol_the_register_holds_no_code_for_stays_unclassified(self, stored):
        assert stored_industry(stored, SYMBOL) is AnalysisIndustry.UNCLASSIFIED

    def test_a_symbol_the_register_never_carried_stays_unclassified(self, stored):
        """Absent from the register is not classified into nothing special."""
        assert stored_industry(stored, "NOROW") is AnalysisIndustry.UNCLASSIFIED

    def test_it_reads_the_register_however_the_symbol_was_spelled(self, stored):
        classify(stored, icb_code="5300", icb_name="Bán lẻ")

        assert stored_industry(stored, SYMBOL.lower()) is AnalysisIndustry.RETAIL


class TestWhatHasNoComputationBehindIt:
    def test_it_is_refused_unavailable_with_a_null_value(self, envelope):
        for figure in _section(envelope, Axis.NEWS).figures:
            assert figure.health is Health.REFUSED
            assert figure.value is None
            assert figure.reason_code == SignalIssue.UNAVAILABLE.value

    def test_the_news_section_as_a_whole_is_refused(self, envelope):
        assert _section(envelope, Axis.NEWS).health is Health.REFUSED

    def test_a_refused_figure_carries_a_sentence_a_person_can_read(self, envelope):
        for figure in envelope.figures:
            if figure.health is Health.REFUSED:
                assert figure.reason, figure.field_id
                assert figure.reason == SIGNAL_ISSUE_SENTENCES[
                    SignalIssue(figure.reason_code)
                ]

    def test_a_healthy_figure_carries_neither_a_code_nor_a_sentence(self, envelope):
        assert envelope.price_zone.health is Health.OK
        assert envelope.price_zone.reason_code is None
        assert envelope.price_zone.reason is None

    def test_a_refused_figure_can_never_be_cited(self, envelope):
        for figure in envelope.figures:
            if figure.health is Health.REFUSED:
                assert not figure.citable
                assert figure.field_id not in envelope.citable_field_ids


class TestTheInputBoundary:
    """No Provider Source, no live read, and one path to a stored session."""

    # Names no module in the nightly lane may reach, whatever it is imported as.
    # Read off the import statements rather than off a call, because a module
    # that cannot import a live client cannot conditionally call one either.
    FORBIDDEN = (
        "vnstock",
        "fiinquant",
        "news_lane",
        "providers.store",
        "company.service",
        "collector",
    )

    def test_the_envelope_imports_nothing_that_could_reach_a_provider(self):
        assert self._forbidden_imports("src/alpha/envelope.py") == []

    def test_neither_does_the_profile_or_its_prose(self):
        assert self._forbidden_imports("src/alpha/field_profile.py") == []
        assert self._forbidden_imports("src/alpha/reasons.py") == []

    def test_only_prepare_bars_reads_a_stored_session(self):
        """No second reader of `provider_snapshots`, direct or through a store."""
        imported = self._imported_names("src/alpha/envelope.py")
        assert "ProviderSnapshot" not in imported
        assert "SnapshotStore" not in imported
        assert "prepare_bars" in imported

    def test_building_one_reaches_no_live_service(self, stored, monkeypatch):
        """Proven rather than asserted: every live seam explodes if it is reached."""
        import src.core.news_lane as news_lane
        import src.core.vnstock_client as vnstock_client
        import src.stocks.providers.fiinquant as fiinquant

        def forbidden(*args, **kwargs):
            raise AssertionError("the nightly pipeline reached a live service")

        monkeypatch.setattr(news_lane.NewsLane, "read", forbidden, raising=False)
        monkeypatch.setattr(
            "src.stocks.company.service.get_company_service", forbidden
        )
        for factory in ("Listing", "Trading", "Quote", "Company", "Finance", "Market"):
            monkeypatch.setattr(vnstock_client, factory, forbidden)
        monkeypatch.setattr(fiinquant, "_default_session_factory", forbidden)
        monkeypatch.setattr(fiinquant, "shared_session_factory", forbidden)

        built = build_envelope(stored, SYMBOL, TRADING_DAY, cross_sections={})

        assert built.price_zone.health is Health.OK
        assert _section(built, Axis.NEWS).health is Health.REFUSED

    def _forbidden_imports(self, relative: str) -> list[str]:
        source = Path(__file__).parents[1] / relative
        modules: list[str] = []
        for node in ast.walk(ast.parse(source.read_text(), filename=str(source))):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        return [
            module
            for module in modules
            if any(banned in module for banned in self.FORBIDDEN)
        ]

    def _imported_names(self, relative: str) -> set[str]:
        source = Path(__file__).parents[1] / relative
        names: set[str] = set()
        for node in ast.walk(ast.parse(source.read_text(), filename=str(source))):
            if isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names)
        return names


class TestSectionHealth:
    def test_no_usable_figure_refuses_the_section(self):
        assert a_section(Health.REFUSED, Health.REFUSED).health is Health.REFUSED

    def test_all_healthy_is_an_ok_section(self):
        assert a_section(Health.OK, Health.OK, Health.OK).health is Health.OK

    def test_a_usable_figure_beside_a_refused_one_degrades_the_section(self):
        assert a_section(Health.OK, Health.REFUSED).health is Health.DEGRADED

    def test_a_degraded_figure_degrades_the_section(self):
        assert a_section(Health.OK, Health.DEGRADED).health is Health.DEGRADED

    def test_a_caller_has_no_way_to_supply_one(self):
        """It is a property of the figures, so there is nowhere to hand one in."""
        assert isinstance(
            inspect.getattr_static(EvidenceSection, "health"), property
        )
        assert "health" not in EvidenceSection.__dataclass_fields__
        assert "health" not in inspect.signature(build_envelope).parameters


class TestFreshness:
    def test_a_stale_reference_reading_degrades_and_keeps_its_as_of(self):
        session = open_session()
        store_window(session)
        read_on = TRADING_DAY - timedelta(days=REFERENCE_STALE_DAYS + 5)
        store_foreign_room(session, read_on=read_on)

        built = build_envelope(session, SYMBOL, TRADING_DAY, cross_sections={})
        room = built.figure(FOREIGN_ROOM_FIELD)

        assert room.health is Health.DEGRADED
        assert room.reason_code == SignalIssue.STALE_REFERENCE_READING.value
        assert room.value is not None
        assert room.as_of == read_on
        session.close()

    def test_a_fresh_reading_is_ok_and_still_carries_its_stamp(self, envelope):
        room = envelope.figure(FOREIGN_ROOM_FIELD)
        assert room.health is Health.OK
        assert room.as_of == TRADING_DAY

    def test_a_stale_field_still_degrades_only_its_own_section(self):
        session = open_session()
        store_window(session)
        store_foreign_room(
            session, read_on=TRADING_DAY - timedelta(days=REFERENCE_STALE_DAYS + 5)
        )

        built = build_envelope(session, SYMBOL, TRADING_DAY, cross_sections={})

        assert _section(built, Axis.MONEY_FLOW).health is Health.DEGRADED
        assert built.price_zone.health is Health.OK
        session.close()

    def test_a_market_snapshot_for_the_wrong_day_fails_the_run(self):
        session = open_session()
        days = store_window(session)
        store_foreign_room(session)

        with pytest.raises(ProductionFailure) as raised:
            build_envelope(
                session, SYMBOL, days[-1] + timedelta(days=1), cross_sections={}
            )

        assert raised.value.code == "missing_market_snapshot"
        session.close()

    def test_a_refused_figure_keeps_no_stamp_at_all(self, envelope):
        for figure in envelope.figures:
            if figure.health is Health.REFUSED:
                assert figure.as_of is None, figure.field_id


class TestReasonCodes:
    def test_every_reason_code_is_a_signal_issue(self, envelope):
        vocabulary = {issue.value for issue in SignalIssue}
        for figure in envelope.figures:
            if figure.reason_code is not None:
                assert figure.reason_code in vocabulary

    def test_every_signal_issue_has_a_sentence_the_artifact_can_print(self):
        """The set cannot grow past the prose, or a refusal renders blank."""
        assert set(SIGNAL_ISSUE_SENTENCES) == set(SignalIssue)
        for sentence in SIGNAL_ISSUE_SENTENCES.values():
            assert sentence.strip().endswith(".")

    def test_mixed_price_basis_appears_where_a_window_crosses_a_seam(self):
        session = open_session()
        days = weekdays_back(TRADING_DAY, SESSIONS)
        list_on(session, SYMBOL, Exchange.HOSE)
        for index, day in enumerate(days):
            close = 20_000.0 + 40.0 * (index % 7)
            write_session(
                session,
                SYMBOL,
                day,
                close=close,
                high=close * 1.004,
                low=close * 0.996,
                total_value_vnd=8_000_000_000.0,
                market_cap_vnd=2e12,
                # The seam, placed deliberately: one session written adjusted at
                # source, far enough back that the price zone's 21-session
                # window never reaches it and the 250-session drawdown window
                # always does. That is what makes this a test about which
                # windows cross the seam rather than about the whole store.
                basis=(
                    PriceBasis.ADJUSTED_AT_SOURCE
                    if index == SESSIONS - 200
                    else PriceBasis.RAW
                ),
            )
        store_foreign_room(session)

        built = build_envelope(session, SYMBOL, TRADING_DAY, cross_sections={})
        drawdown = built.figure("drawdown_stats.current_drawdown_pct")

        # The price zone's 21-session window is clean, so the run stands and the
        # seam is reported by the fields whose windows actually cross it.
        assert built.price_zone.health is Health.OK
        assert drawdown.health is Health.REFUSED
        assert drawdown.reason_code == SignalIssue.MIXED_PRICE_BASIS.value
        session.close()


class TestReadiness:
    def test_a_refused_price_zone_is_insufficient_core_evidence(self):
        session = open_session()
        # Enough sessions to be a Trading Day, far too few for the price zone.
        store_window(session, count=5)

        with pytest.raises(ProductionFailure) as raised:
            build_envelope(session, SYMBOL, TRADING_DAY, cross_sections={})

        assert raised.value.code == "insufficient_core_evidence"
        assert SignalIssue.INSUFFICIENT_HISTORY.value in raised.value.message
        session.close()

    def test_the_price_zone_alone_is_not_enough_to_publish(self, monkeypatch):
        """One citable figure is a structurally complete artifact saying nothing."""
        session = open_session()
        store_window(session)

        import src.alpha.envelope as envelope_module

        original = envelope_module._from_field_value

        def only_the_zone(entry, served):
            figure = original(entry, served)
            if figure.field_id == PRICE_ZONE_FIELD_ID:
                return figure
            return envelope_module._unavailable(entry)

        monkeypatch.setattr(envelope_module, "_from_field_value", only_the_zone)

        with pytest.raises(ProductionFailure) as raised:
            build_envelope(session, SYMBOL, TRADING_DAY, cross_sections={})

        assert raised.value.code == "insufficient_core_evidence"
        session.close()

    def test_a_ready_pair_can_cite_the_zone_and_something_else(self, envelope):
        assert PRICE_ZONE_FIELD_ID in envelope.citable_field_ids
        assert len(envelope.citable_field_ids) >= 2

    def test_every_refusal_comes_out_of_the_pipeline_taxonomy(self):
        from src.alpha.producer import FAILURE_CODES

        assert {"missing_market_snapshot", "insufficient_core_evidence"} <= (
            FAILURE_CODES
        )


class TestTheFingerprint:
    def test_identical_inputs_produce_an_identical_fingerprint(self, stored):
        first = build_envelope(stored, SYMBOL, TRADING_DAY, cross_sections={})
        second = build_envelope(stored, SYMBOL, TRADING_DAY, cross_sections={})
        assert first.fingerprint() == second.fingerprint()

    def test_it_is_insensitive_to_key_order(self, envelope):
        """A hash over the wire form, so a reordered dictionary is the same input."""
        reordered = dict(reversed(list(envelope.as_wire().items())))
        assert _digest(reordered) == envelope.fingerprint()

    def test_one_changed_figure_changes_it(self, stored):
        """Two stores identical but for the foreign room, and nothing else."""
        before = build_envelope(stored, SYMBOL, TRADING_DAY, cross_sections={})

        other = open_session()
        store_window(other)
        store_foreign_room(other, current=900_000)
        after = build_envelope(other, SYMBOL, TRADING_DAY, cross_sections={})

        assert after.figure(FOREIGN_ROOM_FIELD).value != (
            before.figure(FOREIGN_ROOM_FIELD).value
        )
        assert after.fingerprint() != before.fingerprint()
        other.close()

    def test_a_stored_payload_rehashes_to_the_same_value(self, envelope):
        """What a dispute reads has to hash to what the run recorded."""
        assert _digest(json.loads(json.dumps(envelope.as_wire()))) == (
            envelope.fingerprint()
        )


class TestTheCrossSection:
    def test_a_ranking_nobody_measured_is_not_an_unimplemented_field(self, envelope):
        momentum = envelope.figure(MOMENTUM_FIELD)
        assert momentum.health is Health.REFUSED
        assert momentum.reason_code == SignalIssue.RANKING_UNAVAILABLE.value
        # The registry still owns the reading, which is the difference.
        assert momentum.unit == "percentile"
        assert momentum.interpretation.strip()

    def test_a_measured_ranking_places_the_symbol_in_it(self):
        session = open_session()
        store_window(session)
        store_foreign_room(session)
        store_statement(
            session,
            SYMBOL,
            period_end=TRADING_DAY - timedelta(days=40),
            net_income=4e11,
            equity=1e12,
        )
        peers = store_peers(session)

        rankings = measure_cross_sections(
            session, TRADING_DAY, peers=(SYMBOL,) + peers
        )
        built = build_envelope(
            session,
            SYMBOL,
            TRADING_DAY,
            cross_sections=rankings,
            peers=(SYMBOL,) + peers,
        )
        roe = built.figure(ROE_FIELD)

        assert roe.health is Health.OK
        assert 0.0 <= roe.value <= 100.0
        assert roe.extras["n"] >= min_sample_for(len(PEERS) + 1)
        assert roe.as_of == TRADING_DAY - timedelta(days=40)
        session.close()

    def test_a_percentile_over_an_old_quarter_degrades_and_keeps_the_quarter(self):
        session = open_session()
        store_window(session)
        store_foreign_room(session)
        old = TRADING_DAY - timedelta(days=400)
        store_statement(session, SYMBOL, period_end=old, net_income=4e11, equity=1e12)
        peers = store_peers(session, period_end=old)

        built = build_envelope(
            session,
            SYMBOL,
            TRADING_DAY,
            cross_sections=measure_cross_sections(
                session, TRADING_DAY, peers=(SYMBOL,) + peers
            ),
            peers=(SYMBOL,) + peers,
        )
        roe = built.figure(ROE_FIELD)

        assert roe.health is Health.DEGRADED
        assert roe.reason_code == SignalIssue.STALE_FUNDAMENTAL_PERIOD.value
        assert roe.as_of == old
        session.close()

    def test_the_ranked_fields_are_gathered_across_every_industry(self):
        assert MOMENTUM_FIELD in ranked_field_ids()
        assert ROE_FIELD in ranked_field_ids()
        assert ranked_field_ids() == tuple(sorted(ranked_field_ids()))


class TestTheEntryTheProfileDoesNotHold:
    def test_the_price_zone_entry_is_not_on_an_axis(self):
        entry = price_zone_entry()
        for industry in AnalysisIndustry:
            for fields in profile_for(industry).values():
                assert entry.field_id not in {item.field_id for item in fields}

    def test_it_quotes_the_registry_rather_than_restating_it(self):
        from src.stocks.signals.registry import REGISTRY

        assert (
            price_zone_entry().description
            == REGISTRY[PRICE_ZONE_FIELD_ID].interpretation
        )


def _section(envelope, axis: Axis) -> EvidenceSection:
    return next(section for section in envelope.sections if section.axis is axis)


def _digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
