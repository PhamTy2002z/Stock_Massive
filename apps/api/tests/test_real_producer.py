"""What gets published, what is kept about it, and what can never reach it.

The producer is where backend evidence and model judgment meet, so the tests
here are almost entirely about the seam between them —

*Every displayed number is the backend's.* The model's half of the payload is
prose, an ordering of emphasis and a list of ids. There is no key under
``judgment`` where a fragment-supplied figure could be rendered, and that is
checked structurally rather than by reading the prompt.

*The verdict is the column, not the payload.* The rail shows one word for ten
symbols without opening ten payloads, and the fact lives in exactly one place.

*The audit block is complete or the row is not worth having.* Seven fields, and
an ``inputFingerprint`` that rehashes from the evidence stored beside it — a
dispute reads the row, not this system's word for what the row means.

*No chain-of-thought, and no copy of the prompt.* The figures in the payload are
the evidence snapshot the model saw; the instructions are a constant with a
version stamped beside them.

*The stub is gone from ``src``.* Not deprecated — unimportable, which is the only
version of that guarantee a wrong default cannot get past.

The lifecycle tests run against a live Postgres, because what they prove includes
what the database refuses.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete

from src.alpha.analysis_run import (
    MAX_ATTEMPTS_PER_SESSION,
    RunOrigin,
    RunStatus,
    stored_run,
    write_analysis,
)
from src.alpha.generation import PROMPT_VERSION, SYSTEM_PROMPT, Verdict
from src.alpha.models import Analysis, AnalysisRun, WatchlistEntry
from src.alpha.producer import (
    ANALYSIS_SCHEMA_VERSION,
    AnalysisDraft,
    ProductionFailure,
)
from src.alpha.production import (
    AUDIT_FIELDS,
    analysis_payload,
    analysis_producer,
    produce_pair,
    retry_pair,
)
from src.auth.models import User
from src.core.config import get_settings
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import Exchange, ProviderSource
from src.stocks.providers.contracts import (
    Capability,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SnapshotMetadata,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.universe import forget_cohort_cache

from .test_envelope import SESSIONS, weekdays_back
from .test_generation import MODEL, FakeClient, a_fragment, an_envelope
from .test_price_band import list_on, write_session

SYMBOL = "PRDSYM"
TRADING_DAY = date(2026, 8, 12)
ROUTE = "https://route.test/v1"
GENERATED_AT = datetime(2026, 8, 12, 22, 30, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def alpha_schema():
    Base.metadata.create_all(
        sync_engine,
        tables=[
            Analysis.__table__,
            AnalysisRun.__table__,
            WatchlistEntry.__table__,
            ProviderSnapshot.__table__,
            ListingRoster.__table__,
            CorporateAction.__table__,
        ],
        checkfirst=True,
    )


@pytest.fixture(autouse=True)
def declared_universe(monkeypatch):
    """One symbol in the Universe, so a ranking has nothing to rank against.

    Deliberately thin: every percentile in the artifact then arrives refused for
    ``insufficient_cross_section``, which is what a real evening on a small
    Universe produces and what the envelope has to keep saying honestly.
    """
    monkeypatch.setenv("UNIVERSE_SYMBOLS", SYMBOL)
    get_settings.cache_clear()
    forget_cohort_cache()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()
    forget_cohort_cache()


@pytest.fixture(scope="module", autouse=True)
def stored_market(alpha_schema):
    """One symbol's window, written once for the whole module.

    Three hundred and twenty sessions is what the deepest field in the profile
    declares it needs, and writing them per test would spend more time seeding
    than producing.
    """
    with get_sync_db() as session:
        _wipe_market(session)
        list_on(session, SYMBOL, Exchange.HOSE)
        for index, day in enumerate(weekdays_back(TRADING_DAY, SESSIONS)):
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
            )
        _store_foreign_room(session)
        session.commit()

    yield

    with get_sync_db() as session:
        _wipe_market(session)
        session.commit()


@pytest.fixture(autouse=True)
def clean_runs():
    def wipe() -> None:
        with get_sync_db() as session:
            session.execute(delete(Analysis).where(Analysis.symbol == SYMBOL))
            session.execute(delete(AnalysisRun).where(AnalysisRun.symbol == SYMBOL))

    wipe()
    yield
    wipe()


@pytest.fixture
def session():
    session = sync_session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def watcher():
    created: list[int] = []

    def make(*symbols: str) -> int:
        with get_sync_db() as inner:
            user = User(
                email=f"prd-{uuid.uuid4().hex[:12]}@example.com", hashed_password="x"
            )
            inner.add(user)
            inner.flush()
            for symbol in symbols:
                inner.add(WatchlistEntry(user_id=user.id, symbol=symbol))
            created.append(user.id)
            return user.id

    yield make

    with get_sync_db() as inner:
        for user_id in created:
            inner.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user_id))
            inner.execute(delete(User).where(User.id == user_id))


def _wipe_market(session) -> None:
    session.execute(delete(ProviderSnapshot).where(ProviderSnapshot.symbol == SYMBOL))
    session.execute(delete(ListingRoster).where(ListingRoster.symbol == SYMBOL))


def _store_foreign_room(session) -> None:
    stamp = datetime.combine(TRADING_DAY, time.min, tzinfo=VN_TZ)
    snapshot = ReferenceSnapshot(
        symbol=SYMBOL,
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK, effective_at=stamp, observed_at=stamp
        ),
        shares=(ShareCount(share_type=ShareType.OUTSTANDING, value=1_000_000),),
        current_foreign_room=300_000,
        total_foreign_room=1_000_000,
    )
    session.add(
        ProviderSnapshot(
            capability=Capability.REFERENCE.value,
            symbol=SYMBOL,
            source=ProviderSource.VNSTOCK.value,
            schema_version=1,
            effective_at=stamp,
            observed_at=stamp,
            payload=snapshot.model_dump(mode="json"),
        )
    )


def a_producer(*answers, **overrides):
    """A real producer wired to a scripted route.

    Everything except the model call is the shipped path: the envelope is built
    from the store, the payload is the shipped shape, and only the network is
    fake — a real route would make these tests measure a model.
    """
    client = FakeClient(*(answers or (a_fragment(),)))
    producer = analysis_producer(
        client=client,
        config=_config(),
        session_factory=sync_session_factory,
        clock=lambda: GENERATED_AT,
        **overrides,
    )
    return producer, client


def _config():
    from src.core.llm.config import (
        BudgetLanes,
        LLMConfig,
        LLMRoute,
        PricingTable,
        TokenPrices,
        Workload,
    )

    prices = TokenPrices(
        input=1.0, cached_input=0.1, cache_write=1.25, output=4.0
    )
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url=ROUTE, api_key="test-key"),
        models={Workload.BATCH: MODEL, Workload.SESSION: MODEL},
        pricing=PricingTable(
            version="test",
            effective_from=date(2026, 1, 1),
            batch=prices,
            session=prices,
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=50.0,
            analysis_usd=10.0,
            turn_usd=30.0,
            emergency_usd=5.0,
            eval_usd=5.0,
        ),
    )


def a_payload(**overrides):
    """The payload alone, built from a fixed envelope and a fixed fragment."""
    from src.alpha.generation import validate_fragment

    envelope = overrides.pop("envelope", None) or an_envelope()
    fragment = validate_fragment(a_fragment(**overrides.pop("fragment", {})), envelope)
    return analysis_payload(
        envelope,
        fragment,
        model=overrides.pop("model", MODEL),
        route=overrides.pop("route", ROUTE),
        generated_at=overrides.pop("generated_at", GENERATED_AT),
    )


class TestTheAuditMetadata:
    def test_it_carries_all_seven_fields(self):
        assert tuple(a_payload()["audit"]) == AUDIT_FIELDS
        assert len(AUDIT_FIELDS) == 7

    def test_each_one_says_what_it_was_generated_against(self):
        audit = a_payload()["audit"]

        assert audit["schemaVersion"] == ANALYSIS_SCHEMA_VERSION
        assert audit["fieldProfileVersion"] == an_envelope().field_profile_version
        assert audit["promptVersion"] == PROMPT_VERSION
        assert audit["model"] == MODEL
        assert audit["route"] == ROUTE
        assert audit["generatedAt"] == GENERATED_AT.isoformat()

    def test_the_fingerprint_rehashes_from_the_evidence_stored_beside_it(self):
        """A dispute reads the row rather than trusting what produced it."""
        import hashlib

        payload = a_payload()
        rehashed = hashlib.sha256(
            json.dumps(
                payload["evidence"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        assert payload["audit"]["inputFingerprint"] == rehashed

    def test_a_changed_figure_changes_the_fingerprint(self):
        from dataclasses import replace

        envelope = an_envelope()
        moved = replace(envelope, price_zone=replace(envelope.price_zone, value=99.0))

        assert (
            a_payload(envelope=moved)["audit"]["inputFingerprint"]
            != a_payload(envelope=envelope)["audit"]["inputFingerprint"]
        )


class TestWhatThePayloadMayCarry:
    def test_the_verdict_is_the_column_and_never_the_payload(self):
        payload = a_payload()

        assert "verdict" not in payload["judgment"]
        assert "verdict" not in payload
        assert not _values_under(payload["judgment"], "verdict")

    def test_cited_field_ids_are_stored_complete(self):
        payload = a_payload()

        assert payload["citedFieldIds"] == [
            "realized_volatility.yang_zhang_annualized_pct"
        ]

    def test_the_judgment_half_carries_no_number_at_all(self):
        """A fragment-supplied figure has nowhere in the payload to be rendered."""
        for value in _leaves(a_payload()["judgment"]):
            assert not isinstance(value, (int, float)), value

    def test_every_displayed_number_lives_under_the_evidence(self):
        payload = a_payload()
        numbers = [
            value
            for key, value in _pairs(payload)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]

        assert numbers, "the fixture envelope carries figures"
        for key, value in _pairs(payload["judgment"]):
            assert not isinstance(value, (int, float)) or isinstance(value, bool)

    def test_no_chain_of_thought_and_no_copy_of_the_prompt(self):
        blob = json.dumps(a_payload(), ensure_ascii=False)

        assert SYSTEM_PROMPT[:80] not in blob
        for banned in ("reasoning", "chainOfThought", "thinking", "systemPrompt"):
            assert banned not in blob


class TestPublishing:
    def test_a_seeded_symbol_publishes_and_the_verdict_reaches_the_column(
        self, session
    ):
        producer, client = a_producer()

        outcome = produce_pair(
            session, SYMBOL, TRADING_DAY, origin=RunOrigin.NIGHTLY, producer=producer
        )

        assert outcome.status is RunStatus.READY
        assert outcome.produced is True
        assert outcome.analysis.verdict == Verdict.HOLD.value
        assert outcome.analysis.payload["audit"]["promptVersion"] == PROMPT_VERSION
        assert client.calls == 1

    def test_the_published_evidence_is_the_evidence_that_was_sent(self, session):
        producer, client = a_producer()

        outcome = produce_pair(session, SYMBOL, TRADING_DAY, producer=producer)
        sent = json.loads(client.requests[0].messages[1].content)

        assert outcome.analysis.payload["evidence"] == sent

    def test_a_rerun_of_a_ready_pair_produces_nothing_and_spends_nothing(
        self, session
    ):
        first, _ = a_producer()
        produce_pair(session, SYMBOL, TRADING_DAY, producer=first)

        second, client = a_producer()
        outcome = produce_pair(session, SYMBOL, TRADING_DAY, producer=second)

        assert outcome.produced is False
        assert outcome.status is RunStatus.READY
        assert client.calls == 0

    def test_a_death_between_the_two_writes_is_repaired_without_producing(
        self, session
    ):
        """The Analysis is written first, so a retry finds it and only repairs."""
        producer, _ = a_producer()
        produce_pair(session, SYMBOL, TRADING_DAY, producer=producer)
        published = session.get(Analysis, _analysis_id(session))
        run = stored_run(session, SYMBOL, TRADING_DAY)
        run.status = RunStatus.PRODUCING.value
        session.commit()

        second, client = a_producer()
        outcome = produce_pair(session, SYMBOL, TRADING_DAY, producer=second)

        assert client.calls == 0
        assert outcome.produced is False
        assert outcome.status is RunStatus.READY
        assert outcome.analysis.id == published.id
        assert stored_run(session, SYMBOL, TRADING_DAY).status == RunStatus.READY.value

    def test_a_watcher_retrying_publishes_a_real_analysis(self, session, watcher):
        user_id = watcher(SYMBOL)
        producer, client = a_producer()

        outcome = retry_pair(session, user_id, SYMBOL, TRADING_DAY, producer=producer)

        assert outcome.status is RunStatus.READY
        assert outcome.analysis.verdict in {item.value for item in Verdict}
        assert "stub" not in outcome.analysis.payload
        assert client.calls == 1


class TestFailure:
    def test_a_taxonomy_code_and_a_bounded_one_line_reason_are_stored(self, session):
        def failing(symbol: str, trading_day: date) -> AnalysisDraft:
            raise ProductionFailure(
                "llm_transport_error",
                "route did not respond\nand the second line should not survive\n"
                + "x" * 800,
            )

        outcome = produce_pair(session, SYMBOL, TRADING_DAY, producer=failing)

        assert outcome.status is RunStatus.FAILED
        assert outcome.error_code == "llm_transport_error"
        assert "\n" not in outcome.error_message
        assert len(outcome.error_message) <= 500

    def test_a_pair_with_no_run_row_is_a_persistence_failure(self):
        """Nothing may generate without an owner to charge the spend to."""
        producer, client = a_producer()

        with pytest.raises(ProductionFailure) as raised:
            producer(SYMBOL, TRADING_DAY)

        assert raised.value.code == "persistence_error"
        assert client.calls == 0

    def test_the_ceiling_still_holds_after_three_failed_attempts(self, session):
        def failing(symbol: str, trading_day: date) -> AnalysisDraft:
            raise ProductionFailure("llm_transport_error", "route down")

        for _ in range(MAX_ATTEMPTS_PER_SESSION):
            produce_pair(session, SYMBOL, TRADING_DAY, producer=failing)

        producer, client = a_producer()
        outcome = produce_pair(session, SYMBOL, TRADING_DAY, producer=producer)

        assert outcome.locked is True
        assert client.calls == 0


class TestTheRetiredStub:
    def test_nothing_in_src_can_import_a_stub_producer(self):
        import src.alpha.producer as producer_module

        assert not hasattr(producer_module, "stub_producer")

    def test_no_module_under_src_writes_a_stub_payload(self):
        """The guarantee is that the string does not exist, not that it is unused."""
        root = Path(__file__).resolve().parents[1] / "src"
        offenders = [
            path
            for path in root.rglob("*.py")
            if '"stub"' in path.read_text(encoding="utf-8")
            or "'stub'" in path.read_text(encoding="utf-8")
        ]

        assert offenders == []


class TestTheSynchronousSeam:
    def test_it_refuses_to_run_on_the_event_loop_thread(self):
        """Bridging with asyncio.run is correct only off the loop thread."""
        producer, _ = a_producer()

        async def on_the_loop():
            with pytest.raises(RuntimeError) as raised:
                producer(SYMBOL, TRADING_DAY)
            return str(raised.value)

        message = asyncio.run(on_the_loop())

        assert "off the event loop thread" in message

    def test_the_rankings_are_measured_once_for_a_trading_day(self, session):
        """One producer instance is one cohort's worth of work."""
        import src.alpha.production as production

        measured: list[date] = []
        original = production.measure_cross_sections

        def counting(inner_session, trading_day, **kwargs):
            measured.append(trading_day)
            return original(inner_session, trading_day, **kwargs)

        production.measure_cross_sections = counting
        try:
            producer, _ = a_producer(a_fragment(), a_fragment())
            produce_pair(session, SYMBOL, TRADING_DAY, producer=producer)
            with get_sync_db() as other:
                other.execute(delete(Analysis).where(Analysis.symbol == SYMBOL))
                other.execute(delete(AnalysisRun).where(AnalysisRun.symbol == SYMBOL))
            produce_pair(session, SYMBOL, TRADING_DAY, producer=producer)
        finally:
            production.measure_cross_sections = original

        assert measured == [TRADING_DAY]


def _analysis_id(session) -> int:
    row = session.query(Analysis).filter(Analysis.symbol == SYMBOL).one()
    return row.id


def _pairs(value, key: str = "$"):
    """Every (key, leaf) pair in a nested payload, depth first."""
    if isinstance(value, dict):
        for inner_key, inner in value.items():
            yield from _pairs(inner, f"{key}.{inner_key}")
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            yield from _pairs(inner, f"{key}[{index}]")
    else:
        yield key, value


def _leaves(value):
    return (leaf for _, leaf in _pairs(value))


def _values_under(value, name: str) -> list:
    return [leaf for key, leaf in _pairs(value) if key.endswith(f".{name}")]
