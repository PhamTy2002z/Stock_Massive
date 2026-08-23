"""What the Analysis lane's loop bought, measured from rows that already exist.

The loop adds one behaviour: met with a figure the store refused, go and find a
usable substitute. So the measurement is that behaviour, and the tests here are
mostly about the two ways a rate like it is read wrongly:

*The denominator is not every Analysis.* An Analysis whose seed held no refusal
was never asked to substitute. Counting it would produce a number that falls
whenever the store gets better, which is the opposite of what it is for.

*Not looking is a failure, not an absence.* An Analysis with a refused seed
figure and no tool call at all belongs in the denominator. The model deciding
there was nothing worth asking is precisely the outcome under measurement.

Beside those, one number that can fall while the others rise: how much of the
usable evidence the verdict actually rested on. A loop fetching more figures and
citing fewer of them is buying data it does not use, and the one-shot baseline to
read it against is 47.7% of usable figures uncited.

Every count here is exact, so this file gets its own throwaway Postgres. And
``payload`` is JSONB, so SQLite could not stand in even if the counts did not
matter.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.alpha.analysis_reads import (
    REFUSED_HEALTH,
    SUBSTITUTION_CAVEAT,
    cited_figure_rate,
    round_yield,
    substitution_rate,
)
from src.alpha.analysis_run import RunOrigin, RunStatus
from src.alpha.models import Analysis, AnalysisRun, AnalysisToolCall
from src.core.database import Base

from .throwaway_db import create_database, drop_database

LOOP_DB = "stockmassive_loop_measure_test"

SESSION = date(2026, 8, 12)
EARLIER = date(2026, 8, 11)
OUTSIDE = date(2026, 7, 1)
NOW = datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)

SEEDED = "indicator_pack.rsi_14"
DEEP = "drawdown_stats.current_drawdown_pct"
SHALLOW = "realized_volatility.yang_zhang_20d"


@pytest.fixture(scope="module")
def session_factory():
    url = create_database(LOOP_DB)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False, future=True)
    engine.dispose()
    drop_database(LOOP_DB)


@pytest.fixture
def store(session_factory):
    """One empty store per test, so a count is a count."""
    with session_factory() as session:
        for model in (AnalysisToolCall, Analysis, AnalysisRun):
            session.query(model).delete()
        session.commit()
    return _Store(session_factory)


def figure(field_id: str, *, health: str = "ok") -> dict:
    """One figure as ``EvidenceFigure.as_wire`` renders it, trimmed to what is read."""
    return {
        "fieldId": field_id,
        "label": field_id,
        "value": None if health == REFUSED_HEALTH else 51.4,
        "unit": "ratio",
        "kind": "level",
        "health": health,
        "reasonCode": "insufficient_history" if health == REFUSED_HEALTH else None,
        "asOf": None if health == REFUSED_HEALTH else SESSION.isoformat(),
    }


class _Store:
    """The smallest store an Analysis and its trace can exist in."""

    def __init__(self, session_factory) -> None:
        self._factory = session_factory

    def session(self):
        return self._factory()

    def analysis(
        self,
        symbol: str,
        *,
        trading_day: date = SESSION,
        figures: tuple[dict, ...] = (),
        zone: dict | None = None,
        cited: tuple[str, ...] = (),
        fetched: tuple[tuple[str, str], ...] = (),
        calls: tuple[tuple[str, str], ...] = (),
    ) -> None:
        """One Analysis, its run, and the trace of what it asked for.

        ``fetched`` is ``(field_id, health)`` pairs the loop read mid-flight: each
        one becomes both a successful ``get_field`` in the trace and a figure in
        the payload, which is what a real fetched figure is. ``calls`` is
        ``(tool_name, status)`` pairs for trace rows that produced no figure.
        """
        payload = {
            "evidence": {
                "priceZone": zone if zone is not None else figure("price_zone.close"),
                "sections": [
                    {
                        "axis": "technical",
                        "health": "ok",
                        "figures": [*figures, *(figure(fid, health=h) for fid, h in fetched)],
                    }
                ],
            },
            "citedFieldIds": list(cited),
        }
        with self.session() as session:
            run = AnalysisRun(
                symbol=symbol,
                trading_day=trading_day,
                status=RunStatus.READY.value,
                origin=RunOrigin.NIGHTLY.value,
                attempts=1,
            )
            session.add(run)
            session.flush()
            session.add(
                Analysis(
                    symbol=symbol,
                    trading_day=trading_day,
                    verdict="neutral",
                    payload=payload,
                    schema_version=1,
                )
            )
            seq = 0
            for field_id, health in fetched:
                seq += 1
                session.add(
                    AnalysisToolCall(
                        run_id=run.id,
                        round_index=0,
                        seq=seq,
                        tool_name="get_field",
                        arguments={"field_id": field_id},
                        result=figure(field_id, health=health),
                        status="ok",
                        started_at=NOW,
                    )
                )
            for tool_name, status in calls:
                seq += 1
                session.add(
                    AnalysisToolCall(
                        run_id=run.id,
                        round_index=0,
                        seq=seq,
                        tool_name=tool_name,
                        arguments={},
                        result=None if status != "ok" else {"count": 30},
                        status=status,
                        started_at=NOW,
                    )
                )
            session.commit()

    def substitution(self, *, since: date = EARLIER, until: date = SESSION):
        with self.session() as session:
            return substitution_rate(session, since, until)

    def rounds(self, *, since: date = EARLIER, until: date = SESSION):
        with self.session() as session:
            return round_yield(session, since, until)

    def cited(self, *, since: date = EARLIER, until: date = SESSION):
        with self.session() as session:
            return cited_figure_rate(session, since, until)


class TestWhoIsInTheDenominator:
    def test_an_analysis_with_no_refused_seed_figure_is_not_eligible(self, store):
        """Nothing was refused, so nothing was asked for. Not a failure."""
        store.analysis("AAA", figures=(figure(SEEDED),), cited=(SEEDED,))

        reading = store.substitution()

        assert reading.analyses == 1
        assert reading.eligible == 0
        assert reading.rate is None

    def test_a_refused_seed_figure_with_no_tool_call_is_a_failure(self, store):
        """Deciding there was nothing worth asking is the outcome measured."""
        store.analysis("AAA", figures=(figure(DEEP, health=REFUSED_HEALTH),))

        reading = store.substitution()

        assert reading.eligible == 1
        assert reading.substituted == 0
        assert reading.rate == 0.0

    def test_a_refusal_answered_with_a_cited_usable_figure_is_a_substitution(
        self, store
    ):
        store.analysis(
            "AAA",
            figures=(figure(DEEP, health=REFUSED_HEALTH),),
            fetched=((SHALLOW, "ok"),),
            cited=(SHALLOW,),
        )

        reading = store.substitution()

        assert reading.eligible == 1
        assert reading.substituted == 1
        assert reading.rate == 1.0

    def test_a_degraded_substitute_still_counts(self, store):
        """Degraded is a reading with a named condition, and it may be cited."""
        store.analysis(
            "AAA",
            figures=(figure(DEEP, health=REFUSED_HEALTH),),
            fetched=((SHALLOW, "degraded"),),
            cited=(SHALLOW,),
        )

        assert store.substitution().substituted == 1

    def test_a_fetched_figure_nobody_cited_is_not_a_substitution(self, store):
        """Fetching is not substituting. The verdict has to rest on it."""
        store.analysis(
            "AAA",
            figures=(figure(DEEP, health=REFUSED_HEALTH),),
            fetched=((SHALLOW, "ok"),),
            cited=(SEEDED,),
        )

        assert store.substitution().substituted == 0

    def test_a_fetched_figure_that_came_back_refused_is_not_a_substitution(self, store):
        """A refused figure can never support a verdict, however it arrived."""
        store.analysis(
            "AAA",
            figures=(figure(DEEP, health=REFUSED_HEALTH),),
            fetched=((SHALLOW, REFUSED_HEALTH),),
            cited=(SHALLOW,),
        )

        assert store.substitution().eligible == 1
        assert store.substitution().substituted == 0

    def test_a_fetched_figure_does_not_itself_make_an_analysis_eligible(self, store):
        """Eligibility is about the *seed*, and a fetched figure is not seed.

        Without the trace there is no way to tell one from the other in a stored
        payload, and a refused fetch counted as a seed refusal would make the
        loop create its own denominator.
        """
        store.analysis(
            "AAA",
            figures=(figure(SEEDED),),
            fetched=((SHALLOW, REFUSED_HEALTH),),
            cited=(SEEDED,),
        )

        assert store.substitution().eligible == 0

    def test_core_evidence_counts_as_a_seed_figure(self, store):
        """``priceZone`` sits beside the sections, not inside one."""
        store.analysis("AAA", zone=figure("price_zone.close", health=REFUSED_HEALTH))

        assert store.substitution().eligible == 1


class TestTheWindow:
    def test_it_is_inclusive_at_both_ends(self, store):
        store.analysis("AAA", trading_day=EARLIER, figures=(figure(SEEDED),))
        store.analysis("BBB", trading_day=SESSION, figures=(figure(SEEDED),))

        assert store.substitution().analyses == 2

    def test_a_session_outside_it_is_not_counted(self, store):
        store.analysis("AAA", trading_day=OUTSIDE, figures=(figure(SEEDED),))

        assert store.substitution().analyses == 0

    def test_an_empty_window_answers_zero_rather_than_failing(self, store):
        reading = store.substitution(since=OUTSIDE, until=OUTSIDE)

        assert reading.analyses == 0
        assert reading.eligible == 0
        assert reading.rate is None
        assert store.rounds(since=OUTSIDE, until=OUTSIDE).rate is None
        assert store.cited(since=OUTSIDE, until=OUTSIDE).rate is None


class TestTheRoundYield:
    def test_a_call_that_returned_a_usable_figure_is_useful(self, store):
        store.analysis("AAA", fetched=((SHALLOW, "ok"),))

        reading = store.rounds()

        assert reading.calls == 1
        assert reading.useful == 1

    def test_a_call_that_returned_a_refused_figure_spent_a_round(self, store):
        """It succeeded as a call and failed as a question.

        The status column only knows the first, which is why this is judged on
        the figure's health.
        """
        store.analysis("AAA", fetched=((DEEP, REFUSED_HEALTH),))

        reading = store.rounds()

        assert reading.calls == 1
        assert reading.useful == 0

    def test_a_failed_call_is_not_useful(self, store):
        store.analysis("AAA", calls=(("get_field", "tool_error"),))

        assert store.rounds().useful == 0

    def test_a_catalog_listing_is_useful_by_succeeding(self, store):
        """It carries no health because it is not a field read."""
        store.analysis("AAA", calls=(("list_fields", "ok"),))

        reading = store.rounds()

        assert reading.calls == 1
        assert reading.useful == 1

    def test_an_analysis_that_called_nothing_contributes_no_calls(self, store):
        store.analysis("AAA", figures=(figure(SEEDED),))

        assert store.rounds().calls == 0


class TestTheCitedFigureRate:
    def test_it_counts_usable_figures_and_the_ones_the_verdict_named(self, store):
        store.analysis(
            "AAA",
            figures=(figure(SEEDED), figure(SHALLOW), figure(DEEP, health=REFUSED_HEALTH)),
            cited=(SEEDED,),
        )

        reading = store.cited()

        # Two usable in the section plus the price zone; the refused one is not
        # in the denominator because it could never have been cited.
        assert reading.usable == 3
        assert reading.cited == 1

    def test_a_cited_id_naming_nothing_in_the_payload_moves_nothing(self, store):
        """The denominator is figures, so an id with no figure cannot inflate it."""
        store.analysis("AAA", figures=(figure(SEEDED),), cited=("gone.away",))

        reading = store.cited()

        assert reading.usable == 2
        assert reading.cited == 0

    def test_a_fetched_figure_is_counted_like_a_seeded_one(self, store):
        """Downstream a fetched figure is indistinguishable, and should be."""
        store.analysis("AAA", fetched=((SHALLOW, "ok"),), cited=(SHALLOW,))

        reading = store.cited()

        assert reading.cited == 1


class TestHowTheNumberIsPresented:
    def test_the_caveat_travels_with_the_rate(self, store):
        """A rate read as a quality score is worse than no rate at all."""
        store.analysis("AAA", figures=(figure(DEEP, health=REFUSED_HEALTH),))

        wire = store.substitution().as_wire()

        assert wire["caveat"] == SUBSTITUTION_CAVEAT
        assert "does not prove an Analysis is correct" in wire["caveat"]

    def test_no_reading_stores_a_rate_it_derived(self, store):
        """Counts are stored and percentages are properties, so two readers
        cannot disagree about the denominator of a number in a response."""
        store.analysis("AAA", figures=(figure(DEEP, health=REFUSED_HEALTH),))

        for reading in (store.substitution(), store.rounds(), store.cited()):
            assert "rate" not in reading.__dataclass_fields__

    def test_reading_writes_nothing(self, store):
        store.analysis("AAA", figures=(figure(DEEP, health=REFUSED_HEALTH),))
        with store.session() as session:
            before = session.query(AnalysisToolCall).count(), session.query(
                Analysis
            ).count()

        store.substitution()
        store.rounds()
        store.cited()

        with store.session() as session:
            after = session.query(AnalysisToolCall).count(), session.query(
                Analysis
            ).count()
        assert before == after


class TestTheEndpoint:
    """The route is a thin read: admin-only, no threshold, three numbers.

    It reads the dev store rather than this module's throwaway one, so what is
    asserted here is the shape and the gate. The arithmetic is above, where the
    counts are exact.
    """

    @staticmethod
    def _get(url: str):
        from fastapi.testclient import TestClient

        from src.auth.dependencies import require_admin
        from src.main import app

        app.dependency_overrides[require_admin] = lambda: None
        try:
            return TestClient(app).get(url)
        finally:
            app.dependency_overrides.clear()

    def test_it_needs_an_admin(self):
        from fastapi.testclient import TestClient

        from src.main import app

        response = TestClient(app).get("/api/v1/ops/analysis-loop")

        assert response.status_code in {401, 403}

    def test_it_returns_the_three_numbers_and_the_window_it_read(self):
        response = self._get(
            "/api/v1/ops/analysis-loop?since=2026-08-11&until=2026-08-12"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["since"] == "2026-08-11"
        assert body["until"] == "2026-08-12"
        assert set(body) == {
            "since",
            "until",
            "substitution",
            "roundYield",
            "citedFigures",
        }

    def test_it_states_no_verdict_on_the_numbers_it_returns(self):
        """No healthy boolean and no threshold, deliberately: nobody is rostered
        to answer an alert, and a substitution rate is not a quality score."""
        body = self._get("/api/v1/ops/analysis-loop").json()

        assert "healthy" not in body
        assert "status" not in body
        assert "threshold" not in str(body)
        assert body["substitution"]["caveat"] == SUBSTITUTION_CAVEAT

    def test_a_backwards_window_is_read_forwards_rather_than_empty(self):
        """An inverted range is a typo, and answering it with zero rows would
        look exactly like a quiet month."""
        body = self._get(
            "/api/v1/ops/analysis-loop?since=2026-08-12&until=2026-08-11"
        ).json()

        assert body["since"] == "2026-08-11"
        assert body["until"] == "2026-08-12"
