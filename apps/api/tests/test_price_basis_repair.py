"""The one-time repair that stamps a Price Basis on rows written without one.

The migration module is loaded by path and exercised directly, so what the
suite proves is the code that will actually run against the store — not a
re-implementation of it that could drift from the revision.
"""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot
from src.stocks.providers import (
    MARKET_SCHEMA_VERSION,
    Capability,
    MarketSnapshot,
    PriceBasis,
    ProviderSource,
)


def _revision():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "d1f4b7c02e93_stamp_price_basis_on_market_sessions.py"
    )
    spec = importlib.util.spec_from_file_location("price_basis_revision", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


revision = _revision()

SESSION = datetime(2026, 8, 10, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)


def database():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    return engine


def unstamped_payload(source: ProviderSource, effective_at: datetime) -> dict:
    """A market payload exactly as version 1 held it: no basis anywhere in it."""
    return {
        "symbol": "VCB",
        "metadata": {
            "source": source.value,
            "effective_at": effective_at.isoformat(),
            "observed_at": OBSERVED_AT.isoformat(),
            "schema_version": 1,
        },
        "price_unit": "VND",
        "last_price": 59_700,
        "volume": 1_000_000,
        "total_value_vnd": 60_000_000_000,
    }


def row(
    session: Session,
    source: ProviderSource = ProviderSource.FIINQUANT,
    effective_at: datetime = SESSION,
    capability: Capability = Capability.MARKET,
    schema_version: int = 1,
    payload: dict | None = None,
    symbol: str = "VCB",
) -> ProviderSnapshot:
    stored = ProviderSnapshot(
        capability=capability.value,
        symbol=symbol,
        source=source.value,
        effective_at=effective_at,
        observed_at=OBSERVED_AT,
        schema_version=schema_version,
        payload=payload or unstamped_payload(source, effective_at),
    )
    session.add(stored)
    return stored


def market_rows(session: Session) -> list[ProviderSnapshot]:
    return list(
        session.execute(
            select(ProviderSnapshot)
            .where(ProviderSnapshot.capability == Capability.MARKET.value)
            .order_by(ProviderSnapshot.id)
        ).scalars()
    )


def repair(session: Session):
    report = revision.stamp_market_price_basis(session.connection())
    session.commit()
    return report


class TestWhatTheRepairStamps:
    def test_each_source_gets_the_basis_its_rows_have_always_had(self):
        """Keyed on source, which is what settled it for every row so far.

        Every FiinQuant call asked for ``adjusted=False`` and the vnstock quote
        history has no raw option, so no provider is called and nothing is
        re-collected: the rows already are what they are being stamped
        (``docs/adr/0006``).
        """
        engine = database()
        with Session(engine) as session:
            row(session, ProviderSource.FIINQUANT)
            row(session, ProviderSource.VNSTOCK, datetime(2019, 3, 1, tzinfo=timezone.utc))
            session.commit()

            report = repair(session)

            assert report.stamped == 2
            assert [
                (stored.source, stored.payload["price_basis"], stored.schema_version)
                for stored in market_rows(session)
            ] == [
                ("fiinquant", "raw", MARKET_SCHEMA_VERSION),
                ("vnstock", "adjusted_at_source", MARKET_SCHEMA_VERSION),
            ]

    def test_the_version_inside_the_payload_moves_with_the_column(self):
        """The payload keeps its own copy, and a disagreement is a second row.

        ``SnapshotStore.save`` looks a session up by ``metadata.schema_version``
        and writes the column from it, so a repaired row still saying 1 inside
        would be inserted beside itself the next time anything round-tripped it
        — the exact duplication this repair exists to avoid.
        """
        engine = database()
        with Session(engine) as session:
            row(session)
            session.commit()
            repair(session)

            stored = market_rows(session)[0]

            assert stored.schema_version == MARKET_SCHEMA_VERSION
            assert stored.payload["metadata"]["schema_version"] == MARKET_SCHEMA_VERSION

    def test_a_stamped_payload_reads_back_as_a_market_snapshot(self):
        """The repair's output is the contract's input, or it has repaired nothing.

        A payload that still fails validation would leave every reader of that
        session refusing it just as loudly as before.
        """
        engine = database()
        with Session(engine) as session:
            row(session)
            session.commit()
            repair(session)

            snapshot = MarketSnapshot.model_validate(market_rows(session)[0].payload)

            assert snapshot.price_basis is PriceBasis.RAW
            # Nothing else moved: the repair says what the numbers mean, it does
            # not touch the numbers.
            assert snapshot.last_price == 59_700
            assert snapshot.volume == 1_000_000
            assert snapshot.total_value_vnd == 60_000_000_000

    def test_nothing_but_the_market_capability_is_touched(self):
        """Only market prices have a basis.

        A ratio and a share count are not prices, and stamping them would put a
        field on rows whose contracts forbid unknown ones — a 500 on the next
        read rather than a repair.
        """
        engine = database()
        with Session(engine) as session:
            row(session, capability=Capability.VALUATION, payload={"provider_pe": 12.5})
            row(session, capability=Capability.FUNDAMENTAL, payload={"period_end": "2026-06-30"})
            session.commit()

            assert repair(session).stamped == 0
            untouched = list(
                session.execute(select(ProviderSnapshot)).scalars()
            )
            assert [stored.schema_version for stored in untouched] == [1, 1]
            assert all("price_basis" not in stored.payload for stored in untouched)

    def test_a_source_with_no_known_basis_stops_the_repair(self):
        """An invented basis is worse than an unstamped row.

        Stamped wrongly, the row is read as a measurement it never was by every
        window that follows, and nothing later can tell.
        """
        engine = database()
        with Session(engine) as session:
            stored = row(session)
            stored.source = "some_new_provider"
            session.commit()

            with pytest.raises(RuntimeError, match="some_new_provider"):
                revision.stamp_market_price_basis(session.connection())


class TestRunningItMoreThanOnce:
    def test_a_second_run_finds_nothing_and_says_so(self):
        engine = database()
        with Session(engine) as session:
            row(session)
            row(session, effective_at=datetime(2026, 8, 7, tzinfo=timezone.utc))
            session.commit()

            first = repair(session)
            before = [stored.payload for stored in market_rows(session)]
            second = repair(session)

            assert (first.stamped, second.stamped) == (2, 0)
            assert [stored.payload for stored in market_rows(session)] == before

    def test_no_market_row_is_left_at_the_unstamped_version(self):
        """The exit condition of the whole ticket, asserted as a count.

        One row left behind is one window that fails validation at read time,
        and it would fail for a reader who has no way to know why.
        """
        engine = database()
        with Session(engine) as session:
            for day in (7, 10):
                row(session, effective_at=datetime(2026, 8, day, tzinfo=timezone.utc))
            row(session, ProviderSource.VNSTOCK, datetime(2019, 3, 1, tzinfo=timezone.utc))
            session.commit()

            repair(session)

            remaining = session.execute(
                select(func.count())
                .select_from(ProviderSnapshot)
                .where(
                    ProviderSnapshot.capability == Capability.MARKET.value,
                    ProviderSnapshot.schema_version == 1,
                )
            ).scalar_one()
            assert remaining == 0


class TestNoSecondRowBesideTheFirst:
    def test_the_row_count_does_not_move(self):
        """An update, not a re-collection.

        ``schema_version`` is part of ``uq_provider_snapshot_identity``, so a
        re-fetch under 2 would leave the version-1 row in place and add its
        stamped twin — every session in the store, twice.
        """
        engine = database()
        with Session(engine) as session:
            for day in (6, 7, 10):
                row(session, effective_at=datetime(2026, 8, day, tzinfo=timezone.utc))
            session.commit()

            repair(session)

            assert len(market_rows(session)) == 3

    def test_a_session_re_collected_before_the_repair_ran_keeps_one_row(self):
        """The collector may ship before the repair runs, and then both exist.

        Stamping the old row in place would break the identity constraint;
        leaving it would keep a session this system cannot read. It is dropped,
        because the stamped row is the same session written by an adapter that
        knows its own basis first-hand.
        """
        engine = database()
        with Session(engine) as session:
            row(session)
            fresh = unstamped_payload(ProviderSource.FIINQUANT, SESSION)
            fresh["price_basis"] = "raw"
            fresh["metadata"]["schema_version"] = MARKET_SCHEMA_VERSION
            row(session, schema_version=MARKET_SCHEMA_VERSION, payload=fresh)
            session.commit()

            report = repair(session)

            assert (report.stamped, report.superseded) == (0, 1)
            surviving = market_rows(session)
            assert len(surviving) == 1
            assert surviving[0].schema_version == MARKET_SCHEMA_VERSION

    def test_the_store_still_refuses_a_duplicate_identity_afterwards(self):
        """The constraint the repair works around is still doing its job."""
        engine = database()
        with Session(engine) as session:
            row(session)
            session.commit()
            repair(session)

            row(session, schema_version=MARKET_SCHEMA_VERSION)
            with pytest.raises(IntegrityError):
                session.commit()


class TestPuttingItBack:
    def test_a_downgrade_leaves_the_payloads_as_version_one_held_them(self):
        engine = database()
        with Session(engine) as session:
            before = unstamped_payload(ProviderSource.FIINQUANT, SESSION)
            row(session, payload=dict(before))
            session.commit()
            repair(session)

            restored_count = revision.unstamp_market_price_basis(session.connection())
            session.commit()

            restored = market_rows(session)[0]
            assert restored_count == 1
            assert restored.schema_version == 1
            assert restored.payload == before


class TestTheMigrationAndTheContractStayInStep:
    def test_the_spelled_out_names_are_the_ones_the_contract_uses(self):
        """The revision spells these out rather than importing them.

        That is deliberate — a migration records what the data looked like on
        the day it ran — so the check that they still agree belongs here, where
        a rename shows up as a failing test rather than as a repair that stamps
        a basis nothing recognises.
        """
        assert revision.BASIS_BY_SOURCE == {
            ProviderSource.FIINQUANT.value: PriceBasis.RAW.value,
            ProviderSource.VNSTOCK.value: PriceBasis.ADJUSTED_AT_SOURCE.value,
        }
        assert revision.STAMPED_SCHEMA_VERSION == MARKET_SCHEMA_VERSION
        assert revision.MARKET == Capability.MARKET.value
        assert revision.PRICE_BASIS_KEY in MarketSnapshot.model_fields
